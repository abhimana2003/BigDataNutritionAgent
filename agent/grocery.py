from __future__ import annotations
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, List, Optional, Tuple
from agent.interfaces import GroceryGenerator,GroceryItem,GroceryList,MealPlan,Recipe

CATEGORY_MAP = {
    "chicken": "Protein",
    "beef": "Protein",
    "turkey": "Protein",
    "pork": "Protein",
    "salmon": "Protein",
    "shrimp": "Protein",
    "tuna": "Protein",
    "sea bass": "Protein",
    "egg": "Protein",
    "tofu": "Protein",
    "lentil": "Protein",
    "chickpea": "Protein",
    "black bean": "Protein",
    "kidney bean": "Protein",
    "white bean": "Protein",
    "milk": "Dairy",
    "cheese": "Dairy",
    "yogurt": "Dairy",
    "butter": "Dairy",
    "cream": "Dairy",
    "mozzarella": "Dairy",
    "parmesan": "Dairy",
    "feta": "Dairy",
    "halloumi": "Dairy",
    "burrata": "Dairy",
    "rice": "Grains & Pasta",
    "bread": "Grains & Pasta",
    "tortilla": "Grains & Pasta",
    "oat": "Grains & Pasta",
    "pasta": "Grains & Pasta",
    "spaghetti": "Grains & Pasta",
    "quinoa": "Grains & Pasta",
    "granola": "Grains & Pasta",
    "breadcrumb": "Grains & Pasta",
    "bread crumb": "Grains & Pasta",
    "flour": "Grains & Pasta",
    "lettuce": "Produce",
    "greens": "Produce",
    "arugula": "Produce",
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
    "mint": "Produce",
    "ginger": "Produce",
    "asparagus": "Produce",
    "sweet potato": "Produce",
    "cabbage": "Produce",
    "celery": "Produce",
    "mushroom": "Produce",
    "berry": "Produce",
    "apple": "Produce",
    "pear": "Produce",
    "nectarine": "Produce",
    "peach": "Produce",
    "fig": "Produce",
    "cranberry": "Produce",
    "strawberry": "Produce",
    "persimmon": "Produce",
    "watermelon": "Produce",
    "kiwi": "Produce",
    "olive oil": "Pantry",
    "soy sauce": "Pantry",
    "honey": "Pantry",
    "vinegar": "Pantry",
    "mustard": "Pantry",
    "mayo": "Pantry",
    "mayonnaise": "Pantry",
    "salsa": "Pantry",
    "marinara": "Pantry",
    "curry powder": "Pantry",
    "cumin": "Pantry",
    "dill": "Pantry",
    "tahini": "Pantry",
    "peanut butter": "Pantry",
    "coconut milk": "Pantry",
    "vegetable broth": "Pantry",
    "vegetable bouillon": "Pantry",
    "cornstarch": "Pantry",
    "protein powder": "Pantry",
    "chia seed": "Pantry",
    "sugar": "Pantry",
    "brown sugar": "Pantry",
    "maple syrup": "Pantry",
}

UNIT_ALIASES = {
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "tsp": "tsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tbsp": "tbsp",
    "cup": "cup",
    "cups": "cup",
    "ounce": "oz",
    "ounces": "oz",
    "oz": "oz",
    "pound": "lb",
    "pounds": "lb",
    "lb": "lb",
    "lbs": "lb",
    "gram": "g",
    "grams": "g",
    "g": "g",
    "kilogram": "kg",
    "kilograms": "kg",
    "kg": "kg",
    "milliliter": "ml",
    "milliliters": "ml",
    "ml": "ml",
    "liter": "l",
    "liters": "l",
    "l": "l",
    "clove": "clove",
    "cloves": "clove",
    "can": "can",
    "cans": "can",
    "jar": "jar",
    "jars": "jar",
    "bottle": "bottle",
    "bottles": "bottle",
    "bunch": "bunch",
    "bunches": "bunch",
    "loaf": "loaf",
    "loaves": "loaf",
    "dozen": "dozen",
    "dozens": "dozen",
    "count": "count",
    "ball": "ball",
    "balls": "ball",
    "package": "package",
    "packages": "package",
    "pkg": "package",
    "scoop": "scoop",
    "scoops": "scoop",
    "slice": "slice",
    "slices": "slice",
    "sprig": "sprig",
    "sprigs": "sprig",
    "leaf": "leaf",
    "leaves": "leaf",
    "pinch": "pinch",
    "pinches": "pinch",
    "cube": "cube",
    "cubes": "cube",
}

