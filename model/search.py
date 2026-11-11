"""Проверка поиска словами: 30 запросов (search_queries.csv, по 10 на русском, казахском и английском) по
всему каталогу сайта – python search.py -> reports/search/<PERIOD>.json.

- «Сюжет» (plot): описание сюжета, ожидается конкретный фильм (expect – movie_id); попадание – он в первых 10.
- «Жанр» (genre): ожидается жанр (expect – «Horror»; «Romance&Comedy» – оба; «Mystery|Crime» – любой);
  точность – доля таких фильмов в первых 10, для сравнения – доля жанра во всём каталоге (случайный выбор).

Векторы фильмов – те же, что у контентной модели на шаге 5 (кэш e5 в томе Docker): описание фильма с тегами
до границы проверочной части. Балл фильма – косинус между вектором запроса и вектором фильма."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import content
from evaluate import REPORTS, period_from_env
from protocol import load

QUERIES = Path(__file__).resolve().parent / "search_queries.csv"
TOP = 10


def genre_match(genres: pd.Series, expect: str) -> np.ndarray:
    """Подходит ли фильм под ожидание по жанру: «A&B» – оба жанра, «A|B» – любой из них."""
    sets = genres.str.split("|").map(set)
    if "&" in expect:
        need = set(expect.split("&"))
        return sets.map(need.issubset).to_numpy()
    allowed = set(expect.split("|"))
    return sets.map(lambda s: bool(s & allowed)).to_numpy()


def judge(top: np.ndarray, kind: str, expect: str, side: pd.DataFrame) -> dict:
    """Оценка одного списка: сюжет – место ожидаемого фильма (None – не в первых TOP), жанр – доля подходящих."""
    if kind == "plot":
        hits = np.flatnonzero(top == int(expect))
        rank = int(hits[0]) + 1 if len(hits) else None
        return {"rank": rank, "hit": float(rank is not None)}
    return {"precision": float(genre_match(side.loc[top, "genres"], expect).sum() / TOP)}


def run_search(side: pd.DataFrame, variants: dict, queries: pd.DataFrame) -> dict:
    """variants: имя -> функция «список запросов -> матрица баллов (запросы × фильмы каталога)»."""
    ids = side.index.to_numpy()
    out = {"queries": len(queries), "catalog": len(side), "top": TOP, "variants": {}, "chance": {}}
    for kind, expect in queries.loc[queries["kind"] == "genre", ["kind", "expect"]].itertuples(index=False):
        out["chance"][expect] = round(float(genre_match(side["genres"], expect).mean()), 4)
    for name, score in variants.items():
        scores = score(queries["query"].tolist())
        rows = []
        for q, s in zip(queries.itertuples(index=False), scores):
            # одинаковые баллы у всех – запрос модели ничего не сказал (TF-IDF не знает русских и казахских
            # слов): выдача пустая, а не первые фильмы каталога по порядку
            top = ids[np.argsort(-s, kind="stable")[:TOP]] if np.ptp(s) > 0 else ids[:0]
            rows.append({"lang": q.lang, "kind": q.kind, "query": q.query, "expect": str(q.expect),
                         **judge(top, q.kind, str(q.expect), side), "top3": side.loc[top[:3], "title"].tolist()})
        frame = pd.DataFrame(rows)
        summary = {}
        for lang, part in frame.groupby("lang", sort=False):
            summary[lang] = {"plot_hit": round(float(part["hit"].mean()), 3),
                             "genre_precision": round(float(part["precision"].mean()), 3)}
        out["variants"][name] = {"summary": summary, "queries": rows}
        print(name, summary, flush=True)
    return out


def variants_for(side: pd.DataFrame) -> dict:
    e5 = {}
    for langs in (("en",), ("en", "ru")):
        model = content.E5Content(langs)
        model.attach(side)
        e5["e5_" + "".join(langs)] = model.vectors()
    tfidf = content.TfidfContent(words=True)
    tfidf.attach(side)
    tfidf_matrix = tfidf.vectors()

    def e5_score(matrix):
        return lambda texts: content.embed_queries(texts) @ matrix.T

    def tfidf_score(texts):
        return np.vstack([(tfidf_matrix @ tfidf.query_vector(t).T).toarray().ravel() for t in texts])

    return {**{name: e5_score(m) for name, m in e5.items()}, "tfidf_text": tfidf_score}


def main() -> None:
    period = period_from_env()
    tags = load(period)[3]
    side = content.build_side(tags)
    queries = pd.read_csv(QUERIES, dtype={"expect": str})
    if len(queries) != 30:
        sys.exit(f"ожидалось 30 запросов, в {QUERIES.name} – {len(queries)}")
    report = {"period": period, **run_search(side, variants_for(side), queries)}
    out = REPORTS / "search" / f"{period}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"сохранено {out.relative_to(REPORTS.parent)}")


if __name__ == "__main__":
    main()
