"""Pantry coverage scoring and recipe ranking logic."""
from typing import Dict, List, Optional, Tuple

from pantrypal.models import IngredientItem, Recipe
from pantrypal.units import is_staple


def calculate_coverage(
    ingredients: List[IngredientItem],
    pantry: Dict[str, dict],
) -> Tuple[float, List[IngredientItem], List[IngredientItem]]:
    """
    Calculate pantry coverage score and identify available and missing ingredients.
    Formula:
        coverage = sum(min(available_g, required_g)) / sum(required_g)
        (excluding staples from the denominator)
    Returns:
        (coverage_ratio, available_items, missing_items)
    """
    total_required_non_staple = 0.0
    total_available_covered = 0.0
    available_items: List[IngredientItem] = []
    missing_items: List[IngredientItem] = []

    for item in ingredients:
        pantry_entry = pantry.get(item.id.strip().lower(), {})
        is_item_staple = is_staple(item.id) or bool(pantry_entry.get("always_have", False))

        required_g = item.grams

        if is_item_staple:
            # Staples are assumed 100% available and not counted against non-staple mass
            available_items.append(item)
            continue

        total_required_non_staple += required_g
        pantry_g = float(pantry_entry.get("quantity_g", 0.0))

        if pantry_g >= required_g:
            total_available_covered += required_g
            available_items.append(item)
        else:
            total_available_covered += min(pantry_g, required_g)
            missing_items.append(item)

    if total_required_non_staple <= 0.0:
        coverage_score = 1.0
    else:
        coverage_score = total_available_covered / total_required_non_staple

    coverage_score = round(min(1.0, max(0.0, coverage_score)), 3)
    return coverage_score, available_items, missing_items


def rank_recipes(
    candidates: List[Tuple[Recipe, float, List[IngredientItem], float]],
) -> List[Tuple[Recipe, float, List[IngredientItem], float]]:
    """
    Rank candidate recipes based on multi-tier scoring:
    1. Coverage descending (highest coverage first)
    2. Essential gaps ascending (fewer missing essential ingredients)
    3. Calorie delta ascending (closest to target kcal)
    
    candidates item: (recipe, coverage, missing_items, calorie_delta)
    """
    def sort_key(item):
        recipe, coverage, missing, delta_kcal = item
        essential_missing_count = sum(1 for m in missing if m.essential)
        # Negative coverage for descending sort
        return (-coverage, essential_missing_count, abs(delta_kcal))

    return sorted(candidates, key=sort_key)
