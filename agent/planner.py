# meal plan generator module
from __future__ import annotations
import json
import logging
import os
import re
import time
from typing import Any, Callable, Dict, List, Optional
from agent.interfaces import DayPlan, GroceryItem, GroceryList, MealPlan, MealSlot, Planner, PlannedMeal,Recipe, RecipeCandidate,UserProfile
from agent.grocery import SimpleGroceryGenerator
from agent.scoring import is_slot_compatible

logger = logging.getLogger(__name__)

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
2. Merge duplicates (same ingredient) into one item with summed quantity when possible.
3. Keep ingredient names generic and normalized (e.g., "onion", not "small onion, diced").
4. Exclude trivial pantry/household items such as water, salt, pepper, ice, etc.
5. Use null for unknown unit/quantity.

Respond ONLY with the JSON object.
"""


# converts recipe candidates into text rows to include in the prompt
def build_recipe_table(candidates: List[RecipeCandidate]) -> str:
    """Return two sections:
    1. a summary table (id, title, macros, cost, minutes)
    2. a simple ingredient list section that the LLM can use to build the
       grocery list.  Ingredients are separated by commas and prefixed with the
       recipe id.
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
    # start from first { and build up, counting braces
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

VALID_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}


def parse_meal_plan(raw: Dict[str, Any], recipes_by_id: Dict[int, Recipe]) -> MealPlan:
    days_raw = raw.get("days", [])
    days: List[DayPlan] = []
    for d in days_raw:
        day_num = int(d.get("day", len(days) + 1))
        meals: List[PlannedMeal] = []
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


def parse_grocery_list(raw: Dict[str, Any]) -> GroceryList:
    items_raw = raw.get("grocery_list", [])
    items: List[GroceryItem] = []
    if not isinstance(items_raw, list):
        return GroceryList(items=items)

    for item in items_raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        unit_raw = item.get("unit")
        category_raw = item.get("category")
        items.append(
            GroceryItem(
                name=name,
                quantity=_parse_quantity(item.get("quantity")),
                unit=str(unit_raw).strip() if unit_raw not in (None, "", "null") else None,
                category=str(category_raw).strip() if category_raw not in (None, "", "null") else None,
            )
        )

    grocery = GroceryList(items=items)
    if isinstance(raw.get("grocery_text"), str):
        grocery.text = raw.get("grocery_text")
    return grocery


def build_allowed_ids_by_meal_type(candidates: List[RecipeCandidate]) -> Dict[str, List[int]]:
    max_ids_per_type = int(os.environ.get("MEALTYPE_ALLOWED_IDS_MAX", "60"))
    out: Dict[str, List[int]] = {"breakfast": [], "lunch": [], "dinner": []}
    for c in candidates:
        r = c.recipe
        if r is None:
            continue
        for mt in ("breakfast", "lunch", "dinner"):
            if is_slot_compatible(r, MealSlot(day=1, meal_type=mt)):
                out[mt].append(r.recipe_id)
    for mt in out:
        seen = set()
        deduped: List[int] = []
        for rid in out[mt]:
            if rid not in seen:
                deduped.append(rid)
                seen.add(rid)
        out[mt] = deduped[:max_ids_per_type]
    return out


