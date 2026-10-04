"""Unit tests for scaling.py."""
import pytest
from pantrypal.models import Recipe, IngredientItem
from pantrypal.scaling import compute_scale_factor, scale_and_balance_ingredients


def test_scale_factor_clamping():
    recipe = Recipe(
        id="sample_recipe",
        name="Sample Dish",
        servings=1,
        method="microwave",
        ingredients=[
            IngredientItem(id="chicken_breast_raw", grams=200.0, role="bulk_protein")
        ]
    )
    # Chicken 200g has ~240 kcal.
    # Target 1200 kcal -> raw scale = 1200/240 = 5.0 -> clamp to 2.5
    scale, warning = compute_scale_factor(recipe, 1200.0)
    assert scale == 2.5
    assert warning is not None

    # Target 50 kcal -> raw scale = 50/240 = 0.208 -> clamp to 0.5
    scale_min, warning_min = compute_scale_factor(recipe, 50.0)
    assert scale_min == 0.5
    assert warning_min is not None

    # Target 360 kcal -> raw scale = 360/240 = 1.5 -> within bounds
    scale_mid, warning_mid = compute_scale_factor(recipe, 360.0)
    assert pytest.approx(scale_mid, 0.05) == 1.5
    assert warning_mid is None


def test_carnivore_fat_protein_balancing():
    recipe = Recipe(
        id="lean_beef_dish",
        name="Lean Ground Beef with Butter",
        carnivore_ok=True,
        servings=1,
        method="pan_fry",
        ingredients=[
            IngredientItem(id="beef_mince_lean", grams=200.0, role="bulk_protein"),
            IngredientItem(id="butter", grams=5.0, role="fat"),
        ]
    )
    # Beef mince lean 200g: 40g protein, 20g fat
    # Butter 5g: 0g protein, 4g fat
    # Total: protein ~40g, fat ~24g -> ratio = 24/40 = 0.60 (< 0.8 min)
    # Balancing should adjust butter upwards to hit at least 0.8 ratio
    balanced = scale_and_balance_ingredients(recipe, scale=1.0, diet_mode="high_protein_carnivore")
    butter_item = next(i for i in balanced if i.id == "butter")
    assert butter_item.grams > 5.0
