"""Dependency injection providers for FastAPI routes."""

from __future__ import annotations

from fastapi import Depends, Request

from app.falsify.engine import FalsifyEngine
from app.services.verification_service import VerificationService


def get_engine(request: Request) -> FalsifyEngine:
    """Retrieve application-scoped FalsifyEngine instance from app state."""
    return request.app.state.engine


def get_verification_service(
    engine: FalsifyEngine = Depends(get_engine),
) -> VerificationService:
    """Provide VerificationService configured with current engine."""
    return VerificationService(engine)
