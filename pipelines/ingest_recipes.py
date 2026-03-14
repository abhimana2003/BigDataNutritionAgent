import ast
import os
import re
import sys
from pathlib import Path
import pandas as pd
from sqlalchemy.orm import Session
from database import engine, SessionLocal, Base
from models import Recipe


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def contains_term(text: str, term: str) -> bool:
    text = (text or "").lower()
    term = (term or "").strip().lower()
    if not term:
        return False
    pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
    return re.search(pattern, text) is not None


def contains_any(text: str, terms: list[str]) -> bool:
    return any(contains_term(text, term) for term in terms)


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

DAIRY_OR_EGG_KEYWORDS = [
    "milk", "cheese", "cream", "butter", "yogurt", "egg",
    "eggs", "ghee", "half-and-half", "half and half",
    "buttermilk", "parmesan", "mozzarella", "cheddar", "feta",
    "ricotta", "cream cheese", "sour cream", "mascarpone",
    "cottage cheese", "honey", "whey", "casein",
]

GLUTEN_KEYWORDS = [
    "flour", "bread", "pasta", "wheat", "barley", "rye",
    "couscous", "breadcrumbs", "breadcrumb", "noodle", "noodles",
    "cracker", "crackers", "bagel", "naan", "pita", "muffin",
    "semolina", "bulgur", "farro", "seitan", "ramen",
]

ALLERGEN_TAG_RULES = {
    "contains_nuts": [
        "peanut", "peanuts", "almond", "almonds", "cashew", "cashews",
        "walnut", "walnuts", "pecan", "pecans", "hazelnut", "hazelnuts",
        "pistachio", "pistachios", "macadamia", "macadamias",
        "nut butter", "peanut butter", "almond butter", "cashew butter",
        "almond flour", "mixed nuts", "trail mix",
    ],
    "contains_dairy": [
        "milk", "cheese", "butter", "yogurt", "cream", "ghee",
        "buttermilk", "half-and-half", "half and half", "whey",
        "casein", "parmesan", "mozzarella", "cheddar", "feta",
        "ricotta", "cream cheese", "sour cream", "mascarpone",
        "cottage cheese",
    ],
    "contains_gluten": GLUTEN_KEYWORDS,
    "contains_soy": [
        "soy", "soybean", "soybeans", "tofu", "tempeh", "miso",
        "edamame", "soy sauce", "tamari", "shoyu", "soy lecithin",
    ],
    "contains_eggs": [
        "egg", "eggs", "egg white", "egg whites", "egg yolk", "egg yolks",
        "mayonnaise", "mayo", "meringue",
    ],
    "contains_fish": [
        "fish", "salmon", "tuna", "cod", "tilapia", "trout", "roughy",
        "anchovy", "anchovies", "sardine", "sardines",
    ],
    "contains_shellfish": [
        "shrimp", "crab", "lobster", "scallop", "scallops",
        "clam", "clams", "mussel", "mussels", "oyster", "oysters",
    ],
}

LOW_SODIUM_TERMS = [
    "low sodium", "low-sodium", "no salt added", "reduced sodium", "reduced-sodium"
]

HEART_HEALTHY_TERMS = [
    "heart healthy", "heart-healthy"
]

DIABETES_FRIENDLY_TERMS = [
    "diabetic friendly", "diabetes friendly", "low sugar", "low-sugar", "no added sugar"
]


def safe_parse(value):
    if pd.isna(value):
        return None
    try:
        return ast.literal_eval(str(value))
    except (ValueError, SyntaxError):
        return str(value)


