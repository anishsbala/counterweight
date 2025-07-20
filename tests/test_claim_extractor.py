from app.services.claim_extractor import ClaimExtractor


extractor = ClaimExtractor()


def test_extracts_multiple_claims():
    article = (
        "Solar power accounted for most new generation capacity added globally in recent years. "
        "Battery storage costs declined over time, making grid-scale storage more practical. "
        "The article ends with a broad opinion about the energy transition."
    )
    claims = extractor.extract(article)
    assert len(claims) >= 2
    assert claims[0].domain == "energy"


def test_sets_claim_type_and_score():
    article = "According to researchers, unemployment fell 2% while wages increased across several sectors."
    claims = extractor.extract(article)
    assert claims[0].claim_type in {"statistical", "comparative", "attributed"}
    assert claims[0].checkability_score >= 50
    assert claims[0].key_terms
