from __future__ import annotations
from typing import List
import json
import re
from agent.interfaces import Recipe, UserProfile

# maps for normalization
ALLERGY_ALIASES = {
    "nut": "nuts",
    "nuts": "nuts",
    "tree nut": "nuts",
    "tree nuts": "nuts",

    "dairy": "dairy",
    "milk": "dairy",

    "gluten": "gluten",
    "gluten-free": "gluten",
    "gluten_free": "gluten",

    "soy": "soy",
    "soya": "soy",

    "egg": "eggs",
    "eggs": "eggs",
}

MEDICAL_ALIASES = {
    "none": None,
    "diabetes": "diabetes",
    "hypertension": "hypertension",
    "celiac": "celiac",
    "high cholesterol": "high_cholesterol",
    "high_cholesterol": "high_cholesterol",
}

# keyword maps for preferences and allergies
ALLERGY_KEYWORDS = {
    "nuts": [
        "peanut", "peanuts", "almond", "almonds", "cashew", "cashews",
        "walnut", "walnuts", "pecan", "pecans", "hazelnut", "hazelnuts",
        "pistachio", "pistachios", "macadamia", "macadamias",
        "nut butter", "peanut butter", "almond butter", "cashew butter",
        "almond flour", "mixed nuts", "trail mix",
    ],
    "dairy": [
        "milk", "cheese", "butter", "yogurt", "cream", "ghee",
        "buttermilk", "half-and-half", "half and half", "whey",
        "casein", "parmesan", "mozzarella", "cheddar", "feta",
        "ricotta", "cream cheese", "sour cream", "mascarpone",
        "cottage cheese",
    ],
    "gluten": [
        "wheat", "flour", "bread", "pasta", "barley", "rye",
        "couscous", "breadcrumbs", "breadcrumb", "noodle", "noodles",
        "cracker", "crackers", "bagel", "naan", "pita", "muffin",
        "semolina", "bulgur", "farro", "seitan", "ramen",
    ],
    "eggs": [
        "egg", "eggs", "egg white", "egg whites", "egg yolk", "egg yolks",
        "mayonnaise", "mayo", "meringue",
    ],
    "soy": [
        "soy", "soybean", "soybeans", "tofu", "tempeh", "miso",
        "edamame", "soy sauce", "tamari", "shoyu", "soy lecithin",
    ],
    "shellfish": [
        "shrimp", "crab", "lobster", "scallop", "scallops",
        "clam", "clams", "mussel", "mussels", "oyster", "oysters",
    ],
    "fish": [
        "fish", "salmon", "tuna", "cod", "tilapia", "trout", "roughy",
        "anchovy", "anchovies", "sardine", "sardines",
    ],
}

ALLERGY_TAG_MAP = {
    "nuts": "contains_nuts",
    "dairy": "contains_dairy",
    "gluten": "contains_gluten",
    "soy": "contains_soy",
    "eggs": "contains_eggs",
    "shellfish": "contains_shellfish",
    "fish": "contains_fish",
}

MEAT_KEYWORDS = [
    "chicken", "beef", "pork", "lamb", "turkey",
    "bacon", "sausage", "ham", "prosciutto", "pepperoni",
    "salami", "chorizo", "meatball", "meatballs",
    "steak", "sirloin", "ground beef", "ground turkey",
    "ground pork", "ground chicken", "ground lamb",
    "veal", "duck", "goat",
    "gelatin", "chicken broth", "beef broth", "bone broth",
    "burger", "hamburger", "hot dog", "hotdogs",
    "pancetta", "mortadella", "pastrami", "corned beef",
    "pulled pork", "ribs", "rib", "brisket",
    "meat sauce", "bolognese", "meat loaf", "meatloaf",
]

SEAFOOD_KEYWORDS = [
    "fish", "salmon", "tuna", "anchovy", "anchovies",
    "cod", "tilapia", "trout", "roughy", "sardine", "sardines",
    "shrimp", "crab", "lobster", "scallop", "scallops",
    "oyster", "oysters", "clam", "clams", "mussel", "mussels",
    "halibut", "mahi mahi", "catfish", "snapper", "haddock",
]

NON_VEG_KEYWORDS = MEAT_KEYWORDS + SEAFOOD_KEYWORDS