def parse_nutrition(value):
    parsed = safe_parse(value)

    def clean_num(v):
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        cleaned = re.sub(r"[^\d.]", "", s)
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    if isinstance(parsed, dict):
        lowered = {str(k).strip().lower(): v for k, v in parsed.items()}

        def get_any(*keys):
            for key in keys:
                if key in lowered:
                    num = clean_num(lowered[key])
                    if num is not None:
                        return num
            return None

        calories = get_any("calories", "energy")
        protein = get_any("protein", "protein_g")
        carbs = get_any("carbs", "carbohydrate", "carbohydrates", "total carbohydrate", "carbs_g")
        fat = get_any("fat", "total fat", "fat_g")
        sodium = get_any("sodium", "sodium_mg")
        sugar = get_any("sugar", "sugars", "sugar_g")
        fiber = get_any("fiber", "fibre", "fiber_g")
        saturated_fat = get_any("saturated fat", "saturated_fat", "saturated_fat_g")
        cholesterol = get_any("cholesterol", "cholesterol_mg")

        if calories is None and None not in (protein, carbs, fat):
            calories = 4 * protein + 4 * carbs + 9 * fat

        if any(v is not None for v in [calories, protein, carbs, fat, sodium, sugar, fiber, saturated_fat, cholesterol]):
            return {
                "calories": calories,
                "protein": protein,
                "carbs": carbs,
                "fat": fat,
                "sodium_mg": sodium,
                "sugar_g": sugar,
                "fiber_g": fiber,
                "saturated_fat_g": saturated_fat,
                "cholesterol_mg": cholesterol,
            }

    if isinstance(parsed, str):
        text = parsed

        def extract(pattern):
            m = re.search(pattern, text, flags=re.IGNORECASE)
            return float(m.group(1)) if m else None

        fat = extract(r"Total\s+Fat\s+(\d+(?:\.\d+)?)\s*g")
        saturated_fat = extract(r"Saturated\s+Fat\s+(\d+(?:\.\d+)?)\s*g")
        carbs = extract(r"Total\s+Carbohydrate\s+(\d+(?:\.\d+)?)\s*g")
        sugar = extract(r"(?:Total\s+Sugars|Sugars?)\s+(\d+(?:\.\d+)?)\s*g")
        fiber = extract(r"(?:Dietary\s+Fiber|Fibre|Fiber)\s+(\d+(?:\.\d+)?)\s*g")
        protein = extract(r"\bProtein\s+(\d+(?:\.\d+)?)\s*g\b")
        sodium = extract(r"Sodium\s+(\d+(?:\.\d+)?)\s*mg")
        cholesterol = extract(r"Cholesterol\s+(\d+(?:\.\d+)?)\s*mg")
        calories = extract(r"(?:Calories|Energy)\s*[: ]\s*(\d+(?:\.\d+)?)")

        if calories is None and None not in (protein, carbs, fat):
            calories = 4 * protein + 4 * carbs + 9 * fat

        if any(v is not None for v in [calories, protein, carbs, fat, sodium, sugar, fiber, saturated_fat, cholesterol]):
            return {
                "calories": calories,
                "protein": protein,
                "carbs": carbs,
                "fat": fat,
                "sodium_mg": sodium,
                "sugar_g": sugar,
                "fiber_g": fiber,
                "saturated_fat_g": saturated_fat,
                "cholesterol_mg": cholesterol,
            }

    return None


def parse_ingredients(value):
    parsed = safe_parse(value)
    if isinstance(parsed, list):
        out = []
        for item in parsed:
            t = str(item).strip()
            if t:
                out.append(t)
        return out
    if isinstance(parsed, str):
        parts = [p.strip() for p in parsed.split(",") if p and p.strip()]
        return parts if parts else None
    return None


def parse_directions(value):
    parsed = safe_parse(value)
    if isinstance(parsed, list):
        out = []
        for item in parsed:
            t = str(item).strip()
            if t:
                out.append(t)
        return out if out else None
    if isinstance(parsed, str):
        text = parsed.strip()
        if not text:
            return None
        steps = re.split(r"(?<=[.!?])\s+", text)
        steps = [s.strip() for s in steps if s.strip()]
        return steps if steps else [text]
    return None


def derive_dietary_tags(recipe_name=None, ingredients_list=None, nutrition=None):
    text_parts = []

    if recipe_name:
        text_parts.append(str(recipe_name).lower())

    if ingredients_list and isinstance(ingredients_list, list):
        text_parts.append(" ".join(str(x).lower() for x in ingredients_list if x))

    text = " ".join(part for part in text_parts if part).strip()
    if not text:
        return []

    tags = []

    has_meat = contains_any(text, MEAT_KEYWORDS)
    has_seafood = contains_any(text, SEAFOOD_KEYWORDS)
    has_dairy_or_egg = contains_any(text, DAIRY_OR_EGG_KEYWORDS)
    has_gluten = contains_any(text, GLUTEN_KEYWORDS)

    carbs = None
    if isinstance(nutrition, dict):
        carbs = nutrition.get("carbs")
        try:
            carbs = float(carbs) if carbs is not None else None
        except (TypeError, ValueError):
            carbs = None

    if not has_meat and not has_seafood:
        tags.append("vegetarian")

    if not has_meat and not has_seafood and not has_dairy_or_egg:
        tags.append("vegan")

    if not has_meat:
        tags.append("pescatarian")

    if not has_gluten:
        tags.append("gluten_free")

    if carbs is not None:
        if carbs <= 20:
            tags.append("keto")
            tags.append("low_carb")
        elif carbs <= 35:
            tags.append("low_carb")

    return sorted(set(tags))


