#!/usr/bin/env python3
"""
Generate all application files for Gateway Monitor
Run this after setup.py to create the complete application
"""

import os
import pathlib

files = {
    # ============= CONFIG =============
    "app/config.py": '''"""Application configuration"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    database_url: str
    openai_api_key: str
    
    # Email settings (optional for MVP)
    email_provider: str = "sendgrid"
    sendgrid_api_key: str = ""
    alert_from_email: str = ""
    alert_from_name: str = "Gateway Monitor"
    
    # Monitoring settings
    crawl_schedule_hours: int = 24
    
    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
''',

    # ============= DATABASE =============
    "app/db/database.py": '''"""Database configuration and session management"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import get_settings

settings = get_settings()

# Create engine - Railway provides DATABASE_URL automatically
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=300,    # Recycle connections every 5 minutes
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


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
''',

    # ============= MODELS =============
    "app/models/models.py": '''"""Database models"""
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.db.database import Base


class Snapshot(Base):
    """Stores API schema snapshots"""
    __tablename__ = "snapshots"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gateway = Column(String(50), nullable=False, index=True)
    endpoint_path = Column(String(255), nullable=False, index=True)
    spec_type = Column(String(50), nullable=False, default='primary', index=True)
    schema_data = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    changes = relationship("Change", back_populates="snapshot", cascade="all, delete-orphan")


class Change(Base):
    """Stores detected API changes"""
    __tablename__ = "changes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id = Column(UUID(as_uuid=True), ForeignKey("snapshots.id"), nullable=False)
    change_type = Column(String(50), nullable=False, index=True)
    field_path = Column(String(500), nullable=False)
    old_value = Column(JSONB)
    new_value = Column(JSONB)
    ai_summary = Column(Text)
    severity = Column(String(20), index=True)
    change_category = Column(String(50), index=True)
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    snapshot = relationship("Snapshot", back_populates="changes")


class AlertSubscription(Base):
    """Email alert subscriptions"""
    __tablename__ = "alert_subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True, index=True)
    gateway = Column(String(50))  # None = all gateways
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
''',

    # ============= STRIPE CRAWLER SERVICE =============
    "app/services/stripe_crawler.py": '''"""Stripe API specification crawler"""
import httpx
import json
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class StripeCrawler:
    """Crawls Stripe's OpenAPI specification"""
    
    STRIPE_OPENAPI_URL = "https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.json"
    
    async def fetch_spec(self) -> Optional[Dict[str, Any]]:
        """Fetch the complete Stripe OpenAPI specification"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.STRIPE_OPENAPI_URL)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch Stripe OpenAPI spec: {e}")
            return None
    
    async def extract_payment_intents_schema(self, spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract Payment Intents endpoint schema from spec"""
        try:
            # Payment Intents endpoints
            paths = spec.get("paths", {})
            
            # Get create payment intent endpoint
            create_endpoint = paths.get("/v1/payment_intents", {})
            post_method = create_endpoint.get("post", {})
            
            # Get retrieve payment intent endpoint
            retrieve_endpoint = paths.get("/v1/payment_intents/{intent}", {})
            get_method = retrieve_endpoint.get("get", {})
            
            # Extract schemas
            components = spec.get("components", {}).get("schemas", {})
            
            payment_intent_schema = components.get("payment_intent", {})
            
            return {
                "endpoint": "/v1/payment_intents",
                "methods": {
                    "POST": {
                        "parameters": post_method.get("requestBody", {}),
                        "responses": post_method.get("responses", {})
                    },
                    "GET": {
                        "parameters": get_method.get("parameters", []),
                        "responses": get_method.get("responses", {})
                    }
                },
                "schema": payment_intent_schema,
                "properties": payment_intent_schema.get("properties", {}),
                "required": payment_intent_schema.get("required", [])
            }
        except Exception as e:
            logger.error(f"Failed to extract Payment Intents schema: {e}")
            return None
    
    async def get_payment_intents_snapshot(self) -> Optional[Dict[str, Any]]:
        """Get a complete snapshot of Payment Intents API"""
        spec = await self.fetch_spec()
        if not spec:
            return None
        
        return await self.extract_payment_intents_schema(spec)
''',

    # ============= DIFF ENGINE SERVICE =============
    "app/services/diff_engine.py": '''"""Schema comparison and diff engine"""
from typing import Dict, Any, List, Tuple
import json
import logging

logger = logging.getLogger(__name__)


class DiffEngine:
    """Compares two API schemas and identifies changes"""
    
    def compare_schemas(
        self, 
        old_schema: Dict[str, Any], 
        new_schema: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Compare two schemas and return list of changes"""
        changes = []
        
        # Compare properties
        old_props = old_schema.get("properties", {})
        new_props = new_schema.get("properties", {})
        
        # Find new properties
        for prop_name, prop_def in new_props.items():
            if prop_name not in old_props:
                changes.append({
                    "change_type": "property_added",
                    "field_path": f"properties.{prop_name}",
                    "old_value": None,
                    "new_value": prop_def,
                    "severity": self._determine_severity("added", prop_def)
                })
        
        # Find removed properties
        for prop_name, prop_def in old_props.items():
            if prop_name not in new_props:
                changes.append({
                    "change_type": "property_removed",
                    "field_path": f"properties.{prop_name}",
                    "old_value": prop_def,
                    "new_value": None,
                    "severity": "high"  # Removals are usually breaking
                })
        
        # Find modified properties
        for prop_name in old_props.keys():
            if prop_name in new_props:
                prop_changes = self._compare_property(
                    prop_name, 
                    old_props[prop_name], 
                    new_props[prop_name]
                )
                changes.extend(prop_changes)
        
        # Compare required fields
        old_required = set(old_schema.get("required", []))
        new_required = set(new_schema.get("required", []))
        
        # New required fields
        for field in new_required - old_required:
            changes.append({
                "change_type": "field_now_required",
                "field_path": f"required.{field}",
                "old_value": False,
                "new_value": True,
                "severity": "high"  # Making field required is breaking
            })
        
        # Fields no longer required
        for field in old_required - new_required:
            changes.append({
                "change_type": "field_no_longer_required",
                "field_path": f"required.{field}",
                "old_value": True,
                "new_value": False,
                "severity": "low"  # Making field optional is safe
            })
        
        return changes
    
    def _compare_property(
        self, 
        prop_name: str, 
        old_prop: Dict[str, Any], 
        new_prop: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Compare two property definitions"""
        changes = []
        
        # Check type changes
        old_type = old_prop.get("type")
        new_type = new_prop.get("type")
        
        if old_type != new_type:
            changes.append({
                "change_type": "type_changed",
                "field_path": f"properties.{prop_name}.type",
                "old_value": old_type,
                "new_value": new_type,
                "severity": "high"  # Type changes are usually breaking
            })
        
        # Check description changes
        old_desc = old_prop.get("description", "")
        new_desc = new_prop.get("description", "")
        
        if old_desc != new_desc:
            changes.append({
                "change_type": "description_changed",
                "field_path": f"properties.{prop_name}.description",
                "old_value": old_desc,
                "new_value": new_desc,
                "severity": "info"  # Documentation changes are informational
            })
        
        # Check enum changes
        old_enum = old_prop.get("enum", [])
        new_enum = new_prop.get("enum", [])
        
        if old_enum != new_enum:
            added_values = set(new_enum) - set(old_enum)
            removed_values = set(old_enum) - set(new_enum)
            
            if added_values:
                changes.append({
                    "change_type": "enum_values_added",
                    "field_path": f"properties.{prop_name}.enum",
                    "old_value": old_enum,
                    "new_value": new_enum,
                    "severity": "low"
                })
            
            if removed_values:
                changes.append({
                    "change_type": "enum_values_removed",
                    "field_path": f"properties.{prop_name}.enum",
                    "old_value": old_enum,
                    "new_value": new_enum,
                    "severity": "medium"
                })
        
        return changes
    
    def _determine_severity(self, change_type: str, prop_def: Dict[str, Any]) -> str:
        """Determine severity of a change"""
        # New optional properties are low severity
        if change_type == "added":
            return "low"
        
        # Removals are high severity
        if change_type == "removed":
            return "high"
        
        return "medium"
''',

    # ============= AI ANALYZER SERVICE =============
    "app/services/ai_analyzer.py": '''"""AI-powered change analysis using OpenAI"""
import openai
from typing import Dict, Any, Optional
import json
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AIAnalyzer:
    """Uses AI to analyze and summarize API changes"""
    
    def __init__(self):
        openai.api_key = settings.openai_api_key
    
    async def analyze_change(self, change: Dict[str, Any]) -> Optional[str]:
        """Generate AI summary for a single change"""
        try:
            prompt = self._build_prompt(change)
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert API analyst. Provide concise, business-focused summaries of API changes."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return None
    
    def _build_prompt(self, change: Dict[str, Any]) -> str:
        """Build prompt for AI analysis"""
        change_type = change.get("change_type", "")
        field_path = change.get("field_path", "")
        old_value = change.get("old_value")
        new_value = change.get("new_value")
        severity = change.get("severity", "unknown")
        
        prompt = f"""Analyze this API change for Stripe Payment Intents:

Change Type: {change_type}
Field: {field_path}
Severity: {severity}
Old Value: {json.dumps(old_value, indent=2) if old_value else "None"}
New Value: {json.dumps(new_value, indent=2) if new_value else "None"}

Provide a concise summary (2-3 sentences) covering:
1. What changed and why it matters
2. Potential impact on developers
3. Recommended action (if any)
"""
        return prompt
    
    async def categorize_change(self, change: Dict[str, Any]) -> str:
        """Categorize the type of change"""
        change_type = change.get("change_type", "")
        
        categories = {
            "property_added": "enhancement",
            "property_removed": "breaking_change",
            "type_changed": "breaking_change",
            "field_now_required": "breaking_change",
            "field_no_longer_required": "enhancement",
            "enum_values_added": "enhancement",
            "enum_values_removed": "breaking_change",
            "description_changed": "documentation"
        }
        
        return categories.get(change_type, "other")
''',

    # ============= MONITORING SERVICE =============
    "app/services/monitoring_service.py": '''"""Main monitoring service orchestrator"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.services.stripe_crawler import StripeCrawler
from app.services.diff_engine import DiffEngine
from app.services.ai_analyzer import AIAnalyzer
from app.models.models import Snapshot, Change

logger = logging.getLogger(__name__)


class MonitoringService:
    """Orchestrates the monitoring workflow"""
    
    def __init__(self, db: Session):
        self.db = db
        self.crawler = StripeCrawler()
        self.diff_engine = DiffEngine()
        self.ai_analyzer = AIAnalyzer()
    
    async def run_monitoring(self) -> Dict[str, Any]:
        """Run complete monitoring cycle"""
        logger.info("Starting monitoring cycle...")
        
        # Step 1: Fetch current schema
        current_schema = await self.crawler.get_payment_intents_snapshot()
        if not current_schema:
            logger.error("Failed to fetch current schema")
            return {"status": "error", "message": "Failed to fetch schema"}
        
        # Step 2: Get previous snapshot
        previous_snapshot = self._get_latest_snapshot()
        
        # Step 3: Create new snapshot
        new_snapshot = Snapshot(
            gateway="stripe",
            endpoint_path="/v1/payment_intents",
            spec_type="primary",
            schema_data=current_schema
        )
        self.db.add(new_snapshot)
        self.db.commit()
        self.db.refresh(new_snapshot)
        
        # Step 4: Compare if previous exists
        changes_detected = []
        if previous_snapshot:
            changes = self.diff_engine.compare_schemas(
                previous_snapshot.schema_data,
                current_schema
            )
            
            # Step 5: Analyze each change with AI
            for change_data in changes:
                ai_summary = await self.ai_analyzer.analyze_change(change_data)
                category = await self.ai_analyzer.categorize_change(change_data)
                
                change_record = Change(
                    snapshot_id=new_snapshot.id,
                    change_type=change_data["change_type"],
                    field_path=change_data["field_path"],
                    old_value=change_data.get("old_value"),
                    new_value=change_data.get("new_value"),
                    severity=change_data.get("severity", "medium"),
                    change_category=category,
                    ai_summary=ai_summary
                )
                self.db.add(change_record)
                changes_detected.append(change_data)
            
            self.db.commit()
            logger.info(f"Detected {len(changes_detected)} changes")
        else:
            logger.info("First snapshot created - no comparison")
        
        return {
            "status": "success",
            "snapshot_id": str(new_snapshot.id),
            "changes_count": len(changes_detected),
            "changes": changes_detected
        }
    
    def _get_latest_snapshot(self) -> Optional[Snapshot]:
        """Get the most recent snapshot"""
        return self.db.query(Snapshot)\
            .filter(Snapshot.gateway == "stripe")\
            .filter(Snapshot.endpoint_path == "/v1/payment_intents")\
            .order_by(Snapshot.created_at.desc())\
            .first()
    
    def get_recent_changes(self, limit: int = 20) -> List[Change]:
        """Get recent changes"""
        return self.db.query(Change)\
            .order_by(Change.detected_at.desc())\
            .limit(limit)\
            .all()
''',

    # ============= SCHEDULER =============
    "app/scheduler/scheduler.py": '''"""APScheduler configuration for periodic monitoring"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging

from app.config import get_settings
from app.db.database import SessionLocal
from app.services.monitoring_service import MonitoringService

logger = logging.getLogger(__name__)
settings = get_settings()

scheduler = AsyncIOScheduler()


async def scheduled_monitoring_job():
    """Job that runs on schedule"""
    logger.info("Running scheduled monitoring job...")
    db = SessionLocal()
    try:
        service = MonitoringService(db)
        result = await service.run_monitoring()
        logger.info(f"Monitoring completed: {result}")
    except Exception as e:
        logger.error(f"Scheduled monitoring failed: {e}")
    finally:
        db.close()


def start_scheduler():
    """Start the scheduler"""
    scheduler.add_job(
        scheduled_monitoring_job,
        trigger=IntervalTrigger(hours=settings.crawl_schedule_hours),
        id="monitoring_job",
        name="Monitor Stripe API changes",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"Scheduler started - monitoring every {settings.crawl_schedule_hours} hours")


def stop_scheduler():
    """Stop the scheduler"""
    scheduler.shutdown()
    logger.info("Scheduler stopped")
''',

    # ============= MAIN APP =============
    "app/main.py": '''"""FastAPI application entry point"""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import logging

from app.config import get_settings
from app.db.database import get_db, init_db
from app.models.models import Snapshot, Change, AlertSubscription
from app.services.monitoring_service import MonitoringService
from app.scheduler.scheduler import start_scheduler, stop_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()
app = FastAPI(
    title="Gateway Monitor API",
    description="Monitor Stripe API changes automatically",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize database and start scheduler"""
    logger.info("Starting up...")
    init_db()
    start_scheduler()
    logger.info("Application started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down...")
    stop_scheduler()


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Gateway Monitor",
        "version": "1.0.0"
    }


@app.post("/monitor/run")
async def run_monitoring(db: Session = Depends(get_db)):
    """Manually trigger monitoring"""
    try:
        service = MonitoringService(db)
        result = await service.run_monitoring()
        return result
    except Exception as e:
        logger.error(f"Monitoring failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/snapshots")
async def get_snapshots(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get recent snapshots"""
    snapshots = db.query(Snapshot)\
        .order_by(Snapshot.created_at.desc())\
        .limit(limit)\
        .all()
    
    return {
        "snapshots": [
            {
                "id": str(s.id),
                "gateway": s.gateway,
                "endpoint": s.endpoint_path,
                "created_at": s.created_at.isoformat()
            }
            for s in snapshots
        ]
    }


@app.get("/changes")
async def get_changes(
    limit: int = 20,
    severity: str = None,
    db: Session = Depends(get_db)
):
    """Get recent changes"""
    query = db.query(Change)
    
    if severity:
        query = query.filter(Change.severity == severity)
    
    changes = query.order_by(Change.detected_at.desc()).limit(limit).all()
    
    return {
        "changes": [
            {
                "id": str(c.id),
                "type": c.change_type,
                "field": c.field_path,
                "severity": c.severity,
                "category": c.change_category,
                "summary": c.ai_summary,
                "detected_at": c.detected_at.isoformat()
            }
            for c in changes
        ]
    }


@app.post("/subscriptions")
async def create_subscription(
    email: str,
    gateway: str = None,
    db: Session = Depends(get_db)
):
    """Subscribe to email alerts"""
    subscription = AlertSubscription(
        email=email,
        gateway=gateway
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    
    return {
        "id": str(subscription.id),
        "email": email,
        "status": "active"
    }


@app.get("/subscriptions")
async def get_subscriptions(db: Session = Depends(get_db)):
    """Get all active subscriptions"""
    subscriptions = db.query(AlertSubscription)\
        .filter(AlertSubscription.is_active == True)\
        .all()
    
    return {
        "subscriptions": [
            {
                "id": str(s.id),
                "email": s.email,
                "gateway": s.gateway
            }
            for s in subscriptions
        ]
    }
''',

    # ============= ENVIRONMENT TEMPLATE =============
    ".env.example": '''# Database (Railway will provide this automatically)
DATABASE_URL=postgresql://user:password@localhost:5432/gateway_monitor

# OpenAI API Key (get from https://platform.openai.com/api-keys)
OPENAI_API_KEY=sk-your-key-here

# Optional: Email alerts (for future use)
EMAIL_PROVIDER=sendgrid
SENDGRID_API_KEY=
ALERT_FROM_EMAIL=
ALERT_FROM_NAME=Gateway Monitor

# Monitoring schedule (hours)
CRAWL_SCHEDULE_HOURS=24
''',
}

