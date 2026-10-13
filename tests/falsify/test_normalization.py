"""Tests for deterministic claim normalization."""

from __future__ import annotations

import pytest

from app.falsify.exceptions import ClaimValidationError
from app.falsify.llm.provider import MockLLM
from app.falsify.models import ClaimKind
from app.falsify.normalization.normalizer import ClaimNormalizer


@pytest.fixture
def normalizer(config):
    return ClaimNormalizer(config)


class TestQuantitativeNormalization:
    def test_tesla_style_revenue_claim(self, normalizer):
        claim = normalizer.normalize("Tesla's revenue increased by 20% in 2025.")
        assert claim.original_text == "Tesla's revenue increased by 20% in 2025."
        assert any("tesla" in e.lower() for e in claim.entities)
        q = claim.primary_quantity
        assert q is not None
        assert q.metric == "revenue"
        assert q.value == 20.0
        assert q.unit == "percent"
        assert q.direction == "increased"
        assert "2025" in claim.temporal_constraints
        assert claim.claim_kind == ClaimKind.QUANTITATIVE_CHANGE
        assert claim.normalized_text  # canonical restatement produced
        assert claim.normalization_source == "deterministic"

    def test_company_x_placeholder_entity(self, normalizer):
        claim = normalizer.normalize("Company X grew revenue by 40% in 2025.")
        assert "Company X" in claim.entities
        q = claim.primary_quantity
        assert q.value == 40.0
        assert q.direction == "increased"
        assert q.metric == "revenue"

    def test_exact_comparator_and_precision(self, normalizer):
        claim = normalizer.normalize("Company X revenue increased by exactly 30% in 2025.")
        q = claim.primary_quantity
        assert q.comparator == "exactly"
        assert q.implied_precision == 0.5  # "30" implies +/-0.5 rounding

    def test_decimal_precision(self, normalizer):
        claim = normalizer.normalize("Acme Corp profit rose 21.7% last year.")
        q = claim.primary_quantity
        assert q.value == pytest.approx(21.7)
        assert q.implied_precision == pytest.approx(0.05)
        assert "last year" in claim.temporal_constraints

    def test_currency_amount(self, normalizer):
        claim = normalizer.normalize("Apple's revenue was $391 billion in 2024.")
        q = claim.primary_quantity
        assert q is not None
        assert q.unit == "USD"
        assert q.value == pytest.approx(391e9)
        assert claim.claim_kind == ClaimKind.QUANTITATIVE_STATE

    def test_decline_direction(self, normalizer):
        claim = normalizer.normalize("Nokia's market share declined by 5% in 2023.")
        q = claim.primary_quantity
        assert q.direction == "decreased"

    def test_comparison_baseline(self, normalizer):
        claim = normalizer.normalize("Revenue at Intel increased 12% in 2024 compared with 2023.")
        q = claim.primary_quantity
        assert q.comparison_baseline in {"2023"}


class TestNonQuantitativeNormalization:
    def test_factual_claim(self, normalizer):
        claim = normalizer.normalize("The Earth orbits the Sun.")
        entities_lower = [e.lower() for e in claim.entities]
        assert "earth" in entities_lower
        assert "sun" in entities_lower
        assert "orbits" in claim.predicates
        assert claim.claim_kind == ClaimKind.FACTUAL

    def test_geocentric_claim(self, normalizer):
        claim = normalizer.normalize("The Earth is the center of the solar system and the Sun orbits Earth.")
        assert claim.claim_kind == ClaimKind.FACTUAL
        assert len(claim.assertions) >= 1

    def test_causal_claim(self, normalizer):
        claim = normalizer.normalize("Smoking causes lung cancer.")
        assert claim.claim_kind == ClaimKind.CAUSAL

    def test_future_claim(self, normalizer):
        claim = normalizer.normalize("Tesla will deliver 5 million cars in 2030.")
        assert claim.claim_kind == ClaimKind.FUTURE
        assert claim.is_future_claim

    def test_future_relative_year(self, normalizer):
        claim = normalizer.normalize("The company will double revenue next year.")
        assert claim.is_future_claim

    def test_negation_detected(self, normalizer):
        claim = normalizer.normalize("Vaccines do not cause autism.")
        assert claim.negated

    def test_geographic_constraint(self, normalizer):
        claim = normalizer.normalize("Unemployment in France fell below 7% in 2024.")
        assert any("france" in g.lower() for g in claim.geographic_constraints)

    def test_quarter_extraction(self, normalizer):
        claim = normalizer.normalize("NVIDIA revenue grew 50% in Q3 2025.")
        assert any("Q3" in t for t in claim.temporal_constraints)


class TestMultipleAssertions:
    def test_splits_assertions(self, normalizer):
        claim = normalizer.normalize(
            "Company X grew revenue by 40% in 2025. Company X also hired 5000 employees."
        )
        assert len(claim.assertions) >= 2


class TestOriginalPreserved:
    def test_original_text_untouched(self, normalizer):
        messy = "  tesla's   REVENUE increased by 20% in 2025!!!  "
        claim = normalizer.normalize(messy)
        assert claim.original_text == messy.strip()


class TestLLMRefinement:
    def test_llm_merges_extra_entity(self, config):
        config.use_llm_for_normalization = True
        llm = MockLLM(
            {
                "Normalize the following claim": (
                    '{"entities": ["Tesla Inc"], "temporal_constraints": ["FY2025"], '
                    '"claim_kind": "quantitative_change", "negated": false, "is_future_claim": false, '
                    '"normalized_text": "Tesla Inc\'s total revenue rose 20% in fiscal 2025."}'
                )
            }
        )
        normalizer = ClaimNormalizer(config, llm=llm)
        claim = normalizer.normalize("Tesla's revenue increased by 20% in 2025.")
        assert claim.normalization_source == "hybrid"
        assert "Tesla Inc" in claim.entities
        assert claim.normalized_text.startswith("Tesla Inc")
        # deterministic quantity survives the merge
        assert claim.primary_quantity.value == 20.0

    def test_llm_failure_falls_back_to_deterministic(self, config):
        config.use_llm_for_normalization = True
        llm = MockLLM({"Normalize the following claim": "this is not json at all"})
        normalizer = ClaimNormalizer(config, llm=llm)
        claim = normalizer.normalize("Tesla's revenue increased by 20% in 2025.")
        assert claim.normalization_source == "deterministic"
        assert claim.primary_quantity.value == 20.0

    def test_llm_unavailable_falls_back(self, config):
        config.use_llm_for_normalization = True
        llm = MockLLM({})  # no scripted responses -> raises LLMUnavailableError
        normalizer = ClaimNormalizer(config, llm=llm)
        claim = normalizer.normalize("Company X grew revenue by 40% in 2025.")
        assert claim.normalization_source == "deterministic"


class TestInvalidInput:
    def test_empty_claim_raises(self, normalizer):
        with pytest.raises(ClaimValidationError):
            normalizer.normalize("")

    def test_whitespace_claim_raises(self, normalizer):
        with pytest.raises(ClaimValidationError):
            normalizer.normalize("   \n\t ")

    def test_too_long_claim_raises(self, normalizer):
        with pytest.raises(ClaimValidationError):
            normalizer.normalize("word " * 5000)
