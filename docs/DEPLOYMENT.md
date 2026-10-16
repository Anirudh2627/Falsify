# Falsify Production Deployment & Operational Guide

This document provides comprehensive instructions for deploying Falsify in production-like and cloud environments. It details containerization, persistence strategies, database migration workflows, operational probes, security hardening, reverse proxy configuration for Server-Sent Events (SSE), and a hosting provider evaluation.

---

## 1. Architecture Overview

Falsify is designed around a **unified container architecture**:

```
+--------------------------------------------------------------------------+
|                        Falsify Docker Container                          |
|                                                                          |
|  +---------------------------+       +--------------------------------+  |
|  |     Frontend SPA Bundle   |       |          FastAPI App           |  |
|  |     (Compiled Vite React) | ----> |  - /api/verify                 |  |
|  |     Served at / & /assets |       |  - /api/verify/stream (SSE)    |  |
|  +---------------------------+       |  - /api/verifications (CRUD)   |  |
|                                      |  - /health & /ready (Probes)   |  |
|                                      +--------------------------------+  |
|                                                      |                   |
|                                      +--------------------------------+  |
|                                      |        SQLAlchemy 2.x          |  |
|                                      +--------------------------------+  |
+------------------------------------------------------|-------------------+
                                                       v
                                      +--------------------------------+
                                      |     Mounted Storage Volume     |
                                      |     /app/data/falsify.db       |
                                      +--------------------------------+
```

### Why Unified Container Architecture?
1. **Single Port & Same Origin**: Browser requests to `/api/*` and `/health` route to the same origin without cross-origin preflight requests (CORS) or cookie/header mismatch issues.
2. **Minimal Resource Overhead**: Eliminates the need for a separate Node.js server in production; Vite compiles React to static assets served directly by Starlette's high-performance static file handler.
3. **Reproducible Multi-Stage Build**: Node.js and build tooling remain strictly in the builder stage (`node:20-alpine`), producing a lean production runner image based on `python:3.12-slim`.

*(Alternative Split Architecture: If the frontend is hosted separately on Vercel/Cloudflare Pages, set `VITE_API_BASE_URL=https://api.yourdomain.com` in the frontend build and `CORS_ORIGINS=https://your-frontend.vercel.app` on the backend).*

---

## 2. Hosting Provider Assessment & Recommendation

| Provider | Persistent Storage / SQLite | SSE Streaming Support | Build / Container Support | Free Tier / Pricing | Student / Hobby Suitability | Overall Verdict |
|---|---|---|---|---|---|---|
| **Fly.io** | **Yes** (Dedicated Fly Volumes attached to VM) | **Native** (HTTP/2 & keep-alive connections) | Native Dockerfile build | $5/month hobby credits; pay-as-you-go (~$2-3/mo) | High (Straightforward CLI, persistent volume support) | **Recommended (Best Fit)** |
| **Render** | **Requires Paid Plan** (Render Disks: $7/mo service + $0.25/GB disk) | Supported with 100s timeout limits | Native Docker / Git deploy | Free tier has ephemeral disk (wipes SQLite on sleep) | Medium (Free tier unsafe for SQLite) | Viable on Paid Disk only |
| **Railway** | **Requires Paid Plan** (Railway Volumes: $5/mo hobby minimum) | Native streaming support | Native Dockerfile detection | 30-day trial / $5 monthly hobby plan | Medium | Viable on Hobby Plan |
| **Self-Hosted / VPS** (Hetzner / DO) | **Yes** (Local Docker volume mapping) | Full control via Caddy / Nginx | Full Docker Compose support | Fixed $3.50 - $5/month | High (Full control, zero ephemeral disk issues) | **Recommended for Self-Hosting** |
| **Vercel / Netlify** | **No** (Serverless functions have no persistent disk) | Limited (Max duration timeouts on serverless) | Static frontend only | Free tier for frontend | High for frontend; Backend must be hosted elsewhere | Frontend Only |

### Recommended Platform: Fly.io
Fly.io is the top recommendation for Falsify because:
1. It provides persistent block storage (`flyctl volumes create`) that maps directly into `/app/data/falsify.db`.
2. It executes our production `Dockerfile` directly without requiring changes.
3. Its reverse proxy preserves long-lived streaming HTTP connections without aggressive timeouts.
4. It operates well within student budgets.

---

## 3. Persistent SQLite Storage Strategy

Falsify records verification history in SQLite. Container filesystems are disposable across redeployments and restarts.

### Operational Requirements:
1. **Storage Location**: In containerized deployments, set `DATABASE_URL=sqlite:////app/data/falsify.db` and mount a volume at `/app/data`.
2. **Directory Creation**: The application and Alembic migrations automatically verify that the parent directory (`/app/data`) exists before initializing connections.
3. **No Automatic Destructive Migrations**: The application never wipes, recreates, or runs destructive `Base.metadata.drop_all()` during normal startup.
4. **Volume Mapping**:
   - In Docker Compose: `falsify_data:/app/data`
   - In Fly.io: `fly volumes create falsify_data --size 1` mapped to `/app/data`

