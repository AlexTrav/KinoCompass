.PHONY: data check eda figures baselines test

# скачать MovieLens 32M в память, собрать каталог фильмов с названиями и постерами, проверить
data:
	"$(MAKE)" -C data data

# проверить данные и каталог
check:
	"$(MAKE)" -C data check

# исследование: сводки и тесты по набору -> research/results
eda:
	"$(MAKE)" -C research eda

# рисунки исследования и моделей по сохранённым сводкам и отчётам
figures:
	"$(MAKE)" -C research figures
	"$(MAKE)" -C model figures

# базовые модели на валидации -> model/reports/baselines
baselines:
	"$(MAKE)" -C model baselines

# все автотесты
test:
	"$(MAKE)" -C data test
	"$(MAKE)" -C research test
	"$(MAKE)" -C model test
