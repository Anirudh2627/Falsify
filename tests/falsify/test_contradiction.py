"""Tests for contradiction detection."""

from __future__ import annotations

import pytest

from app.falsify.analysis.contradiction import ContradictionDetector
from app.falsify.analysis.evidence import EvidenceAnalyzer
from app.falsify.models import ContradictionType, Severity
from app.falsify.normalization.normalizer import ClaimNormalizer
from tests.conftest import make_evidence


@pytest.fixture
def normalizer(config):
    return ClaimNormalizer(config)


@pytest.fixture
def analyzer(config):
    return EvidenceAnalyzer(config)


@pytest.fixture
def detector(config):
    return ContradictionDetector(config)


def _assess(claim, ev, analyzer):
    return (ev, analyzer.assess(claim, ev))


class TestNumericContradictions:
    def test_20_vs_19_8_is_at_most_low_severity(self, normalizer, analyzer, detector):
        """Spec example: rounding-compatible figures must NOT become a hard contradiction."""
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        ev = make_evidence(
            url="https://www.reuters.com/a", title="Company X results",
            text="Company X revenue increased 19.8% in 2025, per the annual report.",
            publication_date="2026-02-01",
        )
        contradictions = detector.detect(claim, [_assess(claim, ev, analyzer)])
        assert contradictions == []  # analyzer treats it as support -> no contradiction at all

    def test_20_vs_20_yoy_is_support(self, normalizer, analyzer, detector):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        ev = make_evidence(
            url="https://www.reuters.com/b", title="Company X results",
            text="Company X revenue increased 20% year-over-year in 2025.",
            publication_date="2026-02-01",
        )
        assert detector.detect(claim, [_assess(claim, ev, analyzer)]) == []

    def test_30_claim_vs_21_official_is_high_severity(self, normalizer, analyzer, detector):
        """Spec case 3: 'exactly 30%' vs official 21% -> high-severity numerical contradiction."""
        claim = normalizer.normalize("Company X revenue increased by exactly 30% in 2025.")
        ev = make_evidence(
            url="https://www.companyx.com/report", title="Company X Official Report 2025",
            text="Company X total revenue increased 21% in 2025 compared with 2024.",
            publication_date="2026-02-15",
        )
        contradictions = detector.detect(claim, [_assess(claim, ev, analyzer)])
        assert len(contradictions) == 1
        c = contradictions[0]
        assert c.contradiction_type == ContradictionType.NUMERICAL
        assert c.severity in (Severity.HIGH, Severity.CRITICAL)
        assert ev.evidence_id in c.evidence_ids

    def test_direction_flip_is_critical(self, normalizer, analyzer, detector):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        ev = make_evidence(
            url="https://www.bloomberg.com/c", title="Company X revenue falls",
            text="Company X revenue declined 4% in 2025.",
            publication_date="2026-01-15",
        )
        contradictions = detector.detect(claim, [_assess(claim, ev, analyzer)])
        assert len(contradictions) == 1
        assert contradictions[0].severity == Severity.CRITICAL
        assert contradictions[0].contradiction_type == ContradictionType.NUMERICAL

    def test_moderate_gap_is_medium(self, normalizer, analyzer, detector):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        ev = make_evidence(
            url="https://www.reuters.com/d", title="Company X results",
            text="Company X revenue increased 16% in 2025, according to its filing.",
            publication_date="2026-02-01",
        )
        contradictions = detector.detect(claim, [_assess(claim, ev, analyzer)])
        assert len(contradictions) == 1
        assert contradictions[0].severity in (Severity.MEDIUM, Severity.HIGH)


class TestNonNumericContradictionHandling:
    def test_irrelevant_evidence_never_contradicts(self, normalizer, analyzer, detector):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        ev = make_evidence(
            url="https://sports.example/nba", title="NBA scores",
            text="The Lakers increased their win total by 20% in the 2025 season.",
            publication_date="2026-01-01",
        )
        assert detector.detect(claim, [_assess(claim, ev, analyzer)]) == []

    def test_factual_refutation_detected(self, normalizer, analyzer, detector):
        claim = normalizer.normalize("The Sun orbits the Earth.")
        ev = make_evidence(
            url="https://science.nasa.gov/x", title="NASA Solar System",
            text="The geocentric model is false and was disproven centuries ago: Earth orbits the Sun, not the other way around.",
            publication_date="2025-01-01",
        )
        contradictions = detector.detect(claim, [_assess(claim, ev, analyzer)])
        assert len(contradictions) >= 1
        assert contradictions[0].severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)


class TestDefinitionalAndScope:
    def test_definitional_cue_retypes_contradiction(self, normalizer, analyzer, detector):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        ev = make_evidence(
            url="https://www.reuters.com/e", title="Company X adjusted figures",
            text=(
                "On a non-GAAP adjusted basis, excluding one-time items, Company X revenue "
                "increased 14% in 2025."
            ),
            publication_date="2026-02-01",
        )
        contradictions = detector.detect(claim, [_assess(claim, ev, analyzer)])
        assert contradictions
        assert contradictions[0].contradiction_type == ContradictionType.DEFINITIONAL


class TestMerging:
    def test_same_type_contradictions_merge(self, normalizer, analyzer, detector):
        claim = normalizer.normalize("Company X revenue increased by exactly 30% in 2025.")
        ev1 = make_evidence(
            url="https://www.reuters.com/f1", title="R1",
            text="Company X revenue increased 21% in 2025.", publication_date="2026-02-01",
        )
        ev2 = make_evidence(
            url="https://www.bloomberg.com/f2", title="R2",
            text="Company X revenue increased 22% in 2025.", publication_date="2026-02-02",
        )
        contradictions = detector.detect(claim, [_assess(claim, ev1, analyzer), _assess(claim, ev2, analyzer)])
        numerical = [c for c in contradictions if c.contradiction_type == ContradictionType.NUMERICAL]
        assert len(numerical) == 1
        assert len(numerical[0].evidence_ids) == 2

    def test_supporting_evidence_produces_no_contradiction(self, normalizer, analyzer, detector):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        ev = make_evidence(
            url="https://www.companyx.com/g", title="Company X report",
            text="Company X revenue increased 20% in 2025.", publication_date="2026-02-01",
        )
        assert detector.detect(claim, [_assess(claim, ev, analyzer)]) == []
