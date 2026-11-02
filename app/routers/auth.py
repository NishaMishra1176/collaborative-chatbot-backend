"""
Authentication API endpoints.
Provides user login, JWT issuance, and authenticated profile retrieval.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth_dependency import get_current_user
from app.services.auth_service import authenticate_user
from app.services.security import create_access_token

router = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and obtain JWT access token",
    responses={
        200: {"description": "Authentication successful; access token returned."},
        401: {"description": "Invalid credentials provided."},
        422: {"description": "Request validation error."},
        503: {"description": "Database connection unavailable."},
    },
)
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticates a user with email and password:
    - Finds user by email in database
    - Verifies password against stored bcrypt hash
    - Returns HTTP 401 if credentials do not match (without leaking whether email or password was wrong)
    - Returns signed JWT access token with expiration time
    """
    user = authenticate_user(db, credentials)

    token, expires_in = create_access_token(
        subject=user.id,
        extra_claims={"email": user.email},
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
    responses={
        200: {"description": "Current user profile."},
        401: {"description": "Missing, invalid, or expired authentication token."},
    },
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    Returns the profile of the currently authenticated user identified by the Bearer token:
    - Verifies JWT token signature and expiration
    - Returns user ID, name, email, and created_at timestamp
    - Never returns password hashes or JWT secrets
    """
    return current_user
