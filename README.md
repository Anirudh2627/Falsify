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

## Development & Testing

```bash
pip install -r requirements.txt pytest   # Python >= 3.11
cp .env.example .env                     # optional: add TAVILY_API_KEY / LLM_* / DATABASE_URL
alembic upgrade head                     # apply database migrations (creates falsify.db)
python -m pytest tests/                  # run full test suite (242 offline tests)
python scripts/demo_falsify.py           # offline end-to-end demo
TAVILY_API_KEY=... python scripts/smoke_tavily.py   # live smoke test (optional LLM_* vars)
```

## Running the API Server

Start the FastAPI application with uvicorn:

```bash
uvicorn app.main:app --reload --port 8000
```

### Database Persistence & Migrations (SQLite)

Falsify persists verification records in SQLite (`falsify.db`) using SQLAlchemy 2.x and Alembic migrations.

- **Configure Database URL**: Set `DATABASE_URL` in `.env` (defaults to `sqlite:///./falsify.db`).
- **Apply Migrations**: `alembic upgrade head`
- **Session Lifecycle**: Database sessions are request-scoped and cleanly disposed during application lifespan.

### REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` / `/api/health` | Diagnostic status, app & engine versions, provider configuration |
| `POST` | `/api/verify` | Submit a claim (`{"claim": "..."}`) for adversarial verification; results are persisted |
| `POST` | `/api/verify/stream` | Stream real-time verification progress and final result via Server-Sent Events (SSE) |
| `GET` | `/api/verifications` | Paginated verification history with query params (`page`, `page_size`, `verdict`) |
| `GET` | `/api/verifications/{id}` | Retrieve complete stored verification result and full reasoning trace without re-running engine |
| `DELETE` | `/api/verifications/{id}` | Delete a stored verification record (HTTP 204) |

*Note: History endpoints currently have no authentication or access control protection.*

### Real-Time Verification Streaming (Server-Sent Events)

The `POST /api/verify/stream` endpoint enables frontend clients to observe the pipeline's execution in real time without blocking the asyncio event loop.

#### Difference between Endpoints
- `POST /api/verify`: Synchronous request-response. Returns the full JSON result once the pipeline finishes.
- `POST /api/verify/stream`: Real-time streaming response (`text/event-stream`). Yields progressive stage updates followed by the persisted result.

#### SSE Event Protocol

| Event | When Emitted | Payload Schema |
|---|---|---|
| `verification_started` | Immediately upon request acceptance | `{"message": str, "claim": str}` |
| `verification_progress` | As engine transitions between stages | `{"stage": str, "message": str, "progress": float}` |
| `verification_completed` | Pipeline finished and result saved | `{"verification_id": int, "verdict": str, "confidence": float, "result": {...}}` |
| `verification_error` | On unexpected failure / persistence error | `{"code": str, "message": str}` |

#### Example SSE Request via cURL

```bash
curl -N -X POST http://localhost:8000/api/verify/stream \
  -H "Content-Type: application/json" \
  -d '{"claim": "Company X grew revenue by 40% in 2025."}'
```

#### Example SSE Stream Output

```text
id: 1
event: verification_started
data: {"message": "Verification started", "claim": "Company X grew revenue by 40% in 2025."}

id: 2
event: verification_progress
data: {"stage": "normalization", "message": "Normalizing claim and extracting constraints", "progress": 0.1}

id: 3
event: verification_progress
data: {"stage": "hypotheses", "message": "Generating falsification hypotheses", "progress": 0.25}

id: 4
event: verification_progress
data: {"stage": "retrieval", "message": "Retrieving evidence from external sources", "progress": 0.5}

id: 5
event: verification_progress
data: {"stage": "persisting", "message": "Persisting verification record", "progress": 0.98}

id: 6
event: verification_completed
data: {"verification_id": 1, "verdict": "REFUTED", "confidence": 0.777, "result": {"verdict": "REFUTED", ...}}
```

### Example Verification Request (Synchronous)

```bash
curl -X POST http://localhost:8000/api/verify \
  -H "Content-Type: application/json" \
  -d '{"claim": "Company X grew revenue by 40% in 2025."}'
```

### Example History Listing

```bash
curl "http://localhost:8000/api/verifications?page=1&page_size=10&verdict=REFUTED"
```

---

## Frontend Web Application (Phase 4)

A dedicated, light-themed research dashboard built with **React 18**, **Vite 5**, **TypeScript**, and **Tailwind CSS**. It provides a professional, claim-level adversarial verification workspace rather than a conversational chatbot interface.

### Frontend Features

1. **Branded Application Shell**: Clean white and soft-neutral light theme, restrained blue/indigo accents, responsive desktop/tablet/mobile layouts, and real-time backend health monitor polling `/api/health`.
2. **Claim Verification Workspace**:
   - Multiline textarea with live character counter (up to 4,000 characters).
   - Empty and whitespace-only claim validation.
   - Sample claim presets (Revenue Claim, Science Fact, Market Statistics).
   - Keyboard shortcut (`Ctrl + Enter` to verify).
   - Client-side stream cancellation without falsely claiming backend verification was aborted.
