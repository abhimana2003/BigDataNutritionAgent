import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Recipe as RecipeORM
from schemas import CookingTimeLevel, GoalType, MealSlot, MealType, UserProfileCreate


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    RecipeORM.__table__.create(engine, checkfirst=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()

    recipes = [
        RecipeORM(
            id=1,
            recipe_name="Chicken Salad",
            ingredients=["chicken", "lettuce", "olive oil"],
            dietary_tags=["high_protein", "gluten_free"],
            cuisine_path="american",
            category="main",
        ),
        RecipeORM(
            id=2,
            recipe_name="Veggie Pasta",
            ingredients=["pasta", "tomato", "basil"],
            dietary_tags=["vegetarian"],
            cuisine_path="italian",
            category="main",
        ),
        RecipeORM(
            id=3,
            recipe_name="Fruit Bowl",
            ingredients=["banana", "berries"],
            dietary_tags=["vegan"],
            cuisine_path="american",
            category="snack",
        ),
    ]
    session.add_all(recipes)
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def sample_profile():
    return UserProfileCreate(
        username="sample_user",
        age=30,
        height_feet=5,
        height_inches=8,
        weight=165.0,
        gender="female",
        goal=GoalType.weight_loss,
        dietary_preferences=["vegetarian"],
        allergies=[],
        medical_conditions=[],
        budget_level="medium",
        cooking_time=CookingTimeLevel.short,
    )


@pytest.fixture()
def sample_slot():
    return MealSlot(day=1, meal_type=MealType.dinner)
