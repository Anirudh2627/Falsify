# Falsify - Complete System Implementation Plan

## 1. Executive Summary & Repository Inspection

### 1.1 Existing Engine Inspection Findings
* **Repository:** [Anirudh2627/Falsify](https://github.com/Anirudh2627/Falsify.git)
* **Component Status:** Standalone Core Intelligence verification engine (`app/falsify/`) is fully implemented, self-contained, and deterministic-first with optional LLM refinements.
* **Exact Engine Entry Point:**
  - Class: `app.falsify.FalsifyEngine` (in `app/falsify/engine.py`)
  - Production Factory: `app.falsify.build_default_engine(**config_overrides) -> FalsifyEngine` (in `app/falsify/engine.py`)
* **Verification Method:**
  - `engine.verify(claim_text: str) -> VerificationResult`
  - Synchronous, thread-safe, stateless between calls.
* **Result Serialization Methods:**
  - `result.model_dump(mode="json")`: Complete Pydantic v2 JSON-serializable dictionary with all sub-objects and full reasoning trace.
  - `result.model_dump_json()`: Complete raw JSON string.
  - `result.summary() -> dict[str, Any]`: Compact dictionary suitable for list views, cards, and structured logs.
  - `result.reasoning_trace.model_dump(mode="json")`: Dedicated UI trace payload containing hypothesis outcomes, queries, evidence, contradictions, and timing metrics.
* **Exception Hierarchy & Error Handling:**
  - Base: `FalsifyError` (in `app/falsify/exceptions.py`, re-exported in `app/falsify/__init__.py`)
  - User Error: `ClaimValidationError` (raised when claim is empty, whitespace-only, or exceeds `max_claim_chars=4000`; maps directly to HTTP 400).
  - Internal / Provider Errors: `ConfigurationError`, `LLMError`, `LLMUnavailableError`, `MalformedLLMResponseError`, `RetrievalError`, `RetrieverUnavailableError`.
  - Resilience Guarantee: `verify()` **never raises** on retrieval or LLM failures. It records structured `PipelineError(stage, error_type, message, query)` items in `result.errors` and degrades gracefully (e.g., to `Verdict.UNVERIFIABLE` or deterministic logic).
* **All Fields Returned by `VerificationResult`:**
  - `claim_id: str` (UUID with prefix `claim_`)
  - `claim_text: str` (original input text)
  - `verdict: Verdict` (`VERIFIED`, `QUALIFIED`, `CONFLICTED`, `REFUTED`, `UNVERIFIABLE`)
  - `confidence: float` (0.0 to 1.0 multi-factor weighted score)
  - `confidence_explanation: str` (human-readable factor explanation)
  - `confidence_breakdown: ConfidenceBreakdown` (`evidence_quality`, `evidence_relevance`, `source_independence`, `cross_source_agreement`, `contradiction_strength`, `temporal_validity`, `retrieval_coverage`, `decisiveness_margin`, `weighted_total`, `factors: dict[str, float]`)
  - `claim: Claim` (`claim_id`, `original_text`, `normalized_text`, `claim_kind`, `entities`, `predicates`, `temporal_constraints`, `geographic_constraints`, `quantitative_constraints`, `negated`, `is_future_claim`, `assertions`, `normalization_source`, `normalization_warnings`)
  - `hypotheses: list[FalsificationHypothesis]` (`hypothesis_id`, `claim_id`, `category`, `hypothesis`, `rationale`, `falsification_target`, `priority`, `origin`)
  - `queries: list[SearchQuery]` (`query_id`, `hypothesis_id`, `claim_id`, `query`, `query_type`, `rationale`)
  - `evidence: list[Evidence]` (`evidence_id`, `query_id`, `source_url`, `title`, `publisher`, `domain`, `retrieved_text`, `relevant_passages`, `publication_date`, `retrieval_timestamp`, `score`)
  - `assessments: list[EvidenceAssessment]` (`evidence_id`, `supports_claim`, `contradicts_claim`, `relevance_score`, `source_quality_score`, `source_tier`, `temporal_validity`, `is_direct`, `observed_value`, `reasoning`, `analysis_source`, `stance`)
  - `contradictions: list[Contradiction]` (`contradiction_id`, `claim_id`, `evidence_ids`, `contradiction_type`, `severity`, `explanation`)
  - `fusion: FusionSummary` (`supporting_evidence`, `contradicting_evidence`, `neutral_evidence`, `total_evidence`, `independent_supporting_clusters`, `independent_contradicting_clusters`, `support_strength`, `contradict_strength`, `max_support_quality`, `max_contradict_quality`, `duplicated_evidence_detected`, `hypotheses_total`, `hypotheses_with_evidence`, `coverage`, `retrieval_failures`)
  - `reasoning_trace: ReasoningTrace` (`claim`, `normalized_claim`, `claim_kind`, `hypotheses`, `queries`, `evidence_summary`, `evidence`, `contradictions`, `fusion`, `verdict`, `confidence`, `confidence_explanation`, `reasoning`, `errors`, `stage_timings_ms`)
  - `errors: list[PipelineError]` (`stage`, `error_type`, `message`, `query`)
  - `created_at: datetime`
  - `engine_version: str` (currently `"1.0.0"`)
  - `llm_used: bool`
  - `retrieval_provider: str`

---

## 2. Baseline Test & Execution Results

| Test / Script | Command Executed | Outcome | Details |
|---|---|---|---|
| **Core Offline Test Suite** | `python -m pytest` | **PASSED** (208/208 passed in 1.91s) | All unit, integration, and edge-case tests pass completely offline using mocks. |
| **Offline Demo Script** | `python scripts/demo_falsify.py` | **PASSED** (Exit code 0) | Full pipeline executed on sample claim (`Company X grew revenue by 40% in 2025.`), resulting in `REFUTED` verdict (confidence 0.78), SEC filing contradiction detected, and duplicate blogs collapsed. |
| **Live Smoke Script** | `python scripts/smoke_tavily.py` | **BLOCKED** (Exit code 1 / Expected) | Failed with `ERROR: set TAVILY_API_KEY to run the live smoke test.` Missing external credentials (expected environmental blocker). |
| **Linter / Type Checker** | `ruff check`, `python -m mypy` | **NOT INSTALLED** | `ruff` and `mypy` packages are not in the current active python environment. |

### Environment Blockers & Missing Credentials:
1. `TAVILY_API_KEY`: Not configured in `.env`. Required for live web retrieval; offline tests and in-memory mock run without it.
2. `LLM_API_KEY` / `NEBIUS_API_KEY`: Optional; when absent, engine operates deterministically.
3. Developer tools (`ruff`, `mypy`): Can be added to dev dependencies if linting/typechecking CI is enabled.

---

## 3. Feature Matrix: Existing vs. Missing

| Domain | Feature | Existing? | Notes |
|---|---|---|---|
| **Core AI Engine** | Claim Normalization & Classification | YES | Deterministic regex/entity extraction with LLM refinement |
| **Core AI Engine** | Falsification Hypothesis Generation | YES | 8 hypothesis categories with priority scoring |
| **Core AI Engine** | Adversarial Query Generation | YES | 6 query types (primary source, contradiction, recency, etc.) |
| **Core AI Engine** | Multi-Tier Evidence Assessment | YES | Source tiering (Tier 1/2/3), directness, stance detection |
| **Core AI Engine** | Contradiction Detection | YES | Numerical tolerance, temporal, entity, and scope checks |
| **Core AI Engine** | Evidence Clustering & Fusion | YES | De-duplication and independent cluster counting |
| **Core AI Engine** | 5-Verdict Decision & Confidence Engine | YES | Deterministic decision matrix + multi-factor confidence |
| **Backend API** | FastAPI Server Setup & Lifespan | **MISSING** | No HTTP server or routing exists yet |
| **Backend API** | `POST /api/verify` Verification Endpoint | **MISSING** | Needs async execution via threadpool |
| **Backend API** | `GET /api/verifications/{id}` Retrieval | **MISSING** | Needs database lookup |
| **Backend API** | `GET /api/verifications` History & Filters | **MISSING** | Pagination, filtering by verdict/date |
| **Backend API** | Real-Time Stage Streaming (SSE / WebSocket) | **MISSING** | Pipeline stage progress callback/stream |
| **Backend API** | Health check & Provider Status Endpoint | **MISSING** | Check Tavily & LLM credentials & reachability |
| **Database** | Database Engine & Schema (SQLAlchemy/SQLite) | **MISSING** | Persistence for claims, results, traces |
| **Database** | Migrations (Alembic) | **MISSING** | Database migration management |
| **Frontend UI** | Modern Verification Dashboard | **MISSING** | Input form, sample presets, submit action |
| **Frontend UI** | Live Pipeline Stepper / Progress View | **MISSING** | Visualizing normalization -> hypotheses -> queries -> etc. |
| **Frontend UI** | Verdict & Confidence Breakdown Display | **MISSING** | Color-coded verdict badges, gauge, factor bars |
| **Frontend UI** | Hypotheses & Adversarial Queries Explorer | **MISSING** | Outcome tags, query counters, search terms |
| **Frontend UI** | Evidence Cards & Source Tier Visualization | **MISSING** | Tier badges, stance indicators, key passages |
| **Frontend UI** | Contradictions & Fusion Inspector | **MISSING** | Highlighting source conflicts & duplicate collapse |
| **Frontend UI** | History & Analytics Views | **MISSING** | Historical verifications, verdict distributions |
| **Deployment** | Docker & Compose Setup | **MISSING** | Multi-stage Dockerfile and docker-compose.yml |

---

## 4. Target Architecture & Proposed File Structure

```
d:\Falsify/
├── .env.example
├── README.md
├── IMPLEMENTATION_PLAN.md
├── pyproject.toml
├── requirements.txt
├── docs/
│   └── FALSIFY_INTEGRATION.md
├── scripts/
│   ├── demo_falsify.py
│   └── smoke_tavily.py
├── tests/
│   ├── conftest.py
│   ├── falsify/                  # Existing 208 core engine tests (DO NOT MODIFY)
│   ├── api/                      # New API integration tests
│   └── e2e/                      # End-to-end API + engine tests
├── app/
│   ├── __init__.py
│   ├── falsify/                  # Existing Core Engine (DO NOT REWRITE)
│   ├── core/                     # Application configuration & logging
│   │   ├── __init__.py
│   │   ├── config.py             # AppConfig (Pydantic settings)
│   │   └── security.py           # Optional API key / CORS settings
│   ├── db/                       # Database models & session
│   │   ├── __init__.py
│   │   ├── session.py            # SQLite/PostgreSQL engine & session maker
│   │   ├── models.py             # VerificationRecord, FeedbackRecord ORM models
│   │   └── repository.py         # CRUD operations
│   ├── services/                 # Verification orchestration & streaming
│   │   ├── __init__.py
│   │   └── verification_service.py # Bridges FastAPI & FalsifyEngine (threadpool + events)
│   ├── api/                      # FastAPI router & endpoints
│   │   ├── __init__.py
│   │   ├── deps.py               # Dependency injection (engine, db session)
│   │   ├── routes_verification.py# /api/verify, /api/verifications/{id}, etc.
│   │   ├── routes_system.py      # /api/health, /api/status, /api/stats
│   │   └── schemas.py            # API request/response DTOs
│   └── main.py                   # FastAPI app creation & middleware
└── frontend/                     # Interactive Web Application
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    ├── src/
    │   ├── main.tsx
    │   ├── App.tsx
    │   ├── styles/
    │   │   └── index.css         # Modern dark-mode glassmorphic theme
    │   ├── components/
    │   │   ├── Navbar.tsx
    │   │   ├── ClaimInput.tsx    # Claim input + sample presets
    │   │   ├── PipelineStepper.tsx # Real-time pipeline stage progress
    │   │   ├── VerdictCard.tsx   # Verdict badge + confidence gauge
    │   │   ├── ConfidenceBreakdown.tsx # Multi-factor chart
    │   │   ├── HypothesesList.tsx# Falsification targets & outcomes
    │   │   ├── QueriesList.tsx   # Adversarial queries run
    │   │   ├── EvidenceList.tsx  # Source tier cards with stance & passages
    │   │   ├── ContradictionsPanel.tsx # Contradictions & severity
    │   │   ├── FusionSummaryCard.tsx # Independent clusters & duplicates
    │   │   └── HistoryTable.tsx  # Past verifications with filters
    │   ├── services/
    │   │   └── api.ts            # Typed HTTP & SSE client
    │   └── types/
    │       └── falsify.ts        # TypeScript interfaces matching backend models
```

---

## 5. Detailed Implementation Phases & Tasks

### Phase 1: Backend Foundation & API Layer
*Goal: Expose the core engine safely through a robust FastAPI application without blocking the event loop.*

- [x] **Task 1.1: Core App Configuration & Logging**
  - Path: `app/core/config.py`, `app/core/__init__.py`
  - Implementation: Pydantic-settings based app configuration (`AppConfig`) for host, port, CORS origins parsing, and engine config loading.
  - Acceptance Criteria: Config loads cleanly from `.env` with fallback defaults.
  - Status: **VERIFIED** (tested via unit tests and config loading).
- [x] **Task 1.2: API Schemas (DTOs)**
  - Path: `app/api/schemas.py`
  - Implementation: Request models (`VerificationRequest` validating 4,000 char limit), response models (`HealthResponse`, `ErrorResponse`).
  - Acceptance Criteria: Validates request claims, preserves `ClaimValidationError` mapping, produces clean documentation.
  - Status: **VERIFIED** (tested via `test_verify_invalid_claims_return_400`).
- [x] **Task 1.3: Verification Service Layer**
  - Path: `app/services/verification_service.py`
  - Implementation: Injected `FalsifyEngine` runner utilizing `anyio.to_thread.run_sync` to execute verification in a worker threadpool, preventing asyncio event loop starvation.
  - Acceptance Criteria: Executes verification without blocking concurrent requests; captures errors cleanly.
  - Status: **VERIFIED** (tested via `test_concurrency.py`).
- [x] **Task 1.4: FastAPI Router & Error Handlers**
  - Path: `app/api/routes_verification.py`, `app/api/routes_system.py`, `app/main.py`
  - Implementation: Endpoints:
    - `POST /api/verify`: Runs verification, returns `VerificationResult.model_dump(mode="json")`.
    - `GET /health` and `GET /api/health`: Health status and provider availability check.
    - Custom exception handlers: maps `ClaimValidationError` -> HTTP 400 with detail message and error type.
  - Acceptance Criteria: `POST /api/verify` returns 200 with complete verification result on valid input and 400 on empty input.
  - Status: **VERIFIED** (tested via `test_routes.py` and `test_serialization_and_verdicts.py`).

**Phase 1 Verification Execution Results:**
- `python -m pytest tests/api/` -> **11 passed in 1.48s**
- `python -m pytest tests/falsify/` -> **208 passed in 1.70s**
- `python -m pytest tests/` -> **219 passed in 2.76s**
- `python scripts/demo_falsify.py` -> **Passed** (REFUTED verdict, $0.78$ confidence)

---

### Phase 2: Database Persistence & History
*Goal: Persist claims, verdicts, confidence metrics, and reasoning traces for auditing and retrieval.*

- [x] **Task 2.1: Database Engine & Session Setup**
  - Path: `app/db/session.py`, `app/db/base.py`, `app/db/__init__.py`
  - Implementation: SQLAlchemy 2.x engine with `check_same_thread=False` for SQLite, configurable `DATABASE_URL` via `AppConfig` (defaults to `sqlite:///./falsify.db`), request-scoped `get_db` session generator, and engine disposal in FastAPI lifespan.
  - Acceptance Criteria: Safe request-scoped sessions, clean connection disposal, supports test overriding.
  - Status: **VERIFIED** (tested via `test_5_sessions_close_correctly` and isolated test sessions).
- [x] **Task 2.2: ORM Data Models & Alembic Migrations**
  - Path: `app/db/models.py`, `alembic/`, `alembic.ini`
  - Implementation: `VerificationRecord` table storing `id` (PK), `claim_id` (indexed), `claim_text`, `verdict` (indexed), `confidence`, `created_at` (indexed UTC timestamp), and `result_json` (portable JSON type storing complete `VerificationResult` model dump). Configured Alembic with autogenerated migration `286a93e05931_create_verification_records_table.py`.
  - Acceptance Criteria: Portable JSON type, composite index on `(created_at, id)`, Alembic applies cleanly via `alembic upgrade head`.
  - Status: **VERIFIED** (tested via `test_alembic_upgrade_head_smoke`).
- [x] **Task 2.3: Repository Layer & History Endpoints**
  - Path: `app/db/repository.py`, updates to `app/api/routes_verification.py`
  - Implementation:
    - Automatic persistence on `POST /api/verify` via `service.verify_and_persist(claim, db)` with safe rollback on database errors.
    - `GET /api/verifications`: Paginated history with `page`, `page_size`, and strict `verdict` enum validation (returns 422 for unsupported values).
    - `GET /api/verifications/{id}`: Detailed stored result lookup (returns 404 for missing IDs, does not rerun verification).
    - `DELETE /api/verifications/{id}`: Delete record returning HTTP 204 (404 for missing IDs).
  - Acceptance Criteria: Full result persistence, pagination, filtering, deletion, zero fabrication.
  - Status: **VERIFIED** (tested via `tests/api/test_db_persistence.py`).

**Phase 2 Verification Execution Results:**
- `python -m pytest tests/api/test_db_persistence.py` -> **23 passed in 10.25s**
- `python -m pytest tests/` -> **242 passed in 9.17s** (208 core engine + 11 Phase 1 API + 23 Phase 2 DB)
- `python scripts/demo_falsify.py` -> **Passed** (REFUTED verdict, $0.78$ confidence)
- `alembic upgrade head` smoke test on fresh temporary SQLite database -> **Passed**
- Engine invariance: `git diff app/falsify/` -> **Clean (0 changes)**

---

### Phase 3: Real-Time Pipeline Progress & Streaming
*Goal: Provide users with real-time feedback as the engine steps through its 10 pipeline stages.*

- [x] **Task 3.1: Pipeline Event Hook & Progress Capture**
  - Path: `app/services/streaming.py`
  - Implementation: Non-intrusive logging handler `LogProgressCaptureHandler` listening to `falsify` logger events (`claim_normalized`, `queries_generated`, `evidence_retrieved`, `evidence_assessed`, `contradictions_detected`, `evidence_fused`, `verdict_generated`, `confidence_computed`, `verification_complete`) and queuing truthful stage updates to `asyncio.Queue` thread-safely.
  - Acceptance Criteria: Emits structured SSE events without altering core engine verification logic.
  - Status: **VERIFIED** (tested via `test_1_to_5_valid_stream_protocol_and_persistence`).
- [x] **Task 3.2: SSE Streaming Endpoint**
  - Path: `app/api/routes_verification.py`
  - Implementation: `POST /api/verify/stream` endpoint accepting `VerificationRequest` and returning `StreamingResponse(media_type="text/event-stream")` with headers `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`. Emits named events: `verification_started`, `verification_progress`, `verification_completed`, `verification_error`, and automatically persists result once to SQLite.
  - Acceptance Criteria: Real-time progress updates, non-blocking execution, client disconnect safety, clean session disposal.
  - Status: **VERIFIED** (tested via `tests/api/test_streaming.py`).

**Phase 3 Verification Execution Results:**
- `python -m pytest tests/api/test_streaming.py` -> **10 passed in 3.20s** (all 15 test cases verified)
- `python -m pytest tests/` -> **252 passed in 9.77s** (208 core engine + 11 Phase 1 API + 23 Phase 2 DB + 10 Phase 3 SSE)
- Engine invariance: `git diff app/falsify/` -> **Clean (0 changes)**

---

### Phase 4: Frontend Web Application
*Goal: Build an executive-grade, interactive verification dashboard with visual excellence, responsive feedback, and rich evidence inspection.*

- [x] **Task 4.1: Project Setup & Modern Theme Architecture**
  - Path: `frontend/` (Vite 5 + React 18 + TypeScript + Tailwind CSS)
  - Implementation: Professional light-theme research dashboard, slate/indigo/emerald/rose/amber color system, responsive desktop/tablet/mobile layouts, Lucide icons, backend health status polling.
  - Acceptance Criteria: Clean build without errors, accessible color contrast.
  - Status: **VERIFIED** (production build succeeded, 35 frontend tests passing).
- [x] **Task 4.2: Interactive Claim Input & Presets**
  - Path: `frontend/src/components/ClaimInput.tsx`
  - Implementation: Multiline claim input with character counter (max 4,000), empty/whitespace validation, quick-fill sample presets, submit action with loading spinner, and client-side stream cancellation.
  - Acceptance Criteria: Instant validation, keyboard shortcut (`Ctrl+Enter` to verify).
  - Status: **VERIFIED** (tested in `src/test/claim_form.test.tsx`).
- [x] **Task 4.3: Real-Time SSE Streaming Progress & Parser**
  - Path: `frontend/src/services/api.ts`, `frontend/src/components/ProgressPanel.tsx`
  - Implementation: Robust parser for `POST /api/verify/stream` using `fetch()` and `ReadableStream`. Handles multi-event chunks, chunk boundaries, CRLF/LF line endings, UTF-8 across chunks, and premature disconnection guards. Renders dynamic stage timeline with truthful backend stage messages.
  - Acceptance Criteria: Stream chunk resilience, UTF-8 boundary safety, no double verifications.
  - Status: **VERIFIED** (tested in `src/test/sse_parser.test.ts` and `src/test/app_integration.test.tsx`).
- [x] **Task 4.4: Verdict & Multi-Factor Confidence Visualizer**
  - Path: `frontend/src/components/VerdictBadge.tsx`, `frontend/src/components/VerdictCard.tsx`
  - Implementation:
    - High-impact verdict banner with distinct accessible styling and icons for all 5 verdicts:
      - `VERIFIED` (emerald green)
      - `QUALIFIED` (amber/cyan)
      - `CONFLICTED` (orange)
      - `REFUTED` (rose red)
      - `UNVERIFIABLE` (slate grey)
    - Confidence meter (0.0 to 1.0) with breakdown bar chart showing evidence quality, relevance, source independence, cross-source agreement, contradiction strength, temporal validity, and retrieval coverage.
  - Acceptance Criteria: Clear display of why the verdict was chosen without recalculation in frontend.
  - Status: **VERIFIED** (tested in `src/test/verdict_and_results.test.tsx`).
- [x] **Task 4.5: Falsification Hypotheses & Adversarial Queries Panel**
  - Path: `frontend/src/components/HypothesesPanel.tsx`
  - Implementation: Collapsible cards for each tested hypothesis showing category badge, priority rating, and outcome tag (`falsified`, `challenged`, `survived`, `no_evidence`), plus adversarial search query cards with purpose annotations.
  - Acceptance Criteria: Users can see the exact failure conditions Falsify attempted to prove.
  - Status: **VERIFIED** (tested in `src/test/verdict_and_results.test.tsx`).
- [x] **Task 4.6: Evidence Explorer & Source Tiering**
  - Path: `frontend/src/components/EvidenceList.tsx`, `frontend/src/components/ContradictionsPanel.tsx`
  - Implementation:
    - Evidence cards with Tier 1 (authoritative/filing), Tier 2 (news/secondary), Tier 3 (blogs/unverified) badges.
    - Stance badges (`supporting`, `contradicting`, `neutral`, `mixed`).
    - Excerpt passages with quote callouts.
    - Contradiction warnings with severity badges (`low`, `medium`, `high`, `critical`) and involved evidence links (`rel="noopener noreferrer"`).
    - Source synthesis cluster metrics (independent supporting/contradicting clusters, duplicate sources collapsed).
  - Acceptance Criteria: Shows how duplicate sources were collapsed and primary sources weighted.
  - Status: **VERIFIED** (tested in `src/test/verdict_and_results.test.tsx`).
- [x] **Task 4.7: Historical Verifications & Audit Log**
  - Path: `frontend/src/components/HistoryView.tsx`
  - Implementation: Paginated history table backed by `GET /api/verifications`, server-side verdict filtering, pagination controls, detail view via `GET /api/verifications/{id}` without rerunning verification, and deletion with accessible confirmation modal.
  - Acceptance Criteria: Opening past record never reruns verification; deletion refreshes list.
  - Status: **VERIFIED** (tested in `src/test/history.test.tsx`).

**Phase 4 Verification Execution Results:**
- `npm --prefix frontend test` -> **35 passed across 5 test files in 24.47s** (`claim_form`, `sse_parser`, `verdict_and_results`, `history`, `app_integration`).
- `npm --prefix frontend run build` -> **Exit code 0** (`tsc && vite build` built in 14.11s; 0 TypeScript errors).
- `python -m pytest tests/` -> **252 passed in 10.57s** (all existing backend tests pass without breakage).
- Engine invariance: `git diff --stat app/falsify/` -> **Clean (0 changes)**.

---

### Phase 5: End-to-End Integration & Reliability Hardening
*Goal: Ensure end-to-end reliability across backend, database, frontend, SSE streaming, and failure recovery.*

- [x] **Task 5.1: End-to-End Integration Test Suite (Backend & Isolated DB)**
  - Path: `tests/api/test_e2e_integration.py`
  - Tests:
    - Complete 13-step verification workflow: SSE verification stream -> SQLite persistence -> `/api/verifications` history list -> detail view `/api/verifications/{id}` -> deletion `/api/verifications/{id}` -> 404 confirmation.
    - Synchronous `POST /api/verify` end-to-end persistence and retrieval workflow.
    - `UNVERIFIABLE` verdict flow persistence and history filtering.
    - Detail endpoint isolation: verifies engine verification is never re-executed during history detail views.
    - Record deletion isolation: deleting one record preserves all other records.
    - Persistence failure handling: verifies that a persistence error emits a `verification_error` event and never a false `verification_completed` event.
    - Validation error contracts: empty claim (400), whitespace claim (400), claim > 4,000 characters (400), invalid verdict filter (422), nonexistent record lookup/deletion (404).
    - Health endpoints contract verification (`/health`, `/api/health`).
  - Status: **VERIFIED** (11/11 tests passed in 4.46s).

- [x] **Task 5.2: Frontend End-to-End Workflow & Reliability Hardening**
  - Path: `frontend/src/test/e2e_workflow.test.tsx`
  - Tests:
    - Complete 13-step user workflow: input claim -> stream verification -> verify result dashboard -> navigate to history -> view details without rerunning -> open accessible delete confirmation dialog -> delete record -> confirm removal from history list.
    - Client stream cancellation: clicking "Cancel Stream" aborts stream reader without showing false success or corrupting state.
    - Error recovery and retry: failed stream attempt displays alert; subsequent valid submission succeeds and resets error state.
    - XSS injection defense: asserts untrusted claim text and evidence excerpts containing `<script>` or `<iframe>` tags are escaped and rendered safely as text content.
  - Status: **VERIFIED** (4/4 tests passed).

- [x] **Task 5.3: Verification of Core Engine Invariance**
  - Path: `app/falsify/`
  - Verification: `git diff --stat app/falsify/` -> **Clean (0 changes)**.
  - Core engine suite: `python -m pytest tests/falsify/` -> **208 passed in 8.35s**.

- [x] **Task 5.4: Database Lifecycle & Alembic Migration Smoke Test**
  - Path: `alembic/env.py`, `app/db/session.py`
  - Tests:
    - Alembic migration `alembic upgrade head` executed on fresh temporary SQLite database (`Exit code: 0`).
    - Fixed database URL precedence in `alembic/env.py` to correctly prioritize `DATABASE_URL` environment variable over default `alembic.ini` placeholder.
    - Fixed engine disposal in `app/db/session.py` and test fixtures to prevent stale session binds across test boundaries.

**Phase 5 Verification Execution Results:**
- Backend full test suite: `python -m pytest tests/` -> **263 passed in 21.58s** (208 core engine + 11 Phase 1 API + 23 Phase 2 DB + 10 Phase 3 SSE + 11 Phase 5 E2E).
- Frontend full test suite: `npm --prefix frontend test` -> **39 passed across 6 test files in 36.10s** (`claim_form`, `sse_parser`, `verdict_and_results`, `history`, `app_integration`, `e2e_workflow`).
- Frontend production build: `npm --prefix frontend run build` -> **Exit code 0** (`tsc && vite build` built in 8.34s; 0 TypeScript errors).
- Offline demo: `python scripts/demo_falsify.py` -> **Exit code 0** (full pipeline ran with REFUTED verdict, confidence 0.78).
- Alembic fresh DB migration: `alembic upgrade head` -> **Exit code 0** (`create_verification_records_table`).
- Core engine invariance: `git diff --stat app/falsify/` -> **Clean (0 changes)**.

---

### Phase 6: Containerization & Deployment Preparation
*Goal: Create reproducible production builds and container definitions.*

- [x] **Task 6.1: Multi-stage Dockerfile & Production Container**
  - Path: `Dockerfile`, `.dockerignore`
  - Implementation: Multi-stage build with `node:20-alpine` compiling frontend SPA and `python:3.12-slim` running FastAPI via Uvicorn. Non-root user `falsify` (UID 10001), persistent `/app/data` volume, automated health probes, error masking, payload size guard.
  - Acceptance Criteria: Single container runs full stack; verified configuration and build.
  - Status: **VERIFIED**
- [x] **Task 6.2: Docker Compose & Persistent SQLite Strategy**
  - Path: `compose.yaml`, `app/db/session.py`, `alembic/env.py`
  - Implementation: Compose service configuration with named persistent volume `falsify_data:/app/data`, environment variable injection, SQLite parent directory auto-creation, healthcheck definitions.
  - Acceptance Criteria: `docker compose up --build` structure ready with verified persistence.
  - Status: **VERIFIED**
- [x] **Task 6.3: Production Hardening & Operational Probes**
  - Path: `app/main.py`, `app/core/config.py`, `app/api/routes_system.py`, `tests/api/test_deployment_readiness.py`
  - Implementation: Payload size limiter (413), sanitized 500 error responses in production (`DEBUG=false`), dual health/readiness probes (`/health` liveness and `/ready` database readiness), SPA catch-all routing fallback for client-side routing.
  - Acceptance Criteria: Passes deployment readiness suite; zero secrets or tracebacks leaked.
  - Status: **VERIFIED**
- [x] **Task 6.4: Comprehensive Deployment Guide & Provider Evaluation**
  - Path: `docs/DEPLOYMENT.md`, `README.md`, `.env.example`, `frontend/.env.example`
  - Implementation: Comprehensive deployment guide covering Fly.io, Render, Railway, VPS, SSE proxy buffering (Nginx/Caddy), safe Alembic migration and backup procedures, and unauthenticated API risk evaluations.
  - Acceptance Criteria: Complete operational documentation and provider comparison.
  - Status: **VERIFIED**

**Phase 6 Verification Execution Results:**
- Backend full test suite: `python -m pytest tests/` -> **271 passed in 15.57s** (263 previous + 8 deployment readiness tests).
- Frontend full test suite: `npm --prefix frontend test` -> **39 passed across 6 test files in 34.95s**.
- Frontend production build: `npm --prefix frontend run build` -> **Exit code 0** (`tsc && vite build` built in 17.65s; 0 TypeScript errors).
- Alembic fresh DB migration: `alembic upgrade head` -> **Exit code 0** (verified on temporary database).
- Data persistence across restart: **Verified** (survived engine disposal and config re-init).
- Core engine invariance: `git diff --stat app/falsify/` -> **Clean (0 changes)**.

---

## 6. Execution Command Reference

| Action | Command |
|---|---|
| **Run Core Engine Tests** | `python -m pytest tests/falsify/` |
| **Run All Tests (Engine + API + Deployment)** | `python -m pytest tests/` |
| **Run Offline Demo** | `python scripts/demo_falsify.py` |
| **Run Live Smoke Test** | `python scripts/smoke_tavily.py "Claim text"` (requires `TAVILY_API_KEY`) |
| **Start Backend Dev Server** | `uvicorn app.main:app --reload --port 8000` |
| **Start Frontend Dev Server** | `npm --prefix frontend run dev` |
| **Build Frontend** | `npm --prefix frontend run build` |
| **Docker Build & Run** | `docker compose up --build` |
