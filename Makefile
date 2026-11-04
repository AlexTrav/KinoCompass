.PHONY: data check test

# скачать MovieLens 32M, собрать parquet и каталог фильмов с названиями и постерами, проверить
data:
	"$(MAKE)" -C data data

# проверить данные и каталог
check:
	"$(MAKE)" -C data check

# все автотесты
test:
	"$(MAKE)" -C data test
