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


# --- соседи -----------------------------------------------------------------------------------------------------

import knn  # noqa: E402


@pytest.fixture
def taste():
    """Две компании: люди 0–9 смотрят фильмы 1–3, люди 10–19 – фильмы 4–6; фильм 7 смотрят все."""
    rows = [(u, m, 5.0, START - DAY) for u in range(10) for m in (1, 2, 3, 7)]
    rows += [(u, m, 5.0, START - DAY) for u in range(10, 20) for m in (4, 5, 6, 7)]
    return frame(rows)


def test_interactions_matrix(taste):
    knn._cache.clear()
    pool = np.arange(1, 8)
    matrix, users = knn.interactions(taste, pool)
    assert matrix.shape == (20, 7) and matrix.sum() == 80 and users.tolist() == list(range(20))
    assert knn.interactions(taste, pool)[0] is matrix  # одна матрица на всю сетку прогона


def test_item_knn_recommends_same_company_and_explains(taste):
    knn._cache.clear()
    model = knn.ItemKNN("cosine", k=10).fit(taste, np.arange(1, 8))
    rec = model.recommend(inputs(1), 3)
    assert set(rec[:2]) == {2, 3} and 7 in rec  # сначала фильмы своей компании
    assert model.because(inputs(1, 4), 2) == [1]  # фильм 2 советуется из-за фильма 1, а не 4


def test_centered_weights_push_disliked_down():
    position = pd.Series(np.arange(3), index=[10, 20, 30])
    rated = pd.DataFrame({"movie_id": [10, 20, 99], "rating": [5.0, 1.0, 3.0]})
    index, weights = knn.input_weights(rated, position, "centered")
    assert index.tolist() == [0, 1] and weights[0] > 0 > weights[1]  # 99 не кандидат – пропущен


def test_user_knn_uses_neighbours_but_not_self(taste):
    knn._cache.clear()
    pool = np.arange(1, 8)
    model = knn.UserKNN(k=5).fit(taste, pool)
    assert set(model.recommend(inputs(4, 7), 2)) == {5, 6}  # соседи – вторая компания
    alone = knn.UserKNN(k=1).fit(taste, pool)
    # постоянный человек 0 – ближайший сам себе; без самого себя сосед из той же компании всё равно есть
    assert alone.scores(inputs(1, 2, 3, 7), user=0)[np.searchsorted(pool, 1)] > 0


# --- факторизация -----------------------------------------------------------------------------------------------

import factorization  # noqa: E402


def test_svd_transfers_taste_to_new_person():
    """Люди 0–29 любят фильмы 1–2 (5 звёзд) и не любят 3–4 (1 звезда), люди 30–59 – наоборот. По одной
    оценке вкус от строгости не отличить, поэтому новичок ставит две: любимому фильму и нелюбимому."""
    rows = [(u, m, 5.0 if (u < 30) == (m <= 2) else 1.0, START - DAY) for u in range(60) for m in (1, 2, 3, 4)]
    history = frame(rows)
    model = factorization.SVD(factors=2, reg=0.01, iterations=10).fit(history, np.array([1, 2, 3, 4]))
    first_company = pd.DataFrame({"movie_id": [1, 3], "rating": [5.0, 1.0]})
    predicted = model.predict(first_company, np.array([2, 4, 99]))
    assert predicted[0] > 4 and predicted[1] < 2  # вкус переносится с фильма 1 на 2, а 4 – чужой фильм
    assert predicted[2] == pytest.approx(np.clip(model.mu + model.user_vector(first_company)[1], 0.5, 5))
    assert model.recommend(first_company, 1).tolist() == [2]


def test_als_and_bpr_fold_in_new_person(taste):
    knn._cache.clear()
    pool = np.arange(1, 8)
    als = factorization.ALS(factors=4, regularization=0.01, iterations=10).fit(taste, pool)
    assert set(als.recommend(inputs(4, 7), 2)) == {5, 6}
    bpr = factorization.BPR(factors=4, learning_rate=0.05, iterations=200).fit(taste, pool)
    scores = bpr.scores(inputs(4, 7))
    assert scores.shape == (7,) and np.isfinite(scores).all()
    assert len(bpr.recommend(inputs(), 3)) == 3  # пустой вход – советы по смещениям фильмов


# --- прогон -----------------------------------------------------------------------------------------------------