REMOVABLE_DESCRIPTORS = {
    "fresh",
    "frozen",
    "dried",
    "chopped",
    "diced",
    "sliced",
    "minced",
    "grated",
    "shredded",
    "pitted",
    "drained",
    "rinsed",
    "peeled",
    "skinless",
    "boneless",
    "large",
    "small",
    "medium",
    "ripe",
    "thinly",
    "roughly",
    "lightly",
    "finely",
    "cubed",
    "crumbled",
    "toasted",
    "seeded",
    "halved",
    "quartered",
    "freshly",
    "packed",
    "whole",
    "pre",
    "baked",
    "canned",
}

CANONICAL_NAME_MAP = {
    "extra virgin olive oil": "olive oil",
    "baby spinach": "spinach",
    "mixed baby greens": "mixed greens",
    "mixed baby green": "mixed greens",
    "mixed field green": "mixed greens",
    "mixed field greens": "mixed greens",
    "field greens": "mixed greens",
    "black beans": "black bean",
    "black beans canned": "black bean",
    "white beans": "white bean",
    "kidney beans": "kidney bean",
    "eggs": "egg",
    "dry bread crumbs": "bread crumb",
    "breadcrumbs": "bread crumb",
    "bread crumbs": "bread crumb",
    "pine nuts": "pine nut",
    "red onions": "red onion",
    "lemons": "lemon",
    "limes": "lime",
    "avocados": "avocado",
    "strawberries": "strawberry",
    "cranberries": "cranberry",
    "blueberries": "blueberry",
    "raspberries": "raspberry",
    "tomatoes": "tomato",
    "peaches": "peach",
    "rolled oats": "rolled oats",
    "old fashioned oats": "rolled oats",
    "heirloom tomatoes": "tomato",
    "heirloom tomato": "tomato",
    "ripe avocado": "avocado",
    "ball burrata cheese": "burrata cheese",
    "balls burrata cheese": "burrata cheese",
    "burrata balls": "burrata cheese",
    "lowfat vanilla yogurt": "vanilla yogurt",
    "vegetable bouillon cube": "vegetable bouillon",
    "cube vegetable bouillon": "vegetable bouillon",
    "tart apple": "apple",
    "slices pear": "pear",
    "thin slices pear": "pear",
    "pre baked pizza crust": "pizza crust",
    "pizza crust": "pizza crust",
    "thyme leave": "thyme",
    "thyme leaves": "thyme",
    "mint leave": "mint",
    "mint leaves": "mint",
    "leaves basil": "basil",
    "leaves mint": "mint",
    "seasoned bread crumb": "bread crumb",
    "walnut piece": "walnut",
    "walnut pieces": "walnut",
    "raw macadamia nut": "macadamia nut",
    "candied pecan": "pecan",
    "packed brown sugar": "brown sugar",
    "lemon or lime juice": "citrus juice",
    "kiwi fruit": "kiwi",
    "fuyu persimmon": "persimmon",
    "seedless watermelon": "watermelon",
    "baby cucumber": "cucumber",
    "whole wheat bread slices": "whole wheat bread",
    "slices whole wheat bread": "whole wheat bread",
    "thin slices brie cheese": "brie cheese",
    "thick slices french bread": "french bread",
    "pinch ground black pepper": "ground black pepper",
}

BLACKLIST_INGREDIENTS = {
    "water",
    "ice",
    "ice cube",
    "ice cubes",
}

DROP_UNKNOWN_NAMES = {
    "as needed",
    "to taste",
    "crushed",
    "toasted",
    "seeded",
    "freshly black pepper",
    "freshly ground black pepper",
    "watermelon chunk",
    "cut into chunk",
    "cut into chunks",
    "cut into piece",
    "cut into pieces",
    "chunk",
    "chunks",
    "torn into bitesize",
    "bitesize",
    "optional",
}

UNICODE_FRACTIONS = {
    "½": "1/2",
    "⅓": "1/3",
    "⅔": "2/3",
    "¼": "1/4",
    "¾": "3/4",
    "⅛": "1/8",
}

PRODUCE_COUNT_NAMES = {
    "apple",
    "avocado",
    "banana",
    "lemon",
    "lime",
    "pear",
    "nectarine",
    "peach",
    "fig",
    "tomato",
    "cucumber",
    "onion",
    "red onion",
    "bell pepper",
    "red bell pepper",
    "pomegranate",
    "mango",
    "orange",
    "persimmon",
    "kiwi",
    "watermelon",
}

