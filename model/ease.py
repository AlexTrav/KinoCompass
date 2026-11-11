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
COLS = 2048  # столбцов обратной матрицы в одной полосе на GPU (полоса float64 – около 0,37 ГБ)


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


def solve(g: np.ndarray, lam: float, dev: str | None, cols: int = COLS):
    """B = I − P · diag(1 / diag P) при P = (G + λI)⁻¹ – в float64; B (float32) остаётся на устройстве.

    На GPU полная P (float64) в памяти не держится: G + λI симметрична и положительно определена, после
    разложения Холецкого P считается полосами по cols столбцов, и каждая полоса сразу становится своим куском B.
    Пик на 22 309 кандидатах теста: разложение 4 ГБ + B 2 ГБ + полоса около 1,3 ГБ. Прежние способы
    (linalg.inv, cholesky_inverse) держали ещё одну-две матрицы по 4 ГБ и не помещались в 15 ГБ T4."""
    if dev is None:
        p = np.linalg.inv(g.astype(np.float64) + lam * np.eye(len(g)))
        b = -p / np.diag(p)[None, :]
        b[np.diag_indices_from(b)] = 0
        return b.astype(np.float32)
    import torch

    n = len(g)
    gg = torch.from_numpy(g).to(dev, dtype=torch.float64)
    gg.diagonal().add_(lam)
    low = torch.linalg.cholesky(gg)
    del gg
    torch.cuda.empty_cache()
    out = torch.empty((n, n), dtype=torch.float32, device=dev)
    for start in range(0, n, cols):
        width = min(cols, n - start)
        diag = torch.arange(width, device=dev)
        eye = torch.zeros((n, width), dtype=torch.float64, device=dev)
        eye[start + diag, diag] = 1.0
        p = torch.cholesky_solve(eye, low)  # столбцы start … start + width матрицы P
        del eye
        out[:, start: start + width] = (p / -p[start + diag, diag][None, :]).float()
        out[start + diag, start + diag] = 0.0
        del p
    del low
    torch.cuda.empty_cache()
    return out


def solve_cpu(a: np.ndarray, lam: float, cols: int = 1024) -> np.ndarray:
    """То же B на процессоре без лишних копий в оперативной памяти. a – XᵀX в float64, которой владеет только эта
    функция: G + λI раскладывается по Холецкому прямо в ней (scipy), P считается полосами по cols столбцов, и
    каждая полоса сразу становится своим куском B (float32). Пик на 22 309 кандидатах: разложение 4 ГБ + B 2 ГБ
    + полоса около 0,5 ГБ (замер на 8 000 кандидатах: 1,05 ГБ сверх входа при полосе 2048)."""
    from scipy.linalg import cho_factor, cho_solve

    n = len(a)
    a[np.diag_indices(n)] += lam
    factor = cho_factor(a, lower=True, overwrite_a=True, check_finite=False)
    out = np.empty((n, n), dtype=np.float32)
    for start in range(0, n, cols):
        width = min(cols, n - start)
        diag = np.arange(width)
        eye = np.zeros((n, width))
        eye[start + diag, diag] = 1.0
        p = cho_solve(factor, eye, overwrite_b=True, check_finite=False)  # столбцы полосы матрицы P
        out[:, start: start + width] = p / -p[start + diag, diag][None, :]
        out[start + diag, start + diag] = 0.0
        del eye, p
    return out


class EASE(Recommender):
    def __init__(self, lam: float = 500.0, solve_on: str = "auto"):
        """solve_on="cpu" – обращение матрицы на процессоре (итоговый тест: на T4 не хватило видеопамяти);
        баллы людям всё равно считаются на GPU, если он есть."""
        self.lam, self.solve_on = lam, solve_on
        self.name = f"ease_l{lam:g}"

    def fit(self, history, pool):
        super().fit(history, pool)
        dev = device()
        key = (id(history), len(history), len(pool))
        if key not in _gram:
            _gram.clear()
            _gram[key] = gram(interactions(history, pool)[0], dev)
        if self.solve_on == "cpu":
            # XᵀX (float32) сразу переводится в float64 и освобождается – в памяти не лежат обе (2 + 4 ГБ)
            self.b = solve_cpu(_gram.pop(key).astype(np.float64), self.lam)
            if dev:
                import torch

                self.b = torch.from_numpy(self.b).to(dev)  # советы – на GPU, иначе проверка идёт 1,5 часа
        else:
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
