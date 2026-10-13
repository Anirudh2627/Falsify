# Falsify Core Intelligence / Verification Engine — Integration Guide

**Audience:** the API/backend developer and the frontend developer.
**Owner:** Core Intelligence team. **Status:** implemented, tested (208 unit/e2e tests, fully offline), lint-clean.

This document is the contract between the verification engine (`app/falsify/`) and the
rest of the product. The engine has **no dependency on FastAPI, databases, or the
frontend** — it is a pure Python package you call synchronously and serialize.

---

## 1. Quick start

```python
from app.falsify import FalsifyEngine, build_default_engine

# Production: wires providers from environment variables (see §6)
engine = build_default_engine()

result = engine.verify("Company X increased revenue by 20% in 2025.")

result.verdict          # Verdict enum: VERIFIED | QUALIFIED | CONFLICTED | REFUTED | UNVERIFIABLE
result.confidence       # float 0.0..1.0
result.summary()        # compact JSON-ready dict (list views, logs)
result.model_dump(mode="json")   # FULL payload incl. the complete reasoning trace
```

`engine` is **stateless between calls** — construct it once (e.g. as a FastAPI
dependency with app-scoped lifetime) and reuse it; it is safe to call `verify`
from multiple threads.

For tests / full control, inject your own collaborators:

```python
from app.falsify import EngineConfig, FalsifyEngine
from app.falsify.retrieval import TavilyRetriever, InMemoryRetriever
from app.falsify.llm import OpenAICompatLLM, NullLLM, MockLLM

engine = FalsifyEngine(
    config=EngineConfig(max_hypotheses=5, max_total_queries=10),
    llm=NullLLM(),                                   # deterministic-only mode
    retriever=TavilyRetriever(api_key=os.environ["TAVILY_API_KEY"]),
)
```

---

## 2. What the pipeline does (why it is not a search wrapper)

```
Claim → Normalization → Falsification Hypotheses → Adversarial Queries
      → Retrieval → Evidence Assessment → Contradiction Detection
      → Evidence Fusion (dedup/independence) → Verdict → Confidence → Trace
```

The engine never searches for the claim itself. It enumerates concrete ways the
claim could be **false** (numerical / temporal / entity / causal / definitional /
attribution / source / scope), generates queries designed to surface
**counterevidence** (primary filings, contradictory figures, restatements,
alternative definitions), then fuses what it finds. Duplicate/syndicated sources
collapse into a single independent voice, so three blogs copying a wrong number
cannot outweigh one primary filing.

## 3. The result object

`VerificationResult` (pydantic v2, fully JSON-serializable):

| Field | Type | Notes |
|---|---|---|
| `claim_id`, `claim_text` | str | |
| `verdict` | `Verdict` (str enum) | `VERIFIED / QUALIFIED / CONFLICTED / REFUTED / UNVERIFIABLE` — never force-fit to true/false |
| `confidence` | float 0–1 | multi-factor, **not** supporting/total (see §5) |
| `confidence_explanation` | str | human-readable factor summary |
| `confidence_breakdown` | `ConfidenceBreakdown` | every factor as a number (charts!) |
| `claim` | `Claim` | normalized structure: entities, predicates, temporal/geographic/quantitative constraints, claim_kind, assertions; `original_text` always preserved |
| `hypotheses` | `list[FalsificationHypothesis]` | category, hypothesis, rationale, falsification_target, priority, origin |
| `queries` | `list[SearchQuery]` | query, query_type, rationale, linked hypothesis |
| `evidence` | `list[Evidence]` | url, title, publisher, text, passages, dates — **never fabricated** |
| `assessments` | `list[EvidenceAssessment]` | supports/contradicts, relevance, source quality + tier, temporal validity, directness, reasoning |
| `contradictions` | `list[Contradiction]` | type, severity (low→critical), explanation, evidence_ids |
| `fusion` | `FusionSummary` | independent cluster counts, strengths, duplicates collapsed, coverage |
| `reasoning_trace` | `ReasoningTrace` | **the frontend payload** (see §4) |
| `errors` | `list[PipelineError]` | structured, non-fatal stage failures |
| `llm_used`, `retrieval_provider`, `created_at`, `engine_version` | metadata | |

