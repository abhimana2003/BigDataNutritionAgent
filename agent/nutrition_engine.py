from __future__ import annotations
from schemas import UserProfileCreate, NutritionTargets
from services.nutrition_engine import calculate_targets as _calculate_targets

def calculate_targets(profile: UserProfileCreate) -> NutritionTargets:
    return _calculate_targets(profile)