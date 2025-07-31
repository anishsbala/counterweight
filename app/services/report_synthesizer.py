from typing import Dict, List

from app.models import Claim, ClaimResult, EvidenceHit


class ReportSynthesizer:
    def synthesize_claim(self, claim: Claim, evidence: List[EvidenceHit]) -> ClaimResult:
        if not evidence:
            return ClaimResult(
                claim=claim.text,
                claim_type=claim.claim_type,
                domain=claim.domain,
                score=0.0,
                confidence=14.0,
                verdict="insufficient evidence",
                evidence=[],
                explanation="Counterweight could not find enough aligned evidence from the current source bank to justify a claim-level verdict.",
                reviewer_note="Add more domain-specific sources or narrow the claim wording.",
                debug_signals={"top_match": 0.0, "strong_hits": 0.0, "domain_matches": 0.0},
            )

        top = evidence[0]
        top_two = evidence[:2]
        top_three = evidence[:3]
        avg_top_two = sum(item.match_score for item in top_two) / len(top_two)
        avg_top_three = sum(item.match_score for item in top_three) / len(top_three)
        authority_avg = sum(item.authority_score for item in evidence) / len(evidence)
        domain_matches = sum(1 for item in evidence if item.domain == claim.domain)
        strong_hits = sum(1 for item in evidence if item.match_score >= 72.0)
        moderate_hits = sum(1 for item in evidence if item.match_score >= 56.0)
        phrase_hits = sum(len(item.phrase_hits) for item in evidence)
        number_hits = sum(len(item.matched_numbers) for item in evidence)

        credibility = (
            top.match_score * 0.48
            + avg_top_two * 0.18
            + avg_top_three * 0.08
            + (authority_avg * 15.0)
            + min(10.0, domain_matches * 2.5)
            + min(8.0, phrase_hits * 2.0)
            + min(6.0, number_hits * 2.0)
        )
        credibility = round(min(100.0, credibility), 1)

        confidence = 38.0
        confidence += min(20.0, strong_hits * 7.0 + moderate_hits * 2.5)
        confidence += min(16.0, len(evidence) * 4.0)
        confidence += min(12.0, domain_matches * 3.0)
        confidence += min(8.0, phrase_hits * 2.0)
        if claim.hedged:
            confidence -= 7.0
        confidence = round(max(8.0, min(100.0, confidence)), 1)

        verdict = self._verdict_from_signals(credibility, top.match_score, strong_hits, moderate_hits, phrase_hits)
        if self._needs_superlative_downgrade(claim, evidence):
            verdict = self._downgrade(verdict)
            credibility = round(max(0.0, credibility - 7.0), 1)

        explanation = self._build_explanation(claim, evidence, verdict, credibility)
        reviewer_note = self._reviewer_note(claim, evidence, verdict)
        debug_signals: Dict[str, float] = {
            "top_match": round(top.match_score, 1),
            "avg_top_two": round(avg_top_two, 1),
            "avg_top_three": round(avg_top_three, 1),
            "authority_avg": round(authority_avg, 2),
            "strong_hits": float(strong_hits),
            "moderate_hits": float(moderate_hits),
            "domain_matches": float(domain_matches),
            "phrase_hits": float(phrase_hits),
            "number_hits": float(number_hits),
        }

        return ClaimResult(
            claim=claim.text,
            claim_type=claim.claim_type,
            domain=claim.domain,
            score=credibility,
            confidence=confidence,
            verdict=verdict,
            evidence=evidence,
            explanation=explanation,
            reviewer_note=reviewer_note,
            debug_signals=debug_signals,
        )

    def summarize_article(self, results: List[ClaimResult]) -> str:
        if not results:
            return "No checkable claims were extracted from this article."

        counts = self._counts(results)
        return (
            f"Verification finished for {len(results)} claims. "
            f"{counts['likely supported']} looked likely supported, "
            f"{counts['mixed support']} had mixed support, "
            f"{counts['weak support']} had weak support, and "
            f"{counts['insufficient evidence']} had insufficient evidence."
        )

    def verdict_counts(self, results: List[ClaimResult]) -> Dict[str, int]:
        counts = self._counts(results)
        return {
            "likely_supported": counts["likely supported"],
            "mixed_support": counts["mixed support"],
            "weak_support": counts["weak support"],
            "insufficient_evidence": counts["insufficient evidence"],
        }

    def overall_verdict(self, results: List[ClaimResult]) -> str:
        if not results:
            return "insufficient evidence"
        counts = self._counts(results)
        if counts["likely supported"] >= max(counts["mixed support"], counts["weak support"]):
            return "likely supported"
        if counts["mixed support"] > 0:
            return "mixed support"
        if counts["weak support"] > 0:
            return "weak support"
        return "insufficient evidence"

    def _counts(self, results: List[ClaimResult]) -> Dict[str, int]:
        counts = {
            "likely supported": 0,
            "mixed support": 0,
            "weak support": 0,
            "insufficient evidence": 0,
        }
        for result in results:
            counts[result.verdict] += 1
        return counts

    def _verdict_from_signals(
        self,
        credibility: float,
        top_match: float,
        strong_hits: int,
        moderate_hits: int,
        phrase_hits: int,
    ) -> str:
        if top_match < 35.0:
            return "insufficient evidence"
        if credibility >= 70.0 and strong_hits >= 1:
            return "likely supported"
        if credibility >= 54.0 and (moderate_hits >= 2 or phrase_hits >= 1):
            return "mixed support"
        if credibility >= 38.0:
            return "weak support"
        return "insufficient evidence"

    def _needs_superlative_downgrade(self, claim: Claim, evidence: List[EvidenceHit]) -> bool:
        lowered = claim.text.lower()
        strong_words = ("all", "every", "never", "always", "only", "in history", "cheapest", "largest")
        if not any(word in lowered for word in strong_words):
            return False
        return not any(hit.phrase_hits or hit.matched_numbers for hit in evidence[:2])

    def _downgrade(self, verdict: str) -> str:
        order = ["likely supported", "mixed support", "weak support", "insufficient evidence"]
        try:
            index = order.index(verdict)
        except ValueError:
            return verdict
        return order[min(index + 1, len(order) - 1)]

    def _build_explanation(self, claim: Claim, evidence: List[EvidenceHit], verdict: str, score: float) -> str:
        organizations = ", ".join(item.organization for item in evidence[:3])
        strongest = evidence[0]
        caution = ""
        if claim.hedged:
            caution = " The original sentence is hedged, so the verdict is intentionally conservative."
        if self._needs_superlative_downgrade(claim, evidence):
            caution += " The wording is broader than the supporting evidence, so Counterweight downgraded the verdict one step."
        return (
            f"This {claim.claim_type} claim falls in the {claim.domain} domain. "
            f"The best-aligned evidence came from {organizations}. "
            f"The top hit scored {strongest.match_score:.1f} with signals like {strongest.signal_summary}. "
            f"Taken together, those sources place the claim at {verdict} ({score:.1f}/100).{caution}"
        )

    def _reviewer_note(self, claim: Claim, evidence: List[EvidenceHit], verdict: str) -> str:
        if verdict == "likely supported":
            return "Strong domain alignment and multiple credible source matches."
        if verdict == "mixed support":
            return "Evidence is relevant, but the claim wording is broader or stronger than the source summaries."
        if verdict == "weak support":
            return "There is some alignment, but the retrieval signals are still shallow or incomplete."
        return "The current source bank did not supply enough targeted support for this wording."
