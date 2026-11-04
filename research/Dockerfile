# образ только с зависимостями исследования; код исследования и загрузчик набора (data/collect) подключаются
# с хоста, результаты пишутся на хост
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/mpl PYTHONPATH=/data
WORKDIR /research

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
