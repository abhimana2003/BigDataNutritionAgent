from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Union
from enum import Enum
from agent.interfaces import Recipe

class GoalType(str, Enum):
    weight_loss = "weight loss"
    maintenance = "maintenance"
    high_protein = "high protein"

class MealType(str, Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    snack = "snack"

class BudgetLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class CookingTimeLevel(str, Enum):
    short = "short (<30 mins)"
    medium = "medium (30-60 min)"
    long = "long (>60 mins)"

#user profile / existing 

class UserProfileCreate(BaseModel):
    username: str
    age: int = Field(gt=0, lt=120)
    height_feet: int = Field(ge=1, le=8)
    height_inches: int = Field(ge=0, le=11)
    weight: float = Field(ge=40.0, le=1000.0)
    gender: str

    goal: GoalType
    dietary_preferences: List[str] = []
    allergies: List[str] = []
    medical_conditions: List[str] = []

    budget_level: Optional[float]
    cooking_time: CookingTimeLevel

# nutrition layer outputs 

class NutritionTargets(BaseModel):
    daily_calories: float
    protein_g: float
    carbs_g: float
    fat_g: float

    sodium_mg: Optional[float] = None
    sugar_g: Optional[float] = None
    fiber_g: Optional[float] = None

class NutritionRanges(BaseModel):
    calories_min: Optional[float]
    calories_max: Optional[float]
    protein_min: Optional[float]
    protein_max: Optional[float]
    carbs_min: Optional[float]
    carbs_max: Optional[float]
    fat_min: Optional[float]
    fat_max: Optional[float]

# recommender layer 

class MealSlot(BaseModel):
    day: int = Field(ge=1, le=7)
    meal_type: MealType

class RecipeCandidate(BaseModel):
    recipe_id: int
    score: float
    reasons: List[str] = []

    similarity_score: Optional[float] = None
    nutrition_fit_score: Optional[float] = None
    time_fit_score: Optional[float] = None
    budget_fit_score: Optional[float] = None
    recipe: Optional[Recipe] = None

class RecommendationRequest(BaseModel):
    username: str
    slot: MealSlot
    k: int = 10

class RecommendationResponse(BaseModel):
    candidates: List[RecipeCandidate]

# planner layer outputs 
class PlannedMeal(BaseModel):
    day: int = Field(ge=1, le=7)
    meal_type: MealType
    recipe_id: int
    title: Optional[str]
    servings: Optional[int]
    meal_nutrition: Optional[NutritionTargets]

class DayPlan(BaseModel):
    day: int
    meals: List[PlannedMeal] = []
    daily_totals: Optional[NutritionTargets]

class MealPlanResponse(BaseModel):
    #profile_id: int
    username: str
    days: List[DayPlan] = []
    weekly_totals: Optional[NutritionTargets]
    grocery_list: Optional[List["GroceryItem"]]
    grocery_text: Optional[str] = None
    notes: Optional[str]

# grocery list objects 

class GroceryItem(BaseModel):
    name: str
    quantity: Optional[float]
    unit: Optional[str]
    category: Optional[str]

class GroceryList(BaseModel):
    items: List[GroceryItem] = []
    # optional pretty text (e.g. bullet list) that can be shown directly to users
    text: Optional[str] = None

# feedback / preference 

class FeedbackEvent(BaseModel):
    username: str
    recipe_id: int
    action: str  # "like" | "dislike"
    timestamp: Optional[str] = None

class FeedbackRequest(BaseModel):
    username: str
    recipe_id: int
    action: str

class FeedbackResponse(BaseModel):
    ok: bool
    updated_preferences: Optional[Dict[str, Union[Dict[str, float], List[float]]]]

class UserPreferenceState(BaseModel):
    preferred_tags: Optional[Dict[str, float]]
    disliked_ingredients: Optional[Dict[str, float]]
    preference_vector: Optional[List[float]]

# forward refs (grocery list inside meal plan)
MealPlanResponse.update_forward_refs()

class UserProfile(BaseModel):
    id: int
    username: str
    age: int
    height_feet: int
    height_inches: int
    weight: float
    gender: str

    goal: GoalType
    dietary_preferences: List[str] = []
    allergies: List[str] = []
    medical_conditions: List[str] = []

    budget_level: Optional[float]
    cooking_time: CookingTimeLevel

    class Config:
        from_attributes = True  # for SQLAlchemy -> Pydantic