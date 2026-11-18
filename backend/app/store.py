"""Выгрузка модели в памяти сервера и все расчёты сайта (формулы – model/site_core.py, общие с проверкой).

Строки всех матриц – фильмы каталога по возрастанию id (catalog.json.gz). Загружается один раз при старте:
≈ 380 МБ, из них модель запросов e5 – около 200 МБ. Описания сюжета не держатся в памяти – читаются из SQLite."""
import gzip
import json
import os
import sqlite3
import time
from pathlib import Path

import numpy as np
import scipy.sparse as sp

import site_core as core

EXPORT = Path(os.environ.get("EXPORT_DIR", Path(__file__).resolve().parents[1] / "export"))
LANGS = ("ru", "kk", "en")
# название на языке интерфейса: казахского и русского нет у части фильмов – дальше по цепочке (data/README.md)
TITLE_ORDER = {"kk": ("title_kk", "title_ru", "title_en", "title"), "ru": ("title_ru", "title_en", "title"),
               "en": ("title_en", "title")}
# описание сюжета: казахских в выгрузке нет – русское, потом английское
OVERVIEW_ORDER = {"kk": ("ru", "en"), "ru": ("ru", "en"), "en": ("en",)}


class Store:
    def __init__(self, path: Path = EXPORT, encoder=None):
        started = time.perf_counter()
        self.path = Path(path)
        self.manifest = json.loads((self.path / "manifest.json").read_text(encoding="utf-8"))
        with gzip.open(self.path / "catalog.json.gz", "rt", encoding="utf-8") as f:
            self.catalog: list[dict] = json.load(f)
        self.ids = np.array([c["id"] for c in self.catalog], dtype=np.int64)
        self.row = {int(m): i for i, m in enumerate(self.ids)}
        self.n_ratings = np.array([c["n_ratings"] for c in self.catalog], dtype=np.float64)

        self.popularity = np.load(self.path / "popularity.npy").astype(np.float64)
        self.pop_ranks = core.ranks(self.popularity)
        self.known_ranks = core.ranks(self.n_ratings)  # известность – для поиска
        self.items = np.load(self.path / "als_items.npy")
        self.gram = np.load(self.path / "als_gram.npy")
        als = self.manifest["site_model"]["als"]
        self.regularization, self.alpha = als["regularization"], als["alpha"]
        self.tfidf = sp.load_npz(self.path / "tfidf.npz").tocsr()
        self.new_rows = np.array([self.row[m] for m in self.manifest["new_items"]["ids"]], dtype=np.int64)

        if not np.array_equal(np.load(self.path / "e5_ids.npy"), self.ids):
            raise ValueError("порядок векторов e5 не совпадает с каталогом")
        self.e5 = np.load(self.path / "e5_enru.npy").astype(np.float32)
        taste = np.load(self.path / "map.npz")
        self.map_rows = np.array([self.row[int(m)] for m in taste["ids"]], dtype=np.int64)
        self.map_xy = taste["xy"].astype(np.float64)
        self.map_place = {int(r): k for k, r in enumerate(self.map_rows)}
        self._maps: dict[str, bytes] = {}

        # все названия фильма для поиска по названию: строчные, без знаков и года
        self.names = ["|".join(dict.fromkeys(core.normalize_title(c[f]) for f in TITLE_ORDER["kk"] if c[f]))
                      for c in self.catalog]
        self.exact: dict[str, list[int]] = {}
        for i, joined in enumerate(self.names):
            for name in joined.split("|"):
                self.exact.setdefault(name, []).append(i)
        self.encode = encoder or self._onnx_encoder()
        self.load_seconds = time.perf_counter() - started

    def _onnx_encoder(self):
        import onnxruntime as ort
        import sentencepiece

        words = sentencepiece.SentencePieceProcessor(model_file=str(self.path / "e5_sentencepiece.model"))
        options = ort.SessionOptions()
        # бесплатный Render – доля одного ядра; без арены памяти onnxruntime не держит лишнее после запроса
        options.enable_cpu_mem_arena, options.intra_op_num_threads = False, 1
        session = ort.InferenceSession(str(self.path / "e5_query.onnx"), options, providers=["CPUExecutionProvider"])

        def encode(text: str) -> np.ndarray:
            ids = core.encode_query(words, f"query: {text}")
            return session.run(None, {"input_ids": np.array([ids], dtype=np.int64),
                                      "attention_mask": np.ones((1, len(ids)), dtype=np.int64)})[0][0]

        return encode

    # ---------- карточки ----------
    def title(self, i: int, lang: str) -> str:
        c = self.catalog[i]
        return next((c[f] for f in TITLE_ORDER[lang] if c[f]), c["title"])

    def card(self, i: int, lang: str, score: float | None = None) -> dict:
        c = self.catalog[i]
        out = {"id": c["id"], "title": self.title(i, lang), "original_title": c["title"], "year": c["year"],
               "genres": c["genres"], "poster": c["poster"] or None, "mean_rating": c["mean_rating"],
               "n_ratings": c["n_ratings"]}
        if score is not None:
            out["score"] = round(float(score), 4)
        return out

    def top(self, scores: np.ndarray, k: int, lang: str, skip: np.ndarray | None = None) -> list[dict]:
        scores = scores.astype(np.float64, copy=True)
        if skip is not None and len(skip):
            scores[skip] = -np.inf
        order = np.argsort(-scores, kind="stable")[:k]
        return [self.card(int(i), lang, scores[i]) for i in order if np.isfinite(scores[i])]

    def rows_of(self, ratings: dict[int, float]) -> tuple[np.ndarray, np.ndarray, list[int]]:
        """Оценки {id: оценка} -> строки каталога, оценки и id, которых в каталоге нет (они пропускаются)."""
        known = [(self.row[m], r) for m, r in ratings.items() if m in self.row]
        unknown = [m for m in ratings if m not in self.row]
        index = np.array([i for i, _ in known], dtype=np.int64)
        return index, np.array([r for _, r in known], dtype=np.float64), unknown

    # ---------- модели ----------
    def site(self, index: np.ndarray, weight: float = core.SITE_WEIGHT) -> np.ndarray:
        """Модель сайта «популярность × ALS»; weight – вес популярности (ползунок новизны), 0 – чистый ALS."""
        return core.site_scores(self.pop_ranks, self.items, self.gram, index, self.regularization, self.alpha, weight)

    def explain(self, cards: list[dict], index: np.ndarray, lang: str, top: int = 3) -> list[dict]:
        """Добавить к советам «потому что понравились …»: оценённые фильмы с наибольшим положительным вкладом
        в балл ALS и их доля среди положительных вкладов."""
        if not cards:
            return cards
        targets = np.array([self.row[c["id"]] for c in cards], dtype=np.int64)
        c = core.contributions(self.items, self.gram, self.regularization, self.alpha, index, targets)
        for card, row in zip(cards, c):
            positive = np.clip(row, 0, None)
            total = positive.sum()
            order = [j for j in np.argsort(-positive, kind="stable")[:top] if positive[j] > 0]
            card["because"] = [{"id": int(self.ids[index[j]]), "title": self.title(int(index[j]), lang),
                                "share": round(float(positive[j] / total), 3)} for j in order]
        return cards

    def content(self, index: np.ndarray, values: np.ndarray, candidates: np.ndarray | None = None) -> np.ndarray:
        return core.content_scores(self.tfidf, index, values, candidates)

    def new_items(self, index: np.ndarray, values: np.ndarray, k: int, lang: str) -> list[dict]:
        scores = np.full(len(self.catalog), -np.inf)
        scores[self.new_rows] = self.content(index, values, self.new_rows)
        return self.top(scores, k, lang, skip=index)

    def similar(self, i: int, k: int, lang: str) -> list[dict]:
        """«С этим фильмом смотрят» – та же модель сайта для человека, которому понравился только этот фильм."""
        index = np.array([i], dtype=np.int64)
        return self.top(self.site(index), k, lang, skip=index)

    def overview(self, i: int, lang: str) -> str | None:
        with sqlite3.connect(f"file:{self.path / 'overviews.db'}?mode=ro", uri=True) as db:
            row = db.execute("SELECT ru, en FROM overviews WHERE id = ?", (int(self.ids[i]),)).fetchone()
        if row is None:
            return None
        text = dict(zip(("ru", "en"), row))
        return next((text[l] for l in OVERVIEW_ORDER[lang] if text[l]), None)

    # ---------- поиск ----------
    def suggest(self, query: str, k: int, lang: str) -> list[dict]:
        """Подсказки по названию: точное совпадение, потом начало названия, потом вхождение; внутри – самые
        оценённые выше. Пустой запрос – популярное за последний год."""
        q = core.normalize_title(query)
        if not q:
            return self.top(self.popularity, k, lang)
        exact, prefix, inside = [], [], []
        for i, joined in enumerate(self.names):
            if q not in joined:
                continue
            names = joined.split("|")
            (exact if q in names else prefix if any(n.startswith(q) for n in names) else inside).append(i)
        rows = [i for group in (exact, prefix, inside) for i in sorted(group, key=lambda i: -self.n_ratings[i])]
        return [self.card(i, lang) for i in rows[:k]]

    def search(self, query: str, k: int, lang: str) -> dict:
        """Поиск словами: фильмы, чьё название совпало с запросом целиком, – первыми; дальше – e5 с известностью."""
        titled = sorted(self.exact.get(core.normalize_title(query), []), key=lambda i: -self.n_ratings[i])
        scores = core.search_scores(self.e5 @ self.encode(query), self.known_ranks, core.SEARCH_WEIGHT)
        found = [self.card(i, lang) | {"by": "title"} for i in titled[:k]]
        rest = self.top(scores, k, lang, skip=np.array(titled, dtype=np.int64))
        return {"items": (found + [c | {"by": "meaning"} for c in rest])[:k]}

    # ---------- карта вкусов ----------
    def taste_map(self, lang: str) -> bytes:
        """Карта не меняется: ответ (JSON, ≈ 0,4 МБ) собирается один раз на язык и дальше отдаётся готовым."""
        if lang not in self._maps:
            films = [{"id": int(self.ids[i]), "x": round(float(x), 4), "y": round(float(y), 4),
                      "title": self.title(int(i), lang), "genre": (self.catalog[i]["genres"] or ["?"])[0]}
                     for i, (x, y) in zip(self.map_rows, self.map_xy)]
            self._maps[lang] = json.dumps({"films": films}, ensure_ascii=False).encode("utf-8")
        return self._maps[lang]

    def map_me(self, index: np.ndarray, values: np.ndarray) -> dict:
        on_map = [(self.map_place[int(i)], v) for i, v in zip(index, values) if int(i) in self.map_place]
        point = core.map_point(self.map_xy[[p for p, _ in on_map]], np.array([v for _, v in on_map])) \
            if on_map else None
        return {"x": None if point is None else round(float(point[0]), 4),
                "y": None if point is None else round(float(point[1]), 4), "used": len(on_map)}
