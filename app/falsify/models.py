"""Core data contract for the Falsify verification pipeline.

Every stage of the pipeline (normalization -> hypotheses -> queries ->
retrieval -> analysis -> contradiction detection -> fusion -> verdict)
communicates through these strongly-typed Pydantic models.  The final
:class:`VerificationResult` is fully JSON-serializable so the API layer can
return it directly to the frontend.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Verdict(str, Enum):
    """Final determination for a claim.

    Falsify deliberately refuses to collapse everything into true/false.
    """

    VERIFIED = "VERIFIED"
    QUALIFIED = "QUALIFIED"
    CONFLICTED = "CONFLICTED"
    REFUTED = "REFUTED"
    UNVERIFIABLE = "UNVERIFIABLE"


class HypothesisCategory(str, Enum):
    NUMERICAL = "numerical"
    TEMPORAL = "temporal"
    ENTITY = "entity"
    CAUSAL = "causal"
    DEFINITIONAL = "definitional"
    ATTRIBUTION = "attribution"
    SOURCE = "source"
    SCOPE = "scope"


class QueryType(str, Enum):
    PRIMARY_SOURCE = "primary_source"
    CONTRADICTION = "contradiction"
    ALTERNATIVE_INTERPRETATION = "alternative_interpretation"
    RECENCY = "recency"
    INDEPENDENT_REPORTING = "independent_reporting"
    GENERAL = "general"


class ContradictionType(str, Enum):
    NUMERICAL = "numerical"
    TEMPORAL = "temporal"
    ENTITY = "entity"
    DEFINITIONAL = "definitional"
    CAUSAL = "causal"
    SCOPE = "scope"
    ATTRIBUTION = "attribution"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


SEVERITY_WEIGHT: dict[Severity, float] = {
    Severity.LOW: 0.25,
    Severity.MEDIUM: 0.5,
    Severity.HIGH: 0.8,
    Severity.CRITICAL: 1.0,
}


class ClaimKind(str, Enum):
    """Coarse classification of what kind of assertion a claim makes."""

    QUANTITATIVE_CHANGE = "quantitative_change"  # "revenue increased by 20%"
    QUANTITATIVE_STATE = "quantitative_state"  # "revenue was $90B"
    COMPARATIVE = "comparative"  # "A is larger than B"
    CAUSAL = "causal"  # "X causes Y"
    FACTUAL = "factual"  # "The Earth orbits the Sun"
    FUTURE = "future"  # "X will happen in 2030"
    ATTRIBUTION = "attribution"  # "X said Y"
    UNKNOWN = "unknown"


class SourceTier(int, Enum):
    TIER_1 = 1  # primary / authoritative
    TIER_2 = 2  # reputable secondary
    TIER_3 = 3  # blogs, aggregators, forums, social
    UNKNOWN = 0


# ---------------------------------------------------------------------------
# Claim normalization
# ---------------------------------------------------------------------------


class QuantitativeConstraint(BaseModel):
    """A numeric assertion extracted from the claim text."""

    metric: str | None = Field(default=None, description="What is measured, e.g. 'revenue'.")
    raw_value: str = Field(description="The literal value as written, e.g. '20%'.")
    value: float | None = Field(default=None, description="Parsed numeric value.")
    unit: str | None = Field(default=None, description="'percent', 'USD', 'EUR', ...")
    direction: str | None = Field(
        default=None, description="'increased' | 'decreased' | None (static value)."
    )
    comparator: str | None = Field(
        default=None, description="'exactly', 'at least', 'more than', 'approximately', ..."
    )
    comparison_baseline: str | None = Field(
        default=None, description="What the value is compared against, e.g. '2024'."
    )
    implied_precision: float | None = Field(
        default=None,
        description="Rounding implied by how the value was written, e.g. 0.5 for '20%'.",
    )

    @property
    def is_percentage(self) -> bool:
        return (self.unit or "").lower() == "percent"


class Claim(BaseModel):
    """Normalized representation of a claim. Always preserves the original text."""

    claim_id: str = Field(default_factory=lambda: _new_id("claim"))
    original_text: str
    normalized_text: str = ""
    claim_kind: ClaimKind = ClaimKind.UNKNOWN
    entities: list[str] = Field(default_factory=list)
    predicates: list[str] = Field(default_factory=list)
    temporal_constraints: list[str] = Field(default_factory=list)
    geographic_constraints: list[str] = Field(default_factory=list)
    quantitative_constraints: list[QuantitativeConstraint] = Field(default_factory=list)
    negated: bool = False
    is_future_claim: bool = False
    assertions: list[str] = Field(
        default_factory=list, description="Individual assertions when a claim contains several."
    )
    normalization_source: str = Field(
        default="deterministic", description="'deterministic' | 'llm' | 'hybrid'"
    )
    normalization_warnings: list[str] = Field(default_factory=list)

    @property
    def primary_entity(self) -> str | None:
        return self.entities[0] if self.entities else None

    @property
    def primary_quantity(self) -> QuantitativeConstraint | None:
        return self.quantitative_constraints[0] if self.quantitative_constraints else None


# ---------------------------------------------------------------------------
# Falsification hypotheses
# ---------------------------------------------------------------------------


class FalsificationHypothesis(BaseModel):
    """One concrete way in which the claim could be false."""

    hypothesis_id: str = Field(default_factory=lambda: _new_id("hyp"))
    claim_id: str
    category: HypothesisCategory
    hypothesis: str
    rationale: str
    falsification_target: str
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    origin: str = Field(default="deterministic", description="'deterministic' | 'llm'")


# ---------------------------------------------------------------------------
# Search queries
# ---------------------------------------------------------------------------


class SearchQuery(BaseModel):
    """An adversarial search query derived from a falsification hypothesis."""

    query_id: str = Field(default_factory=lambda: _new_id("qry"))
    hypothesis_id: str
    claim_id: str = ""
    query: str
    query_type: QueryType = QueryType.GENERAL
    rationale: str = ""


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


class Evidence(BaseModel):
    """A single retrieved source."""

    evidence_id: str = Field(default_factory=lambda: _new_id("ev"))
    query_id: str | None = None
    source_url: str
    title: str = ""
    publisher: str = ""
    domain: str = ""
    retrieved_text: str = ""
    relevant_passages: list[str] = Field(default_factory=list)
    publication_date: str | None = None
    retrieval_timestamp: datetime = Field(default_factory=_utcnow)
    score: float | None = Field(default=None, description="Retriever-reported relevance, if any.")


class EvidenceAssessment(BaseModel):
    """Structured judgement of one piece of evidence w.r.t. the claim."""

    evidence_id: str
    supports_claim: bool = False
    contradicts_claim: bool = False
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source_tier: SourceTier = SourceTier.UNKNOWN
    temporal_validity: float = Field(default=1.0, ge=0.0, le=1.0)
    is_direct: bool = Field(
        default=False, description="True if the evidence addresses the claim directly, not by inference."
    )
    observed_value: str | None = Field(
        default=None, description="The value/stance actually observed in the evidence, if extractable."
    )
    reasoning: str = ""
    analysis_source: str = Field(default="deterministic", description="'deterministic' | 'llm' | 'hybrid'")

    @property
    def stance(self) -> str:
        if self.supports_claim and not self.contradicts_claim:
            return "supporting"
        if self.contradicts_claim and not self.supports_claim:
            return "contradicting"
        if self.supports_claim and self.contradicts_claim:
            return "mixed"
        return "neutral"


# ---------------------------------------------------------------------------
# Contradictions
# ---------------------------------------------------------------------------


class Contradiction(BaseModel):
    """A detected contradiction between the claim and the evidence."""

    contradiction_id: str = Field(default_factory=lambda: _new_id("ctr"))
    claim_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    contradiction_type: ContradictionType
    severity: Severity = Severity.MEDIUM
    explanation: str = ""


# ---------------------------------------------------------------------------
# Fusion
# ---------------------------------------------------------------------------


class EvidenceCluster(BaseModel):
    """A group of near-duplicate / same-origin evidence items (one independent voice)."""

    cluster_id: str = Field(default_factory=lambda: _new_id("clu"))
    evidence_ids: list[str]
    representative_domain: str = ""
    stance: str = "neutral"  # supporting | contradicting | neutral | mixed
    weight: float = 0.0


class FusionSummary(BaseModel):
    supporting_evidence: int = 0
    contradicting_evidence: int = 0
    neutral_evidence: int = 0
    total_evidence: int = 0
    independent_supporting_clusters: int = 0
    independent_contradicting_clusters: int = 0
    support_strength: float = 0.0
    contradict_strength: float = 0.0
    max_support_quality: float = 0.0
    max_contradict_quality: float = 0.0
    duplicated_evidence_detected: int = 0
    hypotheses_total: int = 0
    hypotheses_with_evidence: int = 0
    coverage: float = 0.0
    retrieval_failures: int = 0


# ---------------------------------------------------------------------------
# Result & trace
# ---------------------------------------------------------------------------


class HypothesisTraceEntry(BaseModel):
    hypothesis_id: str
    hypothesis: str
    category: HypothesisCategory
    priority: float
    tested: bool = False
    queries_run: int = 0
    evidence_found: int = 0
    outcome: str = "not_tested"  # not_tested | no_evidence | survived | challenged | falsified


class QueryTraceEntry(BaseModel):
    query_id: str
    query: str
    hypothesis: str
    purpose: str
    query_type: QueryType
    results_found: int = 0
    retrieval_error: str | None = None


class EvidenceTraceEntry(BaseModel):
    evidence_id: str
    url: str
    title: str
    publisher: str
    source_tier: SourceTier
    stance: str
    relevance_score: float
    source_quality_score: float
    temporal_validity: float
    is_direct: bool
    reasoning: str
    key_passage: str = ""


class ContradictionTraceEntry(BaseModel):
    contradiction_id: str
    type: ContradictionType
    severity: Severity
    explanation: str
    evidence_urls: list[str] = Field(default_factory=list)


class ReasoningTrace(BaseModel):
    """The full, frontend-renderable trace of how the verdict was reached."""

    claim: str = ""
    normalized_claim: str = ""
    claim_kind: ClaimKind = ClaimKind.UNKNOWN
    hypotheses: list[HypothesisTraceEntry] = Field(default_factory=list)
    queries: list[QueryTraceEntry] = Field(default_factory=list)
    evidence_summary: dict[str, int] = Field(default_factory=dict)
    evidence: list[EvidenceTraceEntry] = Field(default_factory=list)
    contradictions: list[ContradictionTraceEntry] = Field(default_factory=list)
    fusion: FusionSummary | None = None
    verdict: Verdict = Verdict.UNVERIFIABLE
    confidence: float = 0.0
    confidence_explanation: str = ""
    reasoning: str = ""
    errors: list[str] = Field(default_factory=list)
    stage_timings_ms: dict[str, int] = Field(default_factory=dict)


class ConfidenceBreakdown(BaseModel):
    """Individual factors that produced the final confidence score."""

    evidence_quality: float = 0.0
    evidence_relevance: float = 0.0
    source_independence: float = 0.0
    cross_source_agreement: float = 0.0
    contradiction_strength: float = 0.0  # penalty-ish factor: higher = less unresolved contradiction
    temporal_validity: float = 0.0
    retrieval_coverage: float = 0.0
    decisiveness_margin: float = 0.0
    weighted_total: float = 0.0
    factors: dict[str, float] = Field(default_factory=dict)


class PipelineError(BaseModel):
    """A structured, non-fatal failure recorded during the pipeline."""

    stage: str
    error_type: str
    message: str
    query: str | None = None


class VerificationResult(BaseModel):
    """The complete output of a Falsify verification run."""

    claim_id: str
    claim_text: str
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_explanation: str = ""
    confidence_breakdown: ConfidenceBreakdown = Field(default_factory=ConfidenceBreakdown)
    claim: Claim
    hypotheses: list[FalsificationHypothesis] = Field(default_factory=list)
    queries: list[SearchQuery] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    assessments: list[EvidenceAssessment] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    fusion: FusionSummary = Field(default_factory=FusionSummary)
    reasoning_trace: ReasoningTrace = Field(default_factory=ReasoningTrace)
    errors: list[PipelineError] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
    engine_version: str = "1.0.0"
    llm_used: bool = False
    retrieval_provider: str = "none"

    # Convenience for the API layer -------------------------------------
    def summary(self) -> dict[str, Any]:
        """Compact JSON-friendly summary suitable for list views / logs."""
        return {
            "claim_id": self.claim_id,
            "claim": self.claim_text,
            "verdict": self.verdict.value,
            "confidence": round(self.confidence, 3),
            "confidence_explanation": self.confidence_explanation,
            "evidence_summary": self.reasoning_trace.evidence_summary,
            "contradictions": [
                {"type": c.type.value, "severity": c.severity.value, "explanation": c.explanation}
                for c in self.reasoning_trace.contradictions
            ],
            "errors": [e.message for e in self.errors],
        }
