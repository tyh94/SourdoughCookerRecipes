#!/usr/bin/env python3
"""USDA FoodData Central -> индекс продуктов приложения.

Переехал из FamilyFoodDiary/NutritionAPI: логика сборки индексов живёт рядом
с самими индексами.

    python3 usda.py

Свежий релиз Foundation Foods скрипт находит сам на странице загрузок и качает в
память: сам дамп в репозиторий не кладётся, нужен только результат.

Названия переводятся на русский через локальный LibreTranslate, поэтому перед запуском:

    docker run -p 5001:5000 libretranslate/libretranslate
"""
import argparse
import io
import json
import re
import sys
import urllib.error
import urllib.request
import zipfile

import time
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum

LT_URL = "http://localhost:5001/translate"

DOWNLOADS_PAGE = "https://fdc.nal.usda.gov/download-datasets"
DATASET_URL = "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_foundation_food_json_%s.zip"
DATASET_RE = re.compile(r"FoodData_Central_foundation_food_json_(\d{4}-\d{2}-\d{2})\.zip")
DEFAULT_OUTPUT = "foods.nutrients.json"

class NutrientType(Enum):
    # Макронутриенты
    CALORIES = "calories"
    PROTEIN = "protein"
    FAT = "fat"
    CARBS = "carbs"
    FIBER = "fiber"
    SUGAR = "sugar"
    FRUCTOSE = "fructose"
    LACTOSE = "lactose"
    
    # Минералы
    CALCIUM = "calcium"
    IRON = "iron"
    MAGNESIUM = "magnesium"
    PHOSPHORUS = "phosphorus"
    POTASSIUM = "potassium"
    SODIUM = "sodium"
    ZINC = "zinc"
    COPPER = "copper"
    MANGANESE = "manganese"
    SELENIUM = "selenium"
    FLUORIDE = "fluoride"
    SULFUR = "sulfur"
    CHLORINE = "chlorine"
    COBALT = "cobalt"
    MOLYBDENUM = "molybdenum"
    CHROMIUM = "chromium"
    
    # Витамины
    VITAMIN_A = "vitaminA"
    VITAMIN_C = "vitaminC"
    VITAMIN_D = "vitaminD"
    VITAMIN_D2 = "vitaminD2"
    VITAMIN_D3 = "vitaminD3"
    VITAMIN_E = "vitaminE"
    VITAMIN_K = "vitaminK"
    VITAMIN_B1 = "vitaminB1"
    VITAMIN_B2 = "vitaminB2"
    VITAMIN_B3 = "vitaminB3"
    VITAMIN_B4 = "vitaminB4"
    VITAMIN_B5 = "vitaminB5"
    VITAMIN_B6 = "vitaminB6"
    VITAMIN_B9 = "vitaminB9"
    VITAMIN_B12 = "vitaminB12"
    FOLIC_ACID = "folicAcid"
    
    # Дополнительные
    CHOLESTEROL = "cholesterol"
    OMEGA_3 = "omega3"
    OMEGA_6 = "omega6"
    BETA_CAROTENE = "betaCarotene"
    ALPHA_CAROTENE = "alphaCarotene"

    # Прочее
    WATER = "water"
    ASH = "ash"
    TRANS_FAT = "transFat"
    SATURATED_FAT = "saturatedFat"
    MONOUNSATURATED_FAT = "monounsaturatedFat"
    POLYUNSATURATED_FAT = "polyunsaturatedFat"
    STARCH = "starch"

