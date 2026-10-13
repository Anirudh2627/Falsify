"""Evidence analysis.

For every retrieved source, produce a structured :class:`EvidenceAssessment`:
does it discuss the claim, support it, contradict it, how relevant is it,
how trustworthy is the source, is it temporally valid, and is the evidence
direct or inferred.

The deterministic analyzer (numeric comparison + lexical stance cues +
domain-based source quality) always runs.  When an LLM is injected its
judgement is merged in -- but hard numeric facts extracted deterministically
are never overridden by the LLM, and irrelevant sources can never be talked
into a stance by either path.
"""

from __future__ import annotations

import re

from app.falsify.analysis.numerics import best_comparison, extract_numeric_observations
from app.falsify.analysis.source_quality import SourceQualityScorer
from app.falsify.config import EngineConfig
from app.falsify.llm.base import LLMProvider
from app.falsify.llm.provider import NullLLM
from app.falsify.logging_utils import log_event
from app.falsify.models import Claim, ClaimKind, Evidence, EvidenceAssessment
from app.falsify.prompts import evidence as prompts

_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")

_REFUTATION_CUES = (
    "debunked", "false", "myth", "incorrect", "wrong", "not true", "did not", "didn't",
    "does not", "doesn't", "contradicts", "disputes", "disputed", "denies", "denied",
    "reversed", "reversal", "no evidence", "hoax", "inaccurate", "misleading",
    "actually decreased", "actually declined", "actually fell",
)
_CORROBORATION_CUES = (
    "confirms", "confirmed", "verified", "consistent with", "according to official",
    "as reported", "demonstrates", "shows that", "established", "well documented",
)


