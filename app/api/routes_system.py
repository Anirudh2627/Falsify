import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import get_engine
from app.api.schemas import HealthResponse
from app.core.config import get_app_config
from app.db.session import get_session_factory
from app.falsify.engine import FalsifyEngine
from app.falsify.llm.provider import NullLLM

logger = logging.getLogger("falsify")

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
@router.get("/api/health", response_model=HealthResponse)
async def get_health(engine: FalsifyEngine = Depends(get_engine)) -> HealthResponse:
    """Return system liveness status, engine version, and provider configuration."""
    config = get_app_config()
    retriever = getattr(engine, "_retriever", None)
    retriever_name = getattr(retriever, "name", "unknown") if retriever else "unknown"
    llm = getattr(engine, "_llm", None)
    llm_configured = llm is not None and not isinstance(llm, NullLLM)

    # Fast non-blocking check on session factory
    db_status = "connected"
    try:
        factory = get_session_factory()
        with factory() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning(f"event=health_db_check_failed error={str(exc)[:120]}")
        db_status = "unavailable"

    return HealthResponse(
        status="ok",
        app_name=config.app_name,
        app_version=config.app_version,
        engine_version="1.0.0",
        retrieval_provider=retriever_name,
        llm_configured=llm_configured,
        database_status=db_status,
        timestamp=datetime.now(UTC),
    )


@router.get("/ready")
@router.get("/api/ready")
async def get_readiness() -> JSONResponse:
    """Readiness probe checking database connectivity and operational availability."""
    db_ok = False
    try:
        factory = get_session_factory()
        with factory() as session:
            session.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        logger.error(f"event=readiness_db_check_failed error={str(exc)[:160]}")
        db_ok = False

    if not db_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unready",
                "database": "disconnected",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "ready",
            "database": "connected",
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
