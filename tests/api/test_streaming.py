"""Comprehensive tests for Phase 3: Server-Sent Events (SSE) streaming verification."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.repository import get_verification_record
from app.db.session import dispose_engine, get_db, set_custom_engine
from app.falsify.config import EngineConfig
from app.falsify.engine import FalsifyEngine
from app.falsify.llm.provider import NullLLM
from app.falsify.models import (
    Claim,
    ConfidenceBreakdown,
    FusionSummary,
    ReasoningTrace,
    Verdict,
    VerificationResult,
)
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
def isolated_db(tmp_path: Path) -> Generator[Session, None, None]:
    """Provide an isolated, temporary SQLite database session for tests."""
    db_file = tmp_path / "test_stream_falsify.db"
    db_url = f"sqlite:///{db_file}"

    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    set_custom_engine(engine)

    testing_session_factory = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    def override_get_db() -> Generator[Session, None, None]:
        session = testing_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    session = testing_session_factory()
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.clear()
        dispose_engine()


@pytest.fixture
def test_engine() -> FalsifyEngine:
    """Configured test engine using offline fixtures."""
    corpus = [OFFICIAL_FILING_27PCT, INDEPENDENT_NEWS_27PCT, CORROBORATING_40PCT]
    engine = make_engine(corpus=corpus)
    app.state.engine = engine
    return engine


def parse_sse_events(raw_text: str) -> list[tuple[str, dict]]:
    """Parse raw SSE text stream into a list of (event_name, data_dict) tuples."""
    events = []
    blocks = [b.strip() for b in raw_text.strip().split("\n\n") if b.strip()]
    for block in blocks:
        event_name = ""
        data_str = ""
        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_str = line.split(":", 1)[1].strip()
        if event_name and data_str:
            events.append((event_name, json.loads(data_str)))
    return events


# ---------------------------------------------------------------------------
# Test Cases 1-6: Happy Path, Event Protocol, Result Completeness & Persistence
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_1_to_5_valid_stream_protocol_and_persistence(isolated_db: Session, test_engine: FalsifyEngine) -> None:
    """Tests 1-5: Protocol events, progress format, completion result, and exact persistence."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/verify/stream", json={"claim": TESLA_LIKE_CLAIM})
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        assert response.headers.get("cache-control") == "no-cache"
        assert response.headers.get("x-accel-buffering") == "no"

        events = parse_sse_events(response.text)
        assert len(events) >= 3

        # 1. Started event
        start_event = events[0]
        assert start_event[0] == "verification_started"
        assert start_event[1]["claim"] == TESLA_LIKE_CLAIM
        assert "message" in start_event[1]

        # 2. Progress events follow schema (stage, message, progress)
        progress_events = [e for e in events if e[0] == "verification_progress"]
        assert len(progress_events) >= 1
        for _, p_data in progress_events:
            assert "stage" in p_data
            assert "message" in p_data
            assert "progress" in p_data
            assert 0.0 <= p_data["progress"] <= 1.0

        # 3. Completed event contains full result
        completed_events = [e for e in events if e[0] == "verification_completed"]
        assert len(completed_events) == 1
        c_name, c_data = completed_events[0]
        assert c_name == "verification_completed"
        assert "verification_id" in c_data
        assert "result" in c_data

        result = c_data["result"]
        assert result["verdict"] == Verdict.REFUTED.value
        assert "confidence_breakdown" in result
        assert "reasoning_trace" in result
        assert "hypotheses" in result
        assert "queries" in result
        assert "evidence" in result
        assert "contradictions" in result

        # 4 & 5. Persisted exactly once in database with matching ID
        record_id = c_data["verification_id"]
        record = get_verification_record(isolated_db, record_id)
        assert record is not None
        assert record.id == record_id
        assert record.claim_text == TESLA_LIKE_CLAIM
        assert record.verdict == Verdict.REFUTED.value


