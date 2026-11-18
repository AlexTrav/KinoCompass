"""API KinoCompass: советы фильмов по нескольким оценкам, новинки, карточка фильма, поиск словами, сравнение
моделей, карта вкусов и сводка производительности. Базы нет: оценки человека приходят в каждом запросе
(хранятся только в его браузере), модель – выгрузка model/export в памяти (store.py).

    uvicorn app.main:app   # локально: make -C backend run
"""
import os
import resource
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from functools import cache
from typing import Literal

import anyio
import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field
from starlette.routing import Match

import site_core as core

from .store import Store

Lang = Literal["ru", "kk", "en"]
THREADS = 4  # одновременных расчётов: на 512 МБ каждый держит временные массивы по каталогу (≈ 0,2–40 МБ)
STARTED = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    anyio.to_thread.current_default_thread_limiter().total_tokens = THREADS
    if getattr(app.state, "store", None) is None:  # тесты подкладывают свою маленькую выгрузку
        app.state.store = Store()
    yield


app = FastAPI(title="KinoCompass API", version="1.0", lifespan=lifespan,
              description="Рекомендации фильмов (MovieLens 32M): «популярность × ALS», новинки по описанию, "
                          "поиск словами (e5), сравнение моделей, карта вкусов")
# уровень 6 вместо 9: карта (0,4 МБ) сжимается втрое быстрее при почти том же размере
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)
app.add_middleware(CORSMiddleware,
                   allow_origins=os.environ.get("CORS_ORIGINS", "https://alextrav.github.io,http://localhost:5173")
                   .split(","), allow_methods=["GET", "POST"], expose_headers=["Server-Timing"])


def store(request: Request) -> Store:
    return request.app.state.store


# ---------- производительность: время ответа каждой точки API (последние SAMPLES запросов) ----------
SAMPLES = 500
timings: dict[str, deque] = defaultdict(lambda: deque(maxlen=SAMPLES))
counts: dict[str, int] = defaultdict(int)


def route_path(scope: dict) -> str | None:
    """Шаблон пути точки API (/api/film/{movie_id}), чтобы все фильмы шли в одну строку сводки; чужие адреса –
    None, чтобы случайные запросы не раздували сводку."""
    for route in api_routes():
        if route.matches(scope)[0] == Match.FULL:
            return route.path
    return None


@cache
def api_routes() -> tuple:
    return tuple(r for r in app.routes if getattr(r, "path", "").startswith("/api/"))


@app.middleware("http")
async def timing(request: Request, call_next):
    began = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - began) * 1000
    response.headers["Server-Timing"] = f"app;dur={ms:.1f}"
    path = route_path(request.scope)
    if path is not None and response.status_code < 400:
        timings[path].append(ms)
        counts[path] += 1
    return response


