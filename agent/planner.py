# meal plan generator module
from __future__ import annotations
import ast
import json
import logging
import os
import re
import time
from typing import Any, Callable, Dict, List, Optional
from agent.interfaces import DayPlan, GroceryItem, GroceryList, MealPlan, MealSlot, Planner, PlannedMeal,Recipe, RecipeCandidate,UserProfile
from agent.grocery import SimpleGroceryGenerator, parse_grocery_list
from agent.scoring import is_slot_compatible

logger = logging.getLogger(__name__)

VALID_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}

UNIT_ALIASES = {
    "cup": "cup",
    "cups": "cup",
    "tbsp": "tbsp",
    "tbsps": "tbsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tsp": "tsp",
    "tsps": "tsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "oz": "oz",
    "ounce": "oz",
    "ounces": "oz",
    "lb": "lb",
    "lbs": "lb",
    "pound": "lb",
    "pounds": "lb",
    "g": "g",
    "gram": "g",
    "grams": "g",
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "ml": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "l": "l",
    "liter": "l",
    "liters": "l",
    "bunch": "bunch",
    "bag": "bag",
    "carton": "carton",
    "dozen": "dozen",
    "can": "can",
    "jar": "jar",
    "bottle": "bottle",
    "loaf": "loaf",
    "count": "count",
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
}

UNIT_TO_BASE = {
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
    "dozen": ("count", 12.0),
}

DROP_GROCERY_NAMES = {"base_servings", "base servings", "ingredients", "ingredient", "none", "null", "n/a"}
DROP_GROCERY_WORDS = {
    "fresh", "frozen", "dried", "ground", "seasoned", "blend", "pitted", "canned", "low", "fat", "lowfat",
    "skinless", "boneless", "sliced", "slice", "sprigs", "sprig", "leaves", "leaf",
}
GROCERY_BLACKLIST = {"salt", "pepper", "black pepper", "salt pepper", "salt and pepper"}

# Prompt template

# sets general context and instructions for LLM
SYSTEM_PROMPT = """\
You are a professional nutritionist AI. You create personalized 7-day meal plans.
You MUST reply with valid JSON only — no markdown fences, no commentary outside the JSON.
"""

# sets instructions for each request from user
USER_PROMPT_TEMPLATE = """\
Create a 7-day meal plan using ONLY the recipes listed below.

## User Profile
- Goal: {goal}
- Dietary preferences: {dietary_preferences}
- Allergies: {allergies}
- Budget level: {budget_level}
- Cooking time preference: {cooking_time}

## Daily Nutritional Targets
- Calories: {daily_calories} kcal
- Protein: {protein_g} g
- Carbs: {carbs_g} g
- Fat: {fat_g} g

## Available Recipes (id | title | kcal | protein | carbs | fat | cost | minutes)
{recipe_table}

(Note: the table above now also includes an "Ingredients:" section listing the
ingredients for each recipe id.  Use those ingredient lists when constructing
your grocery list.)

## Allowed Recipe IDs By Meal Type (must follow)
- Breakfast IDs: {breakfast_ids}
- Lunch IDs: {lunch_ids}
- Dinner IDs: {dinner_ids}

## Rules
1. Each day MUST have exactly 3 meals: breakfast, lunch, dinner.
2. Use a variety of recipes — avoid repeating the same recipe on consecutive days.
3. Try to keep each day's total nutrition close to the daily targets.
4. Respect the user's budget and cooking-time preference.
5. Only use recipe_id values from the list above.
6. Ensure each recipe logically fits the meal type:
   - Breakfast meals should resemble common breakfast foods.
   - Lunch and dinner meals should resemble typical main savory meals.
   - Do not assign recipes to meal types that would feel unrealistic or inappropriate.
   - You MUST only use IDs from the corresponding allowed list above.
7. Do NOT assign alcohol-based recipes or meals containing alcoholic beverages (wine, beer, liquor, spirits, cocktails).
8. Ensure each meal has good sustenance: prefer nutritionally meaningful, filling meals (include a substantial protein/fiber/carb component) and avoid assigning very light snack-like items as full meals.
9. Do not repeat the same recipe more than twice in the 7-day plan, unless there are very limited options for a meal type. In that case, you may repeat a recipe but try to maximize variety and avoid repeating on consecutive days.

## Required JSON output format
{{
  "days": [
    {{
      "day": 1,
      "meals": [
        {{"meal_type": "breakfast", "recipe_id": <int>, "title": "<str>", "servings": <int>}},
        {{"meal_type": "lunch",     "recipe_id": <int>, "title": "<str>", "servings": <int>}},
        {{"meal_type": "dinner",    "recipe_id": <int>, "title": "<str>", "servings": <int>}}
      ]
    }}
  ],
  "grocery_list": [
    {{
      "name": "<ingredient name>",
      "quantity": <number>,
      "unit": "<unit or null>",
      "category": "<produce|protein|dairy|grains|pantry|spices|other>"
    }}
  ],
  "notes": "<optional brief note>"
}}

## Grocery list rules
1. Aggregate ingredients across all 7 days into ONE consolidated list.
2. ONLY include items that can be physically purchased in a grocery store.
3. Remove all preparation/cooking instructions (e.g. "drained", "rinsed", "beaten", "melted", etc.).
4. Remove all quantity descriptors and measurements (e.g. "1 cup", "2 tbsp", "large", "small").
5. Remove all cooking instructions (e.g. "at room temperature", "chopped", "diced", "sliced").
6. Normalize names: "dry bread crumbs" → "bread crumbs", "cooked chicken" → "chicken breast", etc.
7. Exclude trivial pantry staples: water, salt, pepper, oil, garlic powder, paprika, vanilla, cinnamon.
8. Merge duplicates (same ingredient) into one item with summed quantity when possible.
9. Use null for unknown unit/quantity.
10. Return ONLY ingredient names that a shopper would look for in a store, nothing else.

## Examples of what to include vs. exclude:
INCLUDE: "chicken breast", "olive oil", "spinach", "lemon", "salmon", "greek yogurt", "bread crumbs"
EXCLUDE: "drained rinsed", "at room temperature", "chopped", "patted dry", "ice cube", "water", "salt", "pepper"

Respond ONLY with the JSON object.
"""

