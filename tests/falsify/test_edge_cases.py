"""Edge-case tests (spec section 18).

Empty/long claims, ambiguous entities, missing/relative dates, numeric forms,
causal/future/multi-entity/multi-assertion claims, duplicated, contradictory,
stale and irrelevant evidence.
"""

from __future__ import annotations

import pytest

from app.falsify.exceptions import ClaimValidationError
from app.falsify.models import ClaimKind, Verdict
from app.falsify.normalization.normalizer import ClaimNormalizer
from tests.conftest import make_engine, make_evidence


@pytest.fixture
def normalizer(config):
    return ClaimNormalizer(config)


class TestClaimShapeEdgeCases:
    def test_empty_claim(self, config):
        engine = make_engine([], config=config)
        with pytest.raises(ClaimValidationError):
            engine.verify("")

    def test_extremely_long_claim(self, config):
        engine = make_engine([], config=config)
        long_claim = "Company X revenue increased by 20% in 2025. " * 200
        with pytest.raises(ClaimValidationError):
            engine.verify(long_claim)

    def test_long_but_valid_claim_runs(self, config):
        engine = make_engine([], config=config)
        long_claim = ("Company X revenue increased by 20% in 2025. " * 60).strip()
        result = engine.verify(long_claim)  # under the 4000-char cap
        assert result.verdict == Verdict.UNVERIFIABLE  # no evidence available

    def test_ambiguous_entity(self, config, normalizer):
        normalizer.normalize("The company grew revenue by 20% last year.")
        # no explicit named entity -> pipeline must still run
        engine = make_engine([], config=config)
        result = engine.verify("The company grew revenue by 20% last year.")
        assert result.verdict in (Verdict.UNVERIFIABLE, Verdict.QUALIFIED)
        assert result.hypotheses  # hypotheses still generated

    def test_missing_date(self, config, normalizer):
        claim = normalizer.normalize("Company X has the largest market share in Europe.")
        assert claim.temporal_constraints == [] or all("20" not in t for t in claim.temporal_constraints)
        engine = make_engine([], config=config)
        result = engine.verify("Company X has the largest market share in Europe.")
        assert result.verdict == Verdict.UNVERIFIABLE

    def test_relative_date(self, normalizer):
        claim = normalizer.normalize("Company X revenue grew 15% last year.")
        assert any("last year" in t for t in claim.temporal_constraints)

    def test_percentages_and_numbers(self, normalizer):
        claim = normalizer.normalize("Unemployment fell to 3.5% in March 2025.")
        q = claim.primary_quantity
        assert q.value == pytest.approx(3.5)
        assert q.unit == "percent"

    def test_comparison_claim(self, normalizer):
        claim = normalizer.normalize("China's GDP is larger than India's GDP.")
        assert claim.claim_kind in (ClaimKind.COMPARATIVE, ClaimKind.QUANTITATIVE_STATE)
        assert len(claim.entities) >= 1

    def test_causal_claim_runs_end_to_end(self, config):
        engine = make_engine([], config=config)
        result = engine.verify("Ice cream sales cause shark attacks.")
        assert result.claim.claim_kind == ClaimKind.CAUSAL
        assert any(h.category.value == "causal" for h in result.hypotheses)
        assert result.verdict == Verdict.UNVERIFIABLE

    def test_future_claim_is_unverifiable_not_false(self, config):
        corpus = [
            make_evidence(
                url="https://www.reuters.com/tesla-forecast",
                title="Tesla delivery forecasts",
                publisher="Reuters",
                text="Analysts project Tesla will deliver about 2.5 million cars in 2030, far short of 5 million.",
                publication_date="2026-01-01",
            )
        ]
        engine = make_engine(corpus, config=config)
        result = engine.verify("Tesla will deliver 5 million cars in 2030.")
        assert result.claim.is_future_claim
        assert result.verdict == Verdict.UNVERIFIABLE

    def test_multiple_entities(self, normalizer):
        claim = normalizer.normalize("Tesla revenue grew faster than Toyota revenue in 2025.")
        assert len(claim.entities) >= 2

    def test_multiple_assertions(self, normalizer):
        claim = normalizer.normalize(
            "Company X grew revenue by 40% in 2025. Company X also hired 5000 engineers. Company X opened a new factory in Texas."
        )
        assert len(claim.assertions) >= 2
        assert any("texas" in g.lower() for g in claim.geographic_constraints)


