"""FastAPI application entry point"""
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
    snapshots = db.query(Snapshot)        .order_by(Snapshot.created_at.desc())        .limit(limit)        .all()
    
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
    subscriptions = db.query(AlertSubscription)        .filter(AlertSubscription.is_active == True)        .all()
    
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

@app.post("/monitor/test")
async def test_monitoring(db: Session = Depends(get_db)):
    """Test endpoint: Compare a mock old schema against live Stripe API"""
    
    # Create a simple old schema
    old_schema = {
        "type": "object",
        "properties": {
            "amount": {"type": "integer", "description": "Amount in cents"},
            "currency": {"type": "string", "description": "Three-letter ISO code"}
        },
        "required": ["amount", "currency"]
    }
    
    # Create a new schema with changes
    new_schema = {
        "type": "object",
        "properties": {
            "amount": {"type": "integer", "description": "Amount in cents"},
            "currency": {"type": "string", "description": "Three-letter ISO code"},
            "metadata": {"type": "object", "description": "Set of key-value pairs"},  # NEW
            "description": {"type": "string", "description": "Description of payment"},  # NEW
            "customer": {"type": "string", "description": "Customer ID"}  # NEW
        },
        "required": ["amount", "currency", "customer"]  # customer is now required
    }
    
    # Run diff
    from app.services.diff_engine import DiffEngine
    diff_engine = DiffEngine()
    changes = diff_engine.compare_schemas(old_schema, new_schema)
    
    # Analyze with AI
    from app.services.ai_analyzer import AIAnalyzer
    ai_analyzer = AIAnalyzer()
    
    analyzed_changes = []
    for change in changes:
        summary = await ai_analyzer.analyze_change(change)
        analyzed_changes.append({
            "change_type": change["change_type"],
            "field_path": change["field_path"],
            "severity": change["severity"],
            "old_value": change.get("old_value"),
            "new_value": change.get("new_value"),
            "ai_summary": summary
        })
    
    return {
        "status": "test_success",
        "message": "Testing change detection with mock schemas",
        "changes_detected": len(changes),
        "changes": analyzed_changes
    }