# categorizes recipes in general meal families
def meal_family(recipe: Recipe) -> str:
    text = " ".join([recipe.title or "",recipe.cuisine or "", " ".join(recipe.ingredients or []),]).lower()
    if "salad" in text:
        return "salad"

    if any(x in text for x in ["soup", "stew", "chili", "gazpacho", "bisque"]):
        return "soup_stew"

    if any(x in text for x in ["pasta", "spaghetti", "penne", "macaroni", "lasagna", "risotto"]):
        return "pasta"

    if any(x in text for x in ["sandwich", "wrap", "burger", "panini", "melt"]):
        return "sandwich_wrap"

    if any(x in text for x in ["taco", "quesadilla", "fajita", "burrito", "enchilada"]):
        return "taco_mexican"

    if any(x in text for x in ["rice bowl", "grain bowl", "quinoa bowl", "bowl", "rice", "quinoa"]):
        return "bowl_rice_grain"

    if any(x in text for x in ["stir-fry", "stir fry"]):
        return "stir_fry"

    if any(x in text for x in ["casserole", "bake", "baked ziti", "meatloaf"]):
        return "casserole_bake"

    return "other"


# converts recipe candidates into text rows to include in the prompt
def build_recipe_table(candidates: List[RecipeCandidate]) -> str:
    """
    Builds a text block for the recipe candidates to include in the prompt, consisting of:  
    1. a summary table (id, title, macros, cost, minutes)
    2. a ingredients list for each recipe
    """
    summary_rows = []
    ingredient_rows = []
    for c in candidates:
        r = c.recipe
        if r is None:
            continue
        summary_rows.append(
            f"{r.recipe_id} | {r.title} | "
            f"{r.calories or 0:.0f} | {r.protein_g or 0:.0f} | "
            f"{r.carbs_g or 0:.0f} | {r.fat_g or 0:.0f} | "
            f"${r.estimated_cost or 0:.2f} | {r.total_minutes or 0} min"
        )
        if r.ingredients:
            # join ingredients list into one comma-separated string
            ing_text = ", ".join(str(i) for i in r.ingredients)
            ingredient_rows.append(f"{r.recipe_id}: {ing_text}")
    return "\n".join(summary_rows) + "\n\nIngredients:\n" + "\n".join(ingredient_rows)