# Маппинг названий нутриентов USDA к нашим типам
NUTRIENT_MAPPING = {
    # Калории
    "Energy": NutrientType.CALORIES,
    "Energy (Atwater General Factors)": NutrientType.CALORIES,
    
    # Макронутриенты
    "Protein": NutrientType.PROTEIN,
    "Total lipid (fat)": NutrientType.FAT,
    "Carbohydrate, by difference": NutrientType.CARBS,
    "Fiber, total dietary": NutrientType.FIBER,
    "Sugars, Total": NutrientType.SUGAR,
    "Fructose": NutrientType.FRUCTOSE,
    "Lactose": NutrientType.LACTOSE,
    
    # Минералы
    "Calcium, Ca": NutrientType.CALCIUM,
    "Iron, Fe": NutrientType.IRON,
    "Magnesium, Mg": NutrientType.MAGNESIUM,
    "Phosphorus, P": NutrientType.PHOSPHORUS,
    "Potassium, K": NutrientType.POTASSIUM,
    "Sodium, Na": NutrientType.SODIUM,
    "Zinc, Zn": NutrientType.ZINC,
    "Copper, Cu": NutrientType.COPPER,
    "Manganese, Mn": NutrientType.MANGANESE,
    "Selenium, Se": NutrientType.SELENIUM,
    "Fluoride, F": NutrientType.FLUORIDE,
    "Sulfur, S": NutrientType.SULFUR,
    "Chlorine, Cl": NutrientType.CHLORINE,
    "Cobalt, Co": NutrientType.COBALT,
    "Molybdenum, Mo": NutrientType.MOLYBDENUM,
    "Chromium, Cr": NutrientType.CHROMIUM,

    # Витамины
    "Vitamin A, RAE": NutrientType.VITAMIN_A,
    "Vitamin C, total ascorbic acid": NutrientType.VITAMIN_C,
    "Vitamin D (D2 + D3)": NutrientType.VITAMIN_D,
    "Vitamin D2 (ergocalciferol)": NutrientType.VITAMIN_D2,
    "Vitamin D3 (cholecalciferol)": NutrientType.VITAMIN_D3,
    "Vitamin E (alpha-tocopherol)": NutrientType.VITAMIN_E,
    "Vitamin K (phylloquinone)": NutrientType.VITAMIN_K,
    "Thiamin": NutrientType.VITAMIN_B1,
    "Riboflavin": NutrientType.VITAMIN_B2,
    "Niacin": NutrientType.VITAMIN_B3,
    "Choline, total": NutrientType.VITAMIN_B4,
    "Pantothenic acid": NutrientType.VITAMIN_B5,
    "Vitamin B-6": NutrientType.VITAMIN_B6,
    "Folate, total": NutrientType.VITAMIN_B9,
    "Vitamin B-12": NutrientType.VITAMIN_B12,
    "Folic acid": NutrientType.FOLIC_ACID,
    
    # Дополнительные
    "Cholesterol": NutrientType.CHOLESTEROL,
    "Fatty acids, total saturated": NutrientType.SATURATED_FAT,
    "Fatty acids, total monounsaturated": NutrientType.MONOUNSATURATED_FAT,
    "Fatty acids, total polyunsaturated": NutrientType.POLYUNSATURATED_FAT,
    "PUFA 18:3 n-3 c,c,c (ALA)": NutrientType.OMEGA_3,
    "PUFA 18:2 n-6 c,c": NutrientType.OMEGA_6,
    "Carotene, beta": NutrientType.BETA_CAROTENE,
    "Carotene, alpha": NutrientType.ALPHA_CAROTENE,

    # Прочее
    "Water": NutrientType.WATER,
    "Ash": NutrientType.ASH,
    "Fatty acids, total trans": NutrientType.TRANS_FAT,
    "Starch": NutrientType.STARCH,
}

@dataclass
class Serving:
    id: str
    name: str
    weight: float  # Вес в граммах
    description: str = ""
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "weight": self.weight,
            "description": self.description
        }

class TranslationError(RuntimeError):
    """Перевод не удался."""