COUNT_STYLE_UNITS = {
    "count",
    "clove",
    "can",
    "jar",
    "bottle",
    "bunch",
    "loaf",
    "ball",
    "package",
    "scoop",
    "slice",
    "sprig",
    "leaf",
    "cube",
}

ROUND_TO_WHOLE_NAMES = {
    "egg",
    "avocado",
    "banana",
    "apple",
    "pear",
    "nectarine",
    "peach",
    "mango",
    "pizza crust",
    "tomato",
    "pomegranate",
    "garlic",
    "cucumber",
    "kiwi",
    "watermelon",
    "persimmon",
}

ROUND_TO_HALF_NAMES = {
    "lemon",
    "lime",
    "onion",
    "red onion",
}

PANTRY_STAPLES = {
    "salt",
    "black pepper",
    "ground black pepper",
    "ground cinnamon",
    "ground nutmeg",
    "vanilla extract",
}

UNIT_FAMILIES = {
    "tsp": "volume_us",
    "tbsp": "volume_us",
    "cup": "volume_us",
    "oz": "weight_us",
    "lb": "weight_us",
    "g": "weight_metric",
    "kg": "weight_metric",
    "ml": "volume_metric",
    "l": "volume_metric",
    "count": "count",
    "clove": "count",
    "slice": "count",
    "sprig": "count",
    "leaf": "count",
    "cube": "count",
    "pinch": "count",
    "can": "packaging",
    "jar": "packaging",
    "bottle": "packaging",
    "bunch": "packaging",
    "loaf": "packaging",
    "ball": "packaging",
    "package": "packaging",
    "scoop": "packaging",
}

BASE_CONVERSIONS = {
    "tsp": ("tsp", 1.0),
    "tbsp": ("tsp", 3.0),
    "cup": ("tsp", 48.0),
    "oz": ("oz", 1.0),
    "lb": ("oz", 16.0),
    "g": ("g", 1.0),
    "kg": ("g", 1000.0),
    "ml": ("ml", 1.0),
    "l": ("ml", 1000.0),
    "count": ("count", 1.0),
    "clove": ("clove", 1.0),
    "slice": ("slice", 1.0),
    "sprig": ("sprig", 1.0),
    "leaf": ("leaf", 1.0),
    "cube": ("cube", 1.0),
    "pinch": ("pinch", 1.0),
    "can": ("can", 1.0),
    "jar": ("jar", 1.0),
    "bottle": ("bottle", 1.0),
    "bunch": ("bunch", 1.0),
    "loaf": ("loaf", 1.0),
    "ball": ("ball", 1.0),
    "package": ("package", 1.0),
    "scoop": ("scoop", 1.0),
}

PLANNER_UNIT_FAMILIES = {
    "tsp": "volume_us",
    "tbsp": "volume_us",
    "cup": "volume_us",
    "oz": "weight_us",
    "lb": "weight_us",
    "g": "weight_metric",
    "kg": "weight_metric",
    "ml": "volume_metric",
    "l": "volume_metric",
    "count": "count",
    "clove": "count",
    "slice": "count",
    "sprig": "count",
    "leaf": "count",
    "cube": "count",
    "pinch": "count",
    "can": "packaging",
    "jar": "packaging",
    "bottle": "packaging",
    "bunch": "packaging",
    "loaf": "packaging",
    "ball": "packaging",
    "package": "packaging",
    "scoop": "packaging",
}

PLANNER_BASE_CONVERSIONS = {
    "tsp": ("tbsp", 1.0 / 3.0),
    "tbsp": ("tbsp", 1.0),
    "cup": ("tbsp", 16.0),
    "oz": ("oz", 1.0),
    "lb": ("oz", 16.0),
    "g": ("g", 1.0),
    "kg": ("g", 1000.0),
    "ml": ("ml", 1.0),
    "l": ("ml", 1000.0),
    "count": ("count", 1.0),
    "clove": ("clove", 1.0),
    "slice": ("slice", 1.0),
    "sprig": ("sprig", 1.0),
    "leaf": ("leaf", 1.0),
    "cube": ("cube", 1.0),
    "pinch": ("pinch", 1.0),
    "can": ("can", 1.0),
    "jar": ("jar", 1.0),
    "bottle": ("bottle", 1.0),
    "bunch": ("bunch", 1.0),
    "loaf": ("loaf", 1.0),
    "ball": ("ball", 1.0),
    "package": ("package", 1.0),
    "scoop": ("scoop", 1.0),
}

@dataclass
class ParsedIngredient:
    name: str
    quantity: Optional[float]
    unit: Optional[str]
    preparation: Optional[str] = None

