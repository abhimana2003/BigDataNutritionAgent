# profile_editor.py
import streamlit as st
import requests
from typing import Dict, Any

API_URL = "http://localhost:8000/profiles"

def profile_form(prefilled_username: str = None) -> None:
    """
    Shows a prefilled profile form for the given username.
    If username exists in backend, fetches existing data.
    """
    st.subheader("Profile Settings")

    username = prefilled_username or st.text_input("Username", key="profile_username")
    if not username:
        st.info("Please enter a username")
        return

    existing: Dict[str, Any] = {}
    if prefilled_username:
        try:
            resp = requests.get(f"{API_URL}/{username}")
            if resp.status_code == 200:
                existing = resp.json()
        except requests.RequestException:
            st.warning("Could not fetch existing profile data")

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

        dietary_opts = ["None", "Vegetarian", "Vegan", "Pescaterian", "Low Carb", "Keto"]
        allergies_opts = ["None", "Nuts", "Dairy", "Gluten", "Soy", "Eggs"]
        medical_opts = ["None", "Diabetes", "Hypertension", "Celiac", "High Cholesterol"]

        dietary = st.multiselect("Dietary Preferences", dietary_opts,
                                 default=existing.get("dietary_preferences", []), key="dietary")
        allergies = st.multiselect("Allergies", allergies_opts,
                                   default=existing.get("allergies", []), key="allergies")
        medical = st.multiselect("Medical Conditions", medical_opts,
                                 default=existing.get("medical_conditions", []), key="medical")

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
            if existing:
                r = requests.put(f"{API_URL}/{username}", json=payload)
            else:
                r = requests.post(API_URL, json=payload)
            r.raise_for_status()
            st.success("Profile saved successfully!")
            st.session_state["logged_in_user"] = username
            st.session_state["active_page"] = "Meal Plan"
            st.rerun()
        except requests.exceptions.HTTPError as e:
            st.error(f"Failed to save profile: {e} - {r.text}")