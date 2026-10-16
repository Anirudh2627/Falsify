"""Repository for CRUD operations on VerificationRecord."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import VerificationRecord

logger = logging.getLogger("falsify")


def create_verification_record(
    db: Session,
    *,
    claim_id: str | None,
    claim_text: str,
    verdict: str,
    confidence: float,
    result_json: dict[str, Any],
    created_at: datetime | None = None,
) -> VerificationRecord:
    """Create and persist a new verification record."""
    record = VerificationRecord(
        claim_id=claim_id,
        claim_text=claim_text,
        verdict=verdict,
        confidence=confidence,
        result_json=result_json,
        created_at=created_at or datetime.now(UTC),
    )
    db.add(record)
    try:
        db.commit()
        db.refresh(record)
        logger.info(f"event=db_record_created id={record.id} claim_id={record.claim_id}")
        return record
    except Exception as exc:
        db.rollback()
        logger.error(f"event=db_record_create_failed error={str(exc)[:160]}")
        raise


def get_verification_record(db: Session, record_id: int) -> VerificationRecord | None:
    """Fetch a verification record by primary key."""
    stmt = select(VerificationRecord).where(VerificationRecord.id == record_id)
    return db.scalars(stmt).first()


def list_verification_records(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 10,
    verdict: str | None = None,
) -> tuple[list[VerificationRecord], int]:
    """Return paginated verification records ordered newest first, plus total count."""
    base_query = select(VerificationRecord)
    count_query = select(func.count()).select_from(VerificationRecord)

    if verdict is not None:
        base_query = base_query.where(VerificationRecord.verdict == verdict)
        count_query = count_query.where(VerificationRecord.verdict == verdict)

    total = db.scalar(count_query) or 0

    offset = (page - 1) * page_size
    stmt = (
        base_query
        .order_by(VerificationRecord.created_at.desc(), VerificationRecord.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    records = list(db.scalars(stmt).all())
    return records, total


def delete_verification_record(db: Session, record_id: int) -> bool:
    """Delete a verification record by primary key. Returns True if deleted, False if not found."""
    record = get_verification_record(db, record_id)
    if record is None:
        return False
    try:
        db.delete(record)
        db.commit()
        logger.info(f"event=db_record_deleted id={record_id}")
        return True
    except Exception as exc:
        db.rollback()
        logger.error(f"event=db_record_delete_failed id={record_id} error={str(exc)[:160]}")
        raise
