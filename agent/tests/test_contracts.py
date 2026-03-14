import pytest
import re

from agent.interfaces import UserProfile, MealSlot, Recipe, DayPlan, PlannedMeal
from agent.constraints import filter_allowed, is_allowed
from agent.scoring import score_recipe
from agent.feedback import get_user_preferences, record_feedback
from agent.recommender import recommend


def make_profile(**overrides):
    base = dict(
        id=123,
        username="test_user",
        age=25,
        height_feet=5,
        height_inches=6,
        weight_lbs=150,
        gender="female",
        goal="Lose weight",
        dietary_preferences=[],
        allergies=[],
        medical_conditions=[],
        budget_level="medium",
        cooking_time="short",
        cuisine_preferences=[],
        disliked_ingredients=[],
    )
    base.update(overrides)
    return UserProfile(**base)


def test_constraints_allergy_filters_out_nuts():
    profile = make_profile(allergies=["nuts"])
    recipes = [
        Recipe(recipe_id=1, title="Almond smoothie", ingredients=["almond milk", "banana"]),
        Recipe(recipe_id=2, title="Berry smoothie", ingredients=["strawberries", "banana"]),
    ]
    allowed = filter_allowed(profile, recipes)
    titles = [r.title for r in allowed]
    assert "Almond smoothie" not in titles
    assert "Berry smoothie" in titles


def test_constraints_allergy_egg_does_not_match_eggplant():
    profile = make_profile(allergies=["Egg"])
    recipes = [
        Recipe(recipe_id=1, title="Eggplant Stir Fry", ingredients=["eggplant", "garlic"]),
        Recipe(recipe_id=2, title="Omelette", ingredients=["eggs", "cheese"]),
    ]
    allowed = filter_allowed(profile, recipes)
    titles = [r.title for r in allowed]
    assert "Eggplant Stir Fry" in titles
    assert "Omelette" not in titles


def test_medical_none_does_not_filter_anything():
    profile = make_profile(medical_conditions=["None"])
    recipe = Recipe(recipe_id=1, title="Rice Bowl", ingredients=["rice", "beans"], carbs_g=40, fat_g=8)
    assert is_allowed(profile, recipe)


def test_high_cholesterol_normalizes_from_ui_label():
    profile = make_profile(medical_conditions=["High Cholesterol"])
    recipes = [
        Recipe(recipe_id=1, title="Bacon and Eggs", ingredients=["bacon", "eggs"], fat_g=25),
        Recipe(recipe_id=2, title="Bean Soup", ingredients=["beans", "onion"], fat_g=4),
    ]
    allowed = filter_allowed(profile, recipes)
    titles = [r.title for r in allowed]
    assert "Bacon and Eggs" not in titles
    assert "Bean Soup" in titles


def test_celiac_allows_gluten_free_tagged_recipe():
    profile = make_profile(medical_conditions=["Celiac"])
    recipes = [
        Recipe(recipe_id=1, title="GF Pasta", ingredients=["gluten free pasta"], tags=["gluten_free"]),
        Recipe(recipe_id=2, title="Regular Pasta", ingredients=["wheat pasta"], tags=[]),
    ]
    allowed = filter_allowed(profile, recipes)
    titles = [r.title for r in allowed]
    assert "GF Pasta" in titles
    assert "Regular Pasta" not in titles


def test_scoring_goal_normalization_weight_loss_prefers_high_protein():
    profile = make_profile(goal="I want to lose weight")
    r_low_protein = Recipe(recipe_id=1, title="Toast", ingredients=["bread"], protein_g=5, carbs_g=50, fat_g=5)
    r_high_protein = Recipe(recipe_id=2, title="Chicken salad", ingredients=["chicken"], protein_g=30, carbs_g=10, fat_g=10)

    s1, _ = score_recipe(profile, r_low_protein, prefs=None, slot=None)
    s2, _ = score_recipe(profile, r_high_protein, prefs=None, slot=None)
    assert s2 > s1


