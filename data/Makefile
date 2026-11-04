.PHONY: image catalog titles posters check data test clean

IMAGE := kinocompass-data

# Git Bash на Windows иначе превращает пути контейнера (/data/catalog) в пути Windows
export MSYS_NO_PATHCONV=1

# набор MovieLens на диске не хранится: контейнер скачивает архив в оперативную память и читает его оттуда;
# с хоста монтируется только каталог – результат остаётся в data/catalog
RUN := docker run --rm -v "$(CURDIR)/catalog:/data/catalog" $(IMAGE)

# собрать образ со скриптами
image:
	docker build -t $(IMAGE) .

# скачать MovieLens 32M в память (239 МБ, проверка md5), собрать каталог фильмов минимум с 20 оценками
# -> catalog/movies.csv и проверить набор
catalog: image
	$(RUN) catalog

# названия ru/kk/en из Wikidata -> catalog/titles.csv (дозапрашивает только новые фильмы)
titles: image
	$(RUN) titles

# пути постеров TMDb -> catalog/posters.csv; ключ TMDB_TOKEN – из KinoCompass/.env (в git не попадает)
posters: image
	docker run --rm --env-file "$(CURDIR)/../.env" -v "$(CURDIR)/catalog:/data/catalog" $(IMAGE) posters

# скачать набор в память и проверить всё: сверка с README набора, шкала, даты, дубли, каталог
check: image
	$(RUN) check

# всё по порядку с нуля (catalog уже проверяет набор, поэтому отдельный check не нужен)
data: catalog titles posters

# pytest: разбор, каталог, проверки, Wikidata и TMDb – на маленьких данных, без сети
test: image
	docker run --rm --entrypoint python $(IMAGE) -m pytest -q -p no:cacheprovider tests

# удалить образ (каталог в catalog/ остаётся)
clean:
	docker rmi -f $(IMAGE)