def enforce_meal_slot_compatibility(
    plan: MealPlan,
    candidates: List[RecipeCandidate],
) -> MealPlan:
    allowed_ids = build_allowed_ids_by_meal_type(candidates)
    ranked_by_type: Dict[str, List[Recipe]] = {"breakfast": [], "lunch": [], "dinner": []}

    for c in candidates:
        r = c.recipe
        if r is None:
            continue
        for mt in ("breakfast", "lunch", "dinner"):
            if r.recipe_id in allowed_ids[mt]:
                ranked_by_type[mt].append(r)

    usage_by_type: Dict[str, Dict[int, int]] = {"breakfast": {}, "lunch": {}, "dinner": {}}
    prev_day_recipe_by_type: Dict[str, Optional[int]] = {"breakfast": None, "lunch": None, "dinner": None}

    for dp in plan.days:
        used_today: set[int] = set()
        for meal in dp.meals:
            mt = meal.meal_type.lower()
            if mt not in ("breakfast", "lunch", "dinner"):
                continue
            current_ok = meal.recipe_id in allowed_ids[mt]
            chosen: Optional[Recipe] = None

            # keep valid meal if it doesn't duplicate in the same day
            if current_ok and meal.recipe_id not in used_today:
                chosen = next((r for r in ranked_by_type[mt] if r.recipe_id == meal.recipe_id), None)

            # otherwise pick a compatible replacement with diversity preference
            if chosen is None:
                pool = ranked_by_type[mt]
                if not pool:
                    continue
                prev_id = prev_day_recipe_by_type[mt]
                usage = usage_by_type[mt]

                def sort_key(r: Recipe) -> tuple[int, int, int]:
                    return (
                        1 if r.recipe_id in used_today else 0,                # avoid same-day duplicates first
                        1 if prev_id is not None and r.recipe_id == prev_id else 0,  # avoid repeating previous day
                        usage.get(r.recipe_id, 0),                             # prefer less-used recipes
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
    return plan


# ---------------------------------------------------------------------------
# LLM client wrapper
# ---------------------------------------------------------------------------

def _default_openai_client() -> Callable[[str, str], str]:
    """Return a callable(system, user) -> response_text using Ollama locally."""
    try:
        import requests
    except ImportError:
        raise ImportError("Install requests: pip install requests")
    # allow configuration via env vars for flexibility
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
    model = os.environ.get("OLLAMA_MODEL", "neural-chat")
    timeout_s = int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "300"))
    num_predict = int(os.environ.get("OLLAMA_NUM_PREDICT", "2200"))
    temperature = float(os.environ.get("OLLAMA_TEMPERATURE", "0.2"))

    def _extract_text(result: Any) -> Optional[str]:
        if not isinstance(result, dict):
            return None

        # Explicit API-side error from Ollama
        if isinstance(result.get("error"), str) and result["error"].strip():
            raise RuntimeError(f"Ollama error: {result['error']}")

        # Common Ollama keys
        response = result.get("response")
        if isinstance(response, str) and response.strip():
            return response

        text = result.get("text")
        if isinstance(text, str) and text.strip():
            return text

        message = result.get("message")
        if isinstance(message, dict):
            content = message.get("content") or message.get("text")
            if isinstance(content, str) and content.strip():
                return content

        choices = result.get("choices") or result.get("generations")
        if choices and isinstance(choices, list) and len(choices) > 0:
            first = choices[0]
            if isinstance(first, dict):
                choice_text = first.get("text")
                if isinstance(choice_text, str) and choice_text.strip():
                    return choice_text
                choice_msg = first.get("message")
                if isinstance(choice_msg, dict):
                    msg = choice_msg.get("content") or choice_msg.get("text")
                    if isinstance(msg, str) and msg.strip():
                        return msg

        return None

    def call(system_prompt: str, user_prompt: str) -> str:
        # prefer the structured messages API, but also send a combined prompt as fallback
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        payloads = [
            {
                "model": model,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {"num_predict": num_predict, "temperature": temperature},
            },
            {
                "model": model,
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "stream": False,
                "format": "json",
                "options": {"num_predict": num_predict, "temperature": temperature},
            },
        ]

        last_err: Optional[Exception] = None
        last_result_preview: Optional[str] = None
        for payload in payloads:
            for attempt in range(2):
                try:
                    resp = requests.post(ollama_url, json=payload, timeout=timeout_s)
                    resp.raise_for_status()
                    result = resp.json()
                    text = _extract_text(result)
                    done_reason = result.get("done_reason") if isinstance(result, dict) else None
                    if text is not None:
                        return text
                    # some Ollama versions return an initial "load" result with empty text
                    if done_reason == "load" and attempt == 0:
                        time.sleep(1.0)
                        continue
                    # keep preview for diagnostic error if all payloads fail
                    if isinstance(result, dict):
                        last_result_preview = f"keys={list(result.keys())}, done_reason={done_reason}"
                    else:
                        last_result_preview = str(result)[:300]
                    break

                except requests.exceptions.RequestException as e:
                    last_err = e
                    # retry same payload once for transient timeout, then try next payload
                    if attempt == 0:
                        time.sleep(1.0)
                        continue
                    break

        raise RuntimeError(
            f"Ollama request failed (tried messages and prompt payloads). "
            f"Last error: {last_err}. Last response preview: {last_result_preview}. "
            f"Ensure Ollama is running and accessible at {ollama_url}"
        )

    return call


# ---------------------------------------------------------------------------
# MealPlanner class
# ---------------------------------------------------------------------------

