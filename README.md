# Collaborative Generative AI Customer-Care Chatbot Backend

A production-ready, secure backend for a collaborative customer-care chatbot built with **FastAPI**, **SQLAlchemy**, **MySQL**, and **Google Gemini GenAI** (`gemini-3.5-flash`).

---

## Features

- **FastAPI Framework**: High-performance RESTful API with automated Swagger UI documentation (`/docs`) and ReDoc (`/redoc`).
- **User Authentication**:
  - Secure password hashing using **bcrypt** with unique random salt.
  - Stateless authentication using **JSON Web Tokens (JWT)** signed with **HS256**.
  - Protected endpoints validated via reusable FastAPI security dependencies (`get_current_user`).
  - Constant-time verification on login to protect against user enumeration / timing attacks.
- **Google Gemini AI Integration**:
  - Powered by the official `google-genai` Python SDK.
  - Configurable model (defaults to `gemini-3.5-flash`).
  - Protected endpoint (`POST /api/v1/chat`) requiring Bearer token.
  - Strict input validation (1 to 4,000 characters, rejects empty or whitespace-only messages).
  - Resilient error handling (HTTP 502 for upstream failures, HTTP 503 for missing keys, HTTP 504 for timeouts).
- **Database Layer**:
  - **SQLAlchemy ORM** with **PyMySQL** connection driver.
  - Connection pooling with pre-ping validation (`pool_pre_ping=True`) and connection recycling (`pool_recycle=3600`).
  - Automatic database and table creation on application startup.
  - Non-blocking startup (API starts up gracefully even if the MySQL server is temporarily offline).
- **Security & Hygiene**:
  - Environment variables managed through `.env`.
  - Secrets and credentials strictly excluded from version control via `.gitignore`.
  - Safe `.env.example` template provided for easy onboarding.

---

## Project Structure

```text
collaborative-chatbot-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI application setup, CORS, lifespan, routes & error handlers
│   ├── config.py                   # Pydantic & python-dotenv configuration management
│   ├── database.py                 # SQLAlchemy engine, sessionmaker, and DB connection utilities
│   ├── models/
│   │   ├── __init__.py
│   │   └── user.py                 # SQLAlchemy User model (id, name, email, password_hash, created_at)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py                 # LoginRequest, TokenResponse schemas
│   │   ├── user.py                 # UserRegisterRequest, UserResponse schemas
│   │   └── chat.py                 # ChatMessageRequest, ChatMessageResponse schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── security.py             # Password hashing (bcrypt) & JWT issuance/decoding
│   │   ├── auth_service.py         # User registration and authentication business logic
│   │   ├── auth_dependency.py      # FastAPI OAuth2 Bearer token dependency
│   │   └── ai_service.py           # Google Gemini AI client and chat response generation
│   └── routers/
│       ├── __init__.py
│       ├── auth.py                 # POST /api/v1/auth/login, GET /api/v1/auth/me
│       ├── users.py                # POST /api/v1/users/register
│       └── chat.py                 # POST /api/v1/chat
├── tests/
│   ├── __init__.py
│   ├── test_auth.py                # 11 unit & integration tests for registration and JWT auth
│   ├── test_chat.py                # 12 unit & integration tests for chat validation and Gemini AI
│   └── test_general.py             # 3 tests for root, health check, and error handlers
├── .env.example                    # Safe environment variables template
├── .gitignore                      # Git exclusion rules for secrets, venv, caches, logs
├── requirements.txt                # Pinned production and development dependencies
└── README.md                       # Project documentation
```

---

## API Endpoints

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | Public | Welcome metadata and documentation links |
| `GET` | `/health` | Public | Health check confirming service and MySQL status |
| `POST` | `/api/v1/users/register` | Public | Register a new user account |
| `POST` | `/api/v1/auth/login` | Public | Authenticate user and receive JWT access token |
| `GET` | `/api/v1/auth/me` | Bearer Token | Retrieve authenticated user profile |
| `POST` | `/api/v1/chat` | Bearer Token | Send message prompt and receive Google Gemini response |

*(Direct aliases `/api/chat`, `/api/users/register`, and `/api/auth/*` are also supported for backward compatibility).*

---

## Getting Started

### 1. Prerequisites
- Python 3.10+ (Tested on Python 3.11 & 3.14)
- MySQL Server 8.0+
- Google Gemini API Key ([Get one here](https://aistudio.google.com/app/apikey))

### 2. Clone Repository
```bash
git clone https://github.com/NishaMishra1176/collaborative-chatbot-backend.git
cd collaborative-chatbot-backend
```

### 3. Create & Activate Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy the `.env.example` file to `.env`:
```bash
cp .env.example .env
```
Open `.env` and fill in your values:
```ini
PROJECT_NAME="Collaborative Chatbot Backend"
VERSION="0.1.0"
ENVIRONMENT="development"
DEBUG=True

HOST="127.0.0.1"
PORT=8000

DB_USER="root"
DB_PASSWORD="your_mysql_password"
DB_HOST="localhost"
DB_PORT="3306"
DB_NAME="chatbot_db"

JWT_SECRET_KEY="your-super-secret-jwt-key-at-least-32-characters-long"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=60

GEMINI_API_KEY="your_gemini_api_key_here"
GEMINI_MODEL="gemini-3.5-flash"

CORS_ORIGINS="*"
```

### 6. Run the Application
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Once started, visit:
- **Interactive Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative ReDoc UI**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## Running Automated Tests

The test suite runs against an isolated in-memory SQLite database using `unittest.mock` for Gemini API calls. No live MySQL connection or Gemini API quota is required to run tests.

```bash
python -m pytest tests -v
```

**Test Coverage**:
- 26 test cases covering user registration, duplicate email rejection, invalid password handling, JWT generation, invalid/expired token rejection, protected routes, chat input length validation, empty/whitespace rejection, missing API key handling (HTTP 503), upstream Gemini failures (HTTP 502), and timeouts (HTTP 504).

---

## License

This project is licensed under the MIT License.
