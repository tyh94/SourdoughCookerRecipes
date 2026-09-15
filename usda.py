#!/usr/bin/env python3
"""USDA FoodData Central -> индекс продуктов приложения.

Переехал из FamilyFoodDiary/NutritionAPI: логика сборки индексов живёт рядом
с самими индексами.

    python3 usda.py FoodData_Central_foundation_food_json_2025-12-18.json foods.nutrients.json

Исходник качается с https://fdc.nal.usda.gov/download-datasets (Foundation Foods, JSON)
и в репозиторий не кладётся: 6.8 МБ входных данных, из которых нужен только результат.

Названия переводятся на русский через локальный LibreTranslate, поэтому перед запуском:

    docker run -p 5001:5000 libretranslate/libretranslate

Зависимости: pip install requests
"""
import json
import sys

import requests
import time
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum

LT_URL = "http://localhost:5001/translate"

DEFAULT_INPUT = "FoodData_Central_foundation_food_json_2025-12-18.json"
DEFAULT_OUTPUT = "foods.nutrients.json"

class NutrientType(Enum):
    # Макронутриенты
    CALORIES = "calories"
    PROTEIN = "protein"
    FAT = "fat"
    CARBS = "carbs"
    FIBER = "fiber"
    SUGAR = "sugar"
    
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

def translate_text(text: str, source: str = "auto", target: str = "ru", max_retries: int = 3) -> str:
    """Переводит текст через LibreTranslate"""
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
    
    for attempt in range(max_retries):
        try:
            response = requests.post(LT_URL, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                return result.get("translatedText", text)
            elif response.status_code == 429:
                time.sleep(2 ** attempt)  # Экспоненциальная задержка
            else:
                print(f"Ошибка HTTP {response.status_code}: {response.text[:100]}")
        except Exception as e:
            print(f"Ошибка перевода '{text[:50]}...': {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
    
    return text

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

def convert_usda_to_target_format(input_file: str, output_file: str):
    """Основная функция конвертации"""
    # Загружаем данные USDA
    with open(input_file, 'r', encoding='utf-8') as f:
        usda_data = json.load(f)
    
    results = []
    
    if "FoundationFoods" not in usda_data:
        print("Ошибка: Не найден ключ 'FoundationFoods' в JSON")
        return
    
    foods = usda_data["FoundationFoods"]
    total_foods = len(foods)
    
    print(f"Найдено продуктов: {total_foods}")
    
    for idx, food_data in enumerate(foods, 1):
        try:
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
            result = {
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
            }
            
            results.append(result)
            
            # Небольшая задержка чтобы не перегружать сервер перевода
            if idx % 5 == 0:
                time.sleep(0.5)
                
        except Exception as e:
            print(f"Ошибка при обработке продукта {idx}: {e}")
            continue
    
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
    """Основная функция"""
    # Пути приходят аргументами: скрипт запускается из корня репозитория.
    input_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT
    output_file = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUTPUT
    
    try:
        convert_usda_to_target_format(input_file, output_file)
    except FileNotFoundError:
        print(f"Ошибка: Файл {input_file} не найден")
    except json.JSONDecodeError:
        print(f"Ошибка: Неверный формат JSON в файле {input_file}")
    except Exception as e:
        print(f"Неизвестная ошибка: {e}")

if __name__ == "__main__":
    main()