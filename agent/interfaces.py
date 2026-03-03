from __future__ import annotations

from typing import Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field



# Controlled string types
MealType = Literal["breakfast", "lunch", "dinner", "snack"]
FeedbackAction = Literal["like", "dislike"]



# User Profile
class UserProfile(BaseModel):
    """
    Agent-facing user profile.
    This is what the recommender consumes.
    """

    user_id: Optional[int] = None

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


# Meal Slot
class MealSlot(BaseModel):
    """
    Represents a day + meal type combination.
    """
    day: int = Field(ge=1)
    meal_type: MealType



# Recipe (Normalized Agent Model)
class Recipe(BaseModel):
    """
    Normalized recipe representation used internally by the agent.
    All external datasets must be mapped into this shape.
    """

    recipe_id: int
    title: str

    ingredients: List[str] = []
    tags: List[str] = []
    cuisine: Optional[str] = None

    prep_minutes: Optional[int] = None
    cook_minutes: Optional[int] = None
    total_minutes: Optional[int] = None
    servings: Optional[int] = None

    # Nutrition
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None

    estimated_cost: Optional[float] = None
    url: Optional[str] = None


# Recommendation Output
class RecipeCandidate(BaseModel):
    """
    Output object returned by recommend().
    """
    recipe_id: int
    score: float
    reasons: List[str] = []
    recipe: Optional[Recipe] = None



# Feedback + Learning
class FeedbackEvent(BaseModel):
    user_id: int
    recipe_id: int
    action: FeedbackAction


class UserPreferences(BaseModel):
    """
    Learned per-user weights from feedback.
    """
    tag_weights: Dict[str, float] = {}
    ingredient_weights: Dict[str, float] = {}
    cuisine_weights: Dict[str, float] = {}


# Function Contracts
def recommend(
    user_id: int,
    profile: UserProfile,
    slot: MealSlot,
    k: int = 10,
) -> List[RecipeCandidate]:
    """
    Return top-k recommended recipes for this user & meal slot.
    Implemented in agent/recommender.py
    """
    raise NotImplementedError


def record_feedback(event: FeedbackEvent) -> None:
    """
    Store like/dislike feedback and update preferences.
    Implemented in agent/mock_store.py
    """
    raise NotImplementedError



# Planner Layer Models
class PlannedMeal(BaseModel):
    """A single meal assignment inside a weekly plan."""
    day: int = Field(ge=1, le=7)
    meal_type: MealType
    recipe_id: int
    title: str
    servings: int = 1
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None


class DayPlan(BaseModel):
    """All meals for one day."""
    day: int = Field(ge=1, le=7)
    meals: List[PlannedMeal] = []


class MealPlan(BaseModel):
    """Complete 7-day meal plan."""
    days: List[DayPlan] = []
    notes: Optional[str] = None


class GroceryItem(BaseModel):
    """A single grocery list entry."""
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    category: Optional[str] = None


class GroceryList(BaseModel):
    """Aggregated grocery list from a meal plan."""
    items: List[GroceryItem] = []
    # optional human-readable text produced by an LLM or other postprocessor
    text: Optional[str] = None



# Abstract Interfaces (ABCs)
from abc import ABC, abstractmethod


class Retriever(ABC):
    """Retrieves candidate recipes for a user + slot."""

    @abstractmethod
    def retrieve(
        self,
        profile: UserProfile,
        slot: MealSlot,
        k: int = 10,
    ) -> List[RecipeCandidate]:
        ...


class Scorer(ABC):
    """Scores / re-ranks a list of recipe candidates."""

    @abstractmethod
    def score(
        self,
        profile: UserProfile,
        candidates: List[RecipeCandidate],
        slot: MealSlot,
    ) -> List[RecipeCandidate]:
        ...


class Planner(ABC):
    """Generates a 7-day meal plan from ranked recipes."""

    @abstractmethod
    def generate_plan(
        self,
        profile: UserProfile,
        candidates: List[RecipeCandidate],
        nutrition_targets: Dict,
    ) -> MealPlan:
        ...


class GroceryGenerator(ABC):
    """Produces a consolidated grocery list from a meal plan."""

    @abstractmethod
    def generate(
        self,
        meal_plan: MealPlan,
        recipes_by_id: Dict[int, Recipe],
    ) -> GroceryList:
        ...