# Helper functions for going through and normalizing ingredient lines, categorizing ingredients, converting units, and formatting the grocery list

def _replace_unicode_fractions(text: str) -> str:
    out = text
    for k, v in UNICODE_FRACTIONS.items():
        out = out.replace(k, v)
    return out


def _parse_fraction(text: str) -> Optional[float]:
    if "/" not in text:
        return None
    parts = text.split("/", 1)
    if len(parts) != 2:
        return None
    try:
        num = float(parts[0].strip())
        den = float(parts[1].strip())
    except ValueError:
        return None
    if den == 0:
        return None
    return num / den


def _parse_quantity_prefix(text: str) -> Tuple[Optional[float], str]:
    s = _replace_unicode_fractions(text.strip())
    if not s:
        return None, text
    match = re.match(r"^(\d+\s+\d+/\d+|\d+/\d+|\d+\.\d+|\d+)\b", s)
    if not match:
        return None, text
    token = match.group(1)
    rest = s[match.end():].strip()

    if " " in token and "/" in token:
        whole, frac = token.split(" ", 1)
        frac_val = _parse_fraction(frac)
        try:
            whole_val = float(whole)
        except ValueError:
            return None, text
        if frac_val is None:
            return None, text
        return whole_val + frac_val, rest

    if "/" in token:
        frac_val = _parse_fraction(token)
        return (frac_val, rest) if frac_val is not None else (None, text)

    try:
        return float(token), rest
    except ValueError:
        return None, text


def _smart_singularize(s: str) -> str:
    if s in CANONICAL_NAME_MAP:
        return CANONICAL_NAME_MAP[s]
    if s.endswith("ies") and len(s) > 3:
        return s[:-3] + "y"
    if s.endswith("oes") and len(s) > 3:
        return s[:-2]
    if s.endswith("ches") or s.endswith("shes"):
        return s[:-2]
    if s.endswith("ves") and len(s) > 3:
        return s[:-3] + "f"
    if s.endswith("ses") and not s.endswith("ss"):
        return s[:-2]
    if s.endswith("s") and not s.endswith("ss") and not s.endswith("us"):
        return s[:-1]
    return s


def _pluralize_word(word: str) -> str:
    irregular = {
        "leaf": "leaves",
        "loaf": "loaves",
        "tomato": "tomatoes",
        "potato": "potatoes",
        "berry": "berries",
    }
    if word in irregular:
        return irregular[word]
    if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    return word + "s"


def canonicalize_ingredient_name(name: str) -> str:
    s = _replace_unicode_fractions(name.lower().strip())
    s = s.replace("&", "and")
    s = s.replace("-", " ")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^\w\s/]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return ""

    s = re.sub(r"^(?:about|approximately|approx)\s+", "", s)
    s = re.sub(r"^(?:a|an)\s+", "", s)
    s = re.sub(r"^(?:of)\s+", "", s)
    s = re.sub(r"^(?:\d+\s+\d+/\d+|\d+/\d+|\d+\.\d+|\d+)\s+", "", s)

    tokens = [t for t in s.split() if t not in REMOVABLE_DESCRIPTORS]
    s = " ".join(tokens).strip()
    if not s:
        return ""

    if s in CANONICAL_NAME_MAP:
        return CANONICAL_NAME_MAP[s]

    singular = _smart_singularize(s)
    return CANONICAL_NAME_MAP.get(singular, singular)


def _normalize_ingredient(name: str) -> str:
    s = (name or "").strip().lower()
    if not s:
        return ""
    if "such as" in s:
        return ""
    if "at room temperature" in s:
        return ""
    s = re.sub(r"\bsimilar amount of your favorite fruit\b", "", s).strip()
    return canonicalize_ingredient_name(s)


def _is_blacklisted(name: str) -> bool:
    return name in BLACKLIST_INGREDIENTS or name in DROP_UNKNOWN_NAMES


def parse_ingredient_line(raw: str) -> Optional[ParsedIngredient]:
    if not raw:
        return None

    text = _replace_unicode_fractions(raw.strip().lower())
    if not text or "to taste" in text:
        return None
    if text in BLACKLIST_INGREDIENTS:
        return None

    text = re.sub(r"\([^)]*\)", "", text)
    text = text.split(";", 1)[0].strip()
    text = text.split(",", 1)[0].strip()

    quantity, remainder = _parse_quantity_prefix(text)
    if quantity is None or not remainder:
        return None

    parts = remainder.split()
    unit = None
    name_tokens: List[str] = []

    if parts:
        unit_candidate = UNIT_ALIASES.get(parts[0])
        if unit_candidate:
            unit = unit_candidate
            name_tokens = parts[1:]
        else:
            unit = "count"
            name_tokens = parts

    if not name_tokens:
        return None

    name = canonicalize_ingredient_name(" ".join(name_tokens))
    if not name or _is_blacklisted(name):
        return None

    if unit == "dozen":
        quantity = quantity * 12.0
        unit = "count"

    return ParsedIngredient(name=name, quantity=quantity, unit=unit)


