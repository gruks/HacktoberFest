"""Unit tests for deterministic planner pipeline."""
import pytest
from pantrypal.models import Profile
from pantrypal.planner import recommend


def test_planner_recommendation_flow():
    profile = Profile(
        sex="male",
        age=28,
        height_cm=178.0,
        weight_kg=75.0,
        activity="sedentary",
        goal="lose",
        diet_mode="high_protein_carnivore",
        meals_per_day=3,
    )
    utensils = {"air_fryer", "microwave", "stove"}
    pantry = {
        "beef_steak_ribeye": {"quantity_g": 500.0, "always_have": False, "price_per_100g": 3.0},
        "butter": {"quantity_g": 200.0, "always_have": False, "price_per_100g": 1.0},
        "salt": {"quantity_g": 100.0, "always_have": True, "price_per_100g": None},
        "black_pepper": {"quantity_g": 50.0, "always_have": True, "price_per_100g": None},
    }

    plans = recommend(profile, utensils, pantry, top_k=5)
    assert len(plans) > 0
    # The top plan should be high coverage since ribeye and butter are stocked
    top_plan = plans[0]
    assert top_plan.coverage > 0.0
    assert top_plan.final_nutrition.protein > 0.0
    assert len(top_plan.final_steps) > 0
    assert top_plan.recipe.carnivore_ok is True


def test_planner_handles_empty_pantry():
    profile = Profile(
        sex="female",
        age=26,
        height_cm=165.0,
        weight_kg=60.0,
        activity="moderate",
        goal="maintain",
        diet_mode="light_oil_healthy",
        meals_per_day=3,
    )
    utensils = {"stove", "microwave", "air_fryer"}
    pantry = {}

    plans = recommend(profile, utensils, pantry, top_k=5)
    assert len(plans) == 5
    # All recipes should have coverage 0.0, and shopping list should hold all ingredients
    assert plans[0].coverage == 0.0
    assert len(plans[0].shopping_list) > 0
