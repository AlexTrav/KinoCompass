import hashlib
import io
import zipfile

import pandas as pd
import pytest
import requests

from collect import movielens, net, tmdb, wikidata
from collect.config import POSTERS_COLUMNS, TITLES_COLUMNS
from collect.store import load, save


class FakeResponse:
    def __init__(self, status: int, headers: dict | None = None):
        self.status_code = status
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)


# --- повторы HTTP ---------------------------------------------------------------------------------------------

def test_request_retries_5xx_then_succeeds(monkeypatch):
    answers = iter([FakeResponse(503), FakeResponse(429, {"Retry-After": "1"}), FakeResponse(200)])
    pauses = []
    monkeypatch.setattr(net.requests, "request", lambda *a, **k: next(answers))
    monkeypatch.setattr(net.time, "sleep", pauses.append)
    assert net.request("GET", "https://example.org").status_code == 200
    assert len(pauses) == 2 and pauses[1] >= 1


def test_request_404_and_4xx(monkeypatch):
    monkeypatch.setattr(net.requests, "request", lambda *a, **k: FakeResponse(404))
    assert net.request("GET", "https://example.org", allow_404=True) is None
    with pytest.raises(requests.HTTPError):
        net.request("GET", "https://example.org")


# --- набор MovieLens в памяти ---------------------------------------------------------------------------------

# маленький архив в формате ml-32m: те же файлы и колонки, теги с запятой и кавычками внутри поля
CSV = {
    "ratings.csv": "userId,movieId,rating,timestamp\n1,1,4.0,944006400\n1,2,3.5,1696982400\n",
    "tags.csv": 'userId,movieId,tag,timestamp\n1,1,"funny, witty",944006400\n2,1,"say ""hi""",944006400\n',
    "movies.csv": 'movieId,title,genres\n1,"Matrix, The (1999)",Action|Sci-Fi\n2,Heat (1995),Crime\n',
    "links.csv": "movieId,imdbId,tmdbId\n1,0133093,603\n2,0113277,\n",
    "README.txt": "Usage License\n",
}


def _fake_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in CSV.items():
            archive.writestr(f"ml-32m/{name}", text)
    return buffer.getvalue()


class Stream(FakeResponse):
    # ответ с телом content; break_at – после стольких байт соединение «рвётся», как у GroupLens
    def __init__(self, content: bytes, status: int = 200, break_at: int | None = None):
        super().__init__(status, {"Content-Length": str(len(content))})
        self.content, self.break_at = content, break_at

    def iter_content(self, size):
        for start in range(0, len(self.content), 100):
            if self.break_at is not None and start >= self.break_at:
                raise requests.exceptions.ChunkedEncodingError("Connection broken: IncompleteRead")
            yield self.content[start: start + 100]


@pytest.mark.parametrize("resume_status", [206, 200])
def test_fetch_archive_resumes_after_break(monkeypatch, resume_status):
    content = _fake_zip()
    calls = []

    def fake_request(method, url, stream=False, headers=None):
        calls.append(headers)
        if len(calls) == 1:
            return Stream(content, break_at=300)
        start = int(headers["Range"][6:-1]) if resume_status == 206 else 0
        return Stream(content[start:], status=resume_status)

    monkeypatch.setattr(movielens, "request", fake_request)
    monkeypatch.setattr(movielens.time, "sleep", lambda s: None)
    archive = movielens.fetch_archive(expected=hashlib.md5(content).hexdigest())
    assert calls == [None, {"Range": "bytes=300-"}]  # докачка с места обрыва
    assert movielens.read_text(archive, "README.txt") == "Usage License\n"  # md5 сошёлся и при 206, и при 200


def test_fetch_archive_checks_md5(monkeypatch):
    content = _fake_zip()
    monkeypatch.setattr(movielens, "request", lambda *a, **k: Stream(content))
    archive = movielens.fetch_archive(expected=hashlib.md5(content).hexdigest())
    assert movielens.read_text(archive, "README.txt") == "Usage License\n"
    with pytest.raises(SystemExit, match="контрольная сумма"):
        movielens.fetch_archive(expected="0" * 32)


def test_load_reads_tables_from_archive():
    frames = movielens.load(zipfile.ZipFile(io.BytesIO(_fake_zip())))
    ratings, tags, links = frames["ratings"], frames["tags"], frames["links"]
    assert list(ratings.columns) == ["user_id", "movie_id", "rating", "time"]
    assert str(ratings["user_id"].dtype) == "int32" and str(ratings["rating"].dtype) == "float32"
    assert ratings["time"].iloc[0] == pd.Timestamp("1999-12-01", tz="UTC")
    assert tags["tag"].tolist() == ["funny, witty", 'say "hi"']
    assert links["imdb_id"].tolist() == ["0133093", "0113277"] and pd.isna(links["tmdb_id"].iloc[1])
    assert frames["movies"]["title"].iloc[0] == "Matrix, The (1999)"


# --- кэш названий и постеров ----------------------------------------------------------------------------------

