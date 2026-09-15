# SourdoughCookerRecipes

List of my recipes for app

## Индексы продуктов

Приложение FamilyFoodDiary забирает эти файлы по сырым ссылкам GitHub
(`NutrientsSearcherRemote`), поэтому изменения видны сразу после пуша в `main`.

| файл | что внутри |
|---|---|
| `foods.nutrients.json` | USDA, названия переведены на русский |
| `matvaretabellen.nutrients.json` | норвежская таблица Mattilsynet, 2121 продукт |

### Обновить норвежскую таблицу

```
python3 matvaretabellen.py
```

Скрипт качает [открытые данные Matvaretabellen](https://www.matvaretabellen.no/api/)
в двух локалях, сопоставляет нутриенты по кодам EuroFIR, приводит единицы к тем, в
которых их хранит приложение, и кладёт английское и норвежское названия в одну запись.

Если в выводе появится строка «не сопоставлено» — в таблице завелись новые нутриенты,
и их стоит добавить в словарь `EUROFIR` в скрипте.

Источник просит ссылаться на себя: «Matvaretabellen, Mattilsynet».

### Обновить таблицу USDA

```
python3 usda.py FoodData_Central_foundation_food_json_2025-12-18.json foods.nutrients.json
```

Исходник качается руками с [FoodData Central](https://fdc.nal.usda.gov/download-datasets)
(Foundation Foods, JSON) и в репозиторий не кладётся — нужен только результат.

Названия в USDA только английские, поэтому скрипт переводит их на русский локальным
LibreTranslate, который надо поднять заранее:

```
docker run -p 5001:5000 libretranslate/libretranslate
```
