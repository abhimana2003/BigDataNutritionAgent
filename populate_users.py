import random
from database import SessionLocal, Base, engine
from models import UserProfile, Recipe

Base.metadata.create_all(bind=engine)

GENDERS = ["female", "male", "other"]
GOALS = ["weight loss", "maintenance", "high protein", "gluten free"]
DIETARY_OPTIONS = ["vegetarian", "vegan", "pescaterian", "low carb", "keto"]
ALLERGIES = ["nuts", "dairy", "gluten", "soy", "eggs"]
MEDICAL_CONDITIONS = ["diabetes", "hypertension", "celiac", "high cholesterol"]
BUDGET_LEVELS = ["low", "medium", "high"]
COOKING_TIMES = ["short (<30 mins)", "medium (30-60 min)", "long(>60 mins)"]

NUM_USERS = 20  

def random_subset(options):
    return random.sample(options, k=random.randint(0, len(options)))

def random_user_profile():
    return {
        "age": random.randint(18, 70),
        "height_inches": round(random.uniform(0, 11), 1),
        "height_feet": random.randint(3, 7),
        "weight": round(random.uniform(40, 1000), 1),
        "gender": random.choice(GENDERS),
        "goal": random.choice(GOALS),
        "dietary_preferences": random_subset(DIETARY_OPTIONS),
        "allergies": random_subset(ALLERGIES),
        "medical_conditions": random_subset(MEDICAL_CONDITIONS),
        "budget_level": round(random.uniform(20, 500), 1),
        "cooking_time": random.choice(COOKING_TIMES),
    }


def populate_users(num_users=NUM_USERS):
    db = SessionLocal()

    existing = db.query(UserProfile).count()
    if existing > 0:
        print(f"UserProfile table already has {existing} rows. Skipping population.")
        db.close()
        return

    user_objects = []
    all_recipes = db.query(Recipe).all()  
    for _ in range(num_users):
        profile_data = random_user_profile()
        user = UserProfile(**profile_data)

        if all_recipes:
            user.favorite_recipes = random.sample(all_recipes, k=min(3, len(all_recipes)))

        user_objects.append(user)

    db.bulk_save_objects(user_objects)
    db.commit()
    db.close()
    print(f"Populated {len(user_objects)} random users.")


if __name__ == "__main__":
    populate_users()