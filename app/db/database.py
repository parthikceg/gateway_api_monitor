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
    """Convert change_maturity from PG enum to VARCHAR if needed.

    Previous approaches (DROP TABLE, DROP TYPE, ADD VALUE) all failed silently
    on AWS RDS. This approach uses ALTER COLUMN TYPE to convert in-place,
    preserving existing data without needing to drop anything.
    """
    logger.info("=== ENUM MIGRATION START ===")
    raw_conn = engine.raw_connection()
    try:
        raw_conn.autocommit = True
        cursor = raw_conn.cursor()

        # Check current column type
        cursor.execute("""
            SELECT data_type, udt_name FROM information_schema.columns
            WHERE table_name = 'changes' AND column_name = 'change_maturity'
        """)
        col = cursor.fetchone()

        if col is None:
            logger.info("No changes table or change_maturity column — clean state")
            cursor.close()
            return

        logger.info(f"Column type: data_type={col[0]}, udt_name={col[1]}")

        if col[0] == 'USER-DEFINED':
            # Column is still enum — archive old data, then drop and recreate clean
            logger.info("Found enum column — archiving old changes and rebuilding...")

            # Archive existing rows into a backup table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS changes_archive AS
                SELECT * FROM changes
            """)
            cursor.execute("SELECT COUNT(*) FROM changes_archive")
            archived = cursor.fetchone()[0]
            logger.info(f"Archived {archived} rows to changes_archive")

            # Drop the changes table and enum type for a clean slate
            cursor.execute("DROP TABLE changes CASCADE")
            logger.info("DROP TABLE changes: OK")
            cursor.execute("DROP TYPE IF EXISTS changematurity CASCADE")
            logger.info("DROP TYPE changematurity: OK")
        else:
            logger.info("Column is already VARCHAR — no migration needed")

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
