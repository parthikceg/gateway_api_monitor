"""Database configuration and session management"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import get_settings
import logging
import re

logger = logging.getLogger(__name__)

settings = get_settings()


def _ensure_database_exists(db_url: str):
    """Create the target database if it doesn't exist.

    Parses the URL to extract the DB name, connects to the default
    'postgres' database, and runs CREATE DATABASE.
    """
    if not db_url:
        return

    match = re.match(r'(.+)/([^/?]+)(\?.*)?$', db_url)
    if not match:
        return

    base_url = match.group(1)
    target_db = match.group(2)
    query_params = match.group(3) or ""

    if target_db == 'postgres':
        return  # Already using default DB

    # Connect to 'postgres' DB to create the target
    admin_url = f"{base_url}/postgres{query_params}"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    try:
        with admin_engine.connect() as conn:
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db"),
                {"db": target_db}
            )
            if result.fetchone():
                logger.info(f"Database '{target_db}' already exists")
            else:
                conn.execute(text(f'CREATE DATABASE "{target_db}"'))
                logger.info(f"Created database '{target_db}'")
    except Exception as e:
        logger.error(f"Database creation error: {e}")
    finally:
        admin_engine.dispose()


# Ensure target database exists before creating the engine
_ensure_database_exists(settings.database_url)

# Create engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
    connect_args={
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for FastAPI routes"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
