"""End-to-end FalsifyEngine pipeline tests (fully offline, mocked providers).

Covers the six mandated demonstration cases plus the spec's demo scenario
(three copied blogs vs one authoritative filing).
"""

from __future__ import annotations

import json

import pytest

from app.falsify.exceptions import ClaimValidationError
from app.falsify.llm.provider import MockLLM
from app.falsify.models import Verdict
from app.falsify.retrieval.mock import InMemoryRetriever
from tests.conftest import make_engine, make_evidence

# ---------------------------------------------------------------------------
# Case 1: Clearly true -> VERIFIED
# ---------------------------------------------------------------------------

EARTH_ORBITS_SUN = [
    make_evidence(
        url="https://science.nasa.gov/solar-system/our-solar-system",
        title="Our Solar System - NASA Science",
        publisher="NASA",
        text=(
            "The Earth orbits the Sun at an average distance of 93 million miles. "
            "Our solar system consists of the Sun and everything that orbits it, "
            "including Earth and the other planets."
        ),
        publication_date="2025-05-01",
    ),
    make_evidence(
        url="https://www.britannica.com/science/heliocentrism",
        title="Heliocentrism | Definition, Model & Facts | Britannica",
        publisher="Encyclopedia Britannica",
        text=(
            "Heliocentrism is the view that the Sun lies at the center of the solar system "
            "and that the Earth and other planets orbit the Sun."
        ),
        publication_date="2025-01-01",
    ),
]


class TestCase1ClearlyTrue:
    def test_verified(self, config):
        engine = make_engine(EARTH_ORBITS_SUN, config=config)
        result = engine.verify("The Earth orbits the Sun.")
        assert result.verdict == Verdict.VERIFIED
        assert result.fusion.supporting_evidence >= 1
        assert result.fusion.contradicting_evidence == 0
        assert result.confidence >= 0.5


# ---------------------------------------------------------------------------
# Case 2: Clearly false -> REFUTED
# ---------------------------------------------------------------------------

GEOCENTRIC_REFUTATION = [
    make_evidence(
        url="https://science.nasa.gov/heliocentric-model",
        title="The Heliocentric Model - NASA Science",
        publisher="NASA",
        text=(
            "The geocentric model, which held that the Sun orbits the Earth, is false. "
            "It was disproven by the observations of Copernicus, Galileo and Kepler: "
            "the Earth orbits the Sun, not the other way around."
        ),
        publication_date="2025-03-01",
    ),
]


class TestCase2ClearlyFalse:
    def test_refuted(self, config):
        engine = make_engine(GEOCENTRIC_REFUTATION, config=config)
        result = engine.verify("The Earth is the center of the solar system and the Sun orbits Earth.")
        assert result.verdict == Verdict.REFUTED
        assert result.contradictions
        assert result.confidence >= 0.5


# ---------------------------------------------------------------------------
# Case 3: Numerical discrepancy -> REFUTED
# ---------------------------------------------------------------------------

OFFICIAL_21PCT = [
    make_evidence(
        url="https://www.sec.gov/Archives/edgar/data/0000000000/companyx-2025-10k.htm",
        title="Company X Inc. Form 10-K for fiscal year 2025",
        publisher="Company X Inc. (SEC filing)",
        text=(
            "Company X Inc. today announced its audited full year 2025 results. "
            "Total revenue increased 21% in 2025 compared with 2024, reaching $12.1 billion. "
            "The figures in this annual report have been audited by the company's independent auditor."
        ),
        publication_date="2026-02-15",
    ),
]


class TestCase3NumericalDiscrepancy:
    def test_refuted_exactly_30_vs_official_21(self, config):
        engine = make_engine(OFFICIAL_21PCT, config=config)
        result = engine.verify("Company X revenue increased by exactly 30% in 2025.")
        assert result.verdict == Verdict.REFUTED
        numerical = [c for c in result.contradictions if c.contradiction_type.value == "numerical"]
        assert numerical and numerical[0].severity.value in ("high", "critical")
        assert result.confidence >= 0.6

    def test_trace_shows_the_contradiction(self, config):
        engine = make_engine(OFFICIAL_21PCT, config=config)
        result = engine.verify("Company X revenue increased by exactly 30% in 2025.")
        trace = result.reasoning_trace.model_dump(mode="json")
        assert trace["verdict"] == "REFUTED"
        assert any(c["type"] == "numerical" and c["severity"] in ("high", "critical") for c in trace["contradictions"])
        assert trace["evidence_summary"]["contradicting"] >= 1


