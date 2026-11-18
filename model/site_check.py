"""Проверка выгрузки как на сайте: python site_check.py (после python export.py, onnx и e5).

Только то, что будет у бэкенда: numpy, scipy, sqlite3, onnxruntime, sentencepiece – без torch, pandas, implicit.
Загружает model/export, советует по 5 оценкам (смесь «популярность × ALS»), подбирает новинки, открывает описание
фильма, ищет словами; меряет пиковую память процесса (лимит Render – 512 МБ) и время ответа."""
import resource
import time

rss = lambda: resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # noqa: E731 – МБ, пик процесса
BASE = rss()

import gzip  # noqa: E402
import json  # noqa: E402
import sqlite3  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import onnxruntime as ort  # noqa: E402
import scipy.sparse as sp  # noqa: E402
import sentencepiece  # noqa: E402

from site_core import encode_query, ranks, site_scores  # noqa: E402

OUT = Path(__file__).resolve().parent / "export"
LIKED = (1, 2571, 79132, 109487, 58559)  # Toy Story, The Matrix, Inception, Interstellar, The Dark Knight
QUERY = "мультфильм про игрушки, которые оживают"


def main() -> None:
    catalog = json.load(gzip.open(OUT / "catalog.json.gz", "rt", encoding="utf-8"))
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    popularity, items = np.load(OUT / "popularity.npy"), np.load(OUT / "als_items.npy")
    gram, tfidf = np.load(OUT / "als_gram.npy"), sp.load_npz(OUT / "tfidf.npz")
    has_e5 = (OUT / "e5_enru.npy").exists()
    e5 = np.load(OUT / "e5_enru.npy") if has_e5 else \
        np.random.default_rng(0).standard_normal((len(catalog), 384)).astype(np.float16)
    sp_model = sentencepiece.SentencePieceProcessor(model_file=str(OUT / "e5_sentencepiece.model"))
    options = ort.SessionOptions()
    options.enable_cpu_mem_arena, options.intra_op_num_threads = False, 1  # меньше памяти на маленьком сервере
    session = ort.InferenceSession(str(OUT / "e5_query.onnx"), options, providers=["CPUExecutionProvider"])
    db = sqlite3.connect(f"file:{OUT / 'overviews.db'}?mode=ro", uri=True)
    loaded = rss()
    row = {c["id"]: i for i, c in enumerate(catalog)}
    pop_ranks = ranks(popularity)
    liked = np.array([row[m] for m in LIKED])

    tic = time.perf_counter()
    scores = site_scores(pop_ranks, items, gram, liked)
    scores[liked] = -np.inf
    top = np.argsort(-scores)[:10]
    t_rec = (time.perf_counter() - tic) * 1000

    tic = time.perf_counter()
    new_rows = np.array([row[m] for m in manifest["new_items"]["ids"]])
    profile = np.asarray(tfidf[liked].sum(axis=0)).ravel()
    new_top = new_rows[np.argsort(-(tfidf[new_rows] @ profile))[:10]]
    t_new = (time.perf_counter() - tic) * 1000

    tic = time.perf_counter()
    overview = db.execute("SELECT ru, en FROM overviews WHERE id = ?", (int(catalog[top[0]]["id"]),)).fetchone()
    t_film = (time.perf_counter() - tic) * 1000

    tic = time.perf_counter()
    ids = encode_query(sp_model, f"query: {QUERY}")
    query = session.run(None, {"input_ids": np.array([ids], dtype=np.int64),
                               "attention_mask": np.ones((1, len(ids)), dtype=np.int64)})[0][0]
    found = np.argsort(-(e5.astype(np.float32) @ query))[:10]
    t_search = (time.perf_counter() - tic) * 1000

    title = lambda i: catalog[i]["title_ru"] or catalog[i]["title"]  # noqa: E731
    print("советы:", [title(i) for i in top])
    print("новинки:", [title(i) for i in new_top])
    print("описание первого совета:", (overview[0] or overview[1])[:80], "…")
    print(f"поиск «{QUERY}»:", [title(i) for i in found], "" if has_e5 else "(векторы e5 случайные – из Colab ещё нет)")
    print(f"память: до загрузки {BASE:.0f} МБ, после загрузки {loaded:.0f} МБ, пик {rss():.0f} МБ (лимит Render 512)")
    print(f"время: совет {t_rec:.0f} мс, новинки {t_new:.0f} мс, описание {t_film:.1f} мс, поиск {t_search:.0f} мс")


if __name__ == "__main__":
    main()
