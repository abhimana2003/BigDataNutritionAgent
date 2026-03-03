def test_embedding_search_returns_scores(db_session, sample_profile):
    from services.embedding_retrieval import EmbeddingIndex
    from models import Recipe as RecipeORM

    recipes = db_session.query(RecipeORM).limit(50).all()
    idx = EmbeddingIndex()
    results = idx.search(recipes, sample_profile, top_n=10)
    assert len(results) > 0
    r, sim = results[0]
    assert isinstance(sim, float)
    assert 0.0 <= sim <= 1.0