# ---------------------------------------------------------------------------
# Case 4: Conflicting evidence -> CONFLICTED
# ---------------------------------------------------------------------------

CONFLICTING_FIGURES = [
    make_evidence(
        url="https://www.reuters.com/business/companyx-revenue-2025-a",
        title="Company X posts 20% revenue growth in 2025",
        publisher="Reuters",
        text=(
            "Company X said its total revenue increased 20% in 2025 compared with 2024, "
            "according to its published financial statements."
        ),
        publication_date="2026-02-01",
    ),
    make_evidence(
        url="https://www.ft.com/content/companyx-revenue-2025-b",
        title="Company X growth disappoints: revenue up just 12% in 2025",
        publisher="Financial Times",
        text=(
            "Company X revenue increased only 12% in 2025 versus 2024, according to a "
            "filing reviewed by the Financial Times, well below earlier company statements."
        ),
        publication_date="2026-02-05",
    ),
]


class TestCase4ConflictingEvidence:
    def test_conflicted(self, config):
        engine = make_engine(CONFLICTING_FIGURES, config=config)
        result = engine.verify("Company X revenue increased by 20% in 2025.")
        assert result.verdict == Verdict.CONFLICTED
        assert result.fusion.supporting_evidence >= 1
        assert result.fusion.contradicting_evidence >= 1


# ---------------------------------------------------------------------------
# Case 5: Insufficient evidence -> UNVERIFIABLE
# ---------------------------------------------------------------------------

IRRELEVANT_CORPUS = [
    make_evidence(
        url="https://cooking.example/pancakes",
        title="The best pancake recipe",
        publisher="Cooking Blog",
        text="Fluffy pancakes with maple syrup and blueberries. A weekend breakfast classic.",
        publication_date="2025-11-01",
    ),
]


class TestCase5InsufficientEvidence:
    def test_no_evidence_at_all(self, config):
        engine = make_engine([], config=config)
        result = engine.verify("The population of Springfield reached 2.4 million in 2025.")
        assert result.verdict == Verdict.UNVERIFIABLE
        assert result.evidence == []

    def test_only_irrelevant_results(self, config):
        engine = make_engine(IRRELEVANT_CORPUS, config=config)
        result = engine.verify("The population of Springfield reached 2.4 million in 2025.")
        assert result.verdict == Verdict.UNVERIFIABLE
        assert result.fusion.support_strength == 0.0
        assert result.fusion.contradict_strength == 0.0


# ---------------------------------------------------------------------------
# Case 6: Qualification -> QUALIFIED
# ---------------------------------------------------------------------------

QUALIFIED_CORPUS = [
    make_evidence(
        url="https://www.sec.gov/Archives/edgar/data/0000000000/companyx-2025-results.htm",
        title="Company X Inc. reports full year 2025 results",
        publisher="Company X Inc. (SEC filing)",
        text=(
            "Company X Inc. reported that total revenue increased 20% in 2025 compared with 2024, "
            "including the contribution from the Meridian acquisition completed in March 2025."
        ),
        publication_date="2026-02-10",
    ),
    make_evidence(
        url="https://www.reuters.com/business/companyx-organic-growth",
        title="Company X organic growth lags headline number",
        publisher="Reuters",
        text=(
            "On a non-GAAP organic basis, excluding the Meridian acquisition, Company X revenue "
            "increased 17% in 2025, analysts noted after the company's results."
        ),
        publication_date="2026-02-12",
    ),
]


class TestCase6Qualification:
    def test_qualified(self, config):
        engine = make_engine(QUALIFIED_CORPUS, config=config)
        result = engine.verify("Company X revenue increased by 20% in 2025.")
        assert result.verdict == Verdict.QUALIFIED
        assert result.fusion.supporting_evidence >= 1
        assert result.contradictions  # the qualification is documented


# ---------------------------------------------------------------------------
# Spec section 26 demo: blogs copying a wrong number vs one primary filing
# ---------------------------------------------------------------------------

