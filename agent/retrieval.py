# agent/retrieval.py
from __future__ import annotations
from typing import List, Optional
from agent.interfaces import (MealSlot,RecipeCandidate,Retriever,UserProfile)


class RecommenderRetriever(Retriever):
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

# retriever for testing 
class MockRetriever(Retriever):

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
