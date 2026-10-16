"""Adversarial verification and history endpoints."""

from __future__ import annotations

import math
from datetime import UTC
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_engine, get_verification_service
from app.api.schemas import (
    PaginatedVerificationHistory,
    VerificationHistoryItem,
    VerificationRequest,
)
from app.db.repository import (
    delete_verification_record,
    get_verification_record,
    list_verification_records,
)
from app.db.session import get_db
from app.falsify.engine import FalsifyEngine
from app.falsify.models import Verdict
from app.services.streaming import stream_verification
from app.services.verification_service import VerificationService

router = APIRouter(prefix="/api", tags=["verification"])

# Valid verdict filter values
_VALID_VERDICTS = {v.value for v in Verdict}


@router.post("/verify", summary="Verify a claim adversarially and persist history")
async def verify_claim(
    request: VerificationRequest,
    service: VerificationService = Depends(get_verification_service),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Run claim-level adversarial verification and persist results in SQLite.

    Executes normalization, falsification hypothesis generation, adversarial query
    generation, evidence retrieval, contradiction detection, source clustering,
    verdict determination, confidence computation, and reasoning trace synthesis.

    Returns the complete JSON result payload preserving all original fields,
    verdict, confidence breakdown, reasoning trace, and error semantics, enriched with
    the database record ID.
    """
    try:
        result, record = await service.verify_and_persist(request.claim, db)
    except Exception as exc:
        # If the failure is not an expected ClaimValidationError, log and return safe 500
        # without leaking database credentials or internal stack traces
        from app.falsify.exceptions import ClaimValidationError
        if isinstance(exc, ClaimValidationError):
            raise
        import logging
        logging.getLogger("falsify").error(f"event=verify_persistence_failed error={str(exc)[:160]}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to persist verification record", "error_type": "DatabaseError"},
        )

    payload: dict[str, Any] = result.model_dump(mode="json")
    payload["id"] = record.id
    return JSONResponse(content=payload, status_code=200)


@router.post("/verify/stream", summary="Verify a claim adversarially with real-time SSE progress streaming")
async def verify_claim_stream(
    request: VerificationRequest,
    engine: FalsifyEngine = Depends(get_engine),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Run claim-level adversarial verification with real-time Server-Sent Events (SSE).

    Emits named events:
    - verification_started: claim accepted, verification initialized
    - verification_progress: truthful stage updates from the engine
    - verification_completed: persisted record ID and full serialized result
    - verification_error: safe error message if verification or persistence fails
    """
    generator = stream_verification(request.claim, engine=engine, db=db)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/verifications",
    response_model=PaginatedVerificationHistory,
    summary="List paginated verification history",
)
def list_verifications(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=10, ge=1, le=100, description="Items per page"),
    verdict: str | None = Query(default=None, description="Optional verdict filter"),
    db: Session = Depends(get_db),
) -> PaginatedVerificationHistory:
    """Return paginated verification history ordered newest first."""
    if verdict is not None and verdict not in _VALID_VERDICTS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported verdict filter: '{verdict}'. Supported values: {sorted(_VALID_VERDICTS)}",
        )

    records, total = list_verification_records(db, page=page, page_size=page_size, verdict=verdict)
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    items = [
        VerificationHistoryItem(
            id=rec.id,
            claim_id=rec.claim_id,
            claim_text=rec.claim_text,
            verdict=rec.verdict,
            confidence=round(rec.confidence, 3),
            created_at=rec.created_at if rec.created_at.tzinfo else rec.created_at.replace(tzinfo=UTC),
        )
        for rec in records
    ]

    return PaginatedVerificationHistory(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/verifications/{id}",
    summary="Retrieve complete stored verification result",
)
def get_verification(
    id: int,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Return the complete stored verification result without re-executing verification."""
    record = get_verification_record(db, record_id=id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Verification record with ID {id} not found",
        )

    payload = dict(record.result_json)
    payload["id"] = record.id
    return JSONResponse(content=payload, status_code=200)


@router.delete(
    "/verifications/{id}",
    status_code=204,
    summary="Delete a stored verification record",
)
def delete_verification(
    id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a single stored history record by ID."""
    deleted = delete_verification_record(db, record_id=id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Verification record with ID {id} not found",
        )
    return Response(status_code=204)
