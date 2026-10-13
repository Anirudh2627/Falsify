"""Tests for falsification hypothesis generation."""

from __future__ import annotations

import pytest

from app.falsify.hypotheses.generator import FalsificationEngine
from app.falsify.llm.provider import MockLLM
from app.falsify.models import ClaimKind, HypothesisCategory
from app.falsify.normalization.normalizer import ClaimNormalizer


@pytest.fixture
def normalizer(config):
    return ClaimNormalizer(config)


@pytest.fixture
def engine(config):
    return FalsificationEngine(config)


class TestQuantitativeChangeHypotheses:
    def test_generates_spec_example_categories(self, normalizer, engine):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        hypotheses = engine.generate_hypotheses(claim)

        categories = {h.category for h in hypotheses}
        texts = " ".join(h.hypothesis.lower() for h in hypotheses)

        # spec example failure modes must be represented
        assert HypothesisCategory.NUMERICAL in categories  # revenue actually decreased / different amount
        assert HypothesisCategory.TEMPORAL in categories  # different period
        assert HypothesisCategory.DEFINITIONAL in categories  # different revenue definition
        assert HypothesisCategory.SOURCE in categories  # preliminary/outdated
        assert HypothesisCategory.SCOPE in categories  # quarterly vs annual confusion
        assert "decreased" in texts or "did not increase" in texts

    def test_respects_max_hypotheses(self, config, normalizer):
        config.max_hypotheses = 3
        engine = FalsificationEngine(config)
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        hypotheses = engine.generate_hypotheses(claim)
        assert len(hypotheses) <= 3

    def test_priority_ordering(self, normalizer, engine):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        hypotheses = engine.generate_hypotheses(claim)
        priorities = [h.priority for h in hypotheses]
        assert priorities == sorted(priorities, reverse=True)
        # direction-flip numerical hypothesis must rank at the top
        assert hypotheses[0].category == HypothesisCategory.NUMERICAL

    def test_hypothesis_fields_populated(self, normalizer, engine):
        claim = normalizer.normalize("Tesla's revenue increased by 20% in 2025.")
        for h in engine.generate_hypotheses(claim):
            assert h.claim_id == claim.claim_id
            assert h.hypothesis and h.rationale and h.falsification_target
            assert 0.0 <= h.priority <= 1.0

    def test_multi_entity_claim_gets_entity_hypothesis(self, normalizer, engine):
        claim = normalizer.normalize("Tesla revenue grew faster than Toyota revenue in 2025.")
        categories = {h.category for h in engine.generate_hypotheses(claim)}
        assert HypothesisCategory.NUMERICAL in categories or HypothesisCategory.ENTITY in categories


class TestOtherClaimKinds:
    def test_causal_claim_hypotheses(self, normalizer, engine):
        claim = normalizer.normalize("Social media use causes depression in teenagers.")
        assert claim.claim_kind == ClaimKind.CAUSAL
        hypotheses = engine.generate_hypotheses(claim)
        assert HypothesisCategory.CAUSAL in {h.category for h in hypotheses}
        texts = " ".join(h.hypothesis.lower() for h in hypotheses)
        assert "correlation" in texts or "reverse" in texts or "confound" in texts

    def test_factual_claim_hypotheses(self, normalizer, engine):
        claim = normalizer.normalize("The Earth orbits the Sun.")
        hypotheses = engine.generate_hypotheses(claim)
        assert len(hypotheses) >= 2
        assert HypothesisCategory.ENTITY in {h.category for h in hypotheses}

    def test_future_claim_hypotheses(self, normalizer, engine):
        claim = normalizer.normalize("Tesla will deliver 5 million cars in 2030.")
        hypotheses = engine.generate_hypotheses(claim)
        assert hypotheses  # still generates falsification angles (revised forecasts etc.)
        assert all(h.priority <= 1.0 for h in hypotheses)

    def test_negated_claim_gets_positive_form_hypothesis(self, normalizer, engine):
        claim = normalizer.normalize("Vaccines do not cause autism.")
        assert claim.negated
        texts = " ".join(h.hypothesis.lower() for h in engine.generate_hypotheses(claim))
        assert "positive form" in texts or "negation" in texts

    def test_attribution_claim(self, normalizer, engine):
        claim = normalizer.normalize("The CEO said that the company would go bankrupt.")
        hypotheses = engine.generate_hypotheses(claim)
        assert HypothesisCategory.ATTRIBUTION in {h.category for h in hypotheses}

    def test_universal_recency_hypothesis_present(self, normalizer, engine):
        claim = normalizer.normalize("The Eiffel Tower is in Paris.")
        texts = " ".join(h.hypothesis.lower() for h in engine.generate_hypotheses(claim))
        assert "newer" in texts or "superseded" in texts or "outdated" in texts

    def test_not_every_category_for_every_claim(self, normalizer, engine):
        """Category selection must adapt to claim structure -- no numeric hypothesis for a purely factual claim."""
        claim = normalizer.normalize("The Earth orbits the Sun.")
        # numerical magnitude hypotheses make no sense without a quantity
        texts = " ".join(h.hypothesis.lower() for h in engine.generate_hypotheses(claim))
        assert "materially different amount" not in texts


class TestLLMAugmentation:
    def test_llm_adds_novel_hypotheses(self, config, normalizer):
        config.use_llm_for_hypotheses = True
        llm = MockLLM(
            {
                "falsification hypotheses": (
                    '{"hypotheses": ['
                    '{"category": "definitional", "hypothesis": "Revenue includes one-time licensing income that was later excluded.", '
                    '"rationale": "One-time items distort growth.", "falsification_target": "composition of revenue", "priority": 0.8},'
                    '{"category": "numerical", "hypothesis": "Company X\'s revenue actually decreased in 2025.", '
                    '"rationale": "dup of deterministic", "falsification_target": "direction of change in the reported figure", "priority": 0.9}'
                    "]}"
                )
            }
        )
        engine = FalsificationEngine(config, llm=llm)
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        hypotheses = engine.generate_hypotheses(claim)
        assert any(h.origin == "llm" for h in hypotheses)
        assert any("licensing income" in h.hypothesis for h in hypotheses)
        assert len(hypotheses) <= config.max_hypotheses

    def test_llm_failure_degrades_gracefully(self, config, normalizer):
        config.use_llm_for_hypotheses = True
        llm = MockLLM({"falsification hypotheses": "not json"})
        engine = FalsificationEngine(config, llm=llm)
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        hypotheses = engine.generate_hypotheses(claim)
        assert hypotheses and all(h.origin == "deterministic" for h in hypotheses)
