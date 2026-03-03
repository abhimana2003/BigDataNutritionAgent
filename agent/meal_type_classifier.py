"""Simple meal-type classifier for recipes.

This module provides a lightweight sklearn-based model that predicts whether a
recipe is suitable for breakfast, lunch, or dinner.  The classifier is trained
on the existing recipe database using the ``cuisine_path`` or ``dietary_tags``
as weak labels (any recipe whose cuisine contains "breakfast" is treated as a
breakfast example; all others are lumped into lunch/dinner).  The model is
sparse and fast and is only used as a fallback when the rule-based heuristics
in :mod:`agent.scoring` are insufficient.

The training code is idempotent and will re-train the model if the saved
pickle file is missing.  In a real deployment you would run training offline
and commit the resulting artifact to your data pipeline.
"""

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

# where the trained model is persisted
MODEL_PATH = os.path.join(os.path.dirname(__file__), "meal_type_model.pkl")


def _load_recipes_from_db() -> List[Recipe]:
    db = SessionLocal()
    try:
        orm_recipes = db.query(RecipeORM).all()
        # avoid circular import
        from agent.adapters import orm_to_agent_recipe

        return [orm_to_agent_recipe(r) for r in orm_recipes]
    finally:
        db.close()


def _label_recipe(r: Recipe) -> str:
    """Weak label based on cuisine_path or tags."""
    # create a single piece of text to scan for indicators; we want to
    # consider not only the recorded cuisine/tags but also the title and
    # ingredient list, because the existing data set has almost no explicit
    # "breakfast" cuisine paths.  The training labels are therefore
    # necessarily weak, but we can do a better job by looking for a handful of
    # keywords that strongly suggest a breakfast item.
    text = " ".join(
        filter(None, [r.title or "", " ".join(r.ingredients or []), r.cuisine or "", " ".join(r.tags or [])])
    ).lower()

    # keywords that, if they appear anywhere in the title/ingredients/cuisine,
    # strongly hint that the recipe is intended for breakfast.  This list is
    # deliberately conservative; it's a training heuristic, not the final
    # filtering logic, so false positives are less damaging than false
    # negatives.  We avoid very generic words like "bread" which can show up
    # in non-breakfast recipes.
    # NOTE: we intentionally avoid overly generic terms that appear in many
    # recipes (e.g. "egg").  Those were causing fish or savory dishes to be
    # mis-labeled simply because they include a single egg.  The list below is
    # conservative; the rule-based part of ``is_slot_compatible`` will still
    # catch more cases, so the classifier just needs to provide a decent
    # prior.
    breakfast_keywords = [
        "breakfast",
        "pancake",
        "waffle",
        "oatmeal",
        "cereal",
        "granola",
        "muffin",
        "toast",
        "bagel",
        "omelet",
        "omelette",
        "yogurt",
        "smoothie",
        "frittata",
    ]

    for kw in breakfast_keywords:
        if kw in text:
            return "breakfast"

    # otherwise we don't distinguish lunch vs dinner; treat as "lunchdinner"
    return "lunchdinner"


def train_classifier(force: bool = False) -> None:
    """Train (or re-train) and save the meal-type classifier.

    If the model file already exists and ``force`` is False, this is a no-op.
    """
    if os.path.exists(MODEL_PATH) and not force:
        LOGGER.debug("classifier already trained, skipping")
        return

    recipes = _load_recipes_from_db()
    texts = [" ".join([r.title or "", " ".join(r.ingredients or []), " ".join(r.tags or [])]) for r in recipes]
    labels = [_label_recipe(r) for r in recipes]

    # log class distribution so we have some visibility into how many
    # breakfast examples we're actually getting.  If the number is zero we'll
    # know the weak labeling still failed.
    from collections import Counter
    counter = Counter(labels)
    LOGGER.info("label distribution: %s", dict(counter))

    LOGGER.info("training meal-type classifier on %d recipes", len(recipes))
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
        with open(MODEL_PATH, "rb") as f:
            return pickle.load(f)


# load model on import so prediction is fast
_MODEL = _load_model()


def predict_meal_type(recipe: Recipe) -> str:
    """Return predicted meal slot: "breakfast" or "lunchdinner"."""
    if _MODEL is None:
        return "lunchdinner"
    text = " ".join([recipe.title or "", " ".join(recipe.ingredients or []), " ".join(recipe.tags or [])])
    pred = _MODEL.predict([text])[0]
    return pred
