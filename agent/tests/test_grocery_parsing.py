import math
from agent.grocery import aggregate_ingredients, canonicalize_ingredient_name, parse_ingredient_line
from agent.interfaces import DayPlan, MealPlan, PlannedMeal, Recipe
from agent.planner import parse_grocery_list


def test_parse_grocery_list_cleans_noisy_names_and_extracts_qty_unit():
    raw = {
        "grocery_list": [
            {"name": "base_servings", "quantity": None, "unit": None, "category": None},
            {"name": "2 cup frozen bananas", "quantity": None, "unit": None, "category": "produce"},
            {"name": "1.5 lb tilapia fillets", "quantity": None, "unit": None, "category": "protein"},
            {"name": "1 can canned pitted dark cherries", "quantity": None, "unit": None, "category": "produce"},
            {"name": "salt and ground black pepper", "quantity": None, "unit": None, "category": "spices"},
            {"name": "1 avocado", "quantity": None, "unit": None, "category": "produce"},
        ]
    }

    grocery = parse_grocery_list(raw)
    by_name = {item.name: item for item in grocery.items}

    assert "base_servings" not in by_name
    assert "black pepper" not in by_name
    assert "banana" in by_name
    assert by_name["banana"].quantity == 2.0
    assert by_name["banana"].unit == "cup"
    assert "tilapia fillet" in by_name
    assert by_name["tilapia fillet"].quantity == 1.5
    assert by_name["tilapia fillet"].unit == "lb"
    assert "dark cherry" in by_name
    assert by_name["dark cherry"].quantity == 1.0
    assert by_name["dark cherry"].unit == "can"
    assert "avocado" in by_name
    assert by_name["avocado"].quantity == 1.0


def test_parse_grocery_list_merges_equivalent_units():
    raw = {
        "grocery_list": [
            {"name": "banana", "quantity": 1, "unit": "cup", "category": "produce"},
            {"name": "bananas", "quantity": 0.5, "unit": "cups", "category": "produce"},
        ]
    }

    grocery = parse_grocery_list(raw)
    assert len(grocery.items) == 1
    item = grocery.items[0]
    assert item.name == "banana"
    assert item.unit == "tbsp"
    assert item.quantity == 24.0


def test_parse_grocery_list_merges_mixed_volume_units():
    raw = {
        "grocery_list": [
            {"name": "olive oil", "quantity": 1, "unit": "tsp", "category": "pantry"},
            {"name": "olive oil", "quantity": 1, "unit": "tbsp", "category": "pantry"},
            {"name": "olive oil", "quantity": 0.25, "unit": "cup", "category": "pantry"},
        ]
    }
    grocery = parse_grocery_list(raw)
    assert len(grocery.items) == 1
    item = grocery.items[0]
    assert item.unit == "tbsp"
    assert math.isclose(item.quantity or 0.0, 5.3333333, rel_tol=1e-6)


def test_parse_grocery_list_merges_mixed_weight_units():
    raw = {
        "grocery_list": [
            {"name": "salmon", "quantity": 8, "unit": "oz", "category": "protein"},
            {"name": "salmon", "quantity": 1, "unit": "lb", "category": "protein"},
        ]
    }
    grocery = parse_grocery_list(raw)
    assert len(grocery.items) == 1
    item = grocery.items[0]
    assert item.unit == "oz"
    assert item.quantity == 24.0


def test_parse_grocery_list_merges_metric_units():
    raw = {
        "grocery_list": [
            {"name": "yogurt", "quantity": 500, "unit": "g", "category": "dairy"},
            {"name": "yogurt", "quantity": 1, "unit": "kg", "category": "dairy"},
            {"name": "milk", "quantity": 250, "unit": "ml", "category": "dairy"},
            {"name": "milk", "quantity": 1, "unit": "l", "category": "dairy"},
        ]
    }
    grocery = parse_grocery_list(raw)
    by_name = {item.name: item for item in grocery.items}
    assert by_name["yogurt"].unit == "g"
    assert by_name["yogurt"].quantity == 1500.0
    assert by_name["milk"].unit == "ml"
    assert by_name["milk"].quantity == 1250.0


def test_parse_grocery_list_keeps_incompatible_units_separate():
    raw = {
        "grocery_list": [
            {"name": "spinach", "quantity": 1, "unit": "cup", "category": "produce"},
            {"name": "spinach", "quantity": 1, "unit": "lb", "category": "produce"},
        ]
    }
    grocery = parse_grocery_list(raw)
    spinach_units = sorted((item.unit, item.quantity) for item in grocery.items if item.name == "spinach")
    assert spinach_units == [("oz", 16.0), ("tbsp", 16.0)]


