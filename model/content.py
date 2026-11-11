"""Контентная модель: фильм – вектор по его описанию, человек – взвешенная сумма векторов оценённых им фильмов
(профиль вкуса), балл кандидата – скалярное произведение с профилем (векторы фильмов единичной длины – косинус).

- TF-IDF: жанры, десятилетие выпуска и теги как отдельные признаки (тег из нескольких слов – один признак);
  вариант «text» добавляет слова английского описания сюжета.
- e5: смысловой вектор текста «название. жанры. теги. описание» из multilingual-e5-small (384 числа);
  вариант «en_ru» – среднее векторов английского и русского текста.

Описание фильма не знает будущего: теги – только поставленные до границы (protocol.load), описание сюжета,
жанры и год – свойства самого фильма. Главное преимущество перед совместной фильтрацией – новинки: фильму не
нужны оценки, чтобы его советовали (сценарий «новинки», evaluate.py content)."""
import hashlib
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

from baselines import Recommender, Static
from collect.catalog import top_tags
from collect.config import CATALOG_DIR

E5_MODEL = "intfloat/multilingual-e5-small"
CACHE = Path(os.environ.get("CACHE", "/cache"))  # том Docker: модель e5 и посчитанные векторы фильмов
WORD_RE = re.compile(r"[a-z]{3,}")


def build_side(tags: pd.DataFrame) -> pd.DataFrame:
    """Описание фильмов каталога сайта: название (en, ru), год, жанры, теги до границы, описания сюжета."""
    side = pd.read_csv(CATALOG_DIR / "movies.csv", usecols=["movie_id", "title", "year", "genres"],
                       dtype={"year": "Int64"}, keep_default_na=False, na_values={"year": [""]})
    side = side.set_index("movie_id")
    titles = pd.read_csv(CATALOG_DIR / "titles.csv", dtype=str, keep_default_na=False)
    overviews = pd.read_csv(CATALOG_DIR / "overviews.csv.gz", dtype=str, keep_default_na=False)
    for frame, columns in ((titles, ["title_ru", "title_en"]), (overviews, ["overview_en", "overview_ru"])):
        frame = frame.astype({"movie_id": "int64"}).set_index("movie_id")
        side = side.join(frame[columns])
    side["tags"] = top_tags(tags).reindex(side.index)
    return side.fillna({c: "" for c in ("title_ru", "title_en", "overview_en", "overview_ru", "tags")})


def text(row, lang: str) -> str:
    """Текст фильма для e5: название, жанры, теги, описание (русского описания нет – английское)."""
    title = (row.title_ru if lang == "ru" else row.title_en) or row.title
    overview = (row.overview_ru if lang == "ru" else "") or row.overview_en
    parts = [title, row.genres.replace("|", ", "), row.tags.replace("|", ", "), overview]
    return ". ".join(p for p in parts if p)


_model = []  # модель e5 загружается один раз за прогон


def _e5():
    if not _model:
        from sentence_transformers import SentenceTransformer

        _model.append(SentenceTransformer(E5_MODEL, device="cpu", cache_folder=str(CACHE / "hf")))
    return _model[0]


def embed_queries(texts: list[str]) -> np.ndarray:
    """Векторы поисковых запросов: у e5 запрос и текст фильма различаются префиксами query: и passage:."""
    return _e5().encode([f"query: {t}" for t in texts], normalize_embeddings=True, show_progress_bar=False,
                        convert_to_numpy=True).astype(np.float32)


def embed(texts: list[str]) -> np.ndarray:
    """Векторы e5 (единичной длины) – с кэшем в томе Docker: те же тексты не считаются второй раз."""
    key = hashlib.sha1("\n".join([E5_MODEL, *texts]).encode()).hexdigest()[:16]
    path = CACHE / "e5" / f"{key}.npy"
    if path.exists():
        return np.load(path)
    print(f"e5: {len(texts)} текстов", flush=True)
    out = _e5().encode([f"passage: {t}" for t in texts], batch_size=64, normalize_embeddings=True,
                       show_progress_bar=False, convert_to_numpy=True).astype(np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, out)
    return out


