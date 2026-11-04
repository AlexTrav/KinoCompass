import numpy as np
import pandas as pd

from .config import EXPECTED, FIRST_DAY, GENRES, LAST_DAY, MIN_RATINGS


def _count(name: str, actual: int, expected: dict | None) -> list[str]:
    if expected is None or actual == expected[name]:
        return []
    return [f"{name}: {actual} вместо {expected[name]} по README набора"]


# оценки: число строк и пользователей как в README, шкала 0,5–5 с шагом 0,5, даты в периоде набора,
# одна оценка на пару «пользователь – фильм», все фильмы есть в movies. expected=None – без сверки с README.
# На 32 млн строк всё считается массивами numpy, а не хэш-таблицами pandas (nunique, isin, unique): те
# поднимали пик памяти контейнера почти на 1,5 ГБ
def check_ratings(ratings: pd.DataFrame, movie_ids, expected: dict | None = EXPECTED) -> list[str]:
    users = ratings["user_id"].to_numpy(np.int64)
    movies = ratings["movie_id"].to_numpy(np.int64)
    problems = _count("ratings", len(ratings), expected)
    problems += _count("users", int(np.count_nonzero(np.bincount(users))), expected)  # id – небольшие целые
    doubled = ratings["rating"].to_numpy(np.float64) * 2  # шкала 0,5–5 с шагом 0,5 = целые 1–10
    bad = (doubled != np.round(doubled)) | (doubled < 1) | (doubled > 10)
    if bad.any():
        problems.append(f"оценки вне шкалы 0,5–5: {int(bad.sum())}")
    first = pd.Timestamp(FIRST_DAY, tz="UTC") - pd.Timedelta(days=1)
    last = pd.Timestamp(LAST_DAY, tz="UTC") + pd.Timedelta(days=2)
    outside = (ratings["time"] < first) | (ratings["time"] >= last)
    if outside.any():
        problems.append(f"оценки вне периода {FIRST_DAY} – {LAST_DAY}: {int(outside.sum())}")
    # пара как одно число int64 (id фильма < 10^7), отсортированное на месте: повтор – равные соседи
    keys = users * 10_000_000 + movies
    keys.sort()
    duplicates = int(np.count_nonzero(keys[1:] == keys[:-1]))
    del keys
    if duplicates:
        problems.append(f"повторные оценки одной пары «пользователь – фильм»: {duplicates}")
    # известные фильмы – битовая маска по id: проверка каждой оценки – одно обращение к массиву
    known_ids = np.asarray(movie_ids, dtype=np.int64)
    known = np.zeros(max(int(known_ids.max()), int(movies.max())) + 1, dtype=bool)
    known[known_ids] = True
    unknown = int(np.count_nonzero(~known[movies]))
    if unknown:
        problems.append(f"оценки фильмов, которых нет в movies: {unknown}")
    return problems


def check_tables(rows: dict[str, int], expected: dict | None = EXPECTED) -> list[str]:
    return [p for name in ("tags", "movies") for p in _count(name, rows[name], expected)]


# каталог: id без дублей, порог числа оценок, год и жанры в допустимых значениях, IMDb id вида tt0000000;
# названия и постеры – только для фильмов каталога и без дублей
def check_catalog(catalog: pd.DataFrame, titles: pd.DataFrame | None = None,
                  posters: pd.DataFrame | None = None) -> list[str]:
    problems = []
    if catalog["movie_id"].duplicated().any():
        problems.append("каталог: повторяются movie_id")
    if (catalog["n_ratings"] < MIN_RATINGS).any():
        problems.append(f"каталог: фильмы меньше чем с {MIN_RATINGS} оценками")
    if (catalog["title"].fillna("").str.strip() == "").any():
        problems.append("каталог: пустые названия")
    years = catalog["year"].dropna()
    if ((years < 1874) | (years > 2023)).any():
        problems.append("каталог: год вне 1874–2023")
    genres = {g for value in catalog["genres"].fillna("") for g in value.split("|") if g}
    if unknown := genres - GENRES:
        problems.append(f"каталог: неизвестные жанры {sorted(unknown)}")
    imdb = catalog["imdb_id"].dropna()
    if not imdb.str.match(r"^tt\d{7,8}$").all():
        problems.append("каталог: IMDb id не вида tt0000000")
    for name, frame in (("titles", titles), ("posters", posters)):
        if frame is None:
            continue
        if frame["movie_id"].duplicated().any():
            problems.append(f"{name}: повторяются movie_id")
        if not frame["movie_id"].isin(catalog["movie_id"]).all():
            problems.append(f"{name}: фильмы, которых нет в каталоге")
    texts = [catalog["title"], catalog["tags"]] + ([titles[c] for c in titles if c.startswith("title_")]
                                                   if titles is not None else [])
    if any(text.fillna("").str.contains(chr(0x2014), regex=False).any() for text in texts):
        problems.append("длинное тире в названиях или тегах – в проекте только среднее «–»")
    return problems


def _share(part: int, total: int) -> str:
    return f"{part} ({part / total:.0%})" if total else "0"


def summary(ratings: pd.DataFrame, catalog: pd.DataFrame | None = None, titles: pd.DataFrame | None = None,
            posters: pd.DataFrame | None = None) -> dict:
    info = {
        "оценок": len(ratings),
        "пользователей": ratings["user_id"].nunique(),
        "фильмов с оценками": ratings["movie_id"].nunique(),
        "период": f"{ratings['time'].min():%Y-%m-%d} – {ratings['time'].max():%Y-%m-%d}",
        "средняя оценка": round(float(ratings["rating"].mean()), 3),
    }
    if catalog is not None:
        covered = int(catalog["n_ratings"].sum())
        info["фильмов в каталоге"] = len(catalog)
        info["оценок у фильмов каталога"] = _share(covered, len(ratings))
        info["с тегами"] = _share(int((catalog["tags"].fillna("") != "").sum()), len(catalog))
    if titles is not None:
        for lang in ("ru", "kk", "en"):
            info[f"название {lang}"] = _share(int((titles[f"title_{lang}"] != "").sum()), len(catalog))
    if posters is not None:
        info["с постером"] = _share(int((posters["poster_path"] != "").sum()), len(catalog))
    return info