## 4. Rendering the trace (frontend)

`result.reasoning_trace.model_dump(mode="json")` produces exactly the shape the
UI needs:

```json
{
  "claim": "Company X grew revenue by 40% in 2025.",
  "normalized_claim": "Company X's revenue increased by 40% in 2025.",
  "claim_kind": "quantitative_change",
  "hypotheses": [
    {"hypothesis": "Company X's revenue actually decreased ...", "category": "numerical",
     "priority": 0.95, "tested": true, "queries_run": 5, "evidence_found": 5,
     "outcome": "falsified"}
  ],
  "queries": [
    {"query": "Company X revenue 2025 actual reported figure",
     "purpose": "Find the authoritative number to compare against the claimed value.",
     "query_type": "primary_source", "results_found": 5, "retrieval_error": null}
  ],
  "evidence_summary": {"supporting": 3, "contradicting": 2, "neutral": 0, "total": 5},
  "evidence": [
    {"url": "https://www.sec.gov/...", "title": "...", "publisher": "...",
     "source_tier": 1, "stance": "contradicting", "relevance_score": 1.0,
     "source_quality_score": 0.9, "temporal_validity": 1.0, "is_direct": true,
     "reasoning": "...", "key_passage": "..."}
  ],
  "contradictions": [
    {"type": "numerical", "severity": "high",
     "explanation": "Claimed 40% vs observed 27.0 ...", "evidence_urls": ["https://www.sec.gov/..."]}
  ],
  "fusion": {"independent_supporting_clusters": 1, "independent_contradicting_clusters": 2,
              "duplicated_evidence_detected": 2, "coverage": 1.0},
  "verdict": "REFUTED",
  "confidence": 0.78,
  "confidence_explanation": "Confidence 0.78 in verdict REFUTED. ...",
  "reasoning": "Claim: ... Verdict: REFUTED (confidence 0.78). ...",
  "errors": [],
  "stage_timings_ms": {"normalization": 6, "hypotheses": 1, "...": 0}
}
```

`hypotheses[].outcome` ∈ `not_tested | no_evidence | survived | challenged | falsified`
— ideal for a "falsification attempts" panel with per-hypothesis status.

A ready-made demo you can run offline to see this output: `python3 scripts/demo_falsify.py`.

## 5. Verdict & confidence semantics

| Verdict | Meaning |
|---|---|
| `VERIFIED` | Strong, credible, (usually) independent support; falsification attempts found no credible contradiction |
| `QUALIFIED` | Broadly supported but an unresolved qualification exists (definitional caveat, minor numeric gap, single-source support) |
| `CONFLICTED` | Credible evidence on **both** sides within the conflict band; cannot be resolved |
| `REFUTED` | High/critical-severity contradiction backed by credible sources dominates |
| `UNVERIFIABLE` | No relevant evidence, only low-credibility sources, retrieval failure, or an unsettled future claim |

Confidence is a weighted blend of: evidence quality, relevance, source
independence (cluster-based), cross-source agreement (verdict-aware),
unresolved-contradiction strength, temporal validity, and retrieval coverage.
Rounding policy is respected: *"increased 20%"* vs *"increased 19.8%"* is
support (implied precision ±0.5), *"exactly 30%"* vs official *21%* is a
high-severity contradiction, direction flips are critical.

## 6. Configuration & environment

| Env var | Used by | Fallback if missing |
|---|---|---|
| `TAVILY_API_KEY` | `TavilyRetriever` | empty retriever → results become `UNVERIFIABLE` (no crash) |
| `LLM_API_KEY` / `NEBIUS_API_KEY` | `OpenAICompatLLM` | `NullLLM` → fully deterministic pipeline (still functional) |
| `LLM_BASE_URL` | any OpenAI-compatible endpoint (Nebius AI Studio, NVIDIA NIM, OpenAI, vLLM...) | `https://api.openai.com/v1` |
| `LLM_MODEL` | model name | `gpt-4o-mini` |

Tunables via `EngineConfig` (all defaults are demo-safe):
`max_hypotheses=6`, `max_queries_per_hypothesis=3`, `max_total_queries=15`,
`max_evidence_per_query=5`, `max_total_evidence=25`, `llm_max_retries=2`,
`use_llm_for_*` toggles (queries default **off** — deterministic templates are
strong and it saves LLM calls), thresholds (`min_quality_verified`,
`conflict_band`, `numeric_agreement_rel_tol`, `duplicate_text_similarity`, ...).

