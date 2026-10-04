"""Unit tests for db.py persistence."""
import pytest
from pantrypal.models import Profile
from pantrypal.db import (
    init_db,
    save_profile,
    get_profile,
    set_utensils,
    get_utensils,
    set_pantry_item,
    get_pantry,
    delete_pantry_item,
    deduct_pantry_items,
    log_cooked,
    get_cooked_log,
)


@pytest.fixture
def test_db_path(tmp_path):
    return tmp_path / "test_pantrypal.db"


def test_profile_crud(test_db_path):
    init_db(test_db_path)
    assert get_profile(test_db_path) is None

    p = Profile(
        sex="male",
        age=28,
        height_cm=175.0,
        weight_kg=72.0,
        activity="light",
        goal="lose",
        diet_mode="high_protein_carnivore",
        meals_per_day=2,
    )
    save_profile(p, test_db_path)
    loaded = get_profile(test_db_path)
    assert loaded is not None
    assert loaded.sex == "male"
    assert loaded.diet_mode == "high_protein_carnivore"
    assert loaded.weight_kg == 72.0
    assert loaded.meals_per_day == 2

    # Update profile
    p2 = Profile(
        sex="male",
        age=29,
        height_cm=175.0,
        weight_kg=71.0,
        activity="moderate",
        goal="maintain",
        diet_mode="light_oil_healthy",
        meals_per_day=3,
    )
    save_profile(p2, test_db_path)
    loaded2 = get_profile(test_db_path)
    assert loaded2.age == 29
    assert loaded2.diet_mode == "light_oil_healthy"


def test_utensils_crud(test_db_path):
    init_db(test_db_path)
    assert get_utensils(test_db_path) == set()

    set_utensils(["Air_Fryer", "Microwave", "Stove"], test_db_path)
    utensils = get_utensils(test_db_path)
    assert utensils == {"air_fryer", "microwave", "stove"}

    set_utensils(["oven"], test_db_path)
    assert get_utensils(test_db_path) == {"oven"}


def test_pantry_crud_and_deduct(test_db_path):
    init_db(test_db_path)
    set_pantry_item("chicken_thigh_raw", 500.0, always_have=False, price_per_100g=1.20, db_path=test_db_path)
    set_pantry_item("salt", 100.0, always_have=True, db_path=test_db_path)

    pantry = get_pantry(test_db_path)
    assert "chicken_thigh_raw" in pantry
    assert pantry["chicken_thigh_raw"]["quantity_g"] == 500.0
    assert pantry["chicken_thigh_raw"]["always_have"] is False
    assert pantry["chicken_thigh_raw"]["price_per_100g"] == 1.20

    assert "salt" in pantry
    assert pantry["salt"]["always_have"] is True

    # Deduct
    deduct_pantry_items([("chicken_thigh_raw", 200.0), ("salt", 10.0)], test_db_path)
    updated = get_pantry(test_db_path)
    assert updated["chicken_thigh_raw"]["quantity_g"] == 300.0
    # Salt was always_have=True, so it should NOT be deducted
    assert updated["salt"]["quantity_g"] == 100.0

    delete_pantry_item("chicken_thigh_raw", test_db_path)
    after_del = get_pantry(test_db_path)
    assert "chicken_thigh_raw" not in after_del


def test_cooked_log(test_db_path):
    init_db(test_db_path)
    log_id = log_cooked("test_recipe", 1.2, ["delicious", "easy"], test_db_path)
    assert log_id > 0

    logs = get_cooked_log(test_db_path)
    assert len(logs) == 1
    assert logs[0]["recipe_id"] == "test_recipe"
    assert logs[0]["scale"] == 1.2
    assert "delicious" in logs[0]["rating_tags"]
