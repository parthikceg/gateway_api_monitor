"""Database configuration and session management"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()

# Create engine - Railway provides DATABASE_URL automatically
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=300,    # Recycle connections every 5 minutes
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


def _migrate_maturity_to_string():
    """Convert change_maturity column from native PG enum to VARCHAR.

    Native PG enums cache type metadata in connections, causing persistent
    'invalid input value' errors when new values are added. A plain VARCHAR
    column avoids this entirely while the Python ChangeMaturity enum still
    provides application-level type safety.
    """
    logger.info("Running maturity column migration check...")
    raw_conn = engine.raw_connection()
    try:
        raw_conn.autocommit = True
        cursor = raw_conn.cursor()

        # Direct approach: just try the ALTER. If column is already VARCHAR,
        # the cast still succeeds (VARCHAR::text is a no-op). If table doesn't
        # exist yet, it'll error and we catch it gracefully.
        try:
            cursor.execute(
                "ALTER TABLE changes ALTER COLUMN change_maturity "
                "TYPE VARCHAR(100) USING change_maturity::text"
            )
            logger.info("Successfully ensured change_maturity is VARCHAR")
        except Exception as alter_err:
            err_str = str(alter_err)
            if 'does not exist' in err_str:
                logger.info("changes table not found yet, will be created as VARCHAR")
            else:
                logger.error(f"ALTER TABLE failed: {alter_err}")

        cursor.close()
    except Exception as e:
        logger.error(f"Maturity column migration error: {e}")
    finally:
        raw_conn.close()


def init_db():
    """Initialize database tables"""
    _migrate_maturity_to_string()
    Base.metadata.create_all(bind=engine)
