"""Portion scaling and carnivore fat-to-protein ratio balancing."""
from typing import List, Optional, Tuple

from pantrypal.config import (
    CARNIVORE_FAT_PROTEIN_RATIO_MAX,
    CARNIVORE_FAT_PROTEIN_RATIO_MIN,
    SCALE_MAX,
    SCALE_MIN,
)
from pantrypal.models import IngredientItem, Recipe
from pantrypal.nutrition import get_ingredient_nutrition, sum_nutrition


def compute_scale_factor(recipe: Recipe, meal_target_kcal: float) -> Tuple[float, Optional[str]]:
    """
    Compute scale factor based on calorie target:
    scale = meal_target_kcal / (recipe_kcal / servings)
    Clamped to [SCALE_MIN, SCALE_MAX] (0.5 to 2.5).
    Returns (clamped_scale, warning_message).
    """
    base_nutrition = sum_nutrition(recipe.ingredients, recipe.method, recipe.servings, scale=1.0)
    servings = max(1, recipe.servings)
    kcal_per_serving = max(1.0, base_nutrition.kcal / servings)

    raw_scale = meal_target_kcal / kcal_per_serving
    clamped_scale = max(SCALE_MIN, min(SCALE_MAX, raw_scale))
    clamped_scale = round(clamped_scale, 2)

    warning = None
    if raw_scale < SCALE_MIN:
        warning = f"Portion scaled up to minimum limit {SCALE_MIN}x (target required {raw_scale:.2f}x)."
    elif raw_scale > SCALE_MAX:
        warning = f"Portion scaled down to maximum limit {SCALE_MAX}x (target required {raw_scale:.2f}x)."

    return clamped_scale, warning


def scale_and_balance_ingredients(
    recipe: Recipe,
    scale: float,
    diet_mode: str,
) -> List[IngredientItem]:
    """
    Scale ingredient gram quantities.
    For high_protein_carnivore, balance fat-containing animal ingredients
    to preserve fat-to-protein ratio between 0.8:1 and 1.2:1 where possible.
    """
    mode = diet_mode.strip().lower()

    # Step 1: Default linear scaling
    scaled_items: List[IngredientItem] = []
    for item in recipe.ingredients:
        scaled_items.append(
            IngredientItem(
                id=item.id,
                grams=round(item.grams * scale, 1),
                role=item.role,
                essential=item.essential,
                name=item.name,
            )
        )

    if mode != "high_protein_carnivore":
        return scaled_items

    # Step 2: Carnivore fat-to-protein ratio check
    total_fat_g = 0.0
    total_protein_g = 0.0
    fat_item_indices = []

    for idx, item in enumerate(scaled_items):
        nutr = get_ingredient_nutrition(item.id)
        if not nutr:
            continue
        factor = item.grams / 100.0
        total_fat_g += nutr.get("fat", 0.0) * factor
        total_protein_g += nutr.get("protein", 0.0) * factor

        # Identify fat booster ingredients (butter, tallow, ghee)
        if item.id in {"butter", "beef_tallow", "ghee"} or item.role == "fat":
            fat_item_indices.append(idx)

    if total_protein_g <= 0.0 or not fat_item_indices:
        return scaled_items

    current_ratio = total_fat_g / total_protein_g

    # If fat is too low (< 0.8) and we have dedicated fat ingredients, increase fat
    if current_ratio < CARNIVORE_FAT_PROTEIN_RATIO_MIN:
        needed_fat_g = (CARNIVORE_FAT_PROTEIN_RATIO_MIN * total_protein_g) - total_fat_g
        # Add needed fat spread across fat ingredients
        addition_per_item = needed_fat_g / len(fat_item_indices)
        for idx in fat_item_indices:
            scaled_items[idx].grams = round(scaled_items[idx].grams + addition_per_item, 1)

    # If fat is too high (> 1.2), reduce fat ingredients
    elif current_ratio > CARNIVORE_FAT_PROTEIN_RATIO_MAX:
        excess_fat_g = total_fat_g - (CARNIVORE_FAT_PROTEIN_RATIO_MAX * total_protein_g)
        reduction_per_item = excess_fat_g / len(fat_item_indices)
        for idx in fat_item_indices:
            new_grams = max(2.0, scaled_items[idx].grams - reduction_per_item)
            scaled_items[idx].grams = round(new_grams, 1)

    return scaled_items
