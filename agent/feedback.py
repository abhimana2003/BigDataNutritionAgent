from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from database import SessionLocal
from models import Recipe as RecipeORM, UserFeedback as UserFeedbackORM
from agent.interfaces import FeedbackEvent, Recipe, UserPreferences

# valid feedback actions that can be recorded and processed
VALID_ACTIONS = {"like", "dislike", "doesnt_fit"}
_MEMORY_FEEDBACK_RECIPES: Dict[int, List[Tuple[Recipe, str]]] = defaultdict(list)

# normalizes lists of text
def _norm_text_list(values: Optional[Iterable[str]]) -> List[str]:
    out: List[str] = []
    if not values:
        return out
    for value in values:
        text = str(value).strip().lower()
        if text:
            out.append(text)
    return out

# loads a recipe from the database and converts it to the agent's Recipe format
def _load_agent_recipe_from_db(recipe_id: int) -> Optional[Recipe]:
    db = SessionLocal()
    try:
        recipe = db.query(RecipeORM).filter(RecipeORM.id == recipe_id).first()
        if recipe is None:
            return None
        from agent.adapters import orm_to_agent_recipe
        return orm_to_agent_recipe(recipe)
    finally:
        db.close()

# applies user feedback to update their preferences
def _apply_feedback_to_prefs(prefs: UserPreferences, recipe: Recipe, action: str) -> None:
    delta_map = {"like": 1.0, "dislike": -1.0, "doesnt_fit": -1.5}
    delta = delta_map.get(action, -1.0)

    if action == "like":
        if recipe.recipe_id not in prefs.liked_recipes_ids:
            prefs.liked_recipes_ids.append(recipe.recipe_id)
        if recipe.recipe_id in prefs.disliked_recipes_ids:
            prefs.disliked_recipes_ids.remove(recipe.recipe_id)
        if recipe.recipe_id in prefs.doesnt_fit_recipes_ids:
            prefs.doesnt_fit_recipes_ids.remove(recipe.recipe_id)
    elif action == "dislike":
        if recipe.recipe_id not in prefs.disliked_recipes_ids:
            prefs.disliked_recipes_ids.append(recipe.recipe_id)
        if recipe.recipe_id in prefs.liked_recipes_ids:
            prefs.liked_recipes_ids.remove(recipe.recipe_id)
        if recipe.recipe_id in prefs.doesnt_fit_recipes_ids:
            prefs.doesnt_fit_recipes_ids.remove(recipe.recipe_id)
    elif action == "doesnt_fit":
        if recipe.recipe_id not in prefs.doesnt_fit_recipes_ids:
            prefs.doesnt_fit_recipes_ids.append(recipe.recipe_id)
        if recipe.recipe_id in prefs.liked_recipes_ids:
            prefs.liked_recipes_ids.remove(recipe.recipe_id)

    if recipe.cuisine:
        cuisine = recipe.cuisine.lower()
        prefs.cuisine_weights[cuisine] = prefs.cuisine_weights.get(cuisine, 0.0) + delta

    for tag in _norm_text_list(recipe.tags):
        prefs.tag_weights[tag] = prefs.tag_weights.get(tag, 0.0) + delta

    for ing in _norm_text_list(recipe.ingredients[:10]):
        prefs.ingredient_weights[ing] = prefs.ingredient_weights.get(ing, 0.0) + 0.25 * delta

# gets user preferences by looking at their feedback history 
def get_user_preferences(user_id: int) -> UserPreferences:
    prefs = UserPreferences(
        tag_weights={},
        ingredient_weights={},
        cuisine_weights={},
        liked_recipes_ids=[],
        disliked_recipes_ids=[],
        doesnt_fit_recipes_ids=[],
        disliked_ingredients=[],
    )

    user_id = int(user_id)
    db = SessionLocal()
    events = []
    try:
        events = (
            db.query(UserFeedbackORM)
            .filter(UserFeedbackORM.user_id == user_id)
            .order_by(UserFeedbackORM.created_at.asc(), UserFeedbackORM.id.asc())
            .all()
        )
    except Exception:
        events = []
    finally:
        db.close()

    recipe_cache = {}
    for event in events:
        recipe_id = int(event.recipe_id)
        if recipe_id not in recipe_cache:
            recipe_cache[recipe_id] = _load_agent_recipe_from_db(recipe_id)
        recipe = recipe_cache[recipe_id]
        if recipe is None:
            continue
        _apply_feedback_to_prefs(prefs, recipe, str(event.action).strip().lower())

    # Fallback events captured when DB writes were unavailable.
    for recipe, action in _MEMORY_FEEDBACK_RECIPES.get(user_id, []):
        _apply_feedback_to_prefs(prefs, recipe, action)

    return prefs

# records a feedback event in the database and returns a FeedbackEvent object
def record_feedback(user_id: int, recipe: Recipe, action: str) -> FeedbackEvent:
    action = str(action).strip().lower()
    if action not in VALID_ACTIONS:
        raise ValueError(f"Unsupported feedback action: {action}")
    user_id = int(user_id)

    db = SessionLocal()
    try:
        row = UserFeedbackORM(
            user_id=user_id,
            recipe_id=int(recipe.recipe_id),
            action=action,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return FeedbackEvent(user_id=user_id, recipe_id=int(recipe.recipe_id), action=action)
    except Exception:
        # Keep feedback behavior functional even when DB is unavailable.
        try:
            db.rollback()
        except Exception:
            pass
        _MEMORY_FEEDBACK_RECIPES[user_id].append((recipe, action))
        return FeedbackEvent(user_id=user_id, recipe_id=int(recipe.recipe_id), action=action)
    finally:
        db.close()
