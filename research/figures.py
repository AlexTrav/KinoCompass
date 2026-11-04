"""Рисунки исследования для отчёта – только по сохранённым сводкам results/ (набор не нужен):
    make -C research figures FIGURES=/путь/к/папке"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
import pandas as pd

from style import (AQUA, AXIS, BLUE, BLUE_LIGHT, CATEGORICAL, COMMA, DIVERGING, INK, INK2, MUTED, ORANGE,
                   PERCENT, THOUSANDS, WASH, num, percent, save, thousands)

RESULTS = Path(__file__).resolve().parent / "results"
SUMMARY = json.loads((RESULTS / "eda.json").read_text(encoding="utf-8"))

# названия жанров MovieLens по-русски
GENRE_RU = {
    "Action": "Боевик", "Adventure": "Приключения", "Animation": "Анимация", "Children": "Детский",
    "Comedy": "Комедия", "Crime": "Криминал", "Documentary": "Документальный", "Drama": "Драма",
    "Fantasy": "Фэнтези", "Film-Noir": "Нуар", "Horror": "Ужасы", "Musical": "Мюзикл", "Mystery": "Детектив",
    "Romance": "Мелодрама", "Sci-Fi": "Фантастика", "Thriller": "Триллер", "War": "Военный", "Western": "Вестерн",
}


def read(name: str, **kwargs) -> pd.DataFrame:
    return pd.read_csv(RESULTS / f"{name}.csv", **kwargs)


def bin_labels(frame: pd.DataFrame, last: str = "{a} и больше") -> list[str]:
    labels = []
    for i, (a, b) in enumerate(zip(frame["from"], frame["to"])):
        labels.append(last.format(a=thousands(a)) if i == len(frame) - 1 else
                      (thousands(a) if b - a == 1 else f"{thousands(a)}–{thousands(b - 1)}"))
    return labels


def fig_ratings_hist() -> None:
    frame = read("ratings_hist")
    share = frame["count"] / frame["count"].sum()
    liked = frame["rating"] >= 4
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for mask, color, label in ((~liked, BLUE_LIGHT, "ниже 4"), (liked, BLUE, "4 и выше – «понравилось»")):
        ax.bar(frame["rating"][mask], share[mask], width=0.4, color=color, label=label)
    for x, y in zip(frame["rating"], share):
        ax.text(x, y + 0.004, percent(y, 1), ha="center", fontsize=10, color=INK2)
    ax.set_xticks(frame["rating"], [num(r, 1) for r in frame["rating"]])
    ax.yaxis.set_major_formatter(PERCENT)
    ax.set_xlabel("Оценка, звёзды")
    ax.set_ylabel("Доля всех оценок")
    ax.legend(loc="upper left")
    ax.grid(axis="x", visible=False)
    save(fig, 1, "Распределение оценок")


def fig_activity() -> None:
    frame = read("monthly")
    dates = pd.to_datetime(frame["month"])
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True)
    top.plot(dates, frame["ratings"] / 1000, color=BLUE)
    top.set_ylabel("Оценок за месяц, тыс.")
    bottom.plot(dates, frame["new_users"] / 1000, color=ORANGE)
    bottom.set_ylabel("Новых людей за месяц, тыс.")
    for ax in (top, bottom):
        ax.yaxis.set_major_formatter(COMMA)
    bottom.set_xlabel("Месяц оценки")
    save(fig, 2, "Активность MovieLens по месяцам")


def fig_half_stars() -> None:
    frame = read("monthly")
    frame = frame[frame["ratings"] >= 1000]
    dates = pd.to_datetime(frame["month"])
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(dates, frame["half_share"], color=BLUE)
    start = SUMMARY["half_stars_from"]
    if start:
        ax.axvline(pd.Timestamp(start), color=MUTED, linestyle="--", linewidth=1)
        ax.text(pd.Timestamp(start) - pd.Timedelta(days=60), 0.2, f"половинные оценки\nпоявились {pd.Timestamp(start):%m.%Y}",
                color=INK2, ha="right")
    ax.yaxis.set_major_formatter(PERCENT)
    ax.set_xlabel("Месяц оценки")
    ax.set_ylabel("Доля оценок 0,5; 1,5 … 4,5")
    save(fig, 3, "Доля половинных оценок по месяцам")


def fig_long_tail() -> None:
    frame = read("lorenz")
    pop, users = SUMMARY["movies_popularity"], SUMMARY["users_activity"]
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot([0, 1], [0, 1], color=AXIS, linestyle="--", linewidth=1, label="если бы всем поровну")
    ax.plot(frame["items"], frame["movies"], color=BLUE, label=f"фильмы (Джини {num(pop['gini'])})")
    ax.plot(frame["items"], frame["users"], color=ORANGE, label=f"люди (Джини {num(users['gini'])})")
    # у точек – короткие метки в просвете между кривыми, пояснение – в пустом углу под диагональю
    for share, value in ((0.01, pop["top1_share"]), (0.10, pop["top10_share"])):
        ax.plot(share, value, "o", color=BLUE, markersize=7)
        ax.annotate(percent(share), (share, value), xytext=(9, -5), textcoords="offset points", color=INK)
    ax.text(0.4, 0.3, f"верхний 1 % фильмов собирает {percent(pop['top1_share'])} оценок,\n"
                      f"верхние 10 % – {percent(pop['top10_share'])};\n"
                      f"у людей верхний 1 % ставит {percent(users['top1_share'])} оценок", color=INK, va="center")
    ax.xaxis.set_major_formatter(PERCENT)
    ax.yaxis.set_major_formatter(PERCENT)
    ax.set_xlabel("Доля фильмов или людей, от самых активных")
    ax.set_ylabel("Доля всех оценок")
    ax.legend(loc="lower right")
    save(fig, 4, "Длинный хвост популярности")


def fig_bins(name: str, n: int, title: str, xlabel: str, mark: int | None = None, upto: int | None = None) -> None:
    frame = read(name)
    if upto is not None:  # редкие крайние группы – в одну «upto и больше», без пустых столбцов
        tail = frame[frame["from"] >= upto]
        frame = pd.concat([frame[frame["from"] < upto],
                           pd.DataFrame({"from": [upto], "to": [tail["to"].max()], "count": [tail["count"].sum()]})],
                          ignore_index=True)
    share = frame["count"] / frame["count"].sum()
    labels = bin_labels(frame)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    colors = [BLUE if mark is None or a >= mark else BLUE_LIGHT for a in frame["from"]]
    ax.bar(range(len(frame)), share, color=colors, width=0.7)
    if mark is not None:
        ax.set_ylim(0, share.max() * 1.4)  # место для легенды над столбцами
        ax.legend(handles=[Patch(color=BLUE_LIGHT, label=f"меньше {mark}"),
                           Patch(color=BLUE, label=f"{mark} и больше – столько MovieLens просит оценить при знакомстве")],
                  loc="upper left")
    for i, y in enumerate(share):
        ax.text(i, y + 0.004, percent(y, 1), ha="center", fontsize=10, color=INK2)
    ax.set_xticks(range(len(frame)), labels, rotation=30, ha="right")
    ax.yaxis.set_major_formatter(PERCENT)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Доля людей")
    ax.grid(axis="x", visible=False)
    save(fig, n, title)


def fig_popularity() -> None:
    frame = read("popularity")
    info = SUMMARY["popularity_vs_mean"]
    x = np.arange(len(frame))
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.fill_between(x, frame["q25"], frame["q75"], color=BLUE_LIGHT, alpha=0.6, label="половина фильмов группы")
    ax.plot(x, frame["median"], "o-", color=BLUE, markersize=7, label="медиана")
    labels = bin_labels(frame.rename(columns={"from": "from"}).assign(to=list(frame["from"][1:]) + [10 ** 9]))
    ax.set_xticks(x, labels, rotation=30, ha="right")
    ax.yaxis.set_major_formatter(COMMA)
    ax.set_xlabel("Число оценок фильма")
    ax.set_ylabel("Средняя оценка фильма")
    ax.set_title(f"Спирмен ρ = {num(info['spearman'])}, {thousands(info['movies'])} фильмов", color=INK2)
    ax.legend(loc="upper left")
    save(fig, 7, "Популярность фильма и его средняя оценка")


def fig_release_year() -> None:
    frame = read("release_years")
    frame = frame[(frame["ratings"] >= 10_000) & (frame["year"] <= 2023)]
    info = SUMMARY["year_vs_mean"]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(frame["year"], frame["mean_rating"], color=BLUE)
    ax.axhline(SUMMARY["mean_rating"], color=MUTED, linestyle="--", linewidth=1)
    ax.text(frame["year"].min(), SUMMARY["mean_rating"] - 0.015, f"средняя по всем оценкам {num(SUMMARY['mean_rating'])}",
            color=INK2, va="top")
    ax.yaxis.set_major_formatter(COMMA)
    ax.set_xlabel("Год выпуска фильма (годы минимум с 10 000 оценок)")
    ax.set_ylabel("Средняя оценка")
    ax.set_title(f"Спирмен ρ (год – средняя фильма) = {num(info['spearman'])}", color=INK2)
    save(fig, 8, "Год выпуска фильма и средняя оценка")


def fig_age() -> None:
    frame = read("age_at_rating")
    info = SUMMARY["age_at_rating"]
    share = frame["ratings"] / frame["ratings"].sum()
    frame, share = frame[frame["age"] >= 0], share[frame["age"] >= 0]  # оценок до выхода фильма меньше 0,01 %
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.bar(frame["age"], share, color=BLUE, width=0.8)
    ax.set_xticks([0, 5, 10, 20, 30, 40, 50, 60], ["0", "5", "10", "20", "30", "40", "50", "60+"])
    ax.yaxis.set_major_formatter(PERCENT)
    ax.set_xlabel("Сколько лет прошло от выхода фильма до оценки")
    ax.set_ylabel("Доля оценок")
    ax.set_title(f"Медиана – {info['median_age_years']} лет; в год выхода или через год – "
                 f"{percent(info['share_within_1_year'])}", color=INK2)
    ax.grid(axis="x", visible=False)
    save(fig, 9, "Возраст фильма в момент оценки")


def fig_genres() -> None:
    frame = read("genres").sort_values("ratings_share")
    names = [GENRE_RU[g] for g in frame["genre"]]
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 6.5), sharey=True, layout="constrained")
    left.barh(names, frame["ratings_share"], color=BLUE, height=0.65)
    for y, v in enumerate(frame["ratings_share"]):
        left.text(v + 0.005, y, percent(v), va="center", fontsize=10, color=INK2)
    left.xaxis.set_major_formatter(PERCENT)
    left.set_xlabel("Доля всех оценок (фильм бывает в нескольких жанрах)")
    right.plot(frame["mean_rating"], names, "o", color=BLUE, markersize=8)
    right.axvline(SUMMARY["mean_rating"], color=MUTED, linestyle="--", linewidth=1)
    for y, v in enumerate(frame["mean_rating"]):
        right.text(v + 0.012, y, num(v), va="center", fontsize=10, color=INK2)
    right.xaxis.set_major_formatter(COMMA)
    right.set_xlabel("Средняя оценка (пунктир – по всем оценкам)")
    kw = SUMMARY["genres_kruskal"]
    fig.suptitle(f"Краскел – Уоллис по средним фильмов: H = {num(kw['H'], 0)}, p < 0,001" if kw["p"] < 0.001 else "",
                 color=INK2, fontsize=12)
    for ax in (left, right):
        ax.grid(axis="y", visible=False)
    save(fig, 10, "Жанры – доля оценок и средняя оценка")


def heatmap(frame: pd.DataFrame, n: int, title: str, label: str) -> None:
    names = [GENRE_RU[g] for g in frame.index]
    values = frame.to_numpy(dtype=float)
    np.fill_diagonal(values, np.nan)  # жанр сам с собой (всегда 1) – нейтральная клетка, не отвлекает
    limit = np.nanmax(np.abs(values))
    fig, ax = plt.subplots(figsize=(11, 9.5))
    cmap = DIVERGING.copy()
    cmap.set_bad(WASH)
    image = ax.imshow(values, cmap=cmap, vmin=-limit, vmax=limit)
    for i in range(len(values)):
        for j in range(len(values)):
            if not np.isnan(values[i, j]):
                ax.text(j, i, num(values[i, j]), ha="center", va="center", fontsize=7.5,
                        color="white" if abs(values[i, j]) > 0.6 * limit else INK)
    ax.set_xticks(range(len(names)), names, rotation=45, ha="right")
    ax.set_yticks(range(len(names)), names)
    ax.grid(False)
    bar = fig.colorbar(image, ax=ax, shrink=0.8)
    bar.set_label(label)
    bar.ax.yaxis.set_major_formatter(COMMA)
    save(fig, n, title)


def fig_genre_years() -> None:
    frame = read("genre_years")
    frame = frame[frame["ratings"] >= 100_000]
    shown = ["Drama", "Comedy", "Action", "Thriller", "Sci-Fi", "Horror"]
    fig, ax = plt.subplots(figsize=(10.5, 5.5))
    ends = frame[shown].iloc[-1].sort_values()
    # подписи у концов линий разводятся по вертикали, чтобы близкие жанры (боевик и комедия) не слипались
    placed, last = {}, -1.0
    for genre, value in ends.items():
        placed[genre] = last = max(value, last + 0.018)
    for genre, color in zip(shown, CATEGORICAL):
        ax.plot(frame["year"], frame[genre], color=color, label=GENRE_RU[genre])
        ax.text(frame["year"].iloc[-1] + 0.4, placed[genre], GENRE_RU[genre], color=INK, va="center")
    ax.yaxis.set_major_formatter(PERCENT)
    ax.set_xlim(frame["year"].min(), frame["year"].max() + 3.5)
    ax.set_xlabel("Год оценки")
    ax.set_ylabel("Доля оценок фильмам жанра")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=6, frameon=False)
    save(fig, 13, "Доля жанров в оценках по годам")


def fig_tags() -> None:
    frame = read("tags_top").head(20).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 6.5))
    ax.barh(frame["tag"], frame["people"], color=BLUE, height=0.65)
    for y, v in enumerate(frame["people"]):
        ax.text(v, y, f" {thousands(v)}", va="center", fontsize=10, color=INK2)
    ax.xaxis.set_major_formatter(THOUSANDS)
    ax.set_xlim(0, frame["people"].max() * 1.1)
    ax.set_xlabel("Сколько разных людей поставили тег")
    ax.grid(axis="y", visible=False)
    save(fig, 14, "Самые частые теги")


def fig_windows() -> None:
    frame = read("windows")
    labels = [f"{s[:4]}/{e[2:4]}" for s, e in zip(frame["start"], frame["end"])]
    x = np.arange(len(frame))
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    top.bar(x, frame["warm_users"] / 1000, color=BLUE, width=0.65, label="были и раньше («тёплые»)")
    top.bar(x, frame["cold_users"] / 1000, bottom=frame["warm_users"] / 1000, color=ORANGE, width=0.65,
            label="впервые в этом году («холодные»)", edgecolor="white", linewidth=1)
    top.set_ylabel("Активных людей, тыс.")
    top.yaxis.set_major_formatter(COMMA)
    top.set_ylim(0, (frame["warm_users"] + frame["cold_users"]).max() / 1000 * 1.35)  # место для легенды
    top.legend(loc="upper right", ncol=2)
    bottom.plot(x, frame["new_movie_ratings_share"], "o-", color=AQUA, label="оценки новым фильмам")
    bottom.plot(x, frame["cold_user_ratings_share"], "o-", color=ORANGE, label="оценки «холодных» людей")
    bottom.yaxis.set_major_formatter(PERCENT)
    bottom.set_ylim(0, 1)
    bottom.set_ylabel("Доля оценок года")
    bottom.legend(loc="center left")
    bottom.set_xticks(x, labels)
    first, last = pd.Timestamp(frame["start"].iloc[-1]), pd.Timestamp(frame["end"].iloc[-1]) - pd.Timedelta(days=1)
    bottom.set_xlabel(f"Год с {first:%d.%m} по {last:%d.%m} (последний – до конца набора {last:%d.%m.%Y})")
    for ax in (top, bottom):
        ax.grid(axis="x", visible=False)
    save(fig, 15, "Годовые окна для разбиения по времени")


def main() -> None:
    fig_ratings_hist()
    fig_activity()
    fig_half_stars()
    fig_long_tail()
    fig_bins("user_activity", 5, "Сколько фильмов оценивают люди", "Число оценок у человека", upto=2000)
    fig_bins("first_day", 6, "Оценки в первые сутки", "Сколько фильмов человек оценил в первые 24 часа",
             mark=15)
    fig_popularity()
    fig_release_year()
    fig_age()
    fig_genres()
    heatmap(read("genre_cooccurrence", index_col=0), 11, "Сочетания жанров у фильмов",
            "Корреляция «фильм в жанре А» и «фильм в жанре Б»")
    heatmap(read("genre_taste", index_col=0), 12, "Корреляции вкусов по жанрам",
            "Корреляция отклонений оценок человека по жанрам")
    fig_genre_years()
    fig_tags()
    fig_windows()


if __name__ == "__main__":
    main()