### Trade-offs: SQLite vs PostgreSQL
- **Why SQLite is retained**: Falsify is designed for reproducible local, offline, and single-instance verification workflows. SQLite requires zero background services, zero external connection credentials, and minimal memory footprint.
- **When to migrate to PostgreSQL**: If the application scales to multiple concurrent container replicas or horizontally autoscaled pods, SQLite's single-writer limitation will cause locking contention (`sqlite3.OperationalError: database is locked`). At that stage, replacing `sqlite:///...` with `postgresql://user:pass@host:5432/falsify` in `DATABASE_URL` uses SQLAlchemy's multi-host connection pooling without requiring core schema changes.

---

## 4. Production Environment Configuration

All environment variables can be set via `.env` or injected by your container orchestrator.

### Configuration Reference

| Variable | Default | Purpose / Production Guidance |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind IP address for server |
| `PORT` | `8000` | Bind port for Uvicorn |
| `DEBUG` | `false` | When `false`, 500 error traces and secrets are masked from clients |
| `DATABASE_URL` | `sqlite:///./falsify.db` | Connection string (`sqlite:////app/data/falsify.db` in containers) |
| `STATIC_DIR` | `frontend/dist` | Directory containing compiled frontend static assets |
| `CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated or JSON array) |
| `MAX_REQUEST_SIZE_BYTES` | `1048576` (1MB) | Rejects oversized payloads with HTTP 413 |
| `RATE_LIMIT_PER_MINUTE` | `0` | Per-IP rate limiting (set e.g. `60` in exposed public setups) |
| `TAVILY_API_KEY` | *(None)* | API key for live web evidence search |
| `LLM_API_KEY` | *(None)* | API key for OpenAI-compatible reasoning model |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | LLM endpoint URL |
| `LLM_MODEL` | `gpt-4o-mini` | LLM model identifier |
| `VITE_API_BASE_URL` | *(Empty)* | (Frontend build only) Leave empty for same-origin production |

---

## 5. Security & Unauthenticated API Protection

### Threat Model & Exposure Limitations
Falsify endpoints currently have **no user authentication system**. When exposing the service:
- **Paid Quota Consumption**: `POST /api/verify` and `POST /api/verify/stream` trigger external retrieval (Tavily) and LLM queries that bill against your account.
- **Stored Verification Disclosure**: `GET /api/verifications` lists all prior claims and verification traces.
- **Unwanted Deletion**: `DELETE /api/verifications/{id}` allows anyone with network access to delete records.

### Built-in Hardening:
1. **Payload Size Guard**: Incoming requests exceeding `MAX_REQUEST_SIZE_BYTES` are rejected with HTTP 413 before parsing.
2. **Error Masking**: With `DEBUG=false`, internal server errors log full diagnostic details server-side while returning generic JSON responses (`"An internal server error occurred."`) without stack traces or path disclosures.
3. **Non-Root Execution**: Container runs under dedicated system user `falsify` (UID 10001).
4. **No Admin Interface Exposed**: No web-based SQLite browser or raw SQL terminal is mounted.

### Recommended Production Ingress Protection:
Before making Falsify publicly available to the open internet:
- Place the application behind **Cloudflare Zero Trust / Cloudflare Access** or a reverse proxy with **HTTP Basic Authentication**.
- Alternatively, restrict ingress network access using firewall security groups, a VPN (Tailscale/WireGuard), or internal VPC peering.

*(Note: CORS headers do NOT provide authentication or access control; they only instruct browsers on cross-origin resource sharing).*

---

## 6. Health & Operational Probes

Falsify provides two distinct probe endpoints:

### Liveness Probe (`GET /health` or `GET /api/health`)
- Fast, non-blocking check verifying that the Python application process is active and the engine pipeline is initialized.
- Does **not** execute AI verification or query paid external APIs.
- Returns HTTP 200:
  ```json
  {
    "status": "ok",
    "app_name": "Falsify API",
    "app_version": "1.0.0",
    "engine_version": "1.0.0",
    "retrieval_provider": "tavily",
    "llm_configured": true,
    "database_status": "connected",
    "timestamp": "2026-10-15T13:20:00Z"
  }
  ```

### Readiness Probe (`GET /ready` or `GET /api/ready`)
- Verifies that the SQLite database is reachable and accepting queries (`SELECT 1`).
- Returns HTTP 200 when ready:
  ```json
  {"status": "ready", "database": "connected", "timestamp": "2026-10-15T13:20:00Z"}
  ```
- Returns HTTP 503 if the database is locked or unavailable:
  ```json
  {"status": "unready", "database": "disconnected", "timestamp": "2026-10-15T13:20:00Z"}
  ```

---

## 7. Reverse Proxy Configuration for Server-Sent Events (SSE)

When hosting behind Nginx, Caddy, or Cloudflare, reverse proxy buffering will break real-time SSE progress streaming unless properly configured.

### Nginx Configuration
```nginx
server {
    listen 80;
    server_name falsify.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # --- Critical SSE Buffering & Timeout Directives ---
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

### Caddy Configuration
```caddy
falsify.example.com {
    reverse_proxy 127.0.0.1:8000 {
        # Flush responses immediately for SSE streaming
        flush_interval -1
    }
}
```

### Cloudflare Notes
- Ensure **Cloudflare Buffering** or **Rocket Loader** does not buffer `text/event-stream` responses. Cloudflare respects `Cache-Control: no-cache` and `Content-Type: text/event-stream`.

---

## 8. Database Migration & Safe Backup Procedure

Alembic manages database schema versioning.

### Inspect Current Revision
```bash
alembic current
```

### View Migration History
```bash
alembic history --verbose
```

### Apply Pending Migrations
```bash
alembic upgrade head
```

### Production Pre-Migration Backup Procedure
Always snapshot the SQLite database before running schema migrations:

```bash
# 1. Hot online backup using sqlite3 CLI (safe while app is running)
sqlite3 /app/data/falsify.db ".backup /app/data/falsify_backup_$(date +%Y%m%d%H%M%S).db"

# 2. Or using standard file copy when database is idle:
cp /app/data/falsify.db /app/data/falsify_pre_migration.db
```

### Restoring from Backup
```bash
# Stop application process
# Restore database file
cp /app/data/falsify_backup_YYYYMMDDHHMMSS.db /app/data/falsify.db
# Restart application process
```

### Migration Failure Recovery
If a migration fails mid-way:
```bash
# Step back 1 revision
alembic downgrade -1

# Or restore pre-migration database snapshot
cp /app/data/falsify_pre_migration.db /app/data/falsify.db
```

---

## 9. Step-by-Step Deployment Workflows

### Option A: Local Container Testing via Docker Compose
1. Ensure `.env` is configured:
   ```bash
   cp .env.example .env
   ```
2. Build and launch:
   ```bash
   docker compose up --build -d
   ```
3. Inspect logs:
   ```bash
   docker compose logs -f falsify
   ```
4. Check health probe:
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/ready
   ```
5. Open browser at `http://localhost:8000`.

### Option B: Deploying to Fly.io (Recommended Cloud Option)
1. Install Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. Authenticate: `fly auth login`
3. Launch app configuration (without deploying immediately):
   ```bash
   fly launch --no-deploy
   ```
4. Create persistent volume for SQLite storage:
   ```bash
   fly volumes create falsify_data --region iad --size 1
   ```
5. Attach volume in `fly.toml`:
   ```toml
   [mounts]
     source = "falsify_data"
     destination = "/app/data"

   [env]
     DATABASE_URL = "sqlite:////app/data/falsify.db"
     STATIC_DIR = "/app/frontend/dist"
   ```
6. Set secrets:
   ```bash
   fly secrets set TAVILY_API_KEY="tvly-..." LLM_API_KEY="sk-..."
   ```
7. Deploy:
   ```bash
   fly deploy
   ```

---

## 10. Troubleshooting Guide

| Issue | Root Cause | Solution |
|---|---|---|
| **SSE progress bar does not update until completed** | Reverse proxy or CDN is buffering `text/event-stream` chunks | Add `proxy_buffering off;` and `proxy_read_timeout 300s;` in Nginx, or `flush_interval -1` in Caddy. |
| **`sqlite3.OperationalError: unable to open database file`** | Parent directory `/app/data` does not exist or has bad permissions | Ensure Docker volume is mounted at `/app/data` and container runs with user `falsify` owning `/app/data`. |
| **CORS errors when using split frontend** | Frontend URL not present in backend CORS origins | Add frontend URL (e.g. `https://falsify.vercel.app`) to `CORS_ORIGINS` in `.env`. |
| **500 error returned with `"An internal server error occurred"`** | Unexpected backend exception in production mode | Inspect server stdout/stderr logs (`docker logs falsify-app`) for `event=unhandled_exception` traceback. |
| **HTTP 413 Payload Too Large** | Request body exceeded `MAX_REQUEST_SIZE_BYTES` | Increase `MAX_REQUEST_SIZE_BYTES` in `.env` if legitimate claims require larger payloads. |
| **Cold start delays on free tier hosts** | Host spins down container after inactivity (e.g. Render free tier) | Use Fly.io or configure a periodic uptime monitor pinging `/health`. |
