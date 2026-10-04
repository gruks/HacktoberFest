"""Culinary substitution engine and deterministic macro verification loop."""
import json
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from pantrypal.config import MACRO_TOLERANCE, SUBSTITUTIONS_PATH
from pantrypal.llm import llm_pick_substitute
from pantrypal.models import IngredientItem, Recipe, SubstitutionChoice
from pantrypal.nutrition import get_ingredient_nutrition, load_nutrition_db, sum_nutrition
from pantrypal.units import is_staple


@lru_cache(maxsize=1)
def load_substitutions_table() -> Dict[str, List[Dict[str, Any]]]:
    """Load role-based substitution definitions from substitutions.json."""
    if not SUBSTITUTIONS_PATH.exists():
        return {}
    with open(SUBSTITUTIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def find_candidates_for_role(
    role: str,
    missing_id: str,
    pantry: Dict[str, dict],
    diet_mode: str,
    max_candidates: int = 8,
) -> List[Dict[str, Any]]:
    """
    Find candidates for a missing ingredient by flavor role that:
    1. Are present in pantry (quantity_g > 0 or always_have)
    2. Are compatible with diet mode (e.g. carnivore animal-only)
    3. Are not the missing ingredient itself
    """
    subs = load_substitutions_table()
    options = subs.get(role.strip().lower(), [])
    db = load_nutrition_db()
    is_carnivore = diet_mode.strip().lower() == "high_protein_carnivore"

    candidates = []
    for opt in options:
        opt_id = opt["id"]
        if opt_id == missing_id:
            continue

        pentry = pantry.get(opt_id)
        if not pentry:
            continue
        if float(pentry.get("quantity_g", 0.0)) <= 0 and not pentry.get("always_have", False):
            continue

        nutr = db.get(opt_id)
        if not nutr:
            continue

        if is_carnivore and not nutr.get("animal_based", False) and not is_staple(opt_id):
            continue

        candidates.append({
            "id": opt_id,
            "name": nutr.get("name", opt_id),
            "ratio": opt.get("ratio", 1.0),
            "kcal": nutr.get("kcal", 0.0),
            "protein": nutr.get("protein", 0.0),
            "fat": nutr.get("fat", 0.0),
        })

        if len(candidates) >= max_candidates:
            break

    return candidates


def verify_and_rebalance_macro_loop(
    original_ingredients: List[IngredientItem],
    swapped_ingredient_index: int,
    original_missing_item: IngredientItem,
    candidate_id: str,
    initial_ratio: float,
    method: str,
    servings: int,
    scale: float,
    max_attempts: int = 3,
    tolerance: float = MACRO_TOLERANCE,
) -> Optional[Tuple[float, float, float]]:
    """
    Deterministic macro verification loop:
    1. Start with initial quantity: qty = missing_item.grams * initial_ratio
    2. Compute baseline macros without the swap
    3. In each attempt, calculate drift = max(|kcal_new - kcal_old|/kcal_old, |protein_new - protein_old|/protein_old)
    4. If drift <= 0.10: accept
    5. Else: rebalance quantity in code and retry up to 3 attempts
    Returns (accepted_qty, final_kcal_drift, final_protein_drift) or None if rejected.
    """
    baseline_nutrition = sum_nutrition(original_ingredients, method, servings, scale)
    base_kcal = max(1.0, baseline_nutrition.kcal)
    base_protein = max(1.0, baseline_nutrition.protein)

    current_qty = round(original_missing_item.grams * initial_ratio, 1)

    for attempt in range(max_attempts):
        # Create candidate ingredient list with trial swap
        trial_ingredients = [
            IngredientItem(
                id=item.id,
                grams=item.grams,
                role=item.role,
                essential=item.essential,
            )
            for item in original_ingredients
        ]
        trial_ingredients[swapped_ingredient_index] = IngredientItem(
            id=candidate_id,
            grams=current_qty,
            role=original_missing_item.role,
            essential=original_missing_item.essential,
        )

        trial_nutrition = sum_nutrition(trial_ingredients, method, servings, scale)
        kcal_drift = abs(trial_nutrition.kcal - base_kcal) / base_kcal
        prot_drift = abs(trial_nutrition.protein - base_protein) / base_protein

        max_drift = max(kcal_drift, prot_drift)

        if max_drift <= tolerance:
            return current_qty, kcal_drift, prot_drift

        # Deterministic rebalance step
        # Adjust quantity based on primary drifting macro
        if kcal_drift >= prot_drift and trial_nutrition.kcal > 0:
            rebalance_factor = base_kcal / trial_nutrition.kcal
        elif trial_nutrition.protein > 0:
            rebalance_factor = base_protein / trial_nutrition.protein
        else:
            rebalance_factor = 1.0

        # Dampen factor and clamp quantity
        rebalance_factor = max(0.5, min(2.0, rebalance_factor))
        new_qty = round(current_qty * rebalance_factor, 1)

        # Quantity bounds check [0.2x, 3.0x of original]
        min_allowed = round(original_missing_item.grams * 0.2, 1)
        max_allowed = round(original_missing_item.grams * 3.0, 1)
        new_qty = max(min_allowed, min(max_allowed, new_qty))

        if abs(new_qty - current_qty) < 0.5:
            # Cannot converge further
            break
        current_qty = new_qty

    return None


def resolve_substitutions(
    recipe: Recipe,
    scale: float,
    pantry: Dict[str, dict],
    diet_mode: str,
) -> Tuple[List[IngredientItem], List[SubstitutionChoice], List[IngredientItem]]:
    """
    Attempt to resolve missing ingredients with culinary substitutes:
    - Pre-filters pantry candidates for the missing role.
    - LLM picks best culinary option.
    - Macro loop tests and balances quantity.
    Returns:
        (final_ingredients, accepted_swaps, remaining_missing_items)
    """
    final_ingredients: List[IngredientItem] = []
    accepted_swaps: List[SubstitutionChoice] = []
    remaining_missing: List[IngredientItem] = []

    # Prepare base scaled ingredients
    for item in recipe.ingredients:
        final_ingredients.append(
            IngredientItem(
                id=item.id,
                grams=round(item.grams * scale, 1),
                role=item.role,
                essential=item.essential,
                name=item.name,
            )
        )

    for idx, item in enumerate(final_ingredients):
        if is_staple(item.id):
            continue

        pentry = pantry.get(item.id, {})
        avail_g = float(pentry.get("quantity_g", 0.0))

        if avail_g < item.grams:
            # Missing ingredient! Look for substitutes
            candidates = find_candidates_for_role(item.role, item.id, pantry, diet_mode)

            if not candidates:
                remaining_missing.append(item)
                continue

            # LLM picks candidate
            choice = llm_pick_substitute(item.id, item.role, candidates, recipe.name, diet_mode)
            if not choice or "choice_id" not in choice:
                remaining_missing.append(item)
                continue

            chosen_id = choice["choice_id"]
            matched_cand = next((c for c in candidates if c["id"] == chosen_id), None)
            if not matched_cand:
                remaining_missing.append(item)
                continue

            # Macro verification loop
            loop_res = verify_and_rebalance_macro_loop(
                original_ingredients=final_ingredients,
                swapped_ingredient_index=idx,
                original_missing_item=item,
                candidate_id=chosen_id,
                initial_ratio=matched_cand["ratio"],
                method=recipe.method,
                servings=recipe.servings,
                scale=1.0,  # Ingredients already scaled
                max_attempts=3,
                tolerance=MACRO_TOLERANCE,
            )

            if loop_res:
                accepted_qty, _, _ = loop_res
                # Apply swap
                final_ingredients[idx] = IngredientItem(
                    id=chosen_id,
                    grams=accepted_qty,
                    role=item.role,
                    essential=item.essential,
                )
                accepted_swaps.append(
                    SubstitutionChoice(
                        original_id=item.id,
                        substitute_id=chosen_id,
                        ratio=round(accepted_qty / max(1.0, item.grams), 2),
                        reason=choice.get("reason", "Culinary substitution"),
                        taste_note=choice.get("taste_note", ""),
                    )
                )
            else:
                # Macro verification failed
                remaining_missing.append(item)

    return final_ingredients, accepted_swaps, remaining_missing