def translate_text(text: str, source: str = "auto", target: str = "ru", max_retries: int = 3) -> str:
    """Переводит текст через LibreTranslate.

    Падает, если не смог: английское название, молча оставшееся в поле `ru`,
    доедет до приложения и будет выглядеть как настоящий перевод.
    """
    if not text or text.strip() == "":
        return text
    
    payload = {
        "q": text,
        "source": source,
        "target": target,
        "format": "text",
        "alternatives": 0,
        "api_key": ""
    }
    
    request = urllib.request.Request(
        LT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    last_error = "неизвестно"
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                translated = json.load(response).get("translatedText")
            if translated:
                return translated
            last_error = "в ответе нет translatedText"
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}: {e.read()[:100].decode('utf-8', 'replace')}"
            if e.code == 429:
                time.sleep(2 ** attempt)  # Экспоненциальная задержка
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                time.sleep(1)
    
    raise TranslationError(f"не перевести «{text[:60]}»: {last_error}")


def check_translator():
    """Проверяем перевод до скачивания дампа, чтобы не падать на середине."""
    try:
        translate_text("water")
    except TranslationError as error:
        sys.exit(
            f"LibreTranslate не отвечает — {error}\n"
            "Подними его: docker run -p 5001:5000 libretranslate/libretranslate"
        )


def latest_release() -> str:
    """Дата свежего релиза Foundation Foods со страницы загрузок."""
    try:
        with urllib.request.urlopen(DOWNLOADS_PAGE, timeout=60) as response:
            page = response.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError) as error:
        sys.exit(f"Не открылась страница загрузок {DOWNLOADS_PAGE}: {error}")

    # Даты в формате ISO, поэтому свежая — последняя по алфавиту.
    releases = sorted(set(DATASET_RE.findall(page)))
    if not releases:
        sys.exit("На странице загрузок нет Foundation Foods в JSON — поменялась разметка.")
    return releases[-1]


def download_foods() -> List[Dict]:
    """Качает свежий релиз и достаёт из архива единственный JSON."""
    release = latest_release()
    url = DATASET_URL % release
    print(f"Качаю релиз {release}: {url}")
    try:
        with urllib.request.urlopen(url, timeout=300) as response:
            archive = zipfile.ZipFile(io.BytesIO(response.read()))
    except (urllib.error.URLError, TimeoutError, zipfile.BadZipFile) as error:
        sys.exit(f"Не скачался {url}: {error}")

    names = [name for name in archive.namelist() if name.endswith(".json")]
    if not names:
        sys.exit(f"В архиве {url} нет JSON — поменялся формат выгрузки.")
    with archive.open(names[0]) as raw:
        return foods_of(json.load(raw))


