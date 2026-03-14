from agent.recommender import recommend
from agent.interfaces import UserProfile, MealSlot
from agent.feedback import record_feedback

# for testing

def print_top(label, recs, n=5):
    print("\n" + "=" * 80)
    print(label)
    print("=" * 80)
    for i, c in enumerate(recs[:n], start=1):
        r = c.recipe
        print(f"{i:>2}. {r.title} | score={c.score:.2f} | cuisine={r.cuisine} | "
              f"P={r.protein_g} C={r.carbs_g} F={r.fat_g} kcal={r.calories}")
        if c.reasons:
            print("    why:", ", ".join(c.reasons[:4]))


def main():
    user_id = 1
    profile = UserProfile(
        user_id=user_id,
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
        cooking_time="short (<30 mins)",
        cuisine_preferences=[],
        disliked_ingredients=[],
    )
    slot = MealSlot(day=1, meal_type="dinner")

    before = recommend(user_id=user_id, profile=profile, slot=slot, k=10)
    print_top("BEFORE FEEDBACK", before)

    top = before[0].recipe
    print(f"\n>>> Liking: {top.title}")
    record_feedback(user_id=user_id, recipe=top, action="like")

    after_like = recommend(user_id=user_id, profile=profile, slot=slot, k=10)
    print_top("AFTER LIKE", after_like)

    profile.disliked_ingredients = ["mushroom"]
    after_dislike_ing = recommend(user_id=user_id, profile=profile, slot=slot, k=10)
    print_top("AFTER DISLIKING 'mushroom' (profile)", after_dislike_ing)


if __name__ == "__main__":
    main()