class MealPlanner(Planner):
    """
    LLM-powered meal planner.

    Parameters
    ----------
    llm_client : callable(system_prompt, user_prompt) -> str
        Any function that accepts two strings and returns the LLM response text.
        If *None*, a default OpenAI client is created from env vars.
    """

    def __init__(self, llm_client: Optional[Callable[[str, str], str]] = None):
        if llm_client is not None:
            self._llm = llm_client
        else:
            self._llm = _default_openai_client()

    def _generate_raw(
        self,
        profile: UserProfile,
        candidates: List[RecipeCandidate],
        nutrition_targets: Dict[str, float],
    ) -> tuple[Dict[str, Any], Dict[int, Recipe]]:
        recipes_by_id = {
            c.recipe.recipe_id: c.recipe
            for c in candidates
            if c.recipe is not None
        }
        base_prompt = fill_in_prompt(profile, candidates, nutrition_targets)
        parse_error: Optional[Exception] = None
        response_text = ""

        for attempt in range(2):
            if attempt == 0:
                user_prompt = base_prompt
            else:
                user_prompt = (
                    base_prompt
                    + "\n\nIMPORTANT RETRY INSTRUCTION:\n"
                    + "Your previous response was invalid or truncated JSON. "
                    + "Return one complete valid JSON object only, with all 7 days and grocery_list."
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

    # --- public API ----------------------------------------------------------

    def generate_plan(
        self,
        profile: UserProfile,
        candidates: List[RecipeCandidate],
        nutrition_targets: Dict[str, float],
    ) -> MealPlan:
        raw, recipes_by_id = self._generate_raw(profile, candidates, nutrition_targets)
        plan = parse_meal_plan(raw, recipes_by_id)
        plan = enforce_meal_slot_compatibility(plan, candidates)
        return plan

    def generate_plan_with_grocery(
        self,
        profile: UserProfile,
        candidates: List[RecipeCandidate],
        nutrition_targets: Dict[str, float],
    ) -> tuple[MealPlan, GroceryList]:
        raw, recipes_by_id = self._generate_raw(profile, candidates, nutrition_targets)
        plan = parse_meal_plan(raw, recipes_by_id)
        plan = enforce_meal_slot_compatibility(plan, candidates)
        grocery = parse_grocery_list(raw)
        if not grocery.items:
            # fallback keeps endpoint resilient if the model omits grocery_list
            grocery_gen = SimpleGroceryGenerator()
            grocery = grocery_gen.generate(plan, recipes_by_id)
        return plan, grocery


# ---------------------------------------------------------------------------
# Mock planner (no LLM needed)
# ---------------------------------------------------------------------------

class MockMealPlanner(Planner):
    """
    Deterministic planner for tests and offline dev.
    Round-robins through candidates to fill a 7-day plan.
    """

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

        pool_by_type: Dict[str, List[RecipeCandidate]] = {}
        for mt in meal_types:
            typed = [
                c for c in pool
                if c.recipe is not None and is_slot_compatible(c.recipe, MealSlot(day=1, meal_type=mt))
            ]
            # fallback to full pool if filter is too strict for this slot
            pool_by_type[mt] = typed if typed else pool

        idx_by_type = {mt: 0 for mt in meal_types}
        days: List[DayPlan] = []
        for d in range(1, 8):
            meals: List[PlannedMeal] = []
            used_today: set[int] = set()
            for mt in meal_types:
                typed_pool = pool_by_type[mt]
                if not typed_pool:
                    continue

                # pick first not-yet-used-today recipe, otherwise cycle
                start = idx_by_type[mt]
                c = typed_pool[start % len(typed_pool)]
                for offset in range(len(typed_pool)):
                    candidate = typed_pool[(start + offset) % len(typed_pool)]
                    rid = candidate.recipe.recipe_id if candidate.recipe else None
                    if rid is not None and rid not in used_today:
                        c = candidate
                        idx_by_type[mt] = start + offset + 1
                        break
                else:
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
            days.append(DayPlan(day=d, meals=meals))
        plan = MealPlan(days=days, notes="Generated by MockMealPlanner")
        return enforce_meal_slot_compatibility(plan, candidates)

    def generate_plan_with_grocery(
        self,
        profile: UserProfile,
        candidates: List[RecipeCandidate],
        nutrition_targets: Dict[str, float],
    ) -> tuple[MealPlan, GroceryList]:
        plan = self.generate_plan(profile, candidates, nutrition_targets)
        recipes_by_id = {
            c.recipe.recipe_id: c.recipe
            for c in candidates
            if c.recipe is not None
        }
        grocery_gen = SimpleGroceryGenerator()
        grocery = grocery_gen.generate(plan, recipes_by_id)
        return plan, grocery
