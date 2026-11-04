"""Прогон моделей по протоколу проверки: python evaluate.py baselines -> reports/baselines/<PERIOD>.json.

Набор скачивается в память один раз за запуск; все модели учатся на одной истории и проверяются на одних
и тех же людях всех сценариев – поэтому их можно сравнивать парным тестом. Проверочная часть – переменная
окружения PERIOD: validation (по умолчанию) или test (только явно, один раз на шаге 6)."""
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

import baselines
from collect.catalog import parse_genres
from collect.config import GENRES
from metrics import KS, bootstrap_ci, coverage, diversity, holm, list_metrics, novelty, rmse_mae, wilcoxon
from protocol import MIN_ITEM_RATINGS, PERIODS, POSITIVE, Case, candidates, load, scenarios

REPORTS = Path(__file__).resolve().parent / "reports"
MAIN = "ndcg@10"  # главная метрика: по ней выбирается лучшая модель и считается значимость
GENRE_LIST = sorted(GENRES - {"IMAX"})  # IMAX – формат показа, а не жанр


@dataclass
class Context:
    pool: np.ndarray  # кандидаты
    share: np.ndarray  # доля оценок фильма в истории (по id) – для новизны
    bits: np.ndarray  # жанры фильма битовой маской (по id) – для разнообразия


def context(history: pd.DataFrame, movies: pd.DataFrame, pool: np.ndarray) -> Context:
    size = int(max(movies["movie_id"].max(), history["movie_id"].max())) + 1
    share = np.bincount(history["movie_id"], minlength=size) / len(history)
    bits = np.zeros(size, dtype=np.uint32)
    index = {genre: i for i, genre in enumerate(GENRE_LIST)}
    for movie_id, genres in zip(movies["movie_id"], movies["genres"]):
        bits[movie_id] = sum(1 << index[g] for g in parse_genres(genres).split("|") if g in index)
    return Context(pool, share, bits)


def rank_model(model: baselines.Recommender, cases: list[Case], ctx: Context) -> tuple[pd.DataFrame, float]:
    """Метрики каждого человека и покрытие каталога первыми 10 советами."""
    rows, lists = [], []
    for case in cases:
        recommended = model.recommend(case.inputs, max(KS))
        row = {}
        for k in KS:
            row |= list_metrics(recommended, case.targets, k)
        row["novelty@10"] = novelty(recommended[:10], ctx.share)
        row["diversity@10"] = diversity(recommended[:10], ctx.bits)
        rows.append(row)
        lists.append(recommended[:10])
    return pd.DataFrame(rows, index=[c.user for c in cases]), coverage(lists, len(ctx.pool))


def summarize(frame: pd.DataFrame, cover: float) -> dict:
    out = {name: round(float(value), 5) for name, value in frame.mean().items()}
    out["coverage@10"] = round(cover, 5)
    out[f"{MAIN}_ci95"] = [round(v, 5) for v in bootstrap_ci(frame[MAIN].to_numpy())]
    return out


def rate_model(model: baselines.GlobalMean, cases: list[Case]) -> dict:
    errors = np.concatenate([model.predict(c.inputs, c.rated["movie_id"].to_numpy()) - c.rated["rating"].to_numpy()
                             for c in cases])
    return {name: round(value, 5) for name, value in rmse_mae(errors).items()} | {"pairs": int(len(errors))}


def significance(per_user: dict[str, pd.Series]) -> dict:
    """Лучшая по главной метрике против каждой другой: парный Уилкоксон по людям, поправка Холма."""
    best = max(per_user, key=lambda name: per_user[name].mean())
    others = [name for name in per_user if name != best]
    raw = [wilcoxon(per_user[best].to_numpy(), per_user[name].to_numpy()) for name in others]
    adjusted = holm(raw)
    return {"best": best, "vs": {name: {"p": p, "p_holm": q} for name, p, q in zip(others, raw, adjusted)}}


def period_from_env() -> str:
    period = os.environ.get("PERIOD", "validation")
    if period not in PERIODS:
        sys.exit(f"PERIOD должен быть одним из {list(PERIODS)}")
    return period


def run(name: str, ranking: list[baselines.Recommender], rating: list[baselines.GlobalMean]) -> dict:
    period = period_from_env()
    started = time.time()
    history, future, movies = load(period)
    pool = candidates(history)
    cases = scenarios(history, future, pool)
    ctx = context(history, movies, pool)
    liked = future[future["rating"] >= POSITIVE]
    report = {
        "period": period, "bounds": PERIODS[period], "positive": POSITIVE, "min_item_ratings": MIN_ITEM_RATINGS,
        "history_ratings": len(history), "period_ratings": len(future), "candidates": len(pool),
        "liked_outside_candidates": round(float((~liked["movie_id"].isin(pool)).mean()), 4),
        "scenarios": {s: {"people": len(c), "median_inputs": int(np.median([len(x.inputs) for x in c])),
                          "median_targets": int(np.median([len(x.targets) for x in c]))} for s, c in cases.items()},
        "fit_seconds": {}, "ranking": {}, "significance": {}, "rating": {},
    }
    print("сценарии:", report["scenarios"], flush=True)
    for model in ranking:
        tic = time.time()
        model.fit(history, pool)
        report["fit_seconds"][model.name] = round(time.time() - tic, 2)
    for model in rating:
        model.fit(history)
    for scenario, people in cases.items():
        per_user, report["ranking"][scenario] = {}, {}
        for model in ranking:
            frame, cover = rank_model(model, people, ctx)
            per_user[model.name] = frame[MAIN]
            report["ranking"][scenario][model.name] = summarize(frame, cover)
            print(scenario, model.name, MAIN, report["ranking"][scenario][model.name][MAIN], flush=True)
        report["significance"][scenario] = significance(per_user)
        report["rating"][scenario] = {model.name: rate_model(model, people) for model in rating}
    report["seconds"] = round(time.time() - started, 1)
    out = REPORTS / name / f"{period}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"сохранено {out.relative_to(REPORTS.parent)} за {report['seconds']} с")
    return report


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "baselines":
        run("baselines", baselines.ranking_models(), baselines.rating_models())
    else:
        sys.exit("использование: python evaluate.py baselines")


if __name__ == "__main__":
    main()
