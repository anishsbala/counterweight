from app.models import Claim
from app.services.evidence_retriever import EvidenceRetriever
from app.services.source_bank import SourceBankLoader


loader = SourceBankLoader()
retriever = EvidenceRetriever(loader.load())


def test_energy_claim_prefers_energy_sources():
    claim = Claim(
        text="Solar power is now one of the cheapest sources of new electricity generation in many regions.",
        sentence_index=0,
        claim_type="comparative",
        checkability_score=82.0,
        domain="energy",
        key_terms=["solar", "electricity", "generation", "cost"],
        hedged=False,
    )
    evidence = retriever.retrieve(claim)
    domains = {item.domain for item in evidence[:3]}
    assert "energy" in domains
    assert any(item.match_score >= 55 for item in evidence)
    assert any(item.tag_hits or item.phrase_hits for item in evidence)
