from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
import crud, schemas

app = FastAPI(title="Nutrition AI User Profiling API")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/profiles", response_model=schemas.UserProfile)
def create_profile(profile: schemas.UserProfileCreate, db: Session = Depends(get_db)):
    return crud.create_user_profile(db, profile)

@app.get("/profiles", response_model=list[schemas.UserProfile])
def list_profiles(db: Session = Depends(get_db)):
    return crud.get_user_profiles(db)

@app.get("/profiles/{profile_id}", response_model=schemas.UserProfile)
def get_profile(profile_id: int, db: Session = Depends(get_db)):
    db_profile = crud.get_user_profile(db, profile_id)
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return db_profile

@app.put("/profiles/{profile_id}", response_model=schemas.UserProfile)
def update_profile(profile_id: int, profile: schemas.UserProfileCreate, db: Session = Depends(get_db)):
    db_profile = crud.update_user_profile(db, profile_id, profile)
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return db_profile


@app.get("/profiles/{profile_id}/mealplan", response_model=schemas.MealPlanResponse)
def generate_mealplan(profile_id: int, db: Session = Depends(get_db)):
    db_profile = crud.get_user_profile(db, profile_id)
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile_create = schemas.UserProfileCreate(
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

    from agent.interfaces import UserProfile as AgentProfile, MealSlot
    agent_profile = AgentProfile(
        user_id=profile_id,
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
        profile_id=profile_id,
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
