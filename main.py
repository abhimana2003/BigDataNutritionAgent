from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
import crud, schemas
import models
from functools import lru_cache
import re
import copy
from typing import Optional
from datetime import date, timedelta

app = FastAPI(title="Nutrition AI User Profiling API")


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _next_week_start(d: date) -> date:
    return _week_start(d) + timedelta(days=7)


def _to_agent_profile(db_profile: models.UserProfile):
    from agent.interfaces import UserProfile as AgentProfile

    return AgentProfile(
        id=db_profile.id,
        username=db_profile.username,
        age=db_profile.age,
        height_feet=db_profile.height_feet,
        height_inches=db_profile.height_inches,
        weight_lbs=db_profile.weight,
        gender=db_profile.gender,
        goal=str(db_profile.goal),
        dietary_preferences=db_profile.dietary_preferences or [],
        allergies=db_profile.allergies or [],
        medical_conditions=db_profile.medical_conditions or [],
        budget_level=str(db_profile.budget_level),
        cooking_time=str(db_profile.cooking_time),
        cuisine_preferences=[],
        disliked_ingredients=[],
    )


def _nutrition_from_agent_recipe(recipe):
    if recipe is None:
        return None
    if recipe.calories is None and recipe.protein_g is None and recipe.carbs_g is None and recipe.fat_g is None:
        return None
    return schemas.NutritionTargets(
        daily_calories=recipe.calories or 0,
        protein_g=recipe.protein_g or 0,
        carbs_g=recipe.carbs_g or 0,
        fat_g=recipe.fat_g or 0,
    )


def _normalize_ingredients(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, dict):
        for key in ("ingredients", "items"):
            if key in value:
                return _normalize_ingredients(value[key])
        return []
    text = str(value).strip()
    if not text:
        return []
    text = text.strip("[]")
    parts = [p.strip(" '\"") for p in text.split(",")]
    return [p for p in parts if p]


def _normalize_directions(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, dict):
        for key in ("directions", "steps", "instructions"):
            if key in value:
                return _normalize_directions(value[key])
        return []
    text = str(value).strip()
    if not text:
        return []
    lines = [line.strip() for line in re.split(r"\r?\n+", text) if line.strip()]
    if len(lines) > 1:
        return lines
    sentence_steps = [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text) if s.strip()]
    return sentence_steps if sentence_steps else [text]


