"""
Migration script to add multi-tier support
Run this once to update existing database
"""
from sqlalchemy import create_engine, text
from app.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)

def migrate():
    with engine.connect() as conn:
        # Add spec_type column with default
        conn.execute(text("""
            ALTER TABLE snapshots 
            ADD COLUMN IF NOT EXISTS spec_type VARCHAR DEFAULT 'STABLE'
        """))
        
        # Add spec_url column
        conn.execute(text("""
            ALTER TABLE snapshots 
            ADD COLUMN IF NOT EXISTS spec_url VARCHAR
        """))
        
        # Add change_maturity column
        conn.execute(text("""
            ALTER TABLE changes 
            ADD COLUMN IF NOT EXISTS change_maturity VARCHAR
        """))
        
        conn.commit()
        print("✅ Migration completed successfully!")

if __name__ == "__main__":
    migrate()