def read_foods(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        return foods_of(json.load(f))


def foods_of(data: Dict) -> List[Dict]:
    """Продукты из выгрузки.

    В хвосте выгрузки попадаются пустые записи (в релизе 2026-04-30 их 32) —
    пропускаем, но вслух: если однажды пустой окажется вся выгрузка, это будет видно.
    """
    foods = data.get("FoundationFoods")
    if not foods:
        sys.exit("В дампе нет FoundationFoods — поменялся формат выгрузки.")
    real = [food for food in foods if isinstance(food, dict)]
    if len(real) != len(foods):
        print(f"Пустых записей: {len(foods) - len(real)} из {len(foods)} — пропускаю")
    return real

def extract_nutrients(food_data: Dict) -> Dict[str, float]:
    """Извлекает нутриенты из данных USDA"""
    nutrients = {}
    
    if "foodNutrients" not in food_data:
        return nutrients
    
    for nutrient_entry in food_data["foodNutrients"]:
        nutrient_info = nutrient_entry.get("nutrient", {})
        nutrient_name = nutrient_info.get("name", "")
        amount = nutrient_entry.get("amount", 0)
        
        # Пропускаем если нет значения
        if amount is None or amount == 0:
            continue
        
        # Ищем соответствие в маппинге
        for usda_name, nutrient_type in NUTRIENT_MAPPING.items():
            if nutrient_name.startswith(usda_name):
                # Конвертируем в нужный формат
                nutrients[nutrient_type.value] = float(amount)
                break
    
    # Особый случай для калорий (может быть в kJ или kcal)
    # Ищем калории в кДж и конвертируем в ккал
    for nutrient_entry in food_data["foodNutrients"]:
        nutrient_info = nutrient_entry.get("nutrient", {})
        nutrient_name = nutrient_info.get("name", "")
        unit = nutrient_info.get("unitName", "")
        amount = nutrient_entry.get("amount", 0)
        
        if nutrient_name == "Energy" and unit == "kJ" and amount:
            # Конвертируем kJ в kcal (1 kcal = 4.184 kJ)
            kcal = float(amount) / 4.184
            nutrients[NutrientType.CALORIES.value] = kcal
            break
        elif nutrient_name == "Energy" and unit == "kcal" and amount:
            nutrients[NutrientType.CALORIES.value] = float(amount)
            break
    
    return nutrients

def extract_servings(food_data: Dict) -> List[Serving]:
    """Извлекает порции из данных USDA"""
    servings = []
    
    if "foodPortions" not in food_data:
        return servings
    
    for idx, portion in enumerate(food_data["foodPortions"]):
        measure_unit = portion.get("measureUnit", {})
        name = measure_unit.get("name", "")
        abbreviation = measure_unit.get("abbreviation", "")
        weight = portion.get("gramWeight", 0)
        
        # Создаем описание порции
        value = portion.get("value", 1)
        description = f"{value} {abbreviation or name}"
        
        serving = Serving(
            id=f"{food_data.get('fdcId', '')}_{idx}",
            name=name,
            weight=float(weight),
            description=description
        )
        servings.append(serving)
    
    return servings

def convert(foods: List[Dict], output_file: str):
    """Основная функция конвертации"""
    results = []
    total_foods = len(foods)
    
    print(f"Найдено продуктов: {total_foods}")
    
    for idx, food_data in enumerate(foods, 1):
        print(f"Обработка продукта {idx}/{total_foods}: {food_data.get('description', 'N/A')}")
        
        # Получаем ID
        fdc_id = str(food_data.get("fdcId", ""))
        
        # Получаем название на английском
        name_en = food_data.get("description", "")
        
        # Переводим название
        name_ru = translate_text(name_en)
        
        # Извлекаем нутриенты
        nutrients = extract_nutrients(food_data)
        
        # Извлекаем порции
        servings = extract_servings(food_data)
        
        # Переводим названия порций
        translated_servings = []
        for serving in servings:
            # Переводим название порции если нужно
            translated_name = translate_text(serving.name) if serving.name else serving.name
            translated_desc = translate_text(serving.description) if serving.description else serving.description
            
            translated_servings.append({
                "id": serving.id,
                "name": translated_name,
                "weight": serving.weight,
                "description": translated_desc
            })
        
        # Создаем результат.
        # names — словарь «код языка → название»; при добавлении нового
        # языка просто дописывается ключ ("de", "es", ...).
        results.append({
            "id": fdc_id,
            "names": {
                "ru": name_ru,
                "en": name_en,
            },
            "nutrients": nutrients,
            "servings": translated_servings,
            "metadata": {
                "original_name": name_en,
                "foodCategory": food_data.get("foodCategory", {}).get("description", ""),
                "dataType": food_data.get("dataType", "")
            }
        })
        
        # Небольшая задержка чтобы не перегружать сервер перевода
        if idx % 5 == 0:
            time.sleep(0.5)
    
    # Сохраняем результат
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\nГотово! Обработано продуктов: {len(results)}")
    print(f"Результат сохранен в: {output_file}")
    
    # Статистика
    print("\nСтатистика:")
    print(f"  Всего нутриентов найдено: {sum(len(r['nutrients']) for r in results)}")
    print(f"  Всего порций найдено: {sum(len(r['servings']) for r in results)}")

def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", nargs="?", default=DEFAULT_OUTPUT, help="куда записать JSON")
    parser.add_argument("--input", help="взять уже скачанный дамп вместо свежего релиза")
    args = parser.parse_args()

    check_translator()
    foods = read_foods(args.input) if args.input else download_foods()
    if not foods:
        sys.exit("В дампе нет продуктов — похоже, поменялся формат выгрузки.")
    convert(foods, args.output)


if __name__ == "__main__":
    main()