# inserts all the user profile info and recipe candidates into the prompt template
def fill_in_prompt(profile: UserProfile, candidates: List[RecipeCandidate],nutrition_targets: Dict[str, float]) -> str:
    allowed_ids = build_allowed_ids_by_meal_type(candidates)
    breakfast_ids = ", ".join(str(i) for i in allowed_ids["breakfast"]) or "none"
    lunch_ids = ", ".join(str(i) for i in allowed_ids["lunch"]) or "none"
    dinner_ids = ", ".join(str(i) for i in allowed_ids["dinner"]) or "none"
    return USER_PROMPT_TEMPLATE.format(
        goal=profile.goal,
        dietary_preferences=", ".join(profile.dietary_preferences) or "none",
        allergies=", ".join(profile.allergies) or "none",
        budget_level=profile.budget_level,
        cooking_time=profile.cooking_time,
        daily_calories=nutrition_targets.get("daily_calories", 2000),
        protein_g=nutrition_targets.get("protein_g", 100),
        carbs_g=nutrition_targets.get("carbs_g", 250),
        fat_g=nutrition_targets.get("fat_g", 65),
        recipe_table=build_recipe_table(candidates),
        breakfast_ids=breakfast_ids,
        lunch_ids=lunch_ids,
        dinner_ids=dinner_ids,
    )

# Converts the inputted meal plan object intoa text block
def build_meal_plan_lines(plan: MealPlan) -> str:
    lines = []
    for day in plan.days:
        for meal in day.meals:
            lines.append(
                f"day {day.day} | {meal.meal_type} | recipe_id={meal.recipe_id} | "
                f"title={meal.title} | planned_servings={meal.servings}"
            )
    return "\n".join(lines) if lines else "none"

# Converts the inputted meal plan object into a text block listing the unique recipes and their ingredients
def build_recipe_ingredient_lines(plan: MealPlan,recipes_by_id: Dict[int, Recipe],) -> str:
    recipe_ids = []
    seen = set()
    for day in plan.days:
        for meal in day.meals:
            if meal.recipe_id not in seen:
                seen.add(meal.recipe_id)
                recipe_ids.append(meal.recipe_id)

    lines = []
    for rid in recipe_ids:
        recipe = recipes_by_id.get(rid)
        if recipe is None:
            continue
        ingredient_text = ", ".join(recipe.ingredients) if recipe.ingredients else "none"
        lines.append(
            f"{recipe.recipe_id} | {recipe.title} | base_servings={recipe.servings or 1} | "
            f"ingredients={ingredient_text}"
        )
    return "\n".join(lines) if lines else "none"


# JSON parsing helpers
def extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    # strip markdown code fences if present
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    # try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # try to find and parse first complete { ... } block
    start = text.find('{')
    if start != -1:
        # find the matching closing brace
        depth = 0
        end = -1
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        
        # if we found a complete block, try to parse it
        if end > start:
            candidate = text[start:end]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
        
        # if incomplete, try to fix by adding missing closing brackets
        if end == -1 and depth > 0:
            candidate = text[start:] + '}' * depth
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
    
    raise ValueError(f"Could not extract JSON from LLM response:\n{text[:500]}")


