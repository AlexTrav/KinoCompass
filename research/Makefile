.PHONY: image eda figures test all

IMAGE := kinocompass-research

# Git Bash на Windows иначе превращает пути контейнера в пути Windows
export MSYS_NO_PATHCONV=1

# рисунки – в папку отчёта, если передана: make figures FIGURES=/путь/к/Рисункам
FIGURES ?= $(CURDIR)/figures
# код исследования – с хоста; загрузчик набора – из data/collect (только чтение)
RUN := docker run --rm -v "$(CURDIR):/research" -v "$(CURDIR)/../data/collect:/data/collect:ro" $(IMAGE)

image:
	docker build -t $(IMAGE) .

# скачать MovieLens 32M в память и посчитать сводки и тесты -> results/ (5–10 минут, пик памяти около 3 ГБ)
eda: image
	$(RUN) python eda.py

# рисунки только по results/ (набор не нужен); шрифт Times New Roman – из Windows
figures: image
	docker run --rm -v "$(CURDIR):/research" -v "$(FIGURES):/figures" -v "C:/Windows/Fonts:/winfonts:ro" \
		$(IMAGE) python figures.py

# pytest расчётов на маленьких данных (без сети)
test: image
	$(RUN) python -m pytest -q -p no:cacheprovider tests

all: eda figures
