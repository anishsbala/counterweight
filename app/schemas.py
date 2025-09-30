from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VerifyArticleRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    article_text: str = Field(..., min_length=40)
    source_url: Optional[str] = None
    persist: bool = True


class ClaimResponse(BaseModel):
    text: str
    sentence_index: int
    claim_type: str
    checkability_score: float
    domain: str
    key_terms: List[str]
    hedged: bool


class EvidenceResponse(BaseModel):
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
    tag_hits: List[str]
    keyword_hits: List[str]
    phrase_hits: List[str]
    matched_numbers: List[str]
    signal_summary: str
    debug_factors: Dict[str, float]


class ClaimVerificationResponse(BaseModel):
    claim: str
    claim_type: str
    domain: str
    score: float
    confidence: float
    verdict: str
    evidence: List[EvidenceResponse]
    explanation: str
    reviewer_note: str
    debug_signals: Dict[str, float]


class VerdictCountsResponse(BaseModel):
    likely_supported: int
    mixed_support: int
    weak_support: int
    insufficient_evidence: int


class VerifyArticleResponse(BaseModel):
    article_id: int
    title: str
    source_url: Optional[str]
    article_domain: str
    overall_verdict: str
    claims: List[ClaimResponse]
    results: List[ClaimVerificationResponse]
    verdict_counts: VerdictCountsResponse
    report_summary: str
    elapsed_ms: int


class SourceSummaryResponse(BaseModel):
    slug: str
    title: str
    organization: str
    domain: str
    source_type: str
    authority_score: float
    url: str


class SourceDetailResponse(SourceSummaryResponse):
    snippet: str
    tags: List[str]


class ArticleListItemResponse(BaseModel):
    id: int
    title: str
    source_url: Optional[str]
    article_domain: str
    overall_verdict: str
    claim_count: int
    created_at: datetime


class EvidenceHistoryResponse(BaseModel):
    rank: int
    source_slug: str
    title: str
    organization: str
    domain: str
    source_type: str
    snippet: str
    url: str
    authority_score: float
    match_score: float
    relevance_score: float
    coverage_score: float
    authority_component: float
    signal_summary: str
    keyword_hits: List[str]
    tag_hits: List[str]
    phrase_hits: List[str]
    matched_numbers: List[str]


class ClaimHistoryResponse(BaseModel):
    id: int
    sentence_index: int
    claim_text: str
    claim_type: str
    checkability_score: float
    domain: str
    key_terms: List[str]
    hedged: bool
    verdict: str
    credibility_score: float
    confidence_score: float
    explanation: str
    reviewer_note: str
    evidence: List[EvidenceHistoryResponse]


class ArticleDetailResponse(BaseModel):
    id: int
    title: str
    source_url: Optional[str]
    article_text: str
    article_domain: str
    overall_verdict: str
    report_summary: str
    elapsed_ms: int
    created_at: datetime
    claims: List[ClaimHistoryResponse]


class AppStatsResponse(BaseModel):
    articles: int
    claims: int
    evaluations: int
    sources: int


class DomainBreakdownResponse(BaseModel):
    domain: str
    article_count: int
    source_count: int


class BenchmarkResponse(BaseModel):
    available: bool
    jobs: Optional[int] = None
    single_worker_seconds: Optional[float] = None
    four_worker_seconds: Optional[float] = None
    speedup: Optional[float] = None
    generated_at: Optional[datetime] = None
    notes: List[str]


class JobAcceptedResponse(BaseModel):
    job_id: str
    status: str
    status_url: str


class JobStatusBatchRequest(BaseModel):
    job_ids: List[UUID] = Field(..., min_length=1, max_length=100)


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    error: Optional[str] = None


class JobDetailResponse(BaseModel):
    job_id: str
    status: str
    attempts: int
    max_attempts: int
    worker_id: Optional[str] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
