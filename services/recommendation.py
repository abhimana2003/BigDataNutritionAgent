from __future__ import annotations

from typing import List, Optional
from sqlalchemy.orm import Session

from schemas import UserProfileCreate, MealSlot, RecipeCandidate, RecommendationResponse, NutritionTargets
from models import Recipe as RecipeORM  
from services.embedding_retrieval import EmbeddingIndex
from agent.constraints import filter_allowed  
from agent.scoring import score_recipe       
from agent.feedback import get_user_preferences

from agent.adapters import orm_to_agent_recipe  


_embedding_index = EmbeddingIndex()


def recommend_for_profile(
    db: Session,
    profile: UserProfileCreate,
    slot: MealSlot,
    username: str | None = None,
    targets: Optional[NutritionTargets] = None,
    k: int = 10,
    top_n: int = 200,
    user_id: int | None = None,
) -> RecommendationResponse:
    """
    ML retrieval (embeddings) + reranking (rules + prefs).
    """
    effective_username = username or getattr(profile, "username", None)
    if effective_username is None and user_id is not None:
        effective_username = str(user_id)

    recipes_orm = db.query(RecipeORM).all()

    retrieved = _embedding_index.search(recipes_orm, profile, slot=slot, top_n=top_n)  # (orm_recipe, sim)

    agent_recipes = [(orm_to_agent_recipe(r), sim) for (r, sim) in retrieved]

    filtered_pairs = []
    for ar, sim in agent_recipes:
        filtered_pairs.append((ar, sim))
    allowed_only = filter_allowed(profile_to_agent_profile(profile, effective_username or "user"), [r for r, _ in filtered_pairs])
    allowed_set = {r.recipe_id for r in allowed_only}
    filtered_pairs = [(r, sim) for (r, sim) in filtered_pairs if r.recipe_id in allowed_set]

    prefs_user_id = user_id if user_id is not None else effective_username
    prefs = get_user_preferences(prefs_user_id)

    candidates = []
    for r, sim in filtered_pairs:
        s, reasons = score_recipe(profile_to_agent_profile(profile, effective_username or "user"), r, prefs=prefs, slot=slot)

        final_score = 0.6 * sim + 0.4 * s

        candidates.append(
            RecipeCandidate(
                recipe_id=r.recipe_id,
                score=float(final_score),
                reasons=reasons,
                similarity_score=float(sim),
                nutrition_fit_score=None,
                time_fit_score=None,
                budget_fit_score=None,
            )
        )

    candidates.sort(key=lambda x: x.score, reverse=True)
    return RecommendationResponse(candidates=candidates[:k])


def profile_to_agent_profile(profile: UserProfileCreate, username: str):
    from agent.interfaces import UserProfile as AgentProfile
    return AgentProfile(
        username=str(username),
        age=profile.age,
        height_feet=profile.height_feet,
        height_inches=profile.height_inches,
        weight_lbs=profile.weight,
        gender=profile.gender,
        goal=str(profile.goal),
        dietary_preferences=profile.dietary_preferences,
        allergies=profile.allergies,
        medical_conditions=profile.medical_conditions,
        budget_level=str(profile.budget_level),
        cooking_time=str(profile.cooking_time),
        cuisine_preferences=[],
        disliked_ingredients=[],
    )