def _format_decimal(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text else "0"

# Convert mixed fractions after ":" (e.g. 1 1/2) to decimals.
def _normalize_fraction_literals_in_json_like_text(text: str) -> str:
    mixed_pattern = re.compile(r'(?P<prefix>:\s*)(?P<whole>\d+)\s+(?P<num>\d+)\s*/\s*(?P<den>\d+)(?=\s*[,}\]])' )

    def _mixed_repl(match: re.Match[str]) -> str:
        whole = float(match.group("whole"))
        num = float(match.group("num"))
        den = float(match.group("den"))
        if den == 0:
            return match.group(0)
        return f'{match.group("prefix")}{_format_decimal(whole + (num / den))}'

    text = mixed_pattern.sub(_mixed_repl, text)

    # Convert simple fractions after ":" (e.g. 1/4) to decimals.
    frac_pattern = re.compile(
        r'(?P<prefix>:\s*)(?P<num>\d+)\s*/\s*(?P<den>\d+)(?=\s*[,}\]])'
    )

    def _frac_repl(match: re.Match[str]) -> str:
        num = float(match.group("num"))
        den = float(match.group("den"))
        if den == 0:
            return match.group(0)
        return f'{match.group("prefix")}{_format_decimal(num / den)}'

    return frac_pattern.sub(_frac_repl, text)


def _extract_failed_generation_text(error_text: str) -> Optional[str]:
    marker = "'failed_generation': "
    start = error_text.find(marker)
    if start == -1:
        return None
    start += len(marker)
    if start >= len(error_text) or error_text[start] != "'":
        return None
    start += 1

    escaped = False
    out = []
    for idx in range(start, len(error_text)):
        ch = error_text[idx]
        if escaped:
            out.append(ch)
            escaped = False
            continue
        if ch == "\\":
            out.append(ch)
            escaped = True
            continue
        if ch == "'":
            raw_literal = "'" + "".join(out) + "'"
            try:
                return ast.literal_eval(raw_literal)
            except Exception:
                return "".join(out)
        out.append(ch)
    return None


def _recover_json_from_failed_generation_error(err: Exception) -> Optional[str]:
    failed_generation = _extract_failed_generation_text(str(err))
    if not failed_generation:
        return None

    repaired = _normalize_fraction_literals_in_json_like_text(failed_generation)
    try:
        parsed = extract_json(repaired)
    except Exception:
        return None
    return json.dumps(parsed)

def parse_meal_plan(raw: Dict[str, Any], recipes_by_id: Dict[int, Recipe]) -> MealPlan:
    days_raw = raw.get("days", [])
    days = []
    for d in days_raw:
        day_num = int(d.get("day", len(days) + 1))
        meals = []
        for m in d.get("meals", []):
            mt = str(m.get("meal_type", "")).lower()
            if mt not in VALID_MEAL_TYPES:
                mt = "lunch"
            rid = int(m.get("recipe_id", 0))
            title = str(m.get("title", ""))
            servings = int(m.get("servings", 1))
            recipe = recipes_by_id.get(rid)
            meals.append(
                PlannedMeal(
                    day=day_num,
                    meal_type=mt,
                    recipe_id=rid,
                    title=title or (recipe.title if recipe else "Unknown"),
                    servings=servings,
                    calories=recipe.calories if recipe else None,
                    protein_g=recipe.protein_g if recipe else None,
                    carbs_g=recipe.carbs_g if recipe else None,
                    fat_g=recipe.fat_g if recipe else None,
                )
            )
        days.append(DayPlan(day=day_num, meals=meals))
    notes = raw.get("notes")
    return MealPlan(days=days, notes=notes)


def _parse_quantity(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        m = re.search(r"\d+(?:\.\d+)?", s)
        if m:
            return float(m.group())
    return None


def _parse_fractional_number(text: str) -> Optional[float]:
    s = text.strip()
    if not s:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        return float(s)
    mixed = re.fullmatch(r"(\d+)\s+(\d+)\s*/\s*(\d+)", s)
    if mixed:
        whole = float(mixed.group(1))
        num = float(mixed.group(2))
        den = float(mixed.group(3))
        if den != 0:
            return whole + (num / den)
        return None
    frac = re.fullmatch(r"(\d+)\s*/\s*(\d+)", s)
    if frac:
        num = float(frac.group(1))
        den = float(frac.group(2))
        if den != 0:
            return num / den
    return None


def _clean_grocery_name(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.replace("-", " ")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s in DROP_GROCERY_NAMES:
        return ""

    # remove leading quantity-like tokens and count words from freeform names
    s = re.sub(r"^\d+(?:\.\d+)?\s+", "", s)
    s = re.sub(r"^(?:a|an)\s+", "", s)
    tokens = [tok for tok in s.split() if tok not in DROP_GROCERY_WORDS]
    s = " ".join(tokens).strip()

    # special cleanup for common noisy compound seasonings
    s = re.sub(r"\bsalt and\b", "", s).strip()
    s = re.sub(r"\s+", " ", s).strip()
    if s.endswith("ies") and len(s) > 3:
        s = s[:-3] + "y"
    elif s.endswith("s") and not s.endswith("ss"):
        s = s[:-1]
    if s in GROCERY_BLACKLIST:
        return ""
    return s


def _extract_quantity_unit_and_name(name: str,quantity: Optional[float],unit: Optional[str]) -> tuple[str, Optional[float], Optional[str]]:
    s = name.strip()
    if not s:
        return "", quantity, unit

    if quantity is None:
        m = re.match(r"^\s*(\d+(?:\.\d+)?|\d+\s+\d+/\d+|\d+/\d+)\s+(.*)$", s)
        if m:
            parsed = _parse_fractional_number(m.group(1))
            if parsed is not None:
                quantity = parsed
                s = m.group(2).strip()

    if unit is None:
        parts = s.split()
        if parts:
            u = UNIT_ALIASES.get(parts[0].lower())
            if u is not None:
                unit = u
                s = " ".join(parts[1:]).strip()

    return _clean_grocery_name(s), quantity, _normalize_unit(unit)


def _normalize_grocery_name(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.endswith("s") and not s.endswith("ss"):
        s = s[:-1]
    return s


def _normalize_unit(unit: Optional[str]) -> Optional[str]:
    if unit is None:
        return None
    s = unit.strip().lower()
    if not s:
        return None
    return UNIT_ALIASES.get(s, s)


def _convert_quantity(quantity: float, unit: str) -> tuple[float, str, str]:
    base_unit, factor = UNIT_TO_BASE.get(unit, (unit, 1.0))
    family = UNIT_FAMILIES.get(unit, unit)
    return quantity * factor, base_unit, family


def _merge_grocery_items(items: List[GroceryItem]) -> List[GroceryItem]:
    merged = {}
    merged_order = []
    unknown = {}
    unknown_order = []
    counts_by_key = {}

    for item in items:
        key = _normalize_grocery_name(item.name)
        if not key:
            continue
        counts_by_key[key] = counts_by_key.get(key, 0) + 1

    for item in items:
        key = _normalize_grocery_name(item.name)
        if not key:
            continue
        quantity = item.quantity
        unit = _normalize_unit(item.unit)

        if quantity is None or unit is None:
            if key not in unknown:
                unknown[key] = GroceryItem(
                    name=item.name.strip(),
                    quantity=quantity,
                    unit=unit,
                    category=item.category,
                )
                unknown_order.append(key)
            continue

        if counts_by_key.get(key, 0) <= 1:
            merged_key = (key, "single")
            if merged_key not in merged:
                merged[merged_key] = GroceryItem(
                    name=item.name.strip(),
                    quantity=quantity,
                    unit=unit,
                    category=item.category,
                )
                merged_order.append(merged_key)
            continue

        quantity, base_unit, family = _convert_quantity(quantity, unit)
        merged_key = (key, family)

        if merged_key not in merged:
            merged[merged_key] = GroceryItem(
                name=item.name.strip(),
                quantity=quantity,
                unit=base_unit,
                category=item.category,
            )
            merged_order.append(merged_key)
            continue

        current = merged[merged_key]
        current.quantity = (current.quantity or 0.0) + quantity
        current.unit = base_unit
        if current.category is None and item.category is not None:
            current.category = item.category

        if key in unknown:
            unknown.pop(key, None)

    out = []
    for merged_key in merged_order:
        out.append(merged[merged_key])
    for key in unknown_order:
        if any(mk[0] == key for mk in merged_order):
            continue
        out.append(unknown[key])
    return out


def _legacy_parse_grocery_list_unused(raw: Dict[str, Any]) -> GroceryList:
    items_raw = raw.get("grocery_list", [])
    items = []
    if not isinstance(items_raw, list):
        return GroceryList(items=items)

    for item in items_raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        quantity = _parse_quantity(item.get("quantity"))
        unit_raw = item.get("unit")
        unit = str(unit_raw).strip() if unit_raw not in (None, "", "null") else None
        clean_name, quantity, unit = _extract_quantity_unit_and_name(name, quantity, unit)
        if not clean_name:
            continue
        category_raw = item.get("category")
        items.append(
            GroceryItem(
                name=clean_name,
                quantity=quantity,
                unit=unit,
                category=str(category_raw).strip() if category_raw not in (None, "", "null") else None,
            )
        )

    grocery = GroceryList(items=_merge_grocery_items(items))
    if isinstance(raw.get("grocery_text"), str):
        grocery.text = raw.get("grocery_text")
    return grocery


def build_allowed_ids_by_meal_type(candidates: List[RecipeCandidate]) -> Dict[str, List[int]]:
    max_ids_per_type = int(os.environ.get("MEALTYPE_ALLOWED_IDS_MAX", "60"))
    out = {"breakfast": [], "lunch": [], "dinner": []}
    for c in candidates:
        r = c.recipe
        if r is None:
            continue
        for mt in ("breakfast", "lunch", "dinner"):
            if is_slot_compatible(r, MealSlot(day=1, meal_type=mt)):
                out[mt].append(r.recipe_id)
    for mt in out:
        seen = set()
        deduped = []
        for rid in out[mt]:
            if rid not in seen:
                deduped.append(rid)
                seen.add(rid)
        out[mt] = deduped[:max_ids_per_type]
    return out


def enforce_meal_slot_compatibility(plan: MealPlan,candidates: List[RecipeCandidate]) -> MealPlan:
    RECIPE_COOLDOWN_DAYS = 2
    FAMILY_COOLDOWN_DAYS = 1
    allowed_ids = build_allowed_ids_by_meal_type(candidates)
    ranked_by_type = {"breakfast": [], "lunch": [], "dinner": []}

    for c in candidates:
        r = c.recipe
        if r is None:
            continue
        for mt in ("breakfast", "lunch", "dinner"):
            if r.recipe_id in allowed_ids[mt]:
                ranked_by_type[mt].append(r)

    usage_by_type = {"breakfast": {}, "lunch": {}, "dinner": {}}
    prev_day_recipe_by_type = {"breakfast": None, "lunch": None, "dinner": None}
    family_usage_by_type = {"breakfast": {}, "lunch": {}, "dinner": {}}
    prev_day_family_by_type = {"breakfast": None, "lunch": None, "dinner": None}
    last_used_day_by_recipe = {}
    last_used_day_by_family = {"breakfast": {}, "lunch": {}, "dinner": {}}

    for dp in plan.days:
        current_day = int(dp.day)
        used_today = set()
        used_families_today = set()
        for meal in dp.meals:
            mt = meal.meal_type.lower()
            if mt not in ("breakfast", "lunch", "dinner"):
                continue
            current_ok = meal.recipe_id in allowed_ids[mt]
            chosen = None

            # keep valid meal if it doesn't duplicate in the same day
            if current_ok and meal.recipe_id not in used_today:
                last_day = last_used_day_by_recipe.get(meal.recipe_id)
                candidate_recipe = next((r for r in ranked_by_type[mt] if r.recipe_id == meal.recipe_id), None)
                candidate_family = meal_family(candidate_recipe) if candidate_recipe is not None else None
                last_family_day = (
                    last_used_day_by_family[mt].get(candidate_family)
                    if candidate_family is not None else None
                )
                if (
                    (candidate_family is not None and candidate_family in used_families_today)
                    or
                    (last_day is not None and (current_day - last_day) <= RECIPE_COOLDOWN_DAYS)
                    or (last_family_day is not None and (current_day - last_family_day) <= FAMILY_COOLDOWN_DAYS)
                ):
                    current_ok = False
                else:
                    chosen = candidate_recipe

            # otherwise pick a compatible replacement with diversity preference
            if chosen is None:
                pool = ranked_by_type[mt]
                if not pool:
                    continue
                MAX_FAMILY_REPEATS = {
                    "breakfast": 3,
                    "lunch": 2,
                    "dinner": 2,
                }
                prev_id = prev_day_recipe_by_type[mt]
                usage = usage_by_type[mt]
                family_usage = family_usage_by_type[mt]

                tier1 = []
                tier2 = []
                tier3 = []

                for r in pool:
                    rid = r.recipe_id
                    fam = meal_family(r)
                    last_day = last_used_day_by_recipe.get(rid)
                    last_family_day = last_used_day_by_family[mt].get(fam)

                    # Tier 1 (strict): not same exact recipe today, not same family today, not used in last N days, not same family as yesterday, family under weekly cap
                    if rid in used_today:
                        pass
                    elif fam in used_families_today:
                        pass
                    elif last_day is not None and (current_day - last_day) <= RECIPE_COOLDOWN_DAYS:
                        pass
                    elif last_family_day is not None and (current_day - last_family_day) <= FAMILY_COOLDOWN_DAYS:
                        pass
                    elif family_usage.get(fam, 0) >= MAX_FAMILY_REPEATS.get(mt, 2):
                        pass
                    else:
                        tier1.append(r)

                    # Tier 2 (medium): allow same family as yesterday, still block exact recent recipe, still block same-family in the same day, still avoid same-day duplicate recipe, keep weekly family cap
                    if rid in used_today:
                        pass
                    elif fam in used_families_today:
                        pass
                    elif last_day is not None and (current_day - last_day) <= RECIPE_COOLDOWN_DAYS:
                        pass
                    elif family_usage.get(fam, 0) >= MAX_FAMILY_REPEATS.get(mt, 2):
                        pass
                    else:
                        tier2.append(r)

                    # Tier 3 (basic): any compatible recipe; keep only same-day duplicate block
                    if rid not in used_today:
                        tier3.append(r)

                if tier1:
                    pool = tier1
                elif tier2:
                    pool = tier2
                elif tier3:
                    pool = tier3
                else:
                    continue

                def sort_key(r: Recipe) -> tuple[int, int, int, int, str]:
                    fam = meal_family(r)
                    return (
                        1 if r.recipe_id in used_today else 0,                        
                        1 if prev_id is not None and r.recipe_id == prev_id else 0,    
                        family_usage.get(fam, 0),                                      
                        usage.get(r.recipe_id, 0),                                       
                        fam,                                                           
                    )

                chosen = min(pool, key=sort_key)

            meal.recipe_id = chosen.recipe_id
            meal.title = chosen.title
            meal.calories = chosen.calories
            meal.protein_g = chosen.protein_g
            meal.carbs_g = chosen.carbs_g
            meal.fat_g = chosen.fat_g

            used_today.add(chosen.recipe_id)
            usage_by_type[mt][chosen.recipe_id] = usage_by_type[mt].get(chosen.recipe_id, 0) + 1
            prev_day_recipe_by_type[mt] = chosen.recipe_id
            fam = meal_family(chosen)
            used_families_today.add(fam)
            family_usage_by_type[mt][fam] = family_usage_by_type[mt].get(fam, 0) + 1
            prev_day_family_by_type[mt] = fam
            last_used_day_by_recipe[chosen.recipe_id] = current_day
            last_used_day_by_family[mt][fam] = current_day
    return plan



def _default_openai_client() -> Callable[[str, str], str]:
    """Return a callable(system, user) -> response_text using Groq."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("Install openai: pip install openai")

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    base_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    model = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
    timeout_s = int(os.environ.get("GROQ_TIMEOUT_SECONDS", "120"))
    temperature = float(os.environ.get("GROQ_TEMPERATURE", "0.2"))
    max_tokens = int(os.environ.get("GROQ_MAX_TOKENS", "2200"))

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_s)

    def call(system_prompt: str, user_prompt: str) -> str:
        last_err = None
        for _ in range(2):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )
                if not resp.choices:
                    raise RuntimeError("Groq returned no choices")
                content = resp.choices[0].message.content
                if content and content.strip():
                    return content
                raise RuntimeError("Groq returned empty content")
            except Exception as e:
                recovered = _recover_json_from_failed_generation_error(e)
                if recovered is not None:
                    logger.warning(
                        "Recovered Groq failed_generation payload by normalizing fractional numbers to decimals."
                    )
                    return recovered
                last_err = e
                time.sleep(0.7)
                continue

        raise RuntimeError(f"Groq request failed after retries: {last_err}")

    return call


class MealPlanner(Planner):
    def __init__(self, llm_client: Optional[Callable[[str, str], str]] = None):
        if llm_client is not None:
            self._llm = llm_client
        else:
            self._llm = _default_openai_client()

    def _generate_raw(self,profile: UserProfile,candidates: List[RecipeCandidate],nutrition_targets: Dict[str, float]) -> tuple[Dict[str, Any], Dict[int, Recipe]]:
        recipes_by_id = {
            c.recipe.recipe_id: c.recipe
            for c in candidates
            if c.recipe is not None
        }
        base_prompt = fill_in_prompt(profile, candidates, nutrition_targets)
        parse_error = None
        response_text = ""

        for attempt in range(2):
            if attempt == 0:
                user_prompt = base_prompt
            else:
                user_prompt = (
                    base_prompt
                    + "\n\nIMPORTANT RETRY INSTRUCTION:\n"
                    + "Your previous response was invalid or truncated JSON. "
                    + "Return one complete valid JSON object only, with all 7 days. "
                    + "All numeric values must be JSON numbers (decimals allowed); never use fractions like 1/2 or 3/4."
                )

            logger.info("Calling LLM for meal plan generation (attempt %s)…", attempt + 1)
            response_text = self._llm(SYSTEM_PROMPT, user_prompt)
            logger.debug("LLM response:\n%s", response_text)

            if not response_text or not response_text.strip():
                parse_error = RuntimeError("LLM returned empty response text")
                continue

            try:
                raw = extract_json(response_text)
                return raw, recipes_by_id
            except Exception as e:
                parse_error = e
                continue

        raise RuntimeError(
            f"Failed to parse LLM response as JSON after retries. Response preview:\n{response_text[:1000]}"
        ) from parse_error

    def generate_plan(self,profile: UserProfile,candidates: List[RecipeCandidate],nutrition_targets: Dict[str, float]) -> MealPlan:
        raw, recipes_by_id = self._generate_raw(profile, candidates, nutrition_targets)
        plan = parse_meal_plan(raw, recipes_by_id)
        plan = enforce_meal_slot_compatibility(plan, candidates)
        return plan

    def generate_plan_with_grocery(self,profile: UserProfile,candidates: List[RecipeCandidate],nutrition_targets: Dict[str, float]) -> tuple[MealPlan, GroceryList]:
        raw, recipes_by_id = self._generate_raw(profile, candidates, nutrition_targets)
        plan = parse_meal_plan(raw, recipes_by_id)
        plan = enforce_meal_slot_compatibility(plan, candidates)
        grocery_gen = SimpleGroceryGenerator()
        grocery = grocery_gen.generate(plan, recipes_by_id)
        return plan, grocery




# Mock planner for testing
class MockMealPlanner(Planner):
    def generate_plan(
        self,
        profile: UserProfile,
        candidates: List[RecipeCandidate],
        nutrition_targets: Dict[str, float],
    ) -> MealPlan:
        meal_types = ["breakfast", "lunch", "dinner"]
        pool = [c for c in candidates if c.recipe is not None]
        if not pool:
            return MealPlan(days=[], notes="No candidates available")

        pool_by_type = {}
        for mt in meal_types:
            typed = [
                c for c in pool
                if c.recipe is not None and is_slot_compatible(c.recipe, MealSlot(day=1, meal_type=mt))
            ]
            # fallback to full pool if filter is too strict for this slot
            pool_by_type[mt] = typed if typed else pool

        idx_by_type = {mt: 0 for mt in meal_types}
        family_usage_by_type = {mt: {} for mt in meal_types}
        prev_family_by_type = {mt: None for mt in meal_types}
        days = []
        for d in range(1, 8):
            meals = []
            used_today = set()
            used_families_today = set()
            for mt in meal_types:
                typed_pool = pool_by_type[mt]
                if not typed_pool:
                    continue

                start = idx_by_type[mt]
                best_candidate = None
                best_key = None
                for offset in range(len(typed_pool)):
                    candidate = typed_pool[(start + offset) % len(typed_pool)]
                    r = candidate.recipe
                    if r is None:
                        continue

                    rid = r.recipe_id
                    fam = meal_family(r)

                    key = (
                        1 if rid in used_today else 0,
                        1 if fam in used_families_today else 0,
                        1 if prev_family_by_type[mt] is not None and fam == prev_family_by_type[mt] else 0,
                        family_usage_by_type[mt].get(fam, 0),
                        offset,
                    )

                    if best_key is None or key < best_key:
                        best_key = key
                        best_candidate = candidate

                c = best_candidate or typed_pool[start % len(typed_pool)]
                idx_by_type[mt] = start + 1

                r = c.recipe
                if r is None:
                    continue
                meals.append(
                    PlannedMeal(
                        day=d,
                        meal_type=mt,
                        recipe_id=r.recipe_id,
                        title=r.title,
                        servings=1,
                        calories=r.calories,
                        protein_g=r.protein_g,
                        carbs_g=r.carbs_g,
                        fat_g=r.fat_g,
                    )
                )
                used_today.add(r.recipe_id)
                fam = meal_family(r)
                used_families_today.add(fam)
                family_usage_by_type[mt][fam] = family_usage_by_type[mt].get(fam, 0) + 1
                prev_family_by_type[mt] = fam
            days.append(DayPlan(day=d, meals=meals))
        plan = MealPlan(days=days, notes="Generated by MockMealPlanner")
        return enforce_meal_slot_compatibility(plan, candidates)

    def generate_plan_with_grocery(self,profile: UserProfile,candidates: List[RecipeCandidate],nutrition_targets: Dict[str, float]) -> tuple[MealPlan, GroceryList]:
        plan = self.generate_plan(profile, candidates, nutrition_targets)
        recipes_by_id = {
            c.recipe.recipe_id: c.recipe
            for c in candidates
            if c.recipe is not None
        }
        grocery_gen = SimpleGroceryGenerator()
        grocery = grocery_gen.generate(plan, recipes_by_id)
        return plan, grocery
