.PHONY: data check eda figures baselines knn factorization content test

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

# соседи: item-kNN и user-kNN на валидации -> model/reports/knn
knn:
	"$(MAKE)" -C model knn

# матричная факторизация: ALS, BPR и SVD на валидации -> model/reports/factorization
factorization:
	"$(MAKE)" -C model factorization

# контентная модель: TF-IDF и e5 на кандидатах и новинках -> model/reports/content
content:
	"$(MAKE)" -C model content

# все автотесты
test:
	"$(MAKE)" -C data test
	"$(MAKE)" -C research test
	"$(MAKE)" -C model test
