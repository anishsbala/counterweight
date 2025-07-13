import re
from typing import Iterable, List, Tuple

from app.config import TOP_EVIDENCE_PER_CLAIM
from app.models import Claim, EvidenceHit, SourceRecord


class EvidenceRetriever:
    def __init__(self, sources: List[SourceRecord]) -> None:
        self.sources = sources
        self._number_pattern = re.compile(r"\b\d+(?:\.\d+)?%?\b")
        self._stop_words = {
            "the",
            "and",
            "that",
            "with",
            "from",
            "have",
            "this",
            "their",
            "been",
            "were",
            "into",
            "than",
            "many",
            "more",
            "most",
            "some",
            "also",
            "made",
            "making",
            "over",
            "across",
            "using",
            "used",
            "showed",
            "shows",
            "about",
            "which",
            "while",
            "where",
            "because",
            "during",
            "after",
            "before",
        }
        self._canonical = {
            "cheapest": "cost",
            "cheap": "cost",
            "cheaper": "cost",
            "costs": "cost",
            "pricing": "cost",
            "prices": "cost",
            "jobs": "employment",
            "workers": "labor",
            "wages": "wage",
            "earnings": "wage",
            "batteries": "battery",
            "renewables": "renewable",
            "emissions": "emission",
            "students": "student",
            "schools": "school",
            "models": "model",
            "chips": "chip",
            "temperatures": "temperature",
            "hospitals": "hospital",
        }
        self._related_domains = {
            ("energy", "climate"),
            ("climate", "energy"),
            ("economics", "labor"),
            ("labor", "economics"),
            ("education", "demographics"),
            ("demographics", "education"),
            ("technology", "economics"),
            ("economics", "technology"),
        }

    def retrieve(self, claim: Claim) -> List[EvidenceHit]:
        scored_hits: List[Tuple[float, EvidenceHit]] = []
        claim_tokens = self._tokens(claim.text)
        claim_token_set = set(claim_tokens)
        claim_numbers = set(self._number_pattern.findall(claim.text))
        claim_phrases = self._phrases(claim_tokens)
        claim_text_norm = self._normalize_text(claim.text)

        for source in self.sources:
            total_score, hit = self._score_source(
                claim=claim,
                source=source,
                claim_token_set=claim_token_set,
                claim_numbers=claim_numbers,
                claim_phrases=claim_phrases,
                claim_text_norm=claim_text_norm,
            )
            if total_score < 26.0:
                continue
            scored_hits.append((total_score, hit))

        scored_hits.sort(
            key=lambda item: (
                -item[0],
                -item[1].relevance_score,
                -item[1].coverage_score,
                -item[1].authority_score,
                item[1].title,
            )
        )
        return [hit for _, hit in scored_hits[:TOP_EVIDENCE_PER_CLAIM]]

    def _score_source(
        self,
        claim: Claim,
        source: SourceRecord,
        claim_token_set: set[str],
        claim_numbers: set[str],
        claim_phrases: List[str],
        claim_text_norm: str,
    ) -> Tuple[float, EvidenceHit]:
        source_text = f"{source.title} {source.organization} {source.snippet} {' '.join(source.tags)}"
        source_text_norm = self._normalize_text(source_text)
        source_tokens = set(self._tokens(source_text))
        keyword_hits = sorted(claim_token_set & source_tokens)
        tag_hits = sorted({self._canonicalize(tag) for tag in source.tags if self._canonicalize(tag) in claim_token_set})
        phrase_hits = [phrase for phrase in claim_phrases if phrase in source_text_norm]
        source_numbers = set(self._number_pattern.findall(source_text))
        matched_numbers = sorted(claim_numbers & source_numbers)

        domain_score = 0.0
        if claim.domain == source.domain:
            domain_score = 28.0
        elif (claim.domain, source.domain) in self._related_domains:
            domain_score = 10.0
        elif claim.domain == "general":
            domain_score = 4.0

        keyword_score = min(len(keyword_hits) * 6.5, 26.0)
        tag_score = min(len(tag_hits) * 8.0, 24.0)
        phrase_score = min(len(phrase_hits) * 10.0, 24.0)
        number_score = min(len(matched_numbers) * 6.0, 12.0)
        authority_component = round(source.authority_score * 18.0, 1)
        claim_type_bonus = self._claim_type_bonus(claim, source)
        key_term_bonus = min(sum(1 for term in claim.key_terms if self._canonicalize(term) in source_tokens) * 2.5, 10.0)
        text_subset_bonus = 4.0 if claim_text_norm[:80] and claim_text_norm[:80] in source_text_norm else 0.0

        total_score = (
            domain_score
            + keyword_score
            + tag_score
            + phrase_score
            + number_score
            + authority_component
            + claim_type_bonus
            + key_term_bonus
            + text_subset_bonus
        )

        if not keyword_hits and not tag_hits and domain_score < 20.0 and phrase_score == 0.0:
            total_score -= 18.0
        if claim.hedged:
            total_score -= 3.5

        relevance_score = round(min(100.0, keyword_score + tag_score + phrase_score + key_term_bonus + text_subset_bonus), 1)
        coverage_score = round(
            min(100.0, domain_score + len(keyword_hits) * 4.0 + len(tag_hits) * 4.0 + len(phrase_hits) * 5.0),
            1,
        )
        match_score = round(min(100.0, total_score), 1)
        signal_summary = self._build_signal_summary(claim.domain, tag_hits, keyword_hits, phrase_hits, matched_numbers, source)
        debug_factors = {
            "domain_score": round(domain_score, 1),
            "keyword_score": round(keyword_score, 1),
            "tag_score": round(tag_score, 1),
            "phrase_score": round(phrase_score, 1),
            "number_score": round(number_score, 1),
            "authority_component": authority_component,
            "claim_type_bonus": round(claim_type_bonus, 1),
            "key_term_bonus": round(key_term_bonus, 1),
        }

        hit = EvidenceHit(
            slug=source.slug,
            title=source.title,
            url=source.url,
            organization=source.organization,
            domain=source.domain,
            source_type=source.source_type,
            snippet=source.snippet,
            authority_score=source.authority_score,
            match_score=match_score,
            relevance_score=relevance_score,
            coverage_score=coverage_score,
            authority_component=authority_component,
            tag_hits=tag_hits,
            keyword_hits=keyword_hits[:8],
            phrase_hits=phrase_hits[:4],
            matched_numbers=matched_numbers,
            signal_summary=signal_summary,
            debug_factors=debug_factors,
        )
        return match_score, hit

    def _claim_type_bonus(self, claim: Claim, source: SourceRecord) -> float:
        tags = {self._canonicalize(tag) for tag in source.tags}
        if claim.claim_type == "statistical":
            if {"data", "statistics", "dashboard", "report"} & tags:
                return 8.0
        elif claim.claim_type == "causal":
            if {"research", "analysis", "study"} & tags:
                return 7.0
        elif claim.claim_type == "forecast":
            if {"forecast", "outlook", "projection"} & tags:
                return 7.0
        elif claim.claim_type == "comparative":
            if {"comparative", "cost", "trend", "analysis"} & tags:
                return 7.0
        elif claim.claim_type == "attributed":
            if {"report", "analysis", "research", "study"} & tags:
                return 5.0
        return 0.0

    def _build_signal_summary(
        self,
        claim_domain: str,
        tag_hits: List[str],
        keyword_hits: List[str],
        phrase_hits: List[str],
        matched_numbers: List[str],
        source: SourceRecord,
    ) -> str:
        parts = []
        if source.domain == claim_domain:
            parts.append(f"same domain ({claim_domain})")
        if tag_hits:
            parts.append("tag overlap: " + ", ".join(tag_hits[:4]))
        if keyword_hits:
            parts.append("keyword overlap: " + ", ".join(keyword_hits[:4]))
        if phrase_hits:
            parts.append("phrase overlap: " + ", ".join(phrase_hits[:2]))
        if matched_numbers:
            parts.append("matched numbers: " + ", ".join(matched_numbers[:2]))
        parts.append(f"authority {source.authority_score:.2f}")
        parts.append(source.source_type)
        return "; ".join(parts)

    def _tokens(self, text: str) -> List[str]:
        tokens: List[str] = []
        for piece in text.lower().replace("/", " ").replace("-", " ").split():
            cleaned = "".join(ch for ch in piece if ch.isalnum())
            if len(cleaned) < 3:
                continue
            canonical = self._canonicalize(cleaned)
            if canonical in self._stop_words:
                continue
            tokens.append(canonical)
        return tokens

    def _phrases(self, tokens: Iterable[str]) -> List[str]:
        tokens = list(tokens)
        phrases: List[str] = []
        for size in (2, 3):
            for index in range(len(tokens) - size + 1):
                phrase = " ".join(tokens[index : index + size])
                if len(phrase) >= 8:
                    phrases.append(phrase)
        unique: List[str] = []
        for phrase in phrases:
            if phrase not in unique:
                unique.append(phrase)
        return unique[:8]

    def _normalize_text(self, text: str) -> str:
        return " ".join(self._tokens(text))

    def _canonicalize(self, token: str) -> str:
        return self._canonical.get(token, token)
