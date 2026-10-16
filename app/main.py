"""FastAPI main entrypoint and application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes_system import router as system_router
from app.api.routes_verification import router as verification_router
from app.core.config import get_app_config
from app.falsify.engine import build_default_engine
from app.falsify.exceptions import ClaimValidationError

logger = logging.getLogger("falsify")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager: initializes engine on startup."""
    config = get_app_config()
    logger.info(f"event=falsify_api_starting version={config.app_version}")

    # Build and attach production default engine to application state
    # Allows injection or overriding in tests via app.state.engine
    if not hasattr(app.state, "engine") or app.state.engine is None:
        app.state.engine = build_default_engine()

    retriever = getattr(app.state.engine, "_retriever", None)
    retriever_name = getattr(retriever, "name", "unknown") if retriever else "unknown"
    logger.info(f"event=falsify_engine_ready retriever={retriever_name}")
    yield
    from app.db.session import dispose_engine
    dispose_engine()
    logger.info("event=falsify_api_stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = get_app_config()

    app = FastAPI(
        title=config.app_name,
        version=config.app_version,
        description="Claim-level adversarial verification API service.",
        lifespan=lifespan,
    )

    # Environment-based CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request payload size limiter
    @app.middleware("http")
    async def request_size_limiter(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > config.max_request_size_bytes:
                    logger.warning(
                        f"event=payload_too_large size={length} max_allowed={config.max_request_size_bytes}"
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"Request payload too large ({length} bytes > {config.max_request_size_bytes} bytes limit)",
                            "error_type": "PayloadTooLarge",
                        },
                    )
            except ValueError:
                pass
        return await call_next(request)

    # In-memory request rate limiter (sliding window)
    import time
    from collections import defaultdict
    ip_request_timestamps: dict[str, list[float]] = defaultdict(list)

    @app.middleware("http")
    async def rate_limiting_middleware(request: Request, call_next):
        if config.rate_limit_per_minute > 0:
            if request.url.path not in ("/health", "/api/health", "/ready", "/api/ready"):
                client_ip = request.client.host if request.client else "unknown"
                now = time.time()
                cutoff = now - 60.0
                timestamps = [t for t in ip_request_timestamps[client_ip] if t > cutoff]
                if len(timestamps) >= config.rate_limit_per_minute:
                    logger.warning(
                        f"event=rate_limit_exceeded ip={client_ip} limit={config.rate_limit_per_minute}/min"
                    )
                    return JSONResponse(
                        status_code=429,
                        content={
                            "detail": f"Rate limit exceeded: maximum {config.rate_limit_per_minute} requests per minute.",
                            "error_type": "RateLimitExceeded",
                        },
                        headers={"Retry-After": "60"},
                    )
                timestamps.append(now)
                ip_request_timestamps[client_ip] = timestamps
        return await call_next(request)

    # Register custom exception handlers
    @app.exception_handler(ClaimValidationError)
    async def claim_validation_exception_handler(
        request: Request, exc: ClaimValidationError
    ) -> JSONResponse:
        logger.warning(f"event=claim_validation_failed error={str(exc)[:160]}")
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc), "error_type": "ClaimValidationError"},
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Check if any validation error stems from ClaimValidationError
        for err in exc.errors():
            ctx = err.get("ctx", {})
            if "error" in ctx and isinstance(ctx["error"], ClaimValidationError):
                return JSONResponse(
                    status_code=400,
                    content={"detail": str(ctx["error"]), "error_type": "ClaimValidationError"},
                )
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(), "error_type": "RequestValidationError"},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "error_type": "HTTPException"},
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            f"event=unhandled_exception path={request.url.path} error={type(exc).__name__}: {str(exc)[:160]}"
        )
        if config.debug:
            import traceback
            return JSONResponse(
                status_code=500,
                content={
                    "detail": str(exc),
                    "error_type": type(exc).__name__,
                    "traceback": traceback.format_exc(),
                },
            )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An internal server error occurred.",
                "error_type": "InternalServerError",
            },
        )

    # Include route modules
    app.include_router(system_router)
    app.include_router(verification_router)

    # Static files and Single Page Application (SPA) routing
    static_path_str = config.static_dir or "frontend/dist"
    static_dir = Path(static_path_str).resolve()
    index_html = static_dir / "index.html"

    if static_dir.exists() and index_html.exists():
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            reserved_prefixes = ("api/", "health", "ready", "docs", "openapi.json", "redoc")
            if any(full_path == r or full_path.startswith(f"{r}/") or full_path.startswith(r) for r in reserved_prefixes):
                return JSONResponse(status_code=404, content={"detail": "Not Found"})
            file_target = static_dir / full_path
            if full_path and file_target.is_file():
                return FileResponse(file_target)
            return FileResponse(index_html)

    return app


app = create_app()
