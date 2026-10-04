"""Shopping list aggregation and pricing estimation."""
from typing import Dict, List, Optional

from pantrypal.models import IngredientItem, ShoppingItem
from pantrypal.nutrition import get_ingredient_nutrition
from pantrypal.units import format_friendly_quantity, is_staple


def build_shopping_list(
    ingredients: List[IngredientItem],
    pantry: Dict[str, dict],
) -> List[ShoppingItem]:
    """
    Generate shopping items for ingredients where pantry has insufficient quantity.
    Shortfall = required_grams - available_grams.
    Staples are skipped.
    """
    items: List[ShoppingItem] = []

    for item in ingredients:
        ing_id = item.id.strip().lower()
        pentry = pantry.get(ing_id, {})

        if is_staple(ing_id) or bool(pentry.get("always_have", False)):
            continue

        available_g = float(pentry.get("quantity_g", 0.0))
        required_g = item.grams

        if available_g < required_g:
            shortfall = round(required_g - available_g, 1)
            nutr = get_ingredient_nutrition(ing_id)
            display_name = nutr.get("name", ing_id) if nutr else ing_id

            friendly_qty = format_friendly_quantity(ing_id, shortfall)

            # Price estimation if user provided price_per_100g in pantry
            price_est = None
            price_per_100g = pentry.get("price_per_100g")
            if price_per_100g is not None and price_per_100g > 0:
                price_est = round((shortfall / 100.0) * float(price_per_100g), 2)

            items.append(
                ShoppingItem(
                    id=ing_id,
                    name=display_name,
                    shortfall_grams=shortfall,
                    friendly_quantity=friendly_qty,
                    price_est=price_est,
                )
            )

    return items
