"""EASE (Steck, 2019) – линейная модель «фильм × фильм» с решением в одну формулу:
    P = (XᵀX + λI)⁻¹,   B = I − P · diag(1 / diag P),   балл кандидатов = x · B,
где X – матрица «люди × фильмы-кандидаты» (1 за оценку), x – вход человека. Диагональ B нулевая: фильм не
объясняет сам себя. Новый человек не требует пересчёта – его вход просто умножается на B.

На всех ~21 тыс. кандидатах B весит около 2 ГБ, поэтому EASE обучается в Google Colab на GPU
(notebooks/ease.ipynb): XᵀX набирается блоками людей на GPU, обращение – на GPU в двойной точности, B остаётся
на GPU, и баллы человеку считаются там же (на процессоре Colab постоянный с 300 оценками – 0,3 с). Без GPU
тот же код работает на numpy (так он проверяется тестами на маленьких данных). На сайт EASE не идёт –
модель для сравнения."""
import numpy as np
import pandas as pd

from baselines import Recommender
from knn import input_weights, interactions

BLOCK = 20_000  # людей в одном блоке при наборе XᵀX на GPU (плотный блок около 1,7 ГБ)
_gram: dict[tuple, np.ndarray] = {}  # XᵀX одна на всю сетку λ (float32, около 1,8 ГБ)


def device() -> str | None:
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else None
    except ImportError:
        return None


def gram(matrix, dev: str | None) -> np.ndarray:
    """XᵀX (float32) для разреженной X: на GPU – плотными блоками людей, иначе – разреженно на CPU."""
    if dev is None:
        return (matrix.T @ matrix).toarray().astype(np.float32)
    import torch

    n = matrix.shape[1]
    total = torch.zeros((n, n), dtype=torch.float32, device=dev)
    for start in range(0, matrix.shape[0], BLOCK):
        block = torch.from_numpy(matrix[start: start + BLOCK].toarray()).to(dev)
        total += block.T @ block
        del block
    out = total.cpu().numpy()
    del total
    torch.cuda.empty_cache()
    return out


def solve(g: np.ndarray, lam: float, dev: str | None):
    """B = I − P · diag(1 / diag P) при P = (G + λI)⁻¹ – в float64; на GPU всё на месте, без лишних копий,
    и B (float32) остаётся на GPU."""
    if dev is None:
        p = np.linalg.inv(g.astype(np.float64) + lam * np.eye(len(g)))
        b = -p / np.diag(p)[None, :]
        b[np.diag_indices_from(b)] = 0
        return b.astype(np.float32)
    import torch

    gg = torch.from_numpy(g).to(dev, dtype=torch.float64)
    gg.diagonal().add_(lam)
    p = torch.linalg.inv(gg)
    del gg
    p.div_(-torch.diagonal(p).clone()[None, :])
    p.fill_diagonal_(0)
    out = p.float()
    del p
    torch.cuda.empty_cache()
    return out


class EASE(Recommender):
    def __init__(self, lam: float = 500.0):
        self.lam = lam
        self.name = f"ease_l{lam:g}"

    def fit(self, history, pool):
        super().fit(history, pool)
        dev = device()
        key = (id(history), len(history), len(pool))
        if key not in _gram:
            _gram.clear()
            _gram[key] = gram(interactions(history, pool)[0], dev)
        self.b = solve(_gram[key], self.lam, dev)
        return self

    def scores(self, inputs: pd.DataFrame, user=None) -> np.ndarray:
        index, weights = input_weights(inputs, self.position, "binary")
        if not len(index):
            return np.zeros(len(self.pool))
        if isinstance(self.b, np.ndarray):
            return weights @ self.b[index]
        import torch

        rows = self.b[torch.from_numpy(index).to(self.b.device)]
        return (torch.from_numpy(weights.astype(np.float32)).to(self.b.device) @ rows).cpu().numpy()

    def release(self) -> None:
        """После проверки матрица B (2 ГБ) освобождается – в памяти всегда одна."""
        del self.b
        if device():
            import torch

            torch.cuda.empty_cache()


def ease_grid() -> list[EASE]:
    # первая сетка (200, 1000, 5000) дала лучший λ на краю – расширена вправо
    return [EASE(lam) for lam in (200.0, 1000.0, 5000.0, 20000.0, 50000.0)]
