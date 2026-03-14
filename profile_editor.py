# profile_editor.py
import streamlit as st
import requests
from typing import Dict, Any, List

API_URL = "http://localhost:8000/profiles"
# Shows a prefilled profile form for the given username.
# If username exists in backend, fetches existing data.
def profile_form(prefilled_username: str = None) -> None:
    st.title("Profile Settings")
    if st.session_state.get("profile_updated_success"):
        st.success("Profile updated successfully.")
        st.session_state["profile_updated_success"] = False

    username = prefilled_username or st.text_input("Username", key="profile_username")
    if not username:
        st.info("Please enter a username")
        return

    existing = {}
    if prefilled_username:
        try:
            resp = requests.get(f"{API_URL}/{username}")
            if resp.status_code == 200:
                existing = resp.json()
        except requests.RequestException:
            st.warning("Could not fetch existing profile data")

    existing_budget = existing.get("budget_level", 0)
    try:
        budget_default = float(existing_budget or 0)
    except (TypeError, ValueError):
        budget_default = 0.0

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
                              index=gender_opts.index(existing.get("gender", "").capitalize())
                                    if existing.get("gender") else 0,
                              key="gender")

        goal_opts = ["", "weight loss", "maintenance", "high protein"]
        goal = st.selectbox("Goal", goal_opts,
                            index=goal_opts.index(existing.get("goal", "")) if existing.get("goal") else 0,
                            key="goal")

        dietary_opts = ["None", "Vegetarian", "Vegan", "Pescatarian", "Low Carb", "Keto"]
        allergies_opts = ["None", "Nuts", "Dairy", "Gluten", "Soy", "Eggs"]
        medical_opts = ["None", "Diabetes", "Hypertension", "Celiac", "High Cholesterol"]

        dietary = st.multiselect("Dietary Preferences", dietary_opts,
                                 default=existing.get("dietary_preferences", []), key="dietary")
        allergies_default = existing.get("allergies", [])
        if not allergies_default:
            allergies_default = ["None"]
        medical_default = existing.get("medical_conditions", [])
        if not medical_default:
            medical_default = ["None"]

        allergies = st.multiselect("Allergies", allergies_opts,
                                   default=allergies_default, key="allergies")
        medical = st.multiselect("Medical Conditions", medical_opts,
                                 default=medical_default, key="medical")

        budget = st.number_input("Weekly Grocery Budget ($)",
                                 min_value=0.0,
                                 max_value=10000.0,
                                 value=budget_default,
                                 step=1.0,
                                 format="%.2f",
                                 key="budget")

        cook_opts = ["", "short (<30 mins)", "medium (30-60 min)", "long (>60 mins)"]
        cooking_time = st.selectbox("Cooking Time", cook_opts,
                                    index=cook_opts.index(existing.get("cooking_time", "")) if existing.get("cooking_time") else 0,
                                    key="cooking_time")

        submitted = st.form_submit_button("Update Profile")

    if submitted:
        errors = []

        def parse_int(name: str, raw: str, min_val: int, max_val: int):
            value = (raw or "").strip()
            if not value:
                errors.append(f"{name} is required.")
                return None
            try:
                parsed = int(value)
            except ValueError:
                errors.append(f"{name} must be a whole number.")
                return None
            if parsed < min_val or parsed > max_val:
                errors.append(f"{name} must be between {min_val} and {max_val}.")
                return None
            return parsed

        def parse_float(name: str, raw: str, min_val: float, max_val: float):
            value = (raw or "").strip()
            if not value:
                errors.append(f"{name} is required.")
                return None
            try:
                parsed = float(value)
            except ValueError:
                errors.append(f"{name} must be a number.")
                return None
            if parsed < min_val or parsed > max_val:
                errors.append(f"{name} must be between {min_val} and {max_val}.")
                return None
            return parsed

        age_value = parse_int("Age", age, 1, 119)
        height_ft_value = parse_int("Height (feet)", heightFt, 1, 8)
        height_in_value = parse_int("Height (inches)", heightIn, 0, 11)
        weight_value = parse_float("Weight", weight, 40.0, 1000.0)

        if not gender:
            errors.append("Please select a gender.")
        if not goal:
            errors.append("Please select a goal.")
        if not cooking_time:
            errors.append("Please select a cooking time.")

        if errors:
            st.error("Please fix these fields before submitting:")
            for msg in errors:
                st.write(f"- {msg}")
            return

        def clean_list(lst):
            if not lst or "None" in lst:
                return []
            return lst

        payload = {
            "username": username,
            "age": age_value,
            "height_feet": height_ft_value,
            "height_inches": height_in_value,
            "weight": weight_value,
            "gender": gender.lower() if gender else None,
            "goal": goal or None,
            "dietary_preferences": clean_list(dietary),
            "allergies": clean_list(allergies),
            "medical_conditions": clean_list(medical),
            "budget_level": float(budget),
            "cooking_time": cooking_time or None,
        }

        try:
            if existing:
                r = requests.put(f"{API_URL}/{username}", json=payload)
            else:
                r = requests.post(API_URL, json=payload)
            r.raise_for_status()
            st.session_state["profile_updated_success"] = True
            st.session_state["logged_in_user"] = username
            st.session_state["needs_plan_refresh"] = True
            st.session_state["is_first_plan_generation"] = False
            st.session_state["last_mealplan"] = None
            st.session_state["last_mealplan_user"] = None
            st.session_state["active_page"] = "meal"
            st.rerun()
        except requests.exceptions.HTTPError as e:
            st.error(f"Failed to save profile: {e} - {r.text}")
