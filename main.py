from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
import crud, schemas
import models
from functools import lru_cache
import re
from typing import Optional

app = FastAPI(title="Nutrition AI User Profiling API")


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
def create_profile(profile: schemas.UserProfileCreate, db: Session=Depends(get_db)):
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
    if action not in ("like", "dislike"):
        raise HTTPException(status_code=400, detail="Action must be 'like' or 'dislike'")

    from agent.adapters import orm_to_agent_recipe
    from agent.mock_store import record_feedback, get_user_preferences

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

    slot = MealSlot(day=req.day, meal_type=req.meal_type.value)
    profile = _to_agent_profile(user)
    candidates = recommend(user_id=user.id, profile=profile, slot=slot, k=80)

    excluded = set(req.exclude_recipe_ids or [])
    excluded.add(req.current_recipe_id)

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
        return schemas.ReplaceMealResponse(ok=True, meal=meal)

    raise HTTPException(status_code=404, detail="No suitable replacement found")


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
        url=recipe.url,
    )


#@app.put("/profiles/{username}", response_model=schemas.UserProfile)
#def update_profile(username: str, profile: schemas.UserProfileCreate, db: Session=Depends(get_db)):
 #   db_profile = crud.update_user_profile_by_username(db, username, profile)
 #   if db_profile is None:
 #       raise HTTPException(status_code=404, detail="User not found")
 #   return db_profile


#@app.get("/profiles/{profile_id}", response_model=schemas.UserProfile)
#def get_profile(profile_id: int, db: Session = Depends(get_db)):
#    db_profile = crud.get_user_profile(db, profile_id)
#    if db_profile is None:
#        raise HTTPException(status_code=404, detail="Profile not found")
#    return db_profile

#@app.put("/profiles/{profile_id}", response_model=schemas.UserProfile)
#def update_profile(profile_id: int, profile: schemas.UserProfileCreate, db: Session = Depends(get_db)):
#    db_profile = crud.update_user_profile(db, profile_id, profile)
#    if db_profile is None:
#        raise HTTPException(status_code=404, detail="Profile not found")
#    return db_profile

#@app.put("/profiles/{username}", response_model=schemas.UserProfile)
#def update_profile(username: str, profile: schemas.UserProfileCreate, db: Session = Depends(get_db)):
#    db_profile = crud.update_user_profile_by_username(db, username, profile)
#    if db_profile is None:
#        raise HTTPException(status_code=404, detail="User not found")
#    return db_profile


@app.get("/profiles/{username}/mealplan", response_model=schemas.MealPlanResponse)
def generate_mealplan(username: str, db: Session = Depends(get_db)):
    db_profile = crud.get_user_by_username(db, username)
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile_create = schemas.UserProfileCreate(
        username = db_profile.username,
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

    # calculate nutrition targets using the agent implementation directly
    from agent.nutrition_engine import calculate_targets
    targets = calculate_targets(profile_create)
    nutrition_targets = {
        "daily_calories": targets.daily_calories,
        "protein_g": targets.protein_g,
        "carbs_g": targets.carbs_g,
        "fat_g": targets.fat_g,
    }

    from agent.interfaces import MealSlot
    agent_profile = _to_agent_profile(db_profile)

    from agent.retrieval import RecommenderRetriever
    retriever = RecommenderRetriever()
    all_candidates = []
    for meal_type in ["breakfast", "lunch", "dinner"]:
        slot = MealSlot(day=1, meal_type=meal_type)
        cands = retriever.retrieve(agent_profile, slot, k=50)
        all_candidates.extend(cands)

    seen_ids = set()
    unique_candidates = []
    for c in all_candidates:
        if c.recipe_id not in seen_ids:
            seen_ids.add(c.recipe_id)
            unique_candidates.append(c)

    import os
    use_mock = os.getenv("USE_MOCK_PLANNER", "false").lower() in ("1", "true", "yes")

    if use_mock:
        from agent.planner import MockMealPlanner
        planner = MockMealPlanner()
    else:
        from agent.planner import MealPlanner
        planner = MealPlanner()

    import logging
    logger = logging.getLogger(__name__)

    try:
        plan, grocery = planner.generate_plan_with_grocery(
            profile=agent_profile,
            candidates=unique_candidates,
            nutrition_targets=nutrition_targets,
        )
    except Exception as e:
        # If the LLM-based planner failed, fall back to the mock planner so the endpoint remains functional
        logger.exception("LLM planner failed, falling back to MockMealPlanner: %s", e)
        from agent.planner import MockMealPlanner
        planner = MockMealPlanner()
        plan, grocery = planner.generate_plan_with_grocery(
            profile=agent_profile,
            candidates=unique_candidates,
            nutrition_targets=nutrition_targets,
        )
        # annotate the plan notes so callers know we used a fallback
        if plan.notes:
            plan.notes = f"[FALLBACK] {plan.notes} — original error: {str(e)[:300]}"
        else:
            plan.notes = f"[FALLBACK] original LLM planner error: {str(e)[:300]}"


    days_out = []
    for dp in plan.days:
        meals_out = []
        for m in dp.meals:
            meals_out.append(schemas.PlannedMeal(
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
            ))
        day_cals = sum(m.calories or 0 for m in dp.meals)
        day_prot = sum(m.protein_g or 0 for m in dp.meals)
        day_carb = sum(m.carbs_g or 0 for m in dp.meals)
        day_fat = sum(m.fat_g or 0 for m in dp.meals)
        days_out.append(schemas.DayPlan(
            day=dp.day,
            meals=meals_out,
            daily_totals=schemas.NutritionTargets(
                daily_calories=day_cals,
                protein_g=day_prot,
                carbs_g=day_carb,
                fat_g=day_fat,
            ),
        ))

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

    return schemas.MealPlanResponse(
        #profile_id=profile_id,
        username=username,
        days=days_out,
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
