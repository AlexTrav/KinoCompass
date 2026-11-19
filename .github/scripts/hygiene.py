"""Чистота репозитория (CI, задача hygiene): во всех файлах под git – ни длинного тире, ни секретов.

- Длинное тире: во всём проекте только среднее «–» (оформление по правилам задания); сам символ здесь задан кодом.
- Секреты: токены GitHub, JWT (ключ доступа TMDb – JWT), строка TMDB_TOKEN= со значением, приватные ключи.
Файл .env в git не попадает (.gitignore); эта проверка ловит случайно вставленный ключ в коде, ноутбуке или README.

    python .github/scripts/hygiene.py   # код выхода 1 и список нарушений, если они есть
"""
import re
import subprocess
import sys

EM_DASH = chr(0x2014)
SECRETS = {
    "токен GitHub": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{40,}"),
    "JWT (например, ключ TMDb)": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "TMDB_TOKEN со значением": re.compile(r"TMDB_TOKEN\s*=\s*[^\s<`'\"]"),
    "приватный ключ": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
# двоичные файлы и сжатые данные не читаются
SKIP = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".gz", ".zip", ".npy", ".npz", ".onnx", ".db",
        ".parquet", ".pdf", ".docx", ".pptx")


def main() -> int:
    files = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout.decode().split("\0")
    problems = []
    for path in filter(None, files):
        if path.lower().endswith(SKIP):
            continue
        try:
            text = open(path, encoding="utf-8").read()
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if EM_DASH in line:
                problems.append(f"{path}:{number}: длинное тире (нужно среднее «–»)")
            for name, pattern in SECRETS.items():
                if pattern.search(line):
                    problems.append(f"{path}:{number}: похоже на секрет – {name}")
    print("\n".join(problems) if problems else f"чисто: {len([f for f in files if f])} файлов")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
