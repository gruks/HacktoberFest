"""Unit tests for nutrition.py calculations."""
import pytest
from pantrypal.models import IngredientItem
from pantrypal.nutrition import (
    get_ingredient_nutrition,
    sum_nutrition,
    calculate_micro_percentages,
)


def test_ingredient_lookup():
    chicken = get_ingredient_nutrition("chicken_breast_raw")
    assert chicken is not None
    assert chicken["kcal"] == 120.0
    assert chicken["protein"] == 22.5
    assert chicken["animal_based"] is True
    assert "bulk_protein" in chicken["flavor_roles"]


def test_hand_calculated_recipe_macros():
    # 200g chicken breast + 10g olive oil
    # Chicken 200g:
    #   kcal: 2 * 120 = 240
    #   protein: 2 * 22.5 = 45.0
    #   carbs: 0.0
    #   fat: 2 * 2.6 = 5.2
    # Olive oil 10g:
    #   kcal: 0.1 * 884 = 88.4
    #   fat: 0.1 * 100 = 10.0
    # Total:
    #   kcal: 240 + 88.4 = 328.4
    #   protein: 45.0
    #   fat: 5.2 + 10.0 = 15.2
    # Method: microwave (adds 0g oil)
    ingredients = [
        IngredientItem(id="chicken_breast_raw", grams=200.0, role="bulk_protein"),
        IngredientItem(id="olive_oil", grams=10.0, role="fat"),
    ]
    info = sum_nutrition(ingredients, method="microwave", scale=1.0)
    assert pytest.approx(info.kcal, 0.1) == 328.4
    assert pytest.approx(info.protein, 0.1) == 45.0
    assert pytest.approx(info.fat, 0.1) == 15.2
    assert pytest.approx(info.carbs, 0.1) == 0.0


def test_cooking_oil_adjustment_air_fry():
    # 200g white fish, method: air_fry (adds 4.0g oil)
    # Fish: 200g -> kcal: 2*82 = 164, fat: 2*0.7 = 1.4, protein: 2*17.8 = 35.6
    # Added oil 4.0g: fat += 4.0, kcal += 4.0 * 8.84 = 35.36
    # Expected fat: 1.4 + 4.0 = 5.4, kcal: 164 + 35.36 = 199.36 -> 199.4
    ingredients = [
        IngredientItem(id="white_fish_fillet", grams=200.0, role="bulk_protein")
    ]
    info = sum_nutrition(ingredients, method="air_fry", scale=1.0)
    assert pytest.approx(info.protein, 0.1) == 35.6
    assert pytest.approx(info.fat, 0.1) == 5.4
    assert pytest.approx(info.kcal, 0.2) == 199.4


def test_boiling_retention_factor():
    # 100g broccoli: vit_c_mg = 89.2
    # Boiled: vit_c_mg should retain 70% -> 89.2 * 0.70 = 62.44
    ingredients = [
        IngredientItem(id="broccoli_raw", grams=100.0, role="crunch")
    ]
    info_boiled = sum_nutrition(ingredients, method="boil", scale=1.0)
    assert pytest.approx(info_boiled.micros["vit_c_mg"], 0.2) == 62.44


def test_micro_percentages_prorated():
    # If meal has 45mg vit C and daily value is 90mg, with 3 meals/day:
    # Pro-rated target per meal is 90 / 3 = 30mg.
    # 45mg / 30mg = 150%
    micros = {"vit_c_mg": 45.0}
    pcts = calculate_micro_percentages(micros, meals_per_day=3)
    assert pytest.approx(pcts["vit_c_mg"], 0.1) == 150.0
