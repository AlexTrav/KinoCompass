"""Поиск сайта на выгрузке (шаг 7): те же 30 запросов, что при выборе модели поиска (search.py), но в том виде,
как ищет бэкенд, – векторы e5 из выгрузки, модель запросов ONNX int8, словарь sentencepiece.

Варианты – чистый e5 и e5, у которого первые SEARCH_POOL фильмов по смыслу переставлены с учётом известности
фильма (число оценок за всё время; веса WEIGHTS). Известность выбрана заранее, а не подобрана на запросах:
поиск «по описанию» обычно ищет фильм, который человек видел или о котором слышал. Запросы «сюжет» загаданы
про известные фильмы, поэтому выигрыш на них – оценка сверху; вес принимается, только если точность по жанру
не падает. python search_site.py -> reports/search/site.json"""
import gzip
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
import pandas as pd
import sentencepiece

from search import QUERIES, run_search
from site_core import encode_query, ranks, search_scores

OUT = Path(__file__).resolve().parent / "export"
REPORT = Path(__file__).resolve().parent / "reports" / "search" / "site.json"
WEIGHTS = (0.0, 0.1, 0.2, 0.3)


def main() -> None:
    catalog = json.load(gzip.open(OUT / "catalog.json.gz", "rt", encoding="utf-8"))
    side = pd.DataFrame({"genres": ["|".join(c["genres"]) for c in catalog], "title": [c["title"] for c in catalog]},
                        index=pd.Index([c["id"] for c in catalog], name="movie_id"))
    e5 = np.load(OUT / "e5_enru.npy").astype(np.float32)
    known = ranks(np.array([c["n_ratings"] for c in catalog], dtype=np.float64))
    sp_model = sentencepiece.SentencePieceProcessor(model_file=str(OUT / "e5_sentencepiece.model"))
    session = ort.InferenceSession(str(OUT / "e5_query.onnx"), providers=["CPUExecutionProvider"])

    def embed(texts: list[str]) -> np.ndarray:
        out = []
        for text in texts:
            ids = encode_query(sp_model, f"query: {text}")
            out.append(session.run(None, {"input_ids": np.array([ids], dtype=np.int64),
                                          "attention_mask": np.ones((1, len(ids)), dtype=np.int64)})[0][0])
        return np.vstack(out)

    queries = pd.read_csv(QUERIES, dtype={"expect": str})
    cosine = e5 @ embed(queries["query"].tolist()).T  # фильмы × запросы: модель запросов – один раз на запрос

    def variant(weight: float):
        return lambda texts: np.vstack([search_scores(cosine[:, i], known, weight) for i in range(len(texts))])

    report = run_search(side, {f"e5_known_w{w:g}": variant(w) for w in WEIGHTS}, queries)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"source": "выгрузка сайта (model/export)", **report}, ensure_ascii=False,
                                 indent=2) + "\n", encoding="utf-8")
    print(f"сохранено {REPORT.relative_to(REPORT.parents[2])}")


if __name__ == "__main__":
    main()