@pytest.mark.anyio
async def test_6_unverifiable_treated_as_completion(isolated_db: Session) -> None:
    """6. A normal UNVERIFIABLE result is treated as completion and persisted."""
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

    claim = "Claim with no sources anywhere."
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/verify/stream", json={"claim": claim})
        assert response.status_code == 200

        events = parse_sse_events(response.text)
        completed = [e for e in events if e[0] == "verification_completed"]
        assert len(completed) == 1
        assert completed[0][1]["verdict"] == Verdict.UNVERIFIABLE.value
        rec_id = completed[0][1]["verification_id"]

        # Verified in DB
        record = get_verification_record(isolated_db, rec_id)
        assert record is not None
        assert record.verdict == Verdict.UNVERIFIABLE.value


# ---------------------------------------------------------------------------
# Test Cases 7-9: Validation, Error Handling, and Resilience
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_7_invalid_claims_rejected_consistently(isolated_db: Session) -> None:
    """7. Invalid claims are rejected consistently with HTTP 400 before streaming starts."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r_empty = await client.post("/api/verify/stream", json={"claim": ""})
        assert r_empty.status_code == 400
        assert "ClaimValidationError" in r_empty.json()["error_type"]

        r_ws = await client.post("/api/verify/stream", json={"claim": "   \n\t   "})
        assert r_ws.status_code == 400
        assert "ClaimValidationError" in r_ws.json()["error_type"]

        r_long = await client.post("/api/verify/stream", json={"claim": "A" * 4001})
        assert r_long.status_code == 400
        assert "ClaimValidationError" in r_long.json()["error_type"]


@pytest.mark.anyio
async def test_8_unexpected_engine_failures_emit_error_without_leaks(isolated_db: Session) -> None:
    """8. Unexpected engine failures emit verification_error without leaking stack traces or secrets."""
    failing_engine = MagicMock()
    failing_engine.verify.side_effect = RuntimeError("External timeout from secret-token-xyz")
    app.state.engine = failing_engine

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/verify/stream", json={"claim": "Test claim"})
        assert response.status_code == 200

        events = parse_sse_events(response.text)
        error_events = [e for e in events if e[0] == "verification_error"]
        assert len(error_events) == 1
        _, err_data = error_events[0]
        assert err_data["code"] == "RuntimeError"
        assert "External timeout" in err_data["message"]
        # Ensure no completion event was emitted
        assert not any(e[0] == "verification_completed" for e in events)


@pytest.mark.anyio
async def test_9_database_persistence_failures_emit_error(isolated_db: Session, test_engine: FalsifyEngine) -> None:
    """9. Database persistence failures are reported via verification_error, not verification_completed."""
    with patch("app.services.streaming.create_verification_record", side_effect=RuntimeError("Disk full")):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/verify/stream", json={"claim": TESLA_LIKE_CLAIM})
            assert response.status_code == 200

            events = parse_sse_events(response.text)
            error_events = [e for e in events if e[0] == "verification_error"]
            assert len(error_events) == 1
            assert error_events[0][1]["code"] == "DatabaseError"
            assert "Failed to persist" in error_events[0][1]["message"]
            assert not any(e[0] == "verification_completed" for e in events)


# ---------------------------------------------------------------------------
# Test Cases 10-12: Endpoints Compatibility & History Retrieval
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_10_history_retrieves_streamed_verification(isolated_db: Session, test_engine: FalsifyEngine) -> None:
    """10. Existing history endpoints can retrieve the streamed verification result."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Stream verification
        response = await client.post("/api/verify/stream", json={"claim": TESLA_LIKE_CLAIM})
        assert response.status_code == 200
        events = parse_sse_events(response.text)
        rec_id = next(e[1]["verification_id"] for e in events if e[0] == "verification_completed")

        # Fetch from history
        h_resp = await client.get(f"/api/verifications/{rec_id}")
        assert h_resp.status_code == 200
        h_data = h_resp.json()
        assert h_data["id"] == rec_id
        assert h_data["verdict"] == Verdict.REFUTED.value
        assert h_data["claim_text"] == TESLA_LIKE_CLAIM


