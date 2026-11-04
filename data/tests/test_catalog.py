import pandas as pd
import pytest

from collect.catalog import build_catalog, norm_tag, parse_genres, parse_title, top_tags
from collect.config import CATALOG_COLUMNS, MIN_RATINGS


@pytest.mark.parametrize("raw, expected", [
    ("Toy Story (1995)", ("Toy Story", 1995)),
    ("Matrix, The (1999)", ("The Matrix", 1999)),
    ("City of Lost Children, The (Cité des enfants perdus, La) (1995)", ("The City of Lost Children", 1995)),
    ("Seven (a.k.a. Se7en) (1995)", ("Seven", 1995)),
    ("(500) Days of Summer (2009)", ("(500) Days of Summer", 2009)),
    ("Auberge espagnole, L' (2002)", ("L'Auberge espagnole", 2002)),
    ("Lord of the Rings: The Two Towers, The (2002)", ("The Lord of the Rings: The Two Towers", 2002)),
    ("Babylon 5", ("Babylon 5", None)),
    ("Big (Bigger (Biggest)) (2001)", ("Big", 2001)),
    ("  Heat (1995) ", ("Heat", 1995)),
])
def test_parse_title(raw, expected):
    assert parse_title(raw) == expected


def test_parse_genres():
    assert parse_genres("Action|Sci-Fi") == "Action|Sci-Fi"
    assert parse_genres("(no genres listed)") == ""


def test_norm_tag():
    assert norm_tag("  Dark   Comedy ") == "dark comedy"
    assert norm_tag("a|b") == "a/b"


def test_top_tags_counts_people_and_drops_single(tags):
    top = top_tags(tags)
    # cyberpunk и philosophy – по 2 человека (регистр и пробелы не важны), «my dvd» и «twist ending» – по одному
    assert top.to_dict() == {1: "cyberpunk|philosophy"}


def test_build_catalog(ratings, movies, links, tags):
    catalog = build_catalog(ratings, movies, links, tags)
    assert list(catalog.columns) == CATALOG_COLUMNS
    assert catalog["movie_id"].tolist() == [1]  # у фильма 2 на одну оценку меньше порога
    row = catalog.iloc[0]
    assert row["title"] == "The Matrix" and row["year"] == 1999
    assert row["genres"] == "Action|Sci-Fi" and row["tags"] == "cyberpunk|philosophy"
    assert row["n_ratings"] == MIN_RATINGS
    assert row["mean_rating"] == pytest.approx((5 + 4 * (MIN_RATINGS - 1)) / MIN_RATINGS)
    assert row["first_rated"] == "1999-12-31"
    assert row["imdb_id"] == "tt0133093" and row["tmdb_id"] == 603


def test_build_catalog_drops_untitled(ratings, movies, links, tags):
    movies = movies.assign(title=movies["title"].where(movies["movie_id"] != 1, " (2019)"))
    assert build_catalog(ratings, movies, links, tags).empty


def test_build_catalog_without_tags_and_tmdb(ratings, movies, links, tags):
    ratings = pd.concat([ratings, ratings.assign(movie_id=3)], ignore_index=True)
    catalog = build_catalog(ratings, movies, links, tags).set_index("movie_id")
    assert catalog.loc[3, "tags"] == "" and catalog.loc[3, "genres"] == ""
    assert pd.isna(catalog.loc[3, "tmdb_id"]) and pd.isna(catalog.loc[3, "year"])
    assert catalog.loc[3, "imdb_id"] == "tt12345678"
