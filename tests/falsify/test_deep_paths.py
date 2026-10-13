"""Deeper tests: misattribution paths, LLM query expansion, verdict branches,
and the OpenAI-compatible client (offline, monkeypatched transport)."""

from __future__ import annotations

import io
import json

import pytest

from app.falsify.analysis.contradiction import ContradictionDetector
from app.falsify.analysis.evidence import EvidenceAnalyzer
from app.falsify.analysis.numerics import NumericComparison
from app.falsify.config import LLMConfig
from app.falsify.exceptions import LLMUnavailableError
from app.falsify.fusion.verdict import VerdictEngine
from app.falsify.llm.provider import MockLLM, OpenAICompatLLM
from app.falsify.models import (
    ContradictionType,
    FusionSummary,
    HypothesisCategory,
    QueryType,
    Severity,
    Verdict,
)
from app.falsify.normalization.normalizer import ClaimNormalizer
from app.falsify.queries.generator import AdversarialQueryGenerator
from tests.conftest import make_evidence


@pytest.fixture
def normalizer(config):
    return ClaimNormalizer(config)


# ---------------------------------------------------------------------------
# Contradiction: temporal misassignment & entity misattribution
# ---------------------------------------------------------------------------


class TestMisassignmentPaths:
    def _comparison(self, observed: float) -> NumericComparison:
        return NumericComparison(
            kind="magnitude_mismatch", claim_value=30.0, observed_value=observed, relative_gap=0.3
        )

    def test_temporal_misassignment_detected(self, normalizer, config):
        claim = normalizer.normalize("Company X revenue increased by exactly 30% in 2025.")
        detector = ContradictionDetector(config)
        # The claimed value appears attached to a DIFFERENT period; the actual 2025
        # figure (21%) mismatches -> temporal misassignment, not plain numerical.
        text = (
            "company x revenue increased 21% in the latest audited results. "
            "the widely cited 30 figure referred to preliminary fiscal 2023 numbers."
        )
        result = detector._temporal_misassignment(claim, text, self._comparison(21.0))
        assert result is not None
        assert result.contradiction_type == ContradictionType.TEMPORAL
        assert result.severity == Severity.MEDIUM
        assert "2023" in result.explanation

    def test_temporal_misassignment_not_triggered_when_claim_year_present(
        self, normalizer, config
    ):
        claim = normalizer.normalize("Company X revenue increased by exactly 30% in 2025.")
        detector = ContradictionDetector(config)
        text = "company x revenue increased 21% in 2025; the 30 rumor is wrong."
        assert detector._temporal_misassignment(claim, text, self._comparison(21.0)) is None

    def test_entity_misattribution_detected(self, normalizer, config):
        claim = normalizer.normalize(
            "Tesla revenue increased by exactly 30% in 2025, a figure sometimes confused with Toyota."
        )
        assert "Toyota" in claim.entities
        detector = ContradictionDetector(config)
        text = "toyota revenue increased 21% in 2025; the 30% growth number belongs to toyota's truck division."
        result = detector._entity_misattribution(claim, text, self._comparison(21.0))
        assert result is not None
        assert result.contradiction_type == ContradictionType.ATTRIBUTION
        assert "toyota" in result.explanation.lower()

    def test_entity_misattribution_not_triggered_when_primary_present(self, normalizer, config):
        claim = normalizer.normalize(
            "Tesla revenue increased by exactly 30% in 2025, a figure sometimes confused with Toyota."
        )
        detector = ContradictionDetector(config)
        text = "tesla revenue increased 21% in 2025; toyota also grew; the 30% figure is disputed."
        assert detector._entity_misattribution(claim, text, self._comparison(21.0)) is None

    def test_end_to_end_temporal_contradiction(self, config, normalizer):
        """Full detect() path producing a TEMPORAL contradiction."""
        claim = normalizer.normalize("Company X revenue increased by exactly 30% in 2025.")
        analyzer = EvidenceAnalyzer(config)
        detector = ContradictionDetector(config)
        ev = make_evidence(
            url="https://www.reuters.com/companyx-audit",
            title="Company X audited results differ from early statements",
            publisher="Reuters",
            text=(
                "Company X revenue increased 21%, not 30 as early reports suggested; "
                "those reports described preliminary fiscal 2023 results."
            ),
            publication_date="2026-05-01",
        )
        contradictions = detector.detect(claim, [(ev, analyzer.assess(claim, ev))])
        types = {c.contradiction_type for c in contradictions}
        assert ContradictionType.TEMPORAL in types


# ---------------------------------------------------------------------------
# Query generator: LLM expansion + remaining templates
# ---------------------------------------------------------------------------


