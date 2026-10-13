"""Confidence calculation.

Confidence is explicitly NOT ``supporting / total``.  It is a weighted
combination of independent factors describing how much trust the *verdict*
deserves:

* evidence quality (source tiers, weighted by relevance)
* evidence relevance
* source independence (cluster-based, duplicate copies don't count)
* cross-source agreement / conflict balance (verdict-aware)
* unresolved contradiction strength (severity-weighted)
* temporal validity
* retrieval coverage (how many falsification hypotheses were actually tested)
"""

from __future__ import annotations

from app.falsify.config import EngineConfig
from app.falsify.logging_utils import log_event
from app.falsify.models import (
    SEVERITY_WEIGHT,
    Claim,
    ConfidenceBreakdown,
    Contradiction,
    EvidenceCluster,
    FusionSummary,
    Severity,
    Verdict,
)

_WEIGHTS = {
    "evidence_quality": 0.20,
    "evidence_relevance": 0.15,
    "source_independence": 0.15,
    "cross_source_agreement": 0.20,
    "contradiction_strength": 0.10,
    "temporal_validity": 0.10,
    "retrieval_coverage": 0.10,
}

_MIN, _MAX = 0.05, 0.97


class ConfidenceCalculator:
    def __init__(self, config: EngineConfig | None = None) -> None:
        self._config = config or EngineConfig()

    def compute(
        self,
        *,
        claim: Claim,
        verdict: Verdict,
        fusion: FusionSummary,
        clusters: list[EvidenceCluster],
        contradictions: list[Contradiction],
        relevance_by_id: dict[str, float],
        quality_by_id: dict[str, float],
        temporal_by_id: dict[str, float],
        stance_by_id: dict[str, str],
    ) -> tuple[float, ConfidenceBreakdown, str]:
        # Special case: no usable evidence at all -> confidence is about the
        # *absence* of evidence, not about evidence we don't have.
        stance_items = [eid for eid, stance in stance_by_id.items() if stance in ("supporting", "contradicting")]
        if not stance_items:
            base = 0.75 if fusion.retrieval_failures == 0 else 0.5
            if claim.is_future_claim:
                base = max(base, 0.7)
            breakdown = ConfidenceBreakdown(
                retrieval_coverage=fusion.coverage,
                weighted_total=base,
                factors={"no_stance_evidence": 1.0},
            )
            explanation = (
                "No source took a decidable stance on the claim, so confidence reflects certainty that "
                "the claim is currently undecidable"
                + (" despite retrieval failures." if fusion.retrieval_failures else ".")
            )
            return base, breakdown, explanation

        total_support = fusion.support_strength
        total_contradict = fusion.contradict_strength
        total = max(total_support + total_contradict, 1e-9)
        majority_stance = "supporting" if total_support >= total_contradict else "contradicting"

        # --- factor: quality & relevance (weighted averages over stance evidence)
        weighted_quality = sum(quality_by_id.get(e, 0.0) * relevance_by_id.get(e, 0.0) for e in stance_items)
        total_rel = sum(relevance_by_id.get(e, 0.0) for e in stance_items) or 1.0
        evidence_quality = weighted_quality / total_rel
        evidence_relevance = total_rel / len(stance_items)

        # --- factor: independence (majority side)
        majority_items = [e for e in stance_items if stance_by_id.get(e) == majority_stance]
        majority_clusters = [c for c in clusters if c.stance == majority_stance]
        source_independence = min(1.0, len(majority_clusters) / max(1, len(majority_items)))

        # --- factor: agreement (verdict-aware)
        dominance = abs(total_support - total_contradict) / total
        balance = 1.0 - dominance
        if verdict in (Verdict.VERIFIED, Verdict.REFUTED):
            agreement = dominance
        elif verdict == Verdict.CONFLICTED:
            agreement = balance  # a well-balanced conflict -> confidently CONFLICTED
        elif verdict == Verdict.QUALIFIED:
            agreement = 0.5 + 0.5 * dominance
        else:  # UNVERIFIABLE with some weak evidence
            agreement = 1.0 - min(1.0, total)

        # --- factor: unresolved contradiction strength (severity weighted)
        max_sev_weight = max((SEVERITY_WEIGHT[c.severity] for c in contradictions), default=0.0)
        if verdict == Verdict.VERIFIED:
            contradiction_factor = 1.0 - max_sev_weight
        elif verdict == Verdict.REFUTED:
            contradiction_factor = 1.0 - (total_support / total)  # residual support weakens REFUTED
        elif verdict == Verdict.CONFLICTED:
            contradiction_factor = 1.0
        elif verdict == Verdict.QUALIFIED:
            contradiction_factor = 1.0 - 0.5 * max_sev_weight
        else:
            contradiction_factor = 1.0 - min(1.0, total)

        # --- factor: temporal validity
        temporal = sum(temporal_by_id.get(e, 0.7) for e in stance_items) / len(stance_items)

        # --- factor: retrieval coverage (penalized by failures)
        failure_penalty = min(0.5, 0.1 * fusion.retrieval_failures)
        coverage = max(0.0, min(1.0, fusion.coverage * (1.0 if fusion.retrieval_failures == 0 else 0.7) + (0.3 if fusion.coverage > 0 else 0.0))) - failure_penalty
        coverage = max(0.0, coverage)

        factors = {
            "evidence_quality": round(evidence_quality, 3),
            "evidence_relevance": round(evidence_relevance, 3),
            "source_independence": round(source_independence, 3),
            "cross_source_agreement": round(agreement, 3),
            "contradiction_strength": round(contradiction_factor, 3),
            "temporal_validity": round(temporal, 3),
            "retrieval_coverage": round(coverage, 3),
        }
        score = sum(_WEIGHTS[k] * factors[k] for k in _WEIGHTS)
        score = round(min(_MAX, max(_MIN, score)), 3)

        breakdown = ConfidenceBreakdown(
            evidence_quality=factors["evidence_quality"],
            evidence_relevance=factors["evidence_relevance"],
            source_independence=factors["source_independence"],
            cross_source_agreement=factors["cross_source_agreement"],
            contradiction_strength=factors["contradiction_strength"],
            temporal_validity=factors["temporal_validity"],
            retrieval_coverage=factors["retrieval_coverage"],
            decisiveness_margin=round(dominance, 3),
            weighted_total=score,
            factors=factors,
        )
        explanation = self._explain(verdict, score, factors, fusion, max_sev_weight)
        log_event("confidence_computed", verdict=verdict.value, confidence=score)
        return score, breakdown, explanation

    @staticmethod
    def _explain(
        verdict: Verdict,
        score: float,
        factors: dict[str, float],
        fusion: FusionSummary,
        max_sev_weight: float,
    ) -> str:
        strongest = sorted(factors.items(), key=lambda kv: kv[1])
        weakest = f"{strongest[0][0].replace('_', ' ')} ({strongest[0][1]:.2f})"
        best = f"{strongest[-1][0].replace('_', ' ')} ({strongest[-1][1]:.2f})"
        parts = [
            f"Confidence {score:.2f} in verdict {verdict.value}.",
            f"Strongest factor: {best}; weakest: {weakest}.",
            f"Independent clusters: {fusion.independent_supporting_clusters} supporting / "
            f"{fusion.independent_contradicting_clusters} contradicting "
            f"({fusion.duplicated_evidence_detected} duplicate(s) collapsed).",
        ]
        if max_sev_weight >= SEVERITY_WEIGHT[Severity.HIGH]:
            parts.append("A high-severity contradiction strongly shapes this score.")
        if fusion.retrieval_failures:
            parts.append(f"{fusion.retrieval_failures} retrieval failure(s) reduced coverage.")
        return " ".join(parts)
