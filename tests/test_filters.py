"""Unit tests for filters.py."""
import pytest
from pantrypal.filters import check_utensils, check_diet_mode, filter_recipes, load_all_recipes
from pantrypal.models import Recipe, IngredientItem


def test_utensil_alternatives():
    recipe = Recipe(
        id="test_airfry",
        name="Air Fryer or Oven Dish",
        requires_any=[["air_fryer"], ["oven"]],
        method="air_fry",
    )
    # Owns air fryer -> True
    assert check_utensils(recipe, {"air_fryer"}) is True
    # Owns oven -> True
    assert check_utensils(recipe, {"oven"}) is True
    # Owns stove only -> False
    assert check_utensils(recipe, {"stove"}) is False
    # Multi-utensil requirement: e.g. stove AND microwave
    multi = Recipe(
        id="test_multi",
        name="Needs both stove and microwave",
        requires_any=[["stove", "microwave"]],
        method="pan_fry",
    )
    assert check_utensils(multi, {"stove"}) is False
    assert check_utensils(multi, {"stove", "microwave"}) is True


def test_diet_mode_carnivore_purity():
    all_recipes = load_all_recipes()
    # Check that in carnivore mode, no plant-based recipes pass
    carnivore_eligible = [r for r in all_recipes if check_diet_mode(r, "high_protein_carnivore")]
    assert len(carnivore_eligible) >= 10
    for r in carnivore_eligible:
        assert r.carnivore_ok is True
        for ing in r.ingredients:
            if ing.id in {"salt", "black_pepper", "water"}:
                continue
            assert ing.id not in {"lentils_dry", "tofu_firm", "broccoli_raw", "tomato", "chickpeas_canned"}


def test_diet_mode_light_oil():
    all_recipes = load_all_recipes()
    healthy_eligible = [r for r in all_recipes if check_diet_mode(r, "light_oil_healthy")]
    assert len(healthy_eligible) >= 15
    for r in healthy_eligible:
        assert r.method != "deep_fry"


def test_filter_recipes_combined():
    all_recipes = load_all_recipes()
    # User owns only microwave, high-protein carnivore
    eligible = filter_recipes(all_recipes, {"microwave"}, "high_protein_carnivore")
    assert len(eligible) > 0
    for r in eligible:
        assert r.carnivore_ok is True
        assert any("microwave" in alt for alt in r.requires_any)
