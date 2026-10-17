"""Unit tests for app.core.security module."""

import pytest
from fastapi import HTTPException, Request
from starlette.datastructures import Headers

from app.core.config import AppConfig, get_app_config
from app.core.security import get_client_ip, sanitize_claim_text, verify_api_key


def test_sanitize_claim_text_valid():
    text = "  Company X grew revenue by 40% in 2025.  \n"
    cleaned = sanitize_claim_text(text)
    assert cleaned == "Company X grew revenue by 40% in 2025."


def test_sanitize_claim_text_strips_null_bytes():
    text = "Claim text\x00with null\x01bytes."
    cleaned = sanitize_claim_text(text)
    assert cleaned == "Claim textwith nullbytes."


def test_sanitize_claim_text_empty():
    with pytest.raises(ValueError, match="empty or whitespace-only"):
        sanitize_claim_text("   \n\t  ")


def test_sanitize_claim_text_exceeds_max():
    with pytest.raises(ValueError, match="exceeds maximum allowed length"):
        sanitize_claim_text("a" * 4001, max_chars=4000)


def test_get_client_ip():
    class DummyRequest:
        headers = Headers({"x-forwarded-for": "203.0.113.195, 70.41.3.18"})
        client = None

    ip = get_client_ip(DummyRequest())
    assert ip == "203.0.113.195"


def test_verify_api_key_when_not_required():
    import anyio

    class DummyRequest:
        headers = Headers({})
        url = type("URL", (), {"path": "/api/verify"})()

    # Default config has api_key=None
    result = anyio.run(verify_api_key, DummyRequest())
    assert result is True

