"""Unit conversion and display formatting utilities."""
import json
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from pantrypal.config import UNITS_PATH


@lru_cache(maxsize=1)
def load_units_data() -> Dict[str, Any]:
    """Load piece definitions and staples list from units.json."""
    if not UNITS_PATH.exists():
        return {"pieces": {}, "staples": []}
    with open(UNITS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def is_staple(ingredient_id: str) -> bool:
    """Return True if the ingredient is an always-available staple."""
    data = load_units_data()
    return ingredient_id.strip().lower() in set(data.get("staples", []))


def get_piece_info(ingredient_id: str) -> Optional[Dict[str, Any]]:
    """Return piece conversion details for an ingredient if defined."""
    data = load_units_data()
    pieces = data.get("pieces", {})
    return pieces.get(ingredient_id.strip().lower())


def convert_to_grams(ingredient_id: str, quantity: float, unit_name: str = "grams") -> float:
    """
    Convert a given quantity into grams.
    Supported unit_names: 'grams', 'g', 'ml' (assuming ~1g/ml density),
    or the item's defined piece unit (e.g., 'piece', 'tbsp', 'clove', 'medium', 'breast').
    """
    unit_clean = unit_name.strip().lower()
    qty = max(0.0, float(quantity))
    if unit_clean in {"grams", "g", "ml"}:
        return round(qty, 1)

    piece_info = get_piece_info(ingredient_id)
    if piece_info:
        piece_unit = piece_info["unit"].lower()
        if unit_clean in {piece_unit, "piece", "pieces", "count"}:
            return round(qty * float(piece_info["grams"]), 1)

    # Fallback to direct grams if unit not recognized
    return round(qty, 1)


def format_friendly_quantity(ingredient_id: str, grams: float) -> str:
    """
    Format quantity in grams into friendly human text.
    For example: '100g' of egg_whole becomes '2 eggs (100g)',
    '14g' of olive_oil becomes '1 tbsp (14g)'.
    """
    grams_val = round(float(grams), 1)
    piece_info = get_piece_info(ingredient_id)
    if not piece_info:
        return f"{int(grams_val) if grams_val.is_integer() else grams_val}g"

    unit_weight = float(piece_info["grams"])
    if unit_weight <= 0:
        return f"{grams_val}g"

    units_count = grams_val / unit_weight
    # If the count is reasonably close to a round or half number (within 10%)
    nearest_half = round(units_count * 2) / 2
    if abs(units_count - nearest_half) <= 0.15 and nearest_half > 0:
        if nearest_half == 1.0:
            count_str = "1"
            display_name = piece_info.get("unit", "piece")
        else:
            count_str = f"{int(nearest_half) if nearest_half.is_integer() else nearest_half}"
            display_name = piece_info.get("display_plural", piece_info.get("unit", "pieces"))
        return f"{count_str} {display_name} ({int(grams_val) if grams_val.is_integer() else grams_val}g)"

    return f"{int(grams_val) if grams_val.is_integer() else grams_val}g"


def get_available_units(ingredient_id: str) -> List[str]:
    """Return available unit options for UI dropdowns."""
    options = ["grams", "g"]
    piece_info = get_piece_info(ingredient_id)
    if piece_info:
        options.append(piece_info["unit"])
    return options
