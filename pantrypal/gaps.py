"""Dietary nutrient gap analysis and advisories."""
from typing import List

from pantrypal.models import NutritionInfo
from pantrypal.nutrition import calculate_micro_percentages

MICRO_DISPLAY_NAMES = {
    "sodium_mg": "Sodium",
    "potassium_mg": "Potassium",
    "calcium_mg": "Calcium",
    "iron_mg": "Iron",
    "magnesium_mg": "Magnesium",
    "zinc_mg": "Zinc",
    "vit_a_ug": "Vitamin A",
    "vit_c_mg": "Vitamin C",
    "vit_d_ug": "Vitamin D",
    "vit_b12_ug": "Vitamin B12",
}


def check_nutrient_gaps(
    nutrition: NutritionInfo,
    diet_mode: str,
    meals_per_day: int = 3,
) -> List[str]:
    """
    Compare meal micronutrients against pro-rated Daily Values.
    Flag any micro below 30% of its pro-rated value with static advisory text.
    """
    gaps: List[str] = []
    pcts = calculate_micro_percentages(nutrition.micros, meals_per_day)

    under_threshold = [
        MICRO_DISPLAY_NAMES.get(k, k)
        for k, pct in pcts.items()
        if pct < 30.0
    ]

    mode = diet_mode.strip().lower()
    if mode == "high_protein_carnivore":
        # Fiber is always 0 on carnivore
        if nutrition.fiber < 1.0:
            gaps.append("Diet Notice: Zero dietary fiber is typical for carnivore protocols.")
        if pcts.get("vit_c_mg", 0.0) < 30.0:
            gaps.append("Micronutrient Gap: Vitamin C is low in this meal. Incorporate fresh liver or light seafood to support micronutrient density.")
        if under_threshold:
            other_gaps = [m for m in under_threshold if m not in {"Vitamin C"}]
            if other_gaps:
                gaps.append(f"Low meal micronutrients (<30% pro-rated DV): {', '.join(other_gaps[:3])}.")

    elif mode == "light_oil_healthy":
        if under_threshold:
            gaps.append(f"Lower meal micronutrients (<30% pro-rated DV): {', '.join(under_threshold[:3])}.")

    return gaps
