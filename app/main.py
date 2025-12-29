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
    import copy
    
    # Get the latest real snapshot
    latest = db.query(Snapshot).order_by(Snapshot.created_at.desc()).first()
    
    if not latest:
        return {"error": "No snapshots found. Run /monitor/run first."}
    
    # Deep copy the schema
    schema = copy.deepcopy(latest.schema_data)
    
    # Properties are at ROOT level!
    if "properties" in schema:
        properties = schema["properties"]
        
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
        
        # Change 4: Add to required list (at root level)
        if "required" in schema:
            if "new_test_field" not in schema["required"]:
                schema["required"].append("new_test_field")
        
        # Change 5: Modify a description
        if "currency" in properties:
            properties["currency"]["description"] = "MODIFIED: Three-letter ISO currency code"
    
    # Create new snapshot
    new_snapshot = Snapshot(
        endpoint_path="/v1/payment_intents",
        gateway="stripe",
        spec_type="openapi3",
        schema_data=schema
    )
    
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


@app.post("/monitor/debug-last-comparison")
async def debug_last_comparison(db: Session = Depends(get_db)):
    """See what the last monitoring run compared"""
    snapshots = db.query(Snapshot).order_by(Snapshot.created_at.desc()).limit(2).all()
    
    if len(snapshots) < 2:
        return {"error": "Need at least 2 snapshots"}
    
    latest = snapshots[0]
    previous = snapshots[1]
    
    return {
        "previous_snapshot": {
            "id": str(previous.id),
            "created_at": previous.created_at.isoformat(),
            "has_new_test_field": "new_test_field" in previous.schema_data.get("requestBody", {}).get("content", {}).get("application/x-www-form-urlencoded", {}).get("schema", {}).get("properties", {}),
            "has_metadata": "metadata" in previous.schema_data.get("requestBody", {}).get("content", {}).get("application/x-www-form-urlencoded", {}).get("schema", {}).get("properties", {})
        },
        "latest_snapshot": {
            "id": str(latest.id),
            "created_at": latest.created_at.isoformat(),
            "has_new_test_field": "new_test_field" in latest.schema_data.get("requestBody", {}).get("content", {}).get("application/x-www-form-urlencoded", {}).get("schema", {}).get("properties", {}),
            "has_metadata": "metadata" in latest.schema_data.get("requestBody", {}).get("content", {}).get("application/x-www-form-urlencoded", {}).get("schema", {}).get("properties", {})
        }
    }


@app.get("/monitor/debug-schema-structure")
async def debug_schema_structure(db: Session = Depends(get_db)):
    """See the actual structure of stored schemas"""
    latest = db.query(Snapshot).order_by(Snapshot.created_at.desc()).first()
    
    if not latest:
        return {"error": "No snapshots"}
    
    schema = latest.schema_data
    
    return {
        "snapshot_id": str(latest.id),
        "top_level_keys": list(schema.keys()),
        "has_requestBody": "requestBody" in schema,
        "has_properties_at_root": "properties" in schema,
        "schema_preview": {
            k: type(v).__name__ for k, v in list(schema.items())[:10]
        }
    }