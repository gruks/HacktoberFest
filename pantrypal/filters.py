"""Utensil constraint and diet mode filtering logic."""
import json
from functools import lru_cache
from typing import List, Set

from pantrypal.config import RECIPES_PATH
from pantrypal.models import Recipe
from pantrypal.nutrition import load_nutrition_db
from pantrypal.units import is_staple


@lru_cache(maxsize=1)
def load_all_recipes() -> List[Recipe]:
    """Load and parse all recipes from recipes.json."""
    if not RECIPES_PATH.exists():
        return []
    with open(RECIPES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Recipe(**r) for r in data]


def check_utensils(recipe: Recipe, owned_utensils: Set[str]) -> bool:
    """
    Check if owned utensils satisfy the recipe's utensil requirements.
    `requires_any` is a list of alternatives. Each alternative is a list of utensils.
    A recipe passes if ANY alternative is completely satisfied by owned_utensils.
    """
    if not recipe.requires_any:
        return True

    owned_clean = {u.strip().lower() for u in owned_utensils}
    for alternative in recipe.requires_any:
        alt_set = {req.strip().lower() for req in alternative}
        if alt_set.issubset(owned_clean):
            return True
    return False


def check_diet_mode(recipe: Recipe, diet_mode: str) -> bool:
    """
    Filter recipes strictly based on diet mode:
    - 'high_protein_carnivore':
        * recipe.carnivore_ok must be True
        * every non-staple ingredient must have animal_based == True
    - 'light_oil_healthy':
        * cooking method must not be deep_fry
        * oil/fat declared in recipe must be <= 10g per serving
    """
    mode = diet_mode.strip().lower()
    db = load_nutrition_db()

    if mode == "high_protein_carnivore":
        if not recipe.carnivore_ok:
            return False
        for item in recipe.ingredients:
            if is_staple(item.id):
                continue
            nutr = db.get(item.id)
            if not nutr or not nutr.get("animal_based", False):
                return False
        return True

    elif mode == "light_oil_healthy":
        if recipe.method.lower() == "deep_fry":
            return False

        # Calculate oil/fat ingredients per serving
        oil_grams = 0.0
        for item in recipe.ingredients:
            if item.id in {"olive_oil", "cooking_spray", "sesame_oil", "coconut_oil"}:
                oil_grams += item.grams

        servings = max(1, recipe.servings)
        if (oil_grams / servings) > 10.0:
            return False
        return True

    return True


def filter_recipes(
    recipes: List[Recipe],
    owned_utensils: Set[str],
    diet_mode: str,
) -> List[Recipe]:
    """Filter candidate recipes by utensil availability and diet compatibility."""
    eligible = []
    for r in recipes:
        if check_utensils(r, owned_utensils) and check_diet_mode(r, diet_mode):
            eligible.append(r)
    return eligible
