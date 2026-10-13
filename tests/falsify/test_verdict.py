"""Tests for the deterministic verdict engine (rule level, no retrieval)."""

from __future__ import annotations

import pytest

from app.falsify.fusion.verdict import VerdictEngine
from app.falsify.models import Contradiction, ContradictionType, FusionSummary, Severity, Verdict
from app.falsify.normalization.normalizer import ClaimNormalizer


@pytest.fixture
def normalizer(config):
    return ClaimNormalizer(config)


@pytest.fixture
def engine(config):
    return VerdictEngine(config)


def _contradiction(severity=Severity.HIGH, ctype=ContradictionType.NUMERICAL):
    return Contradiction(claim_id="c", contradiction_type=ctype, severity=severity, explanation="test")


class TestUnverifiable:
    def test_no_evidence(self, normalizer, engine):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        decision = engine.decide(claim, FusionSummary(), [])
        assert decision.verdict == Verdict.UNVERIFIABLE

    def test_all_irrelevant(self, normalizer, engine):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        fusion = FusionSummary(total_evidence=5, neutral_evidence=5)
        assert engine.decide(claim, fusion, []).verdict == Verdict.UNVERIFIABLE

    def test_retrieval_failures(self, normalizer, engine):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        fusion = FusionSummary(retrieval_failures=10)
        decision = engine.decide(claim, fusion, [])
        assert decision.verdict == Verdict.UNVERIFIABLE
        assert "retrieval" in decision.rationale.lower()

    def test_future_claim_unsettled(self, normalizer, engine):
        claim = normalizer.normalize("Tesla will deliver 5 million cars in 2030.")
        fusion = FusionSummary(
            total_evidence=2, neutral_evidence=1, supporting_evidence=1, support_strength=0.5,
            max_support_quality=0.7,
        )
        assert engine.decide(claim, fusion, []).verdict == Verdict.UNVERIFIABLE


class TestVerified:
    def test_strong_tier1_support(self, normalizer, engine):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        fusion = FusionSummary(
            supporting_evidence=2, total_evidence=2,
            independent_supporting_clusters=2,
            support_strength=1.6, max_support_quality=0.9, coverage=0.5,
        )
        assert engine.decide(claim, fusion, []).verdict == Verdict.VERIFIED

    def test_single_tier1_source_suffices(self, normalizer, engine):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        fusion = FusionSummary(
            supporting_evidence=1, total_evidence=1,
            independent_supporting_clusters=1,
            support_strength=0.85, max_support_quality=0.9,
        )
        assert engine.decide(claim, fusion, []).verdict == Verdict.VERIFIED

    def test_weak_support_alone_is_not_verified(self, normalizer, engine):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        fusion = FusionSummary(
            supporting_evidence=1, total_evidence=1, independent_supporting_clusters=1,
            support_strength=0.5, max_support_quality=0.4,
        )
        assert engine.decide(claim, fusion, []).verdict in (Verdict.QUALIFIED, Verdict.UNVERIFIABLE)


