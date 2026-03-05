import streamlit as st
import requests
from typing import List, Dict, Any
from profile_editor import profile_form

API_URL = "http://localhost:8000/profiles"

# Helper functions
def fetch_profiles() -> List[Dict[str, Any]]:
    try:
        resp = requests.get(API_URL)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        st.error(f"Unable to load profiles: {e}")
        return []

def fetch_profile(username: str) -> Dict[str, Any]:
    try:
        resp = requests.get(f"{API_URL}/{username}")
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return {}

# Profile Form
def show_profile_form(prefilled_username=None) -> None:
    st.title("Nutrition AI Agent — Profile Settings")

    username = prefilled_username or st.text_input("Username", key="profile_username")

    if not username:
        st.info("Please enter a username")
        return

    edit_id = None
    existing = {}  

    with st.form("profile_form"):
        age = st.text_input("Age", value=str(existing.get("age", "")), key="age")
        st.subheader("Height")
        feet, inches = st.columns(2)
        with feet:
            heightFt = st.text_input("Feet", value=str(existing.get("height_feet", "")), key="height_feet")
        with inches:
            heightIn = st.text_input("Height (inches)", value=str(existing.get("height_inches", "")), key="height_inches")
        weight = st.text_input("Weight (lbs)", value=str(existing.get("weight", "")), key="weight")

        gender_opts = ["", "Female", "Male", "Other"]
        gender = st.selectbox("Gender", gender_opts,
                              index=gender_opts.index(existing.get("gender", "")) if existing.get("gender") else 0,
                              key="gender")

        goal_opts = ["", "weight loss", "maintenance", "high protein"]
        goal = st.selectbox("Goal", goal_opts,
                            index=goal_opts.index(existing.get("goal", "")) if existing.get("goal") else 0,
                            key="goal")

        dietary_opts = ["None", "Vegetarian", "Vegan", "Pescaterian", "Low Carb", "Keto"]
        allergies_opts = ["None", "Nuts", "Dairy", "Gluten", "Soy", "Eggs"]
        medical_opts = ["None", "Diabetes", "Hypertension", "Celiac", "High Cholesterol"]

        dietary = st.multiselect("Dietary Preferences", dietary_opts,
                                 default=existing.get("dietary_preferences", []), key="dietary")
        allergies = st.multiselect("Allergies", allergies_opts,
                                   default=existing.get("allergies", []), key="allergies")
        medical = st.multiselect("Medical Conditions", medical_opts,
                                 default=existing.get("medical_conditions", []), key="medical")

        # Budget input as float
        budget = st.number_input("Weekly Grocery Budget ($)",
                                 min_value=0.0,
                                 max_value=10000.0,
                                 value=float(existing.get("budget_level", 0) or 0),
                                 step=1.0,
                                 format="%.2f",
                                 key="budget")

        cook_opts = ["", "short (<30 mins)", "medium (30-60 min)", "long (>60 mins)"]
        cooking_time = st.selectbox("Cooking Time", cook_opts,
                                    index=cook_opts.index(existing.get("cooking_time", "")) if existing.get("cooking_time") else 0,
                                    key="cooking_time")

        submitted = st.form_submit_button("Submit Profile")

    if submitted:
        def clean_list(lst):
            if not lst or "None" in lst:
                return []
            return lst

        payload = {
            "username": username,
            "age": int(age) if age else None,
            "height_feet": int(heightFt) if heightFt else None,
            "height_inches": int(heightIn) if heightIn else None,
            "weight": float(weight) if weight else None,
            "gender": gender.lower() if gender else None,
            "goal": goal or None,
            "dietary_preferences": clean_list(dietary),
            "allergies": clean_list(allergies),
            "medical_conditions": clean_list(medical),
            "budget_level": float(budget),
            "cooking_time": cooking_time or None,
        }

        try:
            if edit_id is not None:
                r = requests.put(f"{API_URL}/{edit_id}", json=payload)
            else:
                r = requests.post(API_URL, json=payload)
            r.raise_for_status()
            st.success("Profile successfully created!")

            # Set session state to show tabs after creation
            st.session_state["logged_in_user"] = username
            st.session_state["creating_profile"] = False
            st.session_state["active_page"] = "Meal Plan"
            st.rerun()

        except requests.exceptions.HTTPError as e:
            st.error(f"Failed to save profile: {e} - {r.text}")