def test_feedback_like_increases_scores_for_similar_recipes():
    user_id = 999
    profile = make_profile(id=user_id, goal="Gain muscle")

    slot = MealSlot(day=1, meal_type="dinner")

    before = recommend(user_id=user_id, profile=profile, slot=slot, k=10)
    assert len(before) > 0
    liked = before[0].recipe

    record_feedback(user_id=user_id, recipe=liked, action="like")

    after = recommend(user_id=user_id, profile=profile, slot=slot, k=10)
    assert len(after) > 0

    prefs = get_user_preferences(user_id)
    if liked.cuisine:
        assert prefs.cuisine_weights.get(liked.cuisine.lower(), 0) > 0
    for t in liked.tags:
        assert prefs.tag_weights.get(t.lower(), 0) > 0


def test_profile_disliked_ingredient_penalizes_recipe():
    profile = make_profile(disliked_ingredients=["mushroom"])
    r_mush = Recipe(recipe_id=1, title="Mushroom omelette", ingredients=["mushroom", "eggs"], protein_g=20)
    r_no = Recipe(recipe_id=2, title="Greek yogurt bowl", ingredients=["yogurt", "berries"], protein_g=20)

    s_m, _ = score_recipe(profile, r_mush, prefs=None, slot=None)
    s_n, _ = score_recipe(profile, r_no, prefs=None, slot=None)
    assert s_n > s_m


from agent.mock_data import (
    MOCK_RECIPES_BY_ID,
    MOCK_NUTRITION_TARGETS,
    MOCK_PROFILE,
    mock_candidates,
)
from agent.planner import (
    MockMealPlanner,
    MealPlanner,
    extract_json,
    parse_meal_plan,
)
from agent.grocery import SimpleGroceryGenerator, aggregate_ingredients
from agent.interfaces import MealPlan, GroceryList


def test_mock_planner_produces_7_day_schedule():
    planner = MockMealPlanner()
    candidates = mock_candidates()
    plan = planner.generate_plan(
        profile=MOCK_PROFILE,
        candidates=candidates,
        nutrition_targets=MOCK_NUTRITION_TARGETS,
    )
    assert isinstance(plan, MealPlan)
    assert len(plan.days) == 7
    for day_plan in plan.days:
        assert 1 <= day_plan.day <= 7
        assert len(day_plan.meals) == 3
        meal_types = {m.meal_type for m in day_plan.meals}
        assert meal_types == {"breakfast", "lunch", "dinner"}
        for meal in day_plan.meals:
            assert meal.recipe_id in MOCK_RECIPES_BY_ID


def test_mock_planner_all_recipe_ids_are_valid():
    planner = MockMealPlanner()
    candidates = mock_candidates()
    plan = planner.generate_plan(
        profile=MOCK_PROFILE,
        candidates=candidates,
        nutrition_targets=MOCK_NUTRITION_TARGETS,
    )
    valid_ids = {c.recipe_id for c in candidates}
    for day_plan in plan.days:
        for meal in day_plan.meals:
            assert meal.recipe_id in valid_ids, (
                f"Day {day_plan.day} {meal.meal_type}: recipe_id {meal.recipe_id} not in candidates"
            )


def test_grocery_list_from_mock_plan():
    planner = MockMealPlanner()
    candidates = mock_candidates()
    plan = planner.generate_plan(
        profile=MOCK_PROFILE,
        candidates=candidates,
        nutrition_targets=MOCK_NUTRITION_TARGETS,
    )
    gen = SimpleGroceryGenerator()
    grocery = gen.generate(plan, MOCK_RECIPES_BY_ID)
    assert isinstance(grocery, GroceryList)
    assert hasattr(grocery, "text")
    assert len(grocery.items) > 0
    for item in grocery.items:
        assert item.name
        if item.quantity is not None:
            assert item.quantity > 0
        assert item.unit != "meals"
        assert item.category is not None


