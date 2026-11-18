.PHONY: image test run load

IMAGE := kinocompass-api

# Git Bash на Windows иначе превращает пути контейнера в пути Windows
export MSYS_NO_PATHCONV=1

# выгрузка модели с хоста (python export.py в model/), а не из релиза – как на Render, но без скачивания
EXPORT := -v "$(CURDIR)/../model/export:/app/export:ro"

# контекст – корень репозитория (в образ идут model/site_core.py и manifest.json); EXPORT_URL пустой – без скачивания
image:
	docker build -f Dockerfile --build-arg EXPORT_URL= -t $(IMAGE) ..

# pytest на маленькой искусственной выгрузке (tests/conftest.py), без сети
test: image
	docker run --rm $(IMAGE) python -m pytest -q tests

# API на http://localhost:8000 (документация – /docs) с лимитом памяти бесплатного Render
run: image
	docker run --rm --memory 512m -p 8000:8000 $(EXPORT) $(IMAGE)

# 100 запросов разных точек на настоящей выгрузке: время ответа и пик памяти при лимите 512 МБ
load: image
	docker run --rm --memory 512m $(EXPORT) $(IMAGE) python load_check.py
