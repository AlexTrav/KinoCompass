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
from protocol import MIN_ITEM_RATINGS, PERIODS, POSITIVE, Case, candidates, load, new_items, scenarios

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
    # фильм без оценок в истории (новинка) считается как полоценки: иначе новизна −log₂ 0 бесконечна
    share = np.maximum(np.bincount(history["movie_id"], minlength=size), 0.5) / len(history)
    bits = np.zeros(size, dtype=np.uint32)
    index = {genre: i for i, genre in enumerate(GENRE_LIST)}
    for movie_id, genres in zip(movies["movie_id"], movies["genres"]):
        bits[movie_id] = sum(1 << index[g] for g in parse_genres(genres).split("|") if g in index)
    return Context(pool, share, bits)


def rank_model(model: baselines.Recommender, cases: list[Case], ctx: Context) -> tuple[pd.DataFrame, float, float]:
    """Метрики каждого человека, покрытие каталога первыми 10 советами и время совета одному человеку, мс."""
    rows, lists = [], []
    tic = time.perf_counter()
    for case in cases:
        recommended = model.recommend(case.inputs, max(KS), case.user)
        row = {}
        for k in KS:
            row |= list_metrics(recommended, case.targets, k)
        row["novelty@10"] = novelty(recommended[:10], ctx.share)
        row["diversity@10"] = diversity(recommended[:10], ctx.bits)
        rows.append(row)
        lists.append(recommended[:10])
    ms = (time.perf_counter() - tic) * 1000 / max(len(cases), 1)  # вместе с метриками – верхняя оценка
    return pd.DataFrame(rows, index=[c.user for c in cases]), coverage(lists, len(ctx.pool)), ms


def summarize(frame: pd.DataFrame, cover: float, ms: float) -> dict:
    out = {name: round(float(value), 5) for name, value in frame.mean().items()}
    out["coverage@10"] = round(cover, 5)
    out["ms_per_user"] = round(ms, 2)
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


POOLS = {"candidates": "", "new": "_new"}  # набор кандидатов -> суффикс файлов отчёта


def run(name: str, ranking, rating: list[baselines.GlobalMean], pools: tuple[str, ...] = ("candidates",)) -> dict:
    """Набор скачивается один раз; затем для каждого набора кандидатов – свой отчёт: candidates – фильмы
    минимум с 20 оценками до границы, new – «новинки» каталога с меньшим числом оценок (только контент).
    ranking – список моделей для всех наборов или словарь «набор -> свои модели»."""
    per_pool = ranking if isinstance(ranking, dict) else {kind: ranking for kind in pools}
    pools = tuple(per_pool)
    models = [model for group in per_pool.values() for model in group]
    period = period_from_env()
    started = time.time()
    history, future, movies, tags = load(period)
    loaded = round(time.time() - started, 1)
    side = None
    if any(hasattr(model, "attach") for model in models):  # контентным моделям – описание фильмов
        import content

        side = content.build_side(tags)
        for model in models:
            if hasattr(model, "attach"):
                model.attach(side)
    reports = {}
    for kind in pools:
        pool = candidates(history) if kind == "candidates" else new_items(history, side["year"], period)
        # предсказание звёзд (rating) – только на первом наборе: на новинках RMSE не нужен
        reports[kind] = run_pool(name, period, kind, history, future, movies, pool, per_pool[kind],
                                 rating if kind == pools[0] else [],
                                 {"load": loaded}, time.time())
    return reports[pools[0]] if len(pools) == 1 else reports