def test_grocery_list_aggregates_across_meals():
    planner = MockMealPlanner()
    candidates = mock_candidates()
    plan = planner.generate_plan(
        profile=MOCK_PROFILE,
        candidates=candidates,
        nutrition_targets=MOCK_NUTRITION_TARGETS,
    )
    items = aggregate_ingredients(plan, MOCK_RECIPES_BY_ID)
    names = [i.name for i in items]
    assert len(names) == len(set(names)), "Grocery list should have no duplicate ingredient names"


def test_normalization_and_filtering_drops_junk():
    from agent.grocery import _normalize_ingredient, aggregate_ingredients

    assert _normalize_ingredient("apricots similar amount of your favorite fruit") == "apricot"
    assert _normalize_ingredient("such as gewurztraminer") == ""
    assert _normalize_ingredient("watermelon chunk") == "watermelon chunk"
    assert _normalize_ingredient("at room temperature") == ""

    r = Recipe(recipe_id=99, title="X", ingredients=[
        "apricots similar amount of your favorite fruit",
        "watermelon chunk",
        "1 pound whole pork loin",
        "such as gewurztraminer",
        "1 cup sugar",
    ])
    plan = MealPlan(days=[DayPlan(day=1, meals=[PlannedMeal(day=1, meal_type="breakfast", recipe_id=99, title="X", servings=1)])])
    items = aggregate_ingredients(plan, {99: r})
    names = [i.name for i in items]
    assert "apricot" in names
    assert "sugar" in names
    assert "watermelon chunk" not in names
    assert "pound whole pork loin" not in names
    assert "gewurztraminer" not in names


def test_blacklist_ice_removed():
    r = Recipe(recipe_id=1, title="Iced Tea", ingredients=["ice cubes", "tea bag"], cuisine=None, tags=[])
    plan = MealPlan(days=[DayPlan(day=1, meals=[PlannedMeal(day=1, meal_type="lunch", recipe_id=1, title="Iced Tea", servings=1)])])
    items = aggregate_ingredients(plan, {1: r})
    names = [i.name for i in items]
    assert "ice cube" not in names and "ice" not in names


def test_grocery_text_is_deterministic():
    planner = MockMealPlanner()
    candidates = mock_candidates()
    plan = planner.generate_plan(
        profile=MOCK_PROFILE,
        candidates=candidates,
        nutrition_targets=MOCK_NUTRITION_TARGETS,
    )
    gen = SimpleGroceryGenerator()
    grocery = gen.generate(plan, MOCK_RECIPES_BY_ID)
    assert grocery.text is not None
    assert "meals" not in grocery.text


def test_extract_json_plain():
    raw = '{"days": [], "notes": "ok"}'
    result = extract_json(raw)
    assert result["notes"] == "ok"


def test_extract_json_with_markdown_fences():
    raw = '```json\n{"days": [], "notes": "fenced"}\n```'
    result = extract_json(raw)
    assert result["notes"] == "fenced"


def test_extract_json_with_surrounding_text():
    raw = 'Here is the plan:\n{"days": [], "notes": "embedded"}\nHope you like it!'
    result = extract_json(raw)
    assert result["notes"] == "embedded"


def test_parse_meal_plan_populates_nutrition():
    raw = {
        "days": [
            {
                "day": 1,
                "meals": [
                    {"meal_type": "breakfast", "recipe_id": 1001, "title": "Grilled Chicken Salad", "servings": 1},
                    {"meal_type": "lunch", "recipe_id": 1002, "title": "Veggie Stir Fry", "servings": 1},
                    {"meal_type": "dinner", "recipe_id": 1004, "title": "Salmon with Asparagus", "servings": 1},
                ],
            }
        ],
        "notes": "test",
    }

    plan = parse_meal_plan(raw, MOCK_RECIPES_BY_ID)
    assert plan.days[0].meals[0].calories is not None
    assert plan.days[0].meals[0].protein_g is not None
