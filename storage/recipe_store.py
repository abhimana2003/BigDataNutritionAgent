from sqlalchemy.orm import Session
from models import Recipe
from database import SessionLocal

class RecipeStore:
    def __init__(self):
        self.db: Session = SessionLocal()

    def get_recipe(self, recipe_id: int):
        return self.db.query(Recipe).filter(Recipe.id == recipe_id).first()

    def search_recipes(self, max_calories=None, dietary_preferences=None, allergies=None, max_prep_time=None):
        query = self.db.query(Recipe)

        if max_calories:
            query = query.filter(Recipe.nutrition["calories"].as_float() <= max_calories)

        if dietary_preferences:
            for tag in dietary_preferences:
                query = query.filter(Recipe.dietary_tags.contains([tag]))

        if allergies:
            for allergen in allergies:
                query = query.filter(~Recipe.ingredients.contains([allergen]))

        if max_prep_time:
            query = query.filter(Recipe.prep_time <= max_prep_time)

        return query.all()