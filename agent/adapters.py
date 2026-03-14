from __future__ import annotations
from agent.interfaces import Recipe as AgentRecipe

# takes a recipe row from the SQLAlchemy ORM model and converts it into a Recipe class from interfaces
def orm_to_agent_recipe(r) -> AgentRecipe:
    nutrition = r.nutrition if isinstance(r.nutrition, dict) else {}
    return AgentRecipe(
        recipe_id=int(r.id),
        title=r.recipe_name,
        ingredients=r.ingredients or [],
        tags=r.dietary_tags or [],
        cuisine=r.cuisine_path,
        category=getattr(r, "category", None),
        prep_minutes=r.prep_time,
        cook_minutes=r.cook_time,
        total_minutes=r.total_time,
        servings=r.servings,
        calories=nutrition.get("calories"),
        protein_g=nutrition.get("protein"),
        carbs_g=nutrition.get("carbs"),
        fat_g=nutrition.get("fat"),
        sodium_mg=nutrition.get("sodium_mg"),
        sugar_g=nutrition.get("sugar_g"),
        fiber_g=nutrition.get("fiber_g"),
        saturated_fat_g=nutrition.get("saturated_fat_g"),
        cholesterol_mg=nutrition.get("cholesterol_mg"),
        estimated_cost=r.estimated_cost,
        url=r.url,
    )
