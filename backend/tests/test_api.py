"""Точки API на искусственной выгрузке (conftest.py): ответы и ошибки."""
import numpy as np

import site_core as core

SPACE_FAN = [{"id": 1, "rating": 5}]


def ids(items: list[dict]) -> list[int]:
    return [f["id"] for f in items]


def test_health(client):
    body = client.get("/api/health").json()
    assert body == {"status": "ok", "data_until": "2023-10-13", "catalog": 8, "new_items": 2, "map_films": 6}


def test_films_suggest_by_title_in_any_language(client):
    assert ids(client.get("/api/films", params={"k": 3}).json()["items"]) == [1, 2, 3]  # пусто – популярное
    found = client.get("/api/films", params={"q": "Фильм 1"}).json()["items"]
    assert ids(found) == [1]  # «фильм 1» не входит в «фильм 2…»; точное совпадение
    assert ids(client.get("/api/films", params={"q": "ғарыш", "lang": "kk"}).json()["items"]) == [3]
    many = client.get("/api/films", params={"q": "film"}).json()["items"]
    assert ids(many) == list(range(1, 9))  # начало названия, самые оценённые выше


def test_titles_follow_language_chain(client):
    six = client.get("/api/film/6", params={"lang": "ru"}).json()
    assert six["title"] == "Film 6"  # русского нет – английское
    assert six["titles"] == {"ru": "Film 6", "kk": "Film 6", "en": "Film 6"}
    three = client.get("/api/film/3", params={"lang": "kk"}).json()
    assert three["title"] == "Ғарыш" and three["original_title"] == "Film 3"


def test_recommend_follows_taste_and_skips_rated(client):
    body = client.post("/api/recommend", json={"ratings": SPACE_FAN, "popularity_weight": 0, "k": 3}).json()
    assert set(ids(body["items"])) == {2, 3, 7} and body["tested_weight"] == core.SITE_WEIGHT
    popular = client.post("/api/recommend", json={"ratings": SPACE_FAN, "popularity_weight": 1, "k": 3}).json()
    assert ids(popular["items"]) == [2, 3, 4]  # только популярность, оценённый 1 пропущен


def test_recommend_matches_site_core(client, store):
    """Сервер считает той же функцией, что выгрузка проверялась (site_check.py)."""
    body = client.post("/api/recommend", json={"ratings": [{"id": 4, "rating": 4}, {"id": 2, "rating": 3}],
                                               "k": 6}).json()
    index = np.array([store.row[4], store.row[2]])
    scores = core.site_scores(store.pop_ranks, store.items, store.gram, index)
    scores[index] = -np.inf
    assert ids(body["items"]) == [int(store.ids[i]) for i in np.argsort(-scores, kind="stable")[:6]]


def test_unknown_and_invalid_ratings(client):
    body = client.post("/api/recommend", json={"ratings": [*SPACE_FAN, {"id": 999, "rating": 4}]}).json()
    assert body["unknown"] == [999]
    assert client.post("/api/recommend", json={"ratings": [{"id": 999, "rating": 4}]}).status_code == 422
    assert client.post("/api/recommend", json={"ratings": []}).status_code == 422
    assert client.post("/api/recommend", json={"ratings": [{"id": 1, "rating": 7}]}).status_code == 422
    assert client.post("/api/recommend", json={"ratings": SPACE_FAN, "popularity_weight": 2}).status_code == 422
    assert client.post("/api/recommend", json={"ratings": SPACE_FAN, "lang": "de"}).status_code == 422


def test_new_items_only_from_new_pool(client):
    space = client.post("/api/new", json={"ratings": SPACE_FAN}).json()
    assert ids(space["items"]) == [7, 8] and space["rule"] == "год выпуска ≥ 2022"
    love = client.post("/api/new", json={"ratings": [{"id": 1, "rating": 1}, {"id": 4, "rating": 5}]}).json()
    assert ids(love["items"])[0] == 8  # не понравившаяся фантастика тянет вниз (вес centered)


def test_film_card_overview_and_similar(client):
    card = client.get("/api/film/2", params={"lang": "ru"}).json()
    assert card["overview"] == "Plot 2"  # русского описания нет – английское
    assert client.get("/api/film/1", params={"lang": "ru"}).json()["overview"] == "Сюжет 1"
    assert client.get("/api/film/1", params={"lang": "en"}).json()["overview"] == "Plot 1"
    assert 2 not in ids(card["similar"]) and len(card["similar"]) == 7
    assert client.get("/api/film/5").json()["poster"] is None
    assert client.get("/api/film/999").status_code == 404


def test_search_by_meaning_and_by_title(client):
    space = client.get("/api/search", params={"q": "кино про космос", "k": 4}).json()["items"]
    assert set(ids(space)) == {1, 2, 3, 7} and {f["by"] for f in space} == {"meaning"}
    titled = client.get("/api/search", params={"q": "Фильм 5"}).json()["items"]
    assert titled[0]["id"] == 5 and titled[0]["by"] == "title" and ids(titled).count(5) == 1
    assert client.get("/api/search", params={"q": "   "}).status_code == 422
    assert client.get("/api/search").status_code == 422


def test_compare_four_models(client):
    body = client.post("/api/compare", json={"ratings": SPACE_FAN, "k": 3}).json()["models"]
    assert set(body) == {"popular", "als", "content", "hybrid"}
    assert ids(body["popular"]["items"]) == [2, 3, 4]
    assert set(ids(body["content"]["items"])) == {2, 3, 7}
    assert all(1 not in ids(m["items"]) and m["ms"] >= 0 for m in body.values())


def test_taste_map_and_my_point(client):
    films = client.get("/api/map", params={"lang": "en"}).json()["films"]
    assert [f["id"] for f in films] == [1, 2, 3, 4, 5, 6] and films[0]["genre"] == "Sci-Fi"
    me = client.post("/api/map/me", json={"ratings": [{"id": 1, "rating": 5}, {"id": 4, "rating": 1}]}).json()
    assert (me["x"], me["y"], me["used"]) == (-0.9, 0.1, 2)  # не понравившийся фильм не тянет
    off = client.post("/api/map/me", json={"ratings": [{"id": 7, "rating": 5}]}).json()
    assert off == {"x": None, "y": None, "used": 0, "unknown": []}


def test_perf_counts_endpoints_by_template(client):
    for m in (1, 2, 3):
        client.get(f"/api/film/{m}")
    client.get("/api/film/999")  # ошибка – не в сводке
    client.get("/nowhere")
    body = client.get("/api/perf").json()
    assert body["endpoints"]["/api/film/{movie_id}"]["count"] >= 3
    assert "/nowhere" not in body["endpoints"] and body["memory_mb"]["peak"] > 0 and body["limit_mb"] == 512


def test_site_core_helpers():
    assert core.normalize_title("Ёлки (2010): Новый год!") == "елки новый год"
    cosine = np.array([0.9, 0.8, 0.1, 0.7])
    assert np.argsort(-core.search_scores(cosine, np.zeros(4), 0.0, pool=3))[:3].tolist() == [0, 1, 3]
    assert np.isinf(core.search_scores(cosine, np.zeros(4), 0.0, pool=3)[2])
    assert np.allclose(core.centered([3, 3]), [1, 1]) and np.allclose(core.centered([5, 1]), [2, -2])
    assert core.map_point(np.empty((0, 2)), np.array([])) is None
    assert np.allclose(core.map_point(np.array([[0, 0], [1, 1]]), np.array([2, 1])), [0.5, 0.5])  # никто не понравился
