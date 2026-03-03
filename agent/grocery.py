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
    # avoid ice-related junk that some recipes list for drinks
    "ice", "cube", "ice cube", "ice cubes", "cubes",
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
    # strip trailing commentary or modifiers ('such as...', 'similar...', 'with...',
    # 'at room temperature', etc.)
    s = re.split(r"\b(?:such as|similar|with|and other|or other|to your liking|your favorite|at room temperature|room temperature)\b", s)[0]
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

    def _is_valid_ingredient(name: str) -> bool:
        # reject overly verbose junk or instructions
        if not name or len(name.split()) > 5:
            return False
        for bad in ("such", "similar", "favorite", "amount", "chunk", "pound", "quart", "slice", "piece", "optional", "room temperature"):
            if bad in name:
                return False
        return True

    for day_plan in meal_plan.days:
        for meal in day_plan.meals:
            recipe = recipes_by_id.get(meal.recipe_id)
            if recipe is None:
                continue
            # Track unique ingredients across all recipes
            seen_in_recipe = set()
            for raw_ing in recipe.ingredients:
                name = _normalize_ingredient(raw_ing)
                # Skip empty strings, blacklisted items, or invalid names
                if (
                    name
                    and name not in BLACKLIST_INGREDIENTS
                    and _is_valid_ingredient(name)
                    and name not in seen_in_recipe
                ):
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


# optional LLM post‑processing --------------------------------------------------

def _llm_refine_list(item_names: List[str]) -> Optional[str]:
    """Use an LLM to rewrite a raw ingredient name list into a shopper-friendly
    text output.  Returns ``None`` if the client can't be imported or the call
    fails.  The returned text should be a bullet-point list or similar.
    """
    try:
        from agent.planner import _default_openai_client
    except ImportError:
        return None

    client = _default_openai_client()
    system = (
        "You are an assistant that converts a list of grocery items into a clean"
        " shopping list.  The input lines are ingredient names already normalized"
        " from recipes; please deduplicate them, discard any that are still"
        " nonsensical (e.g. instructions or descriptions), and output one simple"
        " bullet point or line per actual ingredient.  Do not add measurements"
        " or quantities.  Only return the list text."
    )
    user = "Raw items:\n" + "\n".join(item_names)
    try:
        text = client(system, user)
        if text:
            return text.strip()
    except Exception:
        pass
    return None


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
        grocery = GroceryList(items=items)
        # try to produce a human-readable text version via LLM
        try:
            names = [i.name for i in items]
            if names:
                pretty = _llm_refine_list(names)
                if pretty:
                    grocery.text = pretty
        except Exception:
            pass
        return grocery