"""
Automated tests for Core & General Endpoints (GET / and GET /health).
Also includes tests for specific Gemini error variants like invalid API key.
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from google.genai import errors
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.services.ai_service import ai_service

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
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_root_endpoint(client):
    """GET / should return 200 with API metadata and endpoint links."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "docs_url" in data
    assert data["docs_url"] == "/docs"
    assert "health_check" in data
    assert "auth_endpoints" in data
    assert "chat_endpoints" in data


def test_health_check_endpoint(client):
    """GET /health should return 200 with service health status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == settings.PROJECT_NAME
    assert data["version"] == settings.VERSION
    assert "database" in data
    assert "gemini_model" in data


def test_chat_gemini_invalid_api_key_error(client):
    """POST /api/v1/chat when Gemini reports invalid API key should return HTTP 502 with helpful detail."""
    # First register and login a user for the token
    user_payload = {
        "name": "General Test User",
        "email": "generaltest@example.com",
        "password": "Password123!",
    }
    client.post("/api/v1/users/register", json=user_payload)
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "generaltest@example.com", "password": "Password123!"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = errors.APIError(
        code=400,
        response_json={"error": {"message": "API_KEY_INVALID: The provided API key is invalid"}},
    )

    with patch.object(ai_service, "get_client", return_value=mock_client):
        response = client.post(
            "/api/v1/chat",
            json={"message": "Testing invalid api key error"},
            headers=headers,
        )

    assert response.status_code == 502
    assert "invalid" in response.json()["detail"].lower()