def _categorize(ingredient: str) -> str:
    low = ingredient.lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in low:
            return cat
    return "Other"


def _is_produce(name: str) -> bool:
    return _categorize(name) == "Produce"


def _choose_base_unit(name: str, unit: str) -> Tuple[str, float, str]:
    family = UNIT_FAMILIES.get(unit, unit)
    base_unit, factor = BASE_CONVERSIONS.get(unit, (unit, 1.0))
    return base_unit, factor, family


def _convert_to_base(quantity: float, unit: str, name: str) -> Tuple[float, str, str]:
    base_unit, factor, family = _choose_base_unit(name, unit)
    return quantity * factor, base_unit, family


def _round_to_increment(qty: float, step: float) -> float:
    if step <= 0:
        return qty
    return round(qty / step) * step


def _round_up_to_increment(qty: float, step: float) -> float:
    if step <= 0:
        return qty
    return math.ceil(qty / step) * step


def _normalize_display_unit_and_qty(name: str, qty: float, unit: Optional[str]) -> Tuple[float, Optional[str], str]:
    if unit is None:
        return qty, unit, name

    if unit == "tsp":
        if qty >= 3 and abs(qty / 3 - round(qty / 3)) < 1e-6:
            return qty / 3.0, "tbsp", name
        return qty, "tsp", name

    return qty, unit, name


def _shopper_round(name: str, qty: float, unit: Optional[str]) -> Tuple[float, Optional[str], str]:
    if qty <= 0:
        return 0.0, unit, name

    if unit == "count":
        if name in ROUND_TO_WHOLE_NAMES or name == "egg":
            qty = max(1.0, float(math.ceil(qty)))
        elif name in ROUND_TO_HALF_NAMES:
            qty = max(0.5, _round_up_to_increment(qty, 0.5))
        else:
            qty = max(0.5, _round_up_to_increment(qty, 0.5))
        return qty, "count", name

    if unit in {"clove", "slice", "sprig", "leaf", "cube"}:
        qty = max(1.0, float(math.ceil(qty)))
        return qty, unit, name

    if unit in {"can", "jar", "bottle", "bunch", "loaf", "ball", "package", "scoop"}:
        qty = max(1.0, float(math.ceil(qty)))
        return qty, unit, name

    if unit == "pinch":
        qty = max(1.0, float(math.ceil(qty)))
        return qty, unit, name

    if unit == "tsp":
        if qty < 0.25:
            if name in PANTRY_STAPLES:
                return 0.0, None, name
            return 1.0, "pinch", name
        qty = _round_to_increment(qty, 0.25)
        return qty, unit, name

    if unit == "tbsp":
        if qty < 0.25:
            tsp = qty * 3.0
            if tsp < 0.25:
                if name in PANTRY_STAPLES:
                    return 0.0, None, name
                return 1.0, "pinch", name
            return _shopper_round(name, tsp, "tsp")
        qty = _round_to_increment(qty, 0.25)
        return qty, unit, name

    if unit == "cup":
        qty = _round_to_increment(qty, 0.125)
        if qty <= 0:
            return 0.0, None, name
        if _is_produce(name) and name in PRODUCE_COUNT_NAMES and qty < 0.5:
            return 1.0, None, name
        return qty, unit, name

    if unit == "oz":
        qty = _round_to_increment(qty, 0.25)
        return max(qty, 0.25), unit, name

    if unit in {"g", "ml"}:
        qty = round(qty)
        return max(qty, 1.0), unit, name

    return qty, unit, name


def _combine_similar_name_and_unit(name: str, qty: float, unit: Optional[str]) -> Tuple[str, float, Optional[str]]:
    if name in {"basil", "mint", "thyme"} and unit == "leaf":
        unit = "bunch"
        qty = 1.0 if qty <= 8 else math.ceil(qty / 12.0)

    return name, qty, unit


def _display_name(name: str, qty: float, unit: Optional[str]) -> str:
    if qty > 1:
        if unit is None:
            return _pluralize_word(name)
        if unit == "clove" and name == "garlic":
            return "garlic"
        return name
    return name


