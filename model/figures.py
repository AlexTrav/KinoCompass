"""Рисунки моделей для отчёта – только по сохранённым отчётам reports/ (набор не нужен):
    make -C model figures FIGURES=/путь/к/папке
Нумерация продолжает рисунки исследования (research/figures.py – 1–15)."""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

from style import AQUA, BLUE, COMMA, GREEN, INK2, MAGENTA, MUTED, ORANGE, PERCENT, YELLOW, num, percent, save, thousands

REPORTS = Path(__file__).resolve().parent / "reports"

MODEL_RU = {
    "random": "случайная",
    "popular": "популярные за всё время",
    "popular_year": "популярные за последний год",
    "popular_liked": "популярные среди понравившегося",
    "best_rated": "лучшие по средней оценке",
}
SCENARIO_RU = {"cold5": "Новичок, 5 оценок", "cold10": "Новичок, 10 оценок", "warm": "Постоянный"}


def load(name: str, period: str = "validation") -> dict:
    return json.loads((REPORTS / name / f"{period}.json").read_text(encoding="utf-8"))


def fig_baselines() -> None:
    report = load("baselines")
    scenarios = list(SCENARIO_RU)
    fig, axes = plt.subplots(1, len(scenarios), figsize=(13, 4.8), sharey=True, layout="constrained")
    order = sorted(MODEL_RU, key=lambda m: report["ranking"]["warm"][m]["ndcg@10"])
    for ax, scenario in zip(axes, scenarios):
        rows = [report["ranking"][scenario][m] for m in order]
        values = np.array([r["ndcg@10"] for r in rows])
        low = values - np.array([r["ndcg@10_ci95"][0] for r in rows])
        high = np.array([r["ndcg@10_ci95"][1] for r in rows]) - values
        y = np.arange(len(order))
        ax.barh(y, values, color=BLUE, height=0.6, xerr=[low, high], error_kw={"ecolor": INK2, "capsize": 3})
        for i, v in enumerate(values):
            ax.text(v + high[i] + values.max() * 0.03, i, num(v, 3), va="center", fontsize=10, color=INK2)
        ax.set_xlim(0, (values + high).max() * 1.3)
        ax.set_title(f"{SCENARIO_RU[scenario]} ({thousands(report['scenarios'][scenario]['people'])} чел.)")
        ax.xaxis.set_major_formatter(COMMA)
        ax.set_xlabel("NDCG@10 (отрезок – 95 % интервал)")
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(np.arange(len(order)), [MODEL_RU[m] for m in order])
    save(fig, 16, "Базовые модели на валидации")


# семейства моделей шага 4: префикс имени -> (подпись, отчёт, цвет); цвета – по порядку палитры
FAMILIES = {
    "item_knn": ("item-kNN", "knn", BLUE),
    "user_knn": ("user-kNN", "knn", ORANGE),
    "als": ("ALS", "factorization", AQUA),
    "bpr": ("BPR", "factorization", YELLOW),
    "svd": ("SVD", "factorization", MAGENTA),
    "ease": ("EASE", "ease", GREEN),
}
BAR = "popular_year"  # планка – лучшая базовая модель
# куда подписывать лучшую точку семейства на панели постоянных (сдвиг в пунктах), чтобы не задеть соседей
LABEL_AT = {"user_knn": (-7, 0, "right", "center"), "item_knn": (0, -7, "center", "top"),
            "als": (-5, -4, "right", "top")}


def score(report: dict, name: str) -> float:
    """Итоговый балл – среднее NDCG@10 по сценариям (как report["score"] в новых отчётах)."""
    return float(np.mean([report["ranking"][s][name]["ndcg@10"] for s in report["ranking"]]))


def family_runs() -> list[tuple[str, str, dict, list[str]]]:
    """(префикс, подпись, отчёт, настройки семейства) для каждого семейства шага 4."""
    reports = {name: load(name) for name in {run for _, run, _ in FAMILIES.values()}}
    out = []
    for prefix, (label, run, _) in FAMILIES.items():
        names = [n for n in reports[run]["ranking"]["warm"] if n.startswith(prefix + "_")]
        out.append((prefix, label, reports[run], names))
    return out