def derive_health_and_allergen_tags(recipe_name, ingredients_list, existing_tags=None, nutrition=None):
    existing = {
        str(t).strip().lower()
        for t in (existing_tags or [])
        if t is not None and str(t).strip()
    }

    text_parts = []
    if recipe_name:
        text_parts.append(str(recipe_name).lower())
    if ingredients_list:
        text_parts.append(" ".join(str(x).strip().lower() for x in ingredients_list if str(x).strip()))
    if existing:
        text_parts.append(" ".join(sorted(existing)))

    text = " ".join(text_parts)

    for tag, terms in ALLERGEN_TAG_RULES.items():
        if contains_any(text, terms):
            existing.add(tag)

    if contains_any(text, LOW_SODIUM_TERMS):
        existing.add("low_sodium")

    if contains_any(text, HEART_HEALTHY_TERMS):
        existing.add("heart_healthy")

    if contains_any(text, DIABETES_FRIENDLY_TERMS):
        existing.add("diabetes_friendly")

    if isinstance(nutrition, dict):
        sodium = nutrition.get("sodium_mg")
        sugar = nutrition.get("sugar_g")
        fiber = nutrition.get("fiber_g")
        saturated_fat = nutrition.get("saturated_fat_g")
        cholesterol = nutrition.get("cholesterol_mg")
        carbs = nutrition.get("carbs")

        try:
            sodium = float(sodium) if sodium is not None else None
        except (TypeError, ValueError):
            sodium = None
        try:
            sugar = float(sugar) if sugar is not None else None
        except (TypeError, ValueError):
            sugar = None
        try:
            fiber = float(fiber) if fiber is not None else None
        except (TypeError, ValueError):
            fiber = None
        try:
            saturated_fat = float(saturated_fat) if saturated_fat is not None else None
        except (TypeError, ValueError):
            saturated_fat = None
        try:
            cholesterol = float(cholesterol) if cholesterol is not None else None
        except (TypeError, ValueError):
            cholesterol = None
        try:
            carbs = float(carbs) if carbs is not None else None
        except (TypeError, ValueError):
            carbs = None

        if sodium is not None and sodium <= 300:
            existing.add("low_sodium")

        if (saturated_fat is not None and saturated_fat <= 3) and (cholesterol is not None and cholesterol <= 20):
            existing.add("heart_healthy")

        if (carbs is not None and carbs <= 20) and (
            (sugar is None or sugar <= 8) and (fiber is None or fiber >= 3)
        ):
            existing.add("diabetes_friendly")

    return sorted(existing)


def estimate_cost(ingredients_list, cost_per_item=0.75):
    if not ingredients_list or not isinstance(ingredients_list, list):
        return None
    return round(len(ingredients_list) * cost_per_item, 2)


def parse_minutes(value):
    if pd.isna(value):
        return None
    s = str(value).strip().lower()
    if not s:
        return None
    as_int = re.fullmatch(r"\d+", s)
    if as_int:
        return int(s)
    hours_match = re.search(r"(\d+)\s*h", s)
    mins_match = re.search(r"(\d+)\s*m", s)
    hours = int(hours_match.group(1)) if hours_match else 0
    mins = int(mins_match.group(1)) if mins_match else 0
    total = hours * 60 + mins
    if total > 0:
        return total
    fallback = re.search(r"\d+", s)
    if fallback:
        return int(fallback.group())
    return None


def parse_servings(value):
    if pd.isna(value):
        return None
    s = str(value).strip().lower()
    if not s:
        return None
    match = re.search(r"\d+", s)
    if not match:
        return None
    return int(match.group())


