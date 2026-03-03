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


# Items that are too basic or universal to include on a grocery list
BLACKLIST_INGREDIENTS = {
    "water", "salt", "pepper", "black pepper", "garlic powder", "paprika",
    "cumin", "dill", "cinnamon", "vanilla", "oil", "and", "or", "to",
    "taste", "divided", "halved", "quartered", "sliced", "chopped",
    "peeled", "diced", "minced", "grated", "shredded", "beaten", "fresh",
    "ground", "dried", "skinless", "boneless", "for garnish", "optional",
}


def _normalize_ingredient(raw: str) -> str:
    s = raw.strip().lower()
    # Remove measurement units and quantities (with or without numbers)
    s = re.sub(
        r"\b(\d+[\d/.*\s]*)?(cups?|tbsps?|tsps?|oz|lbs?|g|ml|cloves?|pieces?|slices?|fillets?|tablespoons?|teaspoons?|pinches?|dashes?|sticks?)\b",
        "",
        s,
    )
    # Remove common preparation/description words
    s = re.sub(
        r"\b(and|or|to|taste|divided|halved|quartered|sliced|chopped|peeled|diced|minced|grated|shredded|beaten|fresh|ground|dried|skinless|boneless|for|garnish|optional)\b",
        "",
        s,
    )
    # remove size/quantity descriptors that are not useful
    s = re.sub(r"\b(ounce|scoop|large|small|medium|thinly|thickly|pinch|can|container|jar|pkg|package)\b", "", s)
    # Remove non-alphabetic characters except spaces
    s = re.sub(r"[^a-z\s]", "", s)
    # Normalize whitespace
    s = re.sub(r"\s+", " ", s).strip()
    # collapse plural to singular for simple cases
    if s.endswith("s") and not s.endswith("ss"):
        s = s[:-1]
    return s


def aggregate_ingredients(
    meal_plan: MealPlan,
    recipes_by_id: Dict[int, Recipe],
) -> List[GroceryItem]:
    """Aggregate all unique ingredients across the meal plan.
    
    Instead of trying to sum recipe quantities (which requires parsing raw
    ingredient strings), we simply deduplicate ingredients by name and count
    how many recipes use each one. This gives users a practical shopping list.
    """
    ingredient_counts: Dict[str, int] = defaultdict(int)

    for day_plan in meal_plan.days:
        for meal in day_plan.meals:
            recipe = recipes_by_id.get(meal.recipe_id)
            if recipe is None:
                continue
            # Track unique ingredients across all recipes
            seen_in_recipe = set()
            for raw_ing in recipe.ingredients:
                name = _normalize_ingredient(raw_ing)
                # Skip empty strings and blacklisted items
                if name and name not in BLACKLIST_INGREDIENTS and name not in seen_in_recipe:
                    ingredient_counts[name] += 1
                    seen_in_recipe.add(name)

    items: List[GroceryItem] = []
    for name, count in sorted(ingredient_counts.items()):
        items.append(
            GroceryItem(
                name=name,
                quantity=float(count),
                unit="meals",
                category=_categorize(name),
            )
        )
    return items


class SimpleGroceryGenerator(GroceryGenerator):
    """Produces a consolidated grocery list by deduplicating ingredients.
    
    Rather than trying to sum recipe quantities from unparsed ingredient
    strings, this generates a practical shopping list showing which
    ingredients are needed and how many meals they appear in.
    """

    def generate(
        self,
        meal_plan: MealPlan,
        recipes_by_id: Dict[int, Recipe],
    ) -> GroceryList:
        items = aggregate_ingredients(meal_plan, recipes_by_id)
        return GroceryList(items=items)