3. **Real-Time SSE Streaming Progress**:
   - Connects to `POST /api/verify/stream` using standard `fetch()` and `ReadableStream`.
   - Handles multi-event chunks, CRLF/LF line endings, UTF-8 multibyte boundary decoding, and premature disconnect detection.
   - Visual stage timeline displaying active progress message and truthful backend stage transitions.
4. **Comprehensive Result Dashboard**:
   - **Verdict Determination**: Clear, accessible badges and status styling for all 5 verdicts (`VERIFIED`, `QUALIFIED`, `CONFLICTED`, `REFUTED`, `UNVERIFIABLE`).
   - **Multi-Factor Confidence Visualizer**: Overall confidence score gauge, explanation summary, and multi-factor breakdown (evidence quality, relevance, source independence, cross-source agreement, contradiction strength, temporal validity, retrieval coverage).
   - **Evidence Cards**: Grouped with Source Tier badges (Tier 1 Primary / Regulatory, Tier 2 Secondary, Tier 3 Unverified), stance indicators (`supporting`, `contradicting`, `neutral`), relevance and quality scores, relevant excerpts, and safe external links (`target="_blank" rel="noopener noreferrer"`).
   - **Adversarial Hypotheses & Queries**: Collapsible cards detailing tested failure hypotheses with outcome badges (`falsified`, `challenged`, `survived`, `no_evidence`) and adversarial search queries.
   - **Contradiction Detection & Fusion**: Highlighted contradictions with severity tags (`critical`, `high`, `medium`, `low`) and source fusion cluster metrics (independent clusters, duplicate sources collapsed).
   - **Audit & Reasoning Trace**: Stage execution timings in milliseconds, structured pipeline traces, and raw JSON contract toggle for complete inspection.
5. **Verification History**:
   - Paginated table backed directly by `GET /api/verifications`.
   - Server-side verdict filtering and pagination controls.
   - View stored historical results via `GET /api/verifications/{id}` without re-executing verification.
   - Record deletion with an accessible confirmation modal.

### Installing and Running Frontend

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Configure environment (optional, defaults to http://localhost:8000 via Vite proxy)
cp .env.example .env

# Start development server
npm run dev
```

The frontend will be available at `http://localhost:5173`.

### Frontend Scripts

| Command | Action |
|---|---|
| `npm run dev` | Start Vite development server with hot module replacement |
| `npm run build` | Run TypeScript compiler check (`tsc`) and Vite production bundle |
| `npm run preview` | Preview production build locally |
| `npm test` | Run Vitest unit and integration test suite |

### Frontend Environment Configuration

In `frontend/.env.example`:
```bash
# Backend API Base URL (leave blank when using Vite dev proxy on localhost)
VITE_API_BASE_URL=http://localhost:8000
```

---

## Production Deployment & Containerization (Phase 6)

Falsify supports a single-container production deployment where compiled React static assets and the FastAPI REST/SSE endpoints are served together from the same origin on port `8000`.

### Key Operational Features
- **Persistent SQLite Storage**: Uses named volume (`falsify_data:/app/data`) so verification history survives container rebuilds and restarts.
- **Operational Health Probes**:
  - `GET /health` (or `/api/health`): Fast liveness check (does not hit paid external APIs).
  - `GET /ready` (or `/api/ready`): Database connectivity readiness probe (`SELECT 1`).
- **Security & Hardening**:
  - Non-root container execution (`falsify:falsify`, UID 10001).
  - Production error masking (`DEBUG=false` hides tracebacks and secrets from clients).
  - Configurable payload size limits (`MAX_REQUEST_SIZE_BYTES=1048576`).
  - Unauthenticated endpoint risk evaluation and mitigation documentation.
- **SSE Streaming Behind Proxies**: Documented buffering directives (`proxy_buffering off;`) for Nginx and Caddy.

### Quick Start with Docker Compose
```bash
# 1. Copy environment template
cp .env.example .env

# 2. Build and launch container with persistent storage
docker compose up --build -d

# 3. Check health probe
curl http://localhost:8000/health
curl http://localhost:8000/ready

# 4. Open dashboard
open http://localhost:8000
```

### Database Migrations
```bash
# Inspect current schema version
alembic current

# Run pending migrations
alembic upgrade head
```

For complete instructions, cloud provider evaluations (Fly.io, Render, Railway, VPS), safe backup procedures, and troubleshooting, see the comprehensive [Deployment & Operational Guide](docs/DEPLOYMENT.md).

---

See [`docs/FALSIFY_INTEGRATION.md`](docs/FALSIFY_INTEGRATION.md) for the full
API contract, result schema, configuration reference and error semantics.

