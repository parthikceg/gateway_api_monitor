"""FastAPI application entry point"""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.config import get_settings
from app.db.database import get_db, init_db
from app.models.models import Snapshot, Change, AlertSubscription, SpecType, ChangeMaturity
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
    description="Monitor Stripe API changes automatically across multiple tiers",
    version="2.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
        "version": "2.0.0",
        "tiers": ["stable", "preview", "beta"]
    }


# ============================================================================
# MONITORING ENDPOINTS
# ============================================================================

@app.post("/monitor/run")
async def run_monitoring(
    tier: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Trigger monitoring for all tiers or a specific tier
    
    Query params:
    - tier: Optional - 'stable', 'preview', or 'beta'. If not provided, runs all tiers.
    """
    try:
        service = MonitoringService(db)
        
        if tier:
            # Run single tier
            if tier not in ["stable", "preview", "beta"]:
                raise HTTPException(status_code=400, detail="Invalid tier. Must be stable, preview, or beta")
            
            result = await service._monitor_tier(tier)
            return result
        else:
            # Run all tiers
            result = await service.run_monitoring()
            return result
            
    except Exception as e:
        logger.error(f"Monitoring failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/monitor/compare")
async def compare_tiers(
    source: str,
    target: str = "stable",
    db: Session = Depends(get_db)
):
    """
    Compare two tiers to see upcoming features
    
    Query params:
    - source: Tier to compare from ('preview' or 'beta')
    - target: Tier to compare against (default: 'stable')
    
    Examples:
    - /monitor/compare?source=preview&target=stable - See what's coming from preview to stable
    - /monitor/compare?source=beta&target=stable - See what's in beta vs stable
    """
    try:
        if source not in ["preview", "beta"]:
            raise HTTPException(status_code=400, detail="Source must be preview or beta")
        if target not in ["stable", "preview"]:
            raise HTTPException(status_code=400, detail="Target must be stable or preview")
        
        service = MonitoringService(db)
        result = await service._compare_tiers(source, target)
        return result
        
    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SNAPSHOT ENDPOINTS
# ============================================================================

@app.get("/snapshots")
async def get_snapshots(
    limit: int = 10,
    tier: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get recent snapshots
    
    Query params:
    - limit: Number of snapshots to return (default: 10)
    - tier: Filter by tier - 'stable', 'preview', or 'beta' (optional)
    """
    query = db.query(Snapshot)
    
    if tier:
        if tier not in ["stable", "preview", "beta"]:
            raise HTTPException(status_code=400, detail="Invalid tier")
        spec_type_enum = SpecType[tier.upper()]
        query = query.filter(Snapshot.spec_type == spec_type_enum)
    
    snapshots = query.order_by(Snapshot.created_at.desc()).limit(limit).all()
    
    return {
        "snapshots": [
            {
                "id": str(s.id),
                "gateway": s.gateway,
                "endpoint": s.endpoint_path,
                "tier": s.spec_type.value,
                "created_at": s.created_at.isoformat()
            }
            for s in snapshots
        ]
    }


@app.get("/snapshots/stats")
async def get_snapshot_stats(db: Session = Depends(get_db)):
    """Get snapshot statistics by tier"""
    try:
        from sqlalchemy import func
        
        # Count snapshots by spec_type
        results = db.query(
            Snapshot.spec_type,
            func.count(Snapshot.id).label('count')
        ).group_by(Snapshot.spec_type).all()
        
        return {
            "stats": [
                {
                    "tier": result.spec_type.value if hasattr(result.spec_type, 'value') else str(result.spec_type),
                    "count": result.count
                }
                for result in results
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching snapshot stats: {e}", exc_info=True)
        # Return empty stats instead of failing
        return {"stats": []}



@app.get("/snapshots/{snapshot_id}")
async def get_snapshot_detail(snapshot_id: str, db: Session = Depends(get_db)):
    """Get full snapshot details including schema"""
    from uuid import UUID
    
    try:
        snapshot = db.query(Snapshot).filter(Snapshot.id == UUID(snapshot_id)).first()
        
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        
        return {
            "id": str(snapshot.id),
            "gateway": snapshot.gateway,
            "endpoint": snapshot.endpoint_path,
            "tier": snapshot.spec_type.value,
            "spec_url": snapshot.spec_url,
            "created_at": snapshot.created_at.isoformat(),
            "schema_data": snapshot.schema_data
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



# ============================================================================
# CHANGES ENDPOINTS
# ============================================================================

@app.get("/changes")
async def get_changes(
    limit: int = 20,
    severity: str = None,
    tier: Optional[str] = None,
    maturity: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get recent changes with filtering
    
    Query params:
    - limit: Number of changes (default: 20)
    - severity: Filter by severity - 'high', 'medium', 'low', 'info'
    - tier: Filter by tier - 'stable', 'preview', 'beta'
    - maturity: Filter by maturity - 'stable_change', 'new_preview', 'new_beta', etc.
    """
    query = db.query(Change).join(Snapshot)
    
    if severity:
        query = query.filter(Change.severity == severity)
    
    if tier:
        if tier not in ["stable", "preview", "beta"]:
            raise HTTPException(status_code=400, detail="Invalid tier")
        spec_type_enum = SpecType[tier.upper()]
        query = query.filter(Snapshot.spec_type == spec_type_enum)
    
    if maturity:
        try:
            maturity_enum = ChangeMaturity[maturity.upper()]
            query = query.filter(Change.change_maturity == maturity_enum)
        except KeyError:
            raise HTTPException(status_code=400, detail="Invalid maturity level")
    
    changes = query.order_by(Change.detected_at.desc()).limit(limit).all()
    
    return {
        "changes": [
            {
                "id": str(c.id),
                "type": c.change_type,
                "field": c.field_path,
                "severity": c.severity,
                "category": c.change_category,
                "maturity": c.change_maturity.value if c.change_maturity else None,
                "tier": c.snapshot.spec_type.value,
                "summary": c.ai_summary,
                "detected_at": c.detected_at.isoformat()
            }
            for c in changes
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
        spec_type=SpecType.STABLE,
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


# ============================================================================
# AI ENDPOINTS
# ============================================================================

from pydantic import BaseModel
from typing import Any
import os
from openai import OpenAI

class AIQuestion(BaseModel):
    question: str
    context: dict[str, Any]

PAYMENTS_SME_SYSTEM_PROMPT = """You are a Senior Payments Expert and Subject Matter Expert (SME) on payment gateway APIs, with deep expertise in Stripe's API architecture, payment flows, and integration patterns.

Your knowledge includes:
1. **Stripe API Documentation**: Complete understanding of all Stripe API endpoints, objects, and their fields
2. **Payment Concepts**: Authorization holds, capture methods, payment intents, payment methods, refunds, disputes, etc.
3. **Integration Patterns**: Best practices for integrating payment gateways like Stripe with billing platforms like Chargebee
4. **Business Use Cases**: Real-world applications of payment features in e-commerce, SaaS subscriptions, marketplaces, etc.

When explaining a field or feature:
- Explain what the field does in plain language
- Describe the business use cases where this field is valuable
- Provide examples of how payment platforms like Chargebee might use this field
- Mention any important considerations, limitations, or best practices
- If it's a beta/preview feature, explain what new capabilities it enables

Keep responses concise but informative. Use bullet points for clarity. Focus on practical value for developers and product teams building payment integrations."""

@app.post("/ai/ask")
async def ask_ai(request: AIQuestion):
    """Ask AI about a field or API change"""
    try:
        client = OpenAI(
            api_key=os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY"),
            base_url=os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
        )
        
        field_info = request.context.get('field', {})
        tier = field_info.get('tier', 'stable')
        
        context_str = f"""
**Field Being Discussed:**
- Field Name: `{field_info.get('name', 'Unknown')}`
- Data Type: {field_info.get('type', 'Unknown')}
- API Tier: {tier.upper()} {'(Generally Available)' if tier == 'stable' else '(Not yet in GA - subject to change)'}
- Description from Stripe: {field_info.get('description', 'No description available')}
- Required: {'Yes' if field_info.get('required') else 'No'}
"""
        
        messages = [
            {"role": "system", "content": PAYMENTS_SME_SYSTEM_PROMPT}
        ]
        
        conversation_history = request.context.get('conversationHistory', [])
        for msg in conversation_history[-6:]:
            messages.append({"role": msg.get('role', 'user'), "content": msg.get('content', '')})
        
        messages.append({"role": "user", "content": f"{context_str}\n\n**User Question:** {request.question}"})
        
        response = client.chat.completions.create(
            model="gpt-5",
            messages=messages,
            max_completion_tokens=800
        )
        
        return {"answer": response.choices[0].message.content}
    except Exception as e:
        logger.error(f"AI query failed: {e}")
        return {"answer": f"Sorry, I couldn't process your question. Error: {str(e)}"}


# ============================================================================
# SUBSCRIPTION ENDPOINTS
# ============================================================================

from app.models.models import AlertSubscription

class SubscribeRequest(BaseModel):
    name: str
    email: str

@app.post("/subscribe")
async def subscribe(request: SubscribeRequest, db: Session = Depends(get_db)):
    """Subscribe to API change alerts"""
    try:
        existing = db.query(AlertSubscription).filter(AlertSubscription.email == request.email).first()
        
        if existing:
            existing.name = request.name
            existing.is_active = True
            db.commit()
            return {"status": "success", "message": "Subscription updated successfully"}
        
        subscription = AlertSubscription(
            name=request.name,
            email=request.email,
            is_active=True
        )
        db.add(subscription)
        db.commit()
        
        logger.info(f"New subscription: {request.email}")
        return {"status": "success", "message": "Subscribed successfully"}
    except Exception as e:
        logger.error(f"Subscription failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to subscribe")

@app.get("/subscribers")
async def list_subscribers(db: Session = Depends(get_db)):
    """List all active subscribers (admin only)"""
    subscribers = db.query(AlertSubscription).filter(AlertSubscription.is_active == True).all()
    return {
        "subscribers": [
            {
                "id": str(s.id),
                "name": s.name,
                "email": s.email,
                "created_at": s.created_at.isoformat()
            }
            for s in subscribers
        ],
        "count": len(subscribers)
    }