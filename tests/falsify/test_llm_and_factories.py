"""Tests for LLM retry behaviour and provider/config factories (offline)."""

from __future__ import annotations

import json

import pytest

from app.falsify.config import LLMConfig, RetrievalConfig
from app.falsify.exceptions import (
    ClaimValidationError,
    LLMUnavailableError,
    MalformedLLMResponseError,
)
from app.falsify.llm import (
    MockLLM,
    NullLLM,
    OpenAICompatLLM,
    build_llm_from_config,
    generate_json,
)
from app.falsify.llm.provider import build_llm_from_config as _dup_check  # noqa: F401
from app.falsify.normalization.normalizer import ClaimNormalizer
from app.falsify.retrieval import InMemoryRetriever, TavilyRetriever, build_retriever_from_config


class FlakyThenGoodLLM:
    """Returns garbage for the first ``fail_times`` calls, then valid JSON."""

    def __init__(self, payload: dict, fail_times: int = 1) -> None:
        self.payload = payload
        self.fail_times = fail_times
        self.calls = 0

    @property
    def name(self) -> str:
        return "flaky"

    def generate(self, prompt: str, *, system: str | None = None, max_tokens: int | None = None) -> str:
        self.calls += 1
        if self.calls <= self.fail_times:
            return "sorry, here is some prose without any JSON ###"
        return json.dumps(self.payload)


class TestGenerateJsonRetry:
    def test_retries_on_malformed_then_succeeds(self):
        llm = FlakyThenGoodLLM({"ok": True}, fail_times=2)
        data = generate_json(llm, "prompt", max_retries=2)
        assert data == {"ok": True}
        assert llm.calls == 3  # initial + 2 retries

    def test_gives_up_after_max_retries(self):
        llm = FlakyThenGoodLLM({"ok": True}, fail_times=10)
        with pytest.raises(MalformedLLMResponseError):
            generate_json(llm, "prompt", max_retries=1)
        assert llm.calls == 2

    def test_unavailable_propagates_without_retry(self):
        llm = MockLLM({})  # raises LLMUnavailableError for everything
        with pytest.raises(LLMUnavailableError):
            generate_json(llm, "prompt", max_retries=3)
        assert len(llm.calls) == 1  # no pointless retries when the provider is down


class TestRetryIntegratedInPipeline:
    def test_normalizer_retries_malformed_llm(self, config):
        config.use_llm_for_normalization = True
        llm = FlakyThenGoodLLM(
            {
                "entities": ["Tesla Inc"],
                "claim_kind": "quantitative_change",
                "normalized_text": "Tesla Inc revenue rose 20% in 2025.",
            },
            fail_times=1,
        )
        config.llm_max_retries = 2
        normalizer = ClaimNormalizer(config, llm=llm)
        claim = normalizer.normalize("Tesla's revenue increased by 20% in 2025.")
        assert claim.normalization_source == "hybrid"
        assert llm.calls == 2

    def test_normalizer_falls_back_after_exhausted_retries(self, config):
        config.use_llm_for_normalization = True
        config.llm_max_retries = 1
        llm = FlakyThenGoodLLM({"entities": ["X"]}, fail_times=99)
        normalizer = ClaimNormalizer(config, llm=llm)
        claim = normalizer.normalize("Tesla's revenue increased by 20% in 2025.")
        assert claim.normalization_source == "deterministic"
        assert llm.calls == 2  # initial + 1 retry, then graceful fallback


class TestInputValidation:
    def test_none_claim_raises(self, config):
        with pytest.raises(ClaimValidationError, match="must be a string"):
            ClaimNormalizer(config).normalize(None)  # type: ignore[arg-type]

    def test_int_claim_raises(self, config):
        with pytest.raises(ClaimValidationError, match="must be a string"):
            ClaimNormalizer(config).normalize(42)  # type: ignore[arg-type]

    def test_engine_propagates_validation_error(self, config):
        from tests.conftest import make_engine

        engine = make_engine([], config=config)
        with pytest.raises(ClaimValidationError):
            engine.verify(None)  # type: ignore[arg-type]


class TestProviderFactories:
    def test_llm_factory_none_provider(self):
        assert isinstance(build_llm_from_config(LLMConfig(provider="none", api_key="x")), NullLLM)

    def test_llm_factory_missing_key_degrades_to_null(self):
        assert isinstance(build_llm_from_config(LLMConfig(api_key=None)), NullLLM)

    def test_llm_factory_with_key(self):
        llm = build_llm_from_config(LLMConfig(api_key="test-key", model="some-model"))
        assert isinstance(llm, OpenAICompatLLM)
        assert "some-model" in llm.name

    def test_retriever_factory_with_key(self):
        retriever = build_retriever_from_config(RetrievalConfig(api_key="tvly-test"))
        assert isinstance(retriever, TavilyRetriever)

    def test_retriever_factory_without_key_degrades_to_empty(self):
        retriever = build_retriever_from_config(RetrievalConfig(api_key=None))
        assert isinstance(retriever, InMemoryRetriever)
        assert retriever.name == "none"
        assert retriever.search("anything") == []

    def test_build_default_engine_without_env(self, monkeypatch):
        from app.falsify import build_default_engine

        for var in ("TAVILY_API_KEY", "LLM_API_KEY", "NEBIUS_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        engine = build_default_engine()
        assert engine._retriever.name == "none"
        assert isinstance(engine._llm, NullLLM)
        # full pipeline still runs and degrades honestly
        result = engine.verify("Company X revenue increased by 20% in 2025.")
        from app.falsify.models import Verdict

        assert result.verdict == Verdict.UNVERIFIABLE
        assert result.llm_used is False

    def test_build_default_engine_with_env(self, monkeypatch):
        from app.falsify import build_default_engine

        monkeypatch.setenv("TAVILY_API_KEY", "tvly-env-test")
        monkeypatch.setenv("LLM_API_KEY", "llm-env-test")
        monkeypatch.setenv("LLM_MODEL", "nebius-model")
        engine = build_default_engine()
        assert isinstance(engine._retriever, TavilyRetriever)
        assert isinstance(engine._llm, OpenAICompatLLM)
        assert "nebius-model" in engine._llm.name
