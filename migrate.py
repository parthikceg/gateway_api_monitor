"""Pre-startup migration script. Runs BEFORE gunicorn workers start.

Creates tables via SQLAlchemy, then fixes the changematurity enum column
by converting it to VARCHAR. This runs exactly once, with no concurrency
issues from multiple workers.
"""
from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("migrate")

from app.db.database import engine, Base

# Import models so Base.metadata knows about all tables
from app.models.models import Snapshot, Change, AlertSubscription  # noqa: F401

def run():
    logger.info("=== PRE-START MIGRATION ===")

    # Step 1: Create tables (no-op if they already exist)
    Base.metadata.create_all(bind=engine)
    logger.info("create_all() done")

    # Step 2: Fix enum column if needed
    raw_conn = engine.raw_connection()
    try:
        raw_conn.autocommit = True
        cursor = raw_conn.cursor()

        cursor.execute("""
            SELECT data_type, udt_name FROM information_schema.columns
            WHERE table_name = 'changes' AND column_name = 'change_maturity'
        """)
        col = cursor.fetchone()

        if col is None:
            logger.info("No changes table — nothing to fix")
        elif col[0] == 'USER-DEFINED':
            logger.info(f"Column is {col[0]} ({col[1]}) — converting to VARCHAR...")
            cursor.execute("""
                ALTER TABLE changes
                ALTER COLUMN change_maturity TYPE VARCHAR(50)
                USING change_maturity::text
            """)
            logger.info("ALTER COLUMN TYPE: OK")
            cursor.execute("DROP TYPE IF EXISTS changematurity CASCADE")
            logger.info("DROP TYPE: OK")

            # Verify
            cursor.execute("""
                SELECT data_type, udt_name FROM information_schema.columns
                WHERE table_name = 'changes' AND column_name = 'change_maturity'
            """)
            col2 = cursor.fetchone()
            logger.info(f"Verified: data_type={col2[0]}, udt_name={col2[1]}")
        else:
            logger.info(f"Column is already {col[0]} — no fix needed")

        cursor.close()
    except Exception as e:
        logger.error(f"Migration error: {e}")
    finally:
        raw_conn.close()

    engine.dispose()
    logger.info("=== PRE-START MIGRATION DONE ===")

if __name__ == "__main__":
    run()
