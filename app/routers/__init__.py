"""
FastAPI API route handlers package.
"""

from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.chat import router as chat_router

__all__ = ["auth_router", "users_router", "chat_router"]
