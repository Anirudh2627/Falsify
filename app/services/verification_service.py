"""Verification service orchestrating synchronous FalsifyEngine execution in a threadpool."""

from __future__ import annotations

import logging
from typing import Any

import anyio
from sqlalchemy.orm import Session

from app.db.models import VerificationRecord
from app.db.repository import create_verification_record
from app.falsify.engine import FalsifyEngine
from app.falsify.models import VerificationResult

logger = logging.getLogger("falsify")


class VerificationService:
    """Service wrapping FalsifyEngine verification for asynchronous web execution."""

    def __init__(self, engine: FalsifyEngine) -> None:
        self._engine = engine

    @property
    def engine(self) -> FalsifyEngine:
        return self._engine

    async def verify_claim(self, claim: str) -> VerificationResult:
        """Run the full adversarial verification pipeline on a claim in a worker thread.

        Raises:
            ClaimValidationError: if input is invalid (empty, whitespace, or exceeding limit).

        Returns:
            VerificationResult: complete result preserving all original fields and trace.
        """
        logger.info(f"event=api_verification_started chars={len(claim)}")
        result = await anyio.to_thread.run_sync(self._engine.verify, claim)
        logger.info(
            f"event=api_verification_finished claim_id={result.claim_id} "
            f"verdict={result.verdict.value} confidence={result.confidence:.3f}"
        )
        return result

    async def verify_and_persist(
        self, claim: str, db: Session
    ) -> tuple[VerificationResult, VerificationRecord]:
        """Execute verification and persist the complete result record in the database.

        Raises:
            ClaimValidationError: if input is invalid (empty, whitespace, or exceeding limit).
            Exception: if database persistence fails (rolled back cleanly).
        """
        result = await self.verify_claim(claim)
        payload: dict[str, Any] = result.model_dump(mode="json")

        record = create_verification_record(
            db,
            claim_id=result.claim_id,
            claim_text=result.claim_text,
            verdict=result.verdict.value,
            confidence=result.confidence,
            result_json=payload,
            created_at=result.created_at,
        )
        return result, record
