import streamlit as st
import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor, Future
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

          .stApp * {
            animation: none !important;
            transition: none !important;
          }

          .recipe-detail-box {
            margin: -10px 0 14px;
            padding: 1rem 1.1rem;
            border: 1px solid var(--line);
            border-top: 0;
            border-radius: 0 0 16px 16px;
            background: #fff6ea;
            box-shadow: 0 10px 18px rgba(52, 35, 20, 0.06);
          }

          .recipe-detail-meta {
            margin: 0.35rem 0 0.65rem;
            color: var(--muted);
            font-size: 1.02rem;
          }

          .recipe-detail-box h4 {
            margin: 0.5rem 0 0.35rem;
            font-family: "Playfair Display", Georgia, serif;
          }

          .recipe-detail-box ul {
            margin: 0.2rem 0 0.6rem 1.1rem;
          }

          input[type="password"]::-ms-reveal,
          input[type="password"]::-ms-clear {
            display: none;
          }

          input[type="password"]::-webkit-credentials-auto-fill-button,
          input[type="password"]::-webkit-contacts-auto-fill-button {
            visibility: hidden;
            pointer-events: none;
          }

          .nutrition-targets {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 0.6rem;
            margin: 0.75rem 0 1rem;
          }

          .nutrition-target {
            background: #fffaf2;
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 0.7rem 0.85rem;
            box-shadow: 0 6px 14px rgba(52, 35, 20, 0.06);
            text-align: left;
          }

          .nutrition-target .label {
            color: var(--muted);
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
          }

          .nutrition-target .value {
            font-family: "Playfair Display", Georgia, serif;
            font-size: 1.5rem;
            color: var(--text);
            margin-top: 0.2rem;
          }

          .nutrition-target .value span {
            font-family: "Source Sans 3", sans-serif;
            font-size: 0.9rem;
            color: var(--muted);
            margin-left: 0.2rem;
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


def transient_success(message: str, seconds: float = 2.0) -> None:
    slot = st.empty()
    slot.success(message)
    time.sleep(seconds)
    slot.empty()


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
        week_start = None
        cached = st.session_state.get("last_mealplan") or {}
        if isinstance(cached, dict):
            week_start = cached.get("week_start")
        resp = requests.post(
            f"{API_URL}/{username}/replace-meal",
            json={
                "day": day,
                "meal_type": meal_type,
                "current_recipe_id": current_recipe_id,
                "exclude_recipe_ids": exclude_recipe_ids,
                "week_start": week_start,
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


def save_mealplan(username: str, plan: Dict[str, Any]) -> Dict[str, Any]:
    try:
        resp = requests.post(
            f"{API_URL}/{username}/mealplan/save",
            json={"meal_plan": plan},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()
        detail = resp.json().get("detail", "Unknown error")
        st.error(f"Meal plan save failed: {detail}")
        return {}
    except requests.RequestException as e:
        st.error(f"Meal plan save failed: {e}")
        return {}


def request_grocery_refresh(username: str, days: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        resp = requests.post(
            f"{API_URL}/{username}/grocerylist",
            json={"days": days},
            timeout=60,
        )
        if resp.status_code == 200:
            return {"ok": True, "data": resp.json()}
        detail = resp.json().get("detail", "Unknown error")
        return {"ok": False, "error": f"Grocery refresh failed: {detail}"}
    except requests.RequestException as e:
        return {"ok": False, "error": f"Grocery refresh request failed: {e}"}


_grocery_executor = ThreadPoolExecutor(max_workers=2)
_grocery_lock = threading.Lock()


def enqueue_grocery_refresh(username: str, days: List[Dict[str, Any]]) -> None:
    with _grocery_lock:
        existing: Future | None = st.session_state.get("grocery_refresh_future")
        if existing and not existing.done():
            st.session_state["pending_grocery_refresh"] = {"username": username, "days": days}
            return
        st.session_state["grocery_refresh_future"] = _grocery_executor.submit(
            request_grocery_refresh,
            username,
            days,
        )


def poll_grocery_refresh() -> None:
    future: Future | None = st.session_state.get("grocery_refresh_future")
    if not future or not future.done():
        return
    try:
        result = future.result()
    except Exception:
        st.session_state["grocery_refresh_future"] = None
        return
    st.session_state["grocery_refresh_future"] = None
    _apply_grocery_refresh_result(result)
    pending = st.session_state.pop("pending_grocery_refresh", None)
    if pending:
        st.session_state["grocery_refresh_future"] = _grocery_executor.submit(
            request_grocery_refresh,
            pending.get("username"),
            pending.get("days", []),
        )


def _apply_grocery_refresh_result(result: Dict[str, Any]) -> bool:
    if not result:
        return False
    if not result.get("ok"):
        st.session_state["grocery_refresh_error"] = result.get("error", "Unable to refresh grocery list.")
        return False
    payload = result.get("data") or {}
    items = payload.get("items") or []
    text = payload.get("text")
    if not items and not text:
        st.session_state["grocery_refresh_error"] = "Grocery service returned an empty list."
        return False
    gp = st.session_state.get("last_mealplan") or {}
    gp["grocery_list"] = items
    gp["grocery_text"] = text
    st.session_state["last_mealplan"] = gp
    st.session_state["grocery_refresh_error"] = None
    return True


def refresh_grocery_now(username: str, days: List[Dict[str, Any]]) -> bool:
    with st.spinner("Updating grocery list…"):
        result = request_grocery_refresh(username, days)
    return _apply_grocery_refresh_result(result)


def _build_local_grocery_fallback(days: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for day in days or []:
        for meal in day.get("meals", []) or []:
            rid = meal.get("recipe_id")
            if rid is None:
                continue
            detail = fetch_recipe(int(rid), show_error=False)
            ingredients = detail.get("ingredients") or []
            for ing in ingredients:
                name = str(ing).strip()
                if not name:
                    continue
                key = name.lower()
                if key not in merged:
                    merged[key] = {"name": name, "quantity": 1, "unit": None}
                else:
                    merged[key]["quantity"] = int(merged[key].get("quantity") or 0) + 1
    return list(merged.values())

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
    if st.button("← Back to Login", key="back_to_login", type="secondary"):
        st.session_state["creating_profile"] = False
        st.session_state["current_view"] = "login"
        st.rerun()
    st.title("Create Your Profile")

    edit_id = None
    existing = {}  

    with st.form("create_profile_form"):
        default_username = prefilled_username or ""
        username = st.text_input("Username", value=default_username, key="profile_username_create")
        full_name = st.text_input("Full Name", key="profile_full_name_create")
        email = st.text_input("Email", key="profile_email_create")
        password = st.text_input("Password", type="password", key="profile_password_create")

        age = st.text_input("Age", value=str(existing.get("age", "")), key="age_create")
        st.subheader("Height")
        feet, inches = st.columns(2)
        with feet:
            heightFt = st.text_input("Feet", value=str(existing.get("height_feet", "")), key="height_feet_create")
        with inches:
            heightIn = st.text_input("Height (inches)", value=str(existing.get("height_inches", "")), key="height_inches_create")
        weight = st.text_input("Weight (lbs)", value=str(existing.get("weight", "")), key="weight_create")

        gender_opts = ["", "Female", "Male", "Other"]
        gender = st.selectbox("Gender", gender_opts,
                              index=gender_opts.index(existing.get("gender", "")) if existing.get("gender") else 0,
                              key="gender_create")

        goal_opts = ["", "weight loss", "maintenance", "high protein"]
        goal = st.selectbox("Goal", goal_opts,
                            index=goal_opts.index(existing.get("goal", "")) if existing.get("goal") else 0,
                            key="goal_create")

        dietary_opts = ["None", "Vegetarian", "Vegan", "Pescatarian", "Low Carb", "Keto"]
        allergies_opts = ["None", "Nuts", "Dairy", "Gluten", "Soy", "Eggs"]
        medical_opts = ["None", "Diabetes", "Hypertension", "Celiac", "High Cholesterol"]

        dietary = st.multiselect("Dietary Preferences", dietary_opts,
                                 default=existing.get("dietary_preferences", []), key="dietary_create")
        allergies = st.multiselect("Allergies", allergies_opts,
                                   default=existing.get("allergies", []), key="allergies_create")
        medical = st.multiselect("Medical Conditions", medical_opts,
                                 default=existing.get("medical_conditions", []), key="medical_create")

        # Budget input as float
        budget = st.number_input("Weekly Grocery Budget ($)",
                                 min_value=0.0,
                                 max_value=10000.0,
                                 value=float(existing.get("budget_level", 0) or 0),
                                 step=1.0,
                                 format="%.2f",
                                 key="budget_create")

        cook_opts = ["", "short (<30 mins)", "medium (30-60 min)", "long (>60 mins)"]
        cooking_time = st.selectbox("Cooking Time", cook_opts,
                                    index=cook_opts.index(existing.get("cooking_time", "")) if existing.get("cooking_time") else 0,
                                    key="cooking_time_create")

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
            st.session_state["had_successful_login"] = True
            st.session_state["creating_profile"] = False
            st.session_state["current_view"] = "mainApp"
            st.session_state["active_page"] = "meal"
            st.session_state["needs_plan_refresh"] = True
            st.session_state["is_first_plan_generation"] = True
            st.session_state["pending_initial_generation"] = True
            st.session_state["last_mealplan"] = None
            st.session_state["last_mealplan_user"] = None
            st.session_state["new_username"] = None
            st.session_state["post_create_flush"] = True
            for key in [
                "profile_username_create",
                "profile_full_name_create",
                "profile_email_create",
                "profile_password_create",
                "age_create",
                "height_feet_create",
                "height_inches_create",
                "weight_create",
                "gender_create",
                "goal_create",
                "dietary_create",
                "allergies_create",
                "medical_create",
                "budget_create",
                "cooking_time_create",
            ]:
                st.session_state.pop(key, None)
            st.rerun()

        except requests.exceptions.HTTPError as e:
            st.error(f"Failed to save profile: {e} - {r.text}")

# Login Page
def show_login_page():
    st.title("Nutrition AI Agent Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    left_btn, spacer_btn, right_btn = st.columns([0.7, 0.15, 0.15], gap="small")
    with left_btn:
        if st.button("Log In", key="login_submit"):
            try:
                if not username or not password:
                    st.error("Please enter both username and password.")
                    return
                res = requests.post(AUTH_URL, json={"username": username, "password": password})
                if res.status_code == 200:
                    st.session_state["logged_in_user"] = username.strip()
                    st.session_state["had_successful_login"] = True
                    st.session_state["current_view"] = "mainApp"
                    st.session_state["active_page"] = "meal"
                    st.session_state["needs_plan_refresh"] = False
                    st.session_state["is_first_plan_generation"] = False
                    st.session_state["pending_initial_generation"] = False
                    st.session_state["last_mealplan"] = None
                    st.session_state["last_mealplan_user"] = None
                    st.rerun()
                else:
                    st.error("Invalid username or password")
            except requests.RequestException:
                st.error("Server error")
    with right_btn:
        if st.button("Create New Profile", key="login_create_profile", use_container_width=True):
            st.session_state["creating_profile"] = True
            st.session_state["current_view"] = "createProfile"
            st.session_state["new_username"] = username.strip()
            st.rerun()

# Meal Plan Page
def show_mealplan_page() -> None:
    st.title("Weekly Meal Plan")

    username = st.session_state.get("logged_in_user")
    if not username:
        st.info("Please log in first")
        return

    poll_grocery_refresh()

    loading_placeholder = st.empty()
    if st.button("Generate Next Week", type="secondary"):
        try:
            st.session_state["mealplan_generation_in_progress"] = True
            with loading_placeholder.container():
                st.info("Generating next week's meal plan…")
            resp = requests.get(
                f"{API_URL}/{username}/mealplan",
                params={"next_week": "true", "force": "true"},
            )
            resp.raise_for_status()
            data = resp.json()
            st.session_state["last_mealplan"] = data
            st.session_state["last_mealplan_user"] = username
            st.session_state["needs_plan_refresh"] = False
            st.session_state["is_first_plan_generation"] = False
            if not data.get("grocery_list") and not data.get("grocery_text"):
                refresh_grocery_now(username, data.get("days", []))
            data_after_refresh = st.session_state.get("last_mealplan") or data
            has_grocery = bool(data_after_refresh.get("grocery_list") or data_after_refresh.get("grocery_text"))
            if has_grocery:
                st.session_state["pending_initial_generation"] = False
            loading_placeholder.empty()
            st.success("Generated next week's meal plan.")
            st.rerun()
        except requests.RequestException as e:
            loading_placeholder.empty()
            st.error(f"Failed to generate next week's meal plan: {e}")
        finally:
            st.session_state["mealplan_generation_in_progress"] = False

    cached = st.session_state.get("last_mealplan")
    cached_user = st.session_state.get("last_mealplan_user")
    needs_refresh = st.session_state.get("needs_plan_refresh", False)
    is_first_plan_generation = st.session_state.get("is_first_plan_generation", False)

    if needs_refresh or not cached or cached_user != username:
        try:
            st.session_state["mealplan_generation_in_progress"] = True
            with loading_placeholder.container():
                if needs_refresh:
                    if is_first_plan_generation:
                        st.info("Generating your meal plan…")
                    else:
                        st.info("Your profile changed — regenerating your plan…")
                else:
                    st.info("Loading your meal plan…")

            params = {"force": "true"} if needs_refresh else {}
            resp = requests.get(f"{API_URL}/{username}/mealplan",params=params)
            resp.raise_for_status()

            data = resp.json()
            st.session_state["last_mealplan"] = data
            st.session_state["last_mealplan_user"] = username
            st.session_state["needs_plan_refresh"] = False
            st.session_state["is_first_plan_generation"] = False
            if not data.get("grocery_list") and not data.get("grocery_text"):
                refresh_grocery_now(username, data.get("days", []))
            data_after_refresh = st.session_state.get("last_mealplan") or data
            has_grocery = bool(data_after_refresh.get("grocery_list") or data_after_refresh.get("grocery_text"))
            if has_grocery:
                st.session_state["pending_initial_generation"] = False
            loading_placeholder.empty()

        except requests.RequestException as e:
            loading_placeholder.empty()
            st.error(f"Failed to generate meal plan: {e}")
        finally:
            st.session_state["mealplan_generation_in_progress"] = False

    cached = st.session_state.get("last_mealplan")
    if cached:
        targets = cached.get("nutrition_targets") or {}
        cals = targets.get("daily_calories")
        protein = targets.get("protein_g")
        carbs = targets.get("carbs_g")
        fat = targets.get("fat_g")
        if any(v is not None for v in (cals, protein, carbs, fat)):
            st.markdown('<div class="daily-meals-title">Nutrition Goals</div>', unsafe_allow_html=True)
            def _fmt(val):
                if val is None:
                    return "—"
                return str(int(val)) if isinstance(val, (int, float)) else str(val)

            st.markdown(
                f"""
                <div class="nutrition-targets">
                  <div class="nutrition-target">
                    <div class="label">Calories</div>
                    <div class="value">{_fmt(cals)}<span> kcal</span></div>
                  </div>
                  <div class="nutrition-target">
                    <div class="label">Protein</div>
                    <div class="value">{_fmt(protein)}<span> g</span></div>
                  </div>
                  <div class="nutrition-target">
                    <div class="label">Carbs</div>
                    <div class="value">{_fmt(carbs)}<span> g</span></div>
                  </div>
                  <div class="nutrition-target">
                    <div class="label">Fat</div>
                    <div class="value">{_fmt(fat)}<span> g</span></div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        display_mealplan(cached)

def display_mealplan(data: Dict[str, Any]) -> None:
    days = data.get("days", [])
    if not days:
        st.info("No meal plan data available yet.")
        return

    st.markdown('<div class="daily-meals-title">Daily Meals</div>', unsafe_allow_html=True)
    day_labels = {
        1: "Monday",
        2: "Tuesday",
        3: "Wednesday",
        4: "Thursday",
        5: "Friday",
        6: "Saturday",
        7: "Sunday",
    }
    sorted_days = sorted(
        [d for d in days if d.get("day") is not None],
        key=lambda d: int(d.get("day")),
    )
    tab_names = [day_labels.get(int(day.get("day")), f"Day {int(day.get('day'))}") for day in sorted_days]
    tabs = st.tabs(tab_names)

    for tab, day_data in zip(tabs, sorted_days):
        day_num = int(day_data.get("day"))
        with tab:
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
                open_key = f"open_recipe_{day_num}_{idx}_{recipe_id}"
                if st.session_state.get(open_key):
                    detail = st.session_state.get(f"{open_key}_detail")
                    if detail:
                        image_url = detail.get("image_url")
                        meta_parts = []
                        if detail.get("prep_time") is not None:
                            meta_parts.append(f"Prep: {detail['prep_time']} min")
                        if detail.get("cook_time") is not None:
                            meta_parts.append(f"Cook: {detail['cook_time']} min")
                        if detail.get("total_time") is not None:
                            meta_parts.append(f"Total: {detail['total_time']} min")
                        if detail.get("servings") is not None:
                            meta_parts.append(f"Servings: {detail['servings']}")
                        meta_html = " | ".join(escape(part) for part in meta_parts)

                        ingredients = detail.get("ingredients", []) or []
                        ing_items = "".join(f"<li>{escape(str(item))}</li>" for item in ingredients)
                        ing_html = ing_items or "<li>No ingredient list available.</li>"

                        directions = detail.get("directions", []) or []
                        dir_items = "".join(f"<li>{escape(str(step))}</li>" for step in directions)
                        dir_html = dir_items or "<li>No step-by-step instructions available.</li>"

                        source_link = ""
                        if detail.get("url"):
                            source_link = f"<a href=\"{escape(detail['url'])}\" target=\"_blank\">Open Source Recipe</a>"

                        image_block = ""
                        if image_url:
                            image_block = f"<img src=\"{escape(image_url)}\" alt=\"{escape(title)}\" width=\"320\" />"

                        nutrition_parts = []
                        if detail.get("calories") is not None:
                            nutrition_parts.append(f"Calories: {detail['calories']}")
                        if detail.get("protein_g") is not None:
                            nutrition_parts.append(f"Protein: {detail['protein_g']} g")
                        if detail.get("carbs_g") is not None:
                            nutrition_parts.append(f"Carbs: {detail['carbs_g']} g")
                        if detail.get("fat_g") is not None:
                            nutrition_parts.append(f"Fat: {detail['fat_g']} g")
                        nutrition_html = " | ".join(escape(part) for part in nutrition_parts)

                        st.markdown(
                            f"""
                            <div class="recipe-detail-box">
                              <h3>{escape(title)}</h3>
                              {image_block}
                              <div class="recipe-detail-meta">{meta_html}</div>
                              <div class="recipe-detail-meta">{nutrition_html}</div>
                              <div>{source_link}</div>
                              <h4>Ingredients</h4>
                              <ul>{ing_html}</ul>
                              <h4>Instructions</h4>
                              <ol>{dir_html}</ol>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                act_like, act_dislike, act_doesnt_fit, act_replace, act_open = st.columns([1, 1, 1.1, 1.1, 1.4])

                with act_like:
                    if st.button("Like", key=f"meal_like_{day_num}_{idx}_{recipe_id}", type="secondary"):
                        if recipe_id is None:
                            st.error("Cannot like a meal without recipe id.")
                        elif submit_feedback(st.session_state.get("logged_in_user"), int(recipe_id), "like"):
                            st.success("Saved. Future plans will lean toward similar recipes.")

                with act_dislike:
                    if st.button("Don't Like", key=f"meal_dislike_{day_num}_{idx}_{recipe_id}", type="secondary"):
                        if recipe_id is None:
                            st.error("Cannot submit feedback without recipe id.")
                        elif submit_feedback(st.session_state.get("logged_in_user"), int(recipe_id), "dislike"):
                            st.success("Saved. We'll avoid similar options.")

                with act_doesnt_fit:
                    if st.button("Doesn't Fit", key=f"meal_doesnt_fit_{day_num}_{idx}_{recipe_id}", type="secondary"):
                        if recipe_id is None:
                            st.error("Cannot submit feedback without recipe id.")
                        elif submit_feedback(st.session_state.get("logged_in_user"), int(recipe_id), "doesnt_fit"):
                            loading_placeholder = st.empty()
                            with loading_placeholder.container():
                                st.info("Finding a better fit…")
                            exclude_ids = [
                                int(m.get("recipe_id"))
                                for d in data.get("days", [])
                                for m in d.get("meals", [])
                                if m.get("recipe_id") is not None
                            ]
                            replacement = request_replacement(
                                username=st.session_state.get("logged_in_user"),
                                day=day_num,
                                meal_type=str(meal.get("meal_type", "")),
                                current_recipe_id=int(recipe_id),
                                exclude_recipe_ids=exclude_ids,
                            )
                            new_meal = replacement.get("meal")
                            if new_meal:
                                meal.update(new_meal)
                                st.session_state["last_mealplan"] = data
                                saved = save_mealplan(st.session_state.get("logged_in_user"), data)
                                if saved:
                                    st.session_state["last_mealplan"] = saved
                                refresh_grocery_now(
                                    username=st.session_state.get("logged_in_user"),
                                    days=(st.session_state.get("last_mealplan") or data).get("days", []),
                                )
                                loading_placeholder.empty()
                                st.success("Saved. We'll avoid meals like this.")
                                st.rerun()
                            else:
                                loading_placeholder.empty()
                                transient_success("Saved. We'll avoid meals like this.")

                with act_replace:
                    if st.button("Replace", key=f"meal_replace_{day_num}_{idx}_{recipe_id}", type="secondary"):
                        if recipe_id is None:
                            st.error("Cannot replace a meal without recipe id.")
                        else:
                            loading_placeholder = st.empty()
                            with loading_placeholder.container():
                                st.info("Loading a replacement recipe…")
                            exclude_ids = [
                                int(m.get("recipe_id"))
                                for d in data.get("days", [])
                                for m in d.get("meals", [])
                                if m.get("recipe_id") is not None
                            ]
                            replacement = request_replacement(
                                username=st.session_state.get("logged_in_user"),
                                day=day_num,
                                meal_type=str(meal.get("meal_type", "")),
                                current_recipe_id=int(recipe_id),
                                exclude_recipe_ids=exclude_ids,
                            )
                            new_meal = replacement.get("meal")
                            if new_meal:
                                meal.update(new_meal)
                                st.session_state["last_mealplan"] = data
                                saved = save_mealplan(st.session_state.get("logged_in_user"), data)
                                if saved:
                                    st.session_state["last_mealplan"] = saved
                                refresh_grocery_now(
                                    username=st.session_state.get("logged_in_user"),
                                    days=(st.session_state.get("last_mealplan") or data).get("days", []),
                                )
                                loading_placeholder.empty()
                                st.success("Replaced with a same-category recipe tuned to your likes.")
                                st.rerun()

                with act_open:
                    is_open = st.session_state.get(open_key, False)
                    view_label = "Close Recipe Details" if is_open else "Open Recipe Details"
                    if st.button(view_label, key=f"recipe_open_{day_num}_{idx}_{recipe_id}", type="secondary"):
                        if recipe_id is None:
                            st.error("This meal is missing a recipe id.")
                        else:
                            if is_open:
                                st.session_state[open_key] = False
                                st.rerun()
                            else:
                                detail = fetch_recipe(int(recipe_id), show_error=True)
                                if detail:
                                    st.session_state[open_key] = True
                                    st.session_state[f"{open_key}_detail"] = detail
                                    st.rerun()

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
    st.title("Grocery List")
    poll_grocery_refresh()
    refresh_error = st.session_state.get("grocery_refresh_error")
    if refresh_error:
        st.error(refresh_error)
        st.session_state["grocery_refresh_error"] = None

    gp = st.session_state.get("last_mealplan")
    username = st.session_state.get("logged_in_user")
    cached_user = st.session_state.get("last_mealplan_user")
    needs_refresh = st.session_state.get("needs_plan_refresh", False)
    mealplan_generating = st.session_state.get("mealplan_generation_in_progress", False)
    is_first_plan_generation = st.session_state.get("is_first_plan_generation", False)
    pending_initial_generation = st.session_state.get("pending_initial_generation", False)
    had_successful_login = st.session_state.get("had_successful_login", False)
    refresh_future = st.session_state.get("grocery_refresh_future")
    grocery_refreshing = bool(refresh_future and not refresh_future.done())
    generating_msg = "Your meal plan is still generating, so your grocery list is being prepared too."
    has_current_plan = bool(gp) and cached_user == username
    if not has_current_plan:
        first_time_pending = had_successful_login and not gp and (is_first_plan_generation or pending_initial_generation)
        if needs_refresh or mealplan_generating or grocery_refreshing or first_time_pending:
            st.info(generating_msg)
        else:
            st.info("No grocery list is available yet. Open the Meal Plan tab to load your latest plan.")
        return

    is_updating = needs_refresh or mealplan_generating or grocery_refreshing
    if is_updating:
        st.info("Your meal plan is being regenerated, so your grocery list is updating too.")

    grocery = (gp or {}).get("grocery_list", [])
    text = (gp or {}).get("grocery_text")
    has_grocery_data = bool(text) or bool(grocery)
    if not has_grocery_data:
        st.info(generating_msg)
    else:
        st.session_state["pending_initial_generation"] = False

    # Always try to populate grocery data immediately when missing.
    if not has_grocery_data:
        days_for_user = (gp or {}).get("days", [])
        refreshed = refresh_grocery_now(username, days_for_user)
        gp = st.session_state.get("last_mealplan") or {}
        grocery = gp.get("grocery_list", [])
        text = gp.get("grocery_text")
        has_grocery_data = bool(text) or bool(grocery)

        if not refreshed and not has_grocery_data:
            fallback_items = _build_local_grocery_fallback(days_for_user)
            if fallback_items:
                gp["grocery_list"] = fallback_items
                gp["grocery_text"] = None
                st.session_state["last_mealplan"] = gp
                grocery = fallback_items
                text = None
                has_grocery_data = True
                st.info("Showing a quick grocery list from recipe ingredients while full grocery processing catches up.")

    if not has_grocery_data:
        st.info(generating_msg)
        return
    if text:
        if is_updating:
            st.markdown("<div style='opacity:0.45;'>", unsafe_allow_html=True)
        lines = [line.strip("- ").strip() for line in text.splitlines() if line.strip()]
        for idx, line in enumerate(lines):
            col_check, col_text = st.columns([0.03, 0.97], gap="small", vertical_alignment="center")
            with col_check:
                checked = st.checkbox(
                    f"Grocery item {idx + 1}",
                    key=f"grocery_text_item_{idx}",
                    label_visibility="collapsed",
                )
            with col_text:
                safe_line = escape(line)
                display = f"~~{safe_line}~~" if checked else safe_line
                st.markdown(display)
        if is_updating:
            st.markdown("</div>", unsafe_allow_html=True)
        return
    if not grocery:
        st.write("No grocery items in last meal plan.")
        return
    if is_updating:
        st.markdown("<div style='opacity:0.45;'>", unsafe_allow_html=True)
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
            label = " ".join(parts)
            key = f"grocery_item_{name}_{quantity}_{unit}"
            col_check, col_text = st.columns([0.03, 0.97], gap="small", vertical_alignment="center")
            with col_check:
                checked = st.checkbox(
                    f"Grocery item {name}",
                    key=key,
                    label_visibility="collapsed",
                )
            with col_text:
                safe_label = escape(label)
                display = f"~~{safe_label}~~" if checked else safe_label
                st.markdown(display)
    if is_updating:
        st.markdown("</div>", unsafe_allow_html=True)

# main app flow
if "logged_in_user" not in st.session_state:
    st.session_state["logged_in_user"] = None
if "creating_profile" not in st.session_state:
    st.session_state["creating_profile"] = False
if "new_username" not in st.session_state:
    st.session_state["new_username"] = None
if "selected_recipe" not in st.session_state:
    st.session_state["selected_recipe"] = None
if "recipe_cache" not in st.session_state:
    st.session_state["recipe_cache"] = {}
if "needs_plan_refresh" not in st.session_state:
    st.session_state["needs_plan_refresh"] = False
if "last_mealplan_user" not in st.session_state:
    st.session_state["last_mealplan_user"] = None
if "had_successful_login" not in st.session_state:
    st.session_state["had_successful_login"] = False
if "is_first_plan_generation" not in st.session_state:
    st.session_state["is_first_plan_generation"] = False
if "post_create_flush" not in st.session_state:
    st.session_state["post_create_flush"] = False
if "pending_initial_generation" not in st.session_state:
    st.session_state["pending_initial_generation"] = False
if "mealplan_generation_in_progress" not in st.session_state:
    st.session_state["mealplan_generation_in_progress"] = False
if "pending_grocery_refresh" not in st.session_state:
    st.session_state["pending_grocery_refresh"] = None
if "grocery_refresh_error" not in st.session_state:
    st.session_state["grocery_refresh_error"] = None
if "current_view" not in st.session_state:
    if st.session_state.get("logged_in_user"):
        st.session_state["current_view"] = "mainApp"
    elif st.session_state.get("creating_profile"):
        st.session_state["current_view"] = "createProfile"
    else:
        st.session_state["current_view"] = "login"

# One extra rerun after account creation to clear any stale create-form deltas.
if st.session_state.get("post_create_flush"):
    st.session_state["post_create_flush"] = False
    st.rerun()

# Single render-state gate: exactly one top-level view is mounted each run.
current_view = st.session_state.get("current_view", "login")

login_slot = st.empty()
create_slot = st.empty()
main_slot = st.empty()

if current_view == "createProfile":
    login_slot.empty()
    main_slot.empty()
    with create_slot.container():
        show_profile_form(prefilled_username=st.session_state["new_username"])
    st.stop()

if current_view == "login":
    # If we somehow lost the user after login, reset and show login UI.
    if st.session_state.get("had_successful_login"):
        st.session_state["had_successful_login"] = False
    create_slot.empty()
    main_slot.empty()
    with login_slot.container():
        show_login_page()
    st.stop()

# Fallback guard: main app requires authenticated user.
if not st.session_state.get("logged_in_user"):
    st.session_state["current_view"] = "login"
    st.rerun()

# Logged-in app UI.
login_slot.empty()
create_slot.empty()
with main_slot.container():
    header_left, header_right = st.columns([0.85, 0.15], gap="small")
    with header_right:
        if st.button("Log Out", key="logout_btn", type="secondary", use_container_width=True):
            st.session_state["logged_in_user"] = None
            st.session_state["had_successful_login"] = False
            st.session_state["needs_plan_refresh"] = False
            st.session_state["is_first_plan_generation"] = False
            st.session_state["pending_initial_generation"] = False
            st.session_state["last_mealplan"] = None
            st.session_state["last_mealplan_user"] = None
            st.session_state["selected_recipe"] = None
            st.session_state["creating_profile"] = False
            st.session_state["mealplan_generation_in_progress"] = False
            st.session_state["grocery_refresh_future"] = None
            st.session_state["pending_grocery_refresh"] = None
            st.session_state["grocery_refresh_error"] = None
            st.session_state["current_view"] = "login"
            st.rerun()

    page_keys = ["profile", "meal", "grocery"]
    tabs = st.tabs([NAV_LABELS[k] for k in page_keys])

    with tabs[0]:
        profile_form(prefilled_username=st.session_state.get("logged_in_user"))
    with tabs[1]:
        show_mealplan_page()
    with tabs[2]:
        show_grocery_page()

    if st.session_state.get("selected_recipe"):
        st.markdown("---")
        with st.expander(NAV_LABELS["recipe"], expanded=False):
            show_recipe_details_page()
