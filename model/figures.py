"""Рисунки моделей для отчёта – только по сохранённым отчётам reports/ (набор не нужен):
    make -C model figures FIGURES=/путь/к/папке
Нумерация продолжает рисунки исследования (research/figures.py – 1–15)."""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from style import BLUE, COMMA, INK2, num, save, thousands

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


def main() -> None:
    fig_baselines()


if __name__ == "__main__":
    main()
