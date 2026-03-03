from __future__ import annotations
from typing import List
from agent.interfaces import UserProfile, Recipe

ALLERGY_KEYWORDS = {
    "nuts": ["peanut", "almond", "cashew", "walnut", "pecan", "hazelnut", "pistachio"],
    "dairy": ["milk", "cheese", "butter", "yogurt", "cream"],
    "gluten": ["wheat", "flour", "bread", "pasta", "barley", "rye"],
    "eggs": ["egg", "eggs"],
    "soy": ["soy", "tofu", "soybean"],
}

NON_VEG_KEYWORDS = ["chicken", "beef", "pork", "turkey", "fish", "salmon", "tuna", "shrimp", "bacon"]
NON_VEGAN_KEYWORDS = NON_VEG_KEYWORDS + ["egg", "eggs", "milk", "cheese", "butter", "yogurt", "cream", "honey"]

def normalize_text_list(items: List[str]) -> str:
    return " ".join([x.lower() for x in items if x])

def recipe_violations(profile: UserProfile, recipe: Recipe) -> List[str]:
    violations: List[str] = []
    ing_text = normalize_text_list(recipe.ingredients)

    # allergies
    for allergy in profile.allergies:
        key = allergy.strip().lower()
        if key in ALLERGY_KEYWORDS:
            for kw in ALLERGY_KEYWORDS[key]:
                if kw in ing_text:
                    violations.append(f"allergy:{key}")
                    break

    # diet prefs
    prefs = [p.lower() for p in profile.dietary_preferences]
    if "vegetarian" in prefs:
        if any(kw in ing_text for kw in NON_VEG_KEYWORDS):
            violations.append("diet:vegetarian")

    if "vegan" in prefs:
        if any(kw in ing_text for kw in NON_VEGAN_KEYWORDS):
            violations.append("diet:vegan")

    return list(set(violations))

def is_allowed(profile: UserProfile, recipe: Recipe) -> bool:
    return len(recipe_violations(profile, recipe)) == 0

def filter_allowed(profile: UserProfile, recipes: List[Recipe]) -> List[Recipe]:
    return [r for r in recipes if is_allowed(profile, r)]