def _display_unit(unit: Optional[str], qty: float) -> Optional[str]:
    if unit is None:
        return None

    if qty > 1:
        if unit == "leaf":
            return "leaves"
        if unit == "loaf":
            return "loaves"
        return _pluralize_word(unit)

    return unit


def _format_quantity(quantity: float) -> str:
    rounded = round(quantity, 4)

    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))

    frac = Fraction(rounded).limit_denominator(8)
    if abs(float(frac) - rounded) < 0.03:
        if frac.numerator > frac.denominator:
            whole = frac.numerator // frac.denominator
            rem = frac.numerator % frac.denominator
            if rem == 0:
                return str(whole)
            return f"{whole} {rem}/{frac.denominator}"
        return f"{frac.numerator}/{frac.denominator}"

    return f"{rounded:.2f}".rstrip("0").rstrip(".")

# extracts the meals from a meal plan and deals with different shapes of the meal plan
def _extract_plan_meals(meal_plan) -> List:
    if meal_plan is None:
        return []

    meals = getattr(meal_plan, "meals", None)
    if meals:
        return list(meals)

    if isinstance(meal_plan, dict):
        if isinstance(meal_plan.get("meals"), list):
            return meal_plan["meals"]

        if isinstance(meal_plan.get("days"), list):
            out = []
            for day in meal_plan["days"]:
                if isinstance(day, dict):
                    if isinstance(day.get("meals"), list):
                        out.extend(day["meals"])
                    elif isinstance(day.get("entries"), list):
                        out.extend(day["entries"])
            return out

        if isinstance(meal_plan.get("items"), list):
            return meal_plan["items"]

        if isinstance(meal_plan.get("entries"), list):
            return meal_plan["entries"]

    days = getattr(meal_plan, "days", None)
    if days:
        out = []
        for day in days:
            day_meals = getattr(day, "meals", None)
            if day_meals:
                out.extend(day_meals)
                continue

            day_entries = getattr(day, "entries", None)
            if day_entries:
                out.extend(day_entries)
                continue

            if isinstance(day, dict):
                if isinstance(day.get("meals"), list):
                    out.extend(day["meals"])
                elif isinstance(day.get("entries"), list):
                    out.extend(day["entries"])
        return out

    items = getattr(meal_plan, "items", None)
    if items:
        return list(items)

    entries = getattr(meal_plan, "entries", None)
    if entries:
        return list(entries)

    return []

# function to get an attribute from a meal safely
def _get_meal_attr(meal, attr_name: str, default=None):
    if isinstance(meal, dict):
        return meal.get(attr_name, default)
    return getattr(meal, attr_name, default)

# aggregates ingrediants from the meal plan
def aggregate_ingredients(meal_plan: MealPlan, recipes_by_id: Dict[int, Recipe]) -> List[GroceryItem]:
    grouped: Dict[Tuple[str, str], Dict[str, object]] = defaultdict(
        lambda: {
            "name": "",
            "quantity": 0.0,
            "unit": None,
            "category": None,
        }
    )

    meals = _extract_plan_meals(meal_plan)
    quantified_names: set[str] = set()
    unquantified_counts: Dict[str, float] = defaultdict(float)

    for meal in meals:
        recipe_id = _get_meal_attr(meal, "recipe_id")
        servings = _get_meal_attr(meal, "servings")

        if recipe_id is None:
            continue

        recipe = recipes_by_id.get(recipe_id)
        if recipe is None or not getattr(recipe, "ingredients", None):
            continue

        base_servings = float(getattr(recipe, "servings", 1) or 1)
        requested_servings = float(servings or base_servings or 1)
        scale = requested_servings / base_servings if base_servings else 1.0

        for raw in recipe.ingredients:
            parsed = parse_ingredient_line(raw)
            if parsed is None or parsed.quantity is None or parsed.unit is None:
                normalized_name = _normalize_ingredient(str(raw))
                if not normalized_name or _is_blacklisted(normalized_name):
                    continue
                unquantified_counts[normalized_name] += max(scale, 1.0)
                continue

            normalized_name = canonicalize_ingredient_name(parsed.name)
            if not normalized_name or _is_blacklisted(normalized_name):
                continue

            quantified_names.add(normalized_name)
            qty = parsed.quantity * scale
            qty, base_unit, family = _convert_to_base(qty, parsed.unit, normalized_name)

            key = (normalized_name, family)
            grouped[key]["name"] = normalized_name
            grouped[key]["quantity"] = float(grouped[key]["quantity"]) + qty
            grouped[key]["unit"] = base_unit
            grouped[key]["category"] = _categorize(normalized_name)

    for name, qty in unquantified_counts.items():
        if name in quantified_names or qty <= 0:
            continue
        key = (name, "count")
        grouped[key]["name"] = name
        grouped[key]["quantity"] = float(grouped[key]["quantity"]) + qty
        grouped[key]["unit"] = "count"
        grouped[key]["category"] = _categorize(name)

    items: List[GroceryItem] = []
    for (_, _family), data in grouped.items():
        qty = float(data["quantity"])
        unit = data["unit"]
        name = str(data["name"])

        qty, unit, name = _normalize_display_unit_and_qty(name, qty, unit)
        qty, unit, name = _shopper_round(name, qty, unit)
        name, qty, unit = _combine_similar_name_and_unit(name, qty, unit)

        if qty <= 0:
            continue

        items.append(
            GroceryItem(
                name=name,
                quantity=qty,
                unit=unit,
                category=str(data["category"]) if data["category"] else _categorize(name),
            )
        )

    items.sort(key=lambda x: (x.category or "Other", x.name))
    return items

