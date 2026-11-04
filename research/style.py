"""Общее оформление рисунков для отчёта: шрифт, палитра, оси, сохранение «Рисунок N – Название.png».
Используется рисунками исследования (research/figures.py) и моделей (model/)."""
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

OUT = Path(os.environ.get("FIGURES", "/figures"))

# шрифт отчёта – Times New Roman из Windows (папка Fonts подключена только для чтения)
for name in ("times.ttf", "timesbd.ttf", "timesi.ttf"):
    path = Path("/winfonts") / name
    if path.exists():
        font_manager.fontManager.addfont(str(path))

# палитра (проверена validate_palette.js скилла dataviz): категориальные цвета строго по порядку,
# чернила и сетка – нейтральные
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
CATEGORICAL = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED]
BLUE_LIGHT = "#9ec5f4"
INK, INK2, MUTED, GRID, AXIS, WASH = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#f0efec"
# величина – один оттенок от светлого к тёмному; знак (корреляции) – синий и красный с серой серединой
SEQUENTIAL = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#104281",
                                                        "#0d366b"])
DIVERGING = LinearSegmentedColormap.from_list("blue_red", ["#104281", "#3987e5", "#9ec5f4", WASH, "#f2a3a2",
                                                           RED, "#a32b2b"])

plt.rcParams.update({
    "font.family": "Times New Roman", "font.size": 12, "axes.titlesize": 13, "axes.labelsize": 12,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.8, "axes.axisbelow": True, "legend.frameon": True, "legend.framealpha": 0.95,
    "legend.edgecolor": GRID, "lines.linewidth": 2, "savefig.dpi": 200, "savefig.bbox": "tight",
    "axes.formatter.use_locale": False,
})


MINUS = "−"  # типографский знак минуса вместо дефиса


def num(value: float, digits: int = 2) -> str:
    """Число с десятичной запятой и знаком минуса: 3,54; −0,12."""
    return f"{value:.{digits}f}".replace(".", ",").replace("-", MINUS)


def thousands(value: float) -> str:
    """Целое с пробелом между разрядами: 32 000 204."""
    return f"{int(round(value)):,}".replace(",", " ")


def percent(value: float, digits: int = 0) -> str:
    return f"{value * 100:.{digits}f}".replace(".", ",") + " %"


COMMA = FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",").replace("-", MINUS))
THOUSANDS = FuncFormatter(lambda v, _: thousands(v))
PERCENT = FuncFormatter(lambda v, _: f"{v * 100:g}".replace(".", ",") + " %")


def save(fig, n: int, title: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"Рисунок {n} – {title}.png", facecolor="white")
    plt.close(fig)
    print("saved", n, title)
