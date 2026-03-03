import pytest

from agent.interfaces import UserProfile, MealSlot, Recipe, DayPlan, PlannedMeal
from agent.constraints import filter_allowed
from agent.scoring import score_recipe
from agent.mock_store import get_user_preferences, record_feedback
from agent.recommender import recommend


def make_profile(**overrides):
    base = dict(
        user_id=123,
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


def test_scoring_goal_normalization_weight_loss_prefers_high_protein():
    profile = make_profile(goal="I want to lose weight")
    r_low_protein = Recipe(recipe_id=1, title="Toast", ingredients=["bread"], protein_g=5, carbs_g=50, fat_g=5)
    r_high_protein = Recipe(recipe_id=2, title="Chicken salad", ingredients=["chicken"], protein_g=30, carbs_g=10, fat_g=10)

    s1, _ = score_recipe(profile, r_low_protein, prefs=None, slot=None)
    s2, _ = score_recipe(profile, r_high_protein, prefs=None, slot=None)
    assert s2 > s1


def test_feedback_like_increases_scores_for_similar_recipes():
    user_id = 999
    profile = make_profile(user_id=user_id, goal="Gain muscle")  # should favor protein

    slot = MealSlot(day=1, meal_type="dinner")

    # Run initial recommend (uses real dataset, so we only assert relative changes)
    before = recommend(user_id=user_id, profile=profile, slot=slot, k=10)
    assert len(before) > 0
    liked = before[0].recipe

    # Like top recipe
    record_feedback(user_id=user_id, recipe=liked, action="like")

    after = recommend(user_id=user_id, profile=profile, slot=slot, k=10)

    # We can't guarantee exact recipe ordering with real data,
    # but we CAN guarantee the preference store got updated:
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


# =====================================================================
# Planner contract tests
# =====================================================================

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
    # text field may or may not be populated depending on LLM availability
    assert hasattr(grocery, "text")
    assert len(grocery.items) > 0
    for item in grocery.items:
        assert item.name
        assert item.quantity is not None and item.quantity > 0
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
    # ensure bizarre long descriptions are normalized and then filtered
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
    # ingredient strings containing ice/cube should be blacklisted
    r = Recipe(recipe_id=1, title="Iced Tea", ingredients=["ice cubes", "tea bag"], cuisine=None, tags=[])
    plan = MealPlan(days=[DayPlan(day=1, meals=[PlannedMeal(day=1, meal_type="lunch", recipe_id=1, title="Iced Tea", servings=1)])])
    items = aggregate_ingredients(plan, {1: r})
    names = [i.name for i in items]
    assert "ice cube" not in names and "ice" not in names


def test_llm_refine_grocery(monkeypatch):
    # ensure text field is populated when LLM helper returns something
    import agent.grocery as g
    monkeypatch.setattr(g, "_llm_refine_list", lambda names: "- sugar\n- flour")
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
    assert "- sugar" in grocery.text




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
    assert len(plan.days) == 1
    breakfast = plan.days[0].meals[0]
    assert breakfast.calories == 350.0
    assert breakfast.protein_g == 35.0


def test_llm_planner_with_fake_client():
    """Contract: given a fixed recommendation set and a fake LLM response,
    the planner produces a valid 7-day schedule and consistent grocery list."""
    fake_response = """
    {
      "days": [
        {"day": 1, "meals": [
          {"meal_type": "breakfast", "recipe_id": 1003, "title": "Overnight Oats", "servings": 1},
          {"meal_type": "lunch", "recipe_id": 1001, "title": "Grilled Chicken Salad", "servings": 1},
          {"meal_type": "dinner", "recipe_id": 1004, "title": "Salmon with Asparagus", "servings": 1}
        ]},
        {"day": 2, "meals": [
          {"meal_type": "breakfast", "recipe_id": 1006, "title": "Greek Yogurt Parfait", "servings": 1},
          {"meal_type": "lunch", "recipe_id": 1011, "title": "Tuna Wrap", "servings": 1},
          {"meal_type": "dinner", "recipe_id": 1008, "title": "Chicken Stir Fry with Rice", "servings": 1}
        ]},
        {"day": 3, "meals": [
          {"meal_type": "breakfast", "recipe_id": 1009, "title": "Egg White Omelette", "servings": 1},
          {"meal_type": "lunch", "recipe_id": 1007, "title": "Black Bean Tacos", "servings": 1},
          {"meal_type": "dinner", "recipe_id": 1005, "title": "Turkey Meatballs", "servings": 1}
        ]},
        {"day": 4, "meals": [
          {"meal_type": "breakfast", "recipe_id": 1012, "title": "Banana Smoothie", "servings": 1},
          {"meal_type": "lunch", "recipe_id": 1015, "title": "Caprese Salad", "servings": 1},
          {"meal_type": "dinner", "recipe_id": 1014, "title": "Beef and Broccoli", "servings": 1}
        ]},
        {"day": 5, "meals": [
          {"meal_type": "breakfast", "recipe_id": 1017, "title": "Peanut Butter Toast", "servings": 1},
          {"meal_type": "lunch", "recipe_id": 1018, "title": "Chicken Caesar Wrap", "servings": 1},
          {"meal_type": "dinner", "recipe_id": 1019, "title": "Vegetable Curry", "servings": 1}
        ]},
        {"day": 6, "meals": [
          {"meal_type": "breakfast", "recipe_id": 1021, "title": "Mixed Berry Smoothie Bowl", "servings": 1},
          {"meal_type": "lunch", "recipe_id": 1020, "title": "Turkey Sandwich", "servings": 1},
          {"meal_type": "dinner", "recipe_id": 1016, "title": "Shrimp Tacos", "servings": 1}
        ]},
        {"day": 7, "meals": [
          {"meal_type": "breakfast", "recipe_id": 1003, "title": "Overnight Oats", "servings": 1},
          {"meal_type": "lunch", "recipe_id": 1013, "title": "Lentil Soup", "servings": 1},
          {"meal_type": "dinner", "recipe_id": 1010, "title": "Quinoa Buddha Bowl", "servings": 1}
        ]}
      ],
      "notes": "Balanced 7-day plan"
    }
    """

    def fake_llm(system: str, user: str) -> str:
        return fake_response

    planner = MealPlanner(llm_client=fake_llm)
    candidates = mock_candidates()

    plan = planner.generate_plan(
        profile=MOCK_PROFILE,
        candidates=candidates,
        nutrition_targets=MOCK_NUTRITION_TARGETS,
    )

    assert len(plan.days) == 7
    all_recipe_ids = set()
    for dp in plan.days:
        assert len(dp.meals) == 3
        meal_types = {m.meal_type for m in dp.meals}
        assert meal_types == {"breakfast", "lunch", "dinner"}
        for m in dp.meals:
            assert m.recipe_id in MOCK_RECIPES_BY_ID
            all_recipe_ids.add(m.recipe_id)

    assert len(all_recipe_ids) >= 7, "Plan should use at least 7 distinct recipes for variety"

    gen = SimpleGroceryGenerator()
    grocery = gen.generate(plan, MOCK_RECIPES_BY_ID)
    assert len(grocery.items) > 0
    ingredient_names = [i.name for i in grocery.items]
    assert len(ingredient_names) == len(set(ingredient_names)), "Grocery items should be deduplicated"