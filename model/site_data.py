"""Цифры для страниц сайта «Сравнение моделей» и «Исследование» – из отчётов проверки (model/reports) и
исследования (research/results), а не переписанные руками: python site_data.py -> frontend/src/data/site.json.

Только стандартная библиотека; запускать после изменения отчётов (make -C model site-data)."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
RESEARCH = Path("/research/results") if Path("/research/results").exists() else ROOT.parent / "research" / "results"
OUT = Path("/frontend/src/data/site.json") if Path("/frontend").exists() else ROOT.parent / "frontend" / "src" / "data" / "site.json"
SCENARIOS = ("cold5", "cold10", "warm")

# модель -> (ключ в отчётах, файл итогового теста, файл валидации); семейство – для подписи на сайте
MODELS = {
    "popular": ("popular_year", "final", "final", "baseline"),
    "user_knn": ("user_knn_k200", "final", "final", "neighbors"),
    "item_knn": ("item_knn_cosine_k200_binary", "final", "final", "neighbors"),
    "als": ("als_f64_r0.1_a1", "final", "final", "factorization"),
    "svd": ("svd_f64_r0.03", "final", "final", "factorization"),
    "ease": ("ease_l5000", "final_ease", "ease", "linear"),
    "vae": ("vae_z400_b0.5", "final_gpu", "vae", "neural"),
    "content": ("content_tfidf_meta_centered", "final", "final", "content"),
    "hybrid_vae": ("hybrid_popular_year_vae_z400_b0.5_w0.2", "final_gpu", "hybrid_vae", "hybrid"),
    "hybrid": ("hybrid_popular_year_als_f64_r0.1_a1_w0.4", "final", "final", "hybrid"),
}
NEW_MODELS = {"newest": "newest", "content_text": "content_tfidf_text_centered",
              "hybrid_new": "hybrid_newest_content_tfidf_text_centered_w0.9"}


def report(folder: str, name: str) -> dict:
    path = REPORTS / folder / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def rows(name: str) -> list[dict]:
    with open(RESEARCH / name, encoding="utf-8") as f:
        return [{k: (float(v) if v not in ("", None) and k != "month" else v) for k, v in r.items()} for r in csv.DictReader(f)]


def r4(x):
    return None if x is None else round(float(x), 4)


def models() -> list[dict]:
    out = []
    for key, (name, test_folder, val_folder, family) in MODELS.items():
        test, val = report(test_folder, "test"), report(val_folder, "validation")
        scenarios = {}
        for s in SCENARIOS:
            m = test.get("ranking", {}).get(s, {}).get(name, {})
            scenarios[s] = {"ndcg": r4(m.get("ndcg@10")), "ci": [r4(c) for c in m.get("ndcg@10_ci95", [])],
                            "novelty": r4(m.get("novelty@10")), "coverage": r4(m.get("coverage@10")),
                            "hit": r4(m.get("hit@10"))}
        out.append({"key": key, "family": family, "test": r4(test.get("score", {}).get(name)),
                    "validation": r4(val.get("score", {}).get(name)), "scenarios": scenarios})
    return out


def new_items() -> dict:
    return {period: {key: r4(report("final", f"{period}_new").get("score", {}).get(name))
                     for key, name in NEW_MODELS.items()} for period in ("validation", "test")}


def research() -> dict:
    eda = json.loads((RESEARCH / "eda.json").read_text(encoding="utf-8"))
    years: dict[str, dict] = {}
    for r in rows("monthly.csv"):
        y = years.setdefault(r["month"][:4], {"year": int(r["month"][:4]), "ratings": 0, "new_users": 0})
        y["ratings"] += int(r["ratings"] or 0)
        y["new_users"] += int(r["new_users"] or 0)
    lorenz = rows("lorenz.csv")
    return {
        "ratings": eda["ratings"], "users": eda["users"], "movies_rated": eda["movies_rated"],
        "period": eda["period"], "mean_rating": eda["mean_rating"], "density": eda["density"],
        "top1_share": eda["movies_popularity"]["top1_share"], "top10_share": eda["movies_popularity"]["top10_share"],
        "only_first_day": eda["first_day"]["share_users_only_first_day"],
        "first_day_share": eda["first_day"]["share_ratings_first_day"],
        "lorenz": [[r["items"], r["movies"], r["users"]] for i, r in enumerate(lorenz) if i % 4 == 0 or i == len(lorenz) - 1],
        "ratings_hist": [[r["rating"], int(r["count"])] for r in rows("ratings_hist.csv")],
        "popularity": [[int(r["from"]), r["median"], r["q25"], r["q75"]] for r in rows("popularity.csv")],
        "years": list(years.values()),
    }


def search() -> dict:
    variants = json.loads((REPORTS / "search" / "site.json").read_text(encoding="utf-8"))["variants"]
    return {name.removeprefix("e5_known_w"): v["summary"] for name, v in variants.items()}


def main() -> None:
    test = report("final", "test")
    data = {"protocol": {"bounds": test["bounds"], "candidates": test["candidates"],
                         "people": {s: test["scenarios"][s]["people"] for s in SCENARIOS}},
            "models": models(), "new_items": new_items(), "research": research(), "search": search(),
            "site_model": "hybrid"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    missing = [m["key"] for m in data["models"] if m["test"] is None or m["validation"] is None]
    print(f"сохранено {OUT} ({OUT.stat().st_size / 1024:.1f} КБ); без цифр: {missing or 'нет'}")


if __name__ == "__main__":
    main()
