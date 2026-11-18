# образ API; контекст сборки – корень репозитория (make -C backend image, Render), состав – .dockerignore
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# выгрузка модели (≈ 170 МБ, в git её нет) – из релиза GitHub со сверкой размера и sha256 по manifest.json;
# локально (make image) EXPORT_URL пустой – папка model/export подключается томом
ARG EXPORT_URL=https://github.com/AlexTrav/KinoCompass/releases/download/export-2023-10-13
COPY model/export/manifest.json export/manifest.json
COPY backend/fetch_export.py .
RUN if [ -n "$EXPORT_URL" ]; then python fetch_export.py "$EXPORT_URL" export; fi

COPY model/site_core.py .
COPY backend/app ./app
COPY backend/tests ./tests
COPY backend/load_check.py .

# numpy и onnxruntime – в один поток: на бесплатном Render доля одного ядра
ENV EXPORT_DIR=/app/export PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
# Render передаёт порт в переменной PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
