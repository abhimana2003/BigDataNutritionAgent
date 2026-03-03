from __future__ import annotations
from schemas import FeedbackEvent

_USER_PREFS = {}

def record_feedback(event: FeedbackEvent) -> None:
    state = _USER_PREFS.setdefault(event.user_id, {"likes": set(), "dislikes": set()})
    if event.action == "like":
        state["likes"].add(event.recipe_id)
        state["dislikes"].discard(event.recipe_id)
    elif event.action == "dislike":
        state["dislikes"].add(event.recipe_id)
        state["likes"].discard(event.recipe_id)