import pandas as pd

from collect.catalog import build_catalog
from collect.check import check_catalog, check_ratings, check_tables, summary
from collect.config import EXPECTED
from conftest import utc


def test_clean_ratings_pass(ratings, movies):
    assert check_ratings(ratings, movies["movie_id"], expected=None) == []


def test_counts_compared_with_readme(ratings, movies):
    problems = check_ratings(ratings, movies["movie_id"])
    assert any(p.startswith("ratings:") for p in problems) and any(p.startswith("users:") for p in problems)
    assert check_tables({"tags": EXPECTED["tags"], "movies": EXPECTED["movies"]}) == []
    assert check_tables({"tags": 1, "movies": EXPECTED["movies"]}) == [f"tags: 1 вместо {EXPECTED['tags']} по README набора"]


def test_bad_ratings_found(ratings, movies):
    bad = ratings.copy()
    bad.loc[0, "rating"] = 4.3
    bad.loc[1, "time"] = utc("2024-01-01")
    bad = pd.concat([bad, bad.iloc[[2]], bad.iloc[[3]].assign(movie_id=99)], ignore_index=True)
    problems = check_ratings(bad, movies["movie_id"], expected=None)
    assert len(problems) == 4
    assert any("шкалы" in p for p in problems) and any("периода" in p for p in problems)
    assert any("повторные" in p for p in problems) and any("нет в movies" in p for p in problems)


def test_catalog_checks(ratings, movies, links, tags):
    catalog = build_catalog(ratings, movies, links, tags)
    titles = pd.DataFrame({"movie_id": [1], "title_ru": ["Матрица"], "title_kk": [""], "title_en": ["The Matrix"]})
    posters = pd.DataFrame({"movie_id": [1], "poster_path": ["/m.jpg"]})
    assert check_catalog(catalog, titles, posters) == []

    broken = pd.concat([catalog, catalog], ignore_index=True)
    broken.loc[1, "genres"] = "Cartoon"
    broken.loc[1, "imdb_id"] = "133093"
    problems = check_catalog(broken, pd.concat([titles, titles.assign(movie_id=7)]))
    assert any("повторяются" in p for p in problems) and any("Cartoon" in p for p in problems)
    assert any("IMDb" in p for p in problems) and any("titles: фильмы" in p for p in problems)


def test_catalog_check_finds_em_dash(ratings, movies, links, tags):
    catalog = build_catalog(ratings, movies, links, tags)
    titles = pd.DataFrame({"movie_id": [1], "title_ru": [f"Я {chr(0x2014)} легенда"], "title_kk": [""],
                           "title_en": [""]})
    assert any("длинное тире" in p for p in check_catalog(catalog, titles))


def test_summary(ratings, movies, links, tags):
    catalog = build_catalog(ratings, movies, links, tags)
    posters = pd.DataFrame({"movie_id": [1], "poster_path": [""]})
    info = summary(ratings, catalog, posters=posters)
    assert info["оценок"] == len(ratings) and info["фильмов в каталоге"] == 1
    assert info["с постером"] == "0 (0%)"
    assert info["период"] == "1999-12-31 – 2010-06-01"
