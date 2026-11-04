"""Метрики качества рекомендаций и тесты значимости.

Точность списка из K советов: Precision, Recall, NDCG, MAP, HitRate (релевантно – фильм оценён на 4+).
Свойства советов: покрытие каталога, новизна, разнообразие по жанрам. Оценки: RMSE и MAE.
Значимость: парный тест Уилкоксона по людям с поправкой Холма, доверительные интервалы – бутстрепом."""
import numpy as np
from scipy import stats

KS = (10, 20)


def list_metrics(recommended: np.ndarray, targets: np.ndarray, k: int) -> dict[str, float]:
    """Метрики одного человека для первых k советов. Recall – доля всех понравившихся, NDCG и MAP нормируются
    на лучший возможный список длины min(k, число понравившихся)."""
    top = np.asarray(recommended[:k])
    hits = np.isin(top, targets).astype(np.float64)
    ideal = min(k, len(targets))
    discount = 1 / np.log2(np.arange(2, k + 2))
    precision_at = np.cumsum(hits) / np.arange(1, len(hits) + 1)
    return {
        f"precision@{k}": float(hits.sum() / k),
        f"recall@{k}": float(hits.sum() / len(targets)),
        f"ndcg@{k}": float((hits * discount[: len(hits)]).sum() / discount[:ideal].sum()),
        f"map@{k}": float((precision_at * hits).sum() / ideal),
        f"hit@{k}": float(hits.any()),
    }


def coverage(lists: list[np.ndarray], n_candidates: int) -> float:
    """Доля каталога-кандидатов, которая хоть раз попала в советы."""
    return len(np.unique(np.concatenate(lists))) / n_candidates if lists else 0.0


def novelty(recommended: np.ndarray, share: dict[int, float] | np.ndarray) -> float:
    """Средняя «неожиданность» советов: −log₂ доли оценок фильма в истории (больше – менее заезженные)."""
    return float(np.mean(-np.log2(share[recommended])))


def diversity(recommended: np.ndarray, genre_bits: np.ndarray) -> float:
    """1 − средняя косинусная близость жанров между парами советов (0 – все одного жанра, 1 – без общих)."""
    bits = genre_bits[recommended].astype(np.uint32)
    sizes = np.bitwise_count(bits).astype(np.float64)
    common = np.bitwise_count(bits[:, None] & bits[None, :]).astype(np.float64)
    norm = np.sqrt(np.outer(sizes, sizes))
    with np.errstate(invalid="ignore", divide="ignore"):
        cosine = np.where(norm > 0, common / norm, 0.0)
    upper = np.triu_indices(len(bits), 1)
    return float(1 - cosine[upper].mean()) if len(upper[0]) else 0.0


def rmse_mae(errors: np.ndarray) -> dict[str, float]:
    return {"rmse": float(np.sqrt(np.mean(errors ** 2))), "mae": float(np.mean(np.abs(errors)))}


def bootstrap_ci(values: np.ndarray, n: int = 2000, seed: int = 0, level: float = 0.95) -> tuple[float, float]:
    """Доверительный интервал среднего по людям: перевыборка людей с возвращением."""
    values = np.asarray(values, dtype=np.float64)
    rng = np.random.default_rng(seed)
    means = values[rng.integers(0, len(values), size=(n, len(values)))].mean(axis=1)
    tail = (1 - level) / 2
    return float(np.quantile(means, tail)), float(np.quantile(means, 1 - tail))


def wilcoxon(a: np.ndarray, b: np.ndarray) -> float:
    """p-значение парного теста Уилкоксона (одни и те же люди у двух моделей); при полном совпадении – 1."""
    diff = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    if not np.any(diff):
        return 1.0
    return float(stats.wilcoxon(a, b).pvalue)


def holm(pvalues: list[float]) -> list[float]:
    """Поправка Холма на множественные сравнения: скорректированные p-значения в исходном порядке."""
    order = np.argsort(pvalues)
    m = len(pvalues)
    adjusted = np.empty(m)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[index]))
        adjusted[index] = running
    return adjusted.tolist()
