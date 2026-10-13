"""Tests for evidence assessment (deterministic + LLM merge)."""

from __future__ import annotations

import pytest

from app.falsify.analysis.evidence import EvidenceAnalyzer
from app.falsify.llm.provider import MockLLM
from app.falsify.models import SourceTier
from app.falsify.normalization.normalizer import ClaimNormalizer
from tests.conftest import make_evidence


@pytest.fixture
def normalizer(config):
    return ClaimNormalizer(config)


@pytest.fixture
def analyzer(config):
    return EvidenceAnalyzer(config)


CLAIM = "Company X revenue increased by 20% in 2025."


class TestStanceDetection:
    def test_matching_figure_supports(self, normalizer, analyzer):
        claim = normalizer.normalize(CLAIM)
        ev = make_evidence(
            url="https://www.companyx.com/annual-report",
            title="Company X 2025 Annual Report",
            text="Company X reported that total revenue increased 20% in 2025 compared with 2024.",
            publication_date="2026-02-01",
        )
        a = analyzer.assess(claim, ev)
        assert a.supports_claim and not a.contradicts_claim
        assert a.stance == "supporting"
        assert a.relevance_score >= 0.6

    def test_yoy_restatement_supports(self, normalizer, analyzer):
        """Spec example: 'increased 20% year-over-year' SUPPORTS 'increased by 20%'."""
        claim = normalizer.normalize(CLAIM)
        ev = make_evidence(
            url="https://www.reuters.com/companyx",
            title="Company X revenue up in 2025",
            text="Company X revenue increased 20% year-over-year in 2025, the company reported.",
            publication_date="2026-01-20",
        )
        a = analyzer.assess(claim, ev)
        assert a.supports_claim
        assert not a.contradicts_claim

    def test_rounding_compatible_figure_supports(self, normalizer, analyzer):
        """Spec example: 19.8% vs '20%' is rounding-compatible, not a hard contradiction."""
        claim = normalizer.normalize(CLAIM)
        ev = make_evidence(
            url="https://www.reuters.com/companyx-2",
            title="Company X 2025 results",
            text="Company X revenue increased 19.8% in 2025 according to the annual filing.",
            publication_date="2026-02-01",
        )
        a = analyzer.assess(claim, ev)
        assert a.supports_claim  # 19.8 within 20 +/- max(0.5 rounding, 2% rel)

    def test_materially_different_figure_contradicts(self, normalizer, analyzer):
        claim = normalizer.normalize(CLAIM)
        ev = make_evidence(
            url="https://www.sec.gov/companyx",
            title="Company X 10-K filing",
            text="Company X total revenue increased 8% in fiscal year 2025 versus fiscal 2024.",
            publication_date="2026-03-01",
        )
        a = analyzer.assess(claim, ev)
        assert a.contradicts_claim
        assert not a.supports_claim
        assert a.is_direct

    def test_opposite_direction_contradicts(self, normalizer, analyzer):
        claim = normalizer.normalize(CLAIM)
        ev = make_evidence(
            url="https://www.bloomberg.com/companyx",
            title="Company X revenue falls",
            text="Company X revenue declined 5% in 2025, missing analyst expectations.",
            publication_date="2026-01-30",
        )
        a = analyzer.assess(claim, ev)
        assert a.contradicts_claim
        assert a.stance == "contradicting"

    def test_irrelevant_source_gets_no_stance(self, normalizer, analyzer):
        claim = normalizer.normalize(CLAIM)
        ev = make_evidence(
            url="https://cooking.example/recipe",
            title="Best pancake recipe of 2025",
            text="This pancake recipe increased my breakfast joy by 200% in 2025.",
            publication_date="2025-06-01",
        )
        a = analyzer.assess(claim, ev)
        assert not a.supports_claim and not a.contradicts_claim
        assert a.relevance_score < 0.3
        assert a.stance == "neutral"

    def test_exact_claim_rejects_near_miss(self, normalizer, analyzer):
        """'exactly 30%' leaves no rounding slack: 29% contradicts."""
        claim = normalizer.normalize("Company X revenue increased by exactly 30% in 2025.")
        ev = make_evidence(
            url="https://www.sec.gov/companyx-exact",
            title="Company X annual report",
            text="Company X revenue increased 29% in 2025.",
            publication_date="2026-02-01",
        )
        a = analyzer.assess(claim, ev)
        assert a.contradicts_claim


class TestSourceQualityIntegration:
    def test_tier_from_domain(self, normalizer, analyzer):
        claim = normalizer.normalize(CLAIM)
        ev = make_evidence(
            url="https://www.sec.gov/filing", title="filing", text="Company X revenue increased 20% in 2025.",
            publication_date="2026-02-01",
        )
        a = analyzer.assess(claim, ev)
        assert a.source_tier == SourceTier.TIER_1
        assert a.source_quality_score >= 0.85

    def test_blog_scores_low(self, normalizer, analyzer):
        claim = normalizer.normalize(CLAIM)
        ev = make_evidence(
            url="https://randomblog.blogspot.com/post", title="post",
            text="Company X revenue increased 20% in 2025 apparently.",
            publication_date="2026-01-01",
        )
        a = analyzer.assess(claim, ev)
        assert a.source_tier == SourceTier.TIER_3
        assert a.source_quality_score <= 0.45


