from pathlib import Path

# корень папки data: data/collect/config.py -> collect -> data
DATA_DIR = Path(__file__).resolve().parents[1]
CATALOG_DIR = DATA_DIR / "catalog"  # каталог фильмов для сайта и моделей – единственное, что хранится (в git)

# MovieLens 32M (GroupLens): 5-звёздочные оценки и теги с 09.01.1995 по 12.10.2023. Набор на диске не
# хранится: каждый запуск скачивает архив в память и читает CSV прямо из него (collect/movielens.py)
DATASET = "ml-32m"
ZIP_URL = f"https://files.grouplens.org/datasets/movielens/{DATASET}.zip"
MD5_URL = f"{ZIP_URL}.md5"

# эталонные размеры из README набора: проверка, что скачано и разобрано всё
EXPECTED = {"ratings": 32_000_204, "tags": 2_000_072, "movies": 87_585, "users": 200_948}
# границы периода по README (UTC); при проверке – с запасом в сутки на часовые пояса
FIRST_DAY = "1995-01-09"
LAST_DAY = "2023-10-12"
GENRES = {
    "Action", "Adventure", "Animation", "Children", "Comedy", "Crime", "Documentary", "Drama", "Fantasy",
    "Film-Noir", "Horror", "IMAX", "Musical", "Mystery", "Romance", "Sci-Fi", "Thriller", "War", "Western",
}
NO_GENRES = "(no genres listed)"

# каталог: фильмы минимум с MIN_RATINGS оценками за весь период – их можно оценить на сайте и получить
# в рекомендациях; у фильмов с единичными оценками нет ни надёжной статистики, ни соседей
MIN_RATINGS = 20
# теги фильма: не больше TOP_TAGS самых частых, и только те, что поставили хотя бы MIN_TAG_USERS разных
# людей, – одиночные теги чаще всего личные пометки («seen 2008», «my dvd»)
TOP_TAGS = 10
MIN_TAG_USERS = 2
# артикли, которые MovieLens переносит в конец названия: «Matrix, The» -> «The Matrix»
ARTICLES = ("The", "A", "An", "Les", "La", "Le", "L'", "Il", "El", "Los", "Las", "Die", "Der", "Das", "Det", "Den")

CATALOG_COLUMNS = [
    "movie_id", "title", "year", "genres", "tags", "n_ratings", "mean_rating",
    "first_rated", "last_rated", "imdb_id", "tmdb_id",
]
TITLES_COLUMNS = ["movie_id", "wikidata", "title_ru", "title_kk", "title_en"]
POSTERS_COLUMNS = ["movie_id", "tmdb_id", "poster_path"]

# Wikidata: названия на русском, казахском и английском по IMDb id (свойство P345), лицензия CC0
WIKIDATA_URL = "https://query.wikidata.org/sparql"
WIKIDATA_BATCH = 200  # IMDb id в одном запросе SPARQL
WIKIDATA_PAUSE_SEC = 1.0  # пауза между запросами – вежливо к общему сервису
# язык на сайте -> языковые метки Wikidata по приоритету (у казахских бывает и метка kk-cyrl)
LABEL_LANGS = {"ru": ("ru",), "kk": ("kk", "kk-cyrl"), "en": ("en",)}

# TMDb: путь к постеру по tmdbId; ключ – переменная окружения TMDB_TOKEN («Ключ доступа к API», v4)
TMDB_URL = "https://api.themoviedb.org/3/movie/{}"
TMDB_WORKERS = 8  # параллельных запросов: TMDb разрешает около 40–50 в секунду

SAVE_EVERY = 1000  # при долгой загрузке названий и постеров – промежуточное сохранение (можно прервать)

USER_AGENT = "KinoCompass/1.0 (https://github.com/AlexTrav/KinoCompass; student project)"
TIMEOUT_SEC = 60
# повторы при сбое источника: 5 попыток, паузы растут вдвое (2, 4, 8, 16 с) с небольшим разбросом
RETRIES = 5
BACKOFF_SEC = 2