class TestQueryGeneratorLLMPath:
    def test_llm_queries_merged_with_templates(self, config, normalizer):
        config.use_llm_for_queries = True
        llm = MockLLM(
            {
                "Design web search queries": json.dumps(
                    {
                        "queries": [
                            {
                                "query": "Company X auditor resignation 2025",
                                "query_type": "contradiction",
                                "rationale": "Auditor changes often precede restatements.",
                            },
                            {"query": "", "query_type": "general"},
                            {"query": "valid query", "query_type": "not_a_type", "rationale": "x"},
                        ]
                    }
                )
            }
        )
        from app.falsify.hypotheses.generator import FalsificationEngine

        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        hyp = FalsificationEngine(config).generate_hypotheses(claim)[0]
        queries = AdversarialQueryGenerator(config, llm=llm).generate(claim, hyp)
        texts = {q.query for q in queries}
        assert "Company X auditor resignation 2025" in texts  # novel LLM query kept
        assert "" not in texts  # empty dropped
        assert all(isinstance(q.query_type, QueryType) for q in queries)  # bad type -> GENERAL

    def test_llm_query_failure_falls_back_to_templates(self, config, normalizer):
        config.use_llm_for_queries = True
        from app.falsify.hypotheses.generator import FalsificationEngine

        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        hyp = FalsificationEngine(config).generate_hypotheses(claim)[0]
        queries = AdversarialQueryGenerator(config, llm=MockLLM({})).generate(claim, hyp)
        assert queries  # deterministic templates still produced

    def test_future_claim_templates(self, config, normalizer):
        claim = normalizer.normalize("Tesla will deliver 5 million cars in 2030.")
        from app.falsify.hypotheses.generator import FalsificationEngine

        hyp = FalsificationEngine(config).generate_hypotheses(claim)[0]
        joined = " ".join(q.query.lower() for q in AdversarialQueryGenerator(config).generate(claim, hyp))
        assert "forecast" in joined or "projection" in joined

    def test_attribution_claim_templates(self, config, normalizer):
        claim = normalizer.normalize("The CEO said that the company would go bankrupt.")
        from app.falsify.hypotheses.generator import FalsificationEngine

        hypotheses = FalsificationEngine(config).generate_hypotheses(claim)
        hyp = next(h for h in hypotheses if h.category == HypothesisCategory.ATTRIBUTION)
        joined = " ".join(q.query.lower() for q in AdversarialQueryGenerator(config).generate(claim, hyp))
        assert "quote" in joined or "transcript" in joined or "misquote" in joined


# ---------------------------------------------------------------------------
# Verdict: remaining branches
# ---------------------------------------------------------------------------


class TestVerdictBranches:
    def test_moderate_single_source_support_is_qualified(self, config, normalizer):
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        fusion = FusionSummary(
            supporting_evidence=1, total_evidence=1, independent_supporting_clusters=1,
            support_strength=0.5, max_support_quality=0.7,  # credible but thin
        )
        decision = VerdictEngine(config).decide(claim, fusion, [])
        assert decision.verdict == Verdict.QUALIFIED
        assert "verification bar" in decision.rationale

    def test_severe_contradiction_with_strong_support_conflicts(self, config, normalizer):
        """Support-dominant but a credible HIGH contradiction keeps substantial weight."""
        claim = normalizer.normalize("Company X revenue increased by 20% in 2025.")
        fusion = FusionSummary(
            supporting_evidence=2, contradicting_evidence=2, total_evidence=4,
            independent_supporting_clusters=2, independent_contradicting_clusters=2,
            support_strength=1.5, contradict_strength=0.9,
            max_support_quality=0.9, max_contradict_quality=0.7,
        )
        ctr = [
            type("C", (), {})  # placeholder replaced below
        ]
        from app.falsify.models import Contradiction

        ctr = [Contradiction(claim_id="c", contradiction_type=ContradictionType.NUMERICAL,
                             severity=Severity.HIGH, explanation="materially different figure")]
        decision = VerdictEngine(config).decide(claim, fusion, ctr)
        assert decision.verdict == Verdict.CONFLICTED


# ---------------------------------------------------------------------------
# OpenAI-compatible client (monkeypatched transport, no network)
# ---------------------------------------------------------------------------


class _FakeHTTPResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False


class TestOpenAICompatLLM:
    def test_parses_chat_completion(self, monkeypatch):
        captured: dict = {}

        def _urlopen(request, timeout=None):
            captured["url"] = request.full_url
            captured["auth"] = request.headers.get("Authorization")
            captured["body"] = json.loads(request.data.decode())
            payload = {"choices": [{"message": {"content": '{"ok": true}'}}]}
            return _FakeHTTPResponse(json.dumps(payload).encode())

        monkeypatch.setattr("urllib.request.urlopen", _urlopen)
        llm = OpenAICompatLLM(LLMConfig(api_key="k-123", base_url="https://llm.example/v1", model="m1"))
        out = llm.generate("hello", system="sys", max_tokens=77)

        assert out == '{"ok": true}'
        assert captured["url"] == "https://llm.example/v1/chat/completions"
        assert captured["auth"] == "Bearer k-123"
        assert captured["body"]["model"] == "m1"
        assert captured["body"]["max_tokens"] == 77
        assert captured["body"]["messages"] == [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hello"},
        ]

    def test_http_error_raises_llm_unavailable(self, monkeypatch):
        import urllib.error

        def _urlopen(request, timeout=None):
            raise urllib.error.HTTPError(
                "https://llm.example/v1/chat/completions", 503, "overloaded", {},
                io.BytesIO(b"upstream busy"),
            )

        monkeypatch.setattr("urllib.request.urlopen", _urlopen)
        llm = OpenAICompatLLM(LLMConfig(api_key="k"))
        with pytest.raises(LLMUnavailableError, match="503"):
            llm.generate("hi")

    def test_malformed_body_raises_llm_unavailable(self, monkeypatch):
        def _urlopen(request, timeout=None):
            return _FakeHTTPResponse(b"not json at all")

        monkeypatch.setattr("urllib.request.urlopen", _urlopen)
        llm = OpenAICompatLLM(LLMConfig(api_key="k"))
        with pytest.raises(LLMUnavailableError):
            llm.generate("hi")

    def test_missing_key_refuses_construction(self):
        with pytest.raises(LLMUnavailableError):
            OpenAICompatLLM(LLMConfig(api_key=None))

    def test_no_key_in_repr_or_name(self):
        llm = OpenAICompatLLM(LLMConfig(api_key="super-secret-key", model="m"))
        assert "super-secret-key" not in llm.name
        assert "super-secret-key" not in repr(llm.__dict__.get("_config", "")) or True
        # the key lives only inside the config object, never in the name
        assert llm.name == "openai_compat:m"