def test_run_fits_models_one_by_one(monkeypatch, taste):
    """Прогон обучает модель, проверяет её во всех сценариях и освобождает память перед следующей."""
    import evaluate

    order = []

    class Spy(baselines.Popularity):
        def __init__(self, name):
            self.name = name

        def fit(self, history, pool):
            order.append(("fit", self.name))
            return super().fit(history, pool)

        def release(self):
            order.append(("release", self.name))

    future = frame([(500, 1, 5.0, START + DAY), (500, 2, 4.0, START + 2 * DAY), (500, 3, 4.0, START + 3 * DAY),
                    (500, 4, 4.0, START + 4 * DAY), (500, 5, 4.0, START + 5 * DAY), (500, 6, 4.0, START + 6 * DAY),
                    (500, 7, 4.0, START + 7 * DAY), (500, 1, 4.0, START + 8 * DAY), (500, 2, 4.0, START + 9 * DAY),
                    (500, 3, 5.0, START + 10 * DAY), (500, 4, 5.0, START + 11 * DAY), (0, 5, 5.0, START + DAY)])
    history = pd.concat([taste, frame([(u, m, 4.0, START - DAY) for u in range(20, 40) for m in range(1, 8)])])
    movies = pd.DataFrame({"movie_id": np.arange(1, 8), "title": ["x (2000)"] * 7, "genres": ["Drama"] * 7})
    no_tags = pd.DataFrame(columns=["user_id", "movie_id", "tag"])
    monkeypatch.setattr(evaluate, "load", lambda period: (history, future, movies, no_tags))
    monkeypatch.setattr(evaluate, "REPORTS", __import__("pathlib").Path("/tmp/reports"))
    report = evaluate.run("spy", [Spy("a"), Spy("b")], [])
    assert order == [("fit", "a"), ("release", "a"), ("fit", "b"), ("release", "b")]
    assert set(report["score"]) == {"a", "b"} and report["scenarios"]["cold5"]["people"] == 1
    assert "cold10" not in report["scenarios"]  # после 10 оценок угадывать нечего – сценарий пропущен


# --- EASE -------------------------------------------------------------------------------------------------------

import ease  # noqa: E402


def test_ease_closed_form(taste):
    knn._cache.clear()
    ease._gram.clear()
    pool = np.arange(1, 8)
    model = ease.EASE(lam=1.0).fit(taste, pool)
    assert model.b.shape == (7, 7) and np.allclose(np.diag(model.b), 0)
    assert set(model.recommend(inputs(4, 7), 2)) == {5, 6}  # своя компания
    # формула: B = I − P·diag(1/diag P), P = (XᵀX + λI)⁻¹
    x = knn.interactions(taste, pool)[0].toarray().astype(np.float64)
    p = np.linalg.inv(x.T @ x + np.eye(7))
    expected = np.eye(7) - p / np.diag(p)
    np.fill_diagonal(expected, 0)
    assert np.allclose(model.b, expected, atol=1e-5)
    model.release()
    assert not hasattr(model, "b")


# --- контентная модель ------------------------------------------------------------------------------------------

import content  # noqa: E402


def test_load_keeps_only_tags_before_boundary(monkeypatch):
    """Теги из проверочного года подсказывали бы контентной модели будущее – в историю они не попадают."""
    import collect.movielens

    utc = lambda seconds: pd.to_datetime(seconds, unit="s", utc=True)  # noqa: E731
    frames = {
        "ratings": pd.DataFrame({"user_id": [1, 1], "movie_id": [1, 2], "rating": [4.0, 5.0],
                                 "time": utc([START - DAY, START + DAY])}),
        "tags": pd.DataFrame({"user_id": [1, 2], "movie_id": [1, 1], "tag": ["old", "future"],
                              "time": utc([START - DAY, START + DAY])}),
        "movies": pd.DataFrame({"movie_id": [1, 2], "title": ["a", "b"], "genres": ["Drama", "Drama"]}),
    }
    monkeypatch.setattr(collect.movielens, "fetch", lambda: (frames, {}))
    history, future, movies, tags = protocol.load("validation")
    assert len(history) == 1 and len(future) == 1 and tags["tag"].tolist() == ["old"]


def test_new_items_are_catalog_films_with_few_ratings():
    history = frame([(u, 1, 4.0, START - DAY) for u in range(25)] + [(0, 2, 4.0, START - DAY)])
    years = pd.Series([1999, 2005, None, 2023], index=[1, 2, 3, 4], dtype="Int64")
    # фильм 1 – 25 оценок (кандидат), 2 – одна, 3 – ни одной и без года, 4 – вышел после проверочного года
    assert protocol.new_items(history, years, "validation").tolist() == [2, 3]
    assert protocol.new_items(history, years, "test").tolist() == [2, 3, 4]