def run_pool(name, period, kind, history, future, movies, pool, ranking, rating, stages, started) -> dict:
    print(f"кандидаты: {kind}, {len(pool)} фильмов", flush=True)
    cases = scenarios(history, future, pool)
    for scenario in [s for s, people in cases.items() if not people]:
        print(f"сценарий {scenario}: нет подходящих людей – пропущен", flush=True)
        del cases[scenario]
    stages["scenarios"] = round(time.time() - started, 1)
    ctx = context(history, movies, pool)
    liked = future[future["rating"] >= POSITIVE]
    report = {
        "period": period, "pool": kind, "bounds": PERIODS[period], "positive": POSITIVE,
        "min_item_ratings": MIN_ITEM_RATINGS,
        "history_ratings": len(history), "period_ratings": len(future), "candidates": len(pool),
        "liked_outside_candidates": round(float((~liked["movie_id"].isin(pool)).mean()), 4),
        "scenarios": {s: {"people": len(c), "median_inputs": int(np.median([len(x.inputs) for x in c])),
                          "median_targets": int(np.median([len(x.targets) for x in c]))} for s, c in cases.items()},
        "fit_seconds": {}, "ranking": {}, "significance": {}, "rating": {},
    }
    print("сценарии:", report["scenarios"], flush=True)
    # модели по одной: обучение -> проверка во всех сценариях -> освобождение памяти (EASE держит 2 ГБ)
    per_user = {scenario: {} for scenario in cases}
    report["ranking"] = {scenario: {} for scenario in cases}
    report["rating"] = {scenario: {} for scenario in cases}
    stages["fit"] = stages["evaluate"] = 0.0
    for model in ranking + [m for m in rating if m not in ranking]:
        tic = time.time()
        if model in ranking:
            baselines.fit_once(model, history, pool)  # уже обученная внутри смеси – не переучивается
        else:
            model.fit(history)
        report["fit_seconds"][model.name] = round(time.time() - tic, 2)
        stages["fit"] += time.time() - tic
        tic = time.time()
        for scenario, people in cases.items():
            if model in ranking:
                frame, cover, ms = rank_model(model, people, ctx)
                per_user[scenario][model.name] = frame[MAIN]
                report["ranking"][scenario][model.name] = summarize(frame, cover, ms)
                print(scenario, model.name, MAIN, report["ranking"][scenario][model.name][MAIN], flush=True)
            if model in rating:  # SVD и советует, и предсказывает оценку – обучается один раз
                report["rating"][scenario][model.name] = rate_model(model, people)
        stages["evaluate"] += time.time() - tic
        if hasattr(model, "release"):
            model.release()
            model.fitted_on = None  # память освобождена – следующей смеси придётся обучить заново
    users = []
    for scenario in cases:
        report["significance"][scenario] = significance(per_user[scenario])
        users.append(pd.DataFrame(per_user[scenario]).rename_axis("user").reset_index().assign(scenario=scenario))
    # итоговый балл – среднее NDCG@10 по трём сценариям (критерий выбора настроек и модели по умолчанию)
    report["score"] = {model.name: round(float(np.mean([report["ranking"][s][model.name][MAIN] for s in cases])), 5)
                       for model in ranking}
    report["best"] = max(report["score"], key=report["score"].get) if ranking else None
    stages = {key: round(value, 1) for key, value in stages.items()}
    report["stage_seconds"] = stages
    report["seconds"] = round(stages["load"] + time.time() - started, 1)  # вместе с загрузкой набора
    print("этапы, с:", stages, flush=True)
    out = REPORTS / name / f"{period}{POOLS[kind]}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # NDCG@10 каждого человека – для парных тестов между прогонами (в том числе из Colab)
    pd.concat(users, ignore_index=True).round(5).to_csv(out.with_name(f"{period}{POOLS[kind]}_users.csv.gz"),
                                                        index=False)
    print(f"сохранено {out.relative_to(REPORTS.parent)} за {report['seconds']} с")
    return report


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "baselines":
        run("baselines", baselines.ranking_models(), baselines.rating_models())
    elif command == "knn":
        import knn

        # планка – лучшая базовая модель, в том же прогоне: те же люди, парный тест напрямую
        run("knn", [baselines.RecentPopularity(), *knn.item_grid(), *knn.user_grid()], [])
    elif command == "factorization":
        import factorization as f

        svd = f.svd_grid()
        run("factorization", [baselines.RecentPopularity(), *f.als_grid(), *f.bpr_grid(), *svd],
            [baselines.Biases(), *svd])
    elif command == "ease":
        import ease

        # EASE на всех кандидатах – в Colab на GPU (notebooks/ease.ipynb); без GPU – только на маленьких данных
        run("ease", [baselines.RecentPopularity(), *ease.ease_grid()], [])
    elif command == "content":
        import content

        # те же модели на двух наборах: кандидаты (сравнение с шагом 4) и «новинки» (только контент и база);
        # python evaluate.py content new – только новинки
        pools = tuple(p for p in ("candidates", "new") if len(sys.argv) < 3 or p in sys.argv[2:])
        run("content", [baselines.RandomModel(), content.Newest(), baselines.RecentPopularity(), *content.grid()],
            [], pools=pools)
    elif command == "vae":
        import vae

        # Mult-VAE – в Colab на GPU (notebooks/vae.ipynb); без GPU – только на маленьких данных
        run("vae", [baselines.RecentPopularity(), *vae.vae_grid()], [])
    elif command == "hybrid_vae":
        import hybrid
        import vae

        # популярные за год × Mult-VAE (лучший вариант сетки шага 6а) – в Colab на GPU (notebooks/hybrid_vae.ipynb);
        # сам Mult-VAE отдельно уже проверен (reports/vae), здесь обучается один раз – внутри первой смеси
        popular, model = baselines.RecentPopularity(), vae.MultVAE(latent=400, beta=0.5)
        run("hybrid_vae", [popular, *hybrid.grid(popular, model)], [])
    elif command == "hybrid":
        import content
        import factorization
        import hybrid
        import knn

        # подбор: популярные за год × (ALS | item-kNN) – лучшие настройки шага 4, умещающиеся в память сайта;
        # новинки: свежие по году × контент (лучший на новинках на шаге 5); чистые модели – в том же прогоне
        popular, als = baselines.RecentPopularity(), factorization.ALS(64, 0.1, 1.0)
        item_knn, newest = knn.ItemKNN("cosine", 200, "binary"), content.Newest()
        text = content.TfidfContent(words=True, weighting="centered")
        pools = {
            "candidates": [popular, als, item_knn, *hybrid.grid(popular, als), *hybrid.grid(popular, item_knn)],
            "new": [newest, text, *hybrid.grid(newest, text, hybrid.NEW_WEIGHTS)],
        }
        # python evaluate.py hybrid new – только новинки (минуты вместо 20 минут кандидатов)
        only = sys.argv[2:]
        run("hybrid", {kind: models for kind, models in pools.items() if not only or kind in only}, [])
    elif command == "final_gpu":
        import ease
        import hybrid
        import vae

        # итог шага 6, часть для GPU (Colab, notebooks/final_gpu.ipynb): лучшие EASE и Mult-VAE и смесь
        # «популярность × Mult-VAE» с весом, выбранным на валидации; популярность – для парных сравнений
        popular, model = baselines.RecentPopularity(), vae.MultVAE(latent=400, beta=0.5)
        # смесь – раньше отдельного Mult-VAE: он учится один раз, а память освобождает последним
        # EASE: обращение матрицы на процессоре – на тесте (22 309 кандидатов) не хватило видеопамяти T4
        run("final_gpu", [popular, ease.EASE(5000.0, solve_on="cpu"), hybrid.Hybrid(popular, model, 0.2), model], [])
    elif command == "final":
        import content
        import factorization
        import hybrid
        import knn

        # итог шага 6: лучшие настройки каждого семейства, выбранные на валидации, и гибриды для сайта; на тесте
        # (PERIOD=test) – один прогон, модели учатся на обучении + валидации. EASE и Mult-VAE – в Colab (final_gpu)
        popular, als = baselines.RecentPopularity(), factorization.ALS(64, 0.1, 1.0)
        svd, newest = factorization.SVD(64, 0.03), content.Newest()
        text = content.TfidfContent(words=True, weighting="centered")
        run("final", {
            "candidates": [popular, knn.UserKNN(200), knn.ItemKNN("cosine", 200, "binary"), als, svd,
                           content.TfidfContent(words=False, weighting="centered"), hybrid.Hybrid(popular, als, 0.4)],
            "new": [newest, text, hybrid.Hybrid(newest, text, 0.9)],
        }, [baselines.Biases(), svd])
    else:
        sys.exit("использование: python evaluate.py baselines|knn|factorization|ease|content|vae|hybrid|hybrid_vae"
                 "|final|final_gpu")


if __name__ == "__main__":
    main()
