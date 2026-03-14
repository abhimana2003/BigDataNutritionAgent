from sqlalchemy.orm import Session
from models import UserProfile, MealPlanHistory
import schemas
from fastapi import HTTPException
import models
from sqlalchemy.exc import IntegrityError
from auth_utils import hash_password, verify_password
from datetime import datetime, date


def upsert_user_profile(db: Session, username: str, profile: schemas.UserProfileCreate):
    if not profile.username:
        raise HTTPException(status_code=400, detail="Username is required")

    db_user = db.query(UserProfile).filter(UserProfile.username == profile.username).first()

    if db_user:
        for field, value in profile.dict(exclude={"password"}, exclude_unset=True).items():
            setattr(db_user, field, value)
        if profile.password:
            salt, digest = hash_password(profile.password)
            db_user.password_salt = salt
            db_user.password_hash = digest
    else:
        if not profile.password:
            raise HTTPException(status_code=400, detail="Password is required for new profiles")
        salt, digest = hash_password(profile.password)
        payload = profile.dict(exclude={"password"})
        payload["password_salt"] = salt
        payload["password_hash"] = digest
        db_user = models.UserProfile(**payload)
        db.add(db_user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username or email already exists")

    db.refresh(db_user)
    return db_user


def get_user_profiles(db: Session):
    return db.query(UserProfile).all()


def get_user_by_username(db: Session, username: str):
    return db.query(UserProfile).filter(UserProfile.username == username.strip()).first()


def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.password_salt or "", user.password_hash or ""):
        return None
    return user


def update_user_profile_by_username(db: Session, username: str, profile):
    db_profile = db.query(UserProfile).filter_by(username=username).first()

    if not db_profile:
        return None

    for key, value in profile.dict(exclude_unset=True).items():
        setattr(db_profile, key, value)

    db.commit()
    db.refresh(db_profile)
    return db_profile


def get_latest_mealplan_history_before_or_on(db: Session, username: str, week_start: date):
    return (
        db.query(MealPlanHistory)
        .filter(MealPlanHistory.username == username, MealPlanHistory.week_start <= week_start)
        .order_by(MealPlanHistory.week_start.desc(), MealPlanHistory.created_at.desc())
        .first()
    )


def get_mealplan_history_for_week(db: Session, username: str, week_start: date):
    return (
        db.query(MealPlanHistory)
        .filter(MealPlanHistory.username == username, MealPlanHistory.week_start == week_start)
        .order_by(MealPlanHistory.created_at.desc())
        .first()
    )


def get_latest_mealplan_history(db: Session, username: str):
    return (
        db.query(MealPlanHistory)
        .filter(MealPlanHistory.username == username)
        .order_by(MealPlanHistory.created_at.desc())
        .first()
    )


def upsert_mealplan_history(
    db: Session,
    username: str,
    week_start: date,
    recipe_ids: list[int],
    meal_plan: dict | None = None,
):
    existing = (
        db.query(MealPlanHistory)
        .filter(MealPlanHistory.username == username, MealPlanHistory.week_start == week_start)
        .order_by(MealPlanHistory.created_at.desc())
        .first()
    )
    if existing:
        existing.recipe_ids = recipe_ids
        if meal_plan is not None:
            existing.meal_plan = meal_plan
        existing.created_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    record = MealPlanHistory(
        username=username,
        week_start=week_start,
        recipe_ids=recipe_ids,
        meal_plan=meal_plan,
        created_at=datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
