# образ для скачивания MovieLens, сборки parquet и каталога; данные пишутся на хост через volume, а не в образ
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY collect ./collect
COPY tests ./tests

ENTRYPOINT ["python", "-m", "collect"]
