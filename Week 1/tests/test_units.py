"""Unit tests for units.py conversion and formatting."""
import pytest
from pantrypal.units import (
    convert_to_grams,
    format_friendly_quantity,
    is_staple,
    get_available_units,
)


def test_convert_pieces_to_grams():
    # 2 eggs = 100g
    assert convert_to_grams("egg_whole", 2, "piece") == 100.0
    assert convert_to_grams("egg_whole", 2, "count") == 100.0
    # 1 medium onion = 110g
    assert convert_to_grams("onion", 1, "medium") == 110.0
    # 3 cloves garlic = 15g
    assert convert_to_grams("garlic", 3, "clove") == 15.0
    # 2 tbsp olive oil = 28g
    assert convert_to_grams("olive_oil", 2, "tbsp") == 28.0
    # Direct grams
    assert convert_to_grams("chicken_breast_raw", 250, "grams") == 250.0
    assert convert_to_grams("chicken_breast_raw", 250, "g") == 250.0


def test_format_friendly_quantity():
    # 100g eggs -> 2 eggs (100g)
    assert format_friendly_quantity("egg_whole", 100.0) == "2 eggs (100g)"
    # 50g eggs -> 1 piece (50g)
    assert format_friendly_quantity("egg_whole", 50.0) == "1 piece (50g)"
    # 14g olive oil -> 1 tbsp (14g)
    assert format_friendly_quantity("olive_oil", 14.0) == "1 tbsp (14g)"
    # 200g chicken without standard piece match
    assert format_friendly_quantity("chicken_thigh_raw", 240.0) == "2 thighs (240g)"
    # Unknown item
    assert format_friendly_quantity("mystery_powder", 150.0) == "150g"


def test_staples_detection():
    assert is_staple("salt") is True
    assert is_staple("black_pepper") is True
    assert is_staple("water") is True
    assert is_staple("turmeric") is True
    assert is_staple("chicken_breast_raw") is False
    assert is_staple("salmon_raw") is False


def test_get_available_units():
    units = get_available_units("egg_whole")
    assert "grams" in units
    assert "piece" in units
