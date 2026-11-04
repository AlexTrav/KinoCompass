import numpy as np
import pandas as pd
import pytest

import baselines
import metrics
import protocol

START, STOP = protocol.bounds("validation")
DAY = 86_400


# --- метрики ----------------------------------------------------------------------------------------------------

def test_list_metrics_by_hand():
    rec = np.array([5, 1, 7, 2, 9])
    out = metrics.list_metrics(rec, np.array([1, 2, 3]), 5)
    assert out["precision@5"] == pytest.approx(2 / 5)
    assert out["recall@5"] == pytest.approx(2 / 3)
    assert out["hit@5"] == 1.0
    # попадания на 2-м и 4-м месте; идеал – 3 попадания на первых местах
    dcg = 1 / np.log2(3) + 1 / np.log2(5)
    idcg = 1 + 1 / np.log2(3) + 1 / np.log2(4)
    assert out["ndcg@5"] == pytest.approx(dcg / idcg)
    assert out["map@5"] == pytest.approx((1 / 2 + 2 / 4) / 3)


def test_perfect_and_empty_lists():
    perfect = metrics.list_metrics(np.array([3, 4]), np.array([3, 4]), 2)
    assert perfect["ndcg@2"] == pytest.approx(1) and perfect["map@2"] == pytest.approx(1)
    miss = metrics.list_metrics(np.array([8, 9]), np.array([3]), 2)
    assert miss["ndcg@2"] == 0 and miss["hit@2"] == 0


def test_coverage_novelty_diversity():
    assert metrics.coverage([np.array([1, 2]), np.array([2, 3])], 10) == pytest.approx(0.3)
    share = np.array([0, 0.5, 0.25])
    assert metrics.novelty(np.array([1, 2]), share) == pytest.approx(1.5)
    bits = np.array([0, 0b01, 0b01, 0b10], dtype=np.uint32)
    assert metrics.diversity(np.array([1, 2]), bits) == pytest.approx(0)  # один жанр
    assert metrics.diversity(np.array([1, 3]), bits) == pytest.approx(1)  # без общих жанров


def test_holm_and_wilcoxon_and_bootstrap():
    assert metrics.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    a = np.linspace(0.5, 1, 30)
    assert metrics.wilcoxon(a, a) == 1.0
    assert metrics.wilcoxon(a, a - 0.1) < 0.001
    lo, hi = metrics.bootstrap_ci(np.r_[np.zeros(50), np.ones(50)])
    assert lo < 0.5 < hi and metrics.bootstrap_ci(np.ones(10)) == (1.0, 1.0)


# --- протокол ---------------------------------------------------------------------------------------------------

def frame(rows):
    return pd.DataFrame(rows, columns=protocol.COLUMNS)


@pytest.fixture
def ratings():
    rows = []
    # фильмы 1–3 – популярные в истории (по 20 оценок), фильм 4 – редкий
    for user in range(100, 120):
        rows += [(user, 1, 4.0, START - 10 * DAY), (user, 2, 3.0, START - 9 * DAY), (user, 3, 5.0, START - 8 * DAY)]
    rows.append((100, 4, 5.0, START - 7 * DAY))
    # постоянный 100: в проверочный год любит 2 (уже видел – не цель) и… ничего нового → не войдёт
    rows.append((100, 2, 5.0, START + DAY))
    # постоянный 101: любит в проверочный год фильм 4 (не кандидат) – не цель
    rows.append((101, 4, 5.0, START + DAY))
    # новичок 7: шесть оценок в проверочный год, понравились 2 и 3
    times = [START + DAY * i for i in range(6)]
    for movie, rating, t in zip([1, 4, 1, 2, 3, 2], [3.0, 2.0, 4.0, 5.0, 4.5, 2.0], times):
        rows.append((7, movie, rating, t))
    rows.append((8, 1, 5.0, STOP + DAY))  # после проверочного года – не попадает никуда
    return frame(rows)


def test_split_never_leaks_future(ratings):
    history, future = protocol.split(ratings, "validation")
    assert (history["time"] < START).all()
    assert future["time"].between(START, STOP - 1).all()
    assert 8 not in set(future["user_id"])


def test_candidates_need_min_ratings(ratings):
    history, _ = protocol.split(ratings, "validation")
    assert protocol.candidates(history).tolist() == [1, 2, 3]


def test_cold_cases_see_only_first_k(ratings):
    history, future = protocol.split(ratings, "validation")
    pool = protocol.candidates(history)
    case = protocol.cold_cases(history, future, pool, 2)[0]
    assert case.user == 7 and case.inputs["movie_id"].tolist() == [1, 4]
    # из оставшихся 1 (4,0), 2 (5,0), 3 (4,5), 2 (2,0): фильм 1 уже во входе; у фильма 2 – последняя оценка 2,0
    assert case.targets.tolist() == [3]
    assert sorted(case.rated["movie_id"]) == [2, 3]
    assert protocol.cold_cases(history, future, pool, 6) == []  # после 6 оценок угадывать нечего


def test_warm_cases_exclude_history(ratings):
    history, future = protocol.split(ratings, "validation")
    assert protocol.warm_cases(history, future, protocol.candidates(history)) == []


# --- базовые модели ---------------------------------------------------------------------------------------------

@pytest.fixture
def history():
    rows = [(u, 1, 5.0, START - DAY) for u in range(30)]
    rows += [(u, 2, 2.0, START - 400 * DAY) for u in range(40)]
    rows += [(u, 3, 4.0, START - DAY) for u in range(25)]
    return frame(rows)


def inputs(*movies):
    return pd.DataFrame({"movie_id": list(movies), "rating": [4.0] * len(movies)})


def test_popularity_variants(history):
    pool = np.array([1, 2, 3])
    assert baselines.Popularity().fit(history, pool).recommend(inputs(), 3).tolist() == [2, 1, 3]
    assert baselines.RecentPopularity().fit(history, pool).recommend(inputs(), 3).tolist() == [1, 3, 2]
    assert baselines.LikedPopularity().fit(history, pool).recommend(inputs(), 3).tolist() == [1, 3, 2]
    assert baselines.BestRated().fit(history, pool).recommend(inputs(), 3).tolist() == [1, 3, 2]


def test_recommend_excludes_seen_and_random_is_reproducible(history):
    pool = np.array([1, 2, 3])
    assert baselines.Popularity().fit(history, pool).recommend(inputs(2, 9), 2).tolist() == [1, 3]
    a = baselines.RandomModel(seed=1).fit(history, pool).recommend(inputs(), 3)
    b = baselines.RandomModel(seed=1).fit(history, pool).recommend(inputs(), 3)
    assert a.tolist() == b.tolist() and sorted(a) == [1, 2, 3]


def test_biases_fold_in_user(history):
    model = baselines.Biases().fit(history)
    mu = history["rating"].mean()
    strict = pd.DataFrame({"movie_id": [1, 1, 1], "rating": [3.0, 3.0, 3.0]})
    assert model.predict(strict, np.array([1]))[0] < mu + model.item_bias[1]  # строгий человек – ниже
    assert baselines.GlobalMean().fit(history).predict(strict, np.array([1, 2])).tolist() == [mu, mu]
    assert model.predict(inputs(), np.array([99]))[0] == pytest.approx(mu)  # незнакомый фильм – общее среднее
