# KinoCompass

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Рубежное задание РК-2 по курсу «Искусственный интеллект и машинное обучение»: рекомендательная
система фильмов на данных MovieLens 32M – подбирает фильмы под вкус по 5–10 оценкам и объясняет,
почему именно эти. Сравниваются базовые модели, коллаборативная фильтрация, матричная факторизация,
контентная модель и нейросеть Mult-VAE.

Автор: **Алексей Нерезов**.

> Проект в работе.

## Что уже сделано

- данные: MovieLens 32M скачивается в память при каждом запуске (на диске не хранится), каталог из
  23 349 фильмов (99 % оценок) с названиями на русском, казахском и английском из Wikidata и постерами
  TMDb, проверка данных – [data/](data/README.md).

## Запуск

Нужен только Docker и make:

```bash
make data    # скачать MovieLens 32M в память, собрать каталог фильмов с названиями и постерами, проверить
make check   # проверить данные и каталог
make test    # автотесты
```

Для постеров нужен ключ TMDb: `TMDB_TOKEN=<Ключ доступа к API>` в файле `.env` в корне проекта
(в git не попадает).

## Структура

```
KinoCompass/
  data/      – загрузка MovieLens в память и каталог фильмов (catalog/ – в git)
  Makefile   – общие команды
```

## Данные

MovieLens 32M – GroupLens Research ([условия](data/catalog/ml-32m-README.txt): некоммерческое
использование), F. M. Harper, J. A. Konstan. The MovieLens Datasets: History and Context. ACM TiiS, 2015.
Названия фильмов – [Wikidata](https://www.wikidata.org/) (CC0). Постеры – [TMDb](https://www.themoviedb.org/):
this product uses the TMDB API but is not endorsed or certified by TMDB.
