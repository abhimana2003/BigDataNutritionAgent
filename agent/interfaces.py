# This file defines all the Pydantic models and other interfaces for the different parts of the agent
from __future__ import annotations
from typing import Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field
from abc import ABC, abstractmethod

MealType = Literal["breakfast", "lunch", "dinner", "snack"]
FeedbackAction = Literal["like", "dislike", "doesnt_fit"]


# User Profile
class UserProfile(BaseModel):
    id: Optional[int] = None
    username: str = "user"
    age: int = Field(gt=0, lt=120)
    height_feet: int = Field(ge=1, le=8)
    height_inches: int = Field(ge=0, le=11)
    weight_lbs: float = Field(ge=40.0, le=1000.0)
    gender: str

    goal: str
    dietary_preferences: List[str] = []
    allergies: List[str] = []
    medical_conditions: List[str] = []
    budget_level: str
    cooking_time: str

    # Used for learned personalization
    cuisine_preferences: List[str] = []
    disliked_ingredients: List[str] = []


# Meal slot = day of the week + meal type
class MealSlot(BaseModel):
    day: int = Field(ge=1)
    meal_type: MealType

# Recipe Model
class Recipe(BaseModel):
    recipe_id: int
    title: str
    ingredients: List[str] = []
    tags: List[str] = []
    cuisine: Optional[str] = None
    category: Optional[str] = None
    prep_minutes: Optional[int] = None
    cook_minutes: Optional[int] = None
    total_minutes: Optional[int] = None
    servings: Optional[int] = None

    # Nutrition
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    sodium_mg: Optional[float] = None
    sugar_g: Optional[float] = None
    fiber_g: Optional[float] = None
    saturated_fat_g: Optional[float] = None
    cholesterol_mg: Optional[float] = None
    estimated_cost: Optional[float] = None
    
    url: Optional[str] = None


# Output object of the recommender 
class RecipeCandidate(BaseModel):
    recipe_id: int
    score: float
    reasons: List[str] = []
    recipe: Optional[Recipe] = None


# Feedback Model
class FeedbackEvent(BaseModel):
    user_id: int
    recipe_id: int
    action: FeedbackAction

# User preferences which we use for personalization
class UserPreferences(BaseModel):
    tag_weights: Dict[str, float] = {}
    ingredient_weights: Dict[str, float] = {}
    cuisine_weights: Dict[str, float] = {}

    liked_recipes_ids: List[int] = []
    disliked_recipes_ids: List[int] = []
    doesnt_fit_recipes_ids: List[int] = []
    disliked_ingredients: List[str] = []


# Meal Planner Layer Models

# A single meal assignment inside a weekly plan
class PlannedMeal(BaseModel):
    day: int = Field(ge=1, le=7)
    meal_type: MealType
    recipe_id: int
    title: str
    servings: int = 1
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None

# All meals for one day
class DayPlan(BaseModel):
    day: int = Field(ge=1, le=7)
    meals: List[PlannedMeal] = []

# Entire 7-day meal plan
class MealPlan(BaseModel):
    days: List[DayPlan] = []
    notes: Optional[str] = None

# A single grocery list entry
class GroceryItem(BaseModel):
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    category: Optional[str] = None

# Aggregated grocery list from a meal plan
class GroceryList(BaseModel):
    items: List[GroceryItem] = []
    # optional human-readable text produced by LLM
    text: Optional[str] = None


# Function Contracts
def recommend(id: int, profile: UserProfile, slot: MealSlot, k: int = 10,) -> List[RecipeCandidate]:
    """
    Return top-k recommended recipes for this user & meal slot.
    Implemented in agent/recommender.py
    """
    raise NotImplementedError


def record_feedback(event: FeedbackEvent) -> None:
    """
    Store like/dislike feedback and update preferences.
    Implemented in agent/feedback.py
    """
    raise NotImplementedError



# ABCs
class Retriever(ABC):
    """
    Retrieves candidate recipes for a user + slot
    """
    @abstractmethod
    def retrieve(
        self,
        profile: UserProfile,
        slot: MealSlot,
        k: int = 10,
    ) -> List[RecipeCandidate]:
        ...


class Scorer(ABC):
    """
    Scores / re-ranks a list of recipe candidates
    """
    @abstractmethod
    def score(
        self,
        profile: UserProfile,
        candidates: List[RecipeCandidate],
        slot: MealSlot,
    ) -> List[RecipeCandidate]:
        ...


class Planner(ABC):
    """
    Generates a 7-day meal plan from ranked recipes
    """
    @abstractmethod
    def generate_plan(
        self,
        profile: UserProfile,
        candidates: List[RecipeCandidate],
        nutrition_targets: Dict,
    ) -> MealPlan:
        ...


class GroceryGenerator(ABC):
    """
    Produces a consolidated grocery list from a meal plan
    """
    @abstractmethod
    def generate(
        self,
        meal_plan: MealPlan,
        recipes_by_id: Dict[int, Recipe],
    ) -> GroceryList:
        ...