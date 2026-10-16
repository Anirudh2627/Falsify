"""Database engine, session factory, and FastAPI dependencies."""

from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_app_config

logger = logging.getLogger("falsify")

# Global engine and session factory singletons
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def ensure_sqlite_parent_dir(db_url: str) -> None:
    """Ensure parent directory exists for file-based SQLite database."""
    if db_url.startswith("sqlite:///") and ":memory:" not in db_url:
        from pathlib import Path
        db_path_str = db_url[len("sqlite:///"):]
        if db_path_str:
            parent_dir = Path(db_path_str).resolve().parent
            if parent_dir and not parent_dir.exists():
                parent_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"event=sqlite_directory_created path={parent_dir}")


def get_engine() -> Engine:
    """Retrieve or lazily initialize the SQLAlchemy Engine singleton."""
    global _engine
    if _engine is None:
        config = get_app_config()
        db_url = config.database_url

        connect_args: dict[str, Any] = {}
        if db_url.startswith("sqlite"):
            # Ensure database directory exists before connecting
            ensure_sqlite_parent_dir(db_url)
            # Required for SQLite concurrency in FastAPI
            connect_args["check_same_thread"] = False

        _engine = create_engine(
            db_url,
            connect_args=connect_args,
            echo=False,
            future=True,
        )
        logger.info(f"event=db_engine_created url_prefix={db_url.split('://')[0]}")
        if config.auto_create_tables:
            from app.db.base import Base
            Base.metadata.create_all(bind=_engine)
            logger.info("event=db_auto_create_tables_executed")
        else:
            logger.info("event=db_schema_managed_by_alembic")
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Retrieve or lazily initialize the sessionmaker singleton."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    """FastAPI request-scoped database session dependency.

    Ensures each request gets an isolated session that is cleanly closed upon completion.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def dispose_engine() -> None:
    """Dispose active engine connection pools (e.g. during application shutdown or test teardown)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("event=db_engine_disposed")


def set_custom_engine(custom_engine: Engine | None) -> None:
    """Configure a custom engine (used for isolated test databases)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = custom_engine
    if custom_engine is not None:
        _session_factory = sessionmaker(
            bind=_engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    else:
        _session_factory = None
