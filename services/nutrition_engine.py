# services/nutrition_engine.py
from __future__ import annotations
from schemas import UserProfileCreate, NutritionTargets

def calculate_targets(profile: UserProfileCreate) -> NutritionTargets:
    weight_kg = profile.weight * 0.453592
    height_cm = (profile.height_feet * 12 + profile.height_inches) * 2.54
    age = profile.age

    if str(profile.gender).lower().startswith("m"):
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    activity = 1.2
    tdee = bmr * activity

    goal = str(profile.goal)
    if "weight_loss" in goal:
        calories = tdee - 400
        protein_g = 1.6 * weight_kg
    elif "high_protein" in goal:
        calories = tdee
        protein_g = 2.0 * weight_kg
    else:
        calories = tdee
        protein_g = 1.2 * weight_kg

    fat_g = (0.30 * calories) / 9.0
    carbs_g = max(0.0, (calories - protein_g * 4.0 - fat_g * 9.0) / 4.0)

    return NutritionTargets(
        daily_calories=float(round(calories, 2)),
        protein_g=float(round(protein_g, 2)),
        carbs_g=float(round(carbs_g, 2)),
        fat_g=float(round(fat_g, 2)),
    )