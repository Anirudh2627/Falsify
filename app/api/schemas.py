"""Pydantic request and response schemas for Falsify API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.falsify.exceptions import ClaimValidationError


class VerificationRequest(BaseModel):
    """Payload for submitting a claim for adversarial verification."""

    claim: str = Field(
        ...,
        description="The claim to verify adversarially (max 4,000 characters).",
        examples=["Company X grew revenue by 40% in 2025."],
    )

    @field_validator("claim")
    @classmethod
    def validate_claim_text(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ClaimValidationError(f"Claim text must be a string, got {type(v).__name__}")
        if not v.strip():
            raise ClaimValidationError("Claim text is empty")
        if len(v.strip()) > 4000:
            raise ClaimValidationError(f"Claim too long ({len(v.strip())} chars > 4000)")
        return v


class HealthResponse(BaseModel):
    """Health status and provider configuration report."""

    status: str = "ok"
    app_name: str
    app_version: str
    engine_version: str
    retrieval_provider: str
    llm_configured: bool
    database_status: str = "connected"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ErrorResponse(BaseModel):
    """Standardized API error response format."""

    detail: str
    error_type: str = "FalsifyError"
    extra: dict[str, Any] | None = None


class VerificationHistoryItem(BaseModel):
    """Summary item for a historical verification in list views."""

    id: int
    claim_id: str | None = None
    claim_text: str
    verdict: str
    confidence: float
    created_at: datetime


class PaginatedVerificationHistory(BaseModel):
    """Paginated list of verification history items."""

    items: list[VerificationHistoryItem]
    total: int
    page: int
    page_size: int
    total_pages: int
