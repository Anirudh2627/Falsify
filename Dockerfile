# Multi-stage Dockerfile for Falsify Production Deployment

# --- Stage 1: Build Frontend Assets ---
FROM node:20-alpine AS frontend-builder
WORKDIR /build

# Install dependencies
COPY frontend/package*.json ./
RUN npm install

# Build static SPA assets
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Production Python Runtime ---
FROM python:3.12-slim AS runner

# Operational environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    DATABASE_URL=sqlite:////app/data/falsify.db \
    STATIC_DIR=/app/frontend/dist

# Install minimal OS dependencies for health checking
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root system user and group
RUN groupadd -g 10001 falsify && \
    useradd -u 10001 -g falsify -m -s /bin/bash falsify

WORKDIR /app

# Prepare persistent data directory with proper ownership
RUN mkdir -p /app/data /app/frontend/dist && \
    chown -R falsify:falsify /app

# Install Python backend dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and migrations
COPY app/ ./app
COPY alembic/ ./alembic
COPY alembic.ini .
COPY pyproject.toml .

# Copy compiled frontend SPA bundle from builder stage
COPY --from=frontend-builder --chown=falsify:falsify /build/dist ./frontend/dist

# Ensure falsify user ownership of the application directory
RUN chown -R falsify:falsify /app

# Persistent volume mount point for SQLite database
VOLUME ["/app/data"]

EXPOSE 8000

# Switch to non-root user
USER falsify

# Container liveness health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Production server startup
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
