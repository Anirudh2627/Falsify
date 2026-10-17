"""Database package exposing Base, session management, and models."""

from app.db.base import Base
from app.db.models import VerificationRecord
from app.db.session import dispose_engine, get_db, get_engine

__all__ = ["Base", "VerificationRecord", "get_db", "get_engine", "dispose_engine"]
