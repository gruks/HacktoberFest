"""End-to-end recommendation planner with substitution resolution and step rewrites."""
from typing import Dict, List, Optional, Set, Tuple

from pantrypal.config import TOP_K
from pantrypal.filters import filter_recipes, load_all_recipes
from pantrypal.gaps import check_nutrient_gaps
from pantrypal.llm import llm_rewrite_steps
from pantrypal.models import Plan, Profile, Recipe, StepItem
from pantrypal.nutrition import sum_nutrition
from pantrypal.scaling import compute_scale_factor, scale_and_balance_ingredients
from pantrypal.scoring import calculate_coverage, rank_recipes
from pantrypal.shopping import build_shopping_list
from pantrypal.substitutes import resolve_substitutions
from pantrypal.targets import compute_targets


def recommend(
    profile: Profile,
    utensils: Set[str],
    pantry: Dict[str, dict],
    top_k: int = TOP_K,
    enable_llm_steps: bool = False,
) -> List[Plan]:
    """
    End-to-end recommendation pipeline:
    1. Compute daily and per-meal targets
    2. Filter recipes by owned utensils and diet mode
    3. Scale and balance ingredients, compute coverage and calorie delta
    4. Rank candidates by coverage, essential gaps, and calorie fit
    5. Resolve missing ingredients via culinary substitution and macro verification loop
    6. Rewrite cooking steps for owned utensils (if enabled/available)
    7. Construct rich Plan objects for top-k recipes
    """
    targets = compute_targets(profile)
    all_recipes = load_all_recipes()

    # Hard filtering
    eligible = filter_recipes(all_recipes, utensils, profile.diet_mode)
    if not eligible:
        return []

    # Initial scoring and ranking candidates
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

    cand_by_id = {c["recipe"].id: c for c in scored_candidates}

    plans: List[Plan] = []
    for recipe, _, _, _ in ranked_tuples:
        c = cand_by_id[recipe.id]
        scale = c["scale"]

        # Attempt culinary substitution verify loop for missing ingredients
        final_ing, swapped, remaining_missing = resolve_substitutions(
            recipe=recipe,
            scale=scale,
            pantry=pantry,
            diet_mode=profile.diet_mode,
        )

        # Recompute final nutrition with swapped ingredients
        final_nutrition = sum_nutrition(final_ing, recipe.method, recipe.servings, scale=1.0)

        # Recalculate coverage with substitutions included
        final_coverage, _, _ = calculate_coverage(final_ing, pantry)

        # Micronutrient gap advisories
        gaps = check_nutrient_gaps(final_nutrition, profile.diet_mode, profile.meals_per_day)

        # Shopping list for remaining missing ingredients
        shopping_list = build_shopping_list(remaining_missing, pantry)

        # Step rewrites for utensils
        if enable_llm_steps:
            final_steps = llm_rewrite_steps(recipe.steps, list(utensils), recipe.method)
        else:
            final_steps = [StepItem(text=s) for s in recipe.steps]

        plans.append(
            Plan(
                recipe=recipe,
                scale=scale,
                coverage=final_coverage,
                missing=remaining_missing,
                swapped=swapped,
                final_nutrition=final_nutrition,
                gaps=gaps,
                shopping_list=shopping_list,
                final_steps=final_steps,
            )
        )

    return plans
