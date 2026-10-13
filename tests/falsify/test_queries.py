"""Tests for adversarial search query generation."""

from __future__ import annotations

import pytest

from app.falsify.hypotheses.generator import FalsificationEngine
from app.falsify.models import HypothesisCategory, QueryType
from app.falsify.normalization.normalizer import ClaimNormalizer
from app.falsify.queries.generator import AdversarialQueryGenerator


@pytest.fixture
def normalizer(config):
    return ClaimNormalizer(config)


@pytest.fixture
def falsification(config):
    return FalsificationEngine(config)


@pytest.fixture
def generator(config):
    return AdversarialQueryGenerator(config)


def _hyp(claim, falsification, category):
    for h in falsification.generate_hypotheses(claim):
        if h.category == category:
            return h
    pytest.fail(f"no {category} hypothesis generated")


class TestAdversarialQueries:
    def test_queries_are_adversarial_not_claim_echo(self, normalizer, falsification, generator):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        hyp = _hyp(claim, falsification, HypothesisCategory.NUMERICAL)
        queries = generator.generate(claim, hyp)
        assert queries
        lowered = [q.query.lower() for q in queries]
        # must not merely echo the claim
        assert not any(q == "company x revenue increased by 20% in 2025" for q in lowered)
        joined = " ".join(lowered)
        # must actively probe counterevidence / primary figures
        assert any(word in joined for word in ("decline", "actual", "discrepancy", "restated", "corrected", "compared"))

    def test_primary_source_queries_generated(self, normalizer, falsification, generator):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        all_types = set()
        for hyp in falsification.generate_hypotheses(claim):
            for q in generator.generate(claim, hyp):
                all_types.add(q.query_type)
        assert QueryType.PRIMARY_SOURCE in all_types
        assert QueryType.CONTRADICTION in all_types
        assert QueryType.RECENCY in all_types or QueryType.ALTERNATIVE_INTERPRETATION in all_types

    def test_queries_per_hypothesis_capped(self, config, normalizer, falsification):
        config.max_queries_per_hypothesis = 2
        generator = AdversarialQueryGenerator(config)
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        hyp = _hyp(claim, falsification, HypothesisCategory.NUMERICAL)
        assert len(generator.generate(claim, hyp)) <= 2

    def test_exclude_dedupes_across_hypotheses(self, normalizer, falsification, generator):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        hyp1 = _hyp(claim, falsification, HypothesisCategory.NUMERICAL)
        hyp2 = _hyp(claim, falsification, HypothesisCategory.SOURCE)
        first = generator.generate(claim, hyp1)
        exclude = {q.query for q in first}
        second = generator.generate(claim, hyp2, exclude=exclude)
        assert not ({q.query.lower() for q in first} & {q.query.lower() for q in second})

    def test_query_metadata_populated(self, normalizer, falsification, generator):
        claim = normalizer.normalize("Tesla's revenue increased by 20% in 2025.")
        hyp = _hyp(claim, falsification, HypothesisCategory.NUMERICAL)
        for q in generator.generate(claim, hyp):
            assert q.hypothesis_id == hyp.hypothesis_id
            assert q.claim_id == claim.claim_id
            assert q.rationale
            assert q.query.strip()

    def test_definitional_queries_probe_definitions(self, normalizer, falsification, generator):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        hyp = _hyp(claim, falsification, HypothesisCategory.DEFINITIONAL)
        joined = " ".join(q.query.lower() for q in generator.generate(claim, hyp))
        assert "definition" in joined or "gaap" in joined or "methodology" in joined

    def test_factual_claim_queries_search_for_refutation(self, normalizer, falsification, generator):
        claim = normalizer.normalize("The Earth is the center of the solar system and the Sun orbits Earth.")
        joined_all = ""
        for hyp in falsification.generate_hypotheses(claim):
            joined_all += " " + " ".join(q.query.lower() for q in generator.generate(claim, hyp))
        assert any(w in joined_all for w in ("debunked", "disproven", "myth", "reversed", "criticism", "false"))

    def test_causal_claim_queries_target_confounders(self, normalizer, falsification, generator):
        claim = normalizer.normalize("Social media use causes depression in teenagers.")
        hyp = _hyp(claim, falsification, HypothesisCategory.CAUSAL)
        joined = " ".join(q.query.lower() for q in generator.generate(claim, hyp))
        assert "correlation" in joined or "confound" in joined or "reverse" in joined

    def test_queries_bounded_overall(self, config, normalizer, falsification):
        config.max_queries_per_hypothesis = 3
        config.max_hypotheses = 6
        generator = AdversarialQueryGenerator(config)
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        total = sum(len(generator.generate(claim, h)) for h in falsification.generate_hypotheses(claim))
        assert total <= config.max_hypotheses * config.max_queries_per_hypothesis
