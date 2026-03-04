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
    assert item.unit == "cup"
    assert item.quantity == 1.5
