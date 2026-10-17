"""API package containing routes, schemas, and dependencies."""

from app.api.routes_system import router as system_router
from app.api.routes_verification import router as verification_router

__all__ = ["system_router", "verification_router"]
