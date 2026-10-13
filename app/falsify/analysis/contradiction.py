"""Contradiction detection.

Compares the CLAIM against each assessed piece of evidence and decides
whether the evidence *actually falsifies* the claim -- as opposed to merely
disagreeing, being irrelevant, or using different definitions.

Policy highlights (per product spec):
* "increased 20%" vs "increased 19.8%" -> at most a LOW numerical
  contradiction (rounding-compatible within implied precision);
* "increased 20%" vs "increased 20% year-over-year" -> support, no
  contradiction;
* "increased 30%" vs official "increased 21%" -> HIGH numerical contradiction;
* direction flips ("increased" vs "decreased") -> CRITICAL.
"""

from __future__ import annotations

import re

from app.falsify.analysis.numerics import best_comparison, extract_numeric_observations
from app.falsify.config import EngineConfig
from app.falsify.llm.base import LLMProvider
from app.falsify.llm.provider import NullLLM
from app.falsify.logging_utils import log_event
from app.falsify.models import (
    Claim,
    Contradiction,
    ContradictionType,
    Evidence,
    EvidenceAssessment,
    Severity,
)
from app.falsify.prompts import contradiction as prompts

_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
_DEFINITIONAL_CUES = ("non-gaap", "non gaap", "adjusted", "excluding", "constant currency", "organic growth", "restated basis", "under a different definition")
_SCOPE_CUES = ("segment", "division", "quarter", "quarterly", "region", "north america", "emea", "apac", "domestic only", "excluding international")


