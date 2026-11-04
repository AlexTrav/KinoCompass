import hashlib
import io
import time
import zipfile

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import requests

from .config import DATASET, MD5_URL, RETRIES, ZIP_URL
from .net import backoff, request

# компактные типы: 32 млн оценок в int32/float32 занимают в памяти около 0,5 ГБ вместо 1 ГБ;
# imdbId – строка, чтобы не потерять ведущие нули (tt0114709)
SCHEMAS = {
    "ratings": {"userId": pa.int32(), "movieId": pa.int32(), "rating": pa.float32(), "timestamp": pa.int64()},
    "tags": {"userId": pa.int32(), "movieId": pa.int32(), "tag": pa.string(), "timestamp": pa.int64()},
    "movies": {"movieId": pa.int32(), "title": pa.string(), "genres": pa.string()},
    "links": {"movieId": pa.int32(), "imdbId": pa.string(), "tmdbId": pa.int32()},
}
RENAME = {"userId": "user_id", "movieId": "movie_id", "timestamp": "time", "imdbId": "imdb_id", "tmdbId": "tmdb_id"}


# контрольная сумма архива, которую публикует GroupLens рядом с ним («<md5>  ml-32m.zip»)
def expected_md5() -> str:
    return request("GET", MD5_URL).text.split()[0].lower()


# архив MovieLens целиком в оперативную память (239 МБ) с проверкой md5: на диск не пишется ничего, после
# выхода из контейнера от архива не остаётся следа. Сервер GroupLens иногда рвёт соединение посреди загрузки –
# тогда загрузка продолжается с того же байта (Range), до RETRIES попыток; если сервер докачку не поддержал
# (ответ 200 вместо 206), архив качается заново
def fetch_archive(expected: str | None = None) -> zipfile.ZipFile:
    expected = expected or expected_md5()
    print(f"скачиваю {ZIP_URL} в память", flush=True)
    buffer, digest, total, shown = io.BytesIO(), hashlib.md5(), 0, -1
    for attempt in range(1, RETRIES + 1):
        done = buffer.tell()
        resp = request("GET", ZIP_URL, stream=True, headers={"Range": f"bytes={done}-"} if done else None)
        if done and resp.status_code != 206:
            buffer, digest, done = io.BytesIO(), hashlib.md5(), 0
        total = total or int(resp.headers.get("Content-Length") or 0)
        try:
            for chunk in resp.iter_content(1 << 20):
                buffer.write(chunk)
                digest.update(chunk)
                done = buffer.tell()
                if total and done * 4 // total != shown:
                    shown = done * 4 // total
                    print(f"  {done * 100 // total} % ({done >> 20} из {total >> 20} МБ)", flush=True)
            break
        # обрыв посреди ответа requests выдаёт как ChunkedEncodingError – это не подвид ConnectionError
        except (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError) as error:
            if attempt == RETRIES:
                raise SystemExit(f"не удалось скачать архив за {RETRIES} попыток: {error}") from None
            print(f"  обрыв на {buffer.tell() >> 20} МБ, продолжаю (попытка {attempt + 1} из {RETRIES})", flush=True)
            time.sleep(backoff(attempt))
    if digest.hexdigest() != expected:
        raise SystemExit(f"контрольная сумма архива не совпала: {digest.hexdigest()} вместо {expected}")
    return zipfile.ZipFile(buffer)


# CSV из архива -> таблица: имена колонок в snake_case, время – метка UTC (секунды Unix в README);
# CSV читается потоком прямо из архива, без распаковки на диск
def read_table(archive: zipfile.ZipFile, name: str) -> pa.Table:
    options = pacsv.ConvertOptions(column_types=SCHEMAS[name])
    # в тегах встречаются запятые и кавычки внутри поля – разбор по правилам CSV, с переносами внутри значений
    parse = pacsv.ParseOptions(newlines_in_values=True)
    with archive.open(f"{DATASET}/{name}.csv") as stream:
        table = pacsv.read_csv(stream, parse_options=parse, convert_options=options)
    table = table.rename_columns([RENAME.get(column, column) for column in table.column_names])
    if "time" in table.column_names:
        index = table.column_names.index("time")
        table = table.set_column(index, "time", pc.cast(table["time"], pa.timestamp("s", tz="UTC")))
    return table


def read_text(archive: zipfile.ZipFile, name: str) -> str:
    return archive.read(f"{DATASET}/{name}").decode("utf-8")


# все таблицы набора в pandas: ratings, tags, movies, links. Таблица pyarrow освобождается по ходу перевода
# (self_destruct), а не держится рядом с копией в pandas, – пик памяти меньше почти на гигабайт
def load(archive: zipfile.ZipFile, names: tuple[str, ...] = tuple(SCHEMAS)) -> dict[str, pd.DataFrame]:
    frames = {}
    for name in names:
        table = read_table(archive, name)
        frames[name] = table.to_pandas(split_blocks=True, self_destruct=True)
        del table
        print(f"  {name}: {len(frames[name]):,} строк".replace(",", " "), flush=True)
    return frames


# скачать набор в память, прочитать таблицы (и текстовые файлы из names_text) и сразу освободить архив
def fetch(names_text: tuple[str, ...] = ()) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    archive = fetch_archive()
    texts = {name: read_text(archive, name) for name in names_text}
    frames = load(archive)
    archive.close()
    return frames, texts
