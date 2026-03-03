from __future__ import annotations
import logging
from typing import List

from agent.constraints import filter_allowed
from agent.interfaces import MealSlot, RecipeCandidate, UserProfile
from agent.scoring import is_slot_compatible, score_recipe
from agent.mock_store import get_user_preferences  # you’ll implement in step 3
from agent.adapters import orm_to_agent_recipe
from database import SessionLocal
from models import Recipe as RecipeORM


logger = logging.getLogger(__name__)


def _load_recipes_from_db() -> List:
    db = SessionLocal()
    try:
        orm_recipes = db.query(RecipeORM).all()
        return [orm_to_agent_recipe(r) for r in orm_recipes]
    finally:
        db.close()


def recommend(user_id: int, profile: UserProfile, slot: MealSlot, k: int = 10) -> List[RecipeCandidate]:
    recipes = []
    try:
        recipes = _load_recipes_from_db()
    except Exception as e:
        logger.warning("DB recipe load failed; returning no candidates: %s", e)
        return []

    if not recipes:
        logger.warning("Recipe DB is empty; returning no candidates")
        return []

    allowed = filter_allowed(profile, recipes)
    slot_compatible = [r for r in allowed if is_slot_compatible(r, slot)]
    if slot_compatible:
        allowed = slot_compatible

    prefs = get_user_preferences(user_id)  # can return empty prefs if new user

    candidates: List[RecipeCandidate] = []
    for r in allowed:
        s, reasons = score_recipe(profile, r, prefs=prefs, slot=slot)
        candidates.append(RecipeCandidate(recipe_id=r.recipe_id, score=s, reasons=reasons, recipe=r))

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:k]
