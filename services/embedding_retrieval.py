from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple


class EmbeddingIndex:
    """
    Lightweight token-overlap retriever used for tests and offline execution.
    """

    def _tokenize(self, text: str) -> set[str]:
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        return {t for t in tokens if len(t) > 1}

    def _recipe_text(self, recipe) -> str:
        parts = []
        name = getattr(recipe, "recipe_name", None) or getattr(recipe, "title", None)
        if name:
            parts.append(str(name))
        ingredients = getattr(recipe, "ingredients", None)
        if isinstance(ingredients, list):
            parts.extend(str(i) for i in ingredients)
        elif isinstance(ingredients, dict):
            parts.extend(str(v) for v in ingredients.values())
        tags = getattr(recipe, "dietary_tags", None) or getattr(recipe, "tags", None)
        if isinstance(tags, list):
            parts.extend(str(t) for t in tags)
        cuisine = getattr(recipe, "cuisine_path", None) or getattr(recipe, "cuisine", None)
        if cuisine:
            parts.append(str(cuisine))
        category = getattr(recipe, "category", None)
        if category:
            parts.append(str(category))
        return " ".join(parts)

    def _profile_text(self, profile, slot=None) -> str:
        parts = []
        goal = getattr(profile, "goal", None)
        if goal:
            parts.append(str(goal))
        for field in ("dietary_preferences", "allergies", "medical_conditions"):
            vals = getattr(profile, field, None)
            if isinstance(vals, list):
                parts.extend(str(v) for v in vals)
        if slot is not None:
            meal_type = getattr(slot, "meal_type", None)
            if meal_type is not None:
                parts.append(str(meal_type))
        return " ".join(parts)

    def search(
        self,
        recipes: Iterable,
        profile,
        slot=None,
        top_n: int = 50,
    ) -> List[Tuple[object, float]]:
        profile_tokens = self._tokenize(self._profile_text(profile, slot=slot))
        results = []
        for recipe in recipes:
            recipe_tokens = self._tokenize(self._recipe_text(recipe))
            if not profile_tokens:
                sim = 0.0
            else:
                overlap = len(profile_tokens.intersection(recipe_tokens))
                sim = overlap / max(len(profile_tokens), 1)
            if sim < 0.0:
                sim = 0.0
            if sim > 1.0:
                sim = 1.0
            results.append((recipe, float(sim)))
        results.sort(key=lambda r: r[1], reverse=True)
        return results[:top_n]
