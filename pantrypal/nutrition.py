"""Nutrition lookup, macro/micro summation, cooking adjustments, and DV calculations."""
import json
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from pantrypal.config import (
    COOKING_ADDED_OIL,
    COOKING_RETENTION,
    DAILY_VALUES_PATH,
    NUTRITION_PATH,
)
from pantrypal.models import IngredientItem, NutritionInfo


@lru_cache(maxsize=1)
def load_nutrition_db() -> Dict[str, Any]:
    """Load the full nutrition database from nutrition.json."""
    if not NUTRITION_PATH.exists():
        return {}
    with open(NUTRITION_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_daily_values() -> Dict[str, float]:
    """Load standard reference daily values."""
    if not DAILY_VALUES_PATH.exists():
        return {}
    with open(DAILY_VALUES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_ingredient_nutrition(ingredient_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve raw nutrition profile per 100g for an ingredient."""
    db = load_nutrition_db()
    return db.get(ingredient_id.strip().lower())


def sum_nutrition(
    ingredients: List[IngredientItem],
    method: str = "pan_fry",
    servings: int = 1,
    scale: float = 1.0,
) -> NutritionInfo:
    """
    Sum macros and micros for a list of ingredient items.
    Applies portion scale factor and cooking adjustments (added oil and retention).
    
    Formula per ingredient:
        nutrient = (grams * scale / 100) * nutrient_per_100g
    """
    db = load_nutrition_db()
    servings_count = max(1, servings)

    total_kcal = 0.0
    total_protein = 0.0
    total_carbs = 0.0
    total_fat = 0.0
    total_fiber = 0.0
    total_sugar = 0.0
    total_micros: Dict[str, float] = {
        "sodium_mg": 0.0,
        "potassium_mg": 0.0,
        "calcium_mg": 0.0,
        "iron_mg": 0.0,
        "magnesium_mg": 0.0,
        "zinc_mg": 0.0,
        "vit_a_ug": 0.0,
        "vit_c_mg": 0.0,
        "vit_d_ug": 0.0,
        "vit_b12_ug": 0.0,
    }

    # Track if recipe already contains an explicit fat source
    has_explicit_fat = any(
        item.role.lower() == "fat" or item.id in {"olive_oil", "butter", "ghee", "beef_tallow", "coconut_oil"}
        for item in ingredients
    )

    for item in ingredients:
        raw_info = db.get(item.id.strip().lower())
        if not raw_info:
            continue

        item_grams = item.grams * scale
        factor = item_grams / 100.0

        total_kcal += raw_info.get("kcal", 0.0) * factor
        total_protein += raw_info.get("protein", 0.0) * factor
        total_carbs += raw_info.get("carbs", 0.0) * factor
        total_fat += raw_info.get("fat", 0.0) * factor
        total_fiber += raw_info.get("fiber", 0.0) * factor
        total_sugar += raw_info.get("sugar", 0.0) * factor

        micros = raw_info.get("micros", {})
        for key in total_micros:
            total_micros[key] += micros.get(key, 0.0) * factor

    # Cooking adjustment: added oil
    # Pan fry only adds oil if no explicit fat is in the ingredients
    added_oil_g = COOKING_ADDED_OIL.get(method.strip().lower(), 0.0)
    if method == "pan_fry" and has_explicit_fat:
        added_oil_g = 0.0  # Already declared in recipe

    if added_oil_g > 0:
        oil_added_scaled = added_oil_g * scale
        # Pure oil ≈ 8.84 kcal/g and 1g fat/g
        total_fat += oil_added_scaled
        total_kcal += oil_added_scaled * 8.84

    # Cooking adjustment: nutrient retention
    retention_rules = COOKING_RETENTION.get(method.strip().lower(), {})
    for nutrient, retention_factor in retention_rules.items():
        if nutrient in total_micros:
            total_micros[nutrient] *= retention_factor

    return NutritionInfo(
        kcal=round(total_kcal, 1),
        protein=round(total_protein, 1),
        carbs=round(total_carbs, 1),
        fat=round(total_fat, 1),
        fiber=round(total_fiber, 1),
        sugar=round(total_sugar, 1),
        micros={k: round(v, 2) for k, v in total_micros.items()},
    )


def calculate_micro_percentages(
    micros: Dict[str, float],
    meals_per_day: int = 3,
) -> Dict[str, float]:
    """
    Calculate % of pro-rated Daily Value for each micronutrient in this meal.
    Pro-rated target = Daily Value / meals_per_day.
    """
    dv = load_daily_values()
    meals_count = max(1, meals_per_day)
    percentages: Dict[str, float] = {}

    for nutrient, amount in micros.items():
        standard_dv = dv.get(nutrient)
        if standard_dv and standard_dv > 0:
            prorated_dv = standard_dv / meals_count
            pct = (amount / prorated_dv) * 100.0
            percentages[nutrient] = round(pct, 1)
        else:
            percentages[nutrient] = 0.0

    return percentages
