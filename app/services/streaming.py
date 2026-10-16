"""Server-Sent Events (SSE) streaming service for real-time verification progress."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any

import anyio
from sqlalchemy.orm import Session

from app.db.models import VerificationRecord
from app.db.repository import create_verification_record
from app.db.session import get_session_factory
from app.falsify.engine import FalsifyEngine
from app.falsify.logging_utils import LOGGER_NAME
from app.falsify.models import VerificationResult

logger = logging.getLogger("falsify")

# Regex to parse structured log events: event=<name>
_EVENT_PATTERN = re.compile(r"event=([a-zA-Z0-9_]+)")

# Map engine log events to truthful progress stages
_STAGE_MAP: dict[str, tuple[str, str, float]] = {
    "claim_normalization_started": ("normalization", "Normalizing claim and extracting constraints", 0.10),
    "claim_normalized": ("normalization", "Claim normalized successfully", 0.15),
    "hypotheses_generated": ("hypotheses", "Generating falsification hypotheses", 0.25),
    "queries_generated": ("query_generation", "Generating adversarial search queries", 0.35),
    "evidence_retrieved": ("retrieval", "Retrieving evidence from external sources", 0.50),
    "evidence_assessed": ("assessment", "Assessing evidence relevance and credibility", 0.65),
    "contradictions_detected": ("contradiction_detection", "Evaluating potential contradictions", 0.75),
    "evidence_fused": ("fusion", "Clustering sources and collapsing duplicates", 0.85),
    "verdict_generated": ("verdict", "Determining verification verdict", 0.92),
    "confidence_computed": ("confidence", "Computing multi-factor confidence score", 0.95),
    "verification_complete": ("synthesis", "Synthesizing reasoning trace", 0.97),
}


def format_sse(event: str, data: dict[str, Any], event_id: str | None = None) -> str:
    """Format a named SSE frame with JSON payload and standard framing."""
    lines: list[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, default=str)}")
    lines.append("\n")  # Trailing newline produces double newline separator
    return "\n".join(lines)


class LogProgressCaptureHandler(logging.Handler):
    """Logging handler that captures engine log events and queues truthful progress updates."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue[tuple[str, str, float]],
    ) -> None:
        super().__init__()
        self.loop = loop
        self.queue = queue
        self.seen_events: set[str] = set()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            match = _EVENT_PATTERN.search(msg)
            if not match:
                return
            event_name = match.group(1)
            if event_name in _STAGE_MAP and event_name not in self.seen_events:
                self.seen_events.add(event_name)
                stage_info = _STAGE_MAP[event_name]
                if self.loop.is_running():
                    self.loop.call_soon_threadsafe(self.queue.put_nowait, stage_info)
        except Exception:
            self.handleError(record)


async def stream_verification(
    claim: str,
    engine: FalsifyEngine,
    db: Session | None = None,
) -> AsyncGenerator[str, None]:
    """Execute verification in a threadpool and yield real-time SSE progress events.

    Protocol events:
    - verification_started: claim accepted, verification initialized
    - verification_progress: truthful stage updates from the engine
    - verification_completed: persisted record ID and full serialized result
    - verification_error: safe error message if verification or persistence fails
    """
    event_counter = 0

    def next_id() -> str:
        nonlocal event_counter
        event_counter += 1
        return str(event_counter)

    # 1. Started event
    yield format_sse(
        "verification_started",
        {"message": "Verification started", "claim": claim},
        event_id=next_id(),
    )

    loop = asyncio.get_running_loop()
    progress_queue: asyncio.Queue[tuple[str, str, float]] = asyncio.Queue()
    handler = LogProgressCaptureHandler(loop, progress_queue)

    falsify_logger = logging.getLogger(LOGGER_NAME)
    falsify_logger.addHandler(handler)

    engine_task = asyncio.create_task(anyio.to_thread.run_sync(engine.verify, claim))

    # Manage DB session lifecycle safely
    owns_session = False
    session: Session
    if db is not None:
        session = db
    else:
        session = get_session_factory()()
        owns_session = True

    try:
        # 2. Progress loop while engine executes in worker thread
        progress_sent = False
        while not engine_task.done():
            try:
                stage, message, progress = await asyncio.wait_for(progress_queue.get(), timeout=0.08)
                yield format_sse(
                    "verification_progress",
                    {"stage": stage, "message": message, "progress": progress},
                    event_id=next_id(),
                )
                progress_sent = True
            except TimeoutError:
                pass

        # Drain any remaining progress events captured right before completion
        while not progress_queue.empty():
            stage, message, progress = progress_queue.get_nowait()
            yield format_sse(
                "verification_progress",
                {"stage": stage, "message": message, "progress": progress},
                event_id=next_id(),
            )
            progress_sent = True

        # Fallback truthful progress if test doubles did not emit log events
        if not progress_sent:
            yield format_sse(
                "verification_progress",
                {"stage": "running", "message": "Verification in progress", "progress": 0.50},
                event_id=next_id(),
            )

        # 3. Retrieve engine result
        try:
            result: VerificationResult = await engine_task
        except Exception as exc:
            from app.falsify.exceptions import ClaimValidationError
            err_code = "ClaimValidationError" if isinstance(exc, ClaimValidationError) else type(exc).__name__
            yield format_sse(
                "verification_error",
                {"code": err_code, "message": str(exc)},
                event_id=next_id(),
            )
            return

        # 4. Progress: result being persisted
        yield format_sse(
            "verification_progress",
            {"stage": "persisting", "message": "Persisting verification record", "progress": 0.98},
            event_id=next_id(),
        )

        # 5. Persist result
        payload = result.model_dump(mode="json")
        try:
            record: VerificationRecord = create_verification_record(
                session,
                claim_id=result.claim_id,
                claim_text=result.claim_text,
                verdict=result.verdict.value,
                confidence=result.confidence,
                result_json=payload,
                created_at=result.created_at,
            )
        except Exception as exc:
            logger.error(f"event=stream_persistence_failed error={str(exc)[:160]}")
            yield format_sse(
                "verification_error",
                {"code": "DatabaseError", "message": "Failed to persist verification record"},
                event_id=next_id(),
            )
            return

        # 6. Completed event with persisted record ID and full serialized result
        payload["id"] = record.id
        yield format_sse(
            "verification_completed",
            {
                "verification_id": record.id,
                "verdict": result.verdict.value,
                "confidence": result.confidence,
                "result": payload,
            },
            event_id=next_id(),
        )

    except asyncio.CancelledError:
        logger.info("event=stream_client_disconnected")
        raise
    finally:
        falsify_logger.removeHandler(handler)
        if owns_session:
            session.close()