def test_parse_ingredient_line_examples():
    parsed = parse_ingredient_line("2 tbsp olive oil")
    assert parsed is not None
    assert parsed.name == "olive oil"
    assert parsed.quantity == 2.0
    assert parsed.unit == "tbsp"

    parsed = parse_ingredient_line("1 1/2 cups flour")
    assert parsed is not None
    assert parsed.name == "flour"
    assert parsed.quantity == 1.5
    assert parsed.unit == "cup"

    parsed = parse_ingredient_line("1 dozen eggs")
    assert parsed is not None
    assert parsed.name == "egg"
    assert parsed.quantity == 12.0
    assert parsed.unit == "count"

    parsed = parse_ingredient_line("3 eggs")
    assert parsed is not None
    assert parsed.name == "egg"
    assert parsed.quantity == 3.0
    assert parsed.unit == "count"

    parsed = parse_ingredient_line("1 can black beans, drained and rinsed")
    assert parsed is not None
    assert parsed.name == "black bean"
    assert parsed.quantity == 1.0
    assert parsed.unit == "can"

    parsed = parse_ingredient_line("2 cups baby spinach")
    assert parsed is not None
    assert parsed.name == "spinach"
    assert parsed.quantity == 2.0
    assert parsed.unit == "cup"

    assert parse_ingredient_line("salt and pepper to taste") is None


def test_canonicalize_ingredient_name_examples():
    assert canonicalize_ingredient_name("extra virgin olive oil") == "olive oil"
    assert canonicalize_ingredient_name("baby spinach") == "spinach"
    assert canonicalize_ingredient_name("breadcrumbs") == "bread crumb"
    assert canonicalize_ingredient_name("eggs") == "egg"


def test_aggregate_ingredients_scales_and_merges_with_conversions():
    recipes_by_id = {
        1: Recipe(
            recipe_id=1,
            title="Test A",
            servings=2,
            ingredients=["2 tbsp olive oil", "1 dozen eggs"],
        ),
        2: Recipe(
            recipe_id=2,
            title="Test B",
            servings=4,
            ingredients=["1/4 cup extra virgin olive oil", "4 eggs"],
        ),
    }
    plan = MealPlan(
        days=[
            DayPlan(
                day=1,
                meals=[
                    PlannedMeal(day=1, meal_type="dinner", recipe_id=1, title="A", servings=4),
                    PlannedMeal(day=1, meal_type="lunch", recipe_id=2, title="B", servings=4),
                ],
            )
        ]
    )
    items = aggregate_ingredients(plan, recipes_by_id)
    by_name_unit = {(i.name, i.unit): i for i in items}

    olive = by_name_unit.get(("olive oil", "tbsp"))
    assert olive is not None
    assert olive.quantity == 8.0

    eggs = by_name_unit.get(("egg", "count"))
    assert eggs is not None
    assert eggs.quantity == 28.0


def test_aggregate_ingredients_keeps_incompatible_units_separate():
    recipes_by_id = {
        1: Recipe(
            recipe_id=1,
            title="Test C",
            servings=1,
            ingredients=["1 cup spinach", "1 lb spinach"],
        ),
    }
    plan = MealPlan(
        days=[
            DayPlan(
                day=1,
                meals=[PlannedMeal(day=1, meal_type="dinner", recipe_id=1, title="C", servings=1)],
            )
        ]
    )
    items = aggregate_ingredients(plan, recipes_by_id)
    names = [(i.name, i.unit, i.quantity) for i in items if i.name == "spinach"]
    assert len(names) == 2
    assert ("spinach", "tbsp", 16.0) in names
    assert ("spinach", "oz", 16.0) in names


def test_aggregate_ingredients_drops_unknown_when_quantified():
    recipes_by_id = {
        1: Recipe(
            recipe_id=1,
            title="Test D",
            servings=1,
            ingredients=["spinach", "1 cup spinach"],
        ),
    }
    plan = MealPlan(
        days=[
            DayPlan(
                day=1,
                meals=[PlannedMeal(day=1, meal_type="dinner", recipe_id=1, title="D", servings=1)],
            )
        ]
    )
    items = aggregate_ingredients(plan, recipes_by_id)
    spinach_items = [i for i in items if i.name == "spinach"]
    assert len(spinach_items) == 1
    assert spinach_items[0].quantity == 16.0
