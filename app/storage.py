import json
from typing import Dict, List

from app.db import fetch_all, fetch_one, get_db_connection
from app.models import Claim, ClaimResult, SourceRecord


class CounterweightStore:
    def upsert_sources(self, sources: List[SourceRecord]) -> None:
        if not sources:
            return

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for source in sources:
                    cur.execute(
                        """
                        INSERT INTO sources (
                            slug, title, url, organization, domain, source_type, snippet, tags, authority_score
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (slug) DO UPDATE SET
                            title = EXCLUDED.title,
                            url = EXCLUDED.url,
                            organization = EXCLUDED.organization,
                            domain = EXCLUDED.domain,
                            source_type = EXCLUDED.source_type,
                            snippet = EXCLUDED.snippet,
                            tags = EXCLUDED.tags,
                            authority_score = EXCLUDED.authority_score,
                            updated_at = NOW()
                        """,
                        (
                            source.slug,
                            source.title,
                            source.url,
                            source.organization,
                            source.domain,
                            source.source_type,
                            source.snippet,
                            source.tags,
                            source.authority_score,
                        ),
                    )

    def get_sources(self) -> List[SourceRecord]:
        rows = fetch_all(
            """
            SELECT slug, title, url, organization, domain, source_type, snippet, tags, authority_score
            FROM sources
            ORDER BY authority_score DESC, title ASC
            """
        )
        return [
            SourceRecord(
                slug=row["slug"],
                title=row["title"],
                url=row["url"],
                organization=row["organization"],
                domain=row["domain"],
                source_type=row["source_type"],
                snippet=row["snippet"],
                tags=list(row["tags"] or []),
                authority_score=float(row["authority_score"]),
            )
            for row in rows
        ]

    def get_source_detail(self, slug: str) -> Dict | None:
        row = fetch_one(
            """
            SELECT slug, title, url, organization, domain, source_type, snippet, tags, authority_score
            FROM sources
            WHERE slug = %s
            """,
            (slug,),
        )
        if row is None:
            return None
        row["authority_score"] = float(row["authority_score"])
        row["tags"] = list(row["tags"] or [])
        return row

    def save_verification_run(
        self,
        title: str,
        source_url: str | None,
        article_text: str,
        article_domain: str,
        overall_verdict: str,
        report_summary: str,
        elapsed_ms: int,
        claims: List[Claim],
        results: List[ClaimResult],
    ) -> int:
        claim_map = {result.claim: result for result in results}

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO articles (title, source_url, article_text, article_domain, overall_verdict, report_summary, elapsed_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (title, source_url, article_text, article_domain, overall_verdict, report_summary, elapsed_ms),
                )
                article_id = cur.fetchone()["id"]

                for claim in claims:
                    cur.execute(
                        """
                        INSERT INTO claims (
                            article_id,
                            sentence_index,
                            claim_text,
                            normalized_text,
                            claim_type,
                            checkability_score,
                            domain,
                            key_terms,
                            hedged
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            article_id,
                            claim.sentence_index,
                            claim.text,
                            claim.normalized_text,
                            claim.claim_type,
                            claim.checkability_score,
                            claim.domain,
                            claim.key_terms,
                            claim.hedged,
                        ),
                    )
                    claim_id = cur.fetchone()["id"]
                    result = claim_map[claim.text]
                    cur.execute(
                        """
                        INSERT INTO claim_evaluations (
                            claim_id,
                            verdict,
                            credibility_score,
                            confidence_score,
                            explanation,
                            reviewer_note,
                            evidence_count,
                            top_source_slugs
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            claim_id,
                            result.verdict,
                            result.score,
                            result.confidence,
                            result.explanation,
                            result.reviewer_note,
                            len(result.evidence),
                            [item.slug for item in result.evidence],
                        ),
                    )
                    evaluation_id = cur.fetchone()["id"]

                    for rank, evidence in enumerate(result.evidence, start=1):
                        cur.execute(
                            """
                            INSERT INTO evaluation_evidence (
                                evaluation_id,
                                source_slug,
                                evidence_rank,
                                match_score,
                                relevance_score,
                                coverage_score,
                                authority_component,
                                signal_summary,
                                keyword_hits,
                                tag_hits,
                                phrase_hits,
                                matched_numbers,
                                evidence_snapshot
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                evaluation_id,
                                evidence.slug,
                                rank,
                                evidence.match_score,
                                evidence.relevance_score,
                                evidence.coverage_score,
                                evidence.authority_component,
                                evidence.signal_summary,
                                evidence.keyword_hits,
                                evidence.tag_hits,
                                evidence.phrase_hits,
                                evidence.matched_numbers,
                                json.dumps(
                                    {
                                        "title": evidence.title,
                                        "url": evidence.url,
                                        "organization": evidence.organization,
                                        "domain": evidence.domain,
                                        "source_type": evidence.source_type,
                                        "snippet": evidence.snippet,
                                        "authority_score": evidence.authority_score,
                                    }
                                ),
                            ),
                        )

        return article_id

    def list_articles(self, limit: int = 25) -> List[Dict]:
        return fetch_all(
            """
            SELECT
                a.id,
                a.title,
                a.source_url,
                a.article_domain,
                a.overall_verdict,
                a.created_at,
                COUNT(c.id) AS claim_count
            FROM articles a
            LEFT JOIN claims c ON c.article_id = a.id
            GROUP BY a.id
            ORDER BY a.created_at DESC
            LIMIT %s
            """,
            (limit,),
        )

    def get_article_detail(self, article_id: int) -> Dict | None:
        article = fetch_one(
            """
            SELECT id, title, source_url, article_text, article_domain, overall_verdict, report_summary, elapsed_ms, created_at
            FROM articles
            WHERE id = %s
            """,
            (article_id,),
        )
        if article is None:
            return None

        claim_rows = fetch_all(
            """
            SELECT
                c.id,
                c.sentence_index,
                c.claim_text,
                c.claim_type,
                c.checkability_score,
                c.domain,
                c.key_terms,
                c.hedged,
                e.verdict,
                e.credibility_score,
                e.confidence_score,
                e.explanation,
                e.reviewer_note
            FROM claims c
            JOIN claim_evaluations e ON e.claim_id = c.id
            WHERE c.article_id = %s
            ORDER BY c.sentence_index ASC, c.id ASC
            """,
            (article_id,),
        )

        claims = []
        for row in claim_rows:
            evidence_rows = fetch_all(
                """
                SELECT
                    ee.evidence_rank AS rank,
                    ee.source_slug,
                    ee.match_score,
                    ee.relevance_score,
                    ee.coverage_score,
                    ee.authority_component,
                    ee.signal_summary,
                    ee.keyword_hits,
                    ee.tag_hits,
                    ee.phrase_hits,
                    ee.matched_numbers,
                    ee.evidence_snapshot,
                    s.title,
                    s.url
                FROM evaluation_evidence ee
                LEFT JOIN sources s ON s.slug = ee.source_slug
                JOIN claim_evaluations ce ON ce.id = ee.evaluation_id
                WHERE ce.claim_id = %s
                ORDER BY ee.evidence_rank ASC
                """,
                (row["id"],),
            )
            evidence = []
            for evidence_row in evidence_rows:
                snapshot = evidence_row["evidence_snapshot"]
                if isinstance(snapshot, str):
                    snapshot = json.loads(snapshot)
                evidence.append(
                    {
                        "rank": evidence_row["rank"],
                        "source_slug": evidence_row["source_slug"],
                        "title": evidence_row["title"] or snapshot["title"],
                        "organization": snapshot.get("organization", evidence_row["title"] or snapshot["title"]),
                        "domain": snapshot.get("domain", "general"),
                        "source_type": snapshot.get("source_type", "stored"),
                        "snippet": snapshot.get("snippet", "Stored evidence snapshot"),
                        "url": evidence_row["url"] or snapshot["url"],
                        "authority_score": float(snapshot.get("authority_score", 0.0)),
                        "match_score": float(evidence_row["match_score"]),
                        "relevance_score": float(evidence_row["relevance_score"]),
                        "coverage_score": float(evidence_row["coverage_score"]),
                        "authority_component": float(evidence_row["authority_component"]),
                        "signal_summary": evidence_row["signal_summary"],
                        "keyword_hits": list(evidence_row["keyword_hits"] or []),
                        "tag_hits": list(evidence_row["tag_hits"] or []),
                        "phrase_hits": list(evidence_row["phrase_hits"] or []),
                        "matched_numbers": list(evidence_row["matched_numbers"] or []),
                    }
                )

            claims.append(
                {
                    "id": row["id"],
                    "sentence_index": row["sentence_index"],
                    "claim_text": row["claim_text"],
                    "claim_type": row["claim_type"],
                    "checkability_score": float(row["checkability_score"]),
                    "domain": row["domain"],
                    "key_terms": list(row["key_terms"] or []),
                    "hedged": bool(row["hedged"]),
                    "verdict": row["verdict"],
                    "credibility_score": float(row["credibility_score"]),
                    "confidence_score": float(row["confidence_score"]),
                    "explanation": row["explanation"],
                    "reviewer_note": row["reviewer_note"],
                    "evidence": evidence,
                }
            )

        return {
            "id": article["id"],
            "title": article["title"],
            "source_url": article["source_url"],
            "article_text": article["article_text"],
            "article_domain": article["article_domain"],
            "overall_verdict": article["overall_verdict"],
            "report_summary": article["report_summary"],
            "elapsed_ms": int(article["elapsed_ms"] or 0),
            "created_at": article["created_at"],
            "claims": claims,
        }

    def get_stats(self) -> Dict[str, int]:
        return {
            "articles": int(fetch_one("SELECT COUNT(*) AS count FROM articles")["count"]),
            "claims": int(fetch_one("SELECT COUNT(*) AS count FROM claims")["count"]),
            "evaluations": int(fetch_one("SELECT COUNT(*) AS count FROM claim_evaluations")["count"]),
            "sources": int(fetch_one("SELECT COUNT(*) AS count FROM sources")["count"]),
        }

    def get_domain_breakdown(self) -> List[Dict]:
        rows = fetch_all(
            """
            WITH article_domains AS (
                SELECT article_domain AS domain, COUNT(*) AS article_count
                FROM articles
                GROUP BY article_domain
            ),
            source_domains AS (
                SELECT domain, COUNT(*) AS source_count
                FROM sources
                GROUP BY domain
            )
            SELECT
                COALESCE(ad.domain, sd.domain) AS domain,
                COALESCE(ad.article_count, 0) AS article_count,
                COALESCE(sd.source_count, 0) AS source_count
            FROM article_domains ad
            FULL OUTER JOIN source_domains sd ON ad.domain = sd.domain
            ORDER BY domain ASC
            """
        )
        return rows
