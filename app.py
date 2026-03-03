import streamlit as st
import requests
from typing import List, Dict, Any

API_URL = "http://localhost:8000/profiles"

# ---------- helpers ---------------------------------------------------------

def fetch_profiles() -> List[Dict[str, Any]]:
    try:
        resp = requests.get(API_URL)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        st.error(f"Unable to load profiles: {e}")
        return []


def fetch_profile(profile_id: int) -> Dict[str, Any]:
    try:
        resp = requests.get(f"{API_URL}/{profile_id}")
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return {}


def show_profile_form() -> None:
    st.title("Nutrition AI Agent — Create/Update Profile")

    profiles = fetch_profiles()
    edit_id = None
    if profiles:
        opts = ["New profile"] + [f"{p['id']} - {p.get('age')}yo {p.get('gender')}" for p in profiles]
        sel = st.selectbox("Select existing profile to edit", opts)
        if sel != "New profile":
            edit_id = int(sel.split(" ")[0])

    existing = fetch_profile(edit_id) if edit_id is not None else {}

    # use existing values if present, otherwise defaults
    with st.form("profile_form"):
        age = st.number_input(
            "Age", min_value=1, max_value=120, value=existing.get("age", 25)
        )
        st.subheader("Height")
        feet, inches = st.columns(2)
        with feet:
            heightFt = st.number_input(
                "Feet", min_value=1, max_value=8, value=existing.get("height_feet", 5)
            )
        with inches:
            heightIn = st.number_input(
                "Height (inches)", min_value=0, max_value=11, value=existing.get("height_inches", 0)
            )
        weight = st.number_input(
            "Weight (lbs)", min_value=40.0, max_value=1000.0, value=existing.get("weight", 40.0)
        )
        gender = st.selectbox(
            "Gender", ["Female", "Male", "Other"], index=["Female", "Male", "Other"].index(existing.get("gender", "Female"))
        )
        goal = st.selectbox(
            "Goal",
            ["weight_loss", "maintenance", "high_protein"],
            format_func=lambda x: x.replace("_"," ").title(),
            index=["weight_loss", "maintenance", "high_protein"].index(existing.get("goal", "weight_loss")),
        )
        dietary = st.multiselect(
            "Dietary Preferences",
            ["Vegetarian", "Vegan", "Pescaterian", "Low Carb", "Keto"],
            default=existing.get("dietary_preferences", []),
        )
        allergies = st.multiselect(
            "Allergies", ["Nuts", "Dairy", "Gluten", "Soy", "Eggs"], default=existing.get("allergies", []),
        )
        medical = st.multiselect(
            "Medical Conditions",
            ["Diabetes", "Hypertension", "Celiac", "High Cholesterol"],
            default=existing.get("medical_conditions", []),
        )
        budget = st.selectbox(
            "Weekly Grocery Budget",
            ["low", "medium", "high"],
            format_func=lambda x: x.title(),
            index=["low", "medium", "high"].index(existing.get("budget_level", "medium")),
        )
        cooking_time = st.selectbox(
            "Cooking Time",
            ["short", "medium", "long"],
            format_func=lambda x: x.title(),
            index=["short", "medium", "long"].index(existing.get("cooking_time", "short")),
        )

        submitted = st.form_submit_button("Submit Profile")

    if submitted:
        payload = {
            "age": int(age),
            "height_feet": int(heightFt),
            "height_inches": int(heightIn),
            "weight": float(weight),
            "gender": gender,
            "goal": goal,
            "dietary_preferences": dietary or [],
            "allergies": allergies or [],
            "medical_conditions": medical or [],
            "budget_level": budget,
            "cooking_time": cooking_time,
        }
        try:
            if edit_id is not None:
                r = requests.put(f"{API_URL}/{edit_id}", json=payload)
            else:
                r = requests.post(API_URL, json=payload)
            r.raise_for_status()
            msg = "updated" if edit_id is not None else "saved"
            st.success(f"Profile {msg} successfully!")
        except requests.exceptions.HTTPError as e:
            st.error(f"Failed to save profile: {e} - {r.text}")


def show_mealplan_page() -> None:
    st.title("Nutrition AI Agent — Meal Plan")

    profiles = fetch_profiles()
    if not profiles:
        st.info("No profiles available. Please create one first.")
        return

    # display select box with id and maybe age/goal
    options = [f"{p['id']} - {p.get('age')}yo {p.get('gender')}" for p in profiles]
    choice = st.selectbox("Choose profile", options)
    profile_id = int(choice.split(" ")[0])

    if st.button("Generate meal plan"):
        try:
            resp = requests.get(f"{API_URL}/{profile_id}/mealplan")
            resp.raise_for_status()
            data = resp.json()
            # cache the last generated mealplan so the Grocery tab can show it
            st.session_state["last_mealplan"] = data
            display_mealplan(data)
        except requests.RequestException as e:
            st.error(f"Failed to generate meal plan: {e}")


def display_mealplan(data: Dict[str, Any]) -> None:
    st.subheader("7‑Day Meal Plan")
    days = data.get("days", [])
    for day in days:
        st.markdown(f"**Day {day.get('day')}**")
        meals = day.get("meals", [])
        for m in meals:
            st.write(f"- {m.get('meal_type').capitalize()}: {m.get('title')}")


# ---------- main ------------------------------------------------------------

# use streamlit's native tabs for clean horizontal navigation
tab1, tab2, tab3 = st.tabs(["Create/Update Profile", "Meal Plan", "Grocery List"])

with tab1:
    show_profile_form()

with tab2:
    show_mealplan_page()

with tab3:
    # Grocery list tab: show last generated grocery or allow to fetch by profile
    def show_grocery_page() -> None:
        st.title("Nutrition AI Agent — Grocery List")

        # prefer existing session cached mealplan
        gp = st.session_state.get("last_mealplan")
        if gp:
            st.info("Showing grocery list from last generated meal plan")
            grocery = gp.get("grocery_list", [])
            if not grocery:
                st.write("No grocery items in last meal plan.")
                return
            for item in grocery:
                name = item.get("name")
                quantity = item.get("quantity")
                unit = item.get("unit")
                category = item.get("category")
                qty_text = str(quantity) if quantity is not None else ""
                unit_text = str(unit).strip() if unit not in (None, "", "null") else ""
                category_text = str(category).strip() if category not in (None, "", "null") else ""
                left = " ".join([x for x in [qty_text, unit_text] if x]).strip()
                if left:
                    line = f"- {name}: {left}"
                else:
                    line = f"- {name}"
                st.write(line)
            return

        # No manual fetch: prompt user to generate a meal plan in Meal Plan tab
        st.info("No generated meal plan cached. Go to the 'Meal Plan' tab and click 'Generate meal plan' to populate the grocery list.")
        return

    show_grocery_page()
