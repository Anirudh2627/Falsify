"""Tests for the retrieval layer (offline: httpx is monkeypatched)."""

from __future__ import annotations

import json

import pytest

from app.falsify.config import RetrievalConfig
from app.falsify.exceptions import ConfigurationError, RetrieverUnavailableError
from app.falsify.retrieval.base import EvidenceRetriever, extract_domain
from app.falsify.retrieval.mock import InMemoryRetriever
from app.falsify.retrieval.tavily import TavilyRetriever


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or json.dumps(payload or {})

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


@pytest.fixture
def fake_tavily(monkeypatch):
    captured: dict = {}

    def _install(response: _FakeResponse):
        def _post(url, json=None, timeout=None):
            captured["url"] = url
            captured["payload"] = json
            return response

        monkeypatch.setattr("app.falsify.retrieval.tavily.httpx.post", _post)
        return captured

    return _install


class TestTavilyRetriever:
    def test_requires_api_key(self):
        with pytest.raises(ConfigurationError):
            TavilyRetriever(RetrievalConfig(api_key=None))

    def test_maps_response_to_evidence(self, fake_tavily):
        captured = fake_tavily(
            _FakeResponse(
                payload={
                    "results": [
                        {
                            "title": "Company X 10-K",
                            "url": "https://www.sec.gov/filing.htm",
                            "content": "Revenue increased 27% in 2025.",
                            "score": 0.93,
                            "published_date": "2026-02-01",
                        },
                        {"title": "no url item", "content": "should be skipped"},
                    ]
                }
            )
        )
        retriever = TavilyRetriever(RetrievalConfig(api_key="tvly-test-key"))
        evidence = retriever.search("company x revenue 2025", max_results=5)

        assert len(evidence) == 1  # URL-less result skipped: never fabricate sources
        ev = evidence[0]
        assert ev.source_url == "https://www.sec.gov/filing.htm"
        assert ev.domain == "sec.gov"
        assert ev.retrieved_text == "Revenue increased 27% in 2025."
        assert ev.publication_date == "2026-02-01"
        assert ev.score == pytest.approx(0.93)
        # API key travels in the request body only (Tavily protocol), URL is the API endpoint
        assert captured["url"] == "https://api.tavily.com/search"
        assert captured["payload"]["query"] == "company x revenue 2025"
        assert captured["payload"]["max_results"] == 5

    def test_http_error_raises_structured_failure(self, fake_tavily):
        fake_tavily(_FakeResponse(status_code=500, payload=None, text="internal error"))
        retriever = TavilyRetriever(RetrievalConfig(api_key="tvly-test-key"))
        with pytest.raises(RetrieverUnavailableError, match="500"):
            retriever.search("anything")

    def test_auth_failure_is_distinct(self, fake_tavily):
        fake_tavily(_FakeResponse(status_code=401, payload=None, text="unauthorized"))
        retriever = TavilyRetriever(RetrievalConfig(api_key="bad-key"))
        with pytest.raises(RetrieverUnavailableError, match="authentication"):
            retriever.search("anything")

    def test_rate_limit_is_distinct(self, fake_tavily):
        fake_tavily(_FakeResponse(status_code=429, payload=None, text="slow down"))
        retriever = TavilyRetriever(RetrievalConfig(api_key="tvly-test-key"))
        with pytest.raises(RetrieverUnavailableError, match="rate limit"):
            retriever.search("anything")

    def test_implements_protocol(self):
        retriever = TavilyRetriever(RetrievalConfig(api_key="tvly-test-key"))
        assert isinstance(retriever, EvidenceRetriever)


class TestInMemoryRetriever:
    def test_matches_by_overlap_and_ranks(self):
        from tests.conftest import make_evidence

        corpus = [
            make_evidence(url="https://a.example/1", title="Tesla revenue 2025", text="Tesla revenue increased 20% in 2025"),
            make_evidence(url="https://b.example/2", title="Unrelated", text="pancakes are tasty"),
        ]
        retriever = InMemoryRetriever(corpus)
        results = retriever.search("Tesla revenue 2025 annual report")
        assert results
        assert results[0].source_url == "https://a.example/1"
        assert retriever.queries == ["Tesla revenue 2025 annual report"]

    def test_failure_injection(self):
        retriever = InMemoryRetriever([], fail_with=RetrieverUnavailableError("boom"))
        with pytest.raises(RetrieverUnavailableError):
            retriever.search("q")


class TestExtractDomain:
    def test_strips_www(self):
        assert extract_domain("https://WWW.Reuters.com/article/1") == "reuters.com"

    def test_garbage(self):
        assert extract_domain("not a url") in ("", "not a url")
