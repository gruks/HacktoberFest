"""Deterministic planner and recommendation engine (v1)."""
from typing import Dict, List, Optional, Set, Tuple

from pantrypal.config import TOP_K
from pantrypal.filters import filter_recipes, load_all_recipes
from pantrypal.gaps import check_nutrient_gaps
from pantrypal.models import Plan, Profile, Recipe, StepItem
from pantrypal.nutrition import sum_nutrition
from pantrypal.scaling import compute_scale_factor, scale_and_balance_ingredients
from pantrypal.scoring import calculate_coverage, rank_recipes
from pantrypal.shopping import build_shopping_list
from pantrypal.targets import compute_targets


def recommend(
    profile: Profile,
    utensils: Set[str],
    pantry: Dict[str, dict],
    top_k: int = TOP_K,
) -> List[Plan]:
    """
    End-to-end deterministic recommendation pipeline:
    1. Compute daily and per-meal targets
    2. Filter recipes by owned utensils and diet mode
    3. Scale and balance ingredients, compute coverage and calorie delta
    4. Rank candidates by coverage, essential gaps, and calorie fit
    5. Construct rich Plan objects for top-k recipes
    """
    targets = compute_targets(profile)
    all_recipes = load_all_recipes()

    # Hard filtering
    eligible = filter_recipes(all_recipes, utensils, profile.diet_mode)
    if not eligible:
        return []

    # Scoring and scaling candidates
    scored_candidates = []
    for recipe in eligible:
        scale, _ = compute_scale_factor(recipe, targets.meal_kcal)
        scaled_ingredients = scale_and_balance_ingredients(recipe, scale, profile.diet_mode)
        coverage, _, missing_items = calculate_coverage(scaled_ingredients, pantry)
        scaled_nutrition = sum_nutrition(scaled_ingredients, recipe.method, recipe.servings, scale=1.0)
        calorie_delta = scaled_nutrition.kcal - targets.meal_kcal

        scored_candidates.append({
            "recipe": recipe,
            "coverage": coverage,
            "missing": missing_items,
            "delta": calorie_delta,
            "scale": scale,
            "scaled_ingredients": scaled_ingredients,
            "nutrition": scaled_nutrition,
        })

    # Prepare tuples for ranking: (recipe, coverage, missing, delta)
    tuples_for_ranking = [
        (c["recipe"], c["coverage"], c["missing"], c["delta"])
        for c in scored_candidates
    ]
    ranked_tuples = rank_recipes(tuples_for_ranking)[:top_k]

    # Map ranked recipes back to detailed candidate data
    cand_by_id = {c["recipe"].id: c for c in scored_candidates}

    plans: List[Plan] = []
    for recipe, _, _, _ in ranked_tuples:
        c = cand_by_id[recipe.id]
        scaled_ing = c["scaled_ingredients"]
        nutrition = c["nutrition"]
        scale = c["scale"]
        coverage = c["coverage"]
        missing = c["missing"]

        gaps = check_nutrient_gaps(nutrition, profile.diet_mode, profile.meals_per_day)
        shopping_list = build_shopping_list(scaled_ing, pantry)

        # Baseline steps as StepItem objects
        steps = [StepItem(text=step) for step in recipe.steps]

        plans.append(
            Plan(
                recipe=recipe,
                scale=scale,
                coverage=coverage,
                missing=missing,
                swapped=[],
                final_nutrition=nutrition,
                gaps=gaps,
                shopping_list=shopping_list,
                final_steps=steps,
            )
        )

    return plans
