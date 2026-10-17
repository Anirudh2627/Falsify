"""Test verifying that synchronous verification executes in a threadpool without blocking the event loop."""

from __future__ import annotations

import asyncio
import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.falsify.models import (
    Claim,
    ConfidenceBreakdown,
    FusionSummary,
    ReasoningTrace,
    Verdict,
    VerificationResult,
)
from app.main import app


class SlowEngine:
    """Engine that blocks synchronously for a defined duration to test threadpool execution."""

    def __init__(self, delay_s: float = 0.3) -> None:
        self.delay_s = delay_s

    def verify(self, claim_text: str) -> VerificationResult:
        # Deliberate synchronous sleep to verify worker thread execution
        time.sleep(self.delay_s)
        claim = Claim(original_text=claim_text, normalized_text=claim_text)
        return VerificationResult(
            claim_id=claim.claim_id,
            claim_text=claim_text,
            verdict=Verdict.VERIFIED,
            confidence=0.9,
            confidence_explanation="Verified after simulated retrieval.",
            confidence_breakdown=ConfidenceBreakdown(),
            claim=claim,
            hypotheses=[],
            queries=[],
            evidence=[],
            assessments=[],
            contradictions=[],
            fusion=FusionSummary(),
            reasoning_trace=ReasoningTrace(verdict=Verdict.VERIFIED, confidence=0.9),
            errors=[],
            engine_version="1.0.0",
        )


@pytest.mark.anyio
async def test_verify_does_not_block_event_loop() -> None:
    """Verify that a slow synchronous verify() does not starve concurrent async requests."""
    slow_engine = SlowEngine(delay_s=0.4)
    app.state.engine = slow_engine

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        t0 = time.perf_counter()

        # Launch the slow verification
        verify_task = asyncio.create_task(
            client.post("/api/verify", json={"claim": "Concurrency test claim."})
        )

        # Give verify_task a moment to enter the threadpool
        await asyncio.sleep(0.05)

        # Concurrently request /health - must return immediately because event loop is free
        health_t0 = time.perf_counter()
        health_resp = await client.get("/health")
        health_duration = time.perf_counter() - health_t0

        assert health_resp.status_code == 200
        # Health should respond in under 100ms, well before the 400ms verify task finishes
        assert health_duration < 0.25, f"Health check took too long ({health_duration:.3f}s), event loop was blocked!"

        # Await the slow verification task
        verify_resp = await verify_task
        total_duration = time.perf_counter() - t0

        assert verify_resp.status_code == 200
        assert verify_resp.json()["verdict"] == Verdict.VERIFIED.value
        assert total_duration >= 0.35, f"Verify completed suspiciously fast ({total_duration:.3f}s)"
