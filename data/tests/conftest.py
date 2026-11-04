import pandas as pd
import pytest

from collect.config import MIN_RATINGS


def utc(day: str) -> pd.Timestamp:
    return pd.Timestamp(day, tz="UTC")


# маленький набор в формате work/*.parquet: фильм 1 – MIN_RATINGS оценок (попадает в каталог),
# фильм 2 – на одну меньше (не попадает), фильм 3 – без оценок
@pytest.fixture
def ratings() -> pd.DataFrame:
    rows = [(user, 1, 4.0, utc("2000-01-01") + pd.Timedelta(days=user)) for user in range(MIN_RATINGS)]
    rows += [(user, 2, 3.0, utc("2010-06-01")) for user in range(MIN_RATINGS - 1)]
    rows[0] = (0, 1, 5.0, utc("1999-12-31"))
    return pd.DataFrame(rows, columns=["user_id", "movie_id", "rating", "time"])


@pytest.fixture
def movies() -> pd.DataFrame:
    return pd.DataFrame({
        "movie_id": [1, 2, 3],
        "title": ["Matrix, The (1999)", "Seven (a.k.a. Se7en) (1995)", "Untitled"],
        "genres": ["Action|Sci-Fi", "Mystery|Thriller", "(no genres listed)"],
    })


@pytest.fixture
def links() -> pd.DataFrame:
    return pd.DataFrame({"movie_id": [1, 2, 3], "imdb_id": ["0133093", "0114369", "12345678"],
                         "tmdb_id": [603, 807, None]}).astype({"tmdb_id": "Int32"})


@pytest.fixture
def tags() -> pd.DataFrame:
    return pd.DataFrame({
        "user_id": [1, 2, 3, 1, 4, 5],
        "movie_id": [1, 1, 1, 1, 1, 2],
        "tag": ["Cyberpunk", "cyberpunk ", "philosophy", "Philosophy", "my dvd", "twist ending"],
    })
