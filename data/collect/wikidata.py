import re
import time

import pandas as pd

from .config import LABEL_LANGS, TITLES_COLUMNS, WIKIDATA_BATCH, WIKIDATA_PAUSE_SEC, WIKIDATA_URL
from .net import request
from .store import load, save

IMDB_RE = re.compile(r"^tt\d{7,8}$")
# уточнение неоднозначной метки в конце: «Жеті (фильм)», «Дюна (фильм, 2021)», «(фильм 1934 года)»,
# «(фильм-триллер, 2019)», «Heat (1995 film)»; скобки, которые входят в само название
# («(and Don't Come Back!!)»), не трогаются
NOTE_RE = re.compile(r"\s*\((?:[^()]*\s)?(?:фильм|мультфильм|телефильм|сериал|film|movie)(?:[\s,-][^()]*)?\)\s*$",
                     re.IGNORECASE)


EM_DASH = chr(0x2014)  # длинное тире из меток Wikidata заменяется: во всём проекте только среднее «–»


def clean_label(label: str) -> str:
    return NOTE_RE.sub("", label).strip().replace(EM_DASH, "–")


# SPARQL: элементы Wikidata с данными IMDb id (P345) и их метки на нужных языках; метки – OPTIONAL,
# чтобы фильм без русского и казахского названия всё равно получил свой Q-номер
def build_query(imdb_ids: list[str]) -> str:
    bad = [i for i in imdb_ids if not IMDB_RE.match(i)]
    if bad:
        raise ValueError(f"не IMDb id: {bad[:3]}")
    values = " ".join(f'"{i}"' for i in imdb_ids)
    langs = ", ".join(f'"{lang}"' for codes in LABEL_LANGS.values() for lang in codes)
    return (
        "SELECT ?imdb ?item ?lang ?label WHERE { "
        f"VALUES ?imdb {{ {values} }} "
        "?item wdt:P345 ?imdb . "
        f"OPTIONAL {{ ?item rdfs:label ?label . BIND(LANG(?label) AS ?lang) FILTER(?lang IN ({langs})) }} "
        "}"
    )


def _qnum(qid: str) -> int:
    return int(qid[1:])


# ответ SPARQL -> строка на IMDb id: Q-номер и названия ru/kk/en. Если одному IMDb id соответствуют несколько
# элементов (редкие дубли в Wikidata), берётся старейший – с меньшим Q-номером
def parse_bindings(bindings: list[dict]) -> pd.DataFrame:
    found: dict[str, dict] = {}
    for row in bindings:
        imdb = row["imdb"]["value"]
        qid = row["item"]["value"].rsplit("/", 1)[-1]
        current = found.get(imdb)
        if current is None or _qnum(qid) < _qnum(current["wikidata"]):
            current = found[imdb] = {"wikidata": qid, "labels": {}}
        elif qid != current["wikidata"]:
            continue
        if "lang" in row:
            current["labels"][row["lang"]["value"]] = row["label"]["value"]
    rows = []
    for imdb, item in found.items():
        titles = {
            f"title_{lang}": next((item["labels"][code] for code in codes if code in item["labels"]), "")
            for lang, codes in LABEL_LANGS.items()
        }
        rows.append({"imdb_id": imdb, "wikidata": item["wikidata"], **titles})
    return pd.DataFrame(rows, columns=["imdb_id", "wikidata", *[f"title_{lang}" for lang in LABEL_LANGS]])


def fetch(imdb_ids: list[str]) -> pd.DataFrame:
    resp = request(
        "POST", WIKIDATA_URL,
        data={"query": build_query(imdb_ids), "format": "json"},
        headers={"Accept": "application/sparql-results+json"},
    )
    return parse_bindings(resp.json()["results"]["bindings"])


# названия для фильмов каталога, которых ещё нет в catalog/titles.csv (refresh – запросить все заново);
# фильмы, не найденные в Wikidata, тоже записываются – с пустыми полями, чтобы не спрашивать их повторно
def update_titles(catalog: pd.DataFrame, path, refresh: bool = False, fetch_batch=fetch) -> pd.DataFrame:
    titles = pd.DataFrame(columns=TITLES_COLUMNS) if refresh else load(path, TITLES_COLUMNS)
    valid = catalog["imdb_id"].fillna("").str.match(IMDB_RE.pattern)
    todo = catalog[~catalog["movie_id"].isin(titles["movie_id"]) & valid]
    print(f"  нужно названий: {len(todo)}", flush=True)
    parts = [titles]
    for start in range(0, len(todo), WIKIDATA_BATCH):
        batch = todo.iloc[start: start + WIKIDATA_BATCH][["movie_id", "imdb_id"]]
        found = fetch_batch(batch["imdb_id"].drop_duplicates().tolist())
        rows = batch.merge(found, on="imdb_id", how="left").fillna("")
        parts.append(rows[TITLES_COLUMNS])
        done = start + len(batch)
        if done % (WIKIDATA_BATCH * 5) == 0 or done == len(todo):
            titles = save(pd.concat(parts, ignore_index=True), path, catalog)
            parts = [titles]
            print(f"  {done} из {len(todo)}", flush=True)
        time.sleep(WIKIDATA_PAUSE_SEC)
    titles = pd.concat(parts, ignore_index=True)
    for lang in LABEL_LANGS:  # и у ранее сохранённых: очистка не требует повторных запросов
        titles[f"title_{lang}"] = titles[f"title_{lang}"].map(clean_label)
    return save(titles, path, catalog)
