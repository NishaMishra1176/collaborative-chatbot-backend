"""
Automated unit tests for Google Gemini AI Chat API (POST /api/v1/chat and POST /api/chat).
Uses unittest.mock to mock Google GenAI SDK calls so tests do not make real network requests.
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

# Test in-memory SQLite database setup
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


@pytest.fixture
def auth_headers(client):
    """Creates a user and returns a valid Authorization header with Bearer token."""
    user_payload = {
        "name": "Chat Test User",
        "email": "chatuser@example.com",
        "password": "Password123!",
    }
    client.post("/api/v1/users/register", json=user_payload)
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "chatuser@example.com", "password": "Password123!"},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------
# Authentication & Authorization Tests
# --------------------------------------------------------------------------
def test_chat_unauthenticated(client):
    """POST /api/v1/chat without token should return HTTP 401 Unauthorized."""
    response = client.post("/api/v1/chat", json={"message": "Hello Gemini"})
    assert response.status_code == 401


def test_chat_invalid_token(client):
    """POST /api/v1/chat with invalid token should return HTTP 401 Unauthorized."""
    headers = {"Authorization": "Bearer bad-token-xyz"}
    response = client.post("/api/v1/chat", json={"message": "Hello Gemini"}, headers=headers)
    assert response.status_code == 401


# --------------------------------------------------------------------------
# Input Validation Tests
# --------------------------------------------------------------------------
def test_chat_empty_message(client, auth_headers):
    """POST /api/v1/chat with empty message string should return HTTP 422."""
    response = client.post("/api/v1/chat", json={"message": ""}, headers=auth_headers)
    assert response.status_code == 422


def test_chat_whitespace_only_message(client, auth_headers):
    """POST /api/v1/chat with whitespace-only message should return HTTP 422."""
    response = client.post("/api/v1/chat", json={"message": "   \n\t  "}, headers=auth_headers)
    assert response.status_code == 422


def test_chat_excessively_long_message(client, auth_headers):
    """POST /api/v1/chat with message > 4000 characters should return HTTP 422."""
    long_msg = "A" * 4001
    response = client.post("/api/v1/chat", json={"message": long_msg}, headers=auth_headers)
    assert response.status_code == 422


# --------------------------------------------------------------------------
# Mocked AI Generation Tests (Success & Failures)
# --------------------------------------------------------------------------
def test_chat_v1_success_mocked(client, auth_headers):
    """POST /api/v1/chat with valid input should call Gemini and return structured response."""
    mock_response = MagicMock()
    mock_response.text = "Hello! I am Google Gemini. How can I assist you today?"

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch.object(ai_service, "get_client", return_value=mock_client):
        response = client.post(
            "/api/v1/chat",
            json={"message": "Hello Gemini"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "Hello! I am Google Gemini. How can I assist you today?"
    assert data["model"] == settings.GEMINI_MODEL
    assert "timestamp" in data
    mock_client.models.generate_content.assert_called_once_with(
        model=settings.GEMINI_MODEL,
        contents="Hello Gemini",
    )


def test_chat_v1_prompt_alias_key(client, auth_headers):
    """POST /api/v1/chat with 'prompt' key instead of 'message' should also succeed."""
    mock_response = MagicMock()
    mock_response.text = "Prompt alias response."

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch.object(ai_service, "get_client", return_value=mock_client):
        response = client.post(
            "/api/v1/chat",
            json={"prompt": "Hello with prompt key"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json()["response"] == "Prompt alias response."


def test_chat_legacy_endpoint_success(client, auth_headers):
    """POST /api/chat legacy alias should also succeed."""
    mock_response = MagicMock()
    mock_response.text = "Legacy endpoint response."

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch.object(ai_service, "get_client", return_value=mock_client):
        response = client.post(
            "/api/chat",
            json={"message": "Hello legacy endpoint"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json()["response"] == "Legacy endpoint response."


def test_chat_missing_api_key(client, auth_headers):
    """POST /api/v1/chat when GEMINI_API_KEY is not set should return HTTP 503."""
    with patch.object(settings, "GEMINI_API_KEY", ""):
        ai_service._cached_api_key = None
        response = client.post(
            "/api/v1/chat",
            json={"message": "Test missing key"},
            headers=auth_headers,
        )

    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]


def test_chat_gemini_api_error(client, auth_headers):
    """POST /api/v1/chat when Gemini returns APIError should return HTTP 502."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = errors.APIError(
        code=500,
        response_json={"error": {"message": "Internal server error at Google Gemini"}},
    )

    with patch.object(ai_service, "get_client", return_value=mock_client):
        response = client.post(
            "/api/v1/chat",
            json={"message": "Trigger API error"},
            headers=auth_headers,
        )

    assert response.status_code == 502
    assert "encountered an error" in response.json()["detail"].lower()


def test_chat_gemini_empty_response(client, auth_headers):
    """POST /api/v1/chat when Gemini returns empty text should return HTTP 502."""
    mock_response = MagicMock()
    mock_response.text = "   "

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch.object(ai_service, "get_client", return_value=mock_client):
        response = client.post(
            "/api/v1/chat",
            json={"message": "Trigger empty response"},
            headers=auth_headers,
        )

    assert response.status_code == 502
    assert "empty response" in response.json()["detail"].lower()


def test_chat_gemini_timeout(client, auth_headers):
    """POST /api/v1/chat when Gemini request times out should return HTTP 504."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = TimeoutError("Request timed out")

    with patch.object(ai_service, "get_client", return_value=mock_client):
        response = client.post(
            "/api/v1/chat",
            json={"message": "Trigger timeout"},
            headers=auth_headers,
        )

    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()
