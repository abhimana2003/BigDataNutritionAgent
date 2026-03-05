from sqlalchemy.orm import Session
from models import UserProfile
import schemas
from fastapi import HTTPException
import models


def upsert_user_profile(db: Session, username: str, profile: schemas.UserProfileCreate):
    db_user = db.query(UserProfile).filter(UserProfile.username == profile.username).first()

    if db_user:
        for field, value in profile.dict().items():
            setattr(db_user, field, value)
    else:
        db_user = models.UserProfile(**profile.dict())
        db.add(db_user)

    db.commit()
    db.refresh(db_user)
    return db_user


def get_user_profiles(db: Session):
    return db.query(UserProfile).all()


def get_user_by_username(db: Session, username: str):
    return db.query(UserProfile).filter(UserProfile.username == username).first()


def update_user_profile_by_username(db: Session, username: str, profile):
    db_profile = db.query(UserProfile).filter_by(username=username).first()

    if not db_profile:
        return None

    for key, value in profile.dict(exclude_unset=True).items():
        setattr(db_profile, key, value)

    db.commit()
    db.refresh(db_profile)
    return db_profile