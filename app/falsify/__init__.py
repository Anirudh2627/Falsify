"""Falsify -- claim-level adversarial verification engine (core intelligence component).

Public API for the other team members::

    from app.falsify import FalsifyEngine, build_default_engine

    engine = build_default_engine()          # production wiring from env vars
    result = engine.verify("Company X grew revenue by 40% in 2025.")
    result.verdict                            # Verdict enum (serializable str)
    result.confidence                         # float in [0, 1]
    result.model_dump(mode="json")            # full JSON-serializable payload
    result.summary()                          # compact dict for list views

See docs/FALSIFY_INTEGRATION.md for the complete contract.
"""

from app.falsify.config import EngineConfig, LLMConfig, RetrievalConfig
from app.falsify.engine import FalsifyEngine, build_default_engine
from app.falsify.exceptions import (
    ClaimValidationError,
    ConfigurationError,
    FalsifyError,
    LLMError,
    LLMUnavailableError,
    MalformedLLMResponseError,
    RetrievalError,
    RetrieverUnavailableError,
)
from app.falsify.models import (
    Claim,
    ClaimKind,
    ConfidenceBreakdown,
    Contradiction,
    ContradictionType,
    Evidence,
    EvidenceAssessment,
    EvidenceCluster,
    FalsificationHypothesis,
    FusionSummary,
    HypothesisCategory,
    PipelineError,
    QuantitativeConstraint,
    QueryType,
    ReasoningTrace,
    SearchQuery,
    Severity,
    SourceTier,
    Verdict,
    VerificationResult,
)

__version__ = "1.0.0"

__all__ = [
    # entry points
    "FalsifyEngine",
    "build_default_engine",
    # config
    "EngineConfig",
    "LLMConfig",
    "RetrievalConfig",
    # models
    "Claim",
    "ClaimKind",
    "QuantitativeConstraint",
    "FalsificationHypothesis",
    "HypothesisCategory",
    "SearchQuery",
    "QueryType",
    "Evidence",
    "EvidenceAssessment",
    "SourceTier",
    "Contradiction",
    "ContradictionType",
    "Severity",
    "EvidenceCluster",
    "FusionSummary",
    "ConfidenceBreakdown",
    "ReasoningTrace",
    "PipelineError",
    "VerificationResult",
    "Verdict",
    # exceptions
    "FalsifyError",
    "ClaimValidationError",
    "ConfigurationError",
    "LLMError",
    "LLMUnavailableError",
    "MalformedLLMResponseError",
    "RetrievalError",
    "RetrieverUnavailableError",
    "__version__",
]
