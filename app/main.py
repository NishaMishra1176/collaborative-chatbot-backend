"""
Main entry point for the Collaborative Chatbot Backend FastAPI application.
Phase 4: User Registration, JWT Authentication, and Google Gemini AI Chat API.
"""

import logging
import urllib.parse
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import check_db_connection, create_tables, get_db
from app.routers import auth_router, chat_router, users_router
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.auth_service import authenticate_user
from app.services.security import create_access_token

# ---------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("collaborative_chatbot")


# ---------------------------------------------------------
# Application Lifespan (Startup & Shutdown)
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events cleanly.
    Checks database reachability non-blockingly on startup.
    """
    logger.info("Starting up %s (version: %s)...", settings.PROJECT_NAME, settings.VERSION)
    logger.info("Environment: %s | Debug mode: %s", settings.ENVIRONMENT, settings.DEBUG)
    logger.info("Configured Gemini model: %s", settings.GEMINI_MODEL)

    # Safely check if database is online without blocking startup if offline
    is_connected, msg = check_db_connection()
    if is_connected:
        logger.info("Database connection established. Ensuring tables exist...")
        try:
            create_tables()
            logger.info("Database tables verified.")
        except Exception as exc:
            logger.warning("Unable to verify/create database tables: %s", exc)
    else:
        logger.warning("Database connection could not be established: %s", msg)
        logger.warning(
            "The API is running, but database operations will return HTTP 503 "
            "until MySQL is running with valid credentials in .env."
        )

    yield

    logger.info("Shutting down %s...", settings.PROJECT_NAME)


# ---------------------------------------------------------
# FastAPI App Initialization
# ---------------------------------------------------------
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------
# CORS (Cross-Origin Resource Sharing) Middleware
# ---------------------------------------------------------
origins = settings.cors_origins_list
allow_credentials = False if "*" in origins else True

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Global Error Handlers
# ---------------------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Handles standard HTTP exceptions (e.g. 401 Unauthorized, 404 Not Found, 409 Conflict, 502 Bad Gateway).
    """
    logger.warning(
        "HTTP error %s on %s %s: %s",
        exc.status_code,
        request.method,
        request.url.path,
        exc.detail,
    )
    headers = getattr(exc, "headers", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "status_code": exc.status_code,
            "detail": exc.detail,
        },
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handles validation errors from request bodies, query parameters, or path variables.
    Uses jsonable_encoder to ensure Pydantic custom exception contexts serialize cleanly.
    """
    logger.warning("Validation error on %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "status_code": 422,
            "detail": "Request validation failed",
            "errors": jsonable_encoder(exc.errors()),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catches all unhandled exceptions, logs the error, and returns a safe 500 error response.
    Prevents leaking internal stack traces or secrets in responses.
    """
    logger.exception("Unhandled server error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "status_code": 500,
            "detail": "An internal server error occurred.",
        },
    )


# ---------------------------------------------------------
# Include API Routers (API v1 and legacy aliases)
# ---------------------------------------------------------
# Primary versioned endpoints (/api/v1/...)
app.include_router(chat_router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(users_router, prefix="/api/v1/users", tags=["Users"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])

# OAuth2 compatibility endpoint for Swagger UI Authorize dialog
@app.post("/api/auth/login", response_model=TokenResponse, include_in_schema=False)
async def oauth2_token_login(request: Request, db: Session = Depends(get_db)):
    """
    OAuth2 compatibility token endpoint for Swagger UI's Authorize dialog.
    Supports both application/x-www-form-urlencoded (Swagger OAuth2 flow)
    and application/json.
    """
    ct = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in ct:
        body = await request.body()
        params = urllib.parse.parse_qs(body.decode("utf-8"))
        email = params.get("username", [None])[0] or params.get("email", [None])[0]
        password = params.get("password", [None])[0]
        if not email or not password:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "status": "error",
                    "status_code": 422,
                    "detail": "Username (email) and password are required.",
                },
            )
        credentials = LoginRequest(email=email, password=password)
    else:
        body = await request.json()
        credentials = LoginRequest(**body)

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


# Direct aliases (/api/...) for backward compatibility
app.include_router(chat_router, prefix="/api/chat", tags=["Chat"], include_in_schema=False)
app.include_router(users_router, prefix="/api/users", tags=["Users"], include_in_schema=False)
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"], include_in_schema=False)


# ---------------------------------------------------------
# Core Endpoints (Root & Health)
# ---------------------------------------------------------
@app.get("/", tags=["General"], summary="Root endpoint")
async def root():
    """
    Welcome endpoint returning basic API metadata and helpful documentation links.
    """
    return {
        "message": f"Welcome to the {settings.PROJECT_NAME} API",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs",
        "health_check": "/health",
        "auth_endpoints": {
            "register": "POST /api/v1/users/register",
            "login": "POST /api/v1/auth/login",
            "profile": "GET /api/v1/auth/me",
        },
        "chat_endpoints": {
            "chat": "POST /api/v1/chat",
        },
    }


@app.get("/health", tags=["Health"], summary="Health check endpoint")
async def health_check():
    """
    Health check endpoint returning a simple JSON response confirming
    the backend service is up and running.
    """
    db_connected, _ = check_db_connection()
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": "connected" if db_connected else "disconnected",
        "gemini_model": settings.GEMINI_MODEL,
    }


# ---------------------------------------------------------
# Local Execution Entry Point
# ---------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