def _normalize_image_url(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower().startswith(("http://", "https://")):
        return text
    return None


@lru_cache(maxsize=1)
def _csv_recipe_lookup() -> dict:
    try:
        import pandas as pd
    except ImportError:
        return {}

    from pathlib import Path
    paths = [Path("data/raw/recipes.csv"), Path("data/raw/archive/recipes.csv")]
    csv_path = next((p for p in paths if p.exists()), None)
    if csv_path is None:
        return {}

    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return {}

    out = {}
    for _, row in df.iterrows():
        name = str(row.get("recipe_name", "")).strip().lower()
        if not name or name in out:
            continue
        out[name] = {
            "ingredients": _normalize_ingredients(row.get("ingredients")),
            "directions": _normalize_directions(row.get("directions")),
            "image_url": _normalize_image_url(
                row.get("img_src") or row.get("image_url") or row.get("image")
            ),
        }
    return out


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/profiles", response_model=list[schemas.UserProfile])
def list_profiles(db: Session = Depends(get_db)):
    return crud.get_user_profiles(db)


@app.put("/profiles/{username}", response_model=schemas.UserProfile)
def upsert_profile(username: str, profile: schemas.UserProfileCreate, db: Session = Depends(get_db)):
    if username != profile.username:
        raise HTTPException(status_code=400, detail="Username mismatch")
    return crud.upsert_user_profile(db, username, profile)


@app.get("/profiles/{username}", response_model=schemas.UserProfile)
def get_profile(username: str, db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/profiles", response_model=schemas.UserProfile)
def create_profile(profile: schemas.UserProfileCreate, db: Session = Depends(get_db)):
    existing = crud.get_user_by_username(db, profile.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    return crud.upsert_user_profile(db, profile.username, profile)


@app.post("/auth/login", response_model=schemas.LoginResponse)
def login(req: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = crud.authenticate_user(db, req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return schemas.LoginResponse(ok=True, username=user.username, full_name=user.full_name)


@app.post("/profiles/{username}/feedback", response_model=schemas.FeedbackResponse)
def submit_feedback(username: str, req: schemas.FeedbackRequest, db: Session = Depends(get_db)):
    if username != req.username:
        raise HTTPException(status_code=400, detail="Username mismatch")

    user = crud.get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    recipe = db.query(models.Recipe).filter(models.Recipe.id == req.recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    action = (req.action or "").strip().lower()
    if action not in ("like", "dislike", "doesnt_fit"):
        raise HTTPException(status_code=400, detail="Action must be 'like', 'dislike', or 'doesnt_fit'")

    from agent.adapters import orm_to_agent_recipe
    from agent.feedback import record_feedback, get_user_preferences

    agent_recipe = orm_to_agent_recipe(recipe)
    record_feedback(user.id, agent_recipe, action)
    prefs = get_user_preferences(user.id)

    print(f"Feedback: user={username}, recipe={recipe.id}, action={action}")

    return schemas.FeedbackResponse(
        ok=True,
        updated_preferences={
            "preferred_tags": prefs.tag_weights,
            "preferred_cuisines": prefs.cuisine_weights,
            "preferred_ingredients": prefs.ingredient_weights,
        },
    )


@app.post("/profiles/{username}/replace-meal", response_model=schemas.ReplaceMealResponse)
def replace_meal(username: str, req: schemas.ReplaceMealRequest, db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from agent.interfaces import MealSlot
    from agent.recommender import recommend
    from agent.feedback import get_user_preferences

    slot = MealSlot(day=req.day, meal_type=req.meal_type.value)
    profile = _to_agent_profile(user)
    import random
    candidates = recommend(user_id=user.id, profile=profile, slot=slot, k=200)
    prefs = get_user_preferences(user.id)

    excluded = set(req.exclude_recipe_ids or [])
    excluded.add(req.current_recipe_id)
    excluded.update(getattr(prefs, "disliked_recipes_ids", []))
    excluded.update(getattr(prefs, "doesnt_fit_recipes_ids", []))

    random.shuffle(candidates)
    for cand in candidates:
        recipe = cand.recipe
        if recipe is None:
            continue
        if recipe.recipe_id in excluded:
            continue
        meal = schemas.PlannedMeal(
            day=req.day,
            meal_type=req.meal_type,
            recipe_id=recipe.recipe_id,
            title=recipe.title,
            servings=recipe.servings or 1,
            meal_nutrition=_nutrition_from_agent_recipe(recipe),
        )
        current_week_start = _week_start(date.today())
        target_week_start = req.week_start or current_week_start
        history = crud.get_mealplan_history_for_week(db, username, target_week_start)
        if history is None:
            history = crud.get_latest_mealplan_history(db, username)
        if history and history.meal_plan:
            plan = copy.deepcopy(history.meal_plan)
            days = plan.get("days", [])
            for day in days:
                if int(day.get("day", 0)) != req.day:
                    continue
                meals = day.get("meals", [])
                for m in meals:
                    raw_type = str(m.get("meal_type", "")).lower()
                    if raw_type.startswith("mealtype."):
                        raw_type = raw_type.split("mealtype.", 1)[-1]
                    if raw_type == req.meal_type.value:
                        m.update(meal.model_dump(mode="json"))
                        break
                break
            recipe_ids = sorted(
                {
                    int(m.get("recipe_id"))
                    for d in days
                    for m in d.get("meals", [])
                    if m.get("recipe_id") is not None
                }
            )
            target_week_start = history.week_start if history is not None else current_week_start
            crud.upsert_mealplan_history(
                db=db,
                username=username,
                week_start=target_week_start,
                recipe_ids=recipe_ids,
                meal_plan=plan,
            )
        return schemas.ReplaceMealResponse(ok=True, meal=meal)

    raise HTTPException(status_code=404, detail="No suitable replacement found")


@app.post("/profiles/{username}/grocerylist", response_model=schemas.GroceryList)
def regenerate_grocery_list(
    username: str,
    req: schemas.GroceryListRequest,
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from agent.interfaces import MealPlan, DayPlan, PlannedMeal
    from agent.adapters import orm_to_agent_recipe
    from agent.grocery import SimpleGroceryGenerator
    from models import Recipe as RecipeORM

    days_in = req.days or []
    plan_days = []
    recipe_ids = set()
    for day in days_in:
        meals_out = []
        for meal in day.meals:
            rid = int(meal.recipe_id)
            recipe_ids.add(rid)
            meal_type_value = meal.meal_type.value if hasattr(meal.meal_type, "value") else str(meal.meal_type)
            meals_out.append(
                PlannedMeal(
                    day=int(meal.day),
                    meal_type=str(meal_type_value),
                    recipe_id=rid,
                    title=meal.title or "",
                    servings=meal.servings or 1,
                )
            )
        plan_days.append(DayPlan(day=int(day.day), meals=meals_out))

    plan = MealPlan(days=plan_days)
    if not recipe_ids:
        return schemas.GroceryList(items=[], text=None)

    orm_recipes = db.query(RecipeORM).filter(RecipeORM.id.in_(list(recipe_ids))).all()
    recipes_by_id = {int(r.id): orm_to_agent_recipe(r) for r in orm_recipes}

    grocery_gen = SimpleGroceryGenerator()
    grocery = grocery_gen.generate(plan, recipes_by_id)

    return schemas.GroceryList(
        items=[
            schemas.GroceryItem(
                name=item.name,
                quantity=item.quantity,
                unit=item.unit,
                category=item.category,
            )
            for item in grocery.items
        ],
        text=getattr(grocery, "text", None),
    )


@app.post("/profiles/{username}/mealplan/save", response_model=schemas.MealPlanResponse)
def save_mealplan(
    username: str,
    req: schemas.MealPlanSaveRequest,
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    plan = req.meal_plan or {}
    week_start_val = plan.get("week_start")
    if isinstance(week_start_val, str):
        try:
            week_start = date.fromisoformat(week_start_val)
        except ValueError:
            week_start = _week_start(date.today())
    elif isinstance(week_start_val, date):
        week_start = week_start_val
    else:
        week_start = _week_start(date.today())

    days = plan.get("days", [])
    recipe_ids = sorted(
        {
            int(m.get("recipe_id"))
            for d in days
            for m in d.get("meals", [])
            if m.get("recipe_id") is not None
        }
    )

    try:
        from agent.interfaces import MealPlan, DayPlan, PlannedMeal
        from agent.adapters import orm_to_agent_recipe
        from agent.grocery import SimpleGroceryGenerator
        from models import Recipe as RecipeORM

        plan_days = []
        for day in days:
            meals_out = []
            for meal in day.get("meals", []):
                meals_out.append(
                    PlannedMeal(
                        day=int(meal.get("day", 0)),
                        meal_type=str(meal.get("meal_type", "")),
                        recipe_id=int(meal.get("recipe_id")),
                        title=meal.get("title", "") or "",
                        servings=meal.get("servings") or 1,
                    )
                )
            plan_days.append(DayPlan(day=int(day.get("day", 0)), meals=meals_out))

        plan_obj = MealPlan(days=plan_days)
        orm_recipes = db.query(RecipeORM).filter(RecipeORM.id.in_(recipe_ids)).all()
        recipes_by_id = {int(r.id): orm_to_agent_recipe(r) for r in orm_recipes}
        grocery = SimpleGroceryGenerator().generate(plan_obj, recipes_by_id)

        plan = dict(plan)
        plan["grocery_list"] = [
            {
                "name": item.name,
                "quantity": item.quantity,
                "unit": item.unit,
                "category": item.category,
            }
            for item in grocery.items
        ]
        plan["grocery_text"] = getattr(grocery, "text", None)
    except Exception:
        pass

    crud.upsert_mealplan_history(
        db=db,
        username=username,
        week_start=week_start,
        recipe_ids=recipe_ids,
        meal_plan=plan,
    )

    return plan


@app.get("/recipes/{recipe_id}", response_model=schemas.RecipeDetailResponse)
def get_recipe_detail(recipe_id: int, db: Session = Depends(get_db)):
    recipe = db.query(models.Recipe).filter(models.Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    ingredients = _normalize_ingredients(recipe.ingredients)
    directions = _normalize_directions(recipe.directions)
    image_url = None

    if (not ingredients or not directions) and recipe.recipe_name:
        fallback = _csv_recipe_lookup().get(recipe.recipe_name.strip().lower())
        if fallback:
            if not ingredients:
                ingredients = fallback.get("ingredients", [])
            if not directions:
                directions = fallback.get("directions", [])
            image_url = fallback.get("image_url")

    if image_url is None and recipe.recipe_name:
        fallback = _csv_recipe_lookup().get(recipe.recipe_name.strip().lower())
        if fallback:
            image_url = fallback.get("image_url")

    return schemas.RecipeDetailResponse(
        recipe_id=recipe.id,
        title=recipe.recipe_name,
        ingredients=ingredients,
        directions=directions,
        image_url=image_url,
        prep_time=recipe.prep_time,
        cook_time=recipe.cook_time,
        total_time=recipe.total_time,
        servings=recipe.servings,
        calories=(recipe.nutrition or {}).get("calories") if isinstance(recipe.nutrition, dict) else None,
        protein_g=(recipe.nutrition or {}).get("protein") if isinstance(recipe.nutrition, dict) else None,
        carbs_g=(recipe.nutrition or {}).get("carbs") if isinstance(recipe.nutrition, dict) else None,
        fat_g=(recipe.nutrition or {}).get("fat") if isinstance(recipe.nutrition, dict) else None,
        url=recipe.url,
    )


@app.get("/profiles/{username}/mealplan", response_model=schemas.MealPlanResponse)
def generate_mealplan(
    username: str,
    next_week: bool = False,
    force: bool = False,
    db: Session = Depends(get_db),
):
    db_profile = crud.get_user_by_username(db, username)
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile_create = schemas.UserProfileCreate(
        username=db_profile.username,
        email=db_profile.email,
        full_name=db_profile.full_name,
        password=None,
        age=db_profile.age,
        height_feet=db_profile.height_feet,
        height_inches=db_profile.height_inches,
        weight=db_profile.weight,
        gender=db_profile.gender,
        goal=db_profile.goal,
        dietary_preferences=db_profile.dietary_preferences or [],
        allergies=db_profile.allergies or [],
        medical_conditions=db_profile.medical_conditions or [],
        budget_level=db_profile.budget_level,
        cooking_time=db_profile.cooking_time,
    )

    from agent.nutrition_engine import calculate_targets
    targets = calculate_targets(profile_create)
    nutrition_targets = {
        "daily_calories": targets.daily_calories,
        "protein_g": targets.protein_g,
        "carbs_g": targets.carbs_g,
        "fat_g": targets.fat_g,
    }

    def _targets_match(cached_plan: dict, current_targets: dict) -> bool:
        cached_targets = cached_plan.get("nutrition_targets") or {}
        for key in ("daily_calories", "protein_g", "carbs_g", "fat_g"):
            if key not in cached_targets:
                return False
            try:
                cached_val = float(cached_targets.get(key) or 0)
                current_val = float(current_targets.get(key) or 0)
            except (TypeError, ValueError):
                return False
            if abs(cached_val - current_val) > 1e-3:
                return False
        return True

    def _normalize_cached_plan(cached_plan: dict, week_start: date) -> dict:
        plan = dict(cached_plan)
        plan["week_start"] = week_start
        return plan

    from agent.interfaces import MealSlot
    from agent.retrieval import RecommenderRetriever

    agent_profile = _to_agent_profile(db_profile)

    today = date.today()
    current_week_start = _week_start(today)
    latest_history = crud.get_latest_mealplan_history(db, username)

    if next_week:
        if latest_history and latest_history.week_start:
            target_week_start = latest_history.week_start + timedelta(days=7)
        else:
            target_week_start = _next_week_start(today)
    else:
        target_week_start = current_week_start

    cached_history = crud.get_mealplan_history_for_week(db, username, target_week_start)

    if not force and not next_week:
        latest = crud.get_latest_mealplan_history(db, username)
        if latest and latest.meal_plan:
            cached_plan = latest.meal_plan
            if isinstance(cached_plan, dict) and _targets_match(cached_plan, nutrition_targets):
                return _normalize_cached_plan(cached_plan, latest.week_start)

    if not force and cached_history and cached_history.meal_plan:
        cached_plan = cached_history.meal_plan
        if isinstance(cached_plan, dict) and _targets_match(cached_plan, nutrition_targets):
            return _normalize_cached_plan(cached_plan, target_week_start)

    exclude_recipe_ids = set()
    if next_week:
        prev_week_start = target_week_start - timedelta(days=7)
        prev_plan = crud.get_mealplan_history_for_week(db, username, prev_week_start)
        if prev_plan and prev_plan.recipe_ids:
            exclude_recipe_ids = {
                int(rid) for rid in prev_plan.recipe_ids
                if rid is not None
            }

    retriever = RecommenderRetriever()
    all_candidates = []
    for meal_type in ["breakfast", "lunch", "dinner"]:
        slot = MealSlot(day=1, meal_type=meal_type)
        cands = retriever.retrieve(agent_profile, slot, k=15)
        all_candidates.extend(cands)

    seen_ids = set()
    unique_candidates = []
    for c in all_candidates:
        if c.recipe_id not in seen_ids:
            seen_ids.add(c.recipe_id)
            unique_candidates.append(c)

    if exclude_recipe_ids:
        filtered_candidates = [
            c for c in unique_candidates
            if c.recipe_id not in exclude_recipe_ids
        ]
        if filtered_candidates:
            unique_candidates = filtered_candidates

    import os
    import logging

    use_mock = os.getenv("USE_MOCK_PLANNER", "false").lower() in ("1", "true", "yes")
    logger = logging.getLogger(__name__)

    try:
        if use_mock:
            from agent.planner import MockMealPlanner
            planner = MockMealPlanner()
        else:
            from agent.planner import MealPlanner
            planner = MealPlanner()

        plan, grocery = planner.generate_plan_with_grocery(
            profile=agent_profile,
            candidates=unique_candidates,
            nutrition_targets=nutrition_targets,
        )
    except Exception as e:
        logger.exception("LLM planner failed, falling back to MockMealPlanner: %s", e)
        from agent.planner import MockMealPlanner
        planner = MockMealPlanner()
        plan, grocery = planner.generate_plan_with_grocery(
            profile=agent_profile,
            candidates=unique_candidates,
            nutrition_targets=nutrition_targets,
        )
        if plan.notes:
            plan.notes = f"[FALLBACK] {plan.notes} — original error: {str(e)[:300]}"
        else:
            plan.notes = f"[FALLBACK] original LLM planner error: {str(e)[:300]}"

    days_out = []
    for dp in plan.days:
        meals_out = []
        for m in dp.meals:
            meals_out.append(
                schemas.PlannedMeal(
                    day=m.day,
                    meal_type=m.meal_type,
                    recipe_id=m.recipe_id,
                    title=m.title,
                    servings=m.servings,
                    meal_nutrition=schemas.NutritionTargets(
                        daily_calories=m.calories or 0,
                        protein_g=m.protein_g or 0,
                        carbs_g=m.carbs_g or 0,
                        fat_g=m.fat_g or 0,
                    ) if m.calories is not None else None,
                )
            )
        day_cals = sum(m.calories or 0 for m in dp.meals)
        day_prot = sum(m.protein_g or 0 for m in dp.meals)
        day_carb = sum(m.carbs_g or 0 for m in dp.meals)
        day_fat = sum(m.fat_g or 0 for m in dp.meals)
        days_out.append(
            schemas.DayPlan(
                day=dp.day,
                meals=meals_out,
                daily_totals=schemas.NutritionTargets(
                    daily_calories=day_cals,
                    protein_g=day_prot,
                    carbs_g=day_carb,
                    fat_g=day_fat,
                ),
            )
        )

    total_cals = sum(d.daily_totals.daily_calories for d in days_out if d.daily_totals)
    total_prot = sum(d.daily_totals.protein_g for d in days_out if d.daily_totals)
    total_carb = sum(d.daily_totals.carbs_g for d in days_out if d.daily_totals)
    total_fat = sum(d.daily_totals.fat_g for d in days_out if d.daily_totals)

    grocery_out = [
        schemas.GroceryItem(
            name=item.name,
            quantity=item.quantity,
            unit=item.unit,
            category=item.category,
        )
        for item in grocery.items
    ]
    grocery_text = getattr(grocery, "text", None)

    recipe_ids = sorted(
        {
            int(m.recipe_id)
            for d in plan.days
            for m in d.meals
            if m.recipe_id is not None
        }
    )

    response = schemas.MealPlanResponse(
        username=username,
        week_start=target_week_start,
        days=days_out,
        nutrition_targets=schemas.NutritionTargets(
            daily_calories=nutrition_targets.get("daily_calories", 0),
            protein_g=nutrition_targets.get("protein_g", 0),
            carbs_g=nutrition_targets.get("carbs_g", 0),
            fat_g=nutrition_targets.get("fat_g", 0),
        ),
        weekly_totals=schemas.NutritionTargets(
            daily_calories=total_cals,
            protein_g=total_prot,
            carbs_g=total_carb,
            fat_g=total_fat,
        ),
        grocery_list=grocery_out,
        grocery_text=grocery_text,
        notes=plan.notes,
    )

    crud.upsert_mealplan_history(
        db=db,
        username=username,
        week_start=target_week_start,
        recipe_ids=recipe_ids,
        meal_plan=response.model_dump(mode="json"),
    )

    return response
