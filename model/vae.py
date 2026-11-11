"""Mult-VAE (Liang et al., 2018) – вариационный автокодировщик с мультиномиальным правдоподобием.

Вход – набор оценённых человеком фильмов-кандидатов (1 за оценку, вектор нормируется), кодировщик сжимает его
в распределение «вкуса» из latent чисел, декодировщик возвращает баллы всем кандидатам. Потеря – минус
логарифм softmax по оценённым фильмам плюс β · KL; β растёт от 0 до верхней границы за первые эпохи (KL
annealing), на входе при обучении – dropout 0,5 (модель учится восстанавливать пропущенное).

Новый человек не требует переобучения: его 5–10 оценок подаются на вход, советы – выход декодировщика
(без случайности: берётся среднее распределения). Обучается в Colab на GPU (notebooks/vae.ipynb), без GPU
тот же код работает на процессоре – так он проверяется тестами на маленьких данных."""
import time

import numpy as np
import pandas as pd

from baselines import Recommender
from knn import input_weights, interactions

BATCH = 500


def _net(n_items: int, hidden: int, latent: int):
    import torch
    from torch import nn

    class MultVAE(nn.Module):
        def __init__(self):
            super().__init__()
            self.encoder = nn.Sequential(nn.Linear(n_items, hidden), nn.Tanh(), nn.Linear(hidden, 2 * latent))
            self.decoder = nn.Sequential(nn.Linear(latent, hidden), nn.Tanh(), nn.Linear(hidden, n_items))
            self.drop = nn.Dropout(0.5)

        def forward(self, x):
            x = self.drop(nn.functional.normalize(x, dim=1))
            mu, logvar = self.encoder(x).chunk(2, dim=1)
            z = mu + torch.randn_like(mu) * torch.exp(0.5 * logvar) if self.training else mu
            return self.decoder(z), mu, logvar

    return MultVAE()


class MultVAE(Recommender):
    def __init__(self, latent: int = 200, beta: float = 0.2, hidden: int = 600, epochs: int = 40,
                 anneal_epochs: int = 20, lr: float = 1e-3, seed: int = 0):
        self.latent, self.beta, self.hidden, self.epochs = latent, beta, hidden, epochs
        self.anneal_epochs, self.lr, self.seed = anneal_epochs, lr, seed
        self.name = f"vae_z{latent}_b{beta:g}"

    def fit(self, history, pool):
        import torch

        super().fit(history, pool)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        torch.manual_seed(self.seed)
        rng = np.random.default_rng(self.seed)
        matrix = interactions(history, pool)[0]
        self.net = _net(len(pool), self.hidden, self.latent).to(self.device)
        optimizer = torch.optim.Adam(self.net.parameters(), lr=self.lr)
        steps_per_epoch = -(-matrix.shape[0] // BATCH)
        anneal_steps, step = max(self.anneal_epochs * steps_per_epoch, 1), 0
        self.losses = []
        for epoch in range(self.epochs):
            tic, total = time.time(), 0.0
            self.net.train()
            order = rng.permutation(matrix.shape[0])  # люди в новом порядке каждую эпоху
            for start in range(0, matrix.shape[0], BATCH):
                rows = order[start: start + BATCH]
                x = torch.from_numpy(matrix[rows].toarray().astype(np.float32)).to(self.device)
                logits, mu, logvar = self.net(x)
                nll = -(torch.log_softmax(logits, dim=1) * x).sum(dim=1).mean()
                kl = (-0.5 * (1 + logvar - mu ** 2 - logvar.exp()).sum(dim=1)).mean()
                beta = self.beta * min(step / anneal_steps, 1.0)
                loss = nll + beta * kl
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total += float(loss.detach()) * len(rows)
                step += 1
            self.losses.append(round(total / matrix.shape[0], 3))
            if epoch == 0 or (epoch + 1) % 10 == 0:
                print(f"{self.name}: эпоха {epoch + 1}/{self.epochs}, потеря {self.losses[-1]}, "
                      f"{time.time() - tic:.1f} с", flush=True)
        self.net.eval()
        return self

    def scores(self, inputs: pd.DataFrame, user=None) -> np.ndarray:
        import torch

        index, _ = input_weights(inputs, self.position, "binary")
        x = torch.zeros((1, len(self.pool)), device=self.device)
        if len(index):
            x[0, torch.from_numpy(np.array(index)).to(self.device)] = 1.0
        with torch.no_grad():
            return self.net(x)[0][0].cpu().numpy()

    def release(self) -> None:
        """После проверки сеть освобождает память GPU – в памяти всегда одна."""
        import torch

        del self.net
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def vae_grid() -> list[MultVAE]:
    return [MultVAE(latent, beta) for latent in (200, 400) for beta in (0.2, 0.5)]
