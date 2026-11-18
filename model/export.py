"""Выгрузка моделей для сайта (шаг 6д): python export.py -> model/export/ (в git не идёт; manifest.json – идёт).

Модели, выбранные на валидации и подтверждённые тестом, переобучаются на ВСЕХ данных набора (до 12.10.2023),
кандидаты – фильмы каталога сайта (минимум 20 оценок). Сайту не нужны ни implicit, ни scikit-learn:
- подбор – смесь «популярность × ALS» с весом 0,4 по рангам: популярность за последний год и векторы фильмов
  ALS, вектор нового человека считается по его оценкам одним решением системы (fold_in, numpy);
- новинки – фильмы каталога последних двух лет выпуска, по сходству описаний (TF-IDF) с профилем человека;
- каталог – названия ru/kk/en, год, жанры, постер, описания одним файлом.
Векторы e5 для поиска и модель запросов – отдельно (Colab и ONNX)."""
import gzip
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

import baselines
import content
import factorization
from collect.config import CATALOG_DIR
from protocol import _seconds
from site_core import SITE_WEIGHT, encode_query

OUT = Path(__file__).resolve().parent / "export"
NEW_YEARS = 2  # новинки – фильмы последних NEW_YEARS лет выпуска в каталоге


def load_all() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Все оценки и все теги набора – сайт учится на всём, что есть."""
    from collect.movielens import fetch

    frames, _ = fetch()
    r = frames.pop("ratings")
    ratings = pd.DataFrame({"user_id": r["user_id"].to_numpy(np.int32), "movie_id": r["movie_id"].to_numpy(np.int32),
                            "rating": r["rating"].to_numpy(np.float32), "time": _seconds(r["time"])})
    return ratings, frames["tags"][["user_id", "movie_id", "tag"]]


def catalog_records(side: pd.DataFrame, n_ratings: pd.Series) -> list[dict]:
    posters = pd.read_csv(CATALOG_DIR / "posters.csv", dtype=str, keep_default_na=False)
    poster = posters.astype({"movie_id": "int64"}).set_index("movie_id")["poster_path"]
    movies = pd.read_csv(CATALOG_DIR / "movies.csv", usecols=["movie_id", "mean_rating", "imdb_id", "tmdb_id"],
                         dtype={"tmdb_id": "Int64"}).set_index("movie_id")
    records = []
    for row in side.itertuples():
        records.append({
            "id": int(row.Index), "title": row.title, "title_ru": row.title_ru, "title_kk": row.title_kk,
            "title_en": row.title_en, "year": None if pd.isna(row.year) else int(row.year),
            "genres": [g for g in row.genres.split("|") if g], "poster": poster.get(row.Index, ""),
            "n_ratings": int(n_ratings.get(row.Index, 0)), "mean_rating": float(movies.at[row.Index, "mean_rating"]),
            "imdb_id": movies.at[row.Index, "imdb_id"],
            "tmdb_id": None if pd.isna(movies.at[row.Index, "tmdb_id"]) else int(movies.at[row.Index, "tmdb_id"]),
        })
    return records


def write_overviews(side: pd.DataFrame) -> None:
    """Описания сюжета – в SQLite (стандартная библиотека): сайт читает одно описание при открытии фильма, не
    держа 20 МБ текста в памяти (каталог JSON со всеми описаниями занимал в процессе 106 МБ)."""
    import sqlite3

    path = OUT / "overviews.db"
    path.unlink(missing_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE overviews (id INTEGER PRIMARY KEY, en TEXT NOT NULL, ru TEXT NOT NULL)")
        db.executemany("INSERT INTO overviews VALUES (?, ?, ?)",
                       [(int(i), en, ru) for i, en, ru in zip(side.index, side["overview_en"], side["overview_ru"])])
    sqlite3.connect(path).execute("VACUUM").connection.close()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_list() -> dict:
    """Размер и контрольная сумма каждого файла выгрузки (папки – по файлам внутри, через «/»)."""
    files = sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "manifest.json")
    return {p.relative_to(OUT).as_posix(): {"bytes": p.stat().st_size, "sha256": sha256(p)} for p in files}


def refresh_manifest() -> None:
    """python export.py manifest – после e5 из Colab и ONNX: пересчитать список файлов в manifest.json."""
    path = OUT / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"] = file_list()
    manifest["total_mb"] = round(sum(f["bytes"] for f in manifest["files"].values()) / 2**20, 1)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, info in manifest["files"].items():
        print(f"{name}: {info['bytes'] / 2**20:.1f} МБ")
    print(f"всего {manifest['total_mb']} МБ")


def main() -> None:
    started = time.time()
    ratings, tags = load_all()
    side = content.build_side(tags)
    titles = pd.read_csv(CATALOG_DIR / "titles.csv", dtype=str, keep_default_na=False)
    side = side.join(titles.astype({"movie_id": "int64"}).set_index("movie_id")["title_kk"]).fillna({"title_kk": ""})
    pool = side.index.to_numpy()  # каталог сайта по порядку id: строки всех матриц выгрузки
    OUT.mkdir(parents=True, exist_ok=True)

    popular = baselines.RecentPopularity().fit(ratings, pool)
    np.save(OUT / "popularity.npy", popular.static.astype(np.float32))

    als = factorization.ALS(64, 0.1, 1.0).fit(ratings, pool)
    items = np.asarray(als.model.item_factors, dtype=np.float32)
    np.save(OUT / "als_items.npy", items)
    np.save(OUT / "als_gram.npy", items.astype(np.float64).T @ items.astype(np.float64))

    text = content.TfidfContent(words=True, weighting="centered")
    text.attach(side)
    sp.save_npz(OUT / "tfidf.npz", text.vectors().astype(np.float32).tocsr())

    last_year = int(side["year"].max())
    new_ids = side.index[(side["year"] > last_year - NEW_YEARS).fillna(False)].to_numpy()
    n_ratings = ratings["movie_id"].value_counts()
    # каталог в памяти сайта – без описаний (они – основной объём); описания – в SQLite, по одному фильму
    with gzip.open(OUT / "catalog.json.gz", "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(catalog_records(side, n_ratings), f, ensure_ascii=False)
    write_overviews(side)

    manifest = {
        "data_until": str(pd.to_datetime(int(ratings["time"].max()), unit="s").date()), "ratings": len(ratings),
        "catalog": len(pool), "ids": "строки матриц – фильмы каталога по возрастанию id (catalog.json.gz)",
        "site_model": {"name": "популярность × ALS", "weight_popularity": SITE_WEIGHT,
                       "als": {"factors": 64, "regularization": 0.1, "alpha": 1.0}},
        "new_items": {"rule": f"год выпуска ≥ {last_year - NEW_YEARS + 1}", "count": int(len(new_ids)),
                      "ids": new_ids.tolist(), "model": "TF-IDF по жанрам, тегам и словам описания, вес centered"},
        "files": file_list(),
        "seconds": round(time.time() - started, 1),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, info in manifest["files"].items():
        print(f"{name}: {info['bytes'] / 2**20:.1f} МБ")
    print(f"каталог {len(pool)}, новинок {len(new_ids)}, за {manifest['seconds']} с")


def e5_vectors() -> None:
    """Colab на GPU (notebooks/export_e5.ipynb): векторы e5 для поиска по ВСЕМ тегам – среднее английского и
    русского текста, как лучший вариант проверки поиска (шаг 5в); float16, строки – каталог по id."""
    started = time.time()
    _, tags = load_all()
    side = content.build_side(tags)
    model = content.E5Content(("en", "ru"))
    model.attach(side)
    OUT.mkdir(parents=True, exist_ok=True)
    np.save(OUT / "e5_enru.npy", model.vectors().astype(np.float16))
    np.save(OUT / "e5_ids.npy", side.index.to_numpy(np.int32))
    print(f"векторы e5: {len(side)} фильмов за {time.time() - started:.0f} с")


QUERY_CHECK = ["игрушки оживают, когда хозяина нет дома", "ойыншықтар тірілетін мультфильм",
               "a hacker discovers reality is a simulation", "страшный фильм про призраков в доме",
               "romantic comedy in New York", "соғыс туралы фильм"]


def onnx_query_model() -> None:
    """Docker: модель запросов e5 для сайта – ONNX со сжатием весов до int8 (onnxruntime на сайте вместо torch).
    Внутри – среднее по токенам с маской и нормировка, как у sentence-transformers; проверка – косинус с исходной
    моделью на запросах на трёх языках."""
    import onnxruntime as ort
    import torch
    from onnxruntime.quantization import QuantType, quantize_dynamic
    from transformers import AutoModel, AutoTokenizer

    OUT.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(content.E5_MODEL, cache_dir=str(content.CACHE / "hf"))
    bert = AutoModel.from_pretrained(content.E5_MODEL, cache_dir=str(content.CACHE / "hf")).eval()

    class Encoder(torch.nn.Module):
        def forward(self, input_ids, attention_mask):
            hidden = bert(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
            mask = attention_mask.unsqueeze(-1).to(hidden.dtype)
            return torch.nn.functional.normalize((hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9), dim=1)

    sample = tokenizer(["query: пример запроса", "query: a longer example query"], padding=True, return_tensors="pt")
    full = OUT / "e5_query_fp32.onnx"
    batch, seq = torch.export.Dim("batch"), torch.export.Dim("seq", max=512)
    torch.onnx.export(Encoder(), (sample["input_ids"], sample["attention_mask"]), str(full),
                      input_names=["input_ids", "attention_mask"], output_names=["sentence_embedding"],
                      dynamic_shapes={"input_ids": {0: batch, 1: seq}, "attention_mask": {0: batch, 1: seq}})
    # «embedding» – уже имя узла внутри BERT: выход назван иначе, иначе модель после сжатия не загружается
    ort.InferenceSession(str(full), providers=["CPUExecutionProvider"])  # исходная модель должна загружаться
    quantize_dynamic(str(full), str(OUT / "e5_query.onnx"), weight_type=QuantType.QInt8)
    full.unlink()
    for extra in OUT.glob("e5_query_fp32.onnx*"):
        extra.unlink()
    # словарь e5 для сайта – компактный файл sentencepiece (≈ 5 МБ) вместо tokenizer.json (250 МБ в памяти)
    import shutil

    from huggingface_hub import hf_hub_download

    shutil.copy(hf_hub_download(content.E5_MODEL, "sentencepiece.bpe.model", cache_dir=str(content.CACHE / "hf")),
                OUT / "e5_sentencepiece.model")
    shutil.rmtree(OUT / "e5_tokenizer", ignore_errors=True)  # прежний вариант выгрузки

    # проверка в том виде, как на сайте: номера токенов – encode_query (sentencepiece), модель – ONNX int8
    import sentencepiece

    sp_model = sentencepiece.SentencePieceProcessor(model_file=str(OUT / "e5_sentencepiece.model"))
    texts = [f"query: {q}" for q in QUERY_CHECK]
    same = all(encode_query(sp_model, t) == tokenizer(t)["input_ids"] for t in texts)
    session = ort.InferenceSession(str(OUT / "e5_query.onnx"), providers=["CPUExecutionProvider"])
    mine = np.vstack([session.run(None, {"input_ids": np.array([ids], dtype=np.int64),
                                         "attention_mask": np.ones((1, len(ids)), dtype=np.int64)})[0]
                      for ids in (encode_query(sp_model, t) for t in texts)])
    reference = content.embed_queries(QUERY_CHECK)
    cosine = (mine * reference).sum(1)
    size = (OUT / "e5_query.onnx").stat().st_size / 2**20
    print(f"ONNX int8: {size:.0f} МБ; токены sentencepiece совпали с токенизатором e5: {same}; "
          f"косинус с исходной моделью: мин {cosine.min():.4f}, среднее {cosine.mean():.4f}")


if __name__ == "__main__":
    import sys

    commands = {"e5": e5_vectors, "onnx": onnx_query_model, "manifest": refresh_manifest}
    commands.get(sys.argv[1] if len(sys.argv) > 1 else "", main)()
