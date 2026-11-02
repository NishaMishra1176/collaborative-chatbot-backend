"""
Database configuration and session management using SQLAlchemy.

Note:
SQLAlchemy uses lazy connection pooling. Creating the engine and SessionLocal
does NOT open an immediate network connection to MySQL. The application will start
smoothly even if the MySQL server is offline.
"""

import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

logger = logging.getLogger(__name__)

# Base class for all ORM models (models inherit from Base)
Base = declarative_base()

# SQLAlchemy Database Engine
# pool_pre_ping=True: Tests connections for liveness before giving them to the app
# pool_recycle=3600: Prevents MySQL "gone away" errors by recycling connections after 1 hour
try:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("SQLAlchemy database engine configured with URL: %s", settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else settings.DATABASE_URL)
except Exception as err:
    logger.warning("Could not initialize database engine: %s", err)
    engine = None
    SessionLocal = None


def get_db():
    """
    FastAPI dependency that provides a database session for each request
    and guarantees it is closed after the request completes.
    """
    if SessionLocal is None:
        raise RuntimeError(
            "Database engine is not initialized. Please verify your DATABASE_URL configuration in .env."
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_database_exists():
    """
    If using MySQL and target database does not exist,
    connects to server and creates the database automatically.
    """
    if "mysql" in settings.DATABASE_URL:
        try:
            import pymysql
            conn = pymysql.connect(
                host=settings.DB_HOST,
                port=int(settings.DB_PORT),
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
            )
            with conn.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{settings.DB_NAME}` "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                )
            conn.close()
            logger.info("MySQL database '%s' verified or created.", settings.DB_NAME)
        except Exception as exc:
            logger.debug("Database auto-create check: %s", exc)


def check_db_connection() -> tuple[bool, str]:
    """
    Safely tests if the database is reachable.
    Does NOT block or crash the server when MySQL is not yet running.
    """
    if engine is None:
        return False, "Database engine is not initialized."

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, "Database connection successful."
    except Exception as exc:
        return False, f"Database connection failed: {exc}"


def create_tables():
    """
    Creates database tables for all registered models.
    Safe to call when database is reachable.
    """
    ensure_database_exists()
    if engine is not None:
        Base.metadata.create_all(bind=engine)
