.PHONY: image download parquet catalog titles posters check data test clean

IMAGE := kinocompass-data

# Git Bash на Windows иначе превращает пути контейнера (/data/raw) в пути Windows
export MSYS_NO_PATHCONV=1

# папки данных монтируются с хоста – результат остаётся в data/raw, data/work и data/catalog
VOLUMES := -v "$(CURDIR)/raw:/data/raw" -v "$(CURDIR)/work:/data/work" -v "$(CURDIR)/catalog:/data/catalog"
RUN := docker run --rm $(VOLUMES) $(IMAGE)

# собрать образ со скриптами
image:
	docker build -t $(IMAGE) .

# скачать архив MovieLens 32M (239 МБ) с проверкой md5 и распаковать в raw/
download: image
	$(RUN) download

# CSV -> work/*.parquet с компактными типами (для исследования и моделей)
parquet: image
	$(RUN) parquet

# каталог фильмов минимум с 20 оценками -> catalog/movies.csv
catalog: image
	$(RUN) catalog

# названия ru/kk/en из Wikidata -> catalog/titles.csv (дозапрашивает только новые фильмы)
titles: image
	$(RUN) titles

# пути постеров TMDb -> catalog/posters.csv; ключ TMDB_TOKEN – из KinoCompass/.env (в git не попадает)
posters: image
	docker run --rm --env-file "$(CURDIR)/../.env" $(VOLUMES) $(IMAGE) posters

# проверить всё: сверка с README набора, шкала, даты, дубли, каталог
check: image
	$(RUN) check

# всё по порядку с нуля
data: download parquet catalog titles posters check

# pytest: разбор, каталог, проверки, Wikidata и TMDb – на маленьких данных, без сети
test: image
	docker run --rm --entrypoint python $(IMAGE) -m pytest -q -p no:cacheprovider tests

# удалить образ (данные в raw/, work/ и catalog/ остаются)
clean:
	docker rmi -f $(IMAGE)
