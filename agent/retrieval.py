# agent/retrieval.py
from __future__ import annotations

from typing import Dict, List, Optional

from agent.interfaces import (
    MealSlot,
    Recipe,
    RecipeCandidate,
    Retriever,
    UserProfile,
)


class RecommenderRetriever(Retriever):
    """Retriever backed by the CSV-based recommender pipeline."""

    def retrieve(
        self,
        profile: UserProfile,
        slot: MealSlot,
        k: int = 10,
    ) -> List[RecipeCandidate]:
        from agent.recommender import recommend

        return recommend(
            user_id=profile.id or 0,
            profile=profile,
            slot=slot,
            k=k,
        )


class MockRetriever(Retriever):
    """Returns pre-loaded candidates for testing / offline dev."""

    def __init__(self, candidates: Optional[List[RecipeCandidate]] = None):
        if candidates is not None:
            self._candidates = candidates
        else:
            from agent.mock_data import mock_candidates
            self._candidates = mock_candidates()

    def retrieve(
        self,
        profile: UserProfile,
        slot: MealSlot,
        k: int = 10,
    ) -> List[RecipeCandidate]:
        return self._candidates[:k]