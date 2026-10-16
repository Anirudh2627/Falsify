"""Tests verifying all 5 verdicts and full result serialization over the API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.falsify.models import (
    Claim,
    ConfidenceBreakdown,
    Contradiction,
    ContradictionTraceEntry,
    ContradictionType,
    Evidence,
    EvidenceAssessment,
    EvidenceTraceEntry,
    FalsificationHypothesis,
    FusionSummary,
    HypothesisCategory,
    HypothesisTraceEntry,
    PipelineError,
    QueryTraceEntry,
    QueryType,
    ReasoningTrace,
    SearchQuery,
    Severity,
    SourceTier,
    Verdict,
    VerificationResult,
)
from app.main import app


class DummyEngine:
    """Mock engine that returns a controlled VerificationResult with any verdict."""

    def __init__(self, verdict: Verdict, confidence: float = 0.85) -> None:
        self.verdict = verdict
        self.confidence = confidence

    def verify(self, claim_text: str) -> VerificationResult:
        claim = Claim(original_text=claim_text, normalized_text=claim_text)
        hyp = FalsificationHypothesis(
            claim_id=claim.claim_id,
            category=HypothesisCategory.NUMERICAL,
            hypothesis="The actual number is different.",
            rationale="Adversarial check.",
            falsification_target="numerical_value",
            priority=0.9,
        )
        qry = SearchQuery(
            hypothesis_id=hyp.hypothesis_id,
            claim_id=claim.claim_id,
            query="Company X actual figure",
            query_type=QueryType.PRIMARY_SOURCE,
        )
        ev = Evidence(
            source_url="https://www.example.com/source1",
            title="Authoritative Report",
            publisher="Primary Publisher",
            domain="example.com",
            retrieved_text="Evidence text reporting facts.",
            score=0.95,
        )
        assessment = EvidenceAssessment(
            evidence_id=ev.evidence_id,
            supports_claim=(self.verdict == Verdict.VERIFIED),
            contradicts_claim=(self.verdict == Verdict.REFUTED),
            relevance_score=0.9,
            source_quality_score=0.85,
            source_tier=SourceTier.TIER_1,
            temporal_validity=1.0,
            is_direct=True,
            reasoning="Direct match with primary filings.",
        )
        contradiction = Contradiction(
            claim_id=claim.claim_id,
            evidence_ids=[ev.evidence_id],
            contradiction_type=ContradictionType.NUMERICAL,
            severity=Severity.HIGH,
            explanation="Contradiction observed between claim and source.",
        )
        fusion = FusionSummary(
            supporting_evidence=1 if self.verdict == Verdict.VERIFIED else 0,
            contradicting_evidence=1 if self.verdict == Verdict.REFUTED else 0,
            total_evidence=1,
            independent_supporting_clusters=1 if self.verdict == Verdict.VERIFIED else 0,
            independent_contradicting_clusters=1 if self.verdict == Verdict.REFUTED else 0,
            support_strength=0.9 if self.verdict == Verdict.VERIFIED else 0.0,
            contradict_strength=0.9 if self.verdict == Verdict.REFUTED else 0.0,
            coverage=1.0,
        )
        trace = ReasoningTrace(
            claim=claim_text,
            normalized_claim=claim_text,
            hypotheses=[
                HypothesisTraceEntry(
                    hypothesis_id=hyp.hypothesis_id,
                    hypothesis=hyp.hypothesis,
                    category=hyp.category,
                    priority=hyp.priority,
                    tested=True,
                    outcome="falsified" if self.verdict == Verdict.REFUTED else "survived",
                )
            ],
            queries=[
                QueryTraceEntry(
                    query_id=qry.query_id,
                    query=qry.query,
                    hypothesis=hyp.hypothesis,
                    purpose=qry.rationale,
                    query_type=qry.query_type,
                    results_found=1,
                )
            ],
            evidence=[
                EvidenceTraceEntry(
                    evidence_id=ev.evidence_id,
                    url=ev.source_url,
                    title=ev.title,
                    publisher=ev.publisher,
                    source_tier=assessment.source_tier,
                    stance=assessment.stance,
                    relevance_score=assessment.relevance_score,
                    source_quality_score=assessment.source_quality_score,
                    temporal_validity=assessment.temporal_validity,
                    is_direct=assessment.is_direct,
                    reasoning=assessment.reasoning,
                )
            ],
            contradictions=[
                ContradictionTraceEntry(
                    contradiction_id=contradiction.contradiction_id,
                    type=contradiction.contradiction_type,
                    severity=contradiction.severity,
                    explanation=contradiction.explanation,
                    evidence_urls=[ev.source_url],
                )
            ],
            fusion=fusion,
            verdict=self.verdict,
            confidence=self.confidence,
            confidence_explanation=f"Confidence {self.confidence:.2f} in verdict {self.verdict.value}.",
            reasoning=f"Reasoning summary for verdict {self.verdict.value}.",
            errors=[],
            stage_timings_ms={"normalization": 5, "retrieval": 20, "verdict": 2},
        )

        return VerificationResult(
            claim_id=claim.claim_id,
            claim_text=claim_text,
            verdict=self.verdict,
            confidence=self.confidence,
            confidence_explanation=trace.confidence_explanation,
            confidence_breakdown=ConfidenceBreakdown(
                evidence_quality=0.85,
                evidence_relevance=0.9,
                source_independence=1.0,
                cross_source_agreement=0.9,
                contradiction_strength=0.8,
                temporal_validity=1.0,
                retrieval_coverage=1.0,
                decisiveness_margin=0.5,
                weighted_total=self.confidence,
            ),
            claim=claim,
            hypotheses=[hyp],
            queries=[qry],
            evidence=[ev],
            assessments=[assessment],
            contradictions=[contradiction],
            fusion=fusion,
            reasoning_trace=trace,
            errors=[],
            engine_version="1.0.0",
            llm_used=False,
            retrieval_provider="in_memory",
        )


@pytest.mark.parametrize(
    "expected_verdict",
    [
        Verdict.VERIFIED,
        Verdict.QUALIFIED,
        Verdict.CONFLICTED,
        Verdict.REFUTED,
        Verdict.UNVERIFIABLE,
    ],
)
def test_all_five_verdicts_preserved_and_serialized(expected_verdict: Verdict) -> None:
    """Verify that all five Verdict enum values are faithfully preserved across the API."""
    dummy_engine = DummyEngine(verdict=expected_verdict, confidence=0.82)
    app.state.engine = dummy_engine

    with TestClient(app) as client:
        response = client.post("/api/verify", json={"claim": "Test claim statement."})
        assert response.status_code == 200
        data = response.json()

        # The verdict must match exactly as a string
        assert data["verdict"] == expected_verdict.value
        assert data["reasoning_trace"]["verdict"] == expected_verdict.value
        assert data["confidence"] == 0.82

        # Verify all mandatory top-level fields are present
        required_fields = [
            "claim_id",
            "claim_text",
            "verdict",
            "confidence",
            "confidence_explanation",
            "confidence_breakdown",
            "claim",
            "hypotheses",
            "queries",
            "evidence",
            "assessments",
            "contradictions",
            "fusion",
            "reasoning_trace",
            "errors",
            "created_at",
            "engine_version",
            "llm_used",
            "retrieval_provider",
        ]
        for field in required_fields:
            assert field in data, f"Missing expected field: {field}"
