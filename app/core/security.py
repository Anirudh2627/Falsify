"""Security, authentication, and request sanitization utilities for Falsify API."""

from __future__ import annotations

import hmac
import logging
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_app_config

logger = logging.getLogger("falsify.security")

# Optional HTTP Bearer security scheme
_bearer_scheme = HTTPBearer(auto_error=False)


def get_client_ip(request: Request) -> str:
    """Extract client IP address, respecting reverse proxies and forwarded headers."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Take the leftmost IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


async def verify_api_key(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
) -> bool:
    """FastAPI dependency verifying API key if configured in application settings.

    If no API key is configured (default development mode), access is granted automatically.
    If an API key is configured, client must supply it via `X-API-Key` header or `Authorization: Bearer <token>`.
    """
    config = get_app_config()
    required_key = getattr(config, "api_key", None)

    # If no API key requirement is enforced in config, allow access
    if not required_key:
        return True

    provided_key: str | None = None
    if x_api_key:
        provided_key = x_api_key.strip()
    elif bearer and bearer.credentials:
        provided_key = bearer.credentials.strip()

    if not provided_key or not hmac.compare_digest(provided_key, required_key):
        client_ip = get_client_ip(request)
        logger.warning(f"event=api_key_unauthorized client_ip={client_ip} path={request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Provide via 'X-API-Key' header or 'Bearer' token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True


def sanitize_claim_text(text: str, max_chars: int = 4000) -> str:
    """Sanitize and validate claim input text prior to ingestion into the engine.

    - Strips leading and trailing whitespace
    - Removes ASCII null bytes and non-printable control characters
    - Validates length boundaries
    """
    if not text or not text.strip():
        raise ValueError("Claim text cannot be empty or whitespace-only.")

    # Remove null bytes and non-newline control characters
    cleaned = "".join(ch for ch in text if ch in ("\n", "\r", "\t") or ord(ch) >= 32)
    cleaned = cleaned.strip()

    if not cleaned:
        raise ValueError("Claim text contains only non-printable control characters.")

    if len(cleaned) > max_chars:
        raise ValueError(f"Claim exceeds maximum allowed length of {max_chars} characters ({len(cleaned)} chars).")

    return cleaned
