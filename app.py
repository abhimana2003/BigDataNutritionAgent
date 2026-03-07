import streamlit as st
import requests
from typing import List, Dict, Any
from html import escape
from profile_editor import profile_form

API_URL = "http://localhost:8000/profiles"
AUTH_URL = "http://localhost:8000/auth/login"
RECIPE_URL = "http://localhost:8000/recipes"

NAV_LABELS = {
    "profile": "✏️ Profile Settings",
    "meal": "🍽️ Meal Plan",
    "grocery": "🛒 Grocery List",
    "recipe": "📖 Recipe Details",
}

LEGACY_PAGE_KEYS = {
    "Profile Settings": "profile",
    "Meal Plan": "meal",
    "Grocery List": "grocery",
    "Recipe Details": "recipe",
}

st.set_page_config(page_title="Nutrition AI Agent", layout="wide")


def apply_warm_theme() -> None:
    st.markdown(
        """
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Source+Sans+3:wght@400;600;700&display=swap');

          :root {
            --bg: #f5efe3;
            --panel: #fff9f1;
            --panel-2: #f8eddd;
            --text: #5b3f2a;
            --muted: #7a654f;
            --line: #ead1b6;
            --accent: #f08a24;
            --accent-dark: #d77517;
          }

          html, body, [class*="stApp"] {
            color-scheme: light;
          }

          .stApp {
            background: linear-gradient(180deg, var(--bg) 0%, #fff9f2 100%);
            color: var(--text);
            font-family: "Source Sans 3", sans-serif;
          }

          [data-testid="stHeader"],
          [data-testid="stToolbar"],
          [data-testid="stDecoration"],
          [data-testid="stStatusWidget"] {
            background: transparent;
          }

          .main .block-container {
            max-width: none;
            width: 100%;
            margin-top: 1.25rem;
            margin-bottom: 2rem;
            padding: 2rem 2.2rem 1.5rem;
            border-radius: 24px;
            border: 1px solid var(--line);
            background: linear-gradient(180deg, #fffaf2 0%, var(--panel-2) 100%);
            box-shadow: 0 18px 34px rgba(52, 35, 20, 0.08);
          }

          h1, h2, h3, h4 {
            color: var(--text) !important;
            font-family: "Playfair Display", Georgia, serif !important;
            letter-spacing: 0.2px;
          }

          p, label, .stMarkdown, .stText, .stCaption {
            color: var(--muted) !important;
          }

          .stTextInput > label,
          .stNumberInput > label,
          .stSelectbox > label,
          .stMultiSelect > label {
            color: var(--text) !important;
            font-weight: 700 !important;
          }

          div[data-baseweb="input"] > div,
          div[data-baseweb="base-input"] > div,
          div[data-baseweb="select"] > div {
            background: var(--panel) !important;
            border: 1px solid var(--line) !important;
            border-radius: 12px !important;
            color: var(--text) !important;
          }

          .stTextInput input,
          .stNumberInput input,
          .stSelectbox input,
          .stMultiSelect input,
          .stTextArea textarea {
            color: var(--text) !important;
            -webkit-text-fill-color: var(--text) !important;
            caret-color: var(--text) !important;
          }

          div[data-baseweb="input"] > div:focus-within,
          div[data-baseweb="base-input"] > div:focus-within,
          div[data-baseweb="select"] > div:focus-within {
            border-color: #e7b47b !important;
            box-shadow: 0 0 0 2px rgba(240, 138, 36, 0.15) !important;
          }

          div[data-baseweb="tag"] {
            background: #ffe2c1 !important;
            color: #6f441b !important;
            border: 1px solid #e7b47b !important;
          }

          div[data-baseweb="tag"] * {
            color: #6f441b !important;
            fill: #6f441b !important;
          }

          div[data-baseweb="popover"] {
            background: var(--panel) !important;
            border: 1px solid var(--line) !important;
          }

          div[data-baseweb="popover"] ul,
          div[data-baseweb="popover"] li,
          div[data-baseweb="menu"],
          div[data-baseweb="menu"] > div {
            background: var(--panel) !important;
            color: var(--text) !important;
          }

          div[data-baseweb="popover"] li:hover,
          div[data-baseweb="popover"] li[aria-selected="true"] {
            background: #ffeed7 !important;
          }

          [role="listbox"],
          [role="option"] {
            background: var(--panel) !important;
            color: var(--text) !important;
          }

          [role="option"][aria-selected="true"],
          [role="option"]:hover {
            background: #ffeed7 !important;
          }

          .stButton > button,
          .stFormSubmitButton > button {
            border-radius: 999px !important;
            border: none !important;
            color: #ffffff !important;
            font-weight: 700 !important;
            background: linear-gradient(180deg, var(--accent), var(--accent-dark)) !important;
            box-shadow: 0 8px 14px rgba(240, 138, 36, 0.25) !important;
          }

          .stButton > button[kind="secondary"] {
            background: #fff8ec !important;
            color: #7b624a !important;
            border: 1px solid #e6d5bc !important;
            box-shadow: none !important;
          }

          .stButton > button[kind="secondary"]:hover {
            border-color: #d8bea0 !important;
            background: #fff4e3 !important;
          }

          .stRadio [role="radiogroup"] {
            gap: 0.35rem;
            padding: 0.3rem;
            border-radius: 999px;
            background: #fff6ea;
            border: 1px solid var(--line);
          }

          .stRadio [role="radio"] {
            border-radius: 999px !important;
            color: var(--text) !important;
          }

          .stInfo, .stSuccess, .stWarning, .stError {
            border-radius: 12px;
            border: 1px solid var(--line);
          }

          [data-testid="stForm"] {
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 0.75rem 0.75rem 0.3rem;
            background: rgba(255, 249, 241, 0.6);
          }

          .daily-meals-title {
            font-family: "Playfair Display", Georgia, serif;
            font-size: 2rem;
            color: var(--text);
            margin-bottom: 0.4rem;
          }

          .daily-meal-card {
            background: linear-gradient(180deg, #fffdf8 0%, #fff8ee 100%);
            border: 1px solid #efe1cc;
            border-radius: 20px;
            padding: 0.9rem 1rem 0.8rem;
            box-shadow: 0 10px 18px rgba(79, 52, 24, 0.08);
            margin-bottom: 0.75rem;
          }

          .meal-type-title {
            font-family: "Playfair Display", Georgia, serif;
            font-size: 2rem;
            line-height: 1.05;
            color: #4f331e;
            margin: 0;
          }

          .meal-name {
            font-size: 1.95rem;
            line-height: 1.2;
            color: #4e4034;
            font-weight: 600;
            margin: 0.25rem 0 0.3rem;
          }

          .meal-cal-pill {
            display: inline-block;
            background: #f2ebdc;
            color: #6e5b48;
            border-radius: 999px;
            padding: 0.18rem 0.7rem;
            font-size: 1.25rem;
            font-weight: 700;
          }

          .meal-action-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin-top: 0.7rem;
          }

          .meal-action-chip {
            background: #fff8ec;
            border: 1px solid #e6d5bc;
            border-radius: 12px;
            color: #7b624a;
            font-size: 1.15rem;
            font-weight: 700;
            padding: 0.16rem 0.7rem;
          }

          .meal-thumb-wrap img {
            border-radius: 18px !important;
            box-shadow: 0 8px 16px rgba(64, 42, 21, 0.14);
          }

          .grocery-preview-card {
            background: linear-gradient(180deg, #fffdf9 0%, #fff7eb 100%);
            border: 1px solid #efe1cc;
            border-radius: 20px;
            box-shadow: 0 10px 18px rgba(79, 52, 24, 0.08);
            margin-top: 0.6rem;
            overflow: hidden;
          }

          .grocery-preview-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.85rem 1rem 0.6rem;
            border-bottom: 1px solid #eee1cd;
            background: #fff8ef;
          }

          .grocery-preview-title {
            font-family: "Playfair Display", Georgia, serif;
            font-size: 2rem;
            color: #4f331e;
            margin: 0;
          }

          .grocery-view-label {
            font-size: 1.2rem;
            color: #9a8167;
            font-weight: 700;
          }

          .grocery-preview-body {
            padding: 0.75rem 1rem 0.85rem;
          }

          .grocery-item {
            font-size: 1.55rem;
            color: #5a4a39;
            margin: 0.18rem 0;
            display: flex;
            align-items: center;
            gap: 0.48rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


apply_warm_theme()

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


def fetch_recipe(recipe_id: int, show_error: bool = True) -> Dict[str, Any]:
    cache = st.session_state.get("recipe_cache", {})
    if recipe_id in cache:
        return cache[recipe_id]
    try:
        resp = requests.get(f"{RECIPE_URL}/{recipe_id}")
        resp.raise_for_status()
        data = resp.json()
        cache[recipe_id] = data
        st.session_state["recipe_cache"] = cache
        return data
    except requests.RequestException as e:
        if show_error:
            st.error(f"Unable to load recipe details: {e}")
        return {}


def submit_feedback(username: str, recipe_id: int, action: str) -> bool:
    try:
        resp = requests.post(
            f"{API_URL}/{username}/feedback",
            json={"username": username, "recipe_id": recipe_id, "action": action},
            timeout=20,
        )
        if resp.status_code == 200:
            return True
        detail = resp.json().get("detail", "Unknown error")
        st.error(f"Feedback failed: {detail}")
        return False
    except requests.RequestException as e:
        st.error(f"Feedback request failed: {e}")
        return False


def request_replacement(
    username: str,
    day: int,
    meal_type: str,
    current_recipe_id: int,
    exclude_recipe_ids: List[int],
) -> Dict[str, Any]:
    try:
        resp = requests.post(
            f"{API_URL}/{username}/replace-meal",
            json={
                "day": day,
                "meal_type": meal_type,
                "current_recipe_id": current_recipe_id,
                "exclude_recipe_ids": exclude_recipe_ids,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()
        detail = resp.json().get("detail", "Unknown error")
        st.error(f"Replacement failed: {detail}")
        return {}
    except requests.RequestException as e:
        st.error(f"Replacement request failed: {e}")
        return {}


def _meal_calories(meal: Dict[str, Any]) -> int:
    nutrition = meal.get("meal_nutrition") or {}
    value = nutrition.get("daily_calories")
    if value is None:
        return 0
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def _grocery_icon(item_name: str) -> str:
    name = (item_name or "").lower()
    if any(k in name for k in ["egg"]):
        return "🥚"
    if any(k in name for k in ["spinach", "lettuce", "kale", "greens"]):
        return "🥬"
    if any(k in name for k in ["chicken", "beef", "turkey", "fish", "salmon"]):
        return "🍗"
    if any(k in name for k in ["zucchini", "cucumber"]):
        return "🥒"
    if any(k in name for k in ["oil"]):
        return "🫒"
    if any(k in name for k in ["tomato", "pepper"]):
        return "🍅"
    if any(k in name for k in ["rice", "bread", "pasta"]):
        return "🍞"
    return "🥣"


def _render_grocery_preview(data: Dict[str, Any]) -> None:
    items = data.get("grocery_list") or []
    if not items:
        return

    st.markdown(
        """
        <div class="grocery-preview-card">
          <div class="grocery-preview-head">
            <h3 class="grocery-preview-title">Grocery List Preview</h3>
            <span class="grocery-view-label">View List</span>
          </div>
          <div class="grocery-preview-body">
        """,
        unsafe_allow_html=True,
    )

    preview = items[:6]
    left_items = preview[:3]
    right_items = preview[3:6]
    col_left, col_right = st.columns(2)

    with col_left:
        for item in left_items:
            name = str(item.get("name", "")).strip()
            qty = item.get("quantity")
            unit = item.get("unit")
            qty_text = ""
            if qty is not None:
                qty_text += str(int(qty) if isinstance(qty, float) and qty.is_integer() else qty)
            if unit:
                qty_text = (qty_text + f" {unit}").strip()
            label = f"{qty_text} {name}".strip()
            st.markdown(
                f"<div class='grocery-item'><span>{_grocery_icon(name)}</span><span>{label}</span></div>",
                unsafe_allow_html=True,
            )

    with col_right:
        for item in right_items:
            name = str(item.get("name", "")).strip()
            qty = item.get("quantity")
            unit = item.get("unit")
            qty_text = ""
            if qty is not None:
                qty_text += str(int(qty) if isinstance(qty, float) and qty.is_integer() else qty)
            if unit:
                qty_text = (qty_text + f" {unit}").strip()
            label = f"{qty_text} {name}".strip()
            st.markdown(
                f"<div class='grocery-item'><span>{_grocery_icon(name)}</span><span>{label}</span></div>",
                unsafe_allow_html=True,
            )

    st.markdown("</div></div>", unsafe_allow_html=True)

# Profile Form
def show_profile_form(prefilled_username=None) -> None:
    st.title("Create Your Profile")

    default_username = prefilled_username or ""
    username = st.text_input("Username", value=default_username, key="profile_username_create")
    full_name = st.text_input("Full Name", key="profile_full_name_create")
    email = st.text_input("Email", key="profile_email_create")
    password = st.text_input("Password", type="password", key="profile_password_create")

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
        errors: List[str] = []

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
        if len(username.strip()) < 3:
            errors.append("Username must be at least 3 characters.")
        if email and "@" not in email:
            errors.append("Email must include '@'.")
        if not password or len(password) < 8:
            errors.append("Password must be at least 8 characters.")

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
            "username": username.strip(),
            "email": email.strip() or None,
            "full_name": full_name.strip() or None,
            "password": password,
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
            if edit_id is not None:
                r = requests.put(f"{API_URL}/{edit_id}", json=payload)
            else:
                r = requests.post(API_URL, json=payload)
            r.raise_for_status()
            st.success("Profile successfully created!")

            # Set session state to show tabs after creation
            st.session_state["logged_in_user"] = username.strip()
            st.session_state["creating_profile"] = False
            st.session_state["active_page"] = "meal"
            st.session_state["needs_plan_refresh"] = True
            st.session_state["last_mealplan"] = None
            st.session_state["last_mealplan_user"] = None
            st.rerun()

        except requests.exceptions.HTTPError as e:
            st.error(f"Failed to save profile: {e} - {r.text}")

# Login Page
def show_login_page():
    st.title("Nutrition AI Agent Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Log In"):
            try:
                if not username or not password:
                    st.error("Please enter both username and password.")
                    return
                res = requests.post(AUTH_URL, json={"username": username, "password": password})
                if res.status_code == 200:
                    st.session_state["logged_in_user"] = username.strip()
                    st.session_state["active_page"] = "meal"
                    st.session_state["needs_plan_refresh"] = True
                    st.session_state["last_mealplan"] = None
                    st.session_state["last_mealplan_user"] = None
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
            except requests.RequestException:
                st.error("Server error")

    with col2:
        if st.button("Create New Profile"):
            st.session_state["creating_profile"] = True
            st.session_state["new_username"] = username.strip()
            st.rerun()

# Meal Plan Page
def show_mealplan_page() -> None:
    st.title("Nutrition AI Agent — Meal Plan")

    username = st.session_state.get("logged_in_user")
    if not username:
        st.info("Please log in first")
        return

    cached = st.session_state.get("last_mealplan")
    cached_user = st.session_state.get("last_mealplan_user")
    needs_refresh = st.session_state.get("needs_plan_refresh", False)

    if needs_refresh or not cached or cached_user != username:
        try:
            resp = requests.get(f"{API_URL}/{username}/mealplan")
            resp.raise_for_status()
            data = resp.json()
            st.session_state["last_mealplan"] = data
            st.session_state["last_mealplan_user"] = username
            st.session_state["needs_plan_refresh"] = False
        except requests.RequestException as e:
            st.error(f"Failed to generate meal plan: {e}")

    cached = st.session_state.get("last_mealplan")
    if cached:
        display_mealplan(cached)

def display_mealplan(data: Dict[str, Any]) -> None:
    days = data.get("days", [])
    if not days:
        st.info("No meal plan data available yet.")
        return

    st.markdown('<div class="daily-meals-title">Daily Meals</div>', unsafe_allow_html=True)
    day_numbers = [int(day.get("day")) for day in days if day.get("day") is not None]
    selected_day = st.radio(
        "Day",
        day_numbers,
        horizontal=True,
        key="selected_day",
        label_visibility="collapsed",
    )
    day_data = next((d for d in days if int(d.get("day", -1)) == int(selected_day)), days[0])

    for idx, meal in enumerate(day_data.get("meals", [])):
        meal_type = str(meal.get("meal_type", "")).capitalize()
        title = meal.get("title", "Untitled meal")
        recipe_id = meal.get("recipe_id")
        calories = _meal_calories(meal)
        detail = fetch_recipe(int(recipe_id), show_error=False) if recipe_id is not None else {}
        image_url = detail.get("image_url")
        image_html = ""
        if image_url:
            image_html = (
                '<div class="meal-thumb-wrap">'
                f'<img src="{escape(image_url)}" alt="{escape(title)}" width="190" />'
                "</div>"
            )

        cal_text = f"{calories} cal" if calories > 0 else "Meal"
        st.markdown(
            f"""
            <div class="daily-meal-card">
              <div style="display:flex; justify-content:space-between; gap:0.9rem; align-items:center;">
                <div style="flex:1; min-width:0;">
                  <h3 class="meal-type-title">{escape(meal_type)}</h3>
                  <p class="meal-name">{escape(title)}</p>
                  <span class="meal-cal-pill">{escape(cal_text)}</span>
                </div>
                <div>{image_html}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        act_like, act_replace, act_dislike, act_open = st.columns([1, 1.1, 1.2, 1.4])

        with act_like:
            if st.button("Like", key=f"meal_like_{selected_day}_{idx}_{recipe_id}", type="secondary"):
                if recipe_id is None:
                    st.error("Cannot like a meal without recipe id.")
                elif submit_feedback(st.session_state.get("logged_in_user"), int(recipe_id), "like"):
                    st.success("Saved. Future plans will lean toward similar recipes.")

        with act_replace:
            if st.button("Replace", key=f"meal_replace_{selected_day}_{idx}_{recipe_id}", type="secondary"):
                if recipe_id is None:
                    st.error("Cannot replace a meal without recipe id.")
                else:
                    exclude_ids = [
                        int(m.get("recipe_id"))
                        for m in day_data.get("meals", [])
                        if m.get("recipe_id") is not None
                    ]
                    replacement = request_replacement(
                        username=st.session_state.get("logged_in_user"),
                        day=int(selected_day),
                        meal_type=str(meal.get("meal_type", "")),
                        current_recipe_id=int(recipe_id),
                        exclude_recipe_ids=exclude_ids,
                    )
                    new_meal = replacement.get("meal")
                    if new_meal:
                        meal.update(new_meal)
                        st.session_state["last_mealplan"] = data
                        st.success("Replaced with a same-category recipe tuned to your likes.")
                        st.rerun()

        with act_dislike:
            if st.button("Doesn't Fit", key=f"meal_dislike_{selected_day}_{idx}_{recipe_id}", type="secondary"):
                if recipe_id is None:
                    st.error("Cannot submit feedback without recipe id.")
                elif submit_feedback(st.session_state.get("logged_in_user"), int(recipe_id), "dislike"):
                    st.success("Saved. We'll avoid similar options.")

        with act_open:
            view_label = f"Open Recipe #{recipe_id}" if recipe_id is not None else "Open Recipe"
            if st.button(view_label, key=f"recipe_open_{selected_day}_{idx}_{recipe_id}", type="secondary"):
                if recipe_id is None:
                    st.error("This meal is missing a recipe id.")
                else:
                        detail = fetch_recipe(int(recipe_id), show_error=True)
                        if detail:
                            st.session_state["selected_recipe"] = detail
                            st.session_state["active_page"] = "recipe"
                            st.rerun()

    _render_grocery_preview(data)


def show_recipe_details_page() -> None:
    st.title("Recipe Instructions")
    detail = st.session_state.get("selected_recipe")
    if not detail:
        st.info("Select a meal from 'Meal Plan' and click Open.")
        if st.button("Back to Meal Plan"):
            st.session_state["active_page"] = "meal"
            st.rerun()
        return

    st.subheader(detail.get("title", "Recipe"))
    image_url = detail.get("image_url")
    if image_url:
        st.image(image_url, width=360)

    meta_parts = []
    if detail.get("prep_time") is not None:
        meta_parts.append(f"Prep: {detail['prep_time']} min")
    if detail.get("cook_time") is not None:
        meta_parts.append(f"Cook: {detail['cook_time']} min")
    if detail.get("total_time") is not None:
        meta_parts.append(f"Total: {detail['total_time']} min")
    if detail.get("servings") is not None:
        meta_parts.append(f"Servings: {detail['servings']}")
    if meta_parts:
        st.caption(" | ".join(meta_parts))

    if detail.get("url"):
        st.markdown(f"[Open Source Recipe]({detail['url']})")

    st.markdown("**Ingredients**")
    ingredients = detail.get("ingredients", [])
    if ingredients:
        for item in ingredients:
            st.write(f"- {item}")
    else:
        st.write("No ingredient list available.")

    st.markdown("**Instructions**")
    directions = detail.get("directions", [])
    if directions:
        for i, step in enumerate(directions, start=1):
            st.write(f"{i}. {step}")
    else:
        st.info("No step-by-step instructions available for this recipe in the current dataset.")

    if st.button("Back to Meal Plan"):
        st.session_state["active_page"] = "meal"
        st.rerun()

# Grocery Page
def show_grocery_page() -> None:
    st.title("Nutrition AI Agent — Grocery List")
    gp = st.session_state.get("last_mealplan")
    if not gp:
        st.info("No generated meal plan is available yet. Open the Meal Plan tab to load one.")
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
if "selected_recipe" not in st.session_state:
    st.session_state["selected_recipe"] = None
if "recipe_cache" not in st.session_state:
    st.session_state["recipe_cache"] = {}
if "needs_plan_refresh" not in st.session_state:
    st.session_state["needs_plan_refresh"] = False
if "last_mealplan_user" not in st.session_state:
    st.session_state["last_mealplan_user"] = None

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
        st.session_state["active_page"] = "meal"

    if st.session_state["active_page"] in LEGACY_PAGE_KEYS:
        st.session_state["active_page"] = LEGACY_PAGE_KEYS[st.session_state["active_page"]]

    page_keys = ["profile", "meal", "grocery"]
    if st.session_state.get("selected_recipe"):
        page_keys.append("recipe")
    if st.session_state["active_page"] not in page_keys:
        st.session_state["active_page"] = "meal"

    nav_labels = [NAV_LABELS[k] for k in page_keys]
    label_to_key = {NAV_LABELS[k]: k for k in page_keys}

    selected_label = st.radio(
        "Navigation",
        nav_labels,
        index=nav_labels.index(NAV_LABELS[st.session_state["active_page"]]),
        horizontal=True
    )

    st.session_state["active_page"] = label_to_key[selected_label]

    if st.session_state["active_page"] == "profile":
        profile_form(prefilled_username=st.session_state.get("logged_in_user"))
    elif st.session_state["active_page"] == "meal":
        show_mealplan_page()
    elif st.session_state["active_page"] == "grocery":
        show_grocery_page()
    elif st.session_state["active_page"] == "recipe":
        show_recipe_details_page()
