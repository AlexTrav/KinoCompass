"""Общий интерфейс моделей и базовые модели – планка для kNN, факторизации, контентной модели и Mult-VAE.

Модель учится на истории (fit), а советует по входу человека (scores): у «постоянного» это вся его история,
у «новичка» – первые 5–10 оценок, как на сайте. Так все модели проверяются одинаково и работают на сайте
без переобучения."""
import numpy as np
import pandas as pd

from protocol import POSITIVE

YEAR_SEC = 365 * 86_400


class Recommender:
    """Ранжирует кандидатов: scores – балл каждого кандидата для человека (больше – выше в списке)."""
    name = "?"

    def fit(self, history: pd.DataFrame, pool: np.ndarray) -> "Recommender":
        self.pool = pool
        self.position = pd.Series(np.arange(len(pool)), index=pool)  # id фильма -> номер кандидата
        return self

    def scores(self, inputs: pd.DataFrame, user: int | None = None) -> np.ndarray:
        raise NotImplementedError

    def recommend(self, inputs: pd.DataFrame, k: int, user: int | None = None) -> np.ndarray:
        """k лучших кандидатов, кроме уже оценённых человеком; при равных баллах – по порядку id."""
        scores = np.asarray(self.scores(inputs, user), dtype=np.float64).copy()
        seen = self.position.reindex(inputs["movie_id"]).dropna().to_numpy(np.int64)
        scores[seen] = -np.inf
        if k < len(scores):
            # argpartition среди равных на границе выбирает произвольно – берутся все, кто не хуже k-го балла
            kth = scores[np.argpartition(-scores, k - 1)[k - 1]]
            top = np.flatnonzero(scores >= kth)
        else:
            top = np.arange(len(scores))
        top = top[np.lexsort((top, -scores[top]))][:k]
        return self.pool[top]


def fit_once(model: Recommender, history: pd.DataFrame, pool: np.ndarray) -> Recommender:
    """Обучить, если модель ещё не обучена на этих же данных: одна модель может стоять в прогоне и отдельно, и
    внутри смеси (hybrid.py), – тогда она учится один раз (Mult-VAE на GPU – 8 минут)."""
    key = (id(history), len(history), len(pool), int(pool[0]), int(pool[-1]))
    if getattr(model, "fitted_on", None) != key:
        model.fit(history, pool)
        model.fitted_on = key
    return model


class Static(Recommender):
    """Один и тот же порядок для всех – отличаются лишь исключённые уже оценённые фильмы."""

    def scores(self, inputs: pd.DataFrame, user: int | None = None) -> np.ndarray:
        return self.static

    def counts(self, history: pd.DataFrame) -> np.ndarray:
        return history["movie_id"].value_counts().reindex(self.pool, fill_value=0).to_numpy(np.float64)


class RandomModel(Recommender):
    """Случайный порядок для каждого человека – нижняя граница, проверка, что метрики считаются верно."""
    name = "random"

    def __init__(self, seed: int = 0):
        self.rng = np.random.default_rng(seed)

    def scores(self, inputs: pd.DataFrame, user: int | None = None) -> np.ndarray:
        return self.rng.random(len(self.pool))


class Popularity(Static):
    """Самые оцениваемые фильмы за всю историю."""
    name = "popular"

    def fit(self, history, pool):
        super().fit(history, pool)
        self.static = self.counts(history)
        return self


class RecentPopularity(Static):
    """Самые оцениваемые за последний год до границы – учитывает моду."""
    name = "popular_year"

    def fit(self, history, pool):
        super().fit(history, pool)
        recent = history[history["time"] >= history["time"].max() - YEAR_SEC]
        # при равенстве за год выше тот, кого больше оценивали всегда
        self.static = self.counts(recent) + self.counts(history) / (len(history) + 1)
        return self


class LikedPopularity(Static):
    """Больше всего оценок 4 и выше – «популярное среди понравившегося»."""
    name = "popular_liked"

    def fit(self, history, pool):
        super().fit(history, pool)
        self.static = self.counts(history[history["rating"] >= POSITIVE])
        return self


class BestRated(Static):
    """Лучшие по средней оценке со сглаживанием: (n · среднее + m · общее среднее) / (n + m) – фильм с парой
    пятёрок не обгонит признанную классику."""
    name = "best_rated"

    def __init__(self, m: float = 100):
        self.m = m

    def fit(self, history, pool):
        super().fit(history, pool)
        stats = history.groupby("movie_id")["rating"].agg(["size", "mean"]).reindex(pool)
        mu = float(history["rating"].mean())
        self.static = ((stats["size"] * stats["mean"] + self.m * mu) / (stats["size"] + self.m)).to_numpy()
        return self


# ---------- предсказание оценки ---------------------------------------------------------------------------------

class GlobalMean:
    """Одно число на всех – средняя оценка истории."""
    name = "global_mean"

    def fit(self, history: pd.DataFrame) -> "GlobalMean":
        self.mu = float(history["rating"].mean())
        return self

    def predict(self, inputs: pd.DataFrame, movies: np.ndarray) -> np.ndarray:
        return np.full(len(movies), self.mu)


class Biases(GlobalMean):
    """Общее среднее + смещение фильма + смещение человека, со сглаживанием (Koren, 2010): «этот фильм ценят
    выше среднего, этот человек строже других». Смещение человека считается по его входу – у новичка по 5–10
    оценкам, поэтому модель годится и для сайта."""
    name = "biases"

    def __init__(self, item_reg: float = 25, user_reg: float = 10):
        self.item_reg, self.user_reg = item_reg, user_reg

    def fit(self, history):
        super().fit(history)
        groups = (history["rating"] - self.mu).groupby(history["movie_id"])
        self.item_bias = groups.sum() / (groups.size() + self.item_reg)
        return self

    def user_bias(self, inputs: pd.DataFrame) -> float:
        residual = inputs["rating"].to_numpy() - self.mu - self.item_bias.reindex(inputs["movie_id"], fill_value=0).to_numpy()
        return float(residual.sum() / (len(residual) + self.user_reg))

    def predict(self, inputs, movies):
        raw = self.mu + self.item_bias.reindex(movies, fill_value=0).to_numpy() + self.user_bias(inputs)
        return np.clip(raw, 0.5, 5.0)


def ranking_models() -> list[Recommender]:
    return [RandomModel(), Popularity(), RecentPopularity(), LikedPopularity(), BestRated()]


def rating_models() -> list[GlobalMean]:
    return [GlobalMean(), Biases()]