def get_category(cuisine_path: str | None) -> str | None:
    if not cuisine_path:
        return None

    path = str(cuisine_path).strip().lower()

    if path.startswith("/breakfast and brunch/"):
        return "breakfast"
    if path.startswith("/everyday cooking/vegan/breakfast and brunch/"):
        return "breakfast"
    if path.startswith("/drinks recipes/smoothie recipes/"):
        return "breakfast"

    if path.startswith("/desserts/"):
        return "dessert"
    if path.startswith("/everyday cooking/vegan/desserts/"):
        return "dessert"
    if path.startswith("/holidays and events recipes/christmas/desserts/"):
        return "dessert"

    if path.startswith("/appetizers and snacks/"):
        return "snack"

    if path.startswith("/drinks recipes/"):
        alcoholic_terms = [
            "/cocktail recipes/",
            "/liqueur recipes/",
            "/sangria recipes/",
            "/shot recipes/",
            "/adult punch recipes/",
            "/gin drinks recipes/",
            "/rum drinks recipes/",
            "/tequila drinks recipes/",
            "/vodka drinks recipes/",
            "/whiskey drinks recipes/",
        ]
        if any(term in path for term in alcoholic_terms):
            return None
        return "snack"

    if path.startswith("/bread/"):
        return "snack"
    if path.startswith("/quick bread recipes/"):
        return "snack"

    if path.startswith("/main dishes/"):
        return "main_meal"

    if path.startswith("/meat and poultry/"):
        if "/appetizers/" in path:
            return "snack"
        return "main_meal"
    if path.startswith("/soups, stews and chili recipes/"):
        return "main_meal"
    if path.startswith("/soup recipes/"):
        return "main_meal"
    if path.startswith("/seafood/"):
        return "main_meal"
    if path.startswith("/mexican/main dishes/"):
        return "main_meal"
    if path.startswith("/bbq & grilling/chicken/"):
        return "main_meal"
    if path.startswith("/holidays and events recipes/thanksgiving/turkey/roasted/"):
        return "main_meal"

    if path.startswith("/salad/"):
        snack_salad_terms = [
            "/fruit salad recipes/",
            "/waldorf salad recipes/",
        ]
        if any(term in path for term in snack_salad_terms):
            return "snack"
        return "main_meal"

    if path.startswith("/side dish/"):
        return None
    if path.startswith("/sauces and condiments/"):
        return None
    if path.startswith("/fruits and vegetables/"):
        return None
    if path.startswith("/trusted brands: recipes and tips/"):
        return None
    if path.startswith("/cuisine/"):
        return None
    if path.startswith("/everyday cooking/"):
        return None
    if path.startswith("/holidays and events recipes/"):
        return None

    return None


def ingest(csv_path: str = "data/raw/recipes.csv", force: bool = False):
    Base.metadata.create_all(bind=engine)
    if not Path(csv_path).exists():
        fallback = Path("data/raw/archive/recipes.csv")
        if fallback.exists():
            csv_path = str(fallback)

    df = pd.read_csv(csv_path)
    db: Session = SessionLocal()

    force = force or os.getenv("FORCE_REINGEST", "").strip().lower() in {"1", "true", "yes"}
    if force:
        print("FORCE_REINGEST enabled. Clearing existing recipes before ingestion.")
        db.query(Recipe).delete()
        db.commit()

    if db.query(Recipe).count() > 0:
        print("Recipes table already populated. Skipping ingestion.")
        db.close()
        return

    records = []
    for _, row in df.iterrows():
        ingredients = parse_ingredients(row.get("ingredients"))
        nutrition = parse_nutrition(row.get("nutrition"))
        directions = parse_directions(row.get("directions"))
        cuisine_path = str(row.get("cuisine_path")) if pd.notna(row.get("cuisine_path")) else None
        category = get_category(cuisine_path)

        if category is None:
            continue

        dietary_tags = derive_dietary_tags(
            recipe_name=str(row.get("recipe_name", "Unknown")),
            ingredients_list=ingredients if isinstance(ingredients, list) else [],
            nutrition=nutrition,
        )

        full_tags = derive_health_and_allergen_tags(
            recipe_name=str(row.get("recipe_name", "Unknown")),
            ingredients_list=ingredients if isinstance(ingredients, list) else [],
            existing_tags=dietary_tags,
            nutrition=nutrition,
        )

        recipe = Recipe(
            recipe_name=str(row.get("recipe_name", "Unknown")),
            prep_time=parse_minutes(row.get("prep_time")),
            cook_time=parse_minutes(row.get("cook_time")),
            total_time=parse_minutes(row.get("total_time")),
            servings=parse_servings(row.get("servings")),
            ingredients=ingredients if isinstance(ingredients, list) else None,
            directions=directions,
            rating=float(row["rating"]) if pd.notna(row.get("rating")) else None,
            url=str(row.get("url", "")),
            cuisine_path=cuisine_path,
            category=category,
            nutrition=nutrition,
            timing=safe_parse(row.get("timing")),
            dietary_tags=full_tags,
            estimated_cost=estimate_cost(ingredients if isinstance(ingredients, list) else []),
        )

        records.append(recipe)

    db.bulk_save_objects(records)
    db.commit()
    db.close()
    print(f"Ingested {len(records)} recipes.")


if __name__ == "__main__":
    ingest()