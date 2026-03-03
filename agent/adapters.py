from __future__ import annotations
from agent.interfaces import Recipe as AgentRecipe

def orm_to_agent_recipe(r) -> AgentRecipe:
    return AgentRecipe(
        recipe_id=int(r.id),
        title=r.recipe_name,
        ingredients=r.ingredients or [],
        tags=r.dietary_tags or [],
        cuisine=r.cuisine_path,
        prep_minutes=r.prep_time,
        cook_minutes=r.cook_time,
        total_minutes=r.total_time,
        servings=r.servings,
        calories=(r.nutrition or {}).get("calories") if isinstance(r.nutrition, dict) else None,
        protein_g=(r.nutrition or {}).get("protein") if isinstance(r.nutrition, dict) else None,
        carbs_g=(r.nutrition or {}).get("carbs") if isinstance(r.nutrition, dict) else None,
        fat_g=(r.nutrition or {}).get("fat") if isinstance(r.nutrition, dict) else None,
        estimated_cost=r.estimated_cost,
        url=r.url,
    )