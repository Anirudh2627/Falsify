#!/usr/bin/env python3
"""Real-provider smoke test for Falsify (requires network + credentials).

This is the ONLY place in the codebase that performs live external calls, and
it is a developer script, never imported by the engine or the tests.

Prerequisites (environment variables):
    TAVILY_API_KEY   -- required for retrieval
    LLM_API_KEY      -- optional (any OpenAI-compatible endpoint: Nebius, NVIDIA NIM, OpenAI...)
    LLM_BASE_URL     -- optional, defaults to https://api.openai.com/v1
    LLM_MODEL        -- optional, defaults to gpt-4o-mini

Run:
    python3 scripts/smoke_tavily.py "Company X grew revenue by 40% in 2025."
    python3 scripts/smoke_tavily.py            # uses a built-in real-world claim
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.falsify import build_default_engine
from app.falsify.llm import NullLLM

DEFAULT_CLAIM = "The Eiffel Tower is taller than the Statue of Liberty."


def main() -> None:
    if not os.environ.get("TAVILY_API_KEY"):
        print("ERROR: set TAVILY_API_KEY to run the live smoke test.", file=sys.stderr)
        sys.exit(2)

    claim_text = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CLAIM
    engine = build_default_engine()

    llm_name = "deterministic-only (no LLM configured)" if isinstance(engine._llm, NullLLM) else engine._llm.name
    print(f"Providers: retrieval={engine._retriever.name}  llm={llm_name}")
    print(f"Verifying: {claim_text!r} ...\n")

    result = engine.verify(claim_text)

    print(f"VERDICT:    {result.verdict.value}")
    print(f"CONFIDENCE: {result.confidence:.2f}")
    print(f"EVIDENCE:   {len(result.evidence)} source(s), {result.fusion.independent_supporting_clusters}/"
          f"{result.fusion.independent_contradicting_clusters} independent supporting/contradicting clusters")
    for ev in result.evidence[:5]:
        print(f"  - {ev.source_url}")
    if result.contradictions:
        print("CONTRADICTIONS:")
        for c in result.contradictions:
            print(f"  - {c.contradiction_type.value} ({c.severity.value}): {c.explanation[:200]}")
    if result.errors:
        print("PIPELINE ERRORS (non-fatal):")
        for e in result.errors:
            print(f"  - [{e.stage}] {e.error_type}: {e.message}")
    print("\nWHY:")
    print(result.reasoning_trace.reasoning)
    print("\nsummary() payload:")
    print(json.dumps(result.summary(), indent=2, default=str))


if __name__ == "__main__":
    main()
