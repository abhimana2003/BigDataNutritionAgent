def test_recommendations_include_similarity_score(db_session, sample_profile, sample_slot):
    from services.recommendation import recommend_for_profile

    resp = recommend_for_profile(db_session, user_id=1, profile=sample_profile, slot=sample_slot, k=5, top_n=50)
    assert resp.candidates
    assert resp.candidates[0].similarity_score is not None