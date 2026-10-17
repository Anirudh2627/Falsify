"""Tests for Phase 6 deployment readiness, production configuration, and operational behavior."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import AppConfig, get_app_config
from app.db.models import VerificationRecord
from app.db.repository import create_verification_record, get_verification_record
from app.db.session import dispose_engine, ensure_sqlite_parent_dir, get_engine, get_session_factory, set_custom_engine
from app.main import create_app
from tests.conftest import make_engine


@pytest.fixture
def clean_engine_fixture():
    """Ensure engine is cleanly disposed before and after test."""
    dispose_engine()
    yield
    dispose_engine()


def test_health_and_readiness_endpoints(clean_engine_fixture):
    """Verify /health and /ready endpoints behave according to production contracts."""
    app = create_app()
    app.state.engine = make_engine()

    with TestClient(app) as client:
        # Liveness check
        for path in ["/health", "/api/health"]:
            res = client.get(path)
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "ok"
            assert data["database_status"] == "connected"
            # Ensure no credentials leaked
            assert "api_key" not in data
            assert "database_url" not in data

        # Readiness check
        for path in ["/ready", "/api/ready"]:
            res = client.get(path)
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "ready"
            assert data["database"] == "connected"
            assert "timestamp" in data


def test_readiness_failure_reporting(clean_engine_fixture):
    """Verify readiness returns 503 if database check fails without leaking exception traces."""
    app = create_app()
    app.state.engine = make_engine()

    with patch("app.api.routes_system.get_session_factory", side_effect=RuntimeError("DB connection dead")):
        with TestClient(app) as client:
            res = client.get("/ready")
            assert res.status_code == 503
            data = res.json()
            assert data["status"] == "unready"
            assert data["database"] == "disconnected"
            # Sensitive internal error string must not be leaked to clients
            assert "DB connection dead" not in str(data)


def test_payload_size_limiter(clean_engine_fixture):
    """Verify payload size limiter rejects oversized payloads with 413."""
    app = create_app()
    app.state.engine = make_engine()

    with TestClient(app) as client:
        # Request with oversized content-length header
        res = client.post(
            "/api/verify",
            headers={"Content-Length": "2000000"},  # 2MB > default 1MB
            json={"claim": "Test claim"},
        )
        assert res.status_code == 413
        data = res.json()
        assert data["error_type"] == "PayloadTooLarge"
        assert "Request payload too large" in data["detail"]


def test_generic_exception_handler_sanitizes_500(clean_engine_fixture):
    """Verify unhandled 500 exceptions in production mode do not leak stack traces."""
    app = create_app()
    app.state.engine = make_engine()

    with patch("app.api.routes_system.get_app_config", side_effect=RuntimeError("SecretDatabasePassword123 at /var/internal/path")):
        with TestClient(app, raise_server_exceptions=False) as client:
            res = client.get("/health")
            assert res.status_code == 500
            data = res.json()
            assert data["error_type"] == "InternalServerError"
            assert data["detail"] == "An internal server error occurred."
            # Secrets and paths must not appear in response
            assert "SecretDatabasePassword123" not in str(data)
            assert "traceback" not in data


def test_sqlite_parent_dir_auto_creation(tmp_path):
    """Verify ensure_sqlite_parent_dir creates nested directories automatically."""
    nested_dir = tmp_path / "deeply" / "nested" / "dir"
    db_file = nested_dir / "test_created.db"
    assert not nested_dir.exists()

    db_url = f"sqlite:///{db_file.as_posix()}"
    ensure_sqlite_parent_dir(db_url)

    assert nested_dir.exists()
    assert nested_dir.is_dir()


def test_database_persistence_across_restart(tmp_path):
    """Verify records survive engine disposal and restart on persistent storage."""
    db_file = tmp_path / "persistent_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    with patch.dict(os.environ, {"DATABASE_URL": db_url}):
        # Step 1: Initialize first engine and create record
        dispose_engine()
        get_app_config.cache_clear()
        config1 = get_app_config()
        assert config1.database_url == db_url

        # Initialize schema via Base.metadata.create_all (or alembic) on the fresh test database
        from app.db.base import Base
        Base.metadata.create_all(bind=get_engine())

        factory1 = get_session_factory()
        with factory1() as session:
            rec = create_verification_record(
                session,
                claim_id="persisted_claim_1",
                claim_text="The Earth orbits the Sun.",
                verdict="VERIFIED",
                confidence=0.99,
                result_json={"verdict": "VERIFIED", "confidence": 0.99},
            )
            saved_id = rec.id
            assert saved_id is not None

        # Step 2: Simulate complete application shutdown and restart
        dispose_engine()
        get_app_config.cache_clear()

        # Step 3: Initialize second engine pointing to same storage
        config2 = get_app_config()
        assert config2.database_url == db_url
        factory2 = get_session_factory()
        with factory2() as session:
            loaded_rec = get_verification_record(session, saved_id)
            assert loaded_rec is not None
            assert loaded_rec.claim_id == "persisted_claim_1"
            assert loaded_rec.verdict == "VERIFIED"
            assert loaded_rec.confidence == 0.99

        dispose_engine()
        get_app_config.cache_clear()


def test_rate_limiting_enforced(clean_engine_fixture):
    """Verify rate limiter blocks requests exceeding configured rate_limit_per_minute with HTTP 429."""
    with patch.dict(os.environ, {"RATE_LIMIT_PER_MINUTE": "2"}):
        get_app_config.cache_clear()
        app = create_app()
        app.state.engine = make_engine()

        with TestClient(app) as client:
            # First 2 requests succeed
            r1 = client.get("/api/verifications")
            assert r1.status_code == 200

            r2 = client.get("/api/verifications")
            assert r2.status_code == 200

            # 3rd request exceeds limit -> 429
            r3 = client.get("/api/verifications")
            assert r3.status_code == 429
            data = r3.json()
            assert data["error_type"] == "RateLimitExceeded"
            assert "Rate limit exceeded" in data["detail"]
            assert "Retry-After" in r3.headers

            # Health/ready probes should be exempt from rate limiting
            r_health = client.get("/health")
            assert r_health.status_code == 200

        get_app_config.cache_clear()


def test_config_validation_and_reproducibility():
    """Verify configuration validation catches invalid operational settings."""
    # Invalid port (< 1 or > 65535)
    with pytest.raises(Exception):
        AppConfig(port=99999)

    with pytest.raises(Exception):
        AppConfig(port=-1)

    # Invalid max_request_size_bytes (<= 0)
    with pytest.raises(Exception):
        AppConfig(max_request_size_bytes=0)


def test_spa_static_files_serving(clean_engine_fixture):
    """Verify static assets and SPA fallback are served properly if dist exists."""
    app = create_app()
    with TestClient(app) as client:
        # Check if root / serves index.html (compiled frontend dist)
        res = client.get("/")
        if res.status_code == 200:
            assert "text/html" in res.headers.get("content-type", "")
            # Nested client-side route should also serve index.html
            nested_res = client.get("/history")
            assert nested_res.status_code == 200
            assert "text/html" in nested_res.headers.get("content-type", "")

        # Reserved API route 404 should NOT return index.html
        api_404 = client.get("/api/unknown-endpoint")
        assert api_404.status_code == 404
        assert api_404.headers.get("content-type", "").startswith("application/json")