# Login Page
def show_login_page():
    st.title("Nutrition AI Agent Login")
    username = st.text_input("Username", key="login_username")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Log In"):
            try:
                res = requests.get(f"{API_URL}/{username}")
                if res.status_code == 200:
                    st.session_state["logged_in_user"] = username
                    st.session_state["active_page"] = "Meal Plan"
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error("User not found")
            except requests.RequestException:
                st.error("Server error")

    with col2:
        if st.button("Create New Profile"):
            st.session_state["creating_profile"] = True
            st.session_state["new_username"] = username
            st.rerun()

# Meal Plan Page
def show_mealplan_page() -> None:
    st.title("Nutrition AI Agent — Meal Plan")

    username = st.session_state.get("logged_in_user")
    if not username:
        st.info("Please log in first")
        return

    if st.button("Generate meal plan"):
        try:
            resp = requests.get(f"{API_URL}/{username}/mealplan")
            resp.raise_for_status()
            data = resp.json()
            st.session_state["last_mealplan"] = data
            display_mealplan(data)
        except requests.RequestException as e:
            st.error(f"Failed to generate meal plan: {e}")

def display_mealplan(data: Dict[str, Any]) -> None:
    st.subheader("7‑Day Meal Plan")
    for day in data.get("days", []):
        st.markdown(f"**Day {day.get('day')}**")
        for m in day.get("meals", []):
            st.write(f"- {m.get('meal_type').capitalize()}: {m.get('title')}")

# Grocery Page
def show_grocery_page() -> None:
    st.title("Nutrition AI Agent — Grocery List")
    gp = st.session_state.get("last_mealplan")
    if not gp:
        st.info("No generated meal plan cached. Go to the 'Meal Plan' tab and click 'Generate meal plan'.")
        return
    grocery = gp.get("grocery_list", [])
    text = gp.get("grocery_text")
    if text:
        st.markdown(text)
        return
    if not grocery:
        st.write("No grocery items in last meal plan.")
        return
    for item in grocery:
        name = item.get("name")
        quantity = item.get("quantity")
        unit = item.get("unit")
        parts = []
        if quantity is not None:
            parts.append(str(int(quantity)) if isinstance(quantity, float) and quantity.is_integer() else str(quantity))
        if unit:
            parts.append(str(unit))
        if name:
            parts.append(str(name))
        if parts:
            st.write(f"- {' '.join(parts)}")

# main app flow
if "logged_in_user" not in st.session_state:
    st.session_state["logged_in_user"] = None
if "creating_profile" not in st.session_state:
    st.session_state["creating_profile"] = False
if "new_username" not in st.session_state:
    st.session_state["new_username"] = None
if "show_tabs" not in st.session_state:
    st.session_state["show_tabs"] = False  # controls whether to show the 3 tabs

# If user not logged in or creating profile, show login/profile page
if not st.session_state["logged_in_user"] or st.session_state["creating_profile"]:
    if st.session_state["creating_profile"]:
        show_profile_form(prefilled_username=st.session_state["new_username"])
    else:
        show_login_page()
else:
    # User is logged in and not creating profile: show tabs
    st.session_state["show_tabs"] = True

if st.session_state.get("show_tabs"):
    # Navigation control
    if "active_page" not in st.session_state:
        st.session_state["active_page"] = "Meal Plan"

    page = st.radio(
        "Navigation",
        ["Profile Settings", "Meal Plan", "Grocery List"],
        index=["Profile Settings", "Meal Plan", "Grocery List"].index(st.session_state["active_page"]),
        horizontal=True
    )
    
    st.session_state["active_page"] = page

    if page == "Profile Settings":
        profile_form(prefilled_username=st.session_state.get("logged_in_user"))
    elif page == "Meal Plan":
        show_mealplan_page()
    elif page == "Grocery List":
        show_grocery_page()