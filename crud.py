from sqlalchemy.orm import Session
from models import UserProfile
import schemas

def create_user_profile(db: Session, profile: schemas.UserProfileCreate):
    obj = UserProfile(**profile.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def get_user_profiles(db: Session):
    return db.query(UserProfile).all()

def get_user_profile(db: Session, profile_id: int):
    return db.query(UserProfile).filter(UserProfile.id == profile_id).first()