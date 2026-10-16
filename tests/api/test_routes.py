"""Unit and integration tests for FastAPI endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_app_config
from app.falsify.config import EngineConfig
from app.falsify.engine import FalsifyEngine
from app.falsify.llm.provider import NullLLM
from app.falsify.models import Evidence, Verdict
from app.falsify.retrieval.mock import InMemoryRetriever
from app.main import app
from tests.conftest import (
    CORROBORATING_40PCT,
    INDEPENDENT_NEWS_27PCT,
    OFFICIAL_FILING_27PCT,
    TESLA_LIKE_CLAIM,
    make_engine,
)


@pytest.fixture
def test_client() -> TestClient:
    """TestClient configured with deterministic test engine."""
    test_corpus = [OFFICIAL_FILING_27PCT, INDEPENDENT_NEWS_27PCT, CORROBORATING_40PCT]
    test_engine = make_engine(corpus=test_corpus)
    app.state.engine = test_engine
    with TestClient(app) as client:
        yield client


def test_health_endpoints(test_client: TestClient) -> None:
    """Verify both /health and /api/health respond with 200 and valid schema."""
    for path in ["/health", "/api/health"]:
        response = test_client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["app_name"] == get_app_config().app_name
        assert data["engine_version"] == "1.0.0"
        assert data["retrieval_provider"] == "in_memory"
        assert data["llm_configured"] is False
        assert "timestamp" in data


def test_verify_valid_claim_refuted(test_client: TestClient) -> None:
    """Verify POST /api/verify executes full pipeline and returns complete result."""
    response = test_client.post(
        "/api/verify",
        json={"claim": TESLA_LIKE_CLAIM},
    )
    assert response.status_code == 200
    data = response.json()

    # Core assertion: claim refuted by official filing in test corpus
    assert data["verdict"] == Verdict.REFUTED.value
    assert data["claim_text"] == TESLA_LIKE_CLAIM
    assert data["confidence"] > 0.5
    assert isinstance(data["confidence_explanation"], str)

    # Complete serialization check: all core sub-models present
    assert "claim_id" in data
    assert "claim" in data
    assert data["claim"]["original_text"] == TESLA_LIKE_CLAIM
    assert data["claim"]["claim_kind"] == "quantitative_change"

    assert "hypotheses" in data
    assert len(data["hypotheses"]) > 0

    assert "queries" in data
    assert len(data["queries"]) > 0

    assert "evidence" in data
    assert len(data["evidence"]) >= 2

    assert "assessments" in data
    assert len(data["assessments"]) >= 2

    assert "contradictions" in data
    assert len(data["contradictions"]) >= 1
    assert data["contradictions"][0]["contradiction_type"] == "numerical"

    assert "fusion" in data
    assert data["fusion"]["total_evidence"] >= 2

    assert "reasoning_trace" in data
    trace = data["reasoning_trace"]
    assert trace["verdict"] == Verdict.REFUTED.value
    assert "stage_timings_ms" in trace
    assert "hypotheses" in trace
    assert "evidence" in trace

    assert "confidence_breakdown" in data
    assert "retrieval_coverage" in data["confidence_breakdown"]


def test_verify_invalid_claims_return_400(test_client: TestClient) -> None:
    """Verify empty, whitespace, and excessively long claims return HTTP 400."""
    # 1. Empty string
    res_empty = test_client.post("/api/verify", json={"claim": ""})
    assert res_empty.status_code == 400
    assert "ClaimValidationError" in res_empty.json().get("error_type", "")

    # 2. Whitespace only
    res_ws = test_client.post("/api/verify", json={"claim": "   \n\t   "})
    assert res_ws.status_code == 400
    assert "ClaimValidationError" in res_ws.json().get("error_type", "")

    # 3. Exceeds 4,000 characters
    long_claim = "A" * 4001
    res_long = test_client.post("/api/verify", json={"claim": long_claim})
    assert res_long.status_code == 400
    assert "ClaimValidationError" in res_long.json().get("error_type", "")


def test_resilience_empty_retriever_yields_unverifiable(test_client: TestClient) -> None:
    """Verify engine returns UNVERIFIABLE without crashing when no evidence is found."""
    empty_engine = FalsifyEngine(
        config=EngineConfig(
            use_llm_for_normalization=False,
            use_llm_for_hypotheses=False,
            use_llm_for_queries=False,
            use_llm_for_evidence_assessment=False,
            use_llm_for_synthesis=False,
        ),
        llm=NullLLM(),
        retriever=InMemoryRetriever([], min_overlap=1),
    )
    app.state.engine = empty_engine

    response = test_client.post(
        "/api/verify",
        json={"claim": "Some completely novel claim with no sources."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == Verdict.UNVERIFIABLE.value
    assert len(data["evidence"]) == 0
    # Engine never fabricates evidence
    assert data["reasoning_trace"]["evidence_summary"]["total"] == 0


def test_cors_headers(test_client: TestClient) -> None:
    """Verify CORS headers are returned for cross-origin callers."""
    response = test_client.options(
        "/api/verify",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") in ["*", "http://localhost:5173"]