def test_store_roundtrip_keeps_empty_strings(tmp_path):
    catalog = pd.DataFrame({"movie_id": [1, 2]})
    frame = pd.DataFrame({"movie_id": [2, 1, 9, 1], "wikidata": ["Q2", "", "Q9", "Q1"], "title_ru": ["Б", "", "", "А"],
                          "title_kk": ["", "", "", ""], "title_en": ["B", "", "", "A"]})
    save(frame, tmp_path / "t.csv", catalog)
    back = load(tmp_path / "t.csv", TITLES_COLUMNS)
    assert back["movie_id"].tolist() == [1, 2]  # фильма 9 нет в каталоге, у фильма 1 – последняя запись
    assert back.loc[0, "wikidata"] == "Q1" and back.loc[1, "title_kk"] == ""


# --- Wikidata -------------------------------------------------------------------------------------------------

def _binding(imdb: str, qid: str, lang: str | None = None, label: str | None = None) -> dict:
    row = {"imdb": {"value": imdb}, "item": {"value": f"http://www.wikidata.org/entity/{qid}"}}
    if lang:
        row |= {"lang": {"value": lang}, "label": {"value": label}}
    return row


def test_build_query_rejects_injection():
    assert '"tt0133093"' in wikidata.build_query(["tt0133093"])
    with pytest.raises(ValueError):
        wikidata.build_query(['tt1" } DROP'])


def test_parse_bindings_prefers_kk_and_oldest_item():
    frame = wikidata.parse_bindings([
        _binding("tt0133093", "Q83495", "ru", "Матрица"),
        _binding("tt0133093", "Q83495", "kk-cyrl", "Матрица (kk-cyrl)"),
        _binding("tt0133093", "Q83495", "kk", "Матрица (kk)"),
        _binding("tt0133093", "Q99999999", "ru", "Дубль"),
        _binding("tt0114369", "Q190908"),
    ]).set_index("imdb_id")
    assert frame.loc["tt0133093", "wikidata"] == "Q83495"
    assert frame.loc["tt0133093", "title_ru"] == "Матрица" and frame.loc["tt0133093", "title_kk"] == "Матрица (kk)"
    assert frame.loc["tt0114369", "title_ru"] == "" and frame.loc["tt0114369", "wikidata"] == "Q190908"


@pytest.mark.parametrize("label, expected", [
    ("Жеті (фильм)", "Жеті"),
    ("Дюна (фильм, 2021)", "Дюна"),
    ("Король Лев (мультфильм)", "Король Лев"),
    ("Граф Монте-Кристо (фильм 1934 года)", "Граф Монте-Кристо"),
    ("Игра с огнём (фильм-триллер, 2019)", "Игра с огнём"),
    ("Heat (1995 film)", "Heat"),
    ("Matrix (Film)", "Matrix"),
    ("Get Out (and Don't Come Back!!)", "Get Out (and Don't Come Back!!)"),
    ("Филмография", "Филмография"),
])
def test_clean_label(label, expected):
    assert wikidata.clean_label(label) == expected


def test_clean_label_replaces_em_dash():
    assert wikidata.clean_label(f"Я {chr(0x2014)} легенда") == "Я – легенда"


def test_update_titles_only_new_and_marks_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(wikidata.time, "sleep", lambda s: None)
    catalog = pd.DataFrame({"movie_id": [1, 2, 3], "imdb_id": ["tt0133093", "tt0114369", None]})
    path = tmp_path / "titles.csv"
    save(pd.DataFrame([[1, "Q83495", "Матрица", "", "The Matrix"]], columns=TITLES_COLUMNS), path, catalog)
    asked = []

    def fake_fetch(ids):
        asked.extend(ids)
        return wikidata.parse_bindings([])

    titles = wikidata.update_titles(catalog, path, fetch_batch=fake_fetch)
    assert asked == ["tt0114369"]  # фильм 1 уже есть, у фильма 3 нет IMDb id
    assert titles["movie_id"].tolist() == [1, 2] and titles.loc[1, "wikidata"] == ""


# --- TMDb -----------------------------------------------------------------------------------------------------

def test_tmdb_requires_token(monkeypatch):
    monkeypatch.delenv("TMDB_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="TMDB_TOKEN"):
        tmdb.auth_headers()


def test_update_posters_skips_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("TMDB_TOKEN", "test")
    catalog = pd.DataFrame({"movie_id": [1, 2, 3, 4], "tmdb_id": pd.array([603, 807, None, 5], dtype="Int64")})

    def fake_get(tmdb_id, headers):
        assert headers["Authorization"] == "Bearer test"
        if tmdb_id == 5:
            raise requests.ConnectionError("сеть")
        return {603: "/m.jpg", 807: ""}[tmdb_id]

    posters, errors = tmdb.update_posters(catalog, tmp_path / "p.csv", get=fake_get)
    assert errors == 1
    assert posters[POSTERS_COLUMNS].values.tolist() == [[1, "603", "/m.jpg"], [2, "807", ""]]


def test_update_posters_stops_on_bad_token(tmp_path, monkeypatch):
    monkeypatch.setenv("TMDB_TOKEN", "bad")
    catalog = pd.DataFrame({"movie_id": [1, 2], "tmdb_id": pd.array([603, 807], dtype="Int64")})

    def fake_get(tmdb_id, headers):
        raise requests.HTTPError("401", response=FakeResponse(401))

    with pytest.raises(SystemExit, match="401"):
        tmdb.update_posters(catalog, tmp_path / "p.csv", get=fake_get)