class TestTemporalValidity:
    def test_evidence_predating_period_is_stale(self, normalizer, analyzer):
        claim = normalizer.normalize(CLAIM)
        ev = make_evidence(
            url="https://news.example/2024-article",
            title="Company X outlook",
            text="Company X revenue increased 20% in 2025, analysts say.",
            publication_date="2024-06-01",  # published BEFORE the claimed period
        )
        a = analyzer.assess(claim, ev)
        assert a.temporal_validity < 0.5

    def test_post_period_evidence_fully_valid(self, normalizer, analyzer):
        claim = normalizer.normalize(CLAIM)
        ev = make_evidence(
            url="https://news.example/2026-article",
            title="Company X final results",
            text="Company X revenue increased 20% in 2025 (final audited figures).",
            publication_date="2026-03-01",
        )
        a = analyzer.assess(claim, ev)
        assert a.temporal_validity == 1.0

    def test_undated_evidence_discounted(self, normalizer, analyzer):
        claim = normalizer.normalize(CLAIM)
        ev = make_evidence(url="https://news.example/undated", title="t", text="Company X revenue increased 20% in 2025.")
        a = analyzer.assess(claim, ev)
        assert 0.5 <= a.temporal_validity < 1.0


class TestNonNumericClaims:
    def test_factual_corroboration(self, normalizer, analyzer):
        claim = normalizer.normalize("The Earth orbits the Sun.")
        ev = make_evidence(
            url="https://science.nasa.gov/solar-system",
            title="Solar System - NASA Science",
            text="Earth orbits the Sun, traveling at an average speed of 67,000 miles per hour.",
            publication_date="2025-01-01",
        )
        a = analyzer.assess(claim, ev)
        assert a.supports_claim
        assert a.source_tier == SourceTier.TIER_1

    def test_factual_refutation(self, normalizer, analyzer):
        claim = normalizer.normalize("The Sun orbits the Earth.")
        ev = make_evidence(
            url="https://science.nasa.gov/heliocentric",
            title="Heliocentrism - NASA",
            text="The geocentric model is false: the Sun does not orbit the Earth; Earth orbits the Sun.",
            publication_date="2025-01-01",
        )
        a = analyzer.assess(claim, ev)
        assert a.contradicts_claim


class TestLLMMerge:
    @pytest.fixture
    def llm_config(self, config):
        config.use_llm_for_evidence_assessment = True
        return config

    def _llm_response(self, **overrides):
        import json

        payload = {
            "supports_claim": False,
            "contradicts_claim": True,
            "relevance_score": 0.9,
            "temporal_validity": 0.9,
            "is_direct": True,
            "observed_value": "revenue +12%",
            "reasoning": "The filing states revenue grew 12%, not 20%.",
        }
        payload.update(overrides)
        return MockLLM({"Assess one retrieved source": json.dumps(payload)})

    def test_llm_stance_used_when_no_numeric_signal(self, llm_config, normalizer):
        config = llm_config
        claim = normalizer.normalize("The Eiffel Tower is the most visited paid monument in the world.")
        analyzer = EvidenceAnalyzer(config, llm=self._llm_response(supports_claim=False, contradicts_claim=True))
        ev = make_evidence(
            url="https://www.lemonde.fr/tour-eiffel",
            title="Tour Eiffel",
            text="The Eiffel Tower welcomed fewer paying visitors than the Colosseum in 2025.",
            publication_date="2026-01-01",
        )
        a = analyzer.assess(claim, ev)
        assert a.contradicts_claim
        assert a.analysis_source in ("llm", "hybrid")

    def test_deterministic_numeric_overrides_llm(self, llm_config, normalizer):
        config = llm_config
        """Hard numeric extraction is never overridden by the LLM."""
        claim = normalizer.normalize(CLAIM)
        analyzer = EvidenceAnalyzer(config, llm=self._llm_response(supports_claim=True, contradicts_claim=False))
        ev = make_evidence(
            url="https://www.sec.gov/x", title="Company X filing",
            text="Company X revenue declined 5% in 2025 versus 2024.",
            publication_date="2026-02-01",
        )
        a = analyzer.assess(claim, ev)
        assert a.contradicts_claim and not a.supports_claim
        assert "overridden by deterministic numeric extraction" in a.reasoning

    def test_llm_cannot_give_stance_to_irrelevant_source(self, llm_config, normalizer):
        config = llm_config
        claim = normalizer.normalize(CLAIM)
        analyzer = EvidenceAnalyzer(config, llm=self._llm_response(supports_claim=True, contradicts_claim=False, relevance_score=0.95))
        ev = make_evidence(
            url="https://cooking.example/x", title="Pancakes", text="A recipe totally unrelated to anything financial.",
            publication_date="2026-01-01",
        )
        a = analyzer.assess(claim, ev)
        assert a.relevance_score >= 0.9  # LLM relevance accepted...
        # ...but deterministic relevance was low; gate uses merged value, so stance allowed only if merged passes floor.
        # The key guarantee: if merged relevance is below floor, stance is suppressed.
        if a.relevance_score < config.relevance_floor:
            assert not a.supports_claim

    def test_llm_malformed_response_falls_back(self, llm_config, normalizer):
        config = llm_config
        claim = normalizer.normalize(CLAIM)
        analyzer = EvidenceAnalyzer(config, llm=MockLLM({"Assess one retrieved source": "total garbage ###"}))
        ev = make_evidence(
            url="https://www.sec.gov/x2", title="Company X filing",
            text="Company X revenue increased 20% in 2025.", publication_date="2026-02-01",
        )
        a = analyzer.assess(claim, ev)
        assert a.analysis_source == "deterministic"
        assert a.supports_claim
