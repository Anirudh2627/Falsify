"""Alembic environment script configured for Falsify."""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_app_config
from app.db.base import Base
import app.db.models  # ensure models are imported for metadata registration # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def get_url() -> str:
    """Read database URL from environment, config option, or application settings."""
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    custom_url = config.get_main_option("sqlalchemy.url")
    if custom_url and custom_url.strip() and not custom_url.startswith("driver://"):
        return custom_url.strip()
    return get_app_config().database_url


def _ensure_sqlite_parent_dir(db_url: str) -> None:
    if db_url.startswith("sqlite:///") and ":memory:" not in db_url:
        db_path_str = db_url[len("sqlite:///"):]
        if db_path_str:
            Path(db_path_str).resolve().parent.mkdir(parents=True, exist_ok=True)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    _ensure_sqlite_parent_dir(url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Required for SQLite column alterations
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    db_url = get_url()
    _ensure_sqlite_parent_dir(db_url)
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    connectable = create_engine(
        db_url,
        connect_args=connect_args,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # Required for SQLite
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
