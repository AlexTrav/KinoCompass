import os
import threading
from concurrent.futures import ThreadPoolExecutor
from itertools import chain

import pandas as pd
import requests

from .config import POSTERS_COLUMNS, SAVE_EVERY, TMDB_URL, TMDB_WORKERS
from .net import request
from .store import load, save

_local = threading.local()


def _session() -> requests.Session:
    if not hasattr(_local, "session"):
        _local.session = requests.Session()  # своё соединение у каждого потока – keep-alive без гонок
    return _local.session


# ключ – «Ключ доступа к API» TMDb (v4, Bearer) из переменной окружения; в код, логи и вывод он не попадает
def auth_headers() -> dict:
    token = os.environ.get("TMDB_TOKEN", "").strip()
    if not token:
        raise SystemExit("нет переменной окружения TMDB_TOKEN (KinoCompass/.env – «Ключ доступа к API» TMDb)")
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


# путь к постеру фильма (/abc.jpg) или пустая строка: постера нет или фильм удалён из TMDb (404)
def poster_path(tmdb_id: int, headers: dict) -> str:
    resp = request("GET", TMDB_URL.format(tmdb_id), session=_session(), headers=headers,
                   params={"language": "en-US"}, allow_404=True)
    return "" if resp is None else resp.json().get("poster_path") or ""


# один фильм: (movie_id, tmdb_id, путь) или ошибка; неверный ключ (401) останавливает всю загрузку
def _one(row: tuple[int, int], headers: dict, get) -> tuple[int, int, str] | Exception:
    movie_id, tmdb_id = row
    try:
        return movie_id, tmdb_id, get(tmdb_id, headers)
    except requests.HTTPError as error:
        if error.response is not None and error.response.status_code == 401:
            raise SystemExit("TMDb отклонил ключ (401) – проверь TMDB_TOKEN в KinoCompass/.env") from None
        return error
    except requests.RequestException as error:
        return error


# постеры для фильмов каталога с tmdb_id, которых ещё нет в catalog/posters.csv (refresh – все заново).
# Фильмы с ошибкой запроса не записываются – их подхватит следующий запуск
def update_posters(catalog: pd.DataFrame, path, refresh: bool = False, get=poster_path) -> tuple[pd.DataFrame, int]:
    headers = auth_headers()
    posters = pd.DataFrame(columns=POSTERS_COLUMNS) if refresh else load(path, POSTERS_COLUMNS)
    todo = catalog[~catalog["movie_id"].isin(posters["movie_id"]) & catalog["tmdb_id"].notna()]
    rows = list(zip(todo["movie_id"].astype(int), todo["tmdb_id"].astype(int)))
    print(f"  нужно постеров: {len(rows)}", flush=True)
    found, errors = [], 0
    # первый фильм – отдельно: при неверном ключе остановиться сразу, а не после тысяч отказов в очереди потоков
    first = [_one(rows[0], headers, get)] if rows else []
    with ThreadPoolExecutor(TMDB_WORKERS) as pool:
        rest = pool.map(lambda row: _one(row, headers, get), rows[1:])
        for i, result in enumerate(chain(first, rest), start=1):
            if isinstance(result, Exception):
                errors += 1
            else:
                found.append(result)
            if i % SAVE_EVERY == 0 or i == len(rows):
                fresh = pd.DataFrame(found, columns=POSTERS_COLUMNS).astype(str)
                posters = save(pd.concat([posters, fresh], ignore_index=True), path, catalog)
                found = []
                print(f"  {i} из {len(rows)}, ошибок: {errors}", flush=True)
    return save(posters, path, catalog), errors
