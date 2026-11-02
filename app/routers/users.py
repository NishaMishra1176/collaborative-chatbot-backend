"""
User management API endpoints.
Provides registration for new user accounts.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.user import UserRegisterRequest, UserResponse
from app.services.auth_service import register_user

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    responses={
        201: {"description": "User registered successfully."},
        400: {"description": "Invalid input data."},
        409: {"description": "User with this email already exists."},
        422: {"description": "Validation error."},
        503: {"description": "Database connection unavailable."},
    },
)
def register(
    user_in: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Creates a new user account:
    - Validates required fields and email syntax
    - Hashes password using bcrypt
    - Rejects duplicate email addresses with HTTP 409
    - Returns safe user profile (excluding password hash)
    """
    new_user = register_user(db, user_in)
    return new_user