# formats the grocery list into a human readable format
def format_grocery_items(items: List[GroceryItem]) -> str:
    lines: List[str] = []

    for item in items:
        name = item.name.strip()
        if not name or item.quantity is None:
            continue

        qty = float(item.quantity)
        unit = item.unit

        if qty <= 0:
            continue

        qty_text = _format_quantity(qty)
        disp_unit = _display_unit(unit, qty)
        disp_name = _display_name(name, qty, unit)

        if disp_unit:
            lines.append(f"{qty_text} {disp_unit} {disp_name}")
        else:
            lines.append(f"{qty_text} {disp_name}")

    return "\n".join(lines)

# uses LLM to clean up araw grocery list
def _llm_refine_list(item_names: List[str]) -> Optional[str]:
    try:
        from agent.planner import _default_openai_client
    except ImportError:
        return None

    client = _default_openai_client()
    system = (
        "You are an assistant that converts a list of grocery items into a clean "
        "shopping list. The input lines are ingredient names already normalized "
        "from recipes; please deduplicate them, discard any that are still "
        "nonsensical, and output one simple bullet point or line per actual "
        "ingredient. Do not add measurements or quantities. Only return the list text."
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
    def generate(self, meal_plan: MealPlan, recipes_by_id: Dict[int, Recipe]) -> GroceryList:
        items = aggregate_ingredients(meal_plan, recipes_by_id)
        if not items:
            counts: Dict[str, float] = defaultdict(float)
            for meal in _extract_plan_meals(meal_plan):
                recipe_id = _get_meal_attr(meal, "recipe_id")
                if recipe_id is None:
                    continue
                recipe = recipes_by_id.get(recipe_id)
                if recipe is None:
                    continue
                for raw in getattr(recipe, "ingredients", []) or []:
                    normalized = _normalize_ingredient(str(raw))
                    if not normalized or _is_blacklisted(normalized):
                        continue
                    counts[normalized] += 1.0
            items = [
                GroceryItem(
                    name=name,
                    quantity=qty,
                    unit="count",
                    category=_categorize(name),
                )
                for name, qty in counts.items()
                if qty > 0
            ]
            items.sort(key=lambda x: (x.category or "Other", x.name))
        grocery = GroceryList(items=items)
        grocery.text = format_grocery_items(items)
        return grocery


# helper functions for cleaning, normalizing, and merging grocery items from the LLM 
def _planner_parse_quantity(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = _replace_unicode_fractions(str(value).strip())
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        mixed = re.fullmatch(r"(\d+)\s+(\d+)\s*/\s*(\d+)", s)
        if mixed:
            whole = float(mixed.group(1))
            num = float(mixed.group(2))
            den = float(mixed.group(3))
            return None if den == 0 else whole + (num / den)
        frac = re.fullmatch(r"(\d+)\s*/\s*(\d+)", s)
        if frac:
            num = float(frac.group(1))
            den = float(frac.group(2))
            return None if den == 0 else num / den
        m = re.search(r"\d+(?:\.\d+)?", s)
        if m:
            return float(m.group())
    return None


def _planner_clean_grocery_name(name: str) -> str:
    s = canonicalize_ingredient_name(name)
    if s in {"base_servings", "base servings", "ingredients", "ingredient", "none", "null", "n a"}:
        return ""
    if _is_blacklisted(s):
        return ""
    return s


def _planner_normalize_unit(unit):
    if unit is None:
        return None
    s = str(unit).strip().lower()
    if not s:
        return None
    return UNIT_ALIASES.get(s, s)


def _planner_extract_quantity_unit_and_name(name, quantity, unit):
    s = _replace_unicode_fractions(name.strip())
    if not s:
        return "", quantity, unit
    if quantity is None:
        m = re.match(r"^\s*(\d+(?:\.\d+)?|\d+\s+\d+/\d+|\d+/\d+)\s+(.*)$", s)
        if m:
            quantity = _planner_parse_quantity(m.group(1))
            s = m.group(2).strip()
    if unit is None:
        parts = s.split()
        if parts:
            u = UNIT_ALIASES.get(parts[0].lower())
            if u is not None:
                unit = u
                s = " ".join(parts[1:]).strip()
    return _planner_clean_grocery_name(s), quantity, _planner_normalize_unit(unit)


def _planner_normalize_grocery_name(name: str) -> str:
    return canonicalize_ingredient_name(name)


def _planner_convert_quantity(quantity: float, unit: str, name: str):
    family = PLANNER_UNIT_FAMILIES.get(unit, unit)
    base_unit, factor = PLANNER_BASE_CONVERSIONS.get(unit, (unit, 1.0))
    return quantity * factor, base_unit, family


def _planner_merge_grocery_items(items: List[GroceryItem]) -> List[GroceryItem]:
    merged: Dict[Tuple[str, str], GroceryItem] = {}
    merged_order: List[Tuple[str, str]] = []
    singles: List[GroceryItem] = []
    counts_by_key: Dict[str, int] = {}

    for item in items:
        key = _planner_normalize_grocery_name(item.name)
        if key:
            counts_by_key[key] = counts_by_key.get(key, 0) + 1

    for item in items:
        key = _planner_normalize_grocery_name(item.name)
        if not key:
            continue

        quantity = item.quantity
        unit = _planner_normalize_unit(item.unit)

        if quantity is None:
            continue
        if unit is None:
            unit = "count"

        if counts_by_key.get(key, 0) <= 1:
            singles.append(
                GroceryItem(
                    name=key,
                    quantity=float(quantity),
                    unit=unit,
                    category=item.category or _categorize(key),
                )
            )
            continue

        quantity, base_unit, family = _planner_convert_quantity(quantity, unit, key)
        merged_key = (key, family)

        if merged_key not in merged:
            merged[merged_key] = GroceryItem(
                name=key,
                quantity=quantity,
                unit=base_unit,
                category=item.category or _categorize(key),
            )
            merged_order.append(merged_key)
            continue

        current = merged[merged_key]
        current.quantity = (current.quantity or 0.0) + quantity
        current.unit = base_unit
        if current.category is None and item.category is not None:
            current.category = item.category

    out: List[GroceryItem] = []
    out.extend(singles)
    for merged_key in merged_order:
        gi = merged[merged_key]
        qty = float(gi.quantity or 0.0)
        unit = gi.unit
        name = gi.name

        if qty <= 0:
            continue

        gi.name = name
        gi.quantity = qty
        gi.unit = unit
        out.append(gi)

    out.sort(key=lambda x: (x.category or "Other", x.name))
    return out


def parse_grocery_list(raw: Dict[str, object]) -> GroceryList:
    items_raw = raw.get("grocery_list", []) if isinstance(raw, dict) else []
    items: List[GroceryItem] = []

    if not isinstance(items_raw, list):
        return GroceryList(items=items)

    for item in items_raw:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name", "")).strip()
        if not name:
            continue

        quantity = _planner_parse_quantity(item.get("quantity"))
        unit_raw = item.get("unit")
        unit = str(unit_raw).strip() if unit_raw not in (None, "", "null") else None

        clean_name, quantity, unit = _planner_extract_quantity_unit_and_name(name, quantity, unit)
        if not clean_name:
            continue
        if quantity is not None and unit is None:
            unit = "count"

        category_raw = item.get("category")
        items.append(
            GroceryItem(
                name=clean_name,
                quantity=quantity,
                unit=unit,
                category=str(category_raw).strip() if category_raw not in (None, "", "null") else _categorize(clean_name),
            )
        )

    grocery = GroceryList(items=_planner_merge_grocery_items(items))
    if isinstance(raw.get("grocery_text"), str):
        grocery.text = raw.get("grocery_text")
    elif grocery.items:
        grocery.text = format_grocery_items(grocery.items)
    return grocery