def fig_step4_best() -> None:
    baselines = load("baselines")
    rows = [("популярные за последний год (планка)", baselines, BAR, MUTED)]
    for prefix, label, report, names in family_runs():
        best = max(names, key=lambda n: score(report, n))
        rows.append((label, report, best, BLUE))
    rows.sort(key=lambda r: score(r[1], r[2]))
    scenarios = list(SCENARIO_RU)
    fig, axes = plt.subplots(1, len(scenarios), figsize=(13, 4.6), sharey=True, layout="constrained")
    for ax, scenario in zip(axes, scenarios):
        metrics = [report["ranking"][scenario][name] for _, report, name, _ in rows]
        values = np.array([m["ndcg@10"] for m in metrics])
        low = values - np.array([m["ndcg@10_ci95"][0] for m in metrics])
        high = np.array([m["ndcg@10_ci95"][1] for m in metrics]) - values
        y = np.arange(len(rows))
        ax.barh(y, values, color=[r[3] for r in rows], height=0.6, xerr=[low, high],
                error_kw={"ecolor": INK2, "capsize": 3})
        bar = baselines["ranking"][scenario][BAR]["ndcg@10"]
        ax.axvline(bar, color=INK2, linestyle="--", linewidth=1, zorder=1)
        for i, v in enumerate(values):
            ax.text(v + high[i] + values.max() * 0.03, i, num(v, 3), va="center", fontsize=10, color=INK2, zorder=4,
                    bbox={"facecolor": "white", "edgecolor": "none", "pad": 1})
        ax.set_xlim(0, (values + high).max() * 1.3)
        ax.set_title(f"{SCENARIO_RU[scenario]} ({thousands(baselines['scenarios'][scenario]['people'])} чел.)")
        ax.xaxis.set_major_formatter(COMMA)
        ax.set_xlabel("NDCG@10 (отрезок – 95 % интервал)")
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(np.arange(len(rows)), [r[0] for r in rows])
    save(fig, 17, "Лучшие модели шага 4 против планки на валидации")


def fig_accuracy_coverage() -> None:
    baselines = load("baselines")
    scenarios = list(SCENARIO_RU)
    fig, axes = plt.subplots(1, len(scenarios), figsize=(13, 4.8), layout="constrained")
    for ax, scenario in zip(axes, scenarios):
        base = baselines["ranking"][scenario]
        for name in MODEL_RU:
            ax.scatter(base[name]["coverage@10"], base[name]["ndcg@10"], s=40, color=MUTED, zorder=2,
                       edgecolor="white", linewidth=1)
        ax.annotate("планка", (base[BAR]["coverage@10"], base[BAR]["ndcg@10"]), xytext=(6, -4),
                    textcoords="offset points", fontsize=10, color=INK2, va="top")
        for prefix, label, report, names in family_runs():
            color = FAMILIES[prefix][2]
            points = [(report["ranking"][scenario][n]["coverage@10"], report["ranking"][scenario][n]["ndcg@10"])
                      for n in names]
            xs, ys = zip(*points)
            ax.scatter(xs, ys, s=40, color=color, label=label, zorder=3, edgecolor="white", linewidth=1)
            if scenario == "warm":  # прямые подписи – там, где семейства разошлись сильнее всего
                top = int(np.argmax(ys))
                dx, dy, ha, va = LABEL_AT.get(prefix, (7, 2, "left", "bottom"))
                ax.annotate(label, (xs[top], ys[top]), xytext=(dx, dy), textcoords="offset points", fontsize=10,
                            color=INK2, ha=ha, va=va)
        ax.set_xscale("log")
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: percent(v, 0 if v >= 0.01 else 1)))
        ax.yaxis.set_major_formatter(COMMA)
        ax.set_title(SCENARIO_RU[scenario])
        ax.set_xlabel("Покрытие каталога первыми 10 советами")
    axes[0].set_ylabel("NDCG@10")
    handles = [Line2D([], [], marker="o", linestyle="", markersize=7, color=MUTED, label="базовые")]
    handles += [Line2D([], [], marker="o", linestyle="", markersize=7, color=c, label=l)
                for l, _, c in FAMILIES.values()]
    fig.legend(handles=handles, loc="outside lower center", ncol=len(handles))
    save(fig, 18, "Точность и покрытие каталога у моделей шага 4")


CONTENT_RU = {
    "popular_year": "популярные за последний год",
    "newest": "свежие по году",
    "random": "случайная",
    "content_tfidf_meta_centered": "TF-IDF: жанры, десятилетие, теги",
    "content_tfidf_text_centered": "TF-IDF + слова описания",
    "content_tfidf_text_binary": "TF-IDF + слова описания (вес 1)",
    "content_e5_en_centered": "e5, английский текст",
    "content_e5_enru_binary": "e5, английский + русский (вес 1)",
}
BASES = {"popular_year", "newest", "random"}


def fig_content() -> None:
    panels = [(load("content"), "Кандидаты"), (load("content", "validation_new"), "Новинки")]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), layout="constrained")
    for ax, (report, title) in zip(axes, panels):
        names = sorted(CONTENT_RU, key=lambda n: report["score"][n])
        values = np.array([report["score"][n] for n in names])
        y = np.arange(len(names))
        ax.barh(y, values, height=0.6, color=[MUTED if n in BASES else BLUE for n in names])
        for i, v in enumerate(values):
            ax.text(v + values.max() * 0.02, i, num(v, 3), va="center", fontsize=10, color=INK2)
        ax.set_yticks(y, [CONTENT_RU[n] for n in names])
        ax.set_xlim(0, values.max() * 1.18)
        ax.xaxis.set_major_formatter(COMMA)
        ax.set_xlabel("NDCG@10, среднее по трём сценариям")
        ax.set_title(f"{title} ({thousands(report['candidates'])} фильмов)")
        ax.grid(axis="y", visible=False)
    save(fig, 20, "Контентная модель на кандидатах и новинках")


