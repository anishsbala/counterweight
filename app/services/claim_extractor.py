import re
from typing import Dict, List, Tuple

from app.config import MAX_CLAIMS_PER_ARTICLE
from app.models import Claim
from app.services.article_parser import ArticleParser


class ClaimExtractor:
    def __init__(self) -> None:
        self.parser = ArticleParser()
        self._number_pattern = re.compile(r"\b\d+(?:\.\d+)?%?\b")
        self._date_pattern = re.compile(r"\b(?:19|20)\d{2}\b")
        self._measurement_pattern = re.compile(
            r"\b\d+(?:\.\d+)?\s*(?:million|billion|trillion|tons?|kg|gw|mw|kwh|mwh|percent|%)\b",
            re.IGNORECASE,
        )
        self._attribution_pattern = re.compile(
            r"\b(according to|researchers|analysts|experts|report|study|survey|data from|estimates?|officials|agency)\b",
            re.IGNORECASE,
        )
        self._comparative_pattern = re.compile(
            r"\b(more|less|higher|lower|largest|smallest|majority|minority|cheapest|fastest|slowest|declined|increased|dropped|rose|fell|grew|surpassed|outpaced)\b",
            re.IGNORECASE,
        )
        self._causal_pattern = re.compile(
            r"\b(caused|led to|resulted in|reduced|improved|worsened|boosted|drove|contributed to)\b",
            re.IGNORECASE,
        )
        self._forecast_pattern = re.compile(r"\b(will|projected|forecast|expected|likely to|set to)\b", re.IGNORECASE)
        self._factual_pattern = re.compile(
            r"\b(accounted for|represents?|made up|remains?|reached|hit|totaled|averaged|recorded|showed|shows|reported)\b",
            re.IGNORECASE,
        )
        self._quote_pattern = re.compile(r'".+?"')
        self._opinion_pattern = re.compile(
            r"\b(i think|we think|in my opinion|should|beautiful|terrible|great|amazing|clearly|obviously)\b",
            re.IGNORECASE,
        )
        self._hedge_pattern = re.compile(
            r"\b(may|might|could|appears to|seems to|suggests|possibly|perhaps|reportedly|some reports)\b",
            re.IGNORECASE,
        )
        self._entity_pattern = re.compile(r"\b(?:[A-Z][a-z]+|[A-Z]{2,})(?:\s+(?:[A-Z][a-z]+|[A-Z]{2,}))*\b")
        self._filler_starts = (
            "however",
            "meanwhile",
            "overall",
            "in addition",
            "for example",
            "for instance",
            "still",
        )
        self._stop_terms = {
            "according",
            "recent",
            "years",
            "report",
            "study",
            "researchers",
            "analysts",
            "experts",
            "reports",
            "claim",
            "claims",
            "article",
        }
        self._domain_keywords: Dict[str, Dict[str, int]] = {
            "energy": {
                "solar": 4,
                "wind": 4,
                "battery": 4,
                "storage": 4,
                "electricity": 4,
                "grid": 4,
                "renewable": 4,
                "power": 3,
                "generation": 3,
                "capacity": 3,
                "utility": 2,
            },
            "climate": {
                "climate": 5,
                "temperature": 4,
                "warming": 4,
                "emissions": 4,
                "carbon": 4,
                "greenhouse": 4,
                "sea": 2,
                "level": 2,
                "fossil": 2,
            },
            "health": {
                "health": 4,
                "disease": 4,
                "vaccine": 4,
                "obesity": 4,
                "mortality": 4,
                "hospital": 3,
                "covid": 4,
                "patients": 3,
                "insurance": 2,
            },
            "economics": {
                "inflation": 5,
                "gdp": 5,
                "economy": 4,
                "growth": 3,
                "recession": 4,
                "consumer": 3,
                "spending": 3,
                "trade": 3,
                "productivity": 2,
            },
            "labor": {
                "employment": 5,
                "wages": 4,
                "workers": 4,
                "jobs": 5,
                "unemployment": 5,
                "labor": 5,
                "payroll": 4,
                "earnings": 3,
            },
            "education": {
                "students": 5,
                "schools": 5,
                "graduation": 4,
                "college": 4,
                "education": 5,
                "enrollment": 4,
                "teachers": 3,
            },
            "demographics": {
                "population": 5,
                "households": 4,
                "birth": 4,
                "migration": 4,
                "county": 3,
                "census": 5,
                "residents": 3,
            },
            "technology": {
                "ai": 5,
                "software": 4,
                "chip": 4,
                "internet": 3,
                "broadband": 4,
                "model": 3,
                "compute": 4,
                "semiconductor": 4,
                "cloud": 3,
            },
        }

    def extract(self, article_text: str) -> List[Claim]:
        sentences = self.parser.split_sentences(article_text)
        ranked_claims: List[Tuple[float, Claim]] = []
        seen_signatures = set()

        for index, sentence in enumerate(sentences):
            cleaned = self._clean_sentence(sentence)
            if len(cleaned) < 35:
                continue

            normalized_text = self._normalize_for_signature(cleaned)
            if normalized_text in seen_signatures:
                continue

            score = self._checkability_score(cleaned)
            if score < 38.0:
                continue

            claim_type = self._claim_type(cleaned)
            domain = self._domain(cleaned)
            key_terms = self._key_terms(cleaned)
            hedged = bool(self._hedge_pattern.search(cleaned))
            claim = Claim(
                text=cleaned,
                sentence_index=index,
                claim_type=claim_type,
                checkability_score=round(min(score, 100.0), 1),
                domain=domain,
                key_terms=key_terms,
                hedged=hedged,
                normalized_text=normalized_text,
            )
            ranked_claims.append((score, claim))
            seen_signatures.add(normalized_text)

        ranked_claims.sort(key=lambda item: (-item[0], item[1].sentence_index))
        claims = [claim for _, claim in ranked_claims[:MAX_CLAIMS_PER_ARTICLE]]

        if claims:
            claims.sort(key=lambda item: item.sentence_index)
            return claims

        fallback: List[Claim] = []
        for index, sentence in enumerate(sentences[:MAX_CLAIMS_PER_ARTICLE]):
            cleaned = self._clean_sentence(sentence)
            if len(cleaned) < 35:
                continue
            fallback.append(
                Claim(
                    text=cleaned,
                    sentence_index=index,
                    claim_type="descriptive",
                    checkability_score=36.0,
                    domain=self._domain(cleaned),
                    key_terms=self._key_terms(cleaned),
                    hedged=bool(self._hedge_pattern.search(cleaned)),
                    normalized_text=self._normalize_for_signature(cleaned),
                )
            )
        return fallback

    def _clean_sentence(self, sentence: str) -> str:
        cleaned = sentence.strip().strip('"').strip()
        lowered = cleaned.lower()
        for filler in self._filler_starts:
            if lowered.startswith(f"{filler},"):
                cleaned = cleaned[len(filler) + 1 :].strip()
                break
        return cleaned

    def _checkability_score(self, sentence: str) -> float:
        score = 18.0
        if self._number_pattern.search(sentence):
            score += 18.0
        if self._date_pattern.search(sentence):
            score += 6.0
        if self._measurement_pattern.search(sentence):
            score += 8.0
        if self._attribution_pattern.search(sentence):
            score += 10.0
        if self._comparative_pattern.search(sentence):
            score += 14.0
        if self._causal_pattern.search(sentence):
            score += 12.0
        if self._forecast_pattern.search(sentence):
            score += 7.0
        if self._factual_pattern.search(sentence):
            score += 10.0
        entities = self._entity_pattern.findall(sentence)
        if entities:
            score += min(12.0, 4.0 + (len(entities) * 2.0))
        if len(sentence.split()) >= 10:
            score += 6.0
        if self._quote_pattern.search(sentence):
            score -= 8.0
        if self._hedge_pattern.search(sentence):
            score -= 5.0
        if self._opinion_pattern.search(sentence):
            score -= 20.0
        if sentence.endswith("?"):
            score -= 15.0
        return max(score, 0.0)

    def _claim_type(self, sentence: str) -> str:
        if self._causal_pattern.search(sentence):
            return "causal"
        if self._forecast_pattern.search(sentence):
            return "forecast"
        if self._comparative_pattern.search(sentence):
            return "comparative"
        if self._number_pattern.search(sentence):
            return "statistical"
        if self._attribution_pattern.search(sentence):
            return "attributed"
        return "descriptive"

    def _domain(self, sentence: str) -> str:
        lowered = sentence.lower()
        best_domain = "general"
        best_score = 0
        for domain, keywords in self._domain_keywords.items():
            score = 0
            for keyword, weight in keywords.items():
                if keyword in lowered:
                    score += weight
            if score > best_score:
                best_score = score
                best_domain = domain
        return best_domain

    def _key_terms(self, sentence: str) -> List[str]:
        words = []
        for raw in sentence.lower().replace("/", " ").replace("-", " ").split():
            token = "".join(ch for ch in raw if ch.isalnum())
            if len(token) < 4:
                continue
            if token in self._stop_terms:
                continue
            words.append(token)

        unique: List[str] = []
        for word in words:
            if word not in unique:
                unique.append(word)
        return unique[:8]

    def _normalize_for_signature(self, sentence: str) -> str:
        cleaned = sentence.lower()
        cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        pieces = [piece for piece in cleaned.split() if piece not in self._stop_terms]
        return " ".join(pieces)
