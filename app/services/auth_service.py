"""
Business logic service for user registration and authentication operations.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from fastapi import HTTPException, status

from app.models.user import User
from app.schemas.user import UserRegisterRequest
from app.schemas.auth import LoginRequest
from app.services.security import hash_password, verify_password

logger = logging.getLogger(__name__)


def register_user(db: Session, user_in: UserRegisterRequest) -> User:
    """
    Registers a new user in the database.

    Raises:
        HTTPException(409): If the email is already registered.
        HTTPException(503): If the database is unreachable or misconfigured.
    """
    normalized_email = user_in.email.strip().lower()

    try:
        existing_user = db.query(User).filter(User.email == normalized_email).first()
    except OperationalError as exc:
        logger.error("Database connection error during user registration: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Database service is unavailable. Please verify your MySQL server "
                "is running and credentials in .env are correct."
            ),
        ) from exc
    except SQLAlchemyError as exc:
        logger.error("Database error during user registration: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred during registration.",
        ) from exc

    if existing_user:
        logger.info("Registration rejected: duplicate email %s", normalized_email)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists.",
        )

    # Securely hash password
    hashed_pwd = hash_password(user_in.password)

    new_user = User(
        name=user_in.name.strip(),
        email=normalized_email,
        password_hash=hashed_pwd,
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info("User registered successfully with id: %s", new_user.id)
        return new_user
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Failed to persist new user to database: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save user account to database.",
        ) from exc


def authenticate_user(db: Session, credentials: LoginRequest) -> User:
    """
    Authenticates a user by email and password.

    Raises:
        HTTPException(401): If credentials are invalid (without revealing whether
                            the email or password was wrong).
        HTTPException(503): If the database is unreachable or misconfigured.
    """
    normalized_email = credentials.email.strip().lower()

    try:
        user = db.query(User).filter(User.email == normalized_email).first()
    except OperationalError as exc:
        logger.error("Database connection error during login: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Database service is unavailable. Please verify your MySQL server "
                "is running and credentials in .env are correct."
            ),
        ) from exc
    except SQLAlchemyError as exc:
        logger.error("Database error during login query: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred during authentication.",
        ) from exc

    # Constant time check pattern: always verify password even if user is None
    # to protect against timing attacks
    dummy_hash = "$2b$12$e80yq9j2Wv80q9j2Wv80quq80q9j2Wv80q9j2Wv80q9j2Wv80q9j2"
    password_to_check = user.password_hash if user else dummy_hash
    is_valid = verify_password(credentials.password, password_to_check)

    if not user or not is_valid:
        logger.warning("Failed login attempt for email: %s", normalized_email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info("User %s authenticated successfully.", user.id)
    return user


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """
    Finds a user by their primary key id.
    """
    try:
        return db.query(User).filter(User.id == user_id).first()
    except OperationalError as exc:
        logger.error("Database connection error fetching user by id: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is unavailable.",
        ) from exc
    except SQLAlchemyError as exc:
        logger.error("Database error fetching user by id: %s", exc)
        return None
