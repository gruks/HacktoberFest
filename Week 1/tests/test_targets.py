"""Unit tests for targets.py."""
import pytest
from pantrypal.models import Profile
from pantrypal.targets import (
    calculate_bmr,
    calculate_tdee,
    calculate_protein_target,
    compute_targets,
)


def test_bmr_male_hand_calculation():
    # 75 kg, 178 cm, 28 yo male
    # 10*75 + 6.25*178 - 5*28 + 5 = 750 + 1112.5 - 140 + 5 = 1727.5
    bmr = calculate_bmr("male", 75.0, 178.0, 28)
    assert pytest.approx(bmr, 0.01) == 1727.5


def test_bmr_female_hand_calculation():
    # 60 kg, 165 cm, 30 yo female
    # 10*60 + 6.25*165 - 5*30 - 161 = 600 + 1031.25 - 150 - 161 = 1320.25
    bmr = calculate_bmr("female", 60.0, 165.0, 30)
    assert pytest.approx(bmr, 0.01) == 1320.25


def test_tdee_activity_multipliers():
    bmr = 1500.0
    assert pytest.approx(calculate_tdee(bmr, "sedentary"), 0.01) == 1800.0
    assert pytest.approx(calculate_tdee(bmr, "light"), 0.01) == 2062.5
    assert pytest.approx(calculate_tdee(bmr, "moderate"), 0.01) == 2325.0
    assert pytest.approx(calculate_tdee(bmr, "active"), 0.01) == 2587.5


def test_calorie_deficit_floor_at_bmr():
    # If sedentary (1.2) and extreme deficit were applied, daily kcal must never fall below BMR
    profile = Profile(
        sex="male",
        age=30,
        height_cm=170.0,
        weight_kg=70.0,
        activity="sedentary",
        goal="lose",
        diet_mode="light_oil_healthy",
        meals_per_day=3,
    )
    targets = compute_targets(profile)
    # 1.2 * 0.85 = 1.02, which is > 1.0. Let's verify daily_kcal >= bmr
    assert targets.daily_kcal >= targets.bmr
    assert targets.meal_kcal == pytest.approx(targets.daily_kcal / 3, 0.1)


def test_protein_targets_by_diet_and_goal():
    weight = 80.0
    # Maintain healthy: 1.8 g/kg -> 144 g
    assert pytest.approx(calculate_protein_target(weight, "maintain", "light_oil_healthy"), 0.1) == 144.0
    # Lose healthy: 2.0 g/kg -> 160 g
    assert pytest.approx(calculate_protein_target(weight, "lose", "light_oil_healthy"), 0.1) == 160.0
    # Lose carnivore: 2.0 + 0.2 = 2.2 g/kg (capped at 2.2) -> 176 g
    assert pytest.approx(calculate_protein_target(weight, "lose", "high_protein_carnivore"), 0.1) == 176.0
    # Gain carnivore: 1.8 + 0.2 = 2.0 g/kg -> 160 g
    assert pytest.approx(calculate_protein_target(weight, "gain", "high_protein_carnivore"), 0.1) == 160.0


def test_compute_targets_meal_split():
    profile = Profile(
        sex="male",
        age=25,
        height_cm=180.0,
        weight_kg=80.0,
        activity="moderate",
        goal="maintain",
        diet_mode="light_oil_healthy",
        meals_per_day=4,
    )
    targets = compute_targets(profile)
    assert targets.meal_kcal == pytest.approx(targets.daily_kcal / 4, 0.1)
    assert targets.meal_protein_g == pytest.approx(targets.daily_protein_g / 4, 0.1)
