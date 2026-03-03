from __future__ import annotations

from typing import List, Optional, Tuple

from agent.interfaces import MealSlot, Recipe, UserPreferences, UserProfile

# optional classifier so we can fall back to a learned model if rules
# aren't sufficient.  The module will train itself on first import.
try:
    from agent.meal_type_classifier import predict_meal_type
except ImportError:
    predict_meal_type = lambda r: "lunchdinner"  # no classifier available

BREAKFAST_INCLUDE = [
    "breakfast", "oat", "omelette", "pancake", "waffle", "toast",
    "parfait", "smoothie", "yogurt", "granola", "cereal", "muffin",
]

# Additional excludes to keep obvious non-breakfast meals out; adding a
# generic "fish"/"salmon" entry because those were creeping in via poor
# classifier predictions and still have breakfasty ingredients like egg.
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


def is_slot_compatible(recipe: Recipe, slot: Optional[MealSlot]) -> bool:
    if slot is None:
        return True
    text = _recipe_text(recipe)
    meal_type = slot.meal_type.lower()

    # helper: check tags/cuisine path for explicit meal category
    def has_breakfast_tag() -> bool:
        if recipe.tags:
            for t in recipe.tags:
                if "breakfast" in str(t).lower():
                    return True
        if recipe.cuisine:
            if "breakfast" in str(recipe.cuisine).lower():
                return True
        return False

    if meal_type == "breakfast":
        # first, consult the classifier if present
        if predict_meal_type(recipe) != "breakfast":
            return False

        # still apply rule-based keywords for extra safety
        has_breakfast_signal = has_breakfast_tag() or any(k in text for k in BREAKFAST_INCLUDE)
        has_non_breakfast_signal = any(k in text for k in BREAKFAST_EXCLUDE)
        return has_breakfast_signal and not has_non_breakfast_signal

    if meal_type in ("lunch", "dinner"):
        # classifier may collapse lunch/dinner into same bucket; if it says
        # breakfast, we must reject
        if predict_meal_type(recipe) == "breakfast":
            return False

        has_light_breakfast_signal = any(k in text for k in LUNCH_DINNER_EXCLUDE)
        return not has_light_breakfast_signal

    return True


def meal_type_score(recipe: Recipe, slot: Optional[MealSlot]) -> Tuple[float, List[str]]:
    if slot is None:
        return 0.0, []
    if is_slot_compatible(recipe, slot):
        return 1.0, [f"fits {slot.meal_type}"]
    return -4.0, [f"weak fit for {slot.meal_type}"]


def estimate_calories(recipe: Recipe) -> Optional[float]:
    """
    If calories are missing but macros exist, estimate:
    kcal ≈ 4*protein + 4*carbs + 9*fat
    """
    if recipe.calories is not None:
        return recipe.calories
    if recipe.protein_g is None or recipe.carbs_g is None or recipe.fat_g is None:
        return None
    return 4 * recipe.protein_g + 4 * recipe.carbs_g + 9 * recipe.fat_g


def score_recipe(
    profile: UserProfile,
    recipe: Recipe,
    prefs: Optional[UserPreferences] = None,
    slot: Optional[MealSlot] = None,
) -> Tuple[float, List[str]]:
    """
    Main scoring function: returns (score, reasons).
    Higher score = better recommendation.
    """
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

    # 3) dietary preference tags (light boost; hard constraints should be filtered elsewhere)
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

    # keep reasons readable
    reasons = dedupe(reasons)

    return score, reasons


def goal_score(profile: UserProfile, recipe: Recipe) -> Tuple[float, List[str]]:
    """
    Goal-aware scoring based on calories/macros.
    """
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

        # don’t punish calories too hard here (bulking may require calories)
        if calories is not None and calories < 350:
            s -= 0.5  # might be too light
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
    """
    Cooking time alignment with profile.cooking_time.
    """
    reasons: List[str] = []
    s = 0.0

    pref = (profile.cooking_time or "").lower()
    total = recipe.total_minutes

    if total is None:
        return 0.0, []  # don’t score if unknown for MVP

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
            s += 0.5  # user is okay with longer meals
    return s, reasons


def diet_tag_score(profile: UserProfile, recipe: Recipe) -> Tuple[float, List[str]]:
    """
    Soft scoring based on dietary preferences and recipe tags.
    Hard filtering should be done in constraints.py.
    """
    reasons: List[str] = []
    s = 0.0

    prefs = [p.lower() for p in profile.dietary_preferences]
    tags = [t.lower() for t in recipe.tags]

    # small boosts if tags match what user wants
    for pref in prefs:
        if pref in tags:
            s += 0.5
            reasons.append(pref)

    return s, reasons


def preference_score(profile: UserProfile, recipe: Recipe, prefs: UserPreferences) -> Tuple[float, List[str]]:
    """
    Learned preferences from like/dislike history.
    """
    reasons: List[str] = []
    s = 0.0

    # cuisine
    if recipe.cuisine:
        w = prefs.cuisine_weights.get(recipe.cuisine.lower(), 0.0)
        if w != 0:
            s += 0.3 * w
            if w > 0:
                reasons.append("matches cuisines you liked")

    # tags
    for tag in recipe.tags:
        w = prefs.tag_weights.get(tag.lower(), 0.0)
        if w != 0:
            s += 0.2 * w
            if w > 0:
                reasons.append("similar to recipes you liked")

    # ingredients (this can be noisy, keep it low weight)
    for ing in recipe.ingredients[:10]:
        w = prefs.ingredient_weights.get(ing.lower(), 0.0)
        if w != 0:
            s += 0.05 * w

    return s, reasons


def disliked_penalty(profile: UserProfile, recipe: Recipe) -> Tuple[float, List[str]]:
    """
    Penalize recipes containing disliked ingredients from profile.
    (Feedback dislikes will be handled in prefs weights, but this is user-stated dislikes.)
    """
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
