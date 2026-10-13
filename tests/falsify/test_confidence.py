"""Tests for confidence calculation."""

from __future__ import annotations

import pytest

from app.falsify.fusion.confidence import ConfidenceCalculator
from app.falsify.models import (
    Contradiction,
    ContradictionType,
    EvidenceCluster,
    FusionSummary,
    Severity,
    Verdict,
)
from app.falsify.normalization.normalizer import ClaimNormalizer


@pytest.fixture
def normalizer(config):
    return ClaimNormalizer(config)


@pytest.fixture
def calc(config):
    return ConfidenceCalculator(config)


def _compute(calc, normalizer, *, verdict, fusion, clusters, contradictions, maps, claim_text="Company X revenue increased by 20% in 2025."):
    claim = normalizer.normalize(claim_text)
    return calc.compute(
        claim=claim,
        verdict=verdict,
        fusion=fusion,
        clusters=clusters,
        contradictions=contradictions,
        **maps,
    )


class TestBasicProperties:
    def test_bounds(self, calc, normalizer):
        fusion = FusionSummary(
            supporting_evidence=1, total_evidence=1, independent_supporting_clusters=1,
            support_strength=0.8, max_support_quality=0.9, coverage=0.5,
        )
        score, breakdown, explanation = _compute(
            calc, normalizer, verdict=Verdict.VERIFIED, fusion=fusion, clusters=[], contradictions=[],
            maps=dict(relevance_by_id={"e1": 0.9}, quality_by_id={"e1": 0.9},
                      temporal_by_id={"e1": 1.0}, stance_by_id={"e1": "supporting"}),
        )
        assert 0.0 <= score <= 1.0
        assert explanation
        assert breakdown.weighted_total == score

    def test_no_evidence_unverifiable_confidence(self, calc, normalizer):
        score, _, explanation = _compute(
            calc, normalizer, verdict=Verdict.UNVERIFIABLE, fusion=FusionSummary(),
            clusters=[], contradictions=[],
            maps=dict(relevance_by_id={}, quality_by_id={}, temporal_by_id={}, stance_by_id={}),
        )
        assert 0.6 <= score <= 0.8
        assert "undecidable" in explanation or "no source" in explanation.lower()

    def test_retrieval_failures_lower_confidence(self, calc, normalizer):
        base_maps = dict(relevance_by_id={}, quality_by_id={}, temporal_by_id={}, stance_by_id={})
        score_ok, _, _ = _compute(
            calc, normalizer, verdict=Verdict.UNVERIFIABLE, fusion=FusionSummary(),
            clusters=[], contradictions=[], maps=base_maps,
        )
        score_failed, _, _ = _compute(
            calc, normalizer, verdict=Verdict.UNVERIFIABLE,
            fusion=FusionSummary(retrieval_failures=5),
            clusters=[], contradictions=[], maps=base_maps,
        )
        assert score_failed < score_ok


class TestNotNaiveRatio:
    def test_three_blogs_do_not_beat_one_primary_source(self, calc, normalizer):
        """Confidence must not be 3/4 just because three copies 'support'."""
        # 3 duplicated blogs (one cluster) + 1 contradicting SEC filing
        fusion = FusionSummary(
            supporting_evidence=3, contradicting_evidence=1, total_evidence=4,
            independent_supporting_clusters=1, independent_contradicting_clusters=1,
            support_strength=0.35,  # cluster max, not sum
            contradict_strength=0.85,
            max_support_quality=0.35, max_contradict_quality=0.9,
            duplicated_evidence_detected=2, coverage=0.5,
        )
        clusters = [
            EvidenceCluster(evidence_ids=["b1", "b2", "b3"], stance="supporting", weight=0.35),
            EvidenceCluster(evidence_ids=["s1"], stance="contradicting", weight=0.85),
        ]
        score, _, _ = _compute(
            calc, normalizer, verdict=Verdict.REFUTED, fusion=fusion, clusters=clusters,
            contradictions=[Contradiction(claim_id="c", contradiction_type=ContradictionType.NUMERICAL,
                                          severity=Severity.HIGH, explanation="x")],
            maps=dict(
                relevance_by_id={"b1": 0.6, "b2": 0.6, "b3": 0.6, "s1": 0.9},
                quality_by_id={"b1": 0.35, "b2": 0.35, "b3": 0.35, "s1": 0.9},
                temporal_by_id={"b1": 1.0, "b2": 1.0, "b3": 1.0, "s1": 1.0},
                stance_by_id={"b1": "supporting", "b2": "supporting", "b3": "supporting", "s1": "contradicting"},
            ),
        )
        # naive 3/4 = 0.75; the real confidence in REFUTED is driven by quality/independence
        assert score != pytest.approx(0.75, abs=0.05)
        assert score > 0.6  # confident in REFUTED despite the 3:1 'vote'

    def test_confidence_grows_with_independent_corroboration(self, calc, normalizer):
        single = FusionSummary(
            supporting_evidence=1, total_evidence=1, independent_supporting_clusters=1,
            support_strength=0.8, max_support_quality=0.7, coverage=0.3,
        )
        corroborated = FusionSummary(
            supporting_evidence=3, total_evidence=3, independent_supporting_clusters=3,
            support_strength=2.2, max_support_quality=0.9, coverage=0.8,
        )
        s1, _, _ = _compute(
            calc, normalizer, verdict=Verdict.VERIFIED, fusion=single, clusters=[], contradictions=[],
            maps=dict(relevance_by_id={"e1": 0.8}, quality_by_id={"e1": 0.7},
                      temporal_by_id={"e1": 0.9}, stance_by_id={"e1": "supporting"}),
        )
        s2, _, _ = _compute(
            calc, normalizer, verdict=Verdict.VERIFIED, fusion=corroborated, clusters=[], contradictions=[],
            maps=dict(
                relevance_by_id={"e1": 0.9, "e2": 0.85, "e3": 0.8},
                quality_by_id={"e1": 0.9, "e2": 0.7, "e3": 0.7},
                temporal_by_id={"e1": 1.0, "e2": 1.0, "e3": 1.0},
                stance_by_id={"e1": "supporting", "e2": "supporting", "e3": "supporting"},
            ),
        )
        assert s2 > s1


class TestVerdictAwareness:
    def test_balanced_conflict_yields_moderate_confidence(self, calc, normalizer):
        fusion = FusionSummary(
            supporting_evidence=1, contradicting_evidence=1, total_evidence=2,
            independent_supporting_clusters=1, independent_contradicting_clusters=1,
            support_strength=0.8, contradict_strength=0.8,
            max_support_quality=0.7, max_contradict_quality=0.7, coverage=0.6,
        )
        score, _, explanation = _compute(
            calc, normalizer, verdict=Verdict.CONFLICTED, fusion=fusion, clusters=[], contradictions=[],
            maps=dict(relevance_by_id={"e1": 0.8, "e2": 0.8}, quality_by_id={"e1": 0.7, "e2": 0.7},
                      temporal_by_id={"e1": 1.0, "e2": 1.0},
                      stance_by_id={"e1": "supporting", "e2": "contradicting"}),
        )
        assert 0.3 <= score <= 0.9
        assert "CONFLICTED" in explanation
