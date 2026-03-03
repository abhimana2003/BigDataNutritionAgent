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
        # use text inputs for numeric fields so that the boxes start empty
        age = st.text_input("Age", value=str(existing.get("age", "")))
        st.subheader("Height")
        feet, inches = st.columns(2)
        with feet:
            heightFt = st.text_input("Feet", value=str(existing.get("height_feet", "")))
        with inches:
            heightIn = st.text_input("Height (inches)", value=str(existing.get("height_inches", "")))
        weight = st.text_input("Weight (lbs)", value=str(existing.get("weight", "")))
        gender_opts = ["", "Female", "Male", "Other"]
        gender = st.selectbox(
            "Gender", gender_opts,
            index=gender_opts.index(existing.get("gender", "")),
            key=f"gender_{edit_id}",
        )
        goal_opts = ["", "weight_loss", "maintenance", "high_protein"]
        goal = st.selectbox(
            "Goal",
            goal_opts,
            format_func=lambda x: x.replace("_", " ").title() if x else "",
            index=goal_opts.index(existing.get("goal", "")),
            key=f"goal_{edit_id}",
        )
        # dietary/allergy/medical multiselects include an explicit "None"
        # entry so a user without any restrictions can choose it.  When the
        # form is submitted we convert "None" back to an empty list.
        # keep the "None" choice available but do not preselect it when the
        # profile is new; an empty list means no restrictions.
        dietary_opts = ["None", "Vegetarian", "Vegan", "Pescaterian", "Low Carb", "Keto"]
        allergies_opts = ["None", "Nuts", "Dairy", "Gluten", "Soy", "Eggs"]
        medical_opts = ["None", "Diabetes", "Hypertension", "Celiac", "High Cholesterol"]

        dietary = st.multiselect(
            "Dietary Preferences",
            dietary_opts,
            default=existing.get("dietary_preferences", []),
            key=f"dietary_{edit_id}",
        )
        allergies = st.multiselect(
            "Allergies", allergies_opts, default=existing.get("allergies", []),
            key=f"allergies_{edit_id}",
        )
        medical = st.multiselect(
            "Medical Conditions",
            medical_opts,
            default=existing.get("medical_conditions", []),
            key=f"medical_{edit_id}",
        )

        # display meaningful labels for budget and cooking time while still
        # storing the canonical low/medium/high values in the database
        budget_values = ["", "low", "medium", "high"]
        # updated ranges to reflect larger weekly budgets
        budget_labels = {"low": "$0-200", "medium": "$200-400", "high": "$400-600"}
        current_budget = existing.get("budget_level", "")
        if current_budget not in budget_values:
            current_budget = ""
        budget = st.selectbox(
            "Weekly Grocery Budget",
            budget_values,
            format_func=lambda x: budget_labels.get(x, x.title()),
            index=budget_values.index(current_budget),
            key=f"budget_{edit_id}",
        )

        cook_values = ["", "short", "medium", "long"]
        cook_labels = {"short": "<30 min", "medium": "30-60 min", "long": ">60 min"}
        current_cook = existing.get("cooking_time", "")
        if current_cook not in cook_values:
            current_cook = ""
        cooking_time = st.selectbox(
            "Cooking Time",
            cook_values,
            format_func=lambda x: cook_labels.get(x, x.title()),
            index=cook_values.index(current_cook),
            key=f"cooking_{edit_id}",
        )

        submitted = st.form_submit_button("Submit Profile")

    if submitted:
        # convert any "None" selections back into empty lists before sending
        def clean_list(lst):
            if not lst or "None" in lst:
                return []
            return lst

        # convert numeric strings, allow blank -> 0 or None if desired
        def to_int(s, default=None):
            try:
                return int(s)
            except Exception:
                return default

        def to_float(s, default=None):
            try:
                return float(s)
            except Exception:
                return default

        payload = {
            "age": to_int(age),
            "height_feet": to_int(heightFt),
            "height_inches": to_int(heightIn),
            "weight": to_float(weight),
            "gender": gender or None,
            "goal": goal or None,
            "dietary_preferences": clean_list(dietary),
            "allergies": clean_list(allergies),
            "medical_conditions": clean_list(medical),
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
                st.write(f"- {name}")
            return

        # No manual fetch: prompt user to generate a meal plan in Meal Plan tab
        st.info("No generated meal plan cached. Go to the 'Meal Plan' tab and click 'Generate meal plan' to populate the grocery list.")
        return

    show_grocery_page()
