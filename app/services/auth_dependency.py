"""
Reusable authentication dependency for FastAPI routes.
Validates signed JWT tokens and resolves the current authenticated user.
"""

import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt

from app.database import get_db
from app.models.user import User
from app.services.auth_service import get_user_by_id
from app.services.security import decode_access_token

logger = logging.getLogger(__name__)

# OAuth2 scheme configures Swagger UI to show an Authorize button
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    description="Enter JWT Bearer token obtained from POST /api/auth/login",
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency that extracts, verifies, and decodes the JWT access token,
    and returns the authenticated User instance.

    Raises:
        HTTPException(401): On expired token, invalid token signature, or deleted user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError as exc:
        logger.warning("Access rejected: JWT token has expired.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        logger.warning("Access rejected: Invalid JWT token - %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id_str: str | None = payload.get("sub")
    if not user_id_str:
        logger.warning("Access rejected: JWT payload missing subject claim ('sub').")
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError) as exc:
        logger.warning("Access rejected: JWT 'sub' claim is not a valid integer id.")
        raise credentials_exception from exc

    user = get_user_by_id(db, user_id=user_id)
    if user is None:
        logger.warning("Access rejected: User ID %s not found in database.", user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