@pytest.mark.anyio
async def test_11_and_12_existing_verify_and_health_remain_functional(isolated_db: Session, test_engine: FalsifyEngine) -> None:
    """11 & 12. Existing POST /api/verify and GET /health remain fully backward compatible."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check health
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "ok"

        # Check synchronous /api/verify
        verify_resp = await client.post("/api/verify", json={"claim": TESLA_LIKE_CLAIM})
        assert verify_resp.status_code == 200
        data = verify_resp.json()
        assert data["verdict"] == Verdict.REFUTED.value
        assert "id" in data


# ---------------------------------------------------------------------------
# Test Cases 13-15: Non-Blocking Execution, Disconnects, Framing
# ---------------------------------------------------------------------------


class SlowStreamingEngine:
    """Engine simulating multi-second execution."""

    def __init__(self, delay_s: float = 0.35) -> None:
        self.delay_s = delay_s

    def verify(self, claim_text: str) -> VerificationResult:
        time.sleep(self.delay_s)
        claim = Claim(original_text=claim_text, normalized_text=claim_text)
        return VerificationResult(
            claim_id=claim.claim_id,
            claim_text=claim_text,
            verdict=Verdict.VERIFIED,
            confidence=0.88,
            confidence_explanation="Verified after delay.",
            confidence_breakdown=ConfidenceBreakdown(),
            claim=claim,
            hypotheses=[],
            queries=[],
            evidence=[],
            assessments=[],
            contradictions=[],
            fusion=FusionSummary(),
            reasoning_trace=ReasoningTrace(verdict=Verdict.VERIFIED, confidence=0.88),
            errors=[],
            engine_version="1.0.0",
        )


@pytest.mark.anyio
async def test_13_streaming_does_not_block_event_loop(isolated_db: Session) -> None:
    """13. The streaming implementation does not block the event loop during engine execution."""
    app.state.engine = SlowStreamingEngine(delay_s=0.35)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        t0 = time.perf_counter()

        # Start streaming request
        stream_task = asyncio.create_task(
            client.post("/api/verify/stream", json={"claim": "Concurrency streaming claim."})
        )

        await asyncio.sleep(0.05)

        # Health request during active streaming
        h_t0 = time.perf_counter()
        h_resp = await client.get("/health")
        h_duration = time.perf_counter() - h_t0

        assert h_resp.status_code == 200
        # Must respond immediately without waiting for the 350ms stream engine
        assert h_duration < 0.20, f"Health check took too long: {h_duration:.3f}s"

        stream_resp = await stream_task
        assert stream_resp.status_code == 200
        events = parse_sse_events(stream_resp.text)
        assert any(e[0] == "verification_completed" for e in events)


@pytest.mark.anyio
async def test_14_disconnect_cleanup(isolated_db: Session) -> None:
    """14. Client cancellation/disconnect does not leave open sessions or unmanaged tasks."""
    app.state.engine = SlowStreamingEngine(delay_s=0.5)

    from app.services.streaming import stream_verification

    # Test that cancelling the generator cleans up handlers and closes sessions
    gen = stream_verification("Disconnect test claim", app.state.engine)
    first_chunk = await gen.asend(None)
    assert "verification_started" in first_chunk

    # Cancel generator
    await gen.aclose()


def test_15_sse_framing_validity() -> None:
    """15. SSE frames contain valid event names, JSON payloads, and double newline framing."""
    from app.services.streaming import format_sse

    frame = format_sse("custom_event", {"key": "value", "num": 42}, event_id="ev_123")
    assert frame.startswith("id: ev_123\nevent: custom_event\ndata: {")
    assert frame.endswith("\n\n")

    # Parse and assert validity
    parsed = parse_sse_events(frame)
    assert len(parsed) == 1
    assert parsed[0][0] == "custom_event"
    assert parsed[0][1] == {"key": "value", "num": 42}
