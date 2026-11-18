"""Проверка под нагрузкой на настоящей выгрузке: python load_check.py (make -C backend load, лимит 512 МБ).

Сервер в том же процессе (TestClient), сто запросов вперемешку по всем точкам – как человек на сайте:
подсказки названий, советы с разным положением ползунка, новинки, карточки, поиск на трёх языках, сравнение,
карта. Печатает примеры ответов, время по точкам (/api/perf) и пик памяти процесса."""
import random
import time

from fastapi.testclient import TestClient

from app.main import app

LIKED = [{"id": 1, "rating": 5}, {"id": 2571, "rating": 4.5}, {"id": 79132, "rating": 5},
         {"id": 109487, "rating": 4}, {"id": 58559, "rating": 3}]
QUERIES = [("мультфильм про игрушки, которые оживают", "ru"), ("Начало", "ru"), ("робот убирает мусор", "ru"),
           ("ойыншықтар тірі болады", "kk"), ("toys come to life", "en"), ("Inception", "en")]


def main() -> None:
    random.seed(0)
    started = time.perf_counter()
    with TestClient(app) as client:
        print(f"запуск: {time.perf_counter() - started:.1f} с")
        rec = client.post("/api/recommend", json={"ratings": LIKED}).json()
        print("советы:", [f["title"] for f in rec["items"]])
        free = client.post("/api/recommend", json={"ratings": LIKED, "popularity_weight": 0}).json()
        print("ползунок 0 (только вкус):", [f["title"] for f in free["items"]])
        print("новинки:", [f["title"] for f in client.post("/api/new", json={"ratings": LIKED}).json()["items"]])
        card = client.get("/api/film/79132").json()
        print("Начало: похожие –", [f["title"] for f in card["similar"][:5]], "| описание:", card["overview"][:60])
        for q, lang in QUERIES:
            found = client.get("/api/search", params={"q": q, "lang": lang}).json()["items"]
            print(f"поиск «{q}»:", [f"{f['title']} ({f['by']})" for f in found[:5]])
        print("подсказки «звёздн»:", [f["title"] for f in client.get("/api/films", params={"q": "звёздн"}).json()["items"][:5]])
        print("точка на карте:", client.post("/api/map/me", json={"ratings": LIKED}).json())

        calls = [lambda: client.get("/api/films", params={"q": random.choice(["матр", "love", "война", ""])}),
                 lambda: client.post("/api/recommend", json={"ratings": random.sample(LIKED, 3),
                                                             "popularity_weight": random.choice([0, 0.4, 0.8])}),
                 lambda: client.post("/api/new", json={"ratings": LIKED}),
                 lambda: client.get(f"/api/film/{random.choice([1, 2571, 79132, 296, 318])}"),
                 lambda: client.get("/api/search", params={"q": random.choice(QUERIES)[0]}),
                 lambda: client.post("/api/compare", json={"ratings": LIKED}),
                 lambda: client.get("/api/map", params={"lang": random.choice(["ru", "kk", "en"])}),
                 lambda: client.post("/api/map/me", json={"ratings": LIKED})]
        for _ in range(100):
            response = random.choice(calls)()
            assert response.status_code == 200, response.text
        perf = client.get("/api/perf").json()
    for path, s in perf["endpoints"].items():
        print(f"{path}: {s['count']} запросов, медиана {s['p50_ms']} мс, 95 % – {s['p95_ms']} мс")
    print(f"память: {perf['memory_mb']} МБ (лимит {perf['limit_mb']}), загрузка выгрузки {perf['load_seconds']} с")


if __name__ == "__main__":
    main()