NON_VEGAN_KEYWORDS = NON_VEG_KEYWORDS + [
    "egg", "eggs", "milk", "cheese", "butter", "yogurt", "cream",
    "ghee", "buttermilk", "half-and-half", "half and half",
    "parmesan", "mozzarella", "cheddar", "feta",
    "honey", "whey", "casein",
]

DIABETES_TERMS = [
    "sugar", "brown sugar", "powdered sugar", "honey", "maple syrup",
    "corn syrup", "sweetened condensed milk", "candy", "cookie", "cake",
    "frosting", "icing", "pie", "juice concentrate", "syrup",
]

HYPERTENSION_TERMS = [
    "salt", "soy sauce", "teriyaki", "bouillon", "bacon",
    "ham", "sausage", "pepperoni", "salami", "prosciutto",
    "pickle", "pickles", "olives", "parmesan",
]

CHOLESTEROL_TERMS = [
    "bacon", "sausage", "butter", "cream", "cheese",
    "egg yolk", "egg yolks", "beef", "sirloin", "ham",
    "prosciutto", "pepperoni", "salami",
]

UNSUPPORTED_CATEGORIES = {"", "dessert", "side_dish", "sauce", "condiment", "drink_alcohol"}

# normalizes any list-like input into a list with everything in lowercase and no extra whitespace
def _norm_list(values: List[str] | None) -> List[str]:
    if not values:
        return []
    if isinstance(values, str):
        raw = values.strip()
        if not raw:
            return []
        if raw.startswith("[") and raw.endswith("]"):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(v).strip().lower() for v in parsed if v is not None and str(v).strip()]
            except json.JSONDecodeError:
                pass
        return [raw.lower()]
    return [str(v).strip().lower() for v in values if v is not None and str(v).strip()]


# normalization functions for allergies and conditions
def normalize_allergy(value: str) -> str | None:
    v = str(value).strip().lower()
    if not v:
        return None
    return ALLERGY_ALIASES.get(v, v)

def normalize_condition(value: str) -> str | None:
    v = str(value).strip().lower()
    if not v:
        return None
    return MEDICAL_ALIASES.get(v, v)

# helper function for checking if a term is in some text
def contains_term(text: str, term: str) -> bool:
    text = text.lower()
    term = term.lower().strip()
    if not term:
        return False
    pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
    return re.search(pattern, text) is not None

# helper function for checking whether at least one term from the terms list appears in the text
def contains_any(text: str, terms: List[str]) -> bool:
    return any(contains_term(text, term) for term in terms)

# combines the most relevant recipe fields into one text string
def recipe_search_text(recipe: Recipe) -> str:
    parts = []
    if recipe.title:
        parts.append(recipe.title.lower())

    parts.extend(_norm_list(recipe.ingredients))
    parts.extend(_norm_list(recipe.tags))

    if recipe.cuisine:
        parts.append(str(recipe.cuisine).lower())

    if hasattr(recipe, "category"):
        category = getattr(recipe, "category")
        if category is not None:
            parts.append(str(category).lower())

    return " ".join(parts)

# creates a dict of normalized fields for easier constraint checking for a recipe
def recipe_constraint_fields(recipe: Recipe) -> dict[str, str]:
    return {
        "title": (recipe.title or "").lower(),
        "ingredients": " ".join(_norm_list(recipe.ingredients)),
        "tags": " ".join(_norm_list(recipe.tags)),
        "cuisine": str(recipe.cuisine or "").lower(),
        "category": str(getattr(recipe, "category", "") or "").lower(),
    }

# helper function to return calories and estimates calories from macros if needed
def _get_calories(recipe: Recipe) -> float | None:
    if recipe.calories is not None:
        return recipe.calories
    if recipe.protein_g is None or recipe.carbs_g is None or recipe.fat_g is None:
        return None
    return 4 * recipe.protein_g + 4 * recipe.carbs_g + 9 * recipe.fat_g

