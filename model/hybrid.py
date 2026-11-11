"""Гибрид «свежесть × вкус»: смесь простой модели «что смотрят сейчас» с персональной моделью.

Баллы обеих моделей переводятся в ранги внутри кандидатов (0 – худший, 1 – лучший): так смешиваются модели
с любыми шкалами (счётчики популярности, произведения векторов, суммы сходств). Итог для кандидата:
    w · ранг базы + (1 − w) · ранг персональной модели.

- Подбор: база – популярные за последний год, персональная – ALS, item-kNN или Mult-VAE (те, что умещаются
  в память сайта). Сценарий проверки соответствует числу оценок человека (5, 10, вся история), поэтому вес w
  для каждого числа оценок выбирается по своему сценарию (шаг 6в).
- Новинки: база – «свежие по году», персональная – контент (сходство описаний): на шаге 5 свежесть оказалась
  сильнее вкуса, а контент – персональнее."""
import numpy as np
import pandas as pd

from baselines import Recommender


def ranks(scores: np.ndarray) -> np.ndarray:
    """Ранг каждого балла от 0 (наименьший) до 1 (наибольший); при равенстве выше тот, кто раньше в списке
    кандидатов, – как в Recommender.recommend, поэтому при w = 1 гибрид повторяет базу в точности."""
    out = np.empty(len(scores))
    out[np.argsort(-scores, kind="stable")] = 1 - np.arange(len(scores)) / max(len(scores) - 1, 1)
    return out


class Hybrid(Recommender):
    def __init__(self, base: Recommender, personal: Recommender, weight: float):
        self.base, self.personal, self.weight = base, personal, weight
        self.name = f"hybrid_{base.name}_{personal.name}_w{weight:g}"

    def attach(self, side: pd.DataFrame) -> None:
        for model in (self.base, self.personal):
            if hasattr(model, "attach"):
                model.attach(side)

    def fit(self, history, pool):
        super().fit(history, pool)
        # одна персональная модель и одна база на всю сетку весов: обучаются только при первой встрече
        key = (id(history), len(history), len(pool), int(pool[0]), int(pool[-1]))
        for model in (self.base, self.personal):
            if getattr(model, "fitted_on", None) != key:
                model.fit(history, pool)
                model.fitted_on = key
        self.base_ranks = ranks(np.asarray(self.base.scores(pd.DataFrame({"movie_id": [], "rating": []})),
                                           dtype=np.float64))
        return self

    def scores(self, inputs, user=None):
        personal = ranks(np.asarray(self.personal.scores(inputs, user), dtype=np.float64))
        return self.weight * self.base_ranks + (1 - self.weight) * personal


WEIGHTS = (0.2, 0.4, 0.6, 0.8)
# новинки: первая сетка дала лучший вес свежести 0,8 – на краю, сетка расширена вправо
NEW_WEIGHTS = (*WEIGHTS, 0.9, 0.95)


def grid(base: Recommender, personal: Recommender, weights: tuple[float, ...] = WEIGHTS) -> list[Hybrid]:
    """Сетка весов базы; чистые модели (w = 0 и w = 1) идут в прогон отдельно, как планка."""
    return [Hybrid(base, personal, w) for w in weights]