DEMO_CORPUS = [
    make_evidence(
        url="https://www.sec.gov/Archives/edgar/data/0000000000/companyx-10k-2025.htm",
        title="Company X Inc. Form 10-K, fiscal year 2025",
        publisher="Company X Inc. (SEC filing)",
        text=(
            "Company X Inc. full year 2025: total revenue increased 27% compared with fiscal 2024. "
            "Audited consolidated financial statements are included in this annual report."
        ),
        publication_date="2026-02-20",
    ),
    make_evidence(
        url="https://www.reuters.com/business/companyx-annual-results-2025",
        title="Company X revenue grows 27% in 2025, missing some forecasts",
        publisher="Reuters",
        text=(
            "Company X reported that revenue increased 27% in 2025 versus 2024, according to "
            "the company's annual report filed with regulators."
        ),
        publication_date="2026-02-21",
    ),
] + [
    make_evidence(
        url=f"https://growthblog{i}.blogspot.com/companyx-40-percent",
        title="Company X had an amazing 2025 with 40% revenue growth!",
        publisher="Growth Blog",
        text="Company X grew revenue by 40% in 2025, an incredible performance that beat everyone's expectations.",
        publication_date="2026-01-05",
    )
    for i in range(3)
]


class TestDemoScenario:
    def test_three_copied_blogs_lose_to_primary_sources(self, config):
        engine = make_engine(DEMO_CORPUS, config=config)
        result = engine.verify("Company X grew revenue by 40% in 2025.")
        assert result.verdict == Verdict.REFUTED
        # the 3 blog copies collapsed into one independent voice
        assert result.fusion.duplicated_evidence_detected >= 2
        assert result.fusion.independent_supporting_clusters <= 2
        assert result.fusion.max_contradict_quality > result.fusion.max_support_quality
        assert result.confidence >= 0.5

    def test_demo_trace_is_renderable(self, config):
        engine = make_engine(DEMO_CORPUS, config=config)
        result = engine.verify("Company X grew revenue by 40% in 2025.")
        trace = json.loads(result.reasoning_trace.model_dump_json())
        for key in ("claim", "hypotheses", "queries", "evidence_summary", "contradictions", "verdict", "confidence"):
            assert key in trace
        assert all("hypothesis" in h and "tested" in h for h in trace["hypotheses"])
        assert all("query" in q and "purpose" in q for q in trace["queries"])
        assert "supporting" in trace["evidence_summary"] and "contradicting" in trace["evidence_summary"]


# ---------------------------------------------------------------------------
# Interface & serialization contract (for the API team)
# ---------------------------------------------------------------------------


class TestPublicContract:
    def test_result_is_json_serializable(self, config):
        engine = make_engine(OFFICIAL_21PCT, config=config)
        result = engine.verify("Company X revenue increased by exactly 30% in 2025.")
        dumped = result.model_dump(mode="json")
        serialized = json.dumps(dumped)  # must not raise
        assert json.loads(serialized)["verdict"] == "REFUTED"
        assert isinstance(result.summary(), dict)

    def test_pipeline_stages_all_recorded(self, config):
        engine = make_engine(DEMO_CORPUS, config=config)
        result = engine.verify("Company X grew revenue by 40% in 2025.")
        assert result.claim.original_text == "Company X grew revenue by 40% in 2025."
        assert result.hypotheses, "hypotheses must be generated"
        assert result.queries, "adversarial queries must be generated"
        assert result.evidence, "evidence must be retrieved"
        assert result.assessments
        assert result.reasoning_trace.stage_timings_ms

    def test_adversarial_queries_present_not_claim_echo(self, config):
        engine = make_engine(DEMO_CORPUS, config=config)
        result = engine.verify("Company X grew revenue by 40% in 2025.")
        lowered = {q.query.lower() for q in result.queries}
        assert "company x grew revenue by 40% in 2025" not in lowered
        joined = " ".join(lowered)
        assert any(w in joined for w in ("annual report", "actual", "decline", "discrepancy", "10-k"))

    def test_hypothesis_outcomes_in_trace(self, config):
        engine = make_engine(DEMO_CORPUS, config=config)
        result = engine.verify("Company X grew revenue by 40% in 2025.")
        outcomes = {h.outcome for h in result.reasoning_trace.hypotheses}
        assert outcomes <= {"not_tested", "no_evidence", "survived", "challenged", "falsified"}
        assert "falsified" in outcomes or "challenged" in outcomes


