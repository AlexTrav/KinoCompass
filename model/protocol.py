"""Протокол честной проверки рекомендаций: разбиение по времени, кандидаты и три сценария.

- История – все оценки до начала проверочной части; модели учатся только на ней.
- Проверочная часть – год после границы: валидация (14.10.2021 – 13.10.2022) для выбора моделей и настроек,
  тест (14.10.2022 – 13.10.2023) – один прогон на шаге 6, только явным PERIOD=test.
- Сценарии: «новичок» видит первые 5 или 10 оценок человека, впервые пришедшего в проверочный год (как на
  сайте), «постоянный» – всю свою историю до границы. Угадать нужно фильмы, оценённые на 4 и выше
  в проверочный год, среди кандидатов – фильмов минимум с 20 оценками до границы."""
from dataclasses import dataclass

import numpy as np
import pandas as pd

PERIODS = {
    "validation": ("2021-10-14", "2022-10-14"),
    "test": ("2022-10-14", "2023-10-14"),
}
MIN_ITEM_RATINGS = 20  # кандидаты – фильмы минимум с 20 оценками до границы (как каталог сайта)
POSITIVE = 4.0  # «понравилось»
COLD_INPUTS = (5, 10)  # сколько первых оценок новичка видит модель
COLUMNS = ["user_id", "movie_id", "rating", "time"]  # time – секунды Unix (UTC)


def bounds(period: str) -> tuple[int, int]:
    start, stop = PERIODS[period]
    return int(pd.Timestamp(start, tz="UTC").timestamp()), int(pd.Timestamp(stop, tz="UTC").timestamp())


def split(ratings: pd.DataFrame, period: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """История (всё строго до границы) и проверочный год. Модель получает только историю."""
    start, stop = bounds(period)
    history = ratings[ratings["time"] < start].reset_index(drop=True)
    future = ratings[(ratings["time"] >= start) & (ratings["time"] < stop)].reset_index(drop=True)
    return history, future


def candidates(history: pd.DataFrame) -> np.ndarray:
    """Фильмы минимум с MIN_ITEM_RATINGS оценками в истории – из них модели выбирают советы."""
    counts = history["movie_id"].value_counts()
    return np.sort(counts.index[counts >= MIN_ITEM_RATINGS].to_numpy())


@dataclass
class Case:
    """Один проверяемый человек: что видит модель и что она должна угадать."""
    user: int
    inputs: pd.DataFrame  # movie_id, rating – всё, что модель знает о человеке
    targets: np.ndarray  # фильмы-кандидаты, оценённые на 4+ в проверочный год (не из inputs)
    rated: pd.DataFrame  # movie_id, rating – все оценки кандидатам в проверочный год (для RMSE и MAE)


def _future_part(rows: pd.DataFrame, seen: np.ndarray, pool: np.ndarray) -> tuple[np.ndarray, pd.DataFrame]:
    rows = rows[np.isin(rows["movie_id"], pool) & ~np.isin(rows["movie_id"], seen)]
    rows = rows.drop_duplicates("movie_id", keep="last")
    targets = np.sort(rows.loc[rows["rating"] >= POSITIVE, "movie_id"].to_numpy())
    return targets, rows[["movie_id", "rating"]].reset_index(drop=True)


def warm_cases(history: pd.DataFrame, future: pd.DataFrame, pool: np.ndarray) -> list[Case]:
    """«Постоянные»: были в истории; модель видит всю их историю до границы."""
    returning = np.intersect1d(future["user_id"].unique(), history["user_id"].unique())
    known = history[history["user_id"].isin(returning)].groupby("user_id", sort=True)
    cases = []
    for user, rows in future[future["user_id"].isin(returning)].groupby("user_id", sort=True):
        inputs = known.get_group(user)[["movie_id", "rating"]].reset_index(drop=True)
        targets, rated = _future_part(rows, inputs["movie_id"].to_numpy(), pool)
        if len(targets):
            cases.append(Case(int(user), inputs, targets, rated))
    return cases


def cold_cases(history: pd.DataFrame, future: pd.DataFrame, pool: np.ndarray, k: int) -> list[Case]:
    """«Новички»: впервые пришли в проверочный год; модель видит их первые k оценок (по времени), угадать
    нужно остальные. Человек входит, если после k оценок у него есть хоть один понравившийся кандидат."""
    newcomers = future[~future["user_id"].isin(history["user_id"].unique())]
    cases = []
    for user, rows in newcomers.sort_values(["user_id", "time"], kind="stable").groupby("user_id", sort=True):
        if len(rows) <= k:
            continue
        inputs = rows.iloc[:k][["movie_id", "rating"]].reset_index(drop=True)
        targets, rated = _future_part(rows.iloc[k:], inputs["movie_id"].to_numpy(), pool)
        if len(targets):
            cases.append(Case(int(user), inputs, targets, rated))
    return cases


def scenarios(history: pd.DataFrame, future: pd.DataFrame, pool: np.ndarray) -> dict[str, list[Case]]:
    out = {f"cold{k}": cold_cases(history, future, pool, k) for k in COLD_INPUTS}
    out["warm"] = warm_cases(history, future, pool)
    return out


def load(period: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Набор в память (collect.movielens.fetch), затем история и проверочный год; плюс таблица фильмов."""
    from collect.movielens import fetch

    frames, _ = fetch()
    ratings = frames.pop("ratings")
    times = ratings["time"].dt.tz_localize(None).to_numpy().astype("datetime64[s]").astype(np.int64)
    ratings = pd.DataFrame({"user_id": ratings["user_id"].to_numpy(np.int32),
                            "movie_id": ratings["movie_id"].to_numpy(np.int32),
                            "rating": ratings["rating"].to_numpy(np.float32), "time": times})
    history, future = split(ratings, period)
    del ratings
    return history, future, frames["movies"]
