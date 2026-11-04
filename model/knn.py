"""Коллаборативная фильтрация по соседям.

- item-kNN: для каждого фильма заранее находятся K самых похожих – по тем, кто их оценивал (косинус или
  BM25 из библиотеки implicit). Балл кандидата – сумма сходства с фильмами, которые человек оценил;
  «почему» на сайте – «потому что вам понравились X и Y». Таблица соседей небольшая – годится для сайта.
- user-kNN: среди людей истории ищутся k самых похожих на вход человека (косинус по набору оценённых
  фильмов); советуется то, что понравилось им. Нужна вся матрица оценок – только для исследования."""
import numpy as np
import pandas as pd
import scipy.sparse as sp

from baselines import Recommender
from protocol import POSITIVE


_cache: dict[tuple, tuple[sp.csr_matrix, np.ndarray]] = {}


def interactions(history: pd.DataFrame, pool: np.ndarray, values: str = "binary") -> tuple[sp.csr_matrix, np.ndarray]:
    """Матрица «люди × фильмы-кандидаты» (CSR, float32): 1 за оценку (binary), сама оценка (rating) или
    1 только за оценку 4+ (liked). Вторым – id людей по строкам. Строится один раз на историю: вся сетка
    моделей прогона пользуется той же матрицей."""
    key = (id(history), len(history), len(pool), values)
    if key not in _cache:
        _cache[key] = _build(history, pool, values)
    return _cache[key]


def _build(history: pd.DataFrame, pool: np.ndarray, values: str) -> tuple[sp.csr_matrix, np.ndarray]:
    rows = history[np.isin(history["movie_id"], pool)]
    if values == "liked":
        rows = rows[rows["rating"] >= POSITIVE]
    users, row = np.unique(rows["user_id"].to_numpy(), return_inverse=True)
    col = np.searchsorted(pool, rows["movie_id"].to_numpy())
    data = rows["rating"].to_numpy(np.float32) if values == "rating" else np.ones(len(rows), dtype=np.float32)
    matrix = sp.csr_matrix((data, (row, col)), shape=(len(users), len(pool)), dtype=np.float32)
    matrix.sum_duplicates()
    return matrix, users


def input_weights(inputs: pd.DataFrame, position: pd.Series, mode: str) -> tuple[np.ndarray, np.ndarray]:
    """Вход человека -> (номера кандидатов, веса). binary – каждая оценка с весом 1; centered – оценка минус
    средняя оценка самого человека: понравившееся тянет похожие фильмы вверх, непонравившееся – вниз."""
    rows = inputs.assign(index=position.reindex(inputs["movie_id"]).to_numpy()).dropna(subset=["index"])
    index = rows["index"].to_numpy(np.int64)
    if mode == "binary":
        return index, np.ones(len(index))
    return index, rows["rating"].to_numpy(np.float64) - float(inputs["rating"].mean())


class ItemKNN(Recommender):
    """Соседи по фильмам: сходство из implicit (CosineRecommender или BM25Recommender, по K соседей)."""

    def __init__(self, similarity: str = "cosine", k: int = 100, weighting: str = "binary"):
        self.similarity, self.k, self.weighting = similarity, k, weighting
        self.name = f"item_knn_{similarity}_k{k}_{weighting}"

    def fit(self, history, pool):
        from implicit.nearest_neighbours import BM25Recommender, CosineRecommender

        super().fit(history, pool)
        matrix = interactions(history, pool)[0]
        model = (BM25Recommender if self.similarity == "bm25" else CosineRecommender)(K=self.k, num_threads=0)
        model.fit(matrix, show_progress=False)
        # similarity[i, j] – насколько фильм j похож на фильм i (у каждого i не больше K соседей)
        self.matrix = sp.csr_matrix(model.similarity, dtype=np.float32)
        self.matrix.setdiag(0)
        self.matrix.eliminate_zeros()
        return self

    def scores(self, inputs, user=None):
        index, weights = input_weights(inputs, self.position, self.weighting)
        return np.asarray(self.matrix[index].T @ weights).ravel()

    def because(self, inputs: pd.DataFrame, movie: int, top: int = 3) -> list[int]:
        """«Почему»: фильмы из входа, сильнее всего толкнувшие кандидата вверх."""
        index, weights = input_weights(inputs, self.position, self.weighting)
        column = self.matrix[index][:, int(self.position[movie])].toarray().ravel() * weights
        order = np.argsort(-column)[:top]
        return [int(self.pool[index[i]]) for i in order if column[i] > 0]


class UserKNN(Recommender):
    """Соседи по людям: косинус между набором оценённых фильмов человека и каждого человека истории; балл
    кандидата – сумма сходства соседей, которым он понравился (4+)."""

    def __init__(self, k: int = 100):
        self.k = k
        self.name = f"user_knn_k{k}"

    def fit(self, history, pool):
        super().fit(history, pool)
        seen, self.users = interactions(history, pool, "binary")
        norms = np.sqrt(np.asarray(seen.sum(axis=1)).ravel())
        # строки нормированы заранее: сходство с входом – одно произведение разреженных матриц
        self.seen = sp.csc_matrix(sp.diags(1 / np.maximum(norms, 1e-9)) @ seen, dtype=np.float32)
        liked, liked_users = interactions(history, pool, "liked")
        rows = np.searchsorted(self.users, liked_users)
        self.liked = sp.csr_matrix((liked.data, liked.indices, liked.indptr), shape=liked.shape)
        self.liked_rows = pd.Series(np.arange(len(liked_users)), index=rows)  # строка seen -> строка liked
        return self

    def scores(self, inputs, user=None):
        index, _ = input_weights(inputs, self.position, "binary")
        if not len(index):
            return np.zeros(len(self.pool))
        similarity = np.asarray(self.seen[:, index].sum(axis=1)).ravel() / np.sqrt(len(index))
        if user is not None:  # постоянный человек не сосед самому себе
            own = np.searchsorted(self.users, user)
            if own < len(self.users) and self.users[own] == user:
                similarity[own] = 0
        k = min(self.k, len(similarity))
        neighbours = np.argpartition(-similarity, k - 1)[:k]
        neighbours = neighbours[similarity[neighbours] > 0]
        rows = self.liked_rows.reindex(neighbours).dropna()
        weights = similarity[rows.index.to_numpy()]
        return np.asarray(self.liked[rows.to_numpy(np.int64)].T @ weights).ravel()


def item_grid() -> list[ItemKNN]:
    return [ItemKNN(s, k, w) for s in ("cosine", "bm25") for k in (50, 200) for w in ("binary", "centered")]


def user_grid() -> list[UserKNN]:
    return [UserKNN(k) for k in (50, 100, 200)]
