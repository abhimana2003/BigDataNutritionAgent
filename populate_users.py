import random
from database import SessionLocal, Base, engine
from models import UserProfile, Recipe
from auth_utils import hash_password
import string

Base.metadata.create_all(bind=engine)

GENDERS = ["female", "male", "other"]
GOALS = ["weight loss", "maintenance", "high protein"]
DIETARY_OPTIONS = ["vegetarian", "vegan", "pescaterian", "low carb", "keto"]
ALLERGIES = ["nuts", "dairy", "gluten", "soy", "eggs"]
MEDICAL_CONDITIONS = ["diabetes", "hypertension", "celiac", "high cholesterol"]
BUDGET_LEVELS = ["low", "medium", "high"]
COOKING_TIMES = ["short (<30 mins)", "medium (30-60 min)", "long (>60 mins)"]

NUM_USERS = 10  

def random_subset(options):
    return random.sample(options, k=random.randint(0, len(options)))

def random_user_profile():
    return {
        "age": random.randint(18, 70),
        "height_inches": round(random.randint(0, 11), 1),
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

def generate_username(existing_usernames):
    while True:
        username = "user_" + ''.join(random.choices(string.ascii_lowercase, k=5))
        if username not in existing_usernames:
            return username

def populate_users(num_users=NUM_USERS):
    db = SessionLocal()

    existing_usernames = {user.username for user in db.query(UserProfile.username).all()}

    for _ in range(num_users):
        profile_data = random_user_profile()
        username = generate_username(existing_usernames)
        salt, digest = hash_password("password123")
        user = UserProfile(
            username=username,
            email=f"{username}@example.com",
            full_name=username.replace("_", " ").title(),
            password_salt=salt,
            password_hash=digest,
            **profile_data,
        )

        db.add(user)
        existing_usernames.add(username)
    
    db.commit()
    db.close()

if __name__ == "__main__":
    populate_users()
