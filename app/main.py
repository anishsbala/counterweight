import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    APP_NAME,
    APP_VERSION,
    AUTO_INIT_DB,
    CORS_ORIGINS,
    DEFAULT_ARTICLE_LIMIT,
    SEED_SOURCE_BANK,
    STATIC_DIR,
    TESTING,
)
from app.db import run_sql_file, wait_for_database
from app.jobs import JobService
from app.schemas import (
    AppStatsResponse,
    ArticleDetailResponse,
    ArticleListItemResponse,
    BenchmarkResponse,
    ClaimResponse,
    ClaimVerificationResponse,
    DomainBreakdownResponse,
    EvidenceResponse,
    JobAcceptedResponse,
    JobDetailResponse,
    JobStatusBatchRequest,
    JobStatusResponse,
    SourceDetailResponse,
    SourceSummaryResponse,
    VerdictCountsResponse,
    VerifyArticleRequest,
    VerifyArticleResponse,
)
from app.services.benchmark import BenchmarkService
from app.services.claim_extractor import ClaimExtractor
from app.services.evidence_retriever import EvidenceRetriever
from app.services.report_synthesizer import ReportSynthesizer
from app.services.source_bank import SourceBankLoader
from app.storage import CounterweightStore

store = CounterweightStore()
claim_extractor = ClaimExtractor()
report_synthesizer = ReportSynthesizer()
benchmark_service = BenchmarkService()
source_loader = SourceBankLoader()
source_cache = source_loader.load() if TESTING else []
retriever = EvidenceRetriever(source_cache)
job_service = JobService()


@asynccontextmanager
async def lifespan(_: FastAPI):
    global source_cache, retriever
    if not TESTING:
        wait_for_database()
        if AUTO_INIT_DB:
            run_sql_file(Path("sql/init.sql"))
        if SEED_SOURCE_BANK:
            store.upsert_sources(source_loader.load())
        source_cache = store.get_sources()
        retriever = EvidenceRetriever(source_cache)
        job_service.recover_queued_jobs()
    yield


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/benchmark", response_model=BenchmarkResponse)
def benchmark() -> BenchmarkResponse:
    return benchmark_service.get_summary()


@app.post("/jobs", response_model=JobAcceptedResponse, status_code=202)
def create_job(payload: VerifyArticleRequest) -> JobAcceptedResponse:
    queued_payload = payload.model_copy(update={"persist": True}).model_dump(mode="json")
    return JobAcceptedResponse(**job_service.create_job(queued_payload))


@app.get("/jobs", response_model=List[JobDetailResponse])
def list_jobs(limit: int = Query(50, ge=1, le=100)) -> List[JobDetailResponse]:
    return [JobDetailResponse(**row) for row in job_service.list_jobs(limit)]


@app.post("/jobs/statuses", response_model=List[JobStatusResponse])
def get_job_statuses(payload: JobStatusBatchRequest) -> List[JobStatusResponse]:
    requested_ids = [str(job_id) for job_id in payload.job_ids]
    rows = job_service.job_statuses(requested_ids)
    statuses = {row["job_id"]: row for row in rows}
    return [
        JobStatusResponse(**statuses[job_id]) for job_id in requested_ids if job_id in statuses
    ]


@app.get("/jobs/{job_id}", response_model=JobDetailResponse)
def get_job(job_id: str) -> JobDetailResponse:
    row = job_service.get_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobDetailResponse(**row)


@app.get("/sources", response_model=List[SourceSummaryResponse])
def list_sources() -> List[SourceSummaryResponse]:
    sources = source_loader.load() if TESTING else store.get_sources()
    return [
        SourceSummaryResponse(
            slug=item.slug,
            title=item.title,
            organization=item.organization,
            domain=item.domain,
            source_type=item.source_type,
            authority_score=item.authority_score,
            url=item.url,
        )
        for item in sources
    ]


@app.get("/sources/{slug}", response_model=SourceDetailResponse)
def get_source(slug: str) -> SourceDetailResponse:
    if TESTING:
        row = next((item for item in source_loader.load() if item.slug == slug), None)
        if row is None:
            raise HTTPException(status_code=404, detail="Source not found.")
        return SourceDetailResponse(
            slug=row.slug,
            title=row.title,
            organization=row.organization,
            domain=row.domain,
            source_type=row.source_type,
            authority_score=row.authority_score,
            url=row.url,
            snippet=row.snippet,
            tags=row.tags,
        )

    row = store.get_source_detail(slug)
    if row is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    return SourceDetailResponse(**row)


@app.get("/stats", response_model=AppStatsResponse)
def stats() -> AppStatsResponse:
    if TESTING:
        return AppStatsResponse(articles=0, claims=0, evaluations=0, sources=len(source_loader.load()))
    return AppStatsResponse(**store.get_stats())