class Content(Recommender):
    """Общая часть: матрица векторов всех фильмов каталога, профиль человека по любым оценённым фильмам каталога
    (не только кандидатам), баллы – только кандидатам."""

    def __init__(self, weighting: str = "binary"):
        self.weighting = weighting

    def attach(self, side: pd.DataFrame) -> None:
        if getattr(self, "side", None) is not side:
            self.side, self.matrix = side, None

    def vectors(self):
        raise NotImplementedError

    def fit(self, history, pool):
        super().fit(history, pool)
        if self.matrix is None:
            self.matrix = self.vectors()
        self.row = pd.Series(np.arange(len(self.side)), index=self.side.index)
        rows = self.row.reindex(pool).to_numpy()
        # кандидат вне каталога сайта (фильм без названия « (2019)») – без описания: нулевой вектор, балл 0
        missing = np.isnan(rows)
        self.pool_matrix = self.matrix[np.where(missing, 0, rows).astype(np.int64)]
        if missing.any():
            keep = (~missing).astype(np.float32)
            self.pool_matrix = (sp.diags(keep) @ self.pool_matrix).tocsr() if sp.issparse(self.pool_matrix) \
                else self.pool_matrix * keep[:, None]
        return self

    def weights(self, inputs: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        rows = self.row.reindex(inputs["movie_id"]).to_numpy()
        keep = ~np.isnan(rows)
        w = np.ones(int(keep.sum()))
        if self.weighting == "centered":
            w = inputs["rating"].to_numpy(np.float64)[keep] - float(inputs["rating"].mean())
            if np.allclose(w, 0):  # все оценки одинаковые – «минусов» нет, каждый фильм тянет вверх
                w = np.ones(len(w))
        return rows[keep].astype(np.int64), w

    def scores(self, inputs, user=None):
        rows, w = self.weights(inputs)
        if not len(rows):
            return np.zeros(len(self.pool))
        profile = self.matrix[rows].T @ w
        return np.asarray(self.pool_matrix @ profile).ravel()


class TfidfContent(Content):
    def __init__(self, words: bool = False, weighting: str = "binary"):
        super().__init__(weighting)
        self.words = words
        self.name = f"content_tfidf_{'text' if words else 'meta'}_{weighting}"

    def tokens(self, row) -> list[str]:
        out = [f"genre:{g}" for g in row.genres.split("|") if g and g != "(no genres listed)"]
        if not pd.isna(row.year):
            out.append(f"decade:{int(row.year) // 10 * 10}")
        out += [f"tag:{t}" for t in row.tags.split("|") if t]
        if self.words:
            from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

            out += [w for w in WORD_RE.findall(row.overview_en.lower()) if w not in ENGLISH_STOP_WORDS]
        return out

    def vectors(self) -> sp.csr_matrix:
        from sklearn.feature_extraction.text import TfidfVectorizer

        docs = [self.tokens(row) for row in self.side.itertuples()]
        # признак хотя бы у двух фильмов: уникальный тег или слово ни с чем не связывает
        self.vectorizer = TfidfVectorizer(analyzer=lambda doc: doc, min_df=2, sublinear_tf=True)
        return self.vectorizer.fit_transform(docs).tocsr()

    def query_vector(self, query: str) -> sp.csr_matrix:
        """Запрос словами – вектор по тем же английским словам описаний (другие языки TF-IDF не понимает)."""
        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

        words = [w for w in WORD_RE.findall(query.lower()) if w not in ENGLISH_STOP_WORDS]
        return self.vectorizer.transform([words])


class E5Content(Content):
    def __init__(self, langs: tuple[str, ...] = ("en",), weighting: str = "binary", encoder=embed):
        super().__init__(weighting)
        self.langs, self.encoder = langs, encoder
        self.name = f"content_e5_{''.join(langs)}_{weighting}"

    def vectors(self) -> np.ndarray:
        rows = list(self.side.itertuples())
        total = sum(self.encoder([text(row, lang) for row in rows]) for lang in self.langs)
        return (total / np.linalg.norm(total, axis=1, keepdims=True).clip(1e-12)).astype(np.float32)


class Newest(Static):
    """Сначала самые новые по году выпуска (без года – в конце); база для сценария «новинки»."""
    name = "newest"

    def attach(self, side: pd.DataFrame) -> None:
        self.side = side

    def fit(self, history, pool):
        super().fit(history, pool)
        years = self.side["year"].reindex(pool).astype("float64").fillna(0).to_numpy()
        self.static = years + self.counts(history) / (len(history) + 1)  # в пределах года – по числу оценок
        return self


def grid() -> list[Content]:
    return [model(variant, weighting) for weighting in ("binary", "centered")
            for model, variant in ((TfidfContent, False), (TfidfContent, True), (E5Content, ("en",)),
                                   (E5Content, ("en", "ru")))]