SEARCH_RU = {"e5_en": ("e5, английский текст", BLUE), "e5_enru": ("e5, английский + русский", ORANGE),
             "tfidf_text": ("TF-IDF по словам описания", AQUA)}
LANG_RU = {"ru": "русский", "kk": "казахский", "en": "английский"}


def fig_search() -> None:
    report = load("search")
    langs = list(LANG_RU)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), layout="constrained")
    width = 0.26
    x = np.arange(len(langs))
    for ax, key in zip(axes, ("plot_hit", "genre_precision")):
        for i, (name, (label, color)) in enumerate(SEARCH_RU.items()):
            values = np.array([report["variants"][name]["summary"][lang][key] for lang in langs])
            bars = ax.bar(x + (i - 1) * width, values, width * 0.9, color=color, label=label)
            for bar, v in zip(bars, values):
                text = f"{round(v * 5)} из 5" if key == "plot_hit" else percent(v)
                ax.text(bar.get_x() + bar.get_width() / 2, v + 0.015, text, ha="center", fontsize=9, color=INK2)
        if key == "genre_precision":  # случайный выбор: средняя доля ожидаемых жанров в каталоге
            rows = report["variants"]["e5_en"]["queries"]
            for j, lang in enumerate(langs):
                chance = np.mean([report["chance"][r["expect"]] for r in rows
                                  if r["lang"] == lang and r["kind"] == "genre"])
                ax.hlines(chance, j - 1.5 * width, j + 1.5 * width, color=INK2, linestyle="--", linewidth=1.2)
            ax.text(len(langs) - 1 + 1.5 * width, chance, " случайно", va="center", fontsize=9, color=INK2)
        ax.set_xticks(x, [LANG_RU[lang].capitalize() for lang in langs])
        ax.set_ylim(0, 1.1)
        ax.yaxis.set_major_formatter(PERCENT)
        ax.grid(axis="x", visible=False)
        ax.set_title("Сюжет: нужный фильм в первых 10" if key == "plot_hit"
                     else "Жанр: доля нужного жанра в первых 10")
    axes[0].set_ylabel("Доля запросов")
    axes[1].set_ylabel("Доля фильмов")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=3)
    save(fig, 19, "Поиск словами на трёх языках")


FINAL_RU = {
    "hybrid_popular_year_als_f64_r0.1_a1_w0.4": "популярность × ALS (модель сайта)",
    "hybrid_popular_year_vae_z400_b0.5_w0.2": "популярность × Mult-VAE",
    "vae_z400_b0.5": "Mult-VAE",
    "user_knn_k200": "user-kNN",
    "ease_l5000": "EASE",
    "als_f64_r0.1_a1": "ALS",
    "item_knn_cosine_k200_binary": "item-kNN",
    "popular_year": "популярные за последний год",
    "content_tfidf_meta_centered": "контент (TF-IDF)",
    "svd_f64_r0.03": "SVD",
}


def fig_validation_test() -> None:
    """Итоговый набор: балл на валидации (по ней выбирали) и на тесте (один прогон) для каждой модели."""
    test, val = {}, {}
    for run in ("final", "final_gpu", "final_ease"):
        test |= load(run, "test")["score"]
    for run in ("ease", "vae", "hybrid_vae", "final"):
        val |= load(run)["score"]
    names = sorted(FINAL_RU, key=lambda n: test[n])
    y = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(10, 5.6), layout="constrained")
    for i, n in enumerate(names):
        ax.plot([val[n], test[n]], [i, i], color=MUTED, linewidth=2, zorder=1)
    ax.scatter([val[n] for n in names], y, s=60, color=BLUE, label="валидация (выбор модели)", zorder=2,
               edgecolor="white", linewidth=1)
    ax.scatter([test[n] for n in names], y, s=60, color=ORANGE, label="тест (один прогон)", zorder=3,
               edgecolor="white", linewidth=1)
    for i, n in enumerate(names):
        right = max(val[n], test[n])
        ax.text(right + 0.006, i, num(test[n], 3), va="center", fontsize=10, color=INK2)
    ax.set_yticks(y, [FINAL_RU[n] for n in names])
    ax.set_xlim(0, max(max(test.values()), max(val[n] for n in names)) * 1.12)
    ax.xaxis.set_major_formatter(COMMA)
    ax.set_xlabel("NDCG@10, среднее по трём сценариям (подпись – тест)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    save(fig, 21, "Модели на валидации и на итоговом тесте")


def main() -> None:
    fig_baselines()
    fig_step4_best()
    fig_accuracy_coverage()
    fig_content()
    if (REPORTS / "final_ease" / "test.json").exists():
        fig_validation_test()
    if (REPORTS / "search" / "validation.json").exists():
        fig_search()


if __name__ == "__main__":
    main()
