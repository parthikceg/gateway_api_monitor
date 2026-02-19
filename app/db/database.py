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


def _fix_enum_issues():
    """Fix changematurity enum issues with belt-and-suspenders approach.

    Strategy:
    1. If enum exists, first ADD any missing values so queries work immediately
    2. Then try to DROP TABLE + DROP TYPE for a clean String column
    3. If DROP fails (permissions, locks, etc.), the added values ensure it works anyway
    """
    logger.info("Running enum fix migration...")
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
            # STEP 1: Add missing values so queries work even if DROP fails
            logger.info("Found changematurity enum — adding missing values as safety net")
            required = ['stable_change', 'preview_change', 'beta_change',
                        'cross_tier_preview', 'cross_tier_beta']
            for val in required:
                try:
                    cursor.execute(
                        f"ALTER TYPE changematurity ADD VALUE IF NOT EXISTS '{val}'"
                    )
                except Exception:
                    pass  # Value already exists or PG < 9.3
            logger.info("Ensured all enum values exist")

            # STEP 2: Try to drop everything for a clean String column
            try:
                cursor.execute("DROP TABLE IF EXISTS changes CASCADE")
                cursor.execute("DROP TABLE IF EXISTS changes_archived_enum CASCADE")
                cursor.execute("DROP TYPE IF EXISTS changematurity CASCADE")
                logger.info("Dropped changes table and enum type — clean slate")
            except Exception as drop_err:
                logger.warning(f"DROP failed (enum values added as fallback): {drop_err}")
        else:
            logger.info("No changematurity enum found — clean state")

        cursor.close()
    except Exception as e:
        logger.error(f"Enum fix migration error: {e}")
    finally:
        raw_conn.close()


def init_db():
    """Initialize database tables"""
    _fix_enum_issues()
    engine.dispose()
    Base.metadata.create_all(bind=engine)
