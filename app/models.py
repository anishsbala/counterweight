from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Claim:
    text: str
    sentence_index: int
    claim_type: str
    checkability_score: float
    domain: str
    key_terms: List[str] = field(default_factory=list)
    hedged: bool = False
    normalized_text: str = ""


@dataclass
class SourceRecord:
    slug: str
    title: str
    url: str
    organization: str
    domain: str
    source_type: str
    snippet: str
    tags: List[str]
    authority_score: float


@dataclass
class EvidenceHit:
    slug: str
    title: str
    url: str
    organization: str
    domain: str
    source_type: str
    snippet: str
    authority_score: float
    match_score: float
    relevance_score: float
    coverage_score: float
    authority_component: float
    tag_hits: List[str] = field(default_factory=list)
    keyword_hits: List[str] = field(default_factory=list)
    phrase_hits: List[str] = field(default_factory=list)
    matched_numbers: List[str] = field(default_factory=list)
    signal_summary: str = ""
    debug_factors: Dict[str, float] = field(default_factory=dict)


@dataclass
class ClaimResult:
    claim: str
    claim_type: str
    domain: str
    score: float
    confidence: float
    verdict: str
    evidence: List[EvidenceHit]
    explanation: str
    reviewer_note: str
    debug_signals: Dict[str, float] = field(default_factory=dict)
