.PHONY: image baselines knn factorization figures test

IMAGE := kinocompass-model

# Git Bash на Windows иначе превращает пути контейнера в пути Windows
export MSYS_NO_PATHCONV=1

# проверочная часть: validation (по умолчанию) или test – только явно, один раз на шаге 6
PERIOD ?= validation
# рисунки – в папку отчёта, если передана: make figures FIGURES=/путь/к/Рисункам
FIGURES ?= $(CURDIR)/figures
# код моделей – с хоста; загрузчик набора и оформление рисунков – из data/collect и research (только чтение)
RUN := docker run --rm -e PERIOD=$(PERIOD) -v "$(CURDIR):/model" -v "$(CURDIR)/../data/collect:/data/collect:ro" \
	-v "$(CURDIR)/../research:/research:ro" $(IMAGE)

image:
	docker build -t $(IMAGE) .

# базовые модели: скачать набор в память, прогнать все сценарии -> reports/baselines/$(PERIOD).json
baselines: image
	$(RUN) python evaluate.py baselines

# соседи: item-kNN (сетка из 8 настроек) и user-kNN (3) вместе с планкой -> reports/knn/$(PERIOD).json
knn: image
	$(RUN) python evaluate.py knn

# факторизация: ALS (8 настроек), BPR (4), SVD (4) вместе с планкой -> reports/factorization/$(PERIOD).json
factorization: image
	$(RUN) python evaluate.py factorization

# рисунки по сохранённым отчётам (набор не нужен); шрифт Times New Roman – из Windows
figures: image
	docker run --rm -v "$(CURDIR):/model" -v "$(CURDIR)/../research:/research:ro" -v "$(FIGURES):/figures" \
		-v "C:/Windows/Fonts:/winfonts:ro" $(IMAGE) python figures.py

# pytest протокола, метрик и моделей на маленьких данных (без сети)
test: image
	$(RUN) python -m pytest -q -p no:cacheprovider tests
