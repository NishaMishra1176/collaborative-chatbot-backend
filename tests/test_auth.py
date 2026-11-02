"""
Automated tests for User Registration, Login, and JWT Authentication.
Uses an isolated in-memory SQLite database via FastAPI dependency overrides.
"""

from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services.security import create_access_token

# Setup in-memory SQLite database shared across the test session
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Creates database schema before tests and drops after."""
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


# --------------------------------------------------------------------------
# Test Cases: User Registration
# --------------------------------------------------------------------------
def test_user_registration_success(client):
    """POST /api/users/register should create a user and return a safe profile."""
    payload = {
        "name": "Alice Smith",
        "email": "alice@example.com",
        "password": "Password123!",
    }
    response = client.post("/api/users/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Alice Smith"
    assert data["email"] == "alice@example.com"
    assert "id" in data
    assert "created_at" in data
    # Security check: Password and hash MUST NEVER be in response
    assert "password" not in data
    assert "password_hash" not in data


def test_user_registration_duplicate_email(client):
    """POST /api/users/register should reject duplicate emails with HTTP 409."""
    payload = {
        "name": "Alice Duplicate",
        "email": "alice@example.com",
        "password": "DifferentPass456!",
    }
    response = client.post("/api/users/register", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert "already exists" in data["detail"].lower()


def test_user_registration_invalid_email(client):
    """POST /api/users/register should reject invalid email format with HTTP 422."""
    payload = {
        "name": "Bad Email User",
        "email": "not-an-email",
        "password": "Password123!",
    }
    response = client.post("/api/users/register", json=payload)
    assert response.status_code == 422


def test_user_registration_short_password(client):
    """POST /api/users/register should reject passwords shorter than 6 characters."""
    payload = {
        "name": "Short Pass User",
        "email": "short@example.com",
        "password": "123",
    }
    response = client.post("/api/users/register", json=payload)
    assert response.status_code == 422


# --------------------------------------------------------------------------
# Test Cases: User Login & JWT Generation
# --------------------------------------------------------------------------
def test_login_success(client):
    """POST /api/auth/login should authenticate user and return a valid JWT token."""
    payload = {
        "email": "alice@example.com",
        "password": "Password123!",
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"].lower() == "bearer"
    assert data["expires_in"] > 0
    # Security check: Never return secrets or passwords
    assert "password" not in data
    assert "password_hash" not in data


def test_login_wrong_password(client):
    """POST /api/auth/login with wrong password should return HTTP 401."""
    payload = {
        "email": "alice@example.com",
        "password": "WrongPassword!",
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Invalid email or password"


def test_login_nonexistent_email(client):
    """POST /api/auth/login with unknown email should return generic HTTP 401."""
    payload = {
        "email": "nonexistent@example.com",
        "password": "Password123!",
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 401
    data = response.json()
    # Must not reveal that the email doesn't exist
    assert data["detail"] == "Invalid email or password"


# --------------------------------------------------------------------------
# Test Cases: Protected Endpoint (/api/auth/me)
# --------------------------------------------------------------------------
def test_protected_me_endpoint_success(client):
    """GET /api/auth/me with valid Bearer token should return user profile."""
    # First login to obtain token
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "Password123!"},
    )
    token = login_resp.json()["access_token"]

    # Access /api/auth/me with token
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert data["name"] == "Alice Smith"
    assert "password" not in data
    assert "password_hash" not in data


def test_protected_me_endpoint_missing_token(client):
    """GET /api/auth/me without token should return HTTP 401."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_protected_me_endpoint_invalid_token(client):
    """GET /api/auth/me with an invalid token string should return HTTP 401."""
    headers = {"Authorization": "Bearer this-is-not-a-valid-token"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401
    data = response.json()
    assert "invalid" in data["detail"].lower()


def test_protected_me_endpoint_expired_token(client):
    """GET /api/auth/me with an expired token should return HTTP 401."""
    # Generate an expired token directly (negative expiration delta)
    expired_token, _ = create_access_token(
        subject=1,
        expires_delta=timedelta(seconds=-10),
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401
    data = response.json()
    assert "expired" in data["detail"].lower()