# Create all files
for filepath, content in files.items():
    path = pathlib.Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    print(f"✅ Created {filepath}")

print("\n" + "="*60)
print("🎉 ALL APPLICATION FILES CREATED SUCCESSFULLY!")
print("="*60)
print("\nProject structure:")
print("""
gateway-monitor/
└── backend/
    ├── app/
    │   ├── __init__.py
    │   ├── main.py              # FastAPI app
    │   ├── config.py            # Settings
    │   ├── models/
    │   │   ├── __init__.py
    │   │   └── models.py        # Database models
    │   ├── services/
    │   │   ├── __init__.py
    │   │   ├── stripe_crawler.py
    │   │   ├── diff_engine.py
    │   │   ├── ai_analyzer.py
    │   │   └── monitoring_service.py
    │   ├── scheduler/
    │   │   ├── __init__.py
    │   │   └── scheduler.py
    │   └── db/
    │       ├── __init__.py
    │       └── database.py
    ├── requirements.txt
    ├── Procfile
    ├── railway.json
    ├── .env.example
    ├── .gitignore
    └── README.md
""")

print("\n" + "="*60)
print("NEXT STEPS:")
print("="*60)
print("\n1. Create virtual environment:")
print("   python -m venv venv")
print("   venv\\Scripts\\activate  (Windows)")
print("\n2. Install dependencies:")
print("   pip install -r requirements.txt")
print("\n3. Create .env file:")
print("   copy .env.example .env")
print("   Edit .env with your DATABASE_URL and OPENAI_API_KEY")
print("\n4. For local testing (optional):")
print("   Use Railway's local PostgreSQL or SQLite for testing")
print("\n5. Push to GitHub:")
print("   git add .")
print('   git commit -m "Initial commit"')
print("   git remote add origin <your-repo-url>")
print("   git push -u origin main")
print("\n6. Deploy to Railway:")
print("   - Go to railway.app")
print("   - Create new project from GitHub repo")
print("   - Add PostgreSQL database")
print("   - Set OPENAI_API_KEY environment variable")
print("   - Deploy!")
print("\n" + "="*60)
