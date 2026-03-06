from sqlalchemy import Column, Integer, String, Float, ARRAY, JSON, ForeignKey
from database import Base
from sqlalchemy.orm import relationship


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    full_name = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    password_salt = Column(String, nullable=True)
    age = Column(Integer, nullable=False)
    height_feet = Column(Integer, nullable=False)
    height_inches = Column(Integer, nullable=False)
    weight = Column(Float, nullable=False)
    gender = Column(String, nullable=False)
    goal = Column(String, nullable=False)
    dietary_preferences = Column(ARRAY(String), default=[])
    allergies = Column(ARRAY(String), default=[])
    medical_conditions = Column(ARRAY(String), default=[])
    budget_level = Column(String)
    cooking_time = Column(String)
    recipes = relationship("Recipe", back_populates="user")


class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, index=True)
    recipe_name = Column(String, nullable=False)
    prep_time = Column(Integer)
    cook_time = Column(Integer)
    total_time = Column(Integer)
    servings = Column(Integer)
    ingredients = Column(JSON)
    directions = Column(JSON)
    rating = Column(Float)
    url = Column(String)
    cuisine_path = Column(String)
    nutrition = Column(JSON)
    timing = Column(JSON)
    dietary_tags = Column(JSON)
    estimated_cost = Column(Float)
    username = Column(String, ForeignKey("user_profiles.username"))
    user = relationship("UserProfile", back_populates="recipes")
