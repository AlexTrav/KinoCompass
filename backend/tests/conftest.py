"""Маленькая искусственная выгрузка в формате model/export: 8 фильмов, ответ виден заранее.

1–3 – фантастика про космос (1999), 4–6 – мелодрамы (2005), 7 – фантастика и 8 – мелодрама 2023 года (новинки).
Популярность убывает с номером. Векторы ALS, TF-IDF и e5 – две оси «космос» и «любовь»; модель запросов e5
заменена простым кодировщиком: «space»/«космос» в запросе – ось космоса, иначе – ось любви."""
import gzip
import json
import sqlite3

import numpy as np
import pytest
import scipy.sparse as sp
from fastapi.testclient import TestClient

from app.main import app
from app.store import Store

SPACE, LOVE = np.array([1.0, 0.0]), np.array([0.0, 1.0])
KIND = {1: SPACE, 2: SPACE, 3: SPACE, 4: LOVE, 5: LOVE, 6: LOVE, 7: SPACE, 8: LOVE}


def film(m: int) -> dict:
    space = KIND[m] is SPACE
    return {"id": m, "title": f"Film {m}", "title_ru": "" if m == 6 else f"Фильм {m}",
            "title_kk": "Ғарыш" if m == 3 else "", "title_en": f"Film {m}",
            "year": 2023 if m >= 7 else (1999 if space else 2005),
            "genres": ["Sci-Fi"] if space else ["Romance", "Drama"], "poster": "" if m == 5 else f"/p{m}.jpg",
            "n_ratings": 1000 - m * 100, "mean_rating": 3.5, "imdb_id": f"tt{m:07d}", "tmdb_id": m}


def write_export(path) -> None:
    ids = list(KIND)
    with gzip.open(path / "catalog.json.gz", "wt", encoding="utf-8") as f:
        json.dump([film(m) for m in ids], f, ensure_ascii=False)
    np.save(path / "popularity.npy", np.arange(len(ids), 0, -1).astype(np.float32))
    rng = np.random.default_rng(0)
    items = np.array([KIND[m] + 0.05 * rng.standard_normal(2) for m in ids], dtype=np.float32)
    np.save(path / "als_items.npy", items)
    np.save(path / "als_gram.npy", items.astype(np.float64).T @ items.astype(np.float64))
    sp.save_npz(path / "tfidf.npz", sp.csr_matrix(np.array([KIND[m] for m in ids], dtype=np.float32)))
    np.save(path / "e5_enru.npy", np.array([KIND[m] for m in ids], dtype=np.float16))
    np.save(path / "e5_ids.npy", np.array(ids, dtype=np.int32))
    xy = np.array([[-0.9, 0.1], [-0.8, 0.0], [-0.7, 0.2], [0.8, 0.0], [0.9, -0.1], [0.7, 0.1]], dtype=np.float32)
    np.savez_compressed(path / "map.npz", ids=np.arange(1, 7, dtype=np.int32), xy=xy)
    with sqlite3.connect(path / "overviews.db") as db:
        db.execute("CREATE TABLE overviews (id INTEGER PRIMARY KEY, en TEXT NOT NULL, ru TEXT NOT NULL)")
        db.executemany("INSERT INTO overviews VALUES (?, ?, ?)",
                       [(m, f"Plot {m}", "" if m == 2 else f"Сюжет {m}") for m in ids])
    manifest = {"data_until": "2023-10-13", "site_model": {"als": {"regularization": 0.1, "alpha": 1.0}},
                "new_items": {"rule": "год выпуска ≥ 2022", "count": 2, "ids": [7, 8]}, "files": {}}
    (path / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


def fake_encoder(text: str) -> np.ndarray:
    return SPACE.copy() if any(w in text.lower() for w in ("space", "космос")) else LOVE.copy()


@pytest.fixture(scope="session")
def store(tmp_path_factory) -> Store:
    path = tmp_path_factory.mktemp("export")
    write_export(path)
    return Store(path, encoder=fake_encoder)


@pytest.fixture
def client(store):
    app.state.store = store
    with TestClient(app) as c:
        yield c