# ---------------------------------------------------------------------------
# LLM integration through the pipeline (mocked)
# ---------------------------------------------------------------------------


class TestLLMInTheLoop:
    def test_llm_synthesis_used_when_available(self, config):
        llm = MockLLM(
            {
                "final reasoning summary": json.dumps(
                    {"reasoning": "The SEC filing directly contradicts the claimed 40% growth with an audited 27% figure."}
                )
            }
        )
        config.use_llm_for_synthesis = True
        engine = make_engine(DEMO_CORPUS, llm=llm, config=config)
        result = engine.verify("Company X grew revenue by 40% in 2025.")
        assert "audited 27% figure" in result.reasoning_trace.reasoning
        assert result.llm_used is True

    def test_llm_garbage_everywhere_still_completes(self, config):
        llm = MockLLM(lambda prompt: "### not json ###")
        config.use_llm_for_normalization = True
        config.use_llm_for_hypotheses = True
        config.use_llm_for_evidence_assessment = True
        config.use_llm_for_synthesis = True
        engine = make_engine(OFFICIAL_21PCT, llm=llm, config=config)
        result = engine.verify("Company X revenue increased by exactly 30% in 2025.")
        assert result.verdict == Verdict.REFUTED  # deterministic backbone still works
        assert result.errors == []  # LLM fallbacks are logged, not errors

    def test_llm_unavailable_engine_runs_deterministic(self, config):
        llm = MockLLM({})  # raises LLMUnavailableError for everything
        config.use_llm_for_normalization = True
        config.use_llm_for_hypotheses = True
        engine = make_engine(EARTH_ORBITS_SUN, llm=llm, config=config)
        result = engine.verify("The Earth orbits the Sun.")
        assert result.verdict == Verdict.VERIFIED
        assert result.claim.normalization_source == "deterministic"


# ---------------------------------------------------------------------------
# Structured logging (no secrets)
# ---------------------------------------------------------------------------


class TestStructuredLogging:
    def test_stage_events_emitted(self, config):
        import logging

        from app.falsify.logging_utils import logger as falsify_logger

        records: list[str] = []

        class Capture(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        handler = Capture()
        falsify_logger.addHandler(handler)
        try:
            engine = make_engine(OFFICIAL_21PCT, config=config)
            engine.verify("Company X revenue increased by exactly 30% in 2025.")
        finally:
            falsify_logger.removeHandler(handler)

        joined = "\n".join(records)
        for event in (
            "claim_normalization_started",
            "claim_normalized",
            "hypotheses_generated",
            "queries_generated",
            "evidence_retrieved",
            "evidence_assessed",
            "contradictions_detected",
            "verdict_generated",
            "verification_complete",
        ):
            assert f"event={event}" in joined, f"missing log event {event}"

    def test_api_keys_never_logged(self, config):
        import logging

        from app.falsify.logging_utils import logger as falsify_logger

        records: list[str] = []

        class Capture(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        handler = Capture()
        falsify_logger.addHandler(handler)
        try:
            config.retrieval.api_key = "tvly-SUPER-SECRET-123"
            config.llm.api_key = "sk-SUPER-SECRET-456"
            engine = make_engine([], config=config)
            with pytest.raises(ClaimValidationError):
                engine.verify("")
            engine.verify("Some claim about revenue in 2025.")
        finally:
            falsify_logger.removeHandler(handler)
        joined = "\n".join(records)
        assert "SUPER-SECRET" not in joined


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------


class TestFailureHandling:
    def test_retriever_down_returns_structured_failure(self, config):
        from app.falsify.exceptions import RetrieverUnavailableError

        dead = InMemoryRetriever([], fail_with=RetrieverUnavailableError("connection refused"))
        engine = make_engine([], retriever=dead, config=config)
        result = engine.verify("Company X revenue increased by 20% in 2025.")
        assert result.verdict == Verdict.UNVERIFIABLE
        assert result.errors
        assert all(e.stage == "retrieval" for e in result.errors)
        assert "connection refused" in result.errors[0].message
        assert result.evidence == []  # never fabricated

    def test_empty_claim_raises_validation_error(self, config):
        engine = make_engine([], config=config)
        with pytest.raises(ClaimValidationError):
            engine.verify("")
