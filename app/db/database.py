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
    """Nuclear fix: archive the old changes table and drop the enum type.

    The old 'changes' table has a native PG enum column that is deeply
    embedded in PostgreSQL's type system and resists ALTER TABLE fixes.
    Archiving the table and dropping the enum type guarantees a clean slate.
    create_all() will recreate 'changes' with a plain String column.
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
            logger.info("Found old changematurity enum type — archiving changes table")
            # Archive the old table (preserves data)
            try:
                cursor.execute("ALTER TABLE changes RENAME TO changes_archived_enum")
                logger.info("Archived old changes table to changes_archived_enum")
            except Exception as rename_err:
                if 'does not exist' in str(rename_err):
                    logger.info("No changes table to archive")
                else:
                    logger.error(f"Could not archive changes table: {rename_err}")

            # Drop the enum type completely
            try:
                cursor.execute("DROP TYPE IF EXISTS changematurity CASCADE")
                logger.info("Dropped changematurity enum type")
            except Exception as drop_err:
                logger.warning(f"Could not drop enum type: {drop_err}")
        else:
            logger.info("No changematurity enum type found — clean state")

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
