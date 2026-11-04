import re

import pandas as pd

from .config import ARTICLES, CATALOG_COLUMNS, MIN_RATINGS, MIN_TAG_USERS, NO_GENRES, TOP_TAGS

YEAR_RE = re.compile(r"\s*\((\d{4})\)\s*$")


# название без второго названия в скобках в конце: «Seven (a.k.a. Se7en)» -> «Seven»; скобки ищутся по
# парности, чтобы вложенные «(…(…))» не резали название посередине, а «(500) Days of Summer» не трогается
def strip_alt(title: str) -> str:
    if not title.endswith(")"):
        return title
    depth = 0
    for i in range(len(title) - 1, -1, -1):
        depth += {")": 1, "(": -1}.get(title[i], 0)
        if depth == 0:
            head = title[:i].rstrip()
            return head if i > 0 and title[i - 1] == " " and head else title
    return title


# артикль из конца названия – в начало: «Lord of the Rings: The Two Towers, The» -> «The Lord of …»
def move_article(title: str) -> str:
    for article in ARTICLES:
        suffix = f", {article}"
        if title.endswith(suffix):
            head = title[: -len(suffix)]
            return article + head if article.endswith("'") else f"{article} {head}"
    return title


# «City of Lost Children, The (Cité des enfants perdus, La) (1995)» -> («The City of Lost Children», 1995)
def parse_title(raw: str) -> tuple[str, int | None]:
    title, year = raw.strip(), None
    if match := YEAR_RE.search(title):
        year = int(match.group(1))
        title = title[: match.start()].rstrip()
    return move_article(strip_alt(title)), year


def parse_genres(raw: str) -> str:
    return "" if raw == NO_GENRES else raw


# тег в едином виде: нижний регистр, одиночные пробелы; «|» – разделитель списка в каталоге, внутри тега – «/»
def norm_tag(tag: str) -> str:
    return " ".join(tag.lower().split()).replace("|", "/")


# самые частые теги фильма через «|»: частота – число разных людей, поставивших тег
def top_tags(tags: pd.DataFrame) -> pd.Series:
    frame = tags.assign(tag=tags["tag"].fillna("").map(norm_tag))
    frame = frame[frame["tag"] != ""]
    counts = frame.groupby(["movie_id", "tag"])["user_id"].nunique().rename("users").reset_index()
    counts = counts[counts["users"] >= MIN_TAG_USERS]
    counts = counts.sort_values(["movie_id", "users", "tag"], ascending=[True, False, True])
    return counts.groupby("movie_id").head(TOP_TAGS).groupby("movie_id")["tag"].agg("|".join)


# каталог: фильмы минимум с MIN_RATINGS оценками – название, год, жанры, теги, статистика оценок
# (число, средняя, первая и последняя дата) и ссылки на IMDb и TMDb
def build_catalog(ratings: pd.DataFrame, movies: pd.DataFrame, links: pd.DataFrame,
                  tags: pd.DataFrame) -> pd.DataFrame:
    stats = ratings.groupby("movie_id").agg(
        n_ratings=("rating", "size"),
        mean_rating=("rating", "mean"),
        first_rated=("time", "min"),
        last_rated=("time", "max"),
    )
    stats = stats[stats["n_ratings"] >= MIN_RATINGS]
    catalog = stats.join(movies.set_index("movie_id"), how="left").join(links.set_index("movie_id"), how="left")

    parsed = [parse_title(title) for title in catalog["title"]]
    catalog["title"] = [title for title, _ in parsed]
    catalog["year"] = pd.array([year for _, year in parsed], dtype="Int64")
    # в MovieLens есть фильм без названия – « (2019)»: показать его на сайте нечем, в каталог он не идёт
    catalog = catalog[catalog["title"] != ""].copy()
    catalog["genres"] = catalog["genres"].map(parse_genres)
    catalog["tags"] = top_tags(tags).reindex(catalog.index).fillna("")
    catalog["mean_rating"] = catalog["mean_rating"].astype("float64").round(3)
    for column in ("first_rated", "last_rated"):
        catalog[column] = catalog[column].dt.strftime("%Y-%m-%d")
    catalog["imdb_id"] = "tt" + catalog["imdb_id"]
    catalog["tmdb_id"] = catalog["tmdb_id"].astype("Int64")
    return catalog.reset_index()[CATALOG_COLUMNS].sort_values("movie_id", ignore_index=True)
