"""Скачать выгрузку модели (model/export) из релиза GitHub при сборке образа и сверить каждый файл с manifest.json.

    python fetch_export.py <адрес релиза> <папка>           # адрес – .../releases/download/<тег>
    python fetch_export.py <адрес релиза> <папка> --check   # CI: только размеры, без скачивания

Файл с другой контрольной суммой или размером – ошибка сборки: лучше не выложить сервер, чем выложить его с
чужой или испорченной моделью. Режим --check (задача CI «выгрузка») спрашивает у релиза только размер каждого
файла из manifest.json: если файла нет или он другой, Render при сборке упал бы – CI скажет это раньше."""
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

TRIES = 4


def download(url: str, path: Path, size: int, digest: str) -> None:
    for attempt in range(1, TRIES + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as response, open(path, "wb") as out:
                while chunk := response.read(1 << 20):
                    out.write(chunk)
            data = path.read_bytes()
            if len(data) == size and hashlib.sha256(data).hexdigest() == digest:
                return
            print(f"{path.name}: не совпала контрольная сумма (попытка {attempt})", flush=True)
        except OSError as error:
            print(f"{path.name}: {error} (попытка {attempt})", flush=True)
        time.sleep(5 * attempt)
    sys.exit(f"{path.name}: не удалось скачать без ошибок за {TRIES} попытки")


def check(base: str, files: dict) -> None:
    """Каждый файл манифеста есть в релизе и того же размера (HEAD с переходом по перенаправлению GitHub)."""
    bad = []
    for name, info in files.items():
        try:
            request = urllib.request.Request(f"{base.rstrip('/')}/{name}", method="HEAD")
            with urllib.request.urlopen(request, timeout=60) as response:
                size = int(response.headers.get("Content-Length", -1))
        except OSError as error:
            bad.append(f"{name}: {error}")
            continue
        if size != info["bytes"]:
            bad.append(f"{name}: в релизе {size} байт, в манифесте {info['bytes']}")
        else:
            print(f"{name}: {size} байт – совпадает", flush=True)
    if bad:
        sys.exit("релиз не совпадает с manifest.json:\n" + "\n".join(bad))
    print(f"релиз совпадает с манифестом: {len(files)} файлов")


def main(base: str, folder: str, mode: str = "") -> None:
    out = Path(folder)
    files = json.loads((out / "manifest.json").read_text(encoding="utf-8"))["files"]
    if mode == "--check":
        return check(base, files)
    started = time.time()
    for name, info in files.items():
        download(f"{base.rstrip('/')}/{name}", out / name, info["bytes"], info["sha256"])
        print(f"{name}: {info['bytes'] / 2**20:.1f} МБ – ок", flush=True)
    print(f"выгрузка: {len(files)} файлов за {time.time() - started:.0f} с")


if __name__ == "__main__":
    main(*sys.argv[1:4])