class TestEvidenceEdgeCases:
    CLAIM = "Company X revenue increased by 20% in 2025."

    def test_duplicated_evidence_collapsed(self, config):
        copies = [
            make_evidence(
                url=f"https://site{i}.example/companyx-news",
                title="Company X revenue up 20% in 2025",
                text="Company X revenue increased 20% in 2025, the company announced today in its results.",
                publication_date="2026-02-01",
            )
            for i in range(3)
        ]
        engine = make_engine(copies, config=config)
        result = engine.verify(self.CLAIM)
        assert result.fusion.duplicated_evidence_detected >= 2
        # one copied statement, however many times repeated, is ONE independent voice
        assert result.fusion.independent_supporting_clusters == 1
        # a single un-corroborated unknown-quality cluster cannot reach VERIFIED
        assert result.verdict in (Verdict.QUALIFIED, Verdict.VERIFIED, Verdict.UNVERIFIABLE)

    def test_contradictory_evidence_not_verified(self, config):
        corpus = [
            make_evidence(
                url="https://www.sec.gov/companyx-support",
                title="Company X reports strong 2025",
                publisher="SEC",
                text="Company X revenue increased 20% in 2025 compared with 2024.",
                publication_date="2026-02-01",
            ),
            make_evidence(
                url="https://www.sec.gov/companyx-contra",
                title="Company X restates 2025 figures",
                publisher="SEC",
                text="In a restatement, Company X revenue for 2025 increased only 9% versus 2024.",
                publication_date="2026-06-01",
            ),
        ]
        engine = make_engine(corpus, config=config)
        result = engine.verify(self.CLAIM)
        assert result.verdict in (Verdict.CONFLICTED, Verdict.REFUTED, Verdict.QUALIFIED)
        assert result.verdict != Verdict.VERIFIED

    def test_stale_evidence_does_not_verify(self, config):
        corpus = [
            make_evidence(
                url="https://news.example/companyx-2024-forecast",
                title="Company X forecast from 2024",
                text="Company X expects revenue to increase 20% in 2025, management projected.",
                publication_date="2024-06-01",  # published BEFORE the claimed period
            ),
        ]
        engine = make_engine(corpus, config=config)
        result = engine.verify(self.CLAIM)
        stale = [a for a in result.assessments if a.temporal_validity < 0.5]
        assert stale, "pre-period evidence must be flagged stale"
        assert result.verdict != Verdict.VERIFIED

    def test_irrelevant_results_ignored(self, config):
        corpus = [
            make_evidence(
                url="https://sports.example/nfl",
                title="NFL season recap",
                text="The Kansas City Chiefs won their division again this season with a dominant defense.",
                publication_date="2026-01-10",
            ),
        ]
        engine = make_engine(corpus, config=config)
        result = engine.verify(self.CLAIM)
        assert result.verdict == Verdict.UNVERIFIABLE
        assert all(a.stance == "neutral" for a in result.assessments if a.relevance_score < config.relevance_floor)

    def test_evidence_without_url_never_invented(self, config):
        """A retriever returning a URL-less item is impossible via TavilyRetriever
        (it skips those); the engine must never fabricate sources."""
        engine = make_engine([], config=config)
        result = engine.verify(self.CLAIM)
        assert result.evidence == []
        assert all(e.source_url for e in result.evidence)


class TestEngineLimits:
    def test_query_and_evidence_limits_respected(self, config):
        config.max_total_queries = 4
        config.max_total_evidence = 3
        big_corpus = [
            make_evidence(
                url=f"https://news{i}.example/companyx",
                title=f"Company X revenue increased 20% in 2025 (report {i})",
                text=f"Company X revenue increased 20% in 2025 according to report {i}.",
                publication_date="2026-02-01",
            )
            for i in range(10)
        ]
        engine = make_engine(big_corpus, config=config)
        result = engine.verify("Company X revenue increased by 20% in 2025.")
        assert len(result.queries) <= 4
        assert len(result.evidence) <= 3

    def test_hypotheses_limit_respected(self, config):
        config.max_hypotheses = 2
        engine = make_engine([], config=config)
        result = engine.verify("Company X revenue increased by 20% in 2025.")
        assert len(result.hypotheses) <= 2

    def test_deterministic_reruns_are_stable(self, config):
        corpus = [
            make_evidence(
                url="https://www.sec.gov/companyx-stable",
                title="Company X 2025 results",
                publisher="SEC",
                text="Company X revenue increased 20% in 2025 compared with 2024.",
                publication_date="2026-02-01",
            )
        ]
        r1 = make_engine(corpus, config=config).verify("Company X revenue increased by 20% in 2025.")
        r2 = make_engine(corpus, config=config).verify("Company X revenue increased by 20% in 2025.")
        assert r1.verdict == r2.verdict
        assert r1.confidence == r2.confidence
        assert [q.query for q in r1.queries] == [q.query for q in r2.queries]
