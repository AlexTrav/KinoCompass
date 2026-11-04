import numpy as np
import pandas as pd
import pytest

import eda

DAY = eda.DAY
T0 = int(pd.Timestamp("2021-01-15", tz="UTC").timestamp())


def test_seconds_and_calendar():
    times = pd.Series(pd.to_datetime(["1995-01-09 10:00", "2023-10-12 23:59"]).tz_localize("UTC"))
    secs = eda.seconds(times)
    assert secs.dtype == np.int64 and secs[0] == int(pd.Timestamp("1995-01-09 10:00", tz="UTC").timestamp())
    assert eda.month_label(eda.month_index(secs)[0]) == "1995-01"
    assert eda.year_of(secs).tolist() == [1995, 2023]
    assert eda.day_label(secs[1]) == "2023-10-12"


def test_gini_and_top_share():
    assert eda.gini(np.array([5, 5, 5, 5])) == pytest.approx(0)
    assert eda.gini(np.array([0, 0, 0, 10])) == pytest.approx(0.75)
    assert eda.top_share(np.array([1, 1, 1, 7]), 0.25) == pytest.approx(0.7)


def test_lorenz_ends_and_is_concave():
    curve = eda.lorenz(np.array([10, 5, 3, 1, 1]), points=11)
    assert curve["ratings"].iloc[0] == 0 and curve["ratings"].iloc[-1] == pytest.approx(1)
    assert curve["ratings"].iloc[2] == pytest.approx(0.5)  # 20 % самых популярных фильмов – половина оценок
    assert (np.diff(curve["ratings"], 2) <= 1e-9).all()


def test_first_seen():
    first = eda.first_seen(np.array([2, 0, 2]), np.array([30, 10, 20]), 4)
    assert first[0] == 10 and first[2] == 20 and first[1] == np.iinfo(np.int64).max


def test_monthly():
    users = np.array([1, 1, 2, 2])
    secs = np.array([T0, T0 + DAY, T0 + 31 * DAY, T0 + 32 * DAY])
    rating = np.array([4.0, 3.5, 5.0, 2.5], dtype=np.float32)
    frame = eda.monthly(users, secs, rating, eda.first_seen(users, secs, 3))
    assert frame["month"].tolist() == ["2021-01", "2021-02"]
    assert frame["ratings"].tolist() == [2, 2] and frame["active_users"].tolist() == [1, 1]
    assert frame["new_users"].tolist() == [1, 1] and frame["half_share"].tolist() == [0.5, 0.5]


def test_first_day():
    users = np.array([0, 0, 0, 1, 1])
    secs = np.array([T0, T0 + 3600, T0 + 2 * DAY, T0, T0 + 100])
    info, bins = eda.first_day(users, secs, eda.first_seen(users, secs, 2))
    assert info["share_ratings_first_day"] == 0.8
    assert info["share_users_only_first_day"] == 0.5  # у второго все оценки в первые сутки
    assert bins["count"].sum() == 2


@pytest.fixture
def movies_frame():
    return pd.DataFrame({"movie_id": [1, 2, 3], "title": ["Heat (1995)", "Alien (1979)", "Untitled"],
                         "genres": ["Action|Crime|IMAX", "Horror|Sci-Fi", "(no genres listed)"]})


def test_movie_meta_and_tables(movies_frame):
    years, masks = eda.movie_meta(movies_frame, 4)
    assert years[1:].tolist() == [1995, 1979, 0]
    bit = {g: 1 << i for i, g in enumerate(eda.GENRE_LIST)}
    assert masks[1] == bit["Action"] | bit["Crime"] and masks[3] == 0  # IMAX – не жанр
    movies = np.repeat([1, 2], [30, 20])
    rating = np.r_[np.full(30, 4.0), np.full(20, 3.0)].astype(np.float32)
    table = eda.movie_table(movies, rating)
    assert table["n"].tolist() == [30, 20] and table["positive"].tolist() == [1.0, 0.0]
    genres = eda.genre_table(table, masks).set_index("genre")
    assert genres.loc["Action", "ratings"] == 30 and genres.loc["Horror", "mean_rating"] == 3.0
    assert genres.loc["Action", "ratings_share"] == 0.6
    by_year = eda.year_table(table, years)
    assert by_year.loc[1979, "mean_rating"] == 3.0 and by_year.loc[1995, "movies"] == 1


def test_genre_taste_finds_shared_liking():
    # жанры: Comedy и Romance любят одни и те же люди, Horror – другие
    genres = pd.DataFrame({"movie_id": [1, 2, 3], "title": ["A (2000)", "B (2000)", "C (2000)"],
                           "genres": ["Comedy", "Romance", "Horror"]})
    _, masks = eda.movie_meta(genres, 4)
    rng = np.random.default_rng(0)
    users, movies, rating = [], [], []
    for user in range(1500):
        like = rng.normal()
        for movie, sign in ((1, 1), (2, 1), (3, -1)):
            for _ in range(eda.MIN_GENRE_RATINGS):
                users.append(user), movies.append(movie)
                rating.append(3 + sign * like + rng.normal(scale=0.3))
    corr, n = eda.genre_taste(np.array(users), np.array(movies), np.array(rating, dtype=np.float32), masks)
    assert n == 1500
    assert corr.loc["Comedy", "Romance"] > 0.5 and corr.loc["Comedy", "Horror"] < -0.5
    pairs = eda.strongest_pairs(corr, k=1)
    assert {pairs["positive"][0]["a"], pairs["positive"][0]["b"]} == {"Comedy", "Romance"}


def test_windows_split_warm_and_cold():
    end = int(pd.Timestamp("2023-10-13", tz="UTC").timestamp())
    year = 365 * DAY
    users = np.array([0, 0, 1, 2])
    movies = np.array([1, 2, 1, 3])
    # последняя оценка – 12.10.2023, поэтому окна кончаются 13.10.2023
    secs = np.array([end - 2 * year, end - 10 * DAY, end - 5 * DAY, end - 1])
    rating = np.array([4.0, 4.5, 3.0, 5.0], dtype=np.float32)
    frame = eda.windows(users, movies, secs, rating, eda.first_seen(users, secs, 3),
                        eda.first_seen(movies, secs, 4), count=2)
    last = frame.iloc[-1]
    assert last["end"] == "2023-10-13" and last["ratings"] == 3
    assert last["warm_users"] == 1 and last["cold_users"] == 2 and last["warm_users_with_positive"] == 1
    assert last["new_movies"] == 2  # фильмы 2 и 3 впервые оценены в последнем окне


def test_tag_table():
    tags = pd.DataFrame({"user_id": [1, 2, 2, 3], "movie_id": [10, 10, 10, 20],
                         "tag": ["Funny", "funny ", "dark", None]})
    info, top = eda.tag_table(tags, pd.Series([10, 20, 30]))
    assert top.iloc[0].tolist() == ["funny", 2]  # регистр и пробелы не важны, считаются разные люди
    assert info["share_movies_any_tag"] == 0.3333  # у фильма 20 пустой тег – не в счёт
    assert info["share_movies_shared_tag"] == 0.3333
