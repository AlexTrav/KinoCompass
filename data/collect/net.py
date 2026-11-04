import random
import time

import requests

from .config import BACKOFF_SEC, RETRIES, TIMEOUT_SEC, USER_AGENT


def backoff(attempt: int) -> float:
    """Пауза перед повтором attempt (1, 2, …): 2, 4, 8, 16 с и ±20 % случайно – чтобы параллельные
    запросы не повторялись одновременно."""
    return BACKOFF_SEC * 2 ** (attempt - 1) * random.uniform(0.8, 1.2)


# HTTP-запрос с повтором при обрыве соединения, таймауте или ответе 5xx/429 (для 429 – пауза из Retry-After,
# если сервер её назвал); ошибки запроса (4xx) не повторяются. С allow_404 ответ 404 – не ошибка, а None
# (у TMDb так отвечают удалённые фильмы)
def request(method: str, url: str, *, session: requests.Session | None = None, allow_404: bool = False,
            headers: dict | None = None, **kwargs) -> requests.Response | None:
    http = session or requests
    headers = {"User-Agent": USER_AGENT, **(headers or {})}
    for attempt in range(1, RETRIES + 1):
        wait = backoff(attempt)
        try:
            resp = http.request(method, url, headers=headers, timeout=TIMEOUT_SEC, **kwargs)
        except (requests.ConnectionError, requests.Timeout):
            if attempt == RETRIES:
                raise
        else:
            if resp.status_code == 404 and allow_404:
                return None
            if (resp.status_code < 500 and resp.status_code != 429) or attempt == RETRIES:
                resp.raise_for_status()
                return resp
            if resp.status_code == 429 and resp.headers.get("Retry-After", "").isdigit():
                wait = max(wait, float(resp.headers["Retry-After"]))
        time.sleep(wait)
    raise RuntimeError("unreachable")
