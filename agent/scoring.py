from __future__ import annotations
from typing import List, Optional, Tuple
from agent.interfaces import MealSlot, Recipe, UserPreferences, UserProfile

# optional classifier so we can fall back to a learned model if rules aren't sufficient
try:
    from agent.meal_type_classifier import predict_meal_type
except Exception:
    predict_meal_type = lambda r: "lunchdinner"  # no classifier available

BREAKFAST_INCLUDE = [
    "breakfast", "oat", "omelette", "pancake", "waffle", "toast",
    "parfait", "smoothie", "yogurt", "granola", "cereal", "muffin",
]
BREAKFAST_EXCLUDE = [
    "steak", "burger", "curry", "biryani", "stir-fry", "stir fry", "pasta",
    "taco", "meatball", "bbq", "sandwich", "wrap", "salmon",
    "fish",
]
LUNCH_DINNER_EXCLUDE = [
    "smoothie", "parfait", "oatmeal", "overnight oats", "cereal",
]


def _recipe_text(recipe: Recipe) -> str:
    title = recipe.title or ""
    ingredients = " ".join(recipe.ingredients or [])
    tags = " ".join(recipe.tags or [])
    return f"{title} {ingredients} {tags}".lower()


def _slot_to_expected_labels(slot: MealSlot) -> set[str]:
    if slot.meal_type == "breakfast":
        return {"breakfast"}
    if slot.meal_type in {"lunch", "dinner"}:
        return {"lunchdinner", "main_meal"}
    if slot.meal_type == "snack":
        return {"snack", "dessert"}
    return set()


def _category_match(recipe: Recipe, slot: MealSlot) -> Optional[bool]:
    if not recipe.category:
        return None
    return recipe.category.lower() in _slot_to_expected_labels(slot)


def _classifier_match(recipe: Recipe, slot: MealSlot) -> Optional[bool]:
    try:
        pred = str(predict_meal_type(recipe) or "").strip().lower()
    except Exception:
        return None
    if not pred:
        return None
    return pred in _slot_to_expected_labels(slot)


def _text_analysis_match(recipe: Recipe, slot: MealSlot) -> bool:
    text = _recipe_text(recipe)
    breakfast_hits = sum(1 for k in BREAKFAST_INCLUDE if k in text)
    breakfast_conflict = any(k in text for k in BREAKFAST_EXCLUDE)
    lunch_dinner_conflict = any(k in text for k in LUNCH_DINNER_EXCLUDE)

    if slot.meal_type == "breakfast":
        return breakfast_hits > 0 and not breakfast_conflict
    if slot.meal_type in {"lunch", "dinner"}:
        return not (breakfast_hits > 0 and not breakfast_conflict) and not lunch_dinner_conflict
    if slot.meal_type == "snack":
        snack_terms = ("snack", "bar", "cookie", "brownie", "muffin", "granola", "smoothie")
        return any(k in text for k in snack_terms)
    return False


def is_slot_compatible(recipe: Recipe, slot: MealSlot) -> bool:
    category_signal = _category_match(recipe, slot)
    if category_signal is not None:
        return category_signal

    classifier_signal = _classifier_match(recipe, slot)
    text_signal = _text_analysis_match(recipe, slot)
    return bool(classifier_signal is True or text_signal)


def meal_type_score(recipe: Recipe, slot: Optional[MealSlot]) -> Tuple[float, List[str]]:
    if slot is None:
        return 0.0, []
    if is_slot_compatible(recipe, slot):
        return 1.0, [f"fits {slot.meal_type}"]
    return -4.0, [f"weak fit for {slot.meal_type}"]


def estimate_calories(recipe: Recipe) -> Optional[float]:
    if recipe.calories is not None:
        return recipe.calories
    if recipe.protein_g is None or recipe.carbs_g is None or recipe.fat_g is None:
        return None
    return 4 * recipe.protein_g + 4 * recipe.carbs_g + 9 * recipe.fat_g


def score_recipe(profile: UserProfile, recipe: Recipe, prefs: Optional[UserPreferences] = None, slot: Optional[MealSlot] = None) -> Tuple[float, List[str]]:
    score = 0.0
    reasons: List[str] = []

    # 1) goal-aware scoring
    g_score, g_reasons = goal_score(profile, recipe)
    score += g_score
    reasons += g_reasons

    # 2) cooking time preference
    t_score, t_reasons = time_score(profile, recipe)
    score += t_score
    reasons += t_reasons

    # 3) dietary preference tags 
    d_score, d_reasons = diet_tag_score(profile, recipe)
    score += d_score
    reasons += d_reasons

    # 4) learned user preferences from feedback
    if prefs is not None:
        p_score, p_reasons = preference_score(profile, recipe, prefs)
        score += p_score
        reasons += p_reasons

    # 5) disliked ingredients penalty
    pen, pen_reasons = disliked_penalty(profile, recipe)
    score += pen
    reasons += pen_reasons

    # 6) meal type alignment
    mt_score, mt_reasons = meal_type_score(recipe, slot)
    score += mt_score
    reasons += mt_reasons

    reasons = dedupe(reasons)

    return score, reasons