class EvidenceAnalyzer:
    """Structured evidence assessment (deterministic core + optional LLM)."""

    def __init__(
        self,
        config: EngineConfig | None = None,
        llm: LLMProvider | None = None,
        quality_scorer: SourceQualityScorer | None = None,
    ) -> None:
        self._config = config or EngineConfig()
        self._llm = llm
        self._scorer = quality_scorer or SourceQualityScorer()

    def assess(self, claim: Claim, evidence: Evidence) -> EvidenceAssessment:
        det = self._assess_deterministic(claim, evidence)

        if (
            self._llm is not None
            and not isinstance(self._llm, NullLLM)
            and self._config.use_llm_for_evidence_assessment
        ):
            det = self._merge_llm(claim, evidence, det)

        return det

    # ------------------------------------------------------------------
    # Deterministic assessment
    # ------------------------------------------------------------------

    def _assess_deterministic(self, claim: Claim, evidence: Evidence) -> EvidenceAssessment:
        text = " ".join([evidence.title, " ".join(evidence.relevant_passages), evidence.retrieved_text])
        lowered = text.lower()

        quality, tier = self._scorer.score(
            domain=evidence.domain, url=evidence.source_url, publisher=evidence.publisher, text=text
        )
        relevance = self._relevance(claim, lowered)
        temporal = self._temporal_validity(claim, evidence)

        supports = contradicts = False
        is_direct = False
        observed_value: str | None = None
        reasoning_parts: list[str] = []

        entity_gate_ok = self._entity_present(claim, lowered)
        if relevance < self._config.relevance_floor:
            reasoning_parts.append(
                f"Source does not meaningfully discuss the claim (relevance {relevance:.2f} "
                f"< floor {self._config.relevance_floor:.2f}); no stance assigned."
            )
        elif not entity_gate_ok:
            reasoning_parts.append(
                "None of the claim's named entities appear in the source; it cannot support or "
                "contradict the claim regardless of superficial numeric overlap."
            )
        else:
            stance = self._numeric_stance(claim, lowered)
            if stance is None:
                stance = self._lexical_stance(claim, lowered)
            supports, contradicts, is_direct, observed_value, stance_notes = stance
            reasoning_parts.extend(stance_notes)

        # temporal staleness can neutralize a would-be stance on period-bound claims
        if temporal < 0.5 and (supports or contradicts):
            reasoning_parts.append(
                "Evidence is temporally stale relative to the claim's period; stance discounted."
            )
            if supports:
                supports = False
            # stale *contradictions* are kept but flagged via low temporal validity

        reasoning = " ".join(reasoning_parts) or "No determinable relationship to the claim."
        return EvidenceAssessment(
            evidence_id=evidence.evidence_id,
            supports_claim=supports,
            contradicts_claim=contradicts,
            relevance_score=relevance,
            source_quality_score=quality,
            source_tier=tier,
            temporal_validity=temporal,
            is_direct=is_direct,
            observed_value=observed_value,
            reasoning=reasoning,
            analysis_source="deterministic",
        )

    @staticmethod
    def _entity_present(claim: Claim, lowered_text: str) -> bool:
        """True if at least one named entity of the claim appears in the text.

        Claims without extracted entities pass the gate (nothing to check).
        """
        if not claim.entities:
            return True
        for entity in claim.entities:
            words = [w for w in re.findall(r"[a-z0-9&']+", entity.lower()) if len(w) > 1]
            if words and any(re.search(rf"\b{re.escape(w)}", lowered_text) for w in words[:2]):
                return True
        return False

    def _relevance(self, claim: Claim, lowered_text: str) -> float:
        score = 0.0
        # entities (40%)
        if claim.entities:
            hits = 0
            for entity in claim.entities:
                entity_words = [w for w in re.findall(r"[a-z0-9&.']+", entity.lower()) if len(w) > 1]
                if entity_words and all(re.search(rf"\b{re.escape(w)}", lowered_text) for w in entity_words[:2]):
                    hits += 1
            score += 0.4 * (hits / len(claim.entities))
        else:
            score += 0.1  # no entities extracted: small neutral credit

        # metric / quantity subject (25%)
        q = claim.primary_quantity
        if q and q.metric:
            score += 0.25 if re.search(rf"\b{re.escape(q.metric.lower())}", lowered_text) else 0.0
        elif claim.predicates:
            from app.falsify.normalization.normalizer import _predicate_in_text

            hits = sum(1 for p in claim.predicates if _predicate_in_text(p, lowered_text))
            score += 0.25 * min(1.0, hits / max(1, len(claim.predicates)))

        # temporal constraints (15%)
        if claim.temporal_constraints:
            hits = sum(1 for t in claim.temporal_constraints if t.lower() in lowered_text)
            score += 0.15 * min(1.0, hits / len(claim.temporal_constraints))

        # content-word overlap with the normalized claim (20%)
        content = self._content_words(claim.normalized_text or claim.original_text)
        if content:
            overlap = len(content & self._content_words(lowered_text))
            score += 0.2 * min(1.0, overlap / max(3, len(content) * 0.6))
        return round(min(1.0, score), 3)

    @staticmethod
    def _content_words(text: str) -> set[str]:
        stop = {
            "the", "a", "an", "of", "in", "on", "at", "to", "for", "by", "with", "was", "were",
            "is", "are", "be", "been", "has", "have", "had", "it", "its", "that", "this", "than",
            "from", "and", "or", "as", "about", "into", "over", "after", "before", "will",
        }
        return {w for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in stop}

    def _temporal_validity(self, claim: Claim, evidence: Evidence) -> float:
        claim_year = self._claim_year(claim, evidence)
        pub_year = self._year_from(evidence.publication_date or "")
        if pub_year is None:
            # Undated sources get neutral-but-discounted validity.
            return 0.7 if claim_year is None else 0.65
        if claim_year is None:
            # No period in the claim: recency alone matters (mild).
            return 1.0 if pub_year >= evidence.retrieval_timestamp.year - 3 else 0.8
        if pub_year >= claim_year + 1:
            return 1.0  # published after the period closed: can report final figures
        if pub_year == claim_year:
            # Published during the claimed period: could be preliminary for full-period claims.
            return 0.8
        return 0.35  # published before the period even started: stale for this claim

    def _claim_year(self, claim: Claim, evidence: Evidence) -> int | None:
        for item in claim.temporal_constraints:
            match = _YEAR_RE.search(item)
            if match:
                return int(match.group(1))
            low = item.lower()
            year = evidence.retrieval_timestamp.year
            if "last year" in low:
                return year - 1
            if "this year" in low:
                return year
            if "next year" in low:
                return year + 1
        match = _YEAR_RE.search(claim.original_text)
        return int(match.group(1)) if match else None

    @staticmethod
    def _year_from(date_str: str) -> int | None:
        match = _YEAR_RE.search(date_str)
        return int(match.group(1)) if match else None

    def _numeric_stance(self, claim: Claim, lowered_text: str):
        q = claim.primary_quantity
        if q is None or q.value is None:
            return None
        observations = extract_numeric_observations(lowered_text, metric_hint=q.metric)
        if not observations:
            return None
        comparison = best_comparison(q, observations, rel_tol=self._config.numeric_agreement_rel_tol)
        if comparison is None or comparison.kind == "unrelated":
            return None

        observed = next(
            (o.raw for o in observations if comparison.observed_value is not None and abs(o.value - comparison.observed_value) < 1e-9),
            observations[0].raw,
        )
        notes = [f"Numeric comparison: {'; '.join(comparison.notes)}."]
        if comparison.kind == "match":
            return (True, False, True, observed, notes)
        if comparison.kind == "direction_mismatch":
            return (False, True, True, observed, notes)
        if comparison.kind == "magnitude_mismatch":
            # A near-miss inside rounding language ("about 20%") is support, not contradiction.
            if (q.comparator or "") == "approximately" and comparison.relative_gap <= 0.05:
                notes.append("Gap is within 'approximately' language of the claim; treated as support.")
                return (True, False, True, observed, notes)
            return (False, True, True, observed, notes)
        return None

    def _lexical_stance(self, claim: Claim, lowered_text: str):
        """Fallback stance for non-numeric claims using refutation/corroboration cues."""
        entity_present = False
        if claim.entities:
            entity_words = [w for w in re.findall(r"[a-z0-9]+", claim.entities[0].lower()) if len(w) > 2]
            entity_present = any(re.search(rf"\b{re.escape(w)}", lowered_text) for w in entity_words)
        from app.falsify.normalization.normalizer import _predicate_in_text

        predicate_present = any(_predicate_in_text(p, lowered_text) for p in claim.predicates) if claim.predicates else False

        notes: list[str] = []
        refutation_hits = [cue for cue in _REFUTATION_CUES if cue in lowered_text]
        corroboration_hits = [cue for cue in _CORROBORATION_CUES if cue in lowered_text]

        # Quantitative-direction claims without extractable numbers: use direction words.
        q = claim.primary_quantity
        if q and q.direction:
            opposite = "decreased" if q.direction == "increased" else "increased"
            opposite_words = ("declined", "fell", "dropped", "decreased", "shrank", "contracted") if opposite == "decreased" else ("increased", "grew", "rose", "climbed", "surged", "expanded")
            same_words = ("declined", "fell", "dropped", "decreased", "shrank", "contracted") if q.direction == "decreased" else ("increased", "grew", "rose", "climbed", "surged", "expanded")
            if entity_present and any(re.search(rf"\b{w}\b", lowered_text) for w in opposite_words):
                notes.append(f"Text asserts the opposite direction ('{opposite}') for the claim's subject.")
                return (False, True, entity_present, None, notes)
            if entity_present and any(re.search(rf"\b{w}\b", lowered_text) for w in same_words):
                notes.append("Text asserts the same direction of change for the claim's subject, without a specific figure.")
                return (True, False, False, None, notes)

        if entity_present and refutation_hits:
            notes.append(f"Refutation cues present ({', '.join(refutation_hits[:3])}) in text discussing the claim's subject.")
            return (False, True, predicate_present, None, notes)
        if entity_present and predicate_present and not refutation_hits:
            if corroboration_hits or claim.claim_kind in (ClaimKind.FACTUAL, ClaimKind.COMPARATIVE):
                notes.append(f"Text corroborates the asserted relationship (cues: {', '.join(corroboration_hits[:3]) or 'subject+predicate present, no refutation'} ).")
                return (True, False, bool(corroboration_hits), None, notes)
        notes.append("No clear supporting or contradicting signal in the text.")
        return (False, False, False, None, notes)

    # ------------------------------------------------------------------
    # LLM merge
    # ------------------------------------------------------------------

    def _merge_llm(self, claim: Claim, evidence: Evidence, det: EvidenceAssessment) -> EvidenceAssessment:
        from app.falsify.llm.base import generate_json

        text = " ".join([evidence.title, " ".join(evidence.relevant_passages), evidence.retrieved_text])
        prompt = prompts.build(
            claim.original_text,
            evidence.title,
            evidence.publisher,
            evidence.source_url,
            evidence.publication_date,
            text,
        )
        try:
            data = generate_json(
                self._llm,  # type: ignore[arg-type]
                prompt,
                system=prompts.system_prompt(prompts.EVIDENCE_SYSTEM_ROLE),
                max_retries=self._config.llm_max_retries,
                stage="evidence_assessment",
            )
            if not isinstance(data, dict):
                raise ValueError("assessment payload is not an object")
        except Exception as exc:
            log_event("llm_evidence_assessment_skipped", evidence_id=evidence.evidence_id, reason=str(exc)[:140], level=30)
            return det

        merged = det.model_copy(deep=True)
        merged.analysis_source = "hybrid"

        relevance = _as_float(data.get("relevance_score"), det.relevance_score)
        merged.relevance_score = round(min(1.0, max(0.0, relevance)), 3)
        merged.temporal_validity = round(min(1.0, max(0.0, _as_float(data.get("temporal_validity"), det.temporal_validity))), 3)

        llm_supports = bool(data.get("supports_claim", False))
        llm_contradicts = bool(data.get("contradicts_claim", False))
        llm_reasoning = str(data.get("reasoning", ""))[:600]
        observed = data.get("observed_value")
        if isinstance(observed, str) and observed.strip() and not merged.observed_value:
            merged.observed_value = observed.strip()[:200]

        # Relevance floor gate: irrelevant sources get no stance from anyone.
        # Entity gate: a source that never mentions the claim's entities cannot
        # take a stance, no matter what the LLM says.
        text_lower = " ".join([evidence.title, " ".join(evidence.relevant_passages), evidence.retrieved_text]).lower()
        if merged.relevance_score < self._config.relevance_floor or not self._entity_present(claim, text_lower):
            merged.supports_claim = False
            merged.contradicts_claim = False
            merged.reasoning = (
                f"Stance suppressed (relevance {merged.relevance_score:.2f} below floor or claim entities absent "
                f"from source). LLM notes: {llm_reasoning}"
            ).strip()
            return merged

        # Hard deterministic numeric findings are never overridden by the LLM.
        numeric_decisive = det.is_direct and det.observed_value is not None and "Numeric comparison" in det.reasoning
        if numeric_decisive:
            if (det.supports_claim, det.contradicts_claim) != (llm_supports, llm_contradicts):
                merged.reasoning = (
                    f"{det.reasoning} LLM stance (supports={llm_supports}, contradicts={llm_contradicts}) "
                    f"overridden by deterministic numeric extraction. LLM notes: {llm_reasoning}"
                )
            else:
                merged.reasoning = f"{det.reasoning} LLM concurs. {llm_reasoning}"
            return merged

        merged.supports_claim = llm_supports
        merged.contradicts_claim = llm_contradicts
        if isinstance(data.get("is_direct"), bool):
            merged.is_direct = data["is_direct"]
        merged.reasoning = (llm_reasoning or det.reasoning)
        merged.analysis_source = "llm" if "Numeric comparison" not in det.reasoning else "hybrid"
        return merged


def _as_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
