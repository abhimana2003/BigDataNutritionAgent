from sqlalchemy.orm import Session
from models import Recipe, UserProfile

class RecipeStore:
    def __init__(self, db: Session):
        self.db = db

    def get_user_profile(self, username: str):
        return self.db.query(UserProfile).filter_by(username=username).first()

  
    def filter_recipes_for_user(self, username: str):
        user = self.get_user_profile(username)
        if not user:
            raise ValueError("User not found")
        
        

        query = self.db.query(Recipe).filter(Recipe.username == username)

        if user.goal == "weight_loss":
            query = query.filter(Recipe.nutrition["calories"].as_float() <= 500)

        if user.dietary_preferences:
            for tag in user.dietary_preferences:
                query = query.filter(Recipe.dietary_tags.contains([tag]))

        if user.allergies:
            for allergen in user.allergies:
                query = query.filter(~Recipe.ingredients.contains([allergen]))

        if user.cooking_time:
            query = query.filter(Recipe.prep_time <= user.cooking_time)

        return query.all()

    def assign_recipes_to_user(self, username: str):
        filtered_recipes = self.filter_recipes_for_user(username)

        for recipe in filtered_recipes:
            recipe.username = username

        self.db.commit()

    def get_user_recipes(self, username: str):
        return self.db.query(Recipe).filter_by(username=username).all()