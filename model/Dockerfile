# образ только с зависимостями моделей; код моделей, загрузчик набора (data/collect) и оформление рисунков
# (research/style.py) подключаются с хоста, отчёты пишутся на хост
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/mpl PYTHONPATH=/data:/research
WORKDIR /model

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