## 7. Error contract

* **Invalid input** (empty / >4000 chars): raises `app.falsify.ClaimValidationError`
  → map to HTTP 400.
* **Everything else never raises.** Retrieval outages, LLM outages, malformed
  model JSON, empty result sets are recorded in `result.errors`
  (`stage`, `error_type`, `message`, `query`) and reflected in the verdict
  (typically `UNVERIFIABLE`). The engine **never fabricates evidence**: a
  failed retrieval yields zero items, not placeholders.
* **Malformed LLM output is retried** up to `llm_max_retries` (default 2) per call
  before falling back to deterministic logic; LLM *unavailability* is never retried
  (immediate deterministic fallback).
* `verify()` is synchronous and can take several seconds with live providers
  (up to `max_total_queries` HTTP calls). In FastAPI, run it via
  `run_in_threadpool` / a task queue, or add an async wrapper yourselves —
  the engine holds no shared mutable state.

## 8. Structured logging

Logger name: `falsify` (standard `logging`, `event=<name> key=value` lines).
Events: `claim_normalization_started`, `claim_normalized`, `hypotheses_generated`,
`queries_generated`, `evidence_retrieved`, `evidence_assessed`,
`contradictions_detected`, `evidence_fused`, `verdict_generated`,
`confidence_computed`, `verification_complete`, plus `*_skipped` /
`retrieval_failed` / `stage_failed` warnings. **API keys are never logged**
(asserted by tests). Attach your own handler or set level on
`logging.getLogger("falsify")`.

## 9. Testing against the engine

Use the injected mocks — no network needed:

```python
from app.falsify import EngineConfig, FalsifyEngine
from app.falsify.llm import MockLLM
from app.falsify.retrieval import InMemoryRetriever
from app.falsify.models import Evidence

engine = FalsifyEngine(
    config=EngineConfig(use_llm_for_normalization=False, use_llm_for_hypotheses=False,
                        use_llm_for_evidence_assessment=False, use_llm_for_synthesis=False),
    llm=MockLLM({}),                       # or scripted JSON responses
    retriever=InMemoryRetriever([Evidence(source_url="https://www.sec.gov/...", ...)]),
)
```

## 10. Live smoke test

```bash
export TAVILY_API_KEY=tvly-...
# optional: export LLM_API_KEY=... LLM_BASE_URL=... LLM_MODEL=...
python3 scripts/smoke_tavily.py "The Eiffel Tower is taller than the Statue of Liberty."
```

## 11. Module map

```
requirements.txt       runtime deps (pydantic, httpx)
.env.example           documented environment variables
app/falsify/
  engine.py            FalsifyEngine orchestrator + build_default_engine()
  models.py            ALL pydantic models & enums (the data contract)
  config.py            EngineConfig / RetrievalConfig / LLMConfig
  exceptions.py        FalsifyError hierarchy
  logging_utils.py     structured event logging
  normalization/       ClaimNormalizer (deterministic-first, LLM-refined)
  hypotheses/          FalsificationEngine.generate_hypotheses(claim)
  queries/             AdversarialQueryGenerator.generate(claim, hypothesis)
  retrieval/           EvidenceRetriever protocol, TavilyRetriever, InMemoryRetriever (tests)
  analysis/            EvidenceAnalyzer, ContradictionDetector, SourceQualityScorer, numerics
  fusion/              EvidenceFusion (dedup/clustering), VerdictEngine, ConfidenceCalculator
  llm/                 LLMProvider protocol, OpenAICompatLLM, NullLLM, MockLLM, JSON repair
  prompts/             all prompt templates (separated from business logic, shared guardrails)
tests/falsify/         208 offline tests incl. the 6 spec cases + adversarial edge cases
scripts/               demo_falsify.py (offline demo), smoke_tavily.py (live)
```

Extension points (all dependency-injected, all covered by `Protocol`s):
custom retriever → implement `search(query, max_results) -> list[Evidence]`;
custom LLM → implement `generate(prompt, system=..., max_tokens=...) -> str`.