@app.get("/domains", response_model=List[DomainBreakdownResponse])
def domains() -> List[DomainBreakdownResponse]:
    if TESTING:
        sources = source_loader.load()
        domain_counts: Dict[str, int] = {}
        for item in sources:
            domain_counts[item.domain] = domain_counts.get(item.domain, 0) + 1
        return [
            DomainBreakdownResponse(domain=domain, article_count=0, source_count=count)
            for domain, count in sorted(domain_counts.items())
        ]
    return [DomainBreakdownResponse(**row) for row in store.get_domain_breakdown()]


@app.post("/verify", response_model=VerifyArticleResponse)
def verify_article(payload: VerifyArticleRequest) -> VerifyArticleResponse:
    started = time.perf_counter()
    global source_cache, retriever
    if not retriever.sources:
        source_cache = source_loader.load() if TESTING else store.get_sources()
        retriever = EvidenceRetriever(source_cache)

    claims = claim_extractor.extract(payload.article_text)
    if not claims:
        raise HTTPException(status_code=400, detail="Could not extract any checkable claims from the article.")

    results = []
    for claim in claims:
        evidence = retriever.retrieve(claim)
        results.append(report_synthesizer.synthesize_claim(claim, evidence))

    article_domain = _article_domain(claims)
    verdict_counts = report_synthesizer.verdict_counts(results)
    report_summary = report_synthesizer.summarize_article(results)
    overall_verdict = report_synthesizer.overall_verdict(results)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    article_id = 0
    if not TESTING and payload.persist:
        article_id = store.save_verification_run(
            title=payload.title,
            source_url=payload.source_url,
            article_text=payload.article_text,
            article_domain=article_domain,
            overall_verdict=overall_verdict,
            report_summary=report_summary,
            elapsed_ms=elapsed_ms,
            claims=claims,
            results=results,
        )

    return VerifyArticleResponse(
        article_id=article_id,
        title=payload.title,
        source_url=payload.source_url,
        article_domain=article_domain,
        overall_verdict=overall_verdict,
        claims=[
            ClaimResponse(
                text=item.text,
                sentence_index=item.sentence_index,
                claim_type=item.claim_type,
                checkability_score=item.checkability_score,
                domain=item.domain,
                key_terms=item.key_terms,
                hedged=item.hedged,
            )
            for item in claims
        ],
        results=[
            ClaimVerificationResponse(
                claim=item.claim,
                claim_type=item.claim_type,
                domain=item.domain,
                score=item.score,
                confidence=item.confidence,
                verdict=item.verdict,
                evidence=[
                    EvidenceResponse(
                        slug=evidence.slug,
                        title=evidence.title,
                        url=evidence.url,
                        organization=evidence.organization,
                        domain=evidence.domain,
                        source_type=evidence.source_type,
                        snippet=evidence.snippet,
                        authority_score=evidence.authority_score,
                        match_score=evidence.match_score,
                        relevance_score=evidence.relevance_score,
                        coverage_score=evidence.coverage_score,
                        authority_component=evidence.authority_component,
                        tag_hits=evidence.tag_hits,
                        keyword_hits=evidence.keyword_hits,
                        phrase_hits=evidence.phrase_hits,
                        matched_numbers=evidence.matched_numbers,
                        signal_summary=evidence.signal_summary,
                        debug_factors=evidence.debug_factors,
                    )
                    for evidence in item.evidence
                ],
                explanation=item.explanation,
                reviewer_note=item.reviewer_note,
                debug_signals=item.debug_signals,
            )
            for item in results
        ],
        verdict_counts=VerdictCountsResponse(**verdict_counts),
        report_summary=report_summary,
        elapsed_ms=elapsed_ms,
    )


@app.get("/articles", response_model=List[ArticleListItemResponse])
def list_articles(limit: int = Query(DEFAULT_ARTICLE_LIMIT, ge=1, le=100)) -> List[ArticleListItemResponse]:
    if TESTING:
        return []
    return [ArticleListItemResponse(**row) for row in store.list_articles(limit=limit)]


@app.get("/articles/{article_id}", response_model=ArticleDetailResponse)
def get_article(article_id: int) -> ArticleDetailResponse:
    if TESTING:
        raise HTTPException(status_code=404, detail="Article not found.")
    article = store.get_article_detail(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found.")
    return ArticleDetailResponse(**article)


@app.get("/articles/{article_id}/export")
def export_article(article_id: int):
    if TESTING:
        raise HTTPException(status_code=404, detail="Article not found.")
    article = store.get_article_detail(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found.")
    return JSONResponse(article)


def _article_domain(claims) -> str:
    counts: Dict[str, int] = {}
    for claim in claims:
        counts[claim.domain] = counts.get(claim.domain, 0) + 1
    if not counts:
        return "general"
    return max(counts.items(), key=lambda item: item[1])[0]
