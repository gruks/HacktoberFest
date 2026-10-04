"""Unit tests for substitutions engine and macro verification loop."""
from unittest.mock import patch
import pytest
from pantrypal.models import IngredientItem, Recipe
from pantrypal.substitutes import (
    find_candidates_for_role,
    load_substitutions_table,
    resolve_substitutions,
    verify_and_rebalance_macro_loop,
)


def test_load_substitutions_table():
    subs = load_substitutions_table()
    assert "acid" in subs
    assert "fat" in subs
    assert "creaminess" in subs
    assert "bulk_protein" in subs


def test_find_candidates_pantry_filtering():
    pantry = {
        "lemon_juice": {"quantity_g": 50.0, "always_have": False},
        "vinegar": {"quantity_g": 100.0, "always_have": False},
        "tomato": {"quantity_g": 0.0, "always_have": False},  # 0 qty, not available
    }
    # Looking for acid, missing lemon_juice
    cands = find_candidates_for_role("acid", "lemon_juice", pantry, "light_oil_healthy")
    cand_ids = [c["id"] for c in cands]
    assert "vinegar" in cand_ids
    assert "lemon_juice" not in cand_ids  # Cannot be the missing ingredient itself
    assert "tomato" not in cand_ids  # Not in pantry


def test_carnivore_diet_excludes_plant_candidates():
    pantry = {
        "olive_oil": {"quantity_g": 100.0, "always_have": False},
        "butter": {"quantity_g": 100.0, "always_have": False},
    }
    # In carnivore mode, olive_oil (plant) must be excluded for fat role
    cands = find_candidates_for_role("fat", "beef_tallow", pantry, "high_protein_carnivore")
    cand_ids = [c["id"] for c in cands]
    assert "butter" in cand_ids
    assert "olive_oil" not in cand_ids


def test_verify_macro_loop_converges_within_tolerance():
    # Recipe with 200g chicken breast and 20g lemon juice, replacing lemon juice with vinegar (ratio 0.5)
    ingredients = [
        IngredientItem(id="chicken_breast_raw", grams=200.0, role="bulk_protein", essential=True),
        IngredientItem(id="lemon_juice", grams=20.0, role="acid", essential=False),
    ]
    result = verify_and_rebalance_macro_loop(
        original_ingredients=ingredients,
        swapped_ingredient_index=1,
        original_missing_item=ingredients[1],
        candidate_id="vinegar",
        initial_ratio=0.5,
        method="microwave",
        servings=1,
        scale=1.0,
        max_attempts=3,
        tolerance=0.10,
    )
    assert result is not None
    accepted_qty, kcal_drift, prot_drift = result
    assert kcal_drift <= 0.10 and prot_drift <= 0.10
    assert accepted_qty > 0


def test_resolve_substitutions_with_mocked_llm():
    recipe = Recipe(
        id="test_lemon_chicken",
        name="Lemon Chicken",
        method="microwave",
        ingredients=[
            IngredientItem(id="chicken_breast_raw", grams=200.0, role="bulk_protein", essential=True),
            IngredientItem(id="lemon_juice", grams=20.0, role="acid", essential=False),
        ]
    )
    pantry = {
        "chicken_breast_raw": {"quantity_g": 300.0, "always_have": False},
        "lemon_juice": {"quantity_g": 0.0, "always_have": False},  # Missing
        "vinegar": {"quantity_g": 100.0, "always_have": False},    # Candidate available
    }

    # Mock LLM to pick vinegar
    mock_choice = {
        "choice_id": "vinegar",
        "reason": "Provides bright acidity matching lemon juice.",
        "taste_note": "Sharp and clean.",
    }

    with patch("pantrypal.substitutes.llm_pick_substitute", return_value=mock_choice):
        final_ing, swapped, remaining_missing = resolve_substitutions(
            recipe, scale=1.0, pantry=pantry, diet_mode="light_oil_healthy"
        )

        assert len(swapped) == 1
        assert swapped[0].original_id == "lemon_juice"
        assert swapped[0].substitute_id == "vinegar"
        assert len(remaining_missing) == 0
        assert any(i.id == "vinegar" for i in final_ing)
