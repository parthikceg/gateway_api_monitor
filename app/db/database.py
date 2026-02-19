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
    logger.info("=== ENUM MIGRATION START ===")
    raw_conn = engine.raw_connection()
    try:
        raw_conn.autocommit = True
        cursor = raw_conn.cursor()

        # Log database info
        cursor.execute("SELECT current_database(), current_user, version()")
        row = cursor.fetchone()
        logger.info(f"DB: {row[0]}, User: {row[1]}, PG: {row[2][:60]}")

        # Check if the old enum type still exists
        cursor.execute(
            "SELECT typname FROM pg_type WHERE typname LIKE '%maturity%'"
        )
        matching_types = [r[0] for r in cursor.fetchall()]
        logger.info(f"Types matching '%%maturity%%': {matching_types}")

        has_enum = 'changematurity' in matching_types

        if has_enum:
            # Log current enum values
            cursor.execute("""
                SELECT e.enumlabel FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'changematurity'
                ORDER BY e.enumsortorder
            """)
            current_values = [r[0] for r in cursor.fetchall()]
            logger.info(f"Current enum values: {current_values}")

            # STEP 1: Add missing values so queries work even if DROP fails
            logger.info("Adding missing enum values...")
            required = ['stable_change', 'preview_change', 'beta_change',
                        'cross_tier_preview', 'cross_tier_beta']
            for val in required:
                try:
                    cursor.execute(
                        f"ALTER TYPE changematurity ADD VALUE IF NOT EXISTS '{val}'"
                    )
                    logger.info(f"  ADD VALUE '{val}': OK")
                except Exception as e:
                    logger.info(f"  ADD VALUE '{val}': {e}")

            # Log column type
            cursor.execute("""
                SELECT data_type, udt_name FROM information_schema.columns
                WHERE table_name = 'changes' AND column_name = 'change_maturity'
            """)
            col = cursor.fetchone()
            logger.info(f"Column type: {col}")

            # STEP 2: Try to drop everything for a clean String column
            try:
                cursor.execute("DROP TABLE IF EXISTS changes CASCADE")
                logger.info("DROP TABLE changes: OK")
                cursor.execute("DROP TABLE IF EXISTS changes_archived_enum CASCADE")
                logger.info("DROP TABLE changes_archived_enum: OK")
                cursor.execute("DROP TYPE IF EXISTS changematurity CASCADE")
                logger.info("DROP TYPE changematurity: OK")
            except Exception as drop_err:
                logger.warning(f"DROP failed: {drop_err}")
        else:
            logger.info("No changematurity enum found — clean state")

        cursor.close()
        logger.info("=== ENUM MIGRATION END ===")
    except Exception as e:
        logger.error(f"=== ENUM MIGRATION ERROR: {e} ===")
    finally:
        raw_conn.close()


def init_db():
    """Initialize database tables"""
    _fix_enum_issues()
    engine.dispose()
    Base.metadata.create_all(bind=engine)
