"""Матричная факторизация: каждый человек и каждый фильм – вектор «вкусов» из нескольких десятков чисел.

- SVD (явные оценки): оценка ≈ общее среднее + смещение человека + смещение фильма + произведение векторов;
  обучается чередующимися наименьшими квадратами (ALS) со взвешенной регуляризацией (Zhou et al., 2008).
  Главная цель – предсказание звёзд (RMSE и MAE); для топ-N советует фильмы с наибольшей ожидаемой оценкой.
- ALS (неявная обратная связь, Hu, Koren, Volinsky, 2008) из implicit: учится на факте «оценил».
- BPR (Rendle et al., 2009) из implicit: учится ставить оценённое выше неоценённого.

Новый человек (новичок с 5–10 оценками на сайте и в проверке) получает свой вектор без переобучения модели:
одно решение системы уравнений по его оценкам при неизменных векторах фильмов."""
import numpy as np
import pandas as pd
import scipy.sparse as sp

from baselines import Recommender
from knn import input_weights, interactions


def _positions(inputs: pd.DataFrame, position: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Номера кандидатов во входе и их оценки (фильмы вне кандидатов пропускаются)."""
    index = position.reindex(inputs["movie_id"]).to_numpy()
    keep = ~np.isnan(index)
    return index[keep].astype(np.int64), inputs["rating"].to_numpy(np.float64)[keep]


class ALS(Recommender):
    """Неявный ALS: вход человека – набор оценённых фильмов (вес 1, усиленный в alpha раз)."""

    def __init__(self, factors: int = 64, regularization: float = 0.05, alpha: float = 1.0, iterations: int = 15):
        self.factors, self.regularization, self.alpha, self.iterations = factors, regularization, alpha, iterations
        self.name = f"als_f{factors}_r{regularization:g}_a{alpha:g}"

    def fit(self, history, pool):
        from implicit.cpu.als import AlternatingLeastSquares

        super().fit(history, pool)
        self.model = AlternatingLeastSquares(factors=self.factors, regularization=self.regularization,
                                             alpha=self.alpha, iterations=self.iterations, random_state=0)
        self.model.fit(interactions(history, pool)[0], show_progress=False)
        return self

    def user_vector(self, inputs: pd.DataFrame) -> np.ndarray:
        index, _ = input_weights(inputs, self.position, "binary")
        row = sp.csr_matrix((np.ones(len(index), dtype=np.float32), (np.zeros(len(index), dtype=np.int64), index)),
                            shape=(1, len(self.pool)))
        return self.model.recalculate_user(0, row)

    def scores(self, inputs, user=None):
        return self.model.item_factors @ self.user_vector(inputs)


class BPR(Recommender):
    """BPR: обучение из implicit; новый человек – гребневая регрессия «оценённые фильмы → балл 1» по векторам
    фильмов (у BPR нет точной формулы добавления человека, это приближение)."""

    def __init__(self, factors: int = 64, learning_rate: float = 0.01, regularization: float = 0.01,
                 iterations: int = 100, fold_in_reg: float = 1.0):
        self.factors, self.learning_rate, self.regularization = factors, learning_rate, regularization
        self.iterations, self.fold_in_reg = iterations, fold_in_reg
        self.name = f"bpr_f{factors}_lr{learning_rate:g}"

    def fit(self, history, pool):
        from implicit.cpu.bpr import BayesianPersonalizedRanking

        super().fit(history, pool)
        model = BayesianPersonalizedRanking(factors=self.factors, learning_rate=self.learning_rate,
                                            regularization=self.regularization, iterations=self.iterations,
                                            random_state=0)
        model.fit(interactions(history, pool)[0], show_progress=False)
        items, users = np.asarray(model.item_factors), np.asarray(model.user_factors)
        # implicit хранит смещение фильма последним столбцом, а у людей там всегда 1
        has_bias = np.allclose(users[:, -1], 1)
        self.vectors = items[:, :-1] if has_bias else items
        self.bias = items[:, -1] if has_bias else np.zeros(len(items))
        return self

    def scores(self, inputs, user=None):
        index, _ = _positions(inputs, self.position)
        if not len(index):
            return self.bias.copy()
        x = self.vectors[index]
        u = np.linalg.solve(x.T @ x + self.fold_in_reg * np.eye(x.shape[1]), x.T @ (1 - self.bias[index]))
        return self.vectors @ u + self.bias


class SVD(Recommender):
    """Явная факторизация со смещениями: r ≈ μ + b_человека + b_фильма + p_человека · q_фильма.
    Обучение – ALS: по очереди точно решаются гребневые задачи для всех людей и всех фильмов; регуляризация
    растёт с числом оценок (reg · n). Учится на оценках фильмов-кандидатов."""

    def __init__(self, factors: int = 32, reg: float = 0.05, iterations: int = 8, seed: int = 0):
        self.factors, self.reg, self.iterations, self.seed = factors, reg, iterations, seed
        self.name = f"svd_f{factors}_r{reg:g}"

    def fit(self, history, pool=None):
        pool = pool if pool is not None else np.sort(history["movie_id"].unique())
        super().fit(history, pool)
        rows = history[np.isin(history["movie_id"], pool)]
        users, user_index = np.unique(rows["user_id"].to_numpy(), return_inverse=True)
        item_index = np.searchsorted(pool, rows["movie_id"].to_numpy())
        ratings = rows["rating"].to_numpy(np.float64)
        self.mu = float(ratings.mean())
        by_user = sp.csr_matrix((ratings, (user_index, item_index)), shape=(len(users), len(pool)))
        by_item = by_user.tocsc()
        rng = np.random.default_rng(self.seed)
        self.q = rng.normal(0, 0.1, (len(pool), self.factors))
        self.bi = np.zeros(len(pool))
        p, bu = np.zeros((len(users), self.factors)), np.zeros(len(users))
        for _ in range(self.iterations):
            p, bu = self._solve(by_user.indptr, by_user.indices, by_user.data, self.q, self.bi)
            self.q, self.bi = self._solve(by_item.indptr, by_item.indices, by_item.data, p, bu)
        return self

    def _solve(self, ptr, idx, r, other, other_bias):
        """Гребневая задача для каждой строки: вектор и смещение по оценкам строки при неизменной другой стороне."""
        k = other.shape[1]
        augmented = np.hstack([other, np.ones((len(other), 1))])
        vectors, bias = np.zeros((len(ptr) - 1, k)), np.zeros(len(ptr) - 1)
        eye = np.eye(k + 1)
        for row in range(len(ptr) - 1):
            start, end = ptr[row], ptr[row + 1]
            if start == end:
                continue
            x = augmented[idx[start:end]]
            target = r[start:end] - self.mu - other_bias[idx[start:end]]
            w = np.linalg.solve(x.T @ x + self.reg * (end - start) * eye, x.T @ target)
            vectors[row], bias[row] = w[:k], w[k]
        return vectors, bias

    def user_vector(self, inputs: pd.DataFrame) -> tuple[np.ndarray, float]:
        index, ratings = _positions(inputs, self.position)
        if not len(index):
            return np.zeros(self.factors), 0.0
        p, bu = self._solve(np.array([0, len(index)]), index, ratings, self.q, self.bi)
        return p[0], float(bu[0])

    def scores(self, inputs, user=None):
        p, bu = self.user_vector(inputs)
        return self.mu + bu + self.bi + self.q @ p

    def predict(self, inputs: pd.DataFrame, movies: np.ndarray) -> np.ndarray:
        p, bu = self.user_vector(inputs)
        index = self.position.reindex(movies).to_numpy()
        known = ~np.isnan(index)
        out = np.full(len(movies), self.mu + bu)
        rows = index[known].astype(np.int64)
        out[known] += self.bi[rows] + self.q[rows] @ p
        return np.clip(out, 0.5, 5.0)


def als_grid() -> list[ALS]:
    return [ALS(f, r, a) for f in (64, 128) for r in (0.01, 0.1) for a in (1.0, 10.0)]


def bpr_grid() -> list[BPR]:
    return [BPR(f, lr) for f in (64, 128) for lr in (0.01, 0.05)]


def svd_grid() -> list[SVD]:
    return [SVD(f, r) for f in (32, 64) for r in (0.03, 0.1)]
