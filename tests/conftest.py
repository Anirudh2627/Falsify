"""Shared test fixtures and helpers.

All tests run fully offline: a scripted ``MockLLM`` and an
``InMemoryRetriever`` standing in for the external providers.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.falsify.config import EngineConfig
from app.falsify.engine import FalsifyEngine
from app.falsify.llm.provider import MockLLM, NullLLM
from app.falsify.models import Evidence
from app.falsify.retrieval.mock import InMemoryRetriever


@pytest.fixture
def config() -> EngineConfig:
    """Deterministic-only configuration (no LLM calls by default)."""
    return EngineConfig(
        use_llm_for_normalization=False,
        use_llm_for_hypotheses=False,
        use_llm_for_queries=False,
        use_llm_for_evidence_assessment=False,
        use_llm_for_synthesis=False,
    )


def make_evidence(
    *,
    url: str,
    title: str = "",
    publisher: str = "",
    text: str = "",
    passages: list[str] | None = None,
    publication_date: str | None = None,
    evidence_id: str | None = None,
) -> Evidence:
    return Evidence(
        **({"evidence_id": evidence_id} if evidence_id else {}),
        source_url=url,
        title=title or url,
        publisher=publisher,
        domain=url.split("/")[2].removeprefix("www.") if "://" in url else "",
        retrieved_text=text,
        relevant_passages=passages or [],
        publication_date=publication_date,
        retrieval_timestamp=datetime(2026, 1, 15, tzinfo=UTC),
    )


def make_engine(
    corpus: list[Evidence] | None = None,
    *,
    llm=None,
    config: EngineConfig | None = None,
    retriever=None,
) -> FalsifyEngine:
    cfg = config or EngineConfig(
        use_llm_for_normalization=False,
        use_llm_for_hypotheses=False,
        use_llm_for_queries=False,
        use_llm_for_evidence_assessment=False,
        use_llm_for_synthesis=False,
    )
    return FalsifyEngine(
        config=cfg,
        llm=llm if llm is not None else NullLLM(),
        retriever=retriever if retriever is not None else InMemoryRetriever(corpus or [], min_overlap=1),
    )


# --- reusable fixture corpus: "Company X grew revenue by 40% in 2025" demo ----

TESLA_LIKE_CLAIM = "Company X grew revenue by 40% in 2025."

OFFICIAL_FILING_27PCT = make_evidence(
    url="https://www.companyx.com/investors/annual-report-2025",
    title="Company X 2025 Annual Report",
    publisher="Company X Investor Relations",
    text=(
        "Company X today reported full year 2025 results. Total revenue increased 27% "
        "compared with 2024, reaching $12.7 billion. The company's 2025 annual report "
        "was filed with regulators on February 10, 2026."
    ),
    publication_date="2026-02-10",
)

INDEPENDENT_NEWS_27PCT = make_evidence(
    url="https://www.reuters.com/business/companyx-2025-revenue",
    title="Company X posts 27% revenue growth for 2025, below some estimates",
    publisher="Reuters",
    text=(
        "Company X reported that revenue increased 27% in 2025 versus 2024, according to "
        "its annual report. Analysts had expected stronger growth."
    ),
    publication_date="2026-02-11",
)

CORROBORATING_40PCT = make_evidence(
    url="https://www.example-blog.com/companyx-growth",
    title="Company X had an amazing 2025 with 40% revenue growth",
    publisher="Example Blog",
    text="Company X grew revenue by 40% in 2025, an incredible performance.",
    publication_date="2026-01-05",
)


@pytest.fixture
def mock_llm_factory():
    def _make(responses: dict[str, str] | None = None):
        return MockLLM(responses or {})

    return _make
