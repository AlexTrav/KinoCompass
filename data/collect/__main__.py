import argparse
import sys

import pandas as pd

from .config import CATALOG_DIR, POSTERS_COLUMNS, TITLES_COLUMNS
from .store import load

CATALOG_PATH = CATALOG_DIR / "movies.csv"
TITLES_PATH = CATALOG_DIR / "titles.csv"
POSTERS_PATH = CATALOG_DIR / "posters.csv"
README_COPY = CATALOG_DIR / "ml-32m-README.txt"  # условия лицензии MovieLens едут вместе с каталогом


def read_catalog() -> pd.DataFrame:
    if not CATALOG_PATH.exists():
        sys.exit("нет catalog/movies.csv – сначала make catalog")
    return pd.read_csv(CATALOG_PATH, dtype={"year": "Int64", "tmdb_id": "Int64"}, keep_default_na=True)


# проверка набора (сверка с README, шкала, даты, дубли) и каталога с названиями и постерами
def check(frames: dict[str, pd.DataFrame]) -> list[str]:
    from .check import check_catalog, check_ratings, check_tables, summary

    ratings = frames["ratings"]
    rows = {name: len(frames[name]) for name in ("tags", "movies")}
    problems = check_ratings(ratings, frames["movies"]["movie_id"]) + check_tables(rows)
    catalog = titles = posters = None
    if CATALOG_PATH.exists():
        catalog = read_catalog()
        titles = load(TITLES_PATH, TITLES_COLUMNS) if TITLES_PATH.exists() else None
        posters = load(POSTERS_PATH, POSTERS_COLUMNS) if POSTERS_PATH.exists() else None
        problems += check_catalog(catalog, titles, posters)
    for key, value in summary(ratings, catalog, titles, posters).items():
        print(f"  {key}: {value}")
    return problems


# каталог из набора в памяти и сразу проверка – архив скачивается один раз
def make_catalog() -> list[str]:
    from .catalog import build_catalog
    from .movielens import fetch

    frames, texts = fetch(names_text=("README.txt",))
    catalog = build_catalog(frames["ratings"], frames["movies"], frames["links"], frames["tags"])
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    catalog.to_csv(CATALOG_PATH, index=False, lineterminator="\n")
    README_COPY.write_text(texts["README.txt"], encoding="utf-8", newline="\n")
    print(f"  фильмов в каталоге: {len(catalog)}")
    return check(frames)


def main() -> None:
    parser = argparse.ArgumentParser(description="Данные MovieLens 32M и каталог фильмов KinoCompass")
    parser.add_argument(
        "command",
        choices=["catalog", "titles", "posters", "check"],
        help="catalog – скачать набор в память, собрать каталог фильмов и проверить; titles – названия ru/kk/en "
             "из Wikidata; posters – постеры TMDb (нужен TMDB_TOKEN); check – скачать набор в память и проверить всё",
    )
    parser.add_argument("--refresh", action="store_true", help="titles и posters: запросить все фильмы заново")
    args = parser.parse_args()

    problems: list[str] = []
    if args.command == "catalog":
        problems = make_catalog()
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
        from .movielens import fetch

        problems = check(fetch()[0])

    if problems:
        print("\nпроблемы:\n" + "\n".join(f"- {p}" for p in problems))
        sys.exit(1)
    print("\nготово")


if __name__ == "__main__":
    main()
