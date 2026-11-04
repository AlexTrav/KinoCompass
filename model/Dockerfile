# образ только с зависимостями моделей; код моделей, загрузчик набора (data/collect) и оформление рисунков
# (research/style.py) подключаются с хоста, отчёты пишутся на хост
FROM python:3.12-slim

# implicit распараллеливает сам – BLAS в один поток, без переподписки ядер (так советует implicit)
ENV PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/mpl PYTHONPATH=/data:/research OPENBLAS_NUM_THREADS=1
WORKDIR /model

# libgomp – OpenMP для потоков implicit (в slim-образе его нет)
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
