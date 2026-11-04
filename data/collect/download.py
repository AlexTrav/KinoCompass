import hashlib
import zipfile
from pathlib import Path

from .config import CSV_DIR, CSV_FILES, MD5_URL, RAW_DIR, ZIP_PATH, ZIP_URL
from .net import request


def md5sum(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# контрольная сумма архива, которую публикует GroupLens рядом с ним («<md5>  ml-32m.zip»)
def expected_md5() -> str:
    return request("GET", MD5_URL).text.split()[0].lower()


# скачать архив во временный .part и переименовать только после совпадения контрольной суммы –
# оборванная загрузка не выдаст себя за готовый архив
def fetch_zip(expected: str) -> None:
    part = ZIP_PATH.with_name(ZIP_PATH.name + ".part")
    resp = request("GET", ZIP_URL, stream=True)
    total = int(resp.headers.get("Content-Length") or 0)
    done, shown = 0, -1
    with part.open("wb") as f:
        for chunk in resp.iter_content(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total and done * 10 // total != shown:
                shown = done * 10 // total
                print(f"  {done * 100 // total} % ({done >> 20} из {total >> 20} МБ)", flush=True)
    actual = md5sum(part)
    if actual != expected:
        part.unlink()
        raise SystemExit(f"контрольная сумма архива не совпала: {actual} вместо {expected}")
    part.replace(ZIP_PATH)


# скачать архив MovieLens (если его нет или он испорчен) и распаковать CSV в raw/ml-32m
def download(expected: str | None = None) -> str:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    expected = expected or expected_md5()
    if ZIP_PATH.exists() and md5sum(ZIP_PATH) == expected:
        status = "архив уже скачан, контрольная сумма совпадает"
    else:
        print(f"скачиваю {ZIP_URL}", flush=True)
        fetch_zip(expected)
        status = "архив скачан, контрольная сумма совпадает"
    if not all((CSV_DIR / name).exists() for name in CSV_FILES):
        with zipfile.ZipFile(ZIP_PATH) as archive:
            archive.extractall(RAW_DIR)
        status += ", распакован"
    return status
