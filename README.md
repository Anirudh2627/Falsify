# Falsify

**Claim-level adversarial verification.** An AI system makes a claim; Falsify's
job is to actively try to prove that claim wrong.

> "Here is a claim. What are the strongest ways this claim could be wrong?
> Let's actively search for those failure conditions, evaluate the evidence,
> detect contradictions, and only then produce a verdict."

```
Claim → Normalization → Falsification Hypotheses → Adversarial Queries
      → Evidence Retrieval → Evidence Assessment → Contradiction Detection
      → Evidence Fusion → Verdict → Confidence → Explanation + Evidence Trace
```

## Repository layout

| Path | Owner | Description |
|---|---|---|
| `app/falsify/` | **Core Intelligence** (this component) | The verification engine. Standalone Python package, no API/frontend dependencies. |
| `tests/falsify/` | Core Intelligence | 208 offline tests (mocked LLM + retrieval), incl. the six mandated verification cases and adversarial edge cases. |
| `scripts/` | Core Intelligence | `demo_falsify.py` (offline end-to-end demo), `smoke_tavily.py` (live provider smoke test). |
| `docs/FALSIFY_INTEGRATION.md` | Core Intelligence | **The integration contract for the API/backend and frontend developers.** |

The API layer and frontend are owned by the other team members; the engine is
designed to be mounted behind a single call:

```python
from app.falsify import build_default_engine

engine = build_default_engine()                     # env-configured (Tavily + any OpenAI-compatible LLM)
result = engine.verify("Company X grew revenue by 40% in 2025.")
result.verdict        # REFUTED
result.confidence     # 0.78
result.reasoning_trace  # full evidence trace for the UI
```

## Design principles

1. **Adversarial by construction** — the engine searches for counterevidence
   (primary filings, contradictory numbers, restatements, alternative
   definitions), never for confirmation of the claim.
2. **Five verdicts, not two** — `VERIFIED / QUALIFIED / CONFLICTED / REFUTED /
   UNVERIFIABLE`. Uncertainty is a first-class output.
3. **Deterministic backbone** — normalization, hypothesis templates, query
   generation, numeric comparison, source tiering, fusion, verdict and
   confidence rules are all deterministic and testable. The LLM is an
   *optional refinement* at four clearly-bounded points and can never
   override hard numeric extraction or give a stance to irrelevant sources.
4. **No fabricated evidence, ever** — failed retrievals return structured
   errors; malformed LLM output falls back to deterministic logic; URL-less
   search results are dropped.
5. **Independence over volume** — duplicated/syndicated sources collapse into
   one voice; three blogs copying a wrong number cannot outweigh one primary
   filing.
6. **Provider-agnostic** — `EvidenceRetriever` and `LLMProvider` protocols;
   Tavily and any OpenAI-compatible LLM (Nebius/NVIDIA/OpenAI/vLLM) plug in
   via environment variables.

## Development

```bash
pip install -r requirements.txt pytest   # Python >= 3.11
cp .env.example .env                     # optional: add TAVILY_API_KEY / LLM_* credentials
python -m pytest tests/                  # full offline suite (208 tests)
ruff check app tests scripts             # lint (config in pyproject.toml)
python -m mypy app/                      # type check (clean)
python scripts/demo_falsify.py           # offline end-to-end demo
TAVILY_API_KEY=... python scripts/smoke_tavily.py   # live smoke test (optional LLM_* vars)
```

See [`docs/FALSIFY_INTEGRATION.md`](docs/FALSIFY_INTEGRATION.md) for the full
API contract, result schema, configuration reference and error semantics.