class ContradictionDetector:
    """Detects and classifies contradictions between a claim and evidence."""

    def __init__(self, config: EngineConfig | None = None, llm: LLMProvider | None = None) -> None:
        self._config = config or EngineConfig()
        self._llm = llm

    def detect(
        self, claim: Claim, items: list[tuple[Evidence, EvidenceAssessment]]
    ) -> list[Contradiction]:
        candidates: list[Contradiction] = []
        for evidence, assessment in items:
            # Only relevant evidence that actually contradicts can produce a contradiction.
            if not assessment.contradicts_claim:
                continue
            if assessment.relevance_score < self._config.relevance_floor:
                continue
            contradiction = self._classify(claim, evidence, assessment)
            if contradiction is not None:
                # always attribute the contradiction to the evidence that triggered it
                if evidence.evidence_id not in contradiction.evidence_ids:
                    contradiction.evidence_ids.append(evidence.evidence_id)
                candidates.append(contradiction)

        merged = self._merge(candidates)
        log_event(
            "contradictions_detected",
            claim_id=claim.claim_id,
            count=len(merged),
            severities=[c.severity.value for c in merged],
        )
        return merged

    # ------------------------------------------------------------------

    def _classify(
        self, claim: Claim, evidence: Evidence, assessment: EvidenceAssessment
    ) -> Contradiction | None:
        text = " ".join([evidence.title, " ".join(evidence.relevant_passages), evidence.retrieved_text]).lower()

        ctype = ContradictionType.NUMERICAL
        severity = Severity.MEDIUM
        explanation = assessment.reasoning

        q = claim.primary_quantity
        if q is not None and q.value is not None:
            observations = extract_numeric_observations(text, metric_hint=q.metric)
            comparison = best_comparison(q, observations, rel_tol=self._config.numeric_agreement_rel_tol)

            if comparison is not None and comparison.kind in ("direction_mismatch", "magnitude_mismatch"):
                # --- temporal misassignment: same value, different period ---
                temporal = self._temporal_misassignment(claim, text, comparison)
                if temporal is not None:
                    return temporal

                # --- attribution: value belongs to a different entity ---
                attribution = self._entity_misattribution(claim, text, comparison)
                if attribution is not None:
                    return attribution

                # --- definitional / scope overlays ---
                if any(cue in text for cue in _DEFINITIONAL_CUES) and comparison.kind == "magnitude_mismatch":
                    ctype = ContradictionType.DEFINITIONAL
                    severity = Severity.MEDIUM
                    explanation = (
                        f"Evidence reports {comparison.observed_value} vs claimed {q.raw_value}, but under an "
                        f"apparently different definition/adjustment of the metric. {'; '.join(comparison.notes)}"
                    )
                elif any(cue in text for cue in _SCOPE_CUES) and comparison.kind == "magnitude_mismatch" and comparison.relative_gap <= 0.15:
                    ctype = ContradictionType.SCOPE
                    severity = Severity.LOW
                    explanation = (
                        f"Small numeric gap ({comparison.relative_gap:.0%}) co-occurs with scope language "
                        f"(segment/quarter/region); the claim may hold only in a narrower scope. {'; '.join(comparison.notes)}"
                    )
                elif comparison.kind == "direction_mismatch":
                    ctype = ContradictionType.NUMERICAL
                    severity = Severity.CRITICAL
                    explanation = (
                        f"Claim asserts {q.direction} by {q.raw_value}; evidence asserts the opposite direction "
                        f"({assessment.observed_value or comparison.observed_value}). {'; '.join(comparison.notes)}"
                    )
                else:  # magnitude mismatch
                    ctype = ContradictionType.NUMERICAL
                    severity = self._magnitude_severity(comparison.relative_gap, exact=(q.comparator or "") == "exactly")
                    explanation = (
                        f"Claimed {q.raw_value} vs observed {comparison.observed_value}. {'; '.join(comparison.notes)}"
                    )
            elif comparison is not None and comparison.kind == "match":
                # Deterministic numeric extraction says the evidence AGREES; the
                # contradicting stance must come from something non-numeric --
                # keep it but downgrade and re-type conservatively.
                severity = Severity.LOW
                explanation = (
                    f"Numeric value matches the claim within tolerance, but the assessment flags a "
                    f"contradiction on other grounds: {assessment.reasoning}"
                )
                ctype = ContradictionType.DEFINITIONAL
        else:
            # Non-numeric claim: type from textual cues, severity from source strength.
            if any(cue in text for cue in _DEFINITIONAL_CUES):
                ctype = ContradictionType.DEFINITIONAL
            elif "different period" in text or "earlier period" in text or "quarter rather than" in text:
                ctype = ContradictionType.TEMPORAL
            elif claim.entities and not any(e.lower() in text for e in claim.entities[:1]):
                ctype = ContradictionType.ENTITY
            else:
                ctype = ContradictionType.NUMERICAL if q else ContradictionType.DEFINITIONAL
            strong_source = assessment.source_quality_score >= 0.7 and assessment.relevance_score >= 0.6
            severity = Severity.HIGH if strong_source else Severity.MEDIUM

        contradiction = Contradiction(
            claim_id=claim.claim_id,
            evidence_ids=[evidence.evidence_id],
            contradiction_type=ctype,
            severity=severity,
            explanation=explanation[:900],
        )

        # Optional LLM refinement of type/severity/explanation (advisory only).
        if self._llm is not None and not isinstance(self._llm, NullLLM):
            contradiction = self._refine_with_llm(claim, evidence, text, contradiction)
        return contradiction

    def _magnitude_severity(self, relative_gap: float, *, exact: bool) -> Severity:
        if relative_gap > 0.25 or (exact and relative_gap > 0.1):
            return Severity.HIGH
        if relative_gap >= 0.1:
            return Severity.MEDIUM
        return Severity.LOW

    def _temporal_misassignment(self, claim: Claim, text: str, comparison) -> Contradiction | None:
        """Detect 'the claimed value actually belongs to a different period'."""
        claim_years = {m.group(1) for m in _YEAR_RE.finditer(claim.original_text)}
        if not claim_years or comparison.observed_value is None:
            return None
        evidence_years = {m.group(1) for m in _YEAR_RE.finditer(text)}
        # The exact claimed value appears in the evidence...
        value_str = str(claim.primary_quantity.value if claim.primary_quantity else "")
        value_appears = bool(
            claim.primary_quantity
            and claim.primary_quantity.value is not None
            and re.search(rf"\b{re.escape(_fmt(claim.primary_quantity.value))}(?!\d)(\s*(%|percent))?", text)
        )
        if value_appears and evidence_years and not (evidence_years & claim_years):
            return Contradiction(
                claim_id=claim.claim_id,
                evidence_ids=[],
                contradiction_type=ContradictionType.TEMPORAL,
                severity=Severity.MEDIUM,
                explanation=(
                    f"The claimed value ({value_str}) appears in the evidence attached to period(s) "
                    f"{sorted(evidence_years)}, not the claimed period {sorted(claim_years)}."
                ),
            )
        return None

    def _entity_misattribution(self, claim: Claim, text: str, comparison) -> Contradiction | None:
        """Detect 'the claimed value actually belongs to a different entity'."""
        if not claim.entities:
            return None
        primary_words = [w for w in re.findall(r"[a-z0-9]+", claim.entities[0].lower()) if len(w) > 2]
        primary_present = any(w in text for w in primary_words)
        value_appears = bool(
            claim.primary_quantity
            and claim.primary_quantity.value is not None
            and re.search(rf"\b{re.escape(_fmt(claim.primary_quantity.value))}(?!\d)(\s*(%|percent))?", text)
        )
        other_entities = [e for e in claim.entities[1:] if e.lower() in text]
        if value_appears and not primary_present and other_entities:
            return Contradiction(
                claim_id=claim.claim_id,
                evidence_ids=[],
                contradiction_type=ContradictionType.ATTRIBUTION,
                severity=Severity.MEDIUM,
                explanation=(
                    f"The claimed value appears in the evidence in connection with "
                    f"{other_entities[0]!r}, not with {claim.entities[0]!r}."
                ),
            )
        return None

    def _refine_with_llm(
        self, claim: Claim, evidence: Evidence, text: str, base: Contradiction
    ) -> Contradiction:
        from app.falsify.llm.base import generate_json

        elements = (
            f"entities={claim.entities}; temporal={claim.temporal_constraints}; "
            f"quantities={[q.model_dump(exclude_none=True) for q in claim.quantitative_constraints]}"
        )
        prompt = prompts.build(claim.original_text, elements, text)
        try:
            data = generate_json(
                self._llm,  # type: ignore[arg-type]
                prompt,
                system=prompts.system_prompt(prompts.CONTRADICTION_SYSTEM_ROLE),
                max_retries=self._config.llm_max_retries,
                stage="contradiction",
            )
            if not isinstance(data, dict) or not data.get("is_contradiction"):
                if isinstance(data, dict) and data.get("is_contradiction") is False:
                    log_event("llm_rejected_contradiction", evidence_id=evidence.evidence_id)
                    return None  # type: ignore[return-value]
                raise ValueError("malformed contradiction payload")
            refined = base.model_copy(deep=True)
            try:
                refined.contradiction_type = ContradictionType(str(data["contradiction_type"]).lower())
            except (KeyError, ValueError):
                pass
            try:
                refined.severity = Severity(str(data["severity"]).lower())
            except (KeyError, ValueError):
                pass
            explanation = data.get("explanation")
            if isinstance(explanation, str) and explanation.strip():
                refined.explanation = f"{base.explanation} | LLM analysis: {explanation.strip()[:400]}"
            return refined
        except Exception as exc:
            log_event("llm_contradiction_refinement_skipped", reason=str(exc)[:140], level=30)
            return base

    def _merge(self, contradictions: list[Contradiction]) -> list[Contradiction]:
        """Group contradictions of the same type; keep the strongest severity."""
        order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]
        grouped: dict[ContradictionType, Contradiction] = {}
        for contradiction in contradictions:
            if contradiction is None:  # LLM may have rejected a candidate
                continue
            existing = grouped.get(contradiction.contradiction_type)
            if existing is None:
                grouped[contradiction.contradiction_type] = contradiction.model_copy(deep=True)
            else:
                for eid in contradiction.evidence_ids:
                    if eid not in existing.evidence_ids:
                        existing.evidence_ids.append(eid)
                if order.index(contradiction.severity) < order.index(existing.severity):
                    existing.severity = contradiction.severity
                    existing.explanation = contradiction.explanation
        result = sorted(grouped.values(), key=lambda c: order.index(c.severity))
        return result[:6]


def _fmt(value: float) -> str:
    """Format a float for regex matching against text ('20.0' -> '20')."""
    if value == int(value):
        return str(int(value))
    return f"{value:g}"
