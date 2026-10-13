"""Deterministic verdict engine.

Maps the fused evidence picture onto one of five verdicts.  The rules are
explicit, ordered and side-effect free -- no LLM is involved, so identical
inputs always produce identical verdicts (auditable by design).

Decision tree (in order):

1. No usable evidence / all retrieval failed         -> UNVERIFIABLE
2. Future claim without decisive current evidence    -> UNVERIFIABLE
3. No credible source on either side                 -> UNVERIFIABLE
4. Support-dominant:
   a. severe (HIGH/CRITICAL) credible contradiction,
      contradicting side still substantial          -> CONFLICTED
   b. VERIFIED bar met, no unresolved contradictions -> VERIFIED
   c. otherwise, with unresolved qualifications      -> QUALIFIED
5. Contradiction-dominant:
   a. balanced credible conflict inside conflict band-> CONFLICTED
   b. severe credible contradiction                  -> REFUTED
   c. non-severe but material discrepancy            -> QUALIFIED
6. Everything else                                   -> UNVERIFIABLE
"""

from __future__ import annotations

from dataclasses import dataclass

from app.falsify.config import EngineConfig
from app.falsify.logging_utils import log_event
from app.falsify.models import (
    Claim,
    Contradiction,
    FusionSummary,
    Severity,
    Verdict,
)

_EPS = 1e-9


@dataclass
class VerdictDecision:
    verdict: Verdict
    rationale: str


class VerdictEngine:
    """Rule-based verdict determination (no naive majority voting)."""

    def __init__(self, config: EngineConfig | None = None) -> None:
        self._config = config or EngineConfig()

    def decide(
        self,
        claim: Claim,
        fusion: FusionSummary,
        contradictions: list[Contradiction],
    ) -> VerdictDecision:
        cfg = self._config
        support = fusion.support_strength
        contradict = fusion.contradict_strength
        max_severity = self._max_severity(contradictions)
        severe = max_severity in (Severity.HIGH, Severity.CRITICAL)
        support_credible = fusion.max_support_quality >= cfg.min_quality_verified
        contradict_credible = fusion.max_contradict_quality >= cfg.min_quality_verified

        # ---- 1. No usable evidence ------------------------------------------
        relevant_evidence = fusion.supporting_evidence + fusion.contradicting_evidence
        if fusion.total_evidence == 0 or (support <= _EPS and contradict <= _EPS and relevant_evidence == 0):
            if fusion.retrieval_failures and fusion.total_evidence == 0:
                return self._done(
                    Verdict.UNVERIFIABLE,
                    "All retrieval attempts failed; no evidence could be examined.",
                )
            return self._done(
                Verdict.UNVERIFIABLE,
                "No retrieved source meaningfully addressed the claim (all evidence was irrelevant or absent).",
            )

        # ---- 2. Future claims cannot be settled by current evidence ----------
        if claim.is_future_claim and not severe and support < cfg.min_support_strength_verified:
            return self._done(
                Verdict.UNVERIFIABLE,
                "The claim concerns a future event; no current evidence can settle its outcome. "
                "Only the provenance/currency of the underlying forecast could be checked.",
            )

        # ---- 3. No credible sources on either side ---------------------------
        if not support_credible and not contradict_credible:
            return self._done(
                Verdict.UNVERIFIABLE,
                "Only low-credibility sources addressed the claim "
                f"(best source quality: {max(fusion.max_support_quality, fusion.max_contradict_quality):.2f}); "
                "insufficient reliable evidence for a determination.",
            )

        support_dominant = support >= contradict

        # ---- 4. Support-dominant ----------------------------------------------
        if support_dominant:
            if contradictions:
                if severe and support_credible and contradict_credible and contradict >= support * 0.35:
                    return self._done(
                        Verdict.CONFLICTED,
                        f"Supporting evidence is present ({support:.2f}), but a credible {max_severity.value if max_severity else 'material'}-severity "
                        f"contradiction retains substantial weight ({contradict:.2f}); the conflict cannot be resolved.",
                    )
                return self._done(
                    Verdict.QUALIFIED,
                    f"Support dominates ({support:.2f} vs {contradict:.2f}) but an unresolved qualification remains "
                    f"({contradictions[0].contradiction_type.value}, severity {contradictions[0].severity.value}): "
                    f"{contradictions[0].explanation[:200]}",
                )

            independent_ok = (
                fusion.independent_supporting_clusters >= 2
                or fusion.max_support_quality >= 0.8
            )
            if support >= cfg.min_support_strength_verified and support_credible and independent_ok:
                return self._done(
                    Verdict.VERIFIED,
                    f"Strong, credible, independent support ({support:.2f} across "
                    f"{fusion.independent_supporting_clusters} cluster(s), best source quality "
                    f"{fusion.max_support_quality:.2f}); falsification attempts did not surface a credible contradiction.",
                )
            if support >= 0.4:
                reasons = []
                if not support_credible:
                    reasons.append(f"best supporting source quality is only {fusion.max_support_quality:.2f}")
                if not independent_ok:
                    reasons.append("support rests on a single non-authoritative source")
                if support < cfg.min_support_strength_verified:
                    reasons.append("supporting weight below the verification bar")
                return self._done(
                    Verdict.QUALIFIED,
                    "Evidence leans supportive but falls short of the verification bar: "
                    + ("; ".join(reasons) if reasons else "marginal support strength") + ".",
                )
            return self._done(
                Verdict.UNVERIFIABLE,
                f"Supporting evidence is too weak to decide (support {support:.2f}, contradiction {contradict:.2f}).",
            )

        # ---- 5. Contradiction-dominant ------------------------------------------
        low, high = cfg.conflict_band
        ratio = support / max(contradict, _EPS)
        if support >= 0.4 and support_credible and contradict_credible and low <= ratio <= high:
            return self._done(
                Verdict.CONFLICTED,
                f"Credible evidence exists on both sides (support {support:.2f} vs contradiction {contradict:.2f}, "
                f"ratio {ratio:.2f} inside the conflict band [{low}, {high}]); the conflict cannot be resolved "
                "from the available sources.",
            )
        if severe and contradict_credible and (support < 0.4 or contradict >= support * 0.6):
            return self._done(
                Verdict.REFUTED,
                f"A {max_severity.value if max_severity else 'high'}-severity contradiction is backed by credible sources "
                f"(quality {fusion.max_contradict_quality:.2f}) and dominates the supporting side "
                f"({contradict:.2f} vs {support:.2f}).",
            )
        if fusion.max_contradict_quality >= 0.5:
            return self._done(
                Verdict.QUALIFIED,
                "The claim's direction survives, but the evidence indicates a material discrepancy with the "
                f"claim as stated (contradiction {contradict:.2f} vs support {support:.2f}, max severity "
                f"{max_severity.value if max_severity else 'none'}).",
            )
        return self._done(
            Verdict.UNVERIFIABLE,
            f"Evidence is too weak or sparse to decide (support {support:.2f}, contradiction {contradict:.2f}, "
            f"coverage {fusion.coverage:.0%}).",
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _max_severity(contradictions: list[Contradiction]) -> Severity | None:
        order = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
        severities = [c.severity for c in contradictions]
        return max(severities, key=order.index) if severities else None

    @staticmethod
    def _done(verdict: Verdict, rationale: str) -> VerdictDecision:
        log_event("verdict_generated", verdict=verdict.value, rationale=rationale[:160])
        return VerdictDecision(verdict=verdict, rationale=rationale)