def memory_mb() -> dict:
    """Память процесса: сейчас (VmRSS) и пик (VmHWM) – лимит бесплатного Render 512 МБ."""
    out = {}
    try:
        for line in open("/proc/self/status", encoding="ascii"):
            key, _, value = line.partition(":")
            if key in ("VmRSS", "VmHWM"):
                out["now" if key == "VmRSS" else "peak"] = round(int(value.split()[0]) / 1024)
    except OSError:
        out["peak"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
    return out


# ---------- запросы ----------
class Rated(BaseModel):
    id: int
    rating: float = Field(ge=0.5, le=5)


class Profile(BaseModel):
    ratings: list[Rated] = Field(min_length=1, max_length=500)
    lang: Lang = "ru"
    k: int = Field(10, ge=1, le=50)


class RecommendIn(Profile):
    popularity_weight: float = Field(core.SITE_WEIGHT, ge=0, le=1,
                                     description="вес популярности (ползунок новизны): 0,4 – как на тесте, 0 – только вкус")


def known(s: Store, profile: Profile) -> tuple[np.ndarray, np.ndarray, list[int]]:
    index, values, unknown = s.rows_of({r.id: r.rating for r in profile.ratings})  # повтор id – последняя оценка
    if not len(index):
        raise HTTPException(422, "ни одного оценённого фильма нет в каталоге")
    return index, values, unknown


# ---------- точки API ----------
@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.get("/api/health")
def health(request: Request) -> dict:
    """Жив ли сервер, дата данных и размер каталога."""
    s = store(request)
    return {"status": "ok", "data_until": s.manifest["data_until"], "catalog": len(s.catalog),
            "new_items": len(s.new_rows), "map_films": len(s.map_rows)}


@app.get("/api/films")
def films(request: Request, q: str = Query("", max_length=100), lang: Lang = "ru",
          k: int = Query(20, ge=1, le=50)) -> dict:
    """Подсказки по названию (на любом из трёх языков); пустой запрос – популярное за последний год."""
    return {"items": store(request).suggest(q, k, lang)}


@app.post("/api/recommend")
def recommend(request: Request, body: RecommendIn) -> dict:
    """10 советов модели сайта «популярность × ALS»; оценённые фильмы не советуются."""
    s = store(request)
    index, _, unknown = known(s, body)
    return {"items": s.top(s.site(index, body.popularity_weight), body.k, body.lang, skip=index),
            "popularity_weight": body.popularity_weight, "tested_weight": core.SITE_WEIGHT, "unknown": unknown}


@app.post("/api/new")
def new(request: Request, body: Profile) -> dict:
    """Новинки (фильмы последних двух лет выпуска в каталоге) по сходству описаний с оценёнными фильмами."""
    s = store(request)
    index, values, unknown = known(s, body)
    return {"items": s.new_items(index, values, body.k, body.lang), "rule": s.manifest["new_items"]["rule"],
            "unknown": unknown}


@app.get("/api/film/{movie_id}")
def film(request: Request, movie_id: int, lang: Lang = "ru", k: int = Query(10, ge=1, le=50)) -> dict:
    """Карточка фильма: описание сюжета, ссылки и «с этим фильмом смотрят» (модель сайта по одному фильму)."""
    s = store(request)
    if movie_id not in s.row:
        raise HTTPException(404, "фильма нет в каталоге")
    i = s.row[movie_id]
    c = s.catalog[i]
    return {**s.card(i, lang), "titles": {l: s.title(i, l) for l in ("ru", "kk", "en")},
            "overview": s.overview(i, lang), "imdb_id": c["imdb_id"], "tmdb_id": c["tmdb_id"],
            "similar": s.similar(i, k, lang)}


@app.get("/api/search")
def search(request: Request, q: str = Query(min_length=1, max_length=200), lang: Lang = "ru",
           k: int = Query(10, ge=1, le=50)) -> dict:
    """Поиск словами по смыслу (e5, три языка); совпадение с названием целиком – первым."""
    if not q.strip():
        raise HTTPException(422, "пустой запрос")
    return store(request).search(q.strip(), k, lang)


@app.post("/api/compare")
def compare(request: Request, body: Profile) -> dict:
    """Советы четырёх моделей на одних и тех же оценках и время расчёта каждой (мс)."""
    s = store(request)
    index, values, unknown = known(s, body)
    models = {"popular": lambda: s.popularity, "als": lambda: s.site(index, 0.0),
              "content": lambda: s.content(index, values), "hybrid": lambda: s.site(index)}
    out = {}
    for name, score in models.items():
        began = time.perf_counter()
        items = s.top(score(), body.k, body.lang, skip=index)
        out[name] = {"items": items, "ms": round((time.perf_counter() - began) * 1000, 1)}
    return {"models": out, "unknown": unknown}


@app.get("/api/map")
def taste_map(request: Request, lang: Lang = "ru") -> Response:
    """Карта вкусов: самые оценённые фильмы на плоскости (t-SNE по векторам ALS), координаты в [−1, 1]."""
    return Response(store(request).taste_map(lang), media_type="application/json")


@app.post("/api/map/me")
def map_me(request: Request, body: Profile) -> dict:
    """Точка человека на карте – центр его фильмов с весом «насколько понравился»."""
    s = store(request)
    index, values, unknown = known(s, body)
    return {**s.map_me(index, values), "unknown": unknown}


@app.get("/api/perf")
def perf(request: Request) -> dict:
    """Время ответа каждой точки API (медиана и 95-й процентиль по последним запросам), память и запуск."""
    stats = {path: {"count": counts[path], "p50_ms": round(float(np.percentile(t, 50)), 1),
                    "p95_ms": round(float(np.percentile(t, 95)), 1)}
             for path, t in sorted(timings.items()) if t}
    return {"endpoints": stats, "memory_mb": memory_mb(), "load_seconds": round(store(request).load_seconds, 2),
            "uptime_seconds": round(time.time() - STARTED), "limit_mb": 512}
