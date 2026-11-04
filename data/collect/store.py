from pathlib import Path

import pandas as pd


# CSV-кэш внешних данных (названия Wikidata, постеры и описания TMDb) с ключом movie_id; пустые поля – пустые
# строки, а не NaN, чтобы «не найдено» отличалось от «ещё не спрашивали» (такой фильм просто есть в файле)
def load(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)
    return pd.read_csv(path, dtype=str, keep_default_na=False)[columns].astype({"movie_id": "int64"})


# сохранить кэш: только фильмы каталога, без дублей (свежая запись побеждает), по порядку movie_id
def save(frame: pd.DataFrame, path: Path, catalog: pd.DataFrame) -> pd.DataFrame:
    frame = frame.astype({"movie_id": "int64"})
    frame = frame[frame["movie_id"].isin(catalog["movie_id"])]
    frame = frame.drop_duplicates("movie_id", keep="last").sort_values("movie_id", ignore_index=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    # .gz – сжатие без времени в заголовке: при тех же данных файл тот же, и git не видит изменений
    compression = {"method": "gzip", "mtime": 0} if path.suffix == ".gz" else None
    frame.to_csv(path, index=False, lineterminator="\n", compression=compression)
    return frame
