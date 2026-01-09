"""
REST API routes for Grid Backend.
"""

from fastapi import APIRouter

from grid_backend.api.auth import router as auth_router
from grid_backend.api.zones import router as zones_router
from grid_backend.api.debug import router as debug_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(zones_router, prefix="/zones", tags=["zones"])
api_router.include_router(debug_router, prefix="/debug", tags=["debug"])

__all__ = ["api_router"]
