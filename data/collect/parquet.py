import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from .config import CSV_DIR, WORK_DIR

# компактные типы: 32 млн оценок в int32/float32 занимают в памяти около 0,5 ГБ вместо 1 ГБ;
# imdbId – строка, чтобы не потерять ведущие нули (tt0114709)
SCHEMAS = {
    "ratings": {"userId": pa.int32(), "movieId": pa.int32(), "rating": pa.float32(), "timestamp": pa.int64()},
    "tags": {"userId": pa.int32(), "movieId": pa.int32(), "tag": pa.string(), "timestamp": pa.int64()},
    "movies": {"movieId": pa.int32(), "title": pa.string(), "genres": pa.string()},
    "links": {"movieId": pa.int32(), "imdbId": pa.string(), "tmdbId": pa.int32()},
}
RENAME = {"userId": "user_id", "movieId": "movie_id", "timestamp": "time", "imdbId": "imdb_id", "tmdbId": "tmdb_id"}


# CSV MovieLens -> work/<имя>.parquet: имена колонок в snake_case, время – метка UTC (секунды Unix в README)
def read_table(name: str) -> pa.Table:
    options = pacsv.ConvertOptions(column_types=SCHEMAS[name])
    # в тегах встречаются запятые и кавычки внутри поля – разбор по правилам CSV, с переносами внутри значений
    parse = pacsv.ParseOptions(newlines_in_values=True)
    table = pacsv.read_csv(CSV_DIR / f"{name}.csv", parse_options=parse, convert_options=options)
    table = table.rename_columns([RENAME.get(column, column) for column in table.column_names])
    if "time" in table.column_names:
        index = table.column_names.index("time")
        table = table.set_column(index, "time", pc.cast(table["time"], pa.timestamp("s", tz="UTC")))
    return table


def convert() -> dict[str, int]:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    rows = {}
    for name in SCHEMAS:
        table = read_table(name)
        pq.write_table(table, WORK_DIR / f"{name}.parquet", compression="zstd")
        rows[name] = table.num_rows
        print(f"  {name}: {table.num_rows:,} строк".replace(",", " "), flush=True)
    return rows
