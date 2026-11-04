.PHONY: data check eda figures test

# скачать MovieLens 32M в память, собрать каталог фильмов с названиями и постерами, проверить
data:
	"$(MAKE)" -C data data

# проверить данные и каталог
check:
	"$(MAKE)" -C data check

# исследование: сводки и тесты по набору -> research/results
eda:
	"$(MAKE)" -C research eda

# рисунки исследования по сохранённым сводкам
figures:
	"$(MAKE)" -C research figures

# все автотесты
test:
	"$(MAKE)" -C data test
	"$(MAKE)" -C research test