def goal_score(profile: UserProfile, recipe: Recipe) -> Tuple[float, List[str]]:
    reasons: List[str] = []
    s = 0.0

    goal = (profile.goal or "").lower()
    calories = estimate_calories(recipe)
    protein = recipe.protein_g
    carbs = recipe.carbs_g
    fat = recipe.fat_g

    # Defaults if missing
    protein = protein if protein is not None else 0.0
    carbs = carbs if carbs is not None else 0.0
    fat = fat if fat is not None else 0.0

    # weight loss: prefer lower calorie + decent protein
    if "loss" in goal or "lose" in goal or goal == "weight_loss":
        if calories is not None:
            if calories <= 500:
                s += 2.0
                reasons.append("under ~500 kcal")
            elif calories <= 700:
                s += 1.0
            else:
                s -= 1.0
                reasons.append("higher calorie")

        if protein >= 25:
            s += 2.0
            reasons.append("high protein")
        elif protein >= 15:
            s += 1.0

        # mild penalty for very high fat/carbs
        if fat >= 25:
            s -= 0.5
        if carbs >= 70:
            s -= 0.5

    # gain muscle / high protein: maximize protein
    elif "muscle" in goal or "gain" in goal or "protein" in goal or goal == "high_protein":
        if protein >= 35:
            s += 3.0
            reasons.append("very high protein")
        elif protein >= 25:
            s += 2.0
            reasons.append("high protein")
        elif protein >= 15:
            s += 1.0

        # don’t punish calories too hard here
        if calories is not None and calories < 350:
            s -= 0.5 
    else:
        # maintenance: balanced macros preferred
        if protein >= 20:
            s += 1.0
            reasons.append("good protein")
        if calories is not None and 350 <= calories <= 700:
            s += 1.0
            reasons.append("reasonable calories")

    return s, reasons


def time_score(profile: UserProfile, recipe: Recipe) -> Tuple[float, List[str]]:
    reasons: List[str] = []
    s = 0.0

    pref = (profile.cooking_time or "").lower()
    total = recipe.total_minutes

    if total is None:
        return 0.0, []  

    # interpret categories
    if "short" in pref or "<" in pref:
        if total <= 20:
            s += 1.5
            reasons.append("quick to make")
        elif total <= 35:
            s += 0.5
        else:
            s -= 1.0
            reasons.append("takes longer")
    elif "medium" in pref:
        if total <= 45:
            s += 0.5
        else:
            s -= 0.5
    elif "long" in pref:
        if total >= 45:
            s += 0.5  
    return s, reasons


def diet_tag_score(profile: UserProfile, recipe: Recipe) -> Tuple[float, List[str]]:
    reasons: List[str] = []
    s = 0.0

    prefs = [p.lower() for p in profile.dietary_preferences]
    tags = [t.lower() for t in recipe.tags]

    for pref in prefs:
        if pref in tags:
            s += 0.5
            reasons.append(pref)

    return s, reasons


def preference_score(profile: UserProfile, recipe: Recipe, prefs: UserPreferences) -> Tuple[float, List[str]]:
    if prefs is None:
        return 0, []
    reasons: List[str] = []
    s = 0.0

    

    if recipe.recipe_id in prefs.disliked_recipes_ids:
        return -6.0, ["you previously disliked this recipe"]

    if recipe.recipe_id in prefs.doesnt_fit_recipes_ids:
        return -4.0, ["you said this didn't fit"]

    if recipe.recipe_id in prefs.liked_recipes_ids:
        return 3.0, ["you previously liked this recipe"]

    if recipe.cuisine:
        w = prefs.cuisine_weights.get(recipe.cuisine.lower(), 0.0)
        if w != 0:
            s += 0.3 * w
            if w > 0:
                reasons.append("matches cuisines you liked")

    for tag in recipe.tags:
        w = prefs.tag_weights.get(tag.lower(), 0.0)
        if w != 0:
            s += 0.2 * w
            if w > 0:
                reasons.append("similar to recipes you liked")

    ingredient_matches = 0

    for ing in recipe.ingredients[:10]:
        w = prefs.ingredient_weights.get(ing.lower(), 0.0)

        if w != 0:
            s += 0.1 * w
            ingredient_matches += 1

    if ingredient_matches >= 2:
        reasons.append("contains ingredients you liked")
    elif ingredient_matches == 1:
        reasons.append("contains an ingredient you liked")

    return s, reasons


def disliked_penalty(profile: UserProfile, recipe: Recipe) -> Tuple[float, List[str]]:
    reasons: List[str] = []
    s = 0.0

    dislikes = [d.lower() for d in profile.disliked_ingredients]
    if not dislikes:
        return 0.0, []

    ing_text = " ".join([i.lower() for i in recipe.ingredients])

    for d in dislikes:
        if d and d in ing_text:
            s -= 2.0
            reasons.append(f"contains {d}")

    return s, reasons


def dedupe(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out