# main function to check constraints
# checks a recipe against the user profile and returns a list of all the violations of the recipe
def recipe_violations(profile: UserProfile, recipe: Recipe) -> List[str]:
    violations = []

    fields = recipe_constraint_fields(recipe)
    constraint_text = " ".join([fields["ingredients"], fields["tags"], fields["title"]])

    prefs = set(_norm_list(profile.dietary_preferences))
    allergies = {a for a in (normalize_allergy(x) for x in _norm_list(profile.allergies))if a}
    conditions = {c for c in (normalize_condition(x) for x in _norm_list(profile.medical_conditions))if c}

    if hasattr(recipe, "category"):
        raw_category = getattr(recipe, "category")
    else:
        raw_category = None

    if raw_category is None:
        recipe_category = None
    else:
        recipe_category = str(raw_category).strip().lower()
        if recipe_category == "":
            recipe_category = None
    recipe_tags = set(_norm_list(getattr(recipe, "tags", [])))

    if recipe_category is not None and recipe_category in UNSUPPORTED_CATEGORIES:
        violations.append("category:unsupported")

    for allergy in allergies:
        structured_tag = ALLERGY_TAG_MAP.get(allergy)
        keywords = ALLERGY_KEYWORDS.get(allergy, [])

        if structured_tag and structured_tag in recipe_tags:
            violations.append(f"allergy:{allergy}")
        elif keywords and contains_any(constraint_text, keywords):
            violations.append(f"allergy:{allergy}")

    if "vegetarian" in prefs:
        if "vegetarian" not in recipe_tags:
            violations.append("diet:vegetarian")
        if any(tag in recipe_tags for tag in {"contains_fish", "contains_shellfish"}):
            violations.append("diet:vegetarian")
        if contains_any(constraint_text, NON_VEG_KEYWORDS):
            violations.append("diet:vegetarian")

    if "vegan" in prefs:
        if "vegan" not in recipe_tags and contains_any(constraint_text, NON_VEGAN_KEYWORDS):
            violations.append("diet:vegan")

    if "pescatarian" in prefs:
        if "pescatarian" not in recipe_tags and contains_any(constraint_text, MEAT_KEYWORDS):
            violations.append("diet:pescatarian")

    if "gluten_free" in prefs or "gluten-free" in prefs:
        if "contains_gluten" in recipe_tags:
            violations.append("diet:gluten_free")
        elif "gluten_free" not in recipe_tags and contains_any(constraint_text, ALLERGY_KEYWORDS["gluten"]):
            violations.append("diet:gluten_free")

    carbs = recipe.carbs_g if recipe.carbs_g is not None else 0.0

    if "low_carb" in prefs or "low-carb" in prefs:
        if "low_carb" not in recipe_tags and carbs > 35:
            violations.append("diet:low_carb")

    if "keto" in prefs:
        if "keto" not in recipe_tags and carbs > 20:
            violations.append("diet:keto")

    fat = recipe.fat_g or 0.0
    sodium_mg = getattr(recipe, "sodium_mg", None)
    saturated_fat_g = getattr(recipe, "saturated_fat_g", None)
    cholesterol_mg = getattr(recipe, "cholesterol_mg", None)

    if "diabetes" in conditions:
        if "diabetes_friendly" not in recipe_tags:
            if carbs >= 45 or contains_any(constraint_text, DIABETES_TERMS):
                violations.append("medical:diabetes")

    if "hypertension" in conditions:
        if "low_sodium" not in recipe_tags:
            high_sodium = sodium_mg is not None and sodium_mg > 700
            if high_sodium or contains_any(constraint_text, HYPERTENSION_TERMS):
                violations.append("medical:hypertension")

    if "celiac" in conditions:
        if "contains_gluten" in recipe_tags:
            violations.append("medical:celiac")
        elif "gluten_free" not in recipe_tags and contains_any(constraint_text, ALLERGY_KEYWORDS["gluten"]):
            violations.append("medical:celiac")

    if "high_cholesterol" in conditions:
        if "heart_healthy" not in recipe_tags:
            too_much_sat_fat = saturated_fat_g is not None and saturated_fat_g > 6
            too_much_cholesterol = cholesterol_mg is not None and cholesterol_mg > 100

            if (
                too_much_sat_fat
                or too_much_cholesterol
                or fat >= 20
                or contains_any(constraint_text, CHOLESTEROL_TERMS)
            ):
                violations.append("medical:high_cholesterol")

    return sorted(set(violations))


def is_allowed(profile: UserProfile, recipe: Recipe) -> bool:
    return len(recipe_violations(profile, recipe)) == 0

# helper function to filter a list of recipes based on whether they are allowed for a given user profile
def filter_allowed(profile: UserProfile, recipes: List[Recipe]) -> List[Recipe]:
    return [r for r in recipes if is_allowed(profile, r)]
