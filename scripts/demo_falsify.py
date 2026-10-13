#!/usr/bin/env python3
"""Offline Falsify demo -- shows exactly what the frontend will receive.

Runs the full pipeline against a deterministic fixture corpus (no network,
no API keys).  This mirrors the spec's demo scenario:

    Claim:  "Company X grew revenue by 40% in 2025."
    Truth:  official filing reports 27% -> REFUTED

Run:  python3 scripts/demo_falsify.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.falsify import EngineConfig, FalsifyEngine
from app.falsify.models import Evidence
from app.falsify.retrieval.mock import InMemoryRetriever

CORPUS = [
    Evidence(
        source_url="https://www.sec.gov/Archives/edgar/data/0000000000/companyx-10k-2025.htm",
        title="Company X Inc. Form 10-K, fiscal year 2025",
        publisher="Company X Inc. (SEC filing)",
        domain="sec.gov",
        retrieved_text=(
            "Company X Inc. full year 2025: total revenue increased 27% compared with fiscal 2024, "
            "reaching $12.7 billion. Audited consolidated financial statements are included in this "
            "annual report filed with the Securities and Exchange Commission."
        ),
        publication_date="2026-02-20",
        retrieval_timestamp=datetime(2026, 3, 1, tzinfo=UTC),
    ),
    Evidence(
        source_url="https://www.reuters.com/business/companyx-annual-results-2025",
        title="Company X revenue grows 27% in 2025, missing some forecasts",
        publisher="Reuters",
        domain="reuters.com",
        retrieved_text=(
            "Company X reported that revenue increased 27% in 2025 versus 2024, according to the "
            "company's annual report filed with regulators. Analysts had expected stronger growth."
        ),
        publication_date="2026-02-21",
        retrieval_timestamp=datetime(2026, 3, 1, tzinfo=UTC),
    ),
] + [
    Evidence(
        source_url=f"https://growthblog{i}.blogspot.com/companyx-40-percent",
        title="Company X had an amazing 2025 with 40% revenue growth!",
        publisher="Growth Blog",
        domain=f"growthblog{i}.blogspot.com",
        retrieved_text=(
            "Company X grew revenue by 40% in 2025, an incredible performance that beat "
            "everyone's expectations."
        ),
        publication_date="2026-01-05",
        retrieval_timestamp=datetime(2026, 3, 1, tzinfo=UTC),
    )
    for i in range(3)
]


def main() -> None:
    config = EngineConfig(
        use_llm_for_normalization=False,
        use_llm_for_hypotheses=False,
        use_llm_for_queries=False,
        use_llm_for_evidence_assessment=False,
        use_llm_for_synthesis=False,
    )
    engine = FalsifyEngine(config=config, retriever=InMemoryRetriever(CORPUS, min_overlap=1))

    claim = "Company X grew revenue by 40% in 2025."
    result = engine.verify(claim)

    print("=" * 78)
    print("FALSIFY -- ADVERSARIAL CLAIM VERIFICATION (offline demo)")
    print("=" * 78)
    print(f"\nCLAIM\n  {claim}")
    print(f"\nNORMALIZED\n  {result.claim.normalized_text}")
    print(f"  kind={result.claim.claim_kind.value} entities={result.claim.entities} "
          f"period={result.claim.temporal_constraints}")

    print("\nFALSIFICATION ATTEMPTS (hypotheses tested)")
    for h in result.reasoning_trace.hypotheses:
        mark = {"falsified": "[FALSIFIED]", "challenged": "[challenged]", "survived": "[survived]",
                "no_evidence": "[no evidence]", "not_tested": "[not tested]"}[h.outcome]
        print(f"  {mark:14} ({h.category.value}, p={h.priority:.2f}) {h.hypothesis}")

    print(f"\nADVERSARIAL QUERIES ({len(result.queries)} executed)")
    for q in result.reasoning_trace.queries[:8]:
        print(f"  - {q.query}  [{q.query_type.value}: {q.results_found} hit(s)]")
    if len(result.queries) > 8:
        print(f"  ... and {len(result.queries) - 8} more")

    print(f"\nEVIDENCE ({result.fusion.total_evidence} sources, "
          f"{result.fusion.duplicated_evidence_detected} duplicate(s) collapsed)")
    for e in result.reasoning_trace.evidence:
        print(f"  - [{e.source_tier.name}] {e.publisher or e.url} -- stance={e.stance} "
              f"rel={e.relevance_score:.2f} q={e.source_quality_score:.2f}")

    print("\nCONTRADICTIONS")
    for c in result.reasoning_trace.contradictions:
        print(f"  - {c.type.value.upper()} ({c.severity.value}): {c.explanation}")

    print(f"\nVERDICT:    {result.verdict.value}")
    print(f"CONFIDENCE: {result.confidence:.2f}")
    print(f"\nWHY\n  {result.reasoning_trace.reasoning}")
    print(f"\nCONFIDENCE EXPLANATION\n  {result.confidence_explanation}")

    print("\n" + "=" * 78)
    print("FRONTEND PAYLOAD (result.summary()):")
    print(json.dumps(result.summary(), indent=2, default=str))
    print("\nFull trace available via result.reasoning_trace.model_dump_json()")


if __name__ == "__main__":
    main()
