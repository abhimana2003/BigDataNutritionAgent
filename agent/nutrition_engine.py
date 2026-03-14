from __future__ import annotations

from schemas import UserProfileCreate, NutritionTargets


def calculate_targets(profile: UserProfileCreate) -> NutritionTargets:
    """
    Return daily calorie and macro targets based on user profile.
    Uses a simplified Mifflin-St Jeor equation to estimate basal metabolic rate and applies an activity
    multiplier (assumes moderate activity level). Then adjusts everything based on user's goals

    Macros are set based on the goals:
    If they want high_protein -> 2.2 g protein per kg body weight, 25%% of caloriesfrom fat, remainder from carbs
    For other goals -> 1.6 g protein per kg body weight, 30%% of calories from fat, remainder from carbs
    """

    # convert units
    height_cm = (profile.height_feet * 12 + profile.height_inches) * 2.54
    weight_kg = profile.weight * 0.453592

    # basal metabolic rate
    if profile.gender.lower() == "male":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * profile.age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * profile.age - 161

    # moderate activity multiplier
    tdee = bmr * 1.55

    # goal adjustments
    if profile.goal == "weight_loss":
        daily_calories = tdee - 500
    elif profile.goal == "high_protein":
        daily_calories = tdee + 250
    else:  # maintenance
        daily_calories = tdee

    # macro calculations
    if profile.goal == "high_protein":
        protein_g = weight_kg * 2.2
        fat_g = daily_calories * 0.25 / 9
        carbs_g = (daily_calories - (protein_g * 4 + fat_g * 9)) / 4
    else:
        protein_g = weight_kg * 1.6
        fat_g = daily_calories * 0.30 / 9
        carbs_g = (daily_calories - (protein_g * 4 + fat_g * 9)) / 4

    return NutritionTargets(
        daily_calories=int(daily_calories),
        protein_g=int(protein_g),
        carbs_g=int(carbs_g),
        fat_g=int(fat_g),
    )