from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from agent.interfaces import (
    GroceryGenerator,
    GroceryItem,
    GroceryList,
    MealPlan,
    Recipe,
)

CATEGORY_MAP = {
    "chicken": "Protein",
    "beef": "Protein",
    "turkey": "Protein",
    "pork": "Protein",
    "salmon": "Protein",
    "shrimp": "Protein",
    "tuna": "Protein",
    "egg": "Protein",
    "tofu": "Protein",
    "lentil": "Protein",
    "chickpea": "Protein",
    "black bean": "Protein",
    "milk": "Dairy",
    "cheese": "Dairy",
    "yogurt": "Dairy",
    "butter": "Dairy",
    "cream": "Dairy",
    "mozzarella": "Dairy",
    "parmesan": "Dairy",
    "rice": "Grains & Pasta",
    "bread": "Grains & Pasta",
    "tortilla": "Grains & Pasta",
    "oat": "Grains & Pasta",
    "pasta": "Grains & Pasta",
    "spaghetti": "Grains & Pasta",
    "quinoa": "Grains & Pasta",
    "granola": "Grains & Pasta",
    "breadcrumb": "Grains & Pasta",
    "lettuce": "Produce",
    "tomato": "Produce",
    "onion": "Produce",
    "garlic": "Produce",
    "broccoli": "Produce",
    "carrot": "Produce",
    "spinach": "Produce",
    "kale": "Produce",
    "pepper": "Produce",
    "cucumber": "Produce",
    "avocado": "Produce",
    "banana": "Produce",
    "lemon": "Produce",
    "lime": "Produce",
    "basil": "Produce",
    "cilantro": "Produce",
    "ginger": "Produce",
    "asparagus": "Produce",
    "sweet potato": "Produce",
    "cabbage": "Produce",
    "celery": "Produce",
    "mushroom": "Produce",
    "blueberri": "Produce",
    "strawberri": "Produce",
    "berri": "Produce",
    "olive oil": "Pantry",
    "soy sauce": "Pantry",
    "honey": "Pantry",
    "vinegar": "Pantry",
    "mustard": "Pantry",
    "mayo": "Pantry",
    "salsa": "Pantry",
    "marinara": "Pantry",
    "curry powder": "Pantry",
    "cumin": "Pantry",
    "dill": "Pantry",
    "tahini": "Pantry",
    "peanut butter": "Pantry",
    "coconut milk": "Pantry",
    "vegetable broth": "Pantry",
    "cornstarch": "Pantry",
    "protein powder": "Pantry",
    "chia seed": "Pantry",
}


def _categorize(ingredient: str) -> str:
    low = ingredient.lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in low:
            return cat
    return "Other"


def _normalize_ingredient(raw: str) -> str:
    s = raw.strip().lower()
    s = re.sub(r"\d+[\d/.\s]*(cups?|tbsps?|tsps?|oz|lbs?|g|ml|cloves?|pieces?|slices?|fillets?)\b", "", s)
    s = re.sub(r"[^a-z\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def aggregate_ingredients(
    meal_plan: MealPlan,
    recipes_by_id: Dict[int, Recipe],
) -> List[GroceryItem]:
    counts: Dict[str, int] = defaultdict(int)

    for day_plan in meal_plan.days:
        for meal in day_plan.meals:
            recipe = recipes_by_id.get(meal.recipe_id)
            if recipe is None:
                continue
            for raw_ing in recipe.ingredients:
                name = _normalize_ingredient(raw_ing)
                if name:
                    counts[name] += meal.servings

    items: List[GroceryItem] = []
    for name, qty in sorted(counts.items()):
        items.append(
            GroceryItem(
                name=name,
                quantity=float(qty),
                unit="servings",
                category=_categorize(name),
            )
        )
    return items


class SimpleGroceryGenerator(GroceryGenerator):
    """Aggregates ingredients across all meals in a plan."""

    def generate(
        self,
        meal_plan: MealPlan,
        recipes_by_id: Dict[int, Recipe],
    ) -> GroceryList:
        items = aggregate_ingredients(meal_plan, recipes_by_id)
        return GroceryList(items=items)