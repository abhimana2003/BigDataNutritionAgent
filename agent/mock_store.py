from __future__ import annotations

from typing import Dict, List

from agent.interfaces import FeedbackEvent, Recipe, UserPreferences


USER_PREFS: Dict[int, UserPreferences] = {}
USER_FEEDBACK: Dict[int, List[FeedbackEvent]] = {}


def get_user_preferences(user_id: int) -> UserPreferences:
    if user_id not in USER_PREFS:
        USER_PREFS[user_id] = UserPreferences()
    return USER_PREFS[user_id]


def record_feedback(user_id: int, recipe: Recipe, action: str) -> None:
    """
    Store a like/dislike event and update user preferences weights.
    """
    event = FeedbackEvent(user_id=user_id, recipe_id=recipe.recipe_id, action=action)
    USER_FEEDBACK.setdefault(user_id, []).append(event)

    prefs = get_user_preferences(user_id)
    update_preferences(prefs, recipe, action)


def update_preferences(prefs: UserPreferences, recipe: Recipe, action: str) -> None:
    delta = 1.0 if action == "like" else -1.0

    # cuisine preference
    if recipe.cuisine:
        c = recipe.cuisine.lower()
        prefs.cuisine_weights[c] = prefs.cuisine_weights.get(c, 0.0) + delta

    # tag preference
    for t in recipe.tags:
        key = t.lower()
        prefs.tag_weights[key] = prefs.tag_weights.get(key, 0.0) + delta

    # ingredient preference (small weight to avoid noise)
    for ing in recipe.ingredients[:10]:
        key = ing.lower()
        prefs.ingredient_weights[key] = prefs.ingredient_weights.get(key, 0.0) + 0.25 * delta