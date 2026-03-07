from __future__ import annotations

from collections import defaultdict
from typing import Dict, Set
from schemas import FeedbackEvent
from database import SessionLocal
from models import Recipe as RecipeORM


_USER_PREFS: Dict[int, Dict] = {}


def _get_state(user_id: int) -> Dict:
    return _USER_PREFS.setdefault(
        user_id,
        {
            "likes": set(),
            "dislikes": set(),
            "ingredient_scores": defaultdict(int),
        },
    )


def _get_recipe_ingredients(recipe_id: int):
    db = SessionLocal()
    try:
        recipe = db.query(RecipeORM).filter(RecipeORM.recipe_id == recipe_id).first()
        if recipe and recipe.ingredients:
            return recipe.ingredients
        return []
    finally:
        db.close()


def record_feedback(event: FeedbackEvent) -> None:
    state = _get_state(event.user_id)

    ingredients = _get_recipe_ingredients(event.recipe_id)

    if event.action == "like":

        state["likes"].add(event.recipe_id)
        state["dislikes"].discard(event.recipe_id)

        for ing in ingredients:
            state["ingredient_scores"][ing] += 1

    elif event.action == "dislike":

        state["dislikes"].add(event.recipe_id)
        state["likes"].discard(event.recipe_id)

        for ing in ingredients:
            state["ingredient_scores"][ing] -= 1


def get_user_preferences(user_id: int) -> Dict:
    state = _get_state(user_id)

    return {
        "liked_recipe_ids": state["likes"],
        "disliked_recipe_ids": state["dislikes"],
        "ingredient_scores": dict(state["ingredient_scores"]),
    }