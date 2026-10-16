"""SQLAlchemy database models for Falsify."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Float, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class VerificationRecord(Base):
    """Database record storing historical claim verifications and full reasoning traces."""

    __tablename__ = "verification_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(index=True, nullable=False, default=_utcnow)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        Index("idx_verification_created_at_id", "created_at", "id"),
    )

    def to_summary_dict(self) -> dict[str, Any]:
        """Return a lightweight dictionary suitable for paginated list responses."""
        created_dt = self.created_at
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=UTC)
        return {
            "id": self.id,
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "verdict": self.verdict,
            "confidence": round(self.confidence, 3),
            "created_at": created_dt,
        }
