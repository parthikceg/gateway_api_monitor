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


def _fix_enum_after_create():
    """Convert change_maturity from PG enum to VARCHAR AFTER create_all().

    Root cause: Base.metadata.create_all() recreates the changematurity enum
    type even though the model says Column(String). This happens because
    SQLAlchemy's metadata somehow retains the enum type registration.

    Solution: Let create_all() do its thing, then immediately convert the
    column to VARCHAR and drop the orphaned enum type.
    """
    raw_conn = engine.raw_connection()
    try:
        raw_conn.autocommit = True
        cursor = raw_conn.cursor()

        # Check if the column is still an enum
        cursor.execute("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'changes' AND column_name = 'change_maturity'
        """)
        col = cursor.fetchone()

        if col and col[0] == 'USER-DEFINED':
            cursor.execute("""
                ALTER TABLE changes
                ALTER COLUMN change_maturity TYPE VARCHAR(50)
                USING change_maturity::text
            """)
            cursor.execute("DROP TYPE IF EXISTS changematurity CASCADE")
            logger.info("Converted change_maturity from enum to VARCHAR and dropped type")
        else:
            logger.info("change_maturity is already VARCHAR — no fix needed")

        cursor.close()
    except Exception as e:
        logger.error(f"Post-create enum fix error: {e}")
    finally:
        raw_conn.close()


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    _fix_enum_after_create()
    engine.dispose()
