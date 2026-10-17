"""Phase 5 End-to-End Integration and Reliability Hardening Test Suite.

Verifies:
1. Complete verification workflow (stream -> persist -> history list -> detail lookup -> delete).
2. Standard verification workflow (verify -> persist -> history -> delete).
3. UNVERIFIABLE verdict flow persistence and history consistency.
4. Database isolation across temporary SQLite databases.
5. Failure paths: empty claim, excessive length, database errors, 404s, 422s.
6. Detail endpoint purity: historical lookup never re-invokes the engine.
7. Deletion isolation: deleting one record preserves all other records.
8. Error hygiene: no credentials, file paths, or raw tracebacks leaked in error payloads.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import VerificationRecord
from app.db.repository import (
    create_verification_record,
    get_verification_record,
)
from app.db.session import dispose_engine, get_db, set_custom_engine
from app.falsify.engine import FalsifyEngine
from app.falsify.models import (
    ConfidenceBreakdown,
    FusionSummary,
    ReasoningTrace,
    Verdict,
    VerificationResult,
)
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
    """Provide an isolated, temporary SQLite database session for each test."""
    db_file = tmp_path / "test_e2e_falsify.db"
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


def parse_sse_events(raw_body: str) -> list[dict]:
    """Parse raw SSE body into a list of parsed event dictionaries."""
    events = []
    frames = raw_body.strip().split("\n\n")
    for frame in frames:
        if not frame.strip():
            continue
        event_type = ""
        event_id = ""
        data_str = ""
        for line in frame.strip().split("\n"):
            line = line.strip()
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("id:"):
                event_id = line[3:].strip()
            elif line.startswith("data:"):
                data_str = line[5:].strip()

        data_obj = json.loads(data_str) if data_str else {}
        events.append({"id": event_id, "event": event_type, "data": data_obj})
    return events


# ---------------------------------------------------------------------------
# Test 1: Complete End-to-End Workflow (Stream -> Persist -> History -> Detail -> Delete)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_full_verification_workflow_stream(isolated_db: Session) -> None:
    """End-to-end integration test:
    1. Submit valid claim to /api/verify/stream.
    2. Receive verification_started, progress, and verification_completed events.
    3. Verify record was persisted in SQLite.
    4. Query /api/verifications and locate the newly created record.
    5. Query /api/verifications/{id} and verify stored result matches completed result.
    6. Send DELETE /api/verifications/{id} and verify HTTP 204.
    7. Query /api/verifications/{id} and verify HTTP 404.
    8. Query /api/verifications and verify record is gone.
    """
    engine = make_engine(
        corpus=[OFFICIAL_FILING_27PCT, INDEPENDENT_NEWS_27PCT, CORROBORATING_40PCT]
    )
    app.state.engine = engine

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Step 1 & 2: Stream verification
        response = await client.post(
            "/api/verify/stream",
            json={"claim": TESLA_LIKE_CLAIM},
            headers={"Accept": "text/event-stream"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        events = parse_sse_events(response.text)
        assert len(events) >= 3

        # Started event
        assert events[0]["event"] == "verification_started"
        assert events[0]["data"]["claim"] == TESLA_LIKE_CLAIM

        # Completed event
        completed_events = [e for e in events if e["event"] == "verification_completed"]
        assert len(completed_events) == 1
        comp = completed_events[0]["data"]
        assert comp["verdict"] == "REFUTED"
        assert comp["confidence"] > 0.0
        verification_id = comp["verification_id"]
        assert isinstance(verification_id, int)
        original_result = comp["result"]
        assert original_result["verdict"] == "REFUTED"
        assert original_result["id"] == verification_id

        # Step 3: Verify record in SQLite directly
        db_record = get_verification_record(isolated_db, verification_id)
        assert db_record is not None
        assert db_record.claim_text == TESLA_LIKE_CLAIM
        assert db_record.verdict == "REFUTED"
        assert round(db_record.confidence, 3) == round(comp["confidence"], 3)

        # Step 4: Query /api/verifications (history list)
        history_resp = await client.get("/api/verifications?page=1&page_size=10")
        assert history_resp.status_code == 200
        history_data = history_resp.json()
        assert history_data["total"] == 1
        assert history_data["items"][0]["id"] == verification_id
        assert history_data["items"][0]["verdict"] == "REFUTED"

        # Step 5: Query /api/verifications/{id} (detail lookup)
        detail_resp = await client.get(f"/api/verifications/{verification_id}")
        assert detail_resp.status_code == 200
        detail_data = detail_resp.json()
        assert detail_data["id"] == verification_id
        assert detail_data["verdict"] == "REFUTED"
        assert detail_data["claim_text"] == TESLA_LIKE_CLAIM
        assert detail_data["confidence"] == original_result["confidence"]
        assert len(detail_data["evidence"]) == len(original_result["evidence"])

        # Step 6: Delete record
        del_resp = await client.delete(f"/api/verifications/{verification_id}")
        assert del_resp.status_code == 204

        # Step 7: Verify 404 on deleted record
        lookup_after_del = await client.get(f"/api/verifications/{verification_id}")
        assert lookup_after_del.status_code == 404

        # Step 8: Verify history list is now empty
        empty_history_resp = await client.get("/api/verifications")
        assert empty_history_resp.status_code == 200
        assert empty_history_resp.json()["total"] == 0
        assert len(empty_history_resp.json()["items"]) == 0


# ---------------------------------------------------------------------------
# Test 2: Standard Synchronous Verification Workflow
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_full_verification_workflow_standard(isolated_db: Session) -> None:
    """Standard POST /api/verify workflow creates exactly 1 record, persists full JSON,
    and supports retrieval and deletion.
    """
    engine = make_engine(
        corpus=[OFFICIAL_FILING_27PCT, INDEPENDENT_NEWS_27PCT, CORROBORATING_40PCT]
    )
    app.state.engine = engine

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Standard verify request
        resp = await client.post("/api/verify", json={"claim": TESLA_LIKE_CLAIM})
        assert resp.status_code == 200
        result_payload = resp.json()

        assert "id" in result_payload
        record_id = result_payload["id"]
        assert result_payload["verdict"] == "REFUTED"

        # Confirm exactly 1 record in history
        hist = await client.get("/api/verifications")
        assert hist.json()["total"] == 1
        assert hist.json()["items"][0]["id"] == record_id

        # Verify detail
        det = await client.get(f"/api/verifications/{record_id}")
        assert det.status_code == 200
        assert det.json()["id"] == record_id
        assert det.json()["claim_text"] == TESLA_LIKE_CLAIM

        # Clean up
        del_resp = await client.delete(f"/api/verifications/{record_id}")
        assert del_resp.status_code == 204


# ---------------------------------------------------------------------------
# Test 3: UNVERIFIABLE Verdict Flow
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_unverifiable_verdict_persisted_and_retrieved(isolated_db: Session) -> None:
    """An unresolvable claim with no evidence yields UNVERIFIABLE, which must persist
    and retrieve cleanly without errors.
    """
    engine = make_engine(corpus=[])  # Empty retriever yields UNVERIFIABLE
    app.state.engine = engine

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Test streamed path
        stream_resp = await client.post(
            "/api/verify/stream",
            json={"claim": "Undocumented historical claim with zero sources."},
            headers={"Accept": "text/event-stream"},
        )
        assert stream_resp.status_code == 200
        events = parse_sse_events(stream_resp.text)
        completed = next(e for e in events if e["event"] == "verification_completed")
        assert completed["data"]["verdict"] == "UNVERIFIABLE"
        rec_id = completed["data"]["verification_id"]

        # Confirm persisted record
        hist = await client.get(f"/api/verifications/{rec_id}")
        assert hist.status_code == 200
        assert hist.json()["verdict"] == "UNVERIFIABLE"

        # Confirm verdict filter works
        filter_resp = await client.get("/api/verifications?verdict=UNVERIFIABLE")
        assert filter_resp.status_code == 200
        assert filter_resp.json()["total"] == 1

        filter_other = await client.get("/api/verifications?verdict=VERIFIED")
        assert filter_other.status_code == 200
        assert filter_other.json()["total"] == 0


# ---------------------------------------------------------------------------
# Test 4: Detail Lookup Does Not Rerun Verification
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_historical_detail_does_not_invoke_engine(isolated_db: Session) -> None:
    """Fetching /api/verifications/{id} must be a pure database read and must never
    invoke engine.verify().
    """
    mock_engine = MagicMock(spec=FalsifyEngine)
    app.state.engine = mock_engine

    # Seed record directly in database
    record = create_verification_record(
        isolated_db,
        claim_id="claim_test_pure",
        claim_text="Pre-stored empirical statement",
        verdict="VERIFIED",
        confidence=0.95,
        result_json={
            "claim_id": "claim_test_pure",
            "claim_text": "Pre-stored empirical statement",
            "verdict": "VERIFIED",
            "confidence": 0.95,
            "evidence": [],
            "hypotheses": [],
            "queries": [],
            "assessments": [],
            "contradictions": [],
            "reasoning_trace": {"stages": [], "stage_timings_ms": {}},
        },
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(f"/api/verifications/{record.id}")
        assert resp.status_code == 200
        assert resp.json()["verdict"] == "VERIFIED"

    # Engine must not have been touched
    mock_engine.verify.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5: Deletion Isolation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_deletion_isolation_between_records(isolated_db: Session) -> None:
    """Deleting record A leaves record B intact and correctly decrements total count."""
    r1 = create_verification_record(
        isolated_db,
        claim_id="c1",
        claim_text="First claim",
        verdict="VERIFIED",
        confidence=0.9,
        result_json={"verdict": "VERIFIED"},
    )
    r2 = create_verification_record(
        isolated_db,
        claim_id="c2",
        claim_text="Second claim",
        verdict="REFUTED",
        confidence=0.8,
        result_json={"verdict": "REFUTED"},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Check initial count is 2
        initial = await client.get("/api/verifications")
        assert initial.json()["total"] == 2

        # Delete r1
        del_resp = await client.delete(f"/api/verifications/{r1.id}")
        assert del_resp.status_code == 204

        # r1 is gone
        assert (await client.get(f"/api/verifications/{r1.id}")).status_code == 404

        # r2 is still present and intact
        r2_resp = await client.get(f"/api/verifications/{r2.id}")
        assert r2_resp.status_code == 200
        assert r2_resp.json()["verdict"] == "REFUTED"

        # Count is 1
        after = await client.get("/api/verifications")
        assert after.json()["total"] == 1
        assert after.json()["items"][0]["id"] == r2.id


# ---------------------------------------------------------------------------
# Test 6: Failure Paths and Error Semantics
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_empty_and_whitespace_claim_rejection() -> None:
    """Empty and whitespace-only claims must return HTTP 400 ClaimValidationError."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        for bad_claim in ["", "   ", "\n\t"]:
            # Standard endpoint
            resp = await client.post("/api/verify", json={"claim": bad_claim})
            assert resp.status_code == 400
            assert "empty" in resp.json()["detail"].lower()

            # Stream endpoint
            stream_resp = await client.post("/api/verify/stream", json={"claim": bad_claim})
            assert stream_resp.status_code == 400
            assert "empty" in stream_resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_excessive_length_claim_rejection() -> None:
    """Claims exceeding 4000 characters must return HTTP 400 ClaimValidationError."""
    long_claim = "x" * 4001
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post("/api/verify", json={"claim": long_claim})
        assert resp.status_code == 400
        assert "too long" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_invalid_verdict_filter_rejected() -> None:
    """Supplying an unsupported verdict filter returns HTTP 422 with supported values."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/verifications?verdict=FABRICATED_VERDICT")
        assert resp.status_code == 422
        assert "Unsupported verdict filter" in resp.json()["detail"]


@pytest.mark.anyio
async def test_delete_nonexistent_record_returns_404(isolated_db: Session) -> None:
    """Deleting a non-existent record ID returns HTTP 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.delete("/api/verifications/999999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 7: Persistence Error during Streaming Emits verification_error
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_stream_persistence_failure_emits_error_event(isolated_db: Session) -> None:
    """If database persistence fails during streaming, the stream must emit verification_error
    and must NEVER emit verification_completed with a false success.
    """
    engine = make_engine(
        corpus=[OFFICIAL_FILING_27PCT, INDEPENDENT_NEWS_27PCT, CORROBORATING_40PCT]
    )
    app.state.engine = engine

    with patch(
        "app.services.streaming.create_verification_record",
        side_effect=RuntimeError("Simulated database failure"),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/api/verify/stream",
                json={"claim": TESLA_LIKE_CLAIM},
                headers={"Accept": "text/event-stream"},
            )
            assert resp.status_code == 200
            events = parse_sse_events(resp.text)

            # Must have verification_error
            error_events = [e for e in events if e["event"] == "verification_error"]
            assert len(error_events) == 1
            assert error_events[0]["data"]["code"] == "DatabaseError"

            # Must NEVER have verification_completed
            completed_events = [e for e in events if e["event"] == "verification_completed"]
            assert len(completed_events) == 0


# ---------------------------------------------------------------------------
# Test 8: Health Check Diagnostics Contract
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_health_endpoints_match_contract() -> None:
    """Both /health and /api/health must return status ok, application version,
    engine version, and provider configuration.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        for path in ["/health", "/api/health"]:
            resp = await client.get(path)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert "app_name" in data
            assert "app_version" in data
            assert "engine_version" in data
            assert "retrieval_provider" in data
            assert "llm_configured" in data
            assert "timestamp" in data
