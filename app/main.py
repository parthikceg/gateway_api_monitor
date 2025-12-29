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

@app.post("/monitor/inject-test-snapshot")
async def inject_test_snapshot(db: Session = Depends(get_db)):
    """Create a modified snapshot for testing change detection"""
    from app.models.models import Snapshot
    import json
    from datetime import datetime
    
    # Get the latest real snapshot
    latest = db.query(Snapshot).order_by(Snapshot.created_at.desc()).first()
    
    if not latest:
        return {"error": "No snapshots found. Run /monitor/run first."}
    
    # Parse the schema - check which attribute exists
    schema = None
    if hasattr(latest, 'full_schema'):
        schema = json.loads(latest.full_schema)
    elif hasattr(latest, 'schema_json'):
        schema = json.loads(latest.schema_json)
    elif hasattr(latest, 'schema'):
        schema = json.loads(latest.schema)
    else:
        return {"error": "Could not find schema attribute", "available_attrs": dir(latest)}
    
    # Modify the schema to simulate API changes
    if "requestBody" in schema and "content" in schema["requestBody"]:
        content = schema["requestBody"]["content"].get("application/x-www-form-urlencoded", {})
        if "schema" in content and "properties" in content["schema"]:
            properties = content["schema"]["properties"]
            
            # Change 1: Add a new property
            properties["new_test_field"] = {
                "type": "string",
                "description": "A new test field added for testing"
            }
            
            # Change 2: Remove an existing property
            properties.pop("metadata", None)
            
            # Change 3: Change a field type
            if "amount" in properties:
                properties["amount"]["type"] = "string"  # Changed from integer
            
            # Change 4: Add a new required field
            if "required" in content["schema"]:
                content["schema"]["required"].append("new_test_field")
            
            # Change 5: Modify a description
            if "currency" in properties:
                properties["currency"]["description"] = "MODIFIED: Three-letter ISO currency code"
    
    # Create new snapshot with modified schema
    new_snapshot = Snapshot(
        endpoint="/v1/payment_intents",
        schema_hash="test_modified_" + (latest.schema_hash or "")
    )
    
    # Set the schema using the correct attribute name
    if hasattr(latest, 'full_schema'):
        new_snapshot.full_schema = json.dumps(schema)
    elif hasattr(latest, 'schema_json'):
        new_snapshot.schema_json = json.dumps(schema)
    elif hasattr(latest, 'schema'):
        new_snapshot.schema = json.dumps(schema)
    
    db.add(new_snapshot)
    db.commit()
    db.refresh(new_snapshot)
    
    return {
        "status": "success",
        "message": "Created modified test snapshot",
        "original_snapshot_id": str(latest.id),
        "new_snapshot_id": str(new_snapshot.id),
        "modifications": [
            "Added new_test_field property",
            "Removed metadata property",
            "Changed amount type from integer to string",
            "Made new_test_field required",
            "Modified currency description"
        ],
        "next_step": "Run POST /monitor/run to detect these changes"
    }