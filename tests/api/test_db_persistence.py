"""Comprehensive tests for Phase 2: SQLite database persistence, migrations, and history."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import VerificationRecord
from app.db.repository import (
    create_verification_record,
    delete_verification_record,
    get_verification_record,
    list_verification_records,
)
from app.db.session import dispose_engine, get_db, set_custom_engine
from app.falsify.config import EngineConfig
from app.falsify.engine import FalsifyEngine
from app.falsify.llm.provider import NullLLM
from app.falsify.models import Verdict
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
    db_file = tmp_path / "test_falsify.db"
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
def client(isolated_db: Session) -> Generator[TestClient, None, None]:
    """TestClient configured with test engine and isolated database."""
    test_corpus = [OFFICIAL_FILING_27PCT, INDEPENDENT_NEWS_27PCT, CORROBORATING_40PCT]
    test_engine = make_engine(corpus=test_corpus)
    app.state.engine = test_engine
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# Group 1: Database and Persistence Tests (Cases 1-5)
# ---------------------------------------------------------------------------


def test_1_valid_verification_creates_database_record(client: TestClient, isolated_db: Session) -> None:
    """1. A valid verification request creates a database record."""
    response = client.post("/api/verify", json={"claim": TESLA_LIKE_CLAIM})
    assert response.status_code == 200
    data = response.json()

    assert "id" in data
    record_id = data["id"]
    assert isinstance(record_id, int)

    # Verify persisted in database
    record = get_verification_record(isolated_db, record_id)
    assert record is not None
    assert record.id == record_id
    assert record.claim_text == TESLA_LIKE_CLAIM
    assert record.verdict == Verdict.REFUTED.value
    assert record.confidence > 0.5


def test_2_complete_verification_result_stored_and_retrieved(client: TestClient, isolated_db: Session) -> None:
    """2. The complete verification result is stored and can be retrieved."""
    response = client.post("/api/verify", json={"claim": TESLA_LIKE_CLAIM})
    assert response.status_code == 200
    record_id = response.json()["id"]

    record = get_verification_record(isolated_db, record_id)
    assert record is not None
    stored_result = record.result_json

    # All major fields preserved
    assert stored_result["verdict"] == Verdict.REFUTED.value
    assert stored_result["confidence"] == response.json()["confidence"]
    assert "hypotheses" in stored_result
    assert "queries" in stored_result
    assert "evidence" in stored_result
    assert "assessments" in stored_result
    assert "contradictions" in stored_result
    assert "fusion" in stored_result
    assert "reasoning_trace" in stored_result
    assert "confidence_breakdown" in stored_result


def test_3_unverifiable_result_saved_in_database(client: TestClient, isolated_db: Session) -> None:
    """3. An UNVERIFIABLE result returned normally by the engine is saved."""
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

    claim = "Unknown claim with absolutely no matching sources anywhere."
    response = client.post("/api/verify", json={"claim": claim})
    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == Verdict.UNVERIFIABLE.value
    assert "id" in data

    record = get_verification_record(isolated_db, data["id"])
    assert record is not None
    assert record.verdict == Verdict.UNVERIFIABLE.value
    assert record.claim_text == claim


def test_4_database_errors_cause_rollback_and_error_handling(client: TestClient, isolated_db: Session) -> None:
    """4. Database errors cause appropriate rollback and error handling without leaking secrets."""
    # Simulate a database failure by patching create_verification_record
    from unittest.mock import patch

    with patch("app.services.verification_service.create_verification_record", side_effect=RuntimeError("Disk I/O error")):
        response = client.post("/api/verify", json={"claim": TESLA_LIKE_CLAIM})
        assert response.status_code == 500
        data = response.json()
        assert data["error_type"] == "DatabaseError"
        assert "Failed to persist" in data["detail"]
        # Ensure no SQL credentials or stack traces are leaked
        assert "sqlite" not in data["detail"].lower()
        assert "password" not in data["detail"].lower()


def test_5_sessions_close_correctly(isolated_db: Session) -> None:
    """5. Sessions close correctly after requests."""
    closed_tracker = []

    def tracking_get_db():
        from app.db.session import get_session_factory
        session = get_session_factory()()
        orig_close = session.close

        def tracked_close():
            closed_tracker.append(True)
            orig_close()

        session.close = tracked_close
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = tracking_get_db
    with TestClient(app) as test_client:
        resp = test_client.get("/api/verifications")
        assert resp.status_code == 200

    assert len(closed_tracker) >= 1
    assert all(closed_tracker)


# ---------------------------------------------------------------------------
# Group 2: History List & Filter Tests (Cases 6-13)
# ---------------------------------------------------------------------------


def test_6_empty_history_returns_valid_paginated_response(client: TestClient) -> None:
    """6. Empty history returns a valid empty paginated response."""
    response = client.get("/api/verifications")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert data["total_pages"] == 0


def test_7_multiple_records_returned_newest_first(client: TestClient, isolated_db: Session) -> None:
    """7. Multiple records are returned newest first."""
    for i in range(3):
        create_verification_record(
            isolated_db,
            claim_id=f"claim_{i}",
            claim_text=f"Claim text {i}",
            verdict=Verdict.VERIFIED.value,
            confidence=0.8,
            result_json={"claim": f"Claim {i}"},
            created_at=datetime(2026, 1, 10 + i, 12, 0, 0, tzinfo=UTC),
        )

    response = client.get("/api/verifications")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 3
    # Newest created_at first (index 2, then 1, then 0)
    assert items[0]["claim_text"] == "Claim text 2"
    assert items[1]["claim_text"] == "Claim text 1"
    assert items[2]["claim_text"] == "Claim text 0"


def test_8_pagination_returns_correct_page_and_total_count(client: TestClient, isolated_db: Session) -> None:
    """8. Pagination returns the correct page and total count."""
    for i in range(15):
        create_verification_record(
            isolated_db,
            claim_id=f"claim_{i}",
            claim_text=f"Claim number {i:02d}",
            verdict=Verdict.VERIFIED.value,
            confidence=0.8,
            result_json={"index": i},
            created_at=datetime(2026, 1, 1, i, 0, 0, tzinfo=UTC),
        )

    # Page 1, page_size 5
    p1 = client.get("/api/verifications?page=1&page_size=5")
    assert p1.status_code == 200
    d1 = p1.json()
    assert d1["total"] == 15
    assert d1["page"] == 1
    assert d1["page_size"] == 5
    assert d1["total_pages"] == 3
    assert len(d1["items"]) == 5
    assert d1["items"][0]["claim_text"] == "Claim number 14"

    # Page 2, page_size 5
    p2 = client.get("/api/verifications?page=2&page_size=5")
    assert p2.status_code == 200
    d2 = p2.json()
    assert d2["page"] == 2
    assert len(d2["items"]) == 5
    assert d2["items"][0]["claim_text"] == "Claim number 09"

    # Page 3, page_size 5
    p3 = client.get("/api/verifications?page=3&page_size=5")
    assert p3.status_code == 200
    d3 = p3.json()
    assert d3["page"] == 3
    assert len(d3["items"]) == 5
    assert d3["items"][4]["claim_text"] == "Claim number 00"


def test_9_page_0_is_rejected_422(client: TestClient) -> None:
    """9. page=0 is rejected with HTTP 422."""
    response = client.get("/api/verifications?page=0")
    assert response.status_code == 422


def test_10_page_size_0_is_rejected_422(client: TestClient) -> None:
    """10. page_size=0 is rejected with HTTP 422."""
    response = client.get("/api/verifications?page_size=0")
    assert response.status_code == 422


def test_11_page_size_above_100_is_rejected_422(client: TestClient) -> None:
    """11. page_size above 100 is rejected with HTTP 422."""
    response = client.get("/api/verifications?page_size=101")
    assert response.status_code == 422


def test_12_valid_verdict_filter_returns_matching_records(client: TestClient, isolated_db: Session) -> None:
    """12. A valid verdict filter returns matching records."""
    create_verification_record(
        isolated_db, claim_id="c1", claim_text="Claim A", verdict=Verdict.REFUTED.value,
        confidence=0.8, result_json={}
    )
    create_verification_record(
        isolated_db, claim_id="c2", claim_text="Claim B", verdict=Verdict.VERIFIED.value,
        confidence=0.9, result_json={}
    )
    create_verification_record(
        isolated_db, claim_id="c3", claim_text="Claim C", verdict=Verdict.REFUTED.value,
        confidence=0.75, result_json={}
    )

    # Filter for REFUTED
    resp = client.get("/api/verifications?verdict=REFUTED")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert all(item["verdict"] == "REFUTED" for item in data["items"])

    # Filter for VERIFIED
    resp_v = client.get("/api/verifications?verdict=VERIFIED")
    assert resp_v.status_code == 200
    assert resp_v.json()["total"] == 1
    assert resp_v.json()["items"][0]["claim_text"] == "Claim B"


def test_13_unsupported_verdict_filter_returns_422(client: TestClient) -> None:
    """13. An unsupported verdict filter returns HTTP 422."""
    response = client.get("/api/verifications?verdict=SOME_RANDOM_VERDICT")
    assert response.status_code == 422
    assert "Unsupported verdict filter" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Group 3: History Detail Tests (Cases 14-16)
# ---------------------------------------------------------------------------


def test_14_existing_record_returns_complete_stored_result(client: TestClient, isolated_db: Session) -> None:
    """14. An existing record returns the complete stored result."""
    record = create_verification_record(
        isolated_db,
        claim_id="claim_xyz",
        claim_text="Stored detailed claim.",
        verdict=Verdict.QUALIFIED.value,
        confidence=0.72,
        result_json={
            "claim_id": "claim_xyz",
            "claim_text": "Stored detailed claim.",
            "verdict": "QUALIFIED",
            "confidence": 0.72,
            "reasoning_trace": {"verdict": "QUALIFIED"},
        },
    )

    response = client.get(f"/api/verifications/{record.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == record.id
    assert data["claim_id"] == "claim_xyz"
    assert data["verdict"] == "QUALIFIED"
    assert data["confidence"] == 0.72
    assert data["reasoning_trace"]["verdict"] == "QUALIFIED"


def test_15_nonexistent_record_returns_404(client: TestClient) -> None:
    """15. A nonexistent record returns HTTP 404."""
    response = client.get("/api/verifications/999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_16_retrieving_history_does_not_rerun_engine(client: TestClient, isolated_db: Session) -> None:
    """16. Retrieving history does not rerun the engine."""
    record = create_verification_record(
        isolated_db,
        claim_id="claim_no_run",
        claim_text="Historical claim text.",
        verdict=Verdict.VERIFIED.value,
        confidence=0.88,
        result_json={"claim_text": "Historical claim text."},
    )

    mock_engine = MagicMock()
    app.state.engine = mock_engine

    response = client.get(f"/api/verifications/{record.id}")
    assert response.status_code == 200
    # verify() must NOT have been called
    mock_engine.verify.assert_not_called()


# ---------------------------------------------------------------------------
# Group 4: History Deletion Tests (Cases 17-19)
# ---------------------------------------------------------------------------


def test_17_deleting_existing_record_succeeds(client: TestClient, isolated_db: Session) -> None:
    """17. Deleting an existing record succeeds with HTTP 204."""
    record = create_verification_record(
        isolated_db,
        claim_id="claim_to_delete",
        claim_text="Claim to delete",
        verdict=Verdict.VERIFIED.value,
        confidence=0.8,
        result_json={},
    )
    rec_id = record.id

    response = client.delete(f"/api/verifications/{rec_id}")
    assert response.status_code == 204

    # Verify gone from DB
    assert get_verification_record(isolated_db, rec_id) is None


def test_18_deleting_nonexistent_record_returns_404(client: TestClient) -> None:
    """18. Deleting a nonexistent record returns HTTP 404."""
    response = client.delete("/api/verifications/999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_19_deleting_one_record_leaves_others_intact(client: TestClient, isolated_db: Session) -> None:
    """19. Deleting one record leaves other records intact."""
    r1 = create_verification_record(
        isolated_db, claim_id="c1", claim_text="Record 1", verdict=Verdict.VERIFIED.value,
        confidence=0.8, result_json={}
    )
    r2 = create_verification_record(
        isolated_db, claim_id="c2", claim_text="Record 2", verdict=Verdict.REFUTED.value,
        confidence=0.7, result_json={}
    )

    resp = client.delete(f"/api/verifications/{r1.id}")
    assert resp.status_code == 204

    # r1 is gone, r2 remains
    assert get_verification_record(isolated_db, r1.id) is None
    assert get_verification_record(isolated_db, r2.id) is not None


# ---------------------------------------------------------------------------
# Group 5: Compatibility Tests (Cases 20-23)
# ---------------------------------------------------------------------------


def test_20_existing_verify_response_fields_remain_compatible(client: TestClient) -> None:
    """20. Existing /api/verify response fields remain compatible."""
    response = client.post("/api/verify", json={"claim": TESLA_LIKE_CLAIM})
    assert response.status_code == 200
    data = response.json()

    # Core fields
    for field in [
        "id", "claim_id", "claim_text", "verdict", "confidence",
        "confidence_explanation", "confidence_breakdown", "claim",
        "hypotheses", "queries", "evidence", "assessments",
        "contradictions", "fusion", "reasoning_trace", "errors",
    ]:
        assert field in data, f"Missing field in response: {field}"


def test_21_existing_health_endpoints_still_work(client: TestClient) -> None:
    """21. Existing health endpoints still work."""
    for path in ["/health", "/api/health"]:
        resp = client.get(path)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


def test_22_existing_claim_validation_behavior_remains_unchanged(client: TestClient) -> None:
    """22. Existing claim validation behavior remains unchanged."""
    r_empty = client.post("/api/verify", json={"claim": ""})
    assert r_empty.status_code == 400
    assert "ClaimValidationError" in r_empty.json()["error_type"]

    r_ws = client.post("/api/verify", json={"claim": "    "})
    assert r_ws.status_code == 400
    assert "ClaimValidationError" in r_ws.json()["error_type"]

    r_long = client.post("/api/verify", json={"claim": "a" * 4001})
    assert r_long.status_code == 400
    assert "ClaimValidationError" in r_long.json()["error_type"]


# ---------------------------------------------------------------------------
# Alembic Migration Smoke Test
# ---------------------------------------------------------------------------


def test_alembic_upgrade_head_smoke(tmp_path: Path) -> None:
    """Verify that Alembic migrations run cleanly against a fresh SQLite database."""
    from alembic import command
    from alembic.config import Config

    test_db = tmp_path / "alembic_fresh.db"
    test_db_url = f"sqlite:///{test_db}"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", test_db_url)

    # Run upgrade head
    command.upgrade(alembic_cfg, "head")

    # Verify table and indexes created
    test_engine = create_engine(test_db_url)
    with test_engine.connect() as conn:
        from sqlalchemy import inspect
        inspector = inspect(conn)
        tables = inspector.get_table_names()
        assert "verification_records" in tables

        columns = [c["name"] for c in inspector.get_columns("verification_records")]
        for col in ["id", "claim_id", "claim_text", "verdict", "confidence", "created_at", "result_json"]:
            assert col in columns, f"Column {col} missing from migrated table"

        indexes = [idx["name"] for idx in inspector.get_indexes("verification_records")]
        assert "idx_verification_created_at_id" in indexes
    test_engine.dispose()
