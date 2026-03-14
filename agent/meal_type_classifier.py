from __future__ import annotations
import os
import pickle
import logging
from typing import List
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from agent.interfaces import Recipe
from database import SessionLocal
from models import Recipe as RecipeORM

LOGGER = logging.getLogger(__name__)

# where the trained model is stored 
MODEL_PATH = os.path.join(os.path.dirname(__file__), "meal_type_model_v2.pkl")


def _load_recipes_from_db() -> List[Recipe]:
    db = SessionLocal()
    try:
        orm_recipes = db.query(RecipeORM).all()
        from agent.adapters import orm_to_agent_recipe

        return [orm_to_agent_recipe(r) for r in orm_recipes]
    finally:
        db.close()


def _label_recipe(r: Recipe) -> str:
    """
    Training label from ingest category.
    category values expected: breakfast | main_meal | snack | dessert
    """
    category = str(r.category or "").strip().lower()
    if category == "breakfast":
        return "breakfast"
    if category == "main_meal":
        return "lunchdinner"
    if category in {"snack", "dessert"}:
        return "snack"
    return "lunchdinner"


def train_classifier(force: bool = False) -> None:
    """Train (or re-train) and save the meal-type classifier.
    If the model file already exists and ``force`` is False, this is a no-op.
    """
    if os.path.exists(MODEL_PATH) and not force:
        LOGGER.debug("classifier already trained, skipping")
        return

    recipes = _load_recipes_from_db()
    # train only on rows with known category labels
    labeled = [r for r in recipes if getattr(r, "category", None)]
    texts = [" ".join([r.title or "", " ".join(r.ingredients or []), " ".join(r.tags or [])]) for r in labeled]
    labels = [_label_recipe(r) for r in labeled]

    if len(set(labels)) < 2:
        LOGGER.warning("not enough label diversity for classifier; skipping training")
        return

    from collections import Counter
    counter = Counter(labels)
    LOGGER.info("label distribution: %s", dict(counter))

    LOGGER.info("training meal-type classifier on %d recipes", len(labeled))
    clf = Pipeline([
        ("vect", CountVectorizer(ngram_range=(1, 2), max_features=10000)),
        ("clf", LogisticRegression(max_iter=200))
    ])
    clf.fit(texts, labels)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(clf, f)

    LOGGER.info("meal-type classifier trained and saved to %s", MODEL_PATH)


def _load_model():
    if not os.path.exists(MODEL_PATH):
        train_classifier()
    try:
        with open(MODEL_PATH, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        LOGGER.warning("failed to load meal-type model (%s); retraining", e)
        train_classifier(force=True)
        if not os.path.exists(MODEL_PATH):
            return None
        try:
            with open(MODEL_PATH, "rb") as f:
                return pickle.load(f)
        except Exception as e2:
            LOGGER.warning("failed to load retrained meal-type model (%s)", e2)
            return None


# load model on import so prediction is fast
_MODEL = _load_model()


def predict_meal_type(recipe: Recipe) -> str:
    """Return predicted meal type label: breakfast | lunchdinner | snack."""
    if _MODEL is None:
        return "lunchdinner"
    text = " ".join([recipe.title or "", " ".join(recipe.ingredients or []), " ".join(recipe.tags or [])])
    pred = _MODEL.predict([text])[0]
    return pred