class TestRefuted:
    def test_high_severity_contradiction_dominates(self, normalizer, engine):
        claim = normalizer.normalize("Company X revenue increased by exactly 30% in 2025.")
        fusion = FusionSummary(
            contradicting_evidence=1, total_evidence=1,
            independent_contradicting_clusters=1,
            contradict_strength=0.85, max_contradict_quality=0.9,
        )
        decision = engine.decide(claim, fusion, [_contradiction(Severity.HIGH)])
        assert decision.verdict == Verdict.REFUTED

    def test_critical_direction_flip(self, normalizer, engine):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        fusion = FusionSummary(
            contradicting_evidence=1, total_evidence=1, independent_contradicting_clusters=1,
            contradict_strength=0.8, max_contradict_quality=0.7,
        )
        assert engine.decide(claim, fusion, [_contradiction(Severity.CRITICAL)]).verdict == Verdict.REFUTED

    def test_low_severity_contradiction_does_not_refute(self, normalizer, engine):
        """19.8% vs 20% must never produce REFUTED."""
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        fusion = FusionSummary(
            supporting_evidence=2, contradicting_evidence=1, total_evidence=3,
            independent_supporting_clusters=2, independent_contradicting_clusters=1,
            support_strength=1.0, contradict_strength=0.5,
            max_support_quality=0.9, max_contradict_quality=0.7,
        )
        decision = engine.decide(claim, fusion, [_contradiction(Severity.LOW)])
        assert decision.verdict != Verdict.REFUTED
        assert decision.verdict in (Verdict.QUALIFIED, Verdict.VERIFIED, Verdict.CONFLICTED)

    def test_contradiction_dominant_low_severity_is_qualified(self, normalizer, engine):
        """Contradiction slightly stronger, credible, but only LOW severity -> QUALIFIED."""
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        fusion = FusionSummary(
            supporting_evidence=1, contradicting_evidence=1, total_evidence=2,
            independent_supporting_clusters=1, independent_contradicting_clusters=1,
            support_strength=0.5, contradict_strength=0.6,
            max_support_quality=0.4, max_contradict_quality=0.7,
        )
        decision = engine.decide(claim, fusion, [_contradiction(Severity.LOW)])
        assert decision.verdict == Verdict.QUALIFIED
        assert "max severity low" in decision.rationale


class TestConflicted:
    def test_both_sides_credible_and_balanced(self, normalizer, engine):
        """Spec case 4: two credible sources, materially different figures."""
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        fusion = FusionSummary(
            supporting_evidence=1, contradicting_evidence=1, total_evidence=2,
            independent_supporting_clusters=1, independent_contradicting_clusters=1,
            support_strength=0.8, contradict_strength=0.8,
            max_support_quality=0.7, max_contradict_quality=0.7,
        )
        decision = engine.decide(claim, fusion, [_contradiction(Severity.HIGH)])
        assert decision.verdict == Verdict.CONFLICTED

    def test_conflict_band_respected(self, normalizer, engine):
        """A 10:1 imbalance is not a 'conflict' -- it is a refutation."""
        claim = normalizer.normalize("Company X revenue increased by exactly 30% in 2025.")
        fusion = FusionSummary(
            supporting_evidence=1, contradicting_evidence=3, total_evidence=4,
            independent_supporting_clusters=1, independent_contradicting_clusters=3,
            support_strength=0.5, contradict_strength=2.5,
            max_support_quality=0.6, max_contradict_quality=0.9,
        )
        assert engine.decide(claim, fusion, [_contradiction(Severity.HIGH)]).verdict == Verdict.REFUTED

    def test_low_quality_both_sides_not_conflicted_but_unverifiable(self, normalizer, engine):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        fusion = FusionSummary(
            supporting_evidence=2, contradicting_evidence=2, total_evidence=4,
            independent_supporting_clusters=2, independent_contradicting_clusters=2,
            support_strength=0.6, contradict_strength=0.6,
            max_support_quality=0.35, max_contradict_quality=0.35,
        )
        assert engine.decide(claim, fusion, [_contradiction(Severity.MEDIUM)]).verdict == Verdict.UNVERIFIABLE


class TestQualified:
    def test_support_with_unresolved_qualification(self, normalizer, engine):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        fusion = FusionSummary(
            supporting_evidence=2, contradicting_evidence=1, total_evidence=3,
            independent_supporting_clusters=2, independent_contradicting_clusters=1,
            support_strength=1.4, contradict_strength=0.3,
            max_support_quality=0.9, max_contradict_quality=0.7,
        )
        c = _contradiction(Severity.MEDIUM, ContradictionType.DEFINITIONAL)
        assert engine.decide(claim, fusion, [c]).verdict == Verdict.QUALIFIED

    def test_determinism(self, normalizer, engine):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        fusion = FusionSummary(supporting_evidence=2, total_evidence=2, independent_supporting_clusters=2,
                               support_strength=1.6, max_support_quality=0.9)
        first = engine.decide(claim, fusion, [])
        second = engine.decide(claim, fusion, [])
        assert first.verdict == second.verdict == Verdict.VERIFIED
        assert first.rationale == second.rationale
