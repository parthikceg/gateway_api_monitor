"""Pre-startup migration script. Runs BEFORE gunicorn workers start.

Creates the target database if it doesn't exist, then creates tables.
This runs exactly once via .ebextensions container_commands.
"""
from dotenv import load_dotenv
load_dotenv()

import logging
import os
import re
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("migrate")


def _ensure_database_exists():
    """Create the target database if it doesn't exist.

    Parses DATABASE_URL to extract the db name, connects to the default
    'postgres' database, and runs CREATE DATABASE IF NOT EXISTS.
    """
    from app.config import get_settings
    settings = get_settings()
    db_url = settings.database_url

    if not db_url:
        logger.info("No DATABASE_URL configured — skipping DB creation")
        return

    # Extract database name from URL: postgresql://user:pass@host:port/DBNAME
    match = re.match(r'(.+)/([^/?]+)(\?.*)?$', db_url)
    if not match:
        logger.info("Could not parse database name from URL — skipping")
        return

    base_url = match.group(1)
    target_db = match.group(2)

    if target_db == 'postgres':
        logger.info("Target database is 'postgres' (default) — no creation needed")
        return

    logger.info(f"Target database: {target_db}")

    # Connect to the default 'postgres' database to create the target
    admin_url = f"{base_url}/postgres"

    from sqlalchemy import create_engine, text
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    try:
        with admin_engine.connect() as conn:
            # Check if database exists
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db"),
                {"db": target_db}
            )
            if result.fetchone():
                logger.info(f"Database '{target_db}' already exists")
            else:
                # CREATE DATABASE doesn't support parameters, but target_db
                # comes from our own config, not user input
                conn.execute(text(f'CREATE DATABASE "{target_db}"'))
                logger.info(f"Created database '{target_db}'")
    except Exception as e:
        logger.error(f"Database creation error: {e}")
    finally:
        admin_engine.dispose()


def run():
    logger.info("=== PRE-START MIGRATION ===")

    # Step 1: Create target database if needed
    _ensure_database_exists()

    # Step 2: Create tables (no-op if they already exist)
    from app.db.database import engine, Base
    from app.models.models import Snapshot, Change, AlertSubscription  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("create_all() done")

    # Step 3: Verify column types are correct (sanity check)
    raw_conn = engine.raw_connection()
    try:
        raw_conn.autocommit = True
        cursor = raw_conn.cursor()
        cursor.execute("""
            SELECT data_type, udt_name FROM information_schema.columns
            WHERE table_name = 'changes' AND column_name = 'change_maturity'
        """)
        col = cursor.fetchone()
        if col:
            logger.info(f"change_maturity column: data_type={col[0]}, udt_name={col[1]}")
            if col[0] == 'USER-DEFINED':
                logger.warning("Column is STILL enum — converting to VARCHAR...")
                cursor.execute("""
                    ALTER TABLE changes
                    ALTER COLUMN change_maturity TYPE VARCHAR(50)
                    USING change_maturity::text
                """)
                cursor.execute("DROP TYPE IF EXISTS changematurity CASCADE")
                logger.info("Converted to VARCHAR and dropped enum type")
        else:
            logger.info("No changes table yet — clean state")
        cursor.close()
    except Exception as e:
        logger.error(f"Verification error: {e}")
    finally:
        raw_conn.close()

    engine.dispose()
    logger.info("=== PRE-START MIGRATION DONE ===")


if __name__ == "__main__":
    run()
