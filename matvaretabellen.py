#!/usr/bin/env python3
"""Норвежская таблица Matvaretabellen -> индекс продуктов приложения.

Качает открытые данные Mattilsynet и складывает их в тот же формат, что
`foods.nutrients.json`: список `RawFoodItem`, значения на 100 г, имена по языкам.

    python3 matvaretabellen.py

Результат ложится рядом с `foods.nutrients.json` — оттуда его забирает
`NutrientsSearcherRemote` приложения FamilyFoodDiary. Перевод не нужен: таблица
отдаёт английские и норвежские названия сама, и оба уходят в запись.

Источник просит ссылаться на себя: «Matvaretabellen, Mattilsynet».
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

API = "https://www.matvaretabellen.no/api/{locale}/{name}.json"
DEFAULT_OUTPUT = "matvaretabellen.nutrients.json"

# Сопоставление идёт по euroFirId: это стандартные коды EuroFIR, они устойчивее
# норвежских nutrientId и не поедут при обновлении таблицы.
EUROFIR = {
    "PROT": "protein",
    "FAT": "fat",
    "CHO": "carbs",
    "FIBT": "fiber",
    "SUGAR": "sugar",
    "STARCH": "starch",
    "WATER": "water",
    "CHORL": "cholesterol",
    "FASAT": "saturatedFat",
    "FAMS": "monounsaturatedFat",
    "FAPU": "polyunsaturatedFat",
    "FATRS": "transFat",
    "FAN3": "omega3",
    "FAN6": "omega6",
    "CA": "calcium",
    "FE": "iron",
    "MG": "magnesium",
    "P": "phosphorus",
    "K": "potassium",
    "NA": "sodium",
    "ZN": "zinc",
    "CU": "copper",
    "SE": "selenium",
    "VITA": "vitaminA",
    "CARTB": "betaCarotene",
    "VITD": "vitaminD",
    "VITE": "vitaminE",
    "VITC": "vitaminC",
    "THIA": "vitaminB1",
    "RIBF": "vitaminB2",
    "NIA": "vitaminB3",
    "VITB6": "vitaminB6",
    "FOL": "vitaminB9",
    "VITB12": "vitaminB12",
}

# Есть в таблице, но приложению не нужно: алкоголь, соль (есть натрий), йод,
# ниациновый эквивалент, ретинол и отдельные виды сахара отдельно не храним.
IGNORED = {"ALC", "NACL", "ID", "NIAEQ", "RETOL", "SUGAD", "SUGAN", "VITARE"}

# В чём приложение хранит каждый нутриент.
CANONICAL = {
    "calories": "kcal",
    "protein": "g", "fat": "g", "carbs": "g", "fiber": "g", "sugar": "g",
    "starch": "g", "water": "g",
    "saturatedFat": "g", "monounsaturatedFat": "g", "polyunsaturatedFat": "g",
    "transFat": "g", "omega3": "g", "omega6": "g",
    "cholesterol": "mg", "calcium": "mg", "iron": "mg", "magnesium": "mg",
    "phosphorus": "mg", "potassium": "mg", "sodium": "mg", "zinc": "mg",
    "copper": "mg", "vitaminE": "mg", "vitaminC": "mg",
    "vitaminB1": "mg", "vitaminB2": "mg", "vitaminB3": "mg", "vitaminB6": "mg",
    "selenium": "ug", "vitaminA": "ug", "betaCarotene": "ug",
    "vitaminD": "ug", "vitaminB9": "ug", "vitaminB12": "ug",
}

TO_GRAM = {
    "g": 1.0, "mg": 1e-3, "µg": 1e-6, "ug": 1e-6, "mcg": 1e-6,
    "mg-ate": 1e-3,   # витамин E в мг альфа-токоферолового эквивалента
    "rae": 1e-6,      # витамин A в мкг ретиноловых эквивалентов
    "re": 1e-6,
}
FROM_GRAM = {"g": 1.0, "mg": 1e3, "ug": 1e6}


def convert(value, unit, target):
    """Значение в канонической единице приложения; None — пересчитать нечем."""
    if target == "kcal":
        return value if unit.strip().lower() == "kcal" else None
    factor = TO_GRAM.get(unit.strip().lower())
    if factor is None:
        return None
    return value * factor * FROM_GRAM[target]


def load(name, locale="en"):
    url = API.format(locale=locale, name=name)
    try:
        with urllib.request.urlopen(url, timeout=180) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError) as error:
        sys.exit("Не удалось скачать %s: %s" % (url, error))


def nutrients_of(food, meta_by_id, unmapped):
    values = {}
    for c in food.get("constituents", []):
        if "quantity" not in c:
            continue
        meta = meta_by_id.get(c["nutrientId"])
        if meta is None:
            continue
        euro = meta.get("euroFirId")
        key = EUROFIR.get(euro)
        if key is None:
            # Отдельные жирные кислоты (F18:2, F20:5 и т.п.) не храним — есть суммы.
            if euro not in IGNORED and not (euro or "").startswith(("F1", "F2")):
                unmapped[euro] = unmapped.get(euro, 0) + 1
            continue
        value = convert(c["quantity"], c.get("unit") or meta.get("unit") or "", CANONICAL[key])
        # Отрицательных значений быть не должно, но мусор в данных встречается.
        if value is None or value < 0:
            continue
        values[key] = round(value, 4)

    # Калории лежат отдельным полем, а не среди constituents.
    calories = food.get("calories")
    if "calories" not in values and isinstance(calories, dict):
        quantity = calories.get("quantity")
        if quantity is not None:
            values["calories"] = round(float(quantity), 4)
    return values


def servings_of(food):
    result = []
    for portion in food.get("portions", []):
        name, weight = portion.get("portionName"), portion.get("quantity")
        # Меры не в граммах пересчитать нечем.
        if not name or not weight or portion.get("unit") != "g":
            continue
        result.append({
            "id": "mvt_%s_%s" % (food["foodId"], portion.get("id") or name),
            "name": name,
            "weight": round(float(weight), 2),
        })
    return result


def build():
    meta_by_id = {n["nutrientId"]: n for n in load("nutrients")["nutrients"]}
    foods = load("foods")["foods"]
    # Норвежские названия кладём рядом с английскими: индекс ищет по всем именам
    # сразу, а показывает то, что подходит языку телефона.
    norwegian = {f["foodId"]: f["foodName"] for f in load("foods", "nb")["foods"]}

    items, skipped, unmapped = [], 0, {}
    for food in foods:
        values = nutrients_of(food, meta_by_id, unmapped)
        # Без БЖУ запись бесполезна: по ней не посчитать ни приём пищи, ни цели.
        if not {"protein", "fat", "carbs"} <= values.keys():
            skipped += 1
            continue

        names = {"en": food["foodName"]}
        nb = norwegian.get(food["foodId"])
        if nb and nb != food["foodName"]:
            names["nb"] = nb

        items.append({
            "id": "mvt_%s" % food["foodId"],
            "names": names,
            "nutrients": values,
            "servings": servings_of(food),
        })
    return items, skipped, unmapped


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", nargs="?", default=DEFAULT_OUTPUT, help="куда записать JSON")
    args = parser.parse_args()

    items, skipped, unmapped = build()
    if not items:
        sys.exit("Ничего не собралось — похоже, формат источника изменился.")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
        f.write("\n")

    average = sum(len(i["nutrients"]) for i in items) / len(items)
    print("Записано %s" % args.output)
    print("  продуктов: %d (пропущено без БЖУ: %d)" % (len(items), skipped))
    print("  нутриентов в среднем: %.1f" % average)
    print("  с мерами: %d" % sum(1 for i in items if i["servings"]))
    print("  с норвежским названием: %d" % sum(1 for i in items if "nb" in i["names"]))
    if unmapped:
        top = sorted(unmapped.items(), key=lambda kv: -kv[1])[:10]
        # Появилось после обновления таблицы — возможно, стоит добавить в EUROFIR.
        print("  не сопоставлено: %s" % ", ".join("%s×%d" % t for t in top))


if __name__ == "__main__":
    main()
