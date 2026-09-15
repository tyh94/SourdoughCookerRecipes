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
