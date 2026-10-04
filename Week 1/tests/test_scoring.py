"""Unit tests for scoring.py."""
import pytest
from pantrypal.models import IngredientItem, Recipe
from pantrypal.scoring import calculate_coverage, rank_recipes


def test_coverage_calculation():
    ingredients = [
        IngredientItem(id="chicken_breast_raw", grams=200.0, role="bulk_protein", essential=True),
        IngredientItem(id="broccoli_raw", grams=100.0, role="crunch", essential=False),
        IngredientItem(id="salt", grams=3.0, role="umami", essential=False), # staple
    ]
    # Pantry has 200g chicken, 50g broccoli
    pantry = {
        "chicken_breast_raw": {"quantity_g": 200.0, "always_have": False},
        "broccoli_raw": {"quantity_g": 50.0, "always_have": False},
        "salt": {"quantity_g": 0.0, "always_have": True},
    }
    # Required non-staples: 200 + 100 = 300g.
    # Covered: 200 (chicken) + 50 (broccoli) = 250g.
    # Coverage ratio: 250 / 300 = 0.833
    cov, available, missing = calculate_coverage(ingredients, pantry)
    assert pytest.approx(cov, 0.01) == 0.833
    assert len(missing) == 1
    assert missing[0].id == "broccoli_raw"


def test_ranking_priority():
    r1 = Recipe(id="r1", name="R1", method="pan_fry")
    r2 = Recipe(id="r2", name="R2", method="pan_fry")
    r3 = Recipe(id="r3", name="R3", method="pan_fry")

    # (recipe, coverage, missing_items, delta)
    candidates = [
        (r1, 0.50, [IngredientItem(id="a", grams=10, role="bulk_protein", essential=True)], 10.0),
        (r2, 0.90, [IngredientItem(id="b", grams=10, role="fat", essential=False)], 50.0),
        (r3, 0.90, [], 10.0),
    ]

    ranked = rank_recipes(candidates)
    # r3 should be #1 (coverage 0.90, 0 essential gaps, delta 10)
    # r2 should be #2 (coverage 0.90, 0 essential gaps, delta 50)
    # r1 should be #3 (coverage 0.50)
    assert ranked[0][0].id == "r3"
    assert ranked[1][0].id == "r2"
    assert ranked[2][0].id == "r1"
