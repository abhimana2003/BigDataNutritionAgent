import ast
import re
import sys
from pathlib import Path
import pandas as pd
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import engine, SessionLocal, Base
from models import Recipe


MEAT_KEYWORDS = ["chicken", "beef", "pork", "lamb", "turkey", "bacon", "sausage", "fish", "salmon", "shrimp", "tuna"]
GLUTEN_INGREDIENTS = ["flour", "bread", "pasta", "wheat", "barley", "rye", "couscous"]

def safe_parse(value):
    if pd.isna(value):
        return None
    try:
        return ast.literal_eval(str(value))
    except (ValueError, SyntaxError):
        return str(value)

def parse_nutrition(value):
    parsed = safe_parse(value)
    if isinstance(parsed, dict):
        result = {}
        for k, v in parsed.items():
            try:
                result[k] = float(re.sub(r"[^\d.]", "", str(v)))
            except ValueError:
                result[k] = 0.0
        return result
    if isinstance(parsed, str):
        text = parsed
        def extract(pattern):
            m = re.search(pattern, text, flags=re.IGNORECASE)
            return float(m.group(1)) if m else None

        fat = extract(r"Total\s+Fat\s+(\d+(?:\.\d+)?)\s*g")
        carbs = extract(r"Total\s+Carbohydrate\s+(\d+(?:\.\d+)?)\s*g")
        protein = extract(r"\bProtein\s+(\d+(?:\.\d+)?)\s*g\b")
        calories = extract(r"(?:Calories|Energy)\s*[: ]\s*(\d+(?:\.\d+)?)")
        if calories is None and None not in (protein, carbs, fat):
            calories = 4 * protein + 4 * carbs + 9 * fat

        if any(v is not None for v in (calories, protein, carbs, fat)):
            return {
                "calories": calories,
                "protein": protein,
                "carbs": carbs,
                "fat": fat,
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

def derive_dietary_tags(ingredients_list):
    if not ingredients_list or not isinstance(ingredients_list, list):
        return []
    text = " ".join(ingredients_list).lower()
    tags = []

    has_meat = any(m in text for m in MEAT_KEYWORDS)
    has_gluten = any(g in text for g in GLUTEN_INGREDIENTS)

    if not has_meat:
        tags.append("vegetarian")
        dairy_words = ["milk", "cheese", "cream", "butter", "yogurt", "egg"]
        if not any(d in text for d in dairy_words):
            tags.append("vegan")
    if not has_gluten:
        tags.append("gluten_free")

    return tags

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

def ingest(csv_path: str = "data/raw/recipes.csv"):
    Base.metadata.create_all(bind=engine)
    if not Path(csv_path).exists():
        fallback = Path("data/raw/archive/recipes.csv")
        if fallback.exists():
            csv_path = str(fallback)
    df = pd.read_csv(csv_path)
    db: Session = SessionLocal()

    if db.query(Recipe).count() > 0:
        print("Recipes table already populated. Skipping ingestion.")
        db.close()
        return

    records = []
    for _, row in df.iterrows():
        ingredients = parse_ingredients(row.get("ingredients"))
        nutrition = parse_nutrition(row.get("nutrition"))
        directions = parse_directions(row.get("directions"))

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
            cuisine_path=str(row.get("cuisine_path")) if pd.notna(row.get("cuisine_path")) else None,
            nutrition=nutrition,
            timing=safe_parse(row.get("timing")),
            dietary_tags=derive_dietary_tags(ingredients if isinstance(ingredients, list) else []),
            estimated_cost=estimate_cost(ingredients if isinstance(ingredients, list) else []),
        )

        records.append(recipe)

    db.bulk_save_objects(records)
    db.commit()
    db.close()
    print(f"Ingested {len(records)} recipes.")


if __name__ == "__main__":
    ingest()