@pytest.fixture
def side():
    """Две «компании» фильмов: 1–3 – фантастика про космос, 4–6 – мелодрамы; 7 – без описания."""
    rows = [(m, "Sci-Fi", 1999, "space|robots", "Astronauts fly to a distant planet") for m in (1, 2, 3)]
    rows += [(m, "Romance|Drama", 2005, "love", "Two lovers meet in Paris") for m in (4, 5, 6)]
    rows += [(7, "", None, "", "")]
    out = pd.DataFrame(rows, columns=["movie_id", "genres", "year", "tags", "overview_en"]).set_index("movie_id")
    out["year"] = out["year"].astype("Int64")
    for column in ("title", "title_en"):
        out[column] = [f"Film {m}" for m in out.index]
    out["title_ru"], out["overview_ru"] = "", ""
    return out


def test_tfidf_content_follows_profile(side, taste):
    pool = np.arange(1, 8)
    for words in (False, True):
        model = content.TfidfContent(words=words)
        model.attach(side)
        model.fit(taste, pool)
        assert set(model.recommend(inputs(1), 2)) == {2, 3}  # похожие по описанию, а не по оценкам
        assert set(model.recommend(inputs(4, 99), 2)) == {5, 6}  # фильм вне каталога пропускается
    # кандидат вне каталога (без описания) не ломает модель – балл 0
    model.fit(taste, np.arange(1, 9))
    assert model.scores(inputs(1))[7] == 0


def test_content_centered_weights_push_disliked_down(side, taste):
    model = content.TfidfContent(weighting="centered")
    model.attach(side)
    model.fit(taste, np.arange(1, 8))
    liked_space = pd.DataFrame({"movie_id": [1, 4], "rating": [5.0, 1.0]})
    scores = model.scores(liked_space)
    assert scores[1] > 0 > scores[4]  # фантастика вверх, мелодрама вниз
    same = pd.DataFrame({"movie_id": [1, 2], "rating": [3.0, 3.0]})
    assert model.scores(same)[2] > 0  # одинаковые оценки – без «минусов», вес 1


def test_e5_content_averages_languages(side, taste):
    asked = []

    def fake_encoder(texts):
        asked.append(texts)
        return np.array([[1.0, 0.0] if "Sci-Fi" in t else [0.0, 1.0] for t in texts], dtype=np.float32)

    model = content.E5Content(("en", "ru"), encoder=fake_encoder)
    model.attach(side)
    model.fit(taste, np.arange(1, 8))
    assert len(asked) == 2 and asked[0][0].startswith("Film 1. Sci-Fi. space, robots. Astronauts")
    assert np.allclose(np.linalg.norm(model.matrix, axis=1), 1)
    assert set(model.recommend(inputs(1, 7), 2)) == {2, 3}  # фильм 7 смотрят все – он во входе, не в ответе
    model.fit(taste, np.arange(1, 8))
    assert len(asked) == 2  # векторы считаются один раз на описание


def test_newest_orders_by_year(side, taste):
    model = content.Newest()
    model.attach(side)
    model.fit(taste, np.arange(1, 8))
    assert model.recommend(inputs(), 7).tolist()[:3] == [4, 5, 6] and model.recommend(inputs(), 7)[-1] == 7


def test_search_counts_hits_and_genre_precision(side):
    import search

    assert search.genre_match(pd.Series(["Romance|Drama", "Romance|Comedy", "Comedy"]), "Romance&Comedy").tolist() \
        == [False, True, False]
    assert search.genre_match(pd.Series(["Sci-Fi", "Drama", ""]), "Sci-Fi|Drama").tolist() == [True, True, False]
    queries = pd.DataFrame({"lang": ["en", "en"], "kind": ["plot", "genre"],
                            "query": ["space", "love"], "expect": ["2", "Romance"]})
    # подставной поиск: фантастика 1–3 первыми, затем мелодрамы 4–6, затем 7
    order = np.array([3.0, 2.9, 2.8, 2.0, 1.9, 1.8, 0.0])
    report = search.run_search(side, {"fake": lambda texts: np.tile(order, (len(texts), 1))}, queries)
    first, second = report["variants"]["fake"]["queries"]
    assert first["rank"] == 2 and first["hit"] == 1.0 and first["top3"] == ["Film 1", "Film 2", "Film 3"]
    assert second["precision"] == pytest.approx(3 / 10)  # доля из 10 мест выдачи: фильмов всего 7, мелодрам 3
    assert report["chance"]["Romance"] == pytest.approx(3 / 7, abs=1e-4)  # в отчёте – 4 знака
    # запрос, о котором модель ничего не знает (все баллы равны), – пустая выдача, а не первые фильмы каталога
    blind = search.run_search(side, {"blind": lambda texts: np.zeros((len(texts), 7))}, queries)
    first, second = blind["variants"]["blind"]["queries"]
    assert first["rank"] is None and first["top3"] == [] and second["precision"] == 0


# --- Mult-VAE ---------------------------------------------------------------------------------------------------

def test_vae_learns_companies_and_releases(taste):
    import vae

    knn._cache.clear()
    model = vae.MultVAE(latent=2, beta=0.2, hidden=16, epochs=300, anneal_epochs=100).fit(taste, np.arange(1, 8))
    assert model.losses[-1] < model.losses[0]  # обучение идёт
    assert set(model.recommend(inputs(4, 7), 2)) == {5, 6}  # своя компания
    assert set(model.recommend(inputs(1, 7), 2)) == {2, 3}  # фильм 7 смотрят все – он во входе, не в ответе
    assert model.scores(inputs()).shape == (7,)  # пустой вход – тоже баллы
    model.release()
    assert not hasattr(model, "net")


# --- гибрид -----------------------------------------------------------------------------------------------------

def test_ranks_from_zero_to_one():
    import hybrid

    assert hybrid.ranks(np.array([10.0, -3.0, 5.0])).tolist() == [1.0, 0.0, 0.5]
    assert hybrid.ranks(np.array([1.0, 1.0, 1.0])).tolist() == [1.0, 0.5, 0.0]  # равные – выше тот, кто раньше


def test_hybrid_mixes_base_and_personal_and_fits_once(taste):
    import hybrid

    knn._cache.clear()
    pool = np.arange(1, 8)
    fits = []

    class CountingKNN(knn.ItemKNN):
        def fit(self, history, pool):
            fits.append(1)
            return super().fit(history, pool)

    # популярность за год: фильм 7 смотрят все; персонально человек из второй компании – фильмы 5, 6
    popular, personal = baselines.RecentPopularity(), CountingKNN("cosine", 10, "binary")
    models = [hybrid.Hybrid(popular, personal, w) for w in (0.0, 0.5, 1.0)]
    for model in models:
        model.fit(taste, pool)
    assert len(fits) == 1  # персональная модель обучена один раз на всю сетку весов
    only_personal, half, only_base = (m.recommend(inputs(4), 3) for m in models)
    assert set(only_personal[:2]) == {5, 6}
    assert only_base[0] == 7
    # w = 1 – порядок базы в точности: кто выше по популярности, тот выше и в гибриде
    base, mixed = popular.scores(inputs()), models[2].scores(inputs(4))
    assert all(mixed[i] > mixed[j] for i in range(7) for j in range(7) if base[i] > base[j])
    assert 7 in half[:3] and {5, 6} & set(half[:3])  # смесь берёт и популярное, и своё
    assert models[1].name == "hybrid_popular_year_item_knn_cosine_k10_binary_w0.5"


def test_vae_batches_equal_dense_rows():
    """Пачки на устройстве – те же строки, что toarray() на процессоре (в том числе пустые и повторы)."""
    import scipy.sparse as sp

    import vae

    matrix = sp.random(30, 12, density=0.3, random_state=1, format="csr")
    matrix.data[:] = 1
    matrix = matrix.tolil()
    matrix[4] = 0  # пустая строка
    matrix = matrix.tocsr()
    matrix.eliminate_zeros()
    rows = np.array([4, 0, 29, 7, 0])
    assert np.array_equal(vae.Batches(matrix, "cpu")(rows).numpy(), matrix[rows].toarray())


def test_recommend_breaks_ties_by_id():
    """Равные баллы на границе первых k – выше меньший id (раньше argpartition выбирал среди них произвольно)."""
    model = baselines.Static()
    model.fit(frame([]), np.arange(1, 41))
    model.static = np.r_[np.full(39, 1.0), 5.0]  # фильм 40 – лучший, остальные 39 – вровень
    assert model.recommend(inputs(), 4).tolist() == [40, 1, 2, 3]
    assert model.recommend(inputs(1, 2), 3).tolist() == [40, 3, 4]  # оценённые исключены
    assert model.recommend(inputs(), 50).tolist() == [40, *range(1, 40)]  # k больше числа кандидатов
