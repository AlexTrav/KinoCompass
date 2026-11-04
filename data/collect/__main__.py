import argparse
import shutil
import sys

import pandas as pd
import pyarrow.parquet as pq

from .config import CATALOG_DIR, CSV_DIR, POSTERS_COLUMNS, TITLES_COLUMNS, WORK_DIR
from .store import load

CATALOG_PATH = CATALOG_DIR / "movies.csv"
TITLES_PATH = CATALOG_DIR / "titles.csv"
POSTERS_PATH = CATALOG_DIR / "posters.csv"
README_COPY = CATALOG_DIR / "ml-32m-README.txt"  # условия лицензии MovieLens едут вместе с каталогом


def read_work(name: str, columns: list[str] | None = None) -> pd.DataFrame:
    path = WORK_DIR / f"{name}.parquet"
    if not path.exists():
        sys.exit(f"нет {path.relative_to(WORK_DIR.parent)} – сначала make download parquet")
    return pd.read_parquet(path, columns=columns)


def read_catalog() -> pd.DataFrame:
    if not CATALOG_PATH.exists():
        sys.exit("нет catalog/movies.csv – сначала make catalog")
    return pd.read_csv(CATALOG_PATH, dtype={"year": "Int64", "tmdb_id": "Int64"}, keep_default_na=True)


def make_catalog() -> None:
    from .catalog import build_catalog

    catalog = build_catalog(
        read_work("ratings", ["movie_id", "rating", "time"]),
        read_work("movies"),
        read_work("links"),
        read_work("tags", ["user_id", "movie_id", "tag"]),
    )
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    catalog.to_csv(CATALOG_PATH, index=False, lineterminator="\n")
    shutil.copyfile(CSV_DIR / "README.txt", README_COPY)
    print(f"  фильмов в каталоге: {len(catalog)}")


# проверка всего, что есть: parquet (сверка с README набора) и каталог с названиями и постерами
def check() -> list[str]:
    from .check import check_catalog, check_ratings, check_tables, summary

    ratings = read_work("ratings")
    rows = {name: pq.ParquetFile(WORK_DIR / f"{name}.parquet").metadata.num_rows for name in ("tags", "movies")}
    problems = check_ratings(ratings, read_work("movies", ["movie_id"])["movie_id"]) + check_tables(rows)
    catalog = titles = posters = None
    if CATALOG_PATH.exists():
        catalog = read_catalog()
        titles = load(TITLES_PATH, TITLES_COLUMNS) if TITLES_PATH.exists() else None
        posters = load(POSTERS_PATH, POSTERS_COLUMNS) if POSTERS_PATH.exists() else None
        problems += check_catalog(catalog, titles, posters)
    for key, value in summary(ratings, catalog, titles, posters).items():
        print(f"  {key}: {value}")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description="Данные MovieLens 32M и каталог фильмов KinoCompass")
    parser.add_argument(
        "command",
        choices=["download", "parquet", "catalog", "titles", "posters", "check"],
        help="download – скачать и распаковать архив (проверка md5), parquet – CSV в parquet, catalog – каталог "
             "фильмов, titles – названия ru/kk/en из Wikidata, posters – постеры TMDb (нужен TMDB_TOKEN), "
             "check – проверить всё",
    )
    parser.add_argument("--refresh", action="store_true", help="titles и posters: запросить все фильмы заново")
    args = parser.parse_args()

    problems: list[str] = []
    if args.command == "download":
        from .download import download

        print(download())
    elif args.command == "parquet":
        from .parquet import convert

        convert()
    elif args.command == "catalog":
        make_catalog()
    elif args.command == "titles":
        from .wikidata import update_titles

        titles = update_titles(read_catalog(), TITLES_PATH, refresh=args.refresh)
        print(f"  записано названий: {len(titles)}")
    elif args.command == "posters":
        from .tmdb import update_posters

        posters, errors = update_posters(read_catalog(), POSTERS_PATH, refresh=args.refresh)
        print(f"  записано постеров: {len(posters)}")
        if errors:
            problems.append(f"постеры: {errors} фильмов не получены из-за ошибок – повтори make posters")
    else:
        problems = check()

    if problems:
        print("\nпроблемы:\n" + "\n".join(f"- {p}" for p in problems))
        sys.exit(1)
    print("\nготово")


if __name__ == "__main__":
    main()
