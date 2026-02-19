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


def _nuke_enum_table():
    """Drop changes table and enum type if the old PG enum still exists.

    Previous migration attempts (RENAME, ALTER TABLE, DROP TYPE) failed
    because RENAME fails if the target name already exists. Simplest fix:
    DROP TABLE + DROP TYPE, let create_all() recreate with String column.
    Change data is regenerated on next monitoring run.
    """
    logger.info("Running enum cleanup migration...")
    raw_conn = engine.raw_connection()
    try:
        raw_conn.autocommit = True
        cursor = raw_conn.cursor()

        # Check if the old enum type still exists
        cursor.execute(
            "SELECT 1 FROM pg_type WHERE typname = 'changematurity'"
        )
        has_enum = cursor.fetchone() is not None

        if has_enum:
            logger.info("Found changematurity enum — dropping changes table and type")
            cursor.execute("DROP TABLE IF EXISTS changes CASCADE")
            cursor.execute("DROP TABLE IF EXISTS changes_archived_enum CASCADE")
            cursor.execute("DROP TYPE IF EXISTS changematurity CASCADE")
            logger.info("Dropped changes table and changematurity enum type")
        else:
            logger.info("No changematurity enum found — clean state")

        cursor.close()
    except Exception as e:
        logger.error(f"Enum cleanup migration error: {e}")
    finally:
        raw_conn.close()


def init_db():
    """Initialize database tables"""
    _nuke_enum_table()
    engine.dispose()
    Base.metadata.create_all(bind=engine)
