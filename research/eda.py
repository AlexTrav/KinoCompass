"""Исследование оценок MovieLens 32M: распределение оценок, активность во времени, длинный хвост, новички,
популярность и год выпуска, жанры и корреляции вкусов, теги, окна для разбиения по времени.

Набор скачивается в оперативную память один раз (collect.movielens.fetch). Все расчёты идут по компактным
массивам numpy через bincount и маски жанров – без матрицы «пользователи × фильмы». Сводки пишутся в
results/ (небольшие CSV и eda.json, в git): по ним рисует figures.py без повторной загрузки набора."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from collect.catalog import norm_tag, parse_genres, parse_title
from collect.config import GENRES, MIN_RATINGS

RESULTS = Path(__file__).resolve().parent / "results"
DAY = 86_400
# жанры анализа по алфавиту; IMAX – формат показа, а не жанр, в анализ не входит
GENRE_LIST = sorted(GENRES - {"IMAX"})
POSITIVE = 4.0  # «понравилось» – оценка 4 и выше: цель рекомендаций топ-N на шаге 3
FIRST_DAY_TARGET = 15  # MovieLens просит новичка сразу оценить 15 фильмов
MIN_GENRE_RATINGS = 5  # отклонение вкуса по жанру считается, если у человека не меньше 5 оценок жанра
MIN_PAIR_USERS = 1000  # корреляция пары жанров – если отклонения есть у стольких людей
POPULARITY_BINS = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10_000, 20_000, 50_000, 200_000]
USER_BINS = [20, 30, 50, 100, 200, 500, 1000, 2000, 5000, 10_000, 50_000]
FIRST_DAY_BINS = [1, 5, 10, 15, 20, 50, 100, 100_000]
WINDOWS = 10  # годовых окон, заканчивающихся последним днём набора, – для выбора границ разбиения


# ---------- время ----------------------------------------------------------------------------------------------

def seconds(times: pd.Series) -> np.ndarray:
    """Метки UTC -> секунды Unix (int64) без промежуточных объектов Timestamp на каждую строку."""
    return times.dt.tz_localize(None).to_numpy().astype("datetime64[s]").astype(np.int64)


def month_index(secs: np.ndarray) -> np.ndarray:
    """Номер месяца с января 1970 (int32): 0 – 1970-01."""
    return secs.astype("datetime64[s]").astype("datetime64[M]").astype(np.int32)


def year_of(secs: np.ndarray) -> np.ndarray:
    return (secs.astype("datetime64[s]").astype("datetime64[Y]").astype(np.int32) + 1970).astype(np.int16)


def month_label(index: int) -> str:
    return str(np.datetime64(int(index), "M"))


def day_label(secs: int) -> str:
    return str(np.datetime64(int(secs), "s").astype("datetime64[D]"))


# ---------- неравенство популярности ---------------------------------------------------------------------------

def gini(counts: np.ndarray) -> float:
    """Коэффициент Джини: 0 – у всех поровну, около 1 – почти всё у одного."""
    x = np.sort(np.asarray(counts, dtype=np.float64))
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1) @ x / (n * x.sum()))


def top_share(counts: np.ndarray, share: float) -> float:
    """Доля всех оценок у верхних share объектов по популярности."""
    x = np.sort(np.asarray(counts, dtype=np.float64))[::-1]
    k = max(1, int(np.ceil(share * len(x))))
    return float(x[:k].sum() / x.sum())


def lorenz(counts: np.ndarray, points: int = 201) -> pd.DataFrame:
    """Кривая концентрации: доля объектов (от самых популярных) -> доля их оценок, points точек."""
    x = np.sort(np.asarray(counts, dtype=np.float64))[::-1]
    items = np.r_[0, np.arange(1, len(x) + 1) / len(x)]
    ratings = np.r_[0, np.cumsum(x) / x.sum()]
    grid = np.linspace(0, 1, points)
    return pd.DataFrame({"items": grid, "ratings": np.interp(grid, items, ratings)})


def binned(values: np.ndarray, edges: list[int]) -> pd.DataFrame:
    """Сколько значений в каждом полуинтервале [edges[i]; edges[i+1])."""
    counts, _ = np.histogram(values, bins=edges)
    return pd.DataFrame({"from": edges[:-1], "to": edges[1:], "count": counts})


# ---------- время и активность ---------------------------------------------------------------------------------

def first_seen(keys: np.ndarray, secs: np.ndarray, size: int) -> np.ndarray:
    """Время первой оценки по id (пользователя или фильма); у отсутствующих id – максимум int64."""
    first = np.full(size, np.iinfo(np.int64).max, dtype=np.int64)
    series = pd.Series(secs).groupby(keys, sort=False).min()
    first[series.index.to_numpy()] = series.to_numpy()
    return first


def monthly(users: np.ndarray, secs: np.ndarray, rating: np.ndarray, user_first: np.ndarray) -> pd.DataFrame:
    """По месяцам: оценки, активные и новые пользователи, средняя оценка, доля половинных оценок (3,5 и т. п.)."""
    months = month_index(secs)
    base = int(months.min())
    offset = (months - base).astype(np.int64)
    size = int(offset.max()) + 1
    n = np.bincount(offset, minlength=size)
    half = np.bincount(offset, weights=(np.round(rating * 2) % 2 == 1), minlength=size)
    total = np.bincount(offset, weights=rating, minlength=size)
    pairs = np.unique(users.astype(np.int64) * size + offset)  # пара «пользователь – месяц» один раз
    active = np.bincount(pairs % size, minlength=size)
    seen = user_first[user_first < np.iinfo(np.int64).max]
    new = np.bincount(month_index(seen) - base, minlength=size)
    with np.errstate(invalid="ignore", divide="ignore"):
        frame = pd.DataFrame({
            "month": [month_label(base + i) for i in range(size)],
            "ratings": n, "active_users": active, "new_users": new,
            "mean_rating": np.round(total / n, 4), "half_share": np.round(half / n, 4),
        })
    return frame


def first_day(users: np.ndarray, secs: np.ndarray, user_first: np.ndarray) -> tuple[dict, pd.DataFrame]:
    """Первые сутки пользователя (24 часа от первой оценки): сколько оценок ставится сразу при знакомстве."""
    day1 = secs - user_first[users] < DAY
    per_user = np.bincount(users[day1])
    total = np.bincount(users)
    active = total > 0
    per_user = np.pad(per_user, (0, len(total) - len(per_user)))[active]
    total = total[active]
    info = {
        "share_ratings_first_day": round(float(day1.mean()), 4),
        "median_first_day": int(np.median(per_user)),
        f"share_users_{FIRST_DAY_TARGET}_plus_first_day": round(float((per_user >= FIRST_DAY_TARGET).mean()), 4),
        "share_users_only_first_day": round(float((per_user == total).mean()), 4),
    }
    return info, binned(per_user, FIRST_DAY_BINS)


# ---------- фильмы ---------------------------------------------------------------------------------------------

def movie_table(movies: np.ndarray, rating: np.ndarray) -> pd.DataFrame:
    """По фильму: число оценок, средняя, доля оценок 4 и выше (только фильмы с оценками)."""
    n = np.bincount(movies)
    total = np.bincount(movies, weights=rating)
    positive = np.bincount(movies, weights=rating >= POSITIVE)
    rated = np.flatnonzero(n)
    return pd.DataFrame({"movie_id": rated, "n": n[rated], "mean": total[rated] / n[rated],
                         "positive": positive[rated] / n[rated]})


def popularity_bins(table: pd.DataFrame) -> pd.DataFrame:
    """Средняя оценка фильмов в группах по популярности (фильмы минимум с MIN_RATINGS оценками)."""
    table = table[table["n"] >= MIN_RATINGS]
    groups = pd.cut(table["n"], POPULARITY_BINS, right=False)
    out = table.groupby(groups, observed=True)["mean"].describe()[["count", "25%", "50%", "75%"]]
    out.index = [int(interval.left) for interval in out.index]
    return out.rename(columns={"count": "movies", "25%": "q25", "50%": "median", "75%": "q75"}).rename_axis("from")


def movie_meta(movies: pd.DataFrame, size: int) -> tuple[np.ndarray, np.ndarray]:
    """По id фильма: год выпуска (0 – неизвестен) и битовая маска жанров GENRE_LIST."""
    years = np.zeros(size, dtype=np.int16)
    masks = np.zeros(size, dtype=np.int32)
    bit = {genre: 1 << i for i, genre in enumerate(GENRE_LIST)}
    for movie_id, title, genres in zip(movies["movie_id"], movies["title"], movies["genres"]):
        _, year = parse_title(title)
        years[movie_id] = year or 0
        masks[movie_id] = sum(bit.get(g, 0) for g in parse_genres(genres).split("|") if g)
    return years, masks


def year_table(table: pd.DataFrame, years: np.ndarray) -> pd.DataFrame:
    """По году выпуска: оценки, взвешенная средняя оценка, число фильмов с MIN_RATINGS оценками."""
    frame = table.assign(year=years[table["movie_id"]], total=table["n"] * table["mean"])
    frame = frame[frame["year"] > 0]
    out = frame.groupby("year").agg(ratings=("n", "sum"), total=("total", "sum"),
                                    movies=("n", lambda n: int((n >= MIN_RATINGS).sum())))
    out["mean_rating"] = (out.pop("total") / out["ratings"]).round(4)
    return out


def age_at_rating(movies: np.ndarray, secs: np.ndarray, years: np.ndarray) -> tuple[dict, pd.DataFrame]:
    """Сколько лет прошло от выхода фильма до оценки (год оценки минус год выпуска)."""
    release = years[movies]
    known = release > 0
    age = year_of(secs[known]) - release[known]
    clipped = np.clip(age, -1, 60) + 1
    counts = np.bincount(clipped, minlength=62)
    info = {
        "median_age_years": int(np.median(age)),
        "share_within_1_year": round(float((age <= 1).mean()), 4),
        "share_10_plus_years": round(float((age >= 10).mean()), 4),
        "share_before_release": round(float((age < 0).mean()), 4),
    }
    return info, pd.DataFrame({"age": np.arange(-1, 61), "ratings": counts})


# ---------- жанры ----------------------------------------------------------------------------------------------

def genre_table(table: pd.DataFrame, masks: np.ndarray) -> pd.DataFrame:
    rows = []
    movie_masks = masks[table["movie_id"]]
    for i, genre in enumerate(GENRE_LIST):
        part = table[(movie_masks >> i) & 1 == 1]
        total = int(part["n"].sum())
        weighted = lambda column: round(float((part["n"] * part[column]).sum() / total), 4) if total else None
        rows.append({
            "genre": genre,
            "movies": int((part["n"] >= MIN_RATINGS).sum()),
            "ratings": total,
            "mean_rating": weighted("mean"),
            "positive_share": weighted("positive"),
        })
    frame = pd.DataFrame(rows)
    frame["ratings_share"] = (frame["ratings"] / table["n"].sum()).round(4)
    return frame


def genre_kruskal(table: pd.DataFrame, masks: np.ndarray) -> dict:
    """Различаются ли средние оценки фильмов разных жанров (фильмы с MIN_RATINGS оценками; фильм нескольких
    жанров входит в каждую из своих групп)."""
    table = table[table["n"] >= MIN_RATINGS]
    movie_masks = masks[table["movie_id"]]
    groups = [table["mean"][(movie_masks >> i) & 1 == 1].to_numpy() for i in range(len(GENRE_LIST))]
    h, p = stats.kruskal(*[g for g in groups if len(g)])
    return {"H": round(float(h), 1), "p": float(p)}


def genre_cooccurrence(table: pd.DataFrame, masks: np.ndarray) -> pd.DataFrame:
    """Корреляция (фи) признаков «фильм относится к жанру» между жанрами – фильмы с MIN_RATINGS оценками."""
    movie_masks = masks[table.loc[table["n"] >= MIN_RATINGS, "movie_id"]]
    matrix = np.column_stack([(movie_masks >> i) & 1 for i in range(len(GENRE_LIST))]).astype(np.float64)
    return pd.DataFrame(np.corrcoef(matrix.T), index=GENRE_LIST, columns=GENRE_LIST).round(4)


def genre_taste(users: np.ndarray, movies: np.ndarray, rating: np.ndarray, masks: np.ndarray) -> tuple[pd.DataFrame, int]:
    """Корреляции вкусов: для каждого человека – насколько он в среднем оценивает жанр выше или ниже своей
    обычной оценки (не меньше MIN_GENRE_RATINGS оценок жанра); затем корреляция Пирсона этих отклонений между
    жанрами по людям. Положительная – кто любит один жанр, обычно любит и другой."""
    size = int(users.max()) + 1
    user_mean = np.bincount(users, weights=rating, minlength=size) / np.maximum(np.bincount(users, minlength=size), 1)
    deviation = (rating - user_mean[users]).astype(np.float32)
    movie_masks = masks[movies]
    taste = np.full((size, len(GENRE_LIST)), np.nan, dtype=np.float32)
    for i in range(len(GENRE_LIST)):
        selected = (movie_masks >> i) & 1 == 1
        count = np.bincount(users[selected], minlength=size)
        total = np.bincount(users[selected], weights=deviation[selected], minlength=size)
        enough = count >= MIN_GENRE_RATINGS
        taste[enough, i] = total[enough] / count[enough]
    frame = pd.DataFrame(taste, columns=GENRE_LIST).dropna(how="all")
    return frame.corr(min_periods=MIN_PAIR_USERS).round(4), len(frame)


def genre_years(movies: np.ndarray, secs: np.ndarray, masks: np.ndarray) -> pd.DataFrame:
    """Доля оценок фильмов каждого жанра по годам оценки."""
    years = year_of(secs).astype(np.int64)
    base = int(years.min())
    total = np.bincount(years - base)
    movie_masks = masks[movies]
    frame = pd.DataFrame({"year": np.arange(base, base + len(total)), "ratings": total})
    for i, genre in enumerate(GENRE_LIST):
        selected = (movie_masks >> i) & 1 == 1
        frame[genre] = (np.bincount(years[selected] - base, minlength=len(total)) / total).round(4)
    return frame


def strongest_pairs(matrix: pd.DataFrame, k: int = 5) -> dict:
    """k самых сильных положительных и отрицательных пар (без диагонали и повторов)."""
    upper = matrix.where(np.triu(np.ones(matrix.shape, dtype=bool), 1)).stack().dropna()
    pick = lambda s: [{"a": a, "b": b, "r": round(float(r), 3)} for (a, b), r in s.items()]
    return {"positive": pick(upper.nlargest(k)), "negative": pick(upper.nsmallest(k))}


# ---------- теги -----------------------------------------------------------------------------------------------

def tag_table(tags: pd.DataFrame, rated: pd.Series, top: int = 25) -> tuple[dict, pd.DataFrame]:
    """Самые частые теги (число разных людей) и доля фильмов с MIN_RATINGS оценками, у которых теги есть."""
    frame = tags.assign(tag=tags["tag"].fillna("").map(norm_tag))
    frame = frame[frame["tag"] != ""]
    people = frame[["user_id", "tag"]].drop_duplicates()["tag"].value_counts()
    per_movie = frame.groupby(["movie_id", "tag"])["user_id"].nunique()
    shared = per_movie[per_movie >= 2].index.get_level_values(0).unique()
    info = {
        "distinct_tags": int(len(people)),
        "taggers": int(frame["user_id"].nunique()),
        "share_movies_any_tag": round(float(rated.isin(frame["movie_id"]).mean()), 4),
        "share_movies_shared_tag": round(float(rated.isin(shared).mean()), 4),
    }
    return info, people.head(top).rename_axis("tag").reset_index(name="people")


# ---------- окна для разбиения по времени ----------------------------------------------------------------------

def windows(users: np.ndarray, movies: np.ndarray, secs: np.ndarray, rating: np.ndarray,
            user_first: np.ndarray, movie_first: np.ndarray, count: int = WINDOWS) -> pd.DataFrame:
    """Годовые окна, заканчивающиеся днём после последней оценки (12.10 – 12.10 и т. д.): сколько в окне оценок,
    «тёплых» пользователей (были и раньше), «холодных» (впервые в окне), новых фильмов и оценок им."""
    end = pd.Timestamp(day_label(int(secs.max())), tz="UTC") + pd.Timedelta(days=1)
    rows = []
    for k in range(count):
        stop, start = end - pd.DateOffset(years=k), end - pd.DateOffset(years=k + 1)
        a, b = int(start.timestamp()), int(stop.timestamp())
        inside = (secs >= a) & (secs < b)
        u, m = users[inside], movies[inside]
        active = np.unique(u)
        cold = (user_first[active] >= a).sum()
        positive_users = np.unique(u[rating[inside] >= POSITIVE])
        warm_positive = int((user_first[positive_users] < a).sum())
        new_movies = (movie_first[np.unique(m)] >= a).sum()
        rows.append({
            "start": start.strftime("%Y-%m-%d"), "end": stop.strftime("%Y-%m-%d"),
            "ratings": int(inside.sum()),
            "positive_share": round(float((rating[inside] >= POSITIVE).mean()), 4),
            "active_users": len(active), "warm_users": int(len(active) - cold), "cold_users": int(cold),
            "warm_users_with_positive": warm_positive,
            "cold_user_ratings_share": round(float((user_first[u] >= a).mean()), 4),
            "new_movies": int(new_movies),
            "new_movie_ratings_share": round(float((movie_first[m] >= a).mean()), 4),
        })
    return pd.DataFrame(rows[::-1])


# ---------- запуск ---------------------------------------------------------------------------------------------

def save_csv(frame: pd.DataFrame, name: str, index: bool = False) -> None:
    frame.to_csv(RESULTS / f"{name}.csv", index=index, lineterminator="\n")


def main() -> None:
    from collect.movielens import fetch

    frames, _ = fetch()
    ratings = frames.pop("ratings")
    users = ratings["user_id"].to_numpy(np.int32)
    movies = ratings["movie_id"].to_numpy(np.int32)
    rating = ratings["rating"].to_numpy(np.float32)
    secs = seconds(ratings["time"])
    del ratings
    RESULTS.mkdir(exist_ok=True)
    print("набор в памяти, считаю", flush=True)

    n_users, n_movies = int(users.max()) + 1, int(movies.max()) + 1
    user_first = first_seen(users, secs, n_users)
    movie_first = first_seen(movies, secs, n_movies)
    user_counts = np.bincount(users)
    user_counts = user_counts[user_counts > 0]
    table = movie_table(movies, rating)
    years, masks = movie_meta(frames["movies"], n_movies)

    month = monthly(users, secs, rating, user_first)
    save_csv(month, "monthly")
    half = month[month["half_share"] > 0.01]
    first_info, first_bins = first_day(users, secs, user_first)
    save_csv(first_bins, "first_day")
    save_csv(pd.DataFrame({"rating": np.arange(1, 11) / 2,
                           "count": np.bincount(np.round(rating * 2).astype(np.int64), minlength=11)[1:]}),
             "ratings_hist")
    save_csv(binned(user_counts, USER_BINS), "user_activity")
    save_csv(lorenz(table["n"].to_numpy()).rename(columns={"ratings": "movies"}).assign(
        users=lorenz(user_counts)["ratings"]).round(5), "lorenz")
    save_csv(popularity_bins(table).round(4), "popularity", index=True)

    rated = table.loc[table["n"] >= MIN_RATINGS]
    rho_pop = stats.spearmanr(rated["n"], rated["mean"])
    with_year = rated[years[rated["movie_id"]] > 0]
    rho_year = stats.spearmanr(years[with_year["movie_id"]], with_year["mean"])
    save_csv(year_table(table, years), "release_years", index=True)
    age_info, ages = age_at_rating(movies, secs, years)
    save_csv(ages, "age_at_rating")
    print("жанры", flush=True)

    genres = genre_table(table, masks)
    save_csv(genres, "genres")
    cooc = genre_cooccurrence(table, masks)
    save_csv(cooc, "genre_cooccurrence", index=True)
    taste, taste_users = genre_taste(users, movies, rating, masks)
    save_csv(taste, "genre_taste", index=True)
    save_csv(genre_years(movies, secs, masks), "genre_years")
    tags_info, tags = tag_table(frames["tags"], rated["movie_id"])
    save_csv(tags, "tags_top")
    print("окна для разбиения", flush=True)
    save_csv(windows(users, movies, secs, rating, user_first, movie_first), "windows")

    summary = {
        "ratings": len(rating), "users": len(user_counts), "movies_rated": len(table),
        "density": round(len(rating) / (len(user_counts) * len(table)), 6),
        "period": [day_label(int(secs.min())), day_label(int(secs.max()))],
        "mean_rating": round(float(rating.mean()), 4), "median_rating": float(np.median(rating)),
        "positive_share": round(float((rating >= POSITIVE).mean()), 4),
        "half_stars_from": half["month"].iloc[0] if len(half) else None,
        "users_activity": {
            "median": int(np.median(user_counts)), "mean": round(float(user_counts.mean()), 1),
            "p90": int(np.percentile(user_counts, 90)), "max": int(user_counts.max()),
            "gini": round(gini(user_counts), 4), "top1_share": round(top_share(user_counts, 0.01), 4),
        },
        "movies_popularity": {
            "median": int(table["n"].median()), "with_min_ratings": len(rated),
            "gini": round(gini(table["n"].to_numpy()), 4),
            "top1_share": round(top_share(table["n"].to_numpy(), 0.01), 4),
            "top10_share": round(top_share(table["n"].to_numpy(), 0.10), 4),
            "single_rating_share": round(float((table["n"] == 1).mean()), 4),
        },
        "first_day": first_info,
        "popularity_vs_mean": {"spearman": round(float(rho_pop.statistic), 4), "p": float(rho_pop.pvalue),
                               "movies": len(rated)},
        "year_vs_mean": {"spearman": round(float(rho_year.statistic), 4), "p": float(rho_year.pvalue),
                         "movies": len(with_year)},
        "age_at_rating": age_info,
        "genres_kruskal": genre_kruskal(table, masks),
        "genre_cooccurrence_pairs": strongest_pairs(cooc),
        "genre_taste_pairs": strongest_pairs(taste), "genre_taste_users": taste_users,
        "tags": tags_info,
    }
    (RESULTS / "eda.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
