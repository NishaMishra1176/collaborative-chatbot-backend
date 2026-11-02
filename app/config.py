import os
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Base directory: collaborative-chatbot-backend/
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from the .env file if it exists
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE)


class Settings:
    """
    Centralized configuration management for the application.
    Values are loaded from environment variables (or .env file)
    with safe, beginner-friendly defaults for local development.
    """

    # --- Project Metadata ---
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Collaborative Chatbot Backend")
    VERSION: str = os.getenv("VERSION", "0.1.0")
    DESCRIPTION: str = (
        "A collaborative chatbot backend built with FastAPI, SQLAlchemy, and Google GenAI."
    )
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").strip().lower() in ("true", "1", "yes", "t")

    # --- Server Settings ---
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))

    # --- Database Settings (MySQL) ---
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "3306")
    DB_NAME: str = os.getenv("DB_NAME", "chatbot_db")

    # URL-encode password to support special characters like '@', ':', '/' in passwords
    _quoted_password: str = quote_plus(DB_PASSWORD) if DB_PASSWORD else ""

    # If DATABASE_URL is set in .env, use it directly (e.g. for SQLite or custom connection strings).
    # Otherwise, assemble dynamically from DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME.
    _raw_database_url: str = os.getenv("DATABASE_URL", "").strip()
    DATABASE_URL: str = (
        _raw_database_url
        if _raw_database_url
        else f"mysql+pymysql://{DB_USER}:{_quoted_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    # --- JWT Authentication Settings ---
    # Secret key used for signing JWT tokens (loaded securely from .env)
    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY",
        "collaborative-chatbot-secret-key-change-this-in-production-min32bytes",
    )
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    # --- Google GenAI API Settings ---
    # API key loaded securely from .env (never hardcoded or exposed)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

    # --- CORS Settings ---
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    @property
    def cors_origins_list(self) -> list[str]:
        """Returns the CORS origins as a list of strings."""
        if not self.CORS_ORIGINS or self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # --- Logging Settings ---
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG" if DEBUG else "INFO")


# Export a single settings object to be shared across the entire project
settings = Settings()
