"""Расчёты сайта на одном numpy – общие для выгрузки (export.py), её проверки (site_check.py) и бэкенда (шаг 7):
никаких implicit, scikit-learn, torch и pandas в памяти сайта."""
import re

import numpy as np

SITE_WEIGHT = 0.4  # вес популярности в смеси «популярность × ALS» (шаг 6в, подтверждён тестом)


def ranks(scores: np.ndarray) -> np.ndarray:
    """Ранг каждого балла от 0 (наименьший) до 1 (наибольший); при равенстве выше тот, кто раньше в списке –
    как в hybrid.ranks, по которому смесь выбиралась и проверялась."""
    out = np.empty(len(scores))
    out[np.argsort(-scores, kind="stable")] = 1 - np.arange(len(scores)) / max(len(scores) - 1, 1)
    return out


def fold_in(items: np.ndarray, gram: np.ndarray, regularization: float, alpha: float,
            index: np.ndarray) -> np.ndarray:
    """Вектор нового человека в неявном ALS (Hu, Koren, Volinsky, 2008) при неизменных векторах фильмов:
    (YᵀY + (c − 1)·YᵤᵀYᵤ + λI) x = c·Σ yᵢ, c = alpha – вес оценённого фильма (вход – только факт оценки)."""
    y = items[index].astype(np.float64)
    a = gram + (alpha - 1) * y.T @ y + regularization * np.eye(len(gram))
    return np.linalg.solve(a, alpha * y.sum(axis=0))


def contributions(items: np.ndarray, gram: np.ndarray, regularization: float, alpha: float, index: np.ndarray,
                  targets: np.ndarray) -> np.ndarray:
    """«Почему этот фильм»: вклад каждого оценённого фильма j в балл ALS фильма i – точное разложение,
    c[i, j] = α · yᵢ · A⁻¹ · yⱼ, сумма по j равна items[i] @ fold_in(...). Строки – targets, столбцы – index."""
    y = items[index].astype(np.float64)
    a = gram + (alpha - 1) * y.T @ y + regularization * np.eye(len(gram))
    return alpha * items[targets].astype(np.float64) @ np.linalg.solve(a, y.T)


def site_scores(popularity_ranks: np.ndarray, items: np.ndarray, gram: np.ndarray, index: np.ndarray,
                regularization: float = 0.1, alpha: float = 1.0, weight: float = SITE_WEIGHT) -> np.ndarray:
    """Баллы модели сайта: w · ранг популярности + (1 − w) · ранг ALS для человека с оценёнными фильмами index."""
    user = fold_in(items, gram, regularization, alpha, index)
    return weight * popularity_ranks + (1 - weight) * ranks(items @ user)


def centered(ratings: np.ndarray) -> np.ndarray:
    """Вес оценённого фильма в контентной модели: оценка минус средняя оценка человека (как content.Content,
    weighting="centered"); все оценки одинаковые – «минусов» нет, у каждого фильма вес 1."""
    w = np.asarray(ratings, dtype=np.float64) - float(np.mean(ratings))
    return np.ones(len(w)) if np.allclose(w, 0) else w


def content_scores(tfidf, index: np.ndarray, ratings: np.ndarray, candidates: np.ndarray | None = None) -> np.ndarray:
    """Баллы контентной модели (TF-IDF, вес centered): сходство вектора фильма с профилем человека – суммой
    векторов оценённых фильмов с весами centered. candidates – строки, которым нужен балл (None – все)."""
    profile = tfidf[index].T @ centered(ratings)
    target = tfidf if candidates is None else tfidf[candidates]
    return np.asarray(target @ profile).ravel()


def content_contributions(tfidf, index: np.ndarray, ratings: np.ndarray, targets: np.ndarray) -> np.ndarray:
    """«Почему эта новинка»: вклад оценённого фильма j в балл контентной модели фильма i – точное разложение
    content_scores: c[i, j] = centered(оценки)ⱼ · (tᵢ · tⱼ), сумма по j равна баллу. Строки – targets, столбцы – index."""
    sims = tfidf[targets] @ tfidf[index].T
    sims = sims.toarray() if hasattr(sims, "toarray") else np.asarray(sims)
    return sims * centered(ratings)


SEARCH_POOL = 50  # поиск: известность переставляет только первые SEARCH_POOL фильмов по смыслу (e5)
SEARCH_WEIGHT = 0.1  # вес известности (число оценок): на 30 запросах (search_site.py) – единственный не хуже e5


def search_scores(cosine: np.ndarray, popularity_ranks: np.ndarray, weight: float,
                  pool: int = SEARCH_POOL) -> np.ndarray:
    """Баллы поиска: первые pool фильмов по косинусу e5 переставляются смесью рангов внутри них –
    (1 − w) · ранг по смыслу + w · ранг популярности; остальные – −inf. weight = 0 – чистый e5."""
    top = np.argsort(-cosine, kind="stable")[:pool]
    out = np.full(len(cosine), -np.inf)
    out[top] = (1 - weight) * ranks(cosine[top]) + weight * ranks(popularity_ranks[top])
    return out


def normalize_title(text: str) -> str:
    """Название для сравнения с запросом: строчные, ё = е, без года «(1995)» и знаков препинания."""
    text = re.sub(r"\(\d{4}\)", " ", text.lower().replace("ё", "е"))
    return " ".join(re.findall(r"\w+", text))


def map_point(xy: np.ndarray, ratings: np.ndarray) -> np.ndarray | None:
    """Точка человека на карте вкусов – центр его фильмов с весом «насколько понравился»: max(оценка − 2,5; 0);
    если ни один не понравился – простой центр. xy – координаты оценённых фильмов, которые есть на карте."""
    if not len(xy):
        return None
    w = np.maximum(np.asarray(ratings, dtype=np.float64) - 2.5, 0)
    if w.sum() == 0:
        w = np.ones(len(xy))
    return w @ xy / w.sum()


def encode_query(sp_model, text: str, max_tokens: int = 512) -> list[int]:
    """Номера токенов e5 (XLM-R) через sentencepiece – без tokenizers (его словарь на 250 тыс. в памяти – 250 МБ).
    Как XLMRobertaTokenizer: номер sentencepiece + 1, неизвестный (0) – 3; по краям <s> = 0 и </s> = 2."""
    ids = [piece + 1 if piece else 3 for piece in sp_model.encode(text)][: max_tokens - 2]
    return [0, *ids, 2]
