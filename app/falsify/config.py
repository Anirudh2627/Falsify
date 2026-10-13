"""Configuration for the Falsify engine.

All performance-relevant limits and thresholds live here and are injectable,
so callers (API layer, tests) can tune behaviour without touching code.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field


class RetrievalConfig(BaseModel):
    """Retrieval limits and provider settings."""

    provider: str = Field(default="tavily", description="'tavily' | 'mock' | custom")
    api_key: str | None = Field(default=None, description="Injected from env; never hard-coded.")
    max_results_per_query: int = 5
    request_timeout_s: float = 15.0
    base_url: str = "https://api.tavily.com"

    @classmethod
    def from_env(cls) -> RetrievalConfig:
        return cls(api_key=os.environ.get("TAVILY_API_KEY"))


class LLMConfig(BaseModel):
    """LLM provider settings (OpenAI-compatible: Nebius / NVIDIA / OpenAI / ...)."""

    provider: str = Field(default="openai_compat", description="'openai_compat' | 'none'")
    api_key: str | None = None
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_tokens: int = 1200
    request_timeout_s: float = 60.0
    max_retries: int = 2  # retries on malformed JSON / transient errors

    @classmethod
    def from_env(cls) -> LLMConfig:
        return cls(
            api_key=os.environ.get("LLM_API_KEY") or os.environ.get("NEBIUS_API_KEY"),
            base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
            model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        )


class EngineConfig(BaseModel):
    """Top-level engine configuration: pipeline limits and decision thresholds."""

    # --- pipeline limits -------------------------------------------------
    max_hypotheses: int = Field(default=6, ge=1)
    max_queries_per_hypothesis: int = Field(default=3, ge=1)
    max_total_queries: int = Field(default=15, ge=1)
    max_evidence_per_query: int = Field(default=5, ge=1)
    max_total_evidence: int = Field(default=25, ge=1)
    max_claim_chars: int = Field(default=4000, ge=50)
    llm_max_retries: int = Field(default=2, ge=0)

    # --- LLM usage policy -------------------------------------------------
    use_llm_for_normalization: bool = True
    use_llm_for_hypotheses: bool = True
    use_llm_for_queries: bool = False  # deterministic templates are strong; opt-in to save LLM calls
    use_llm_for_evidence_assessment: bool = True
    use_llm_for_synthesis: bool = True

    # --- analysis thresholds ----------------------------------------------
    relevance_floor: float = Field(default=0.15, ge=0.0, le=1.0)
    # A numerical mismatch <= this relative size is treated as a rounding
    # difference (support), not a contradiction.
    numeric_agreement_rel_tol: float = Field(default=0.02, ge=0.0)
    # Duplicate-detection threshold for near-identical evidence text.
    duplicate_text_similarity: float = Field(default=0.75, ge=0.0, le=1.0)

    # --- fusion / verdict thresholds ---------------------------------------
    min_support_strength_verified: float = Field(default=0.8, ge=0.0)
    min_quality_verified: float = Field(default=0.55, ge=0.0, le=1.0)
    conflict_band: tuple[float, float] = Field(default=(0.35, 3.0))
    # verdict thresholds are applied by VerdictEngine; see fusion/verdict.py

    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)

    @classmethod
    def from_env(cls, **overrides) -> EngineConfig:
        return cls(retrieval=RetrievalConfig.from_env(), llm=LLMConfig.from_env(), **overrides)
