"""FastAPI application entry point"""
from dotenv import load_dotenv
load_dotenv()  # Load .env file before any other imports that use env vars

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging
import os
from pathlib import Path

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

# Determine if running on AWS EB (no root_path needed) or Replit (needs /api prefix)
is_aws = os.environ.get("DB_PROVIDER") == "aws"
root_path = "" if is_aws else "/api"

app = FastAPI(
    title="Gateway Monitor API",
    description="Monitor Stripe API changes automatically across multiple tiers",
    version="2.0.0",
    root_path=root_path,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
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


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    from app.services.stripe_crawler import StripeCrawler
    crawler = StripeCrawler()
    return {
        "status": "healthy",
        "service": "Gateway Monitor",
        "version": "2.0.0",
        "tiers": ["stable", "preview", "beta"],
        "monitored_endpoints": crawler.get_monitored_endpoints()
    }


@app.get("/debug/db-info")
async def debug_db_info(db: Session = Depends(get_db)):
    """Diagnostic endpoint: shows DB state for debugging enum issues"""
    from app.db.database import engine
    raw_conn = engine.raw_connection()
    try:
        raw_conn.autocommit = True
        cursor = raw_conn.cursor()
        info = {}

        # Database info
        cursor.execute("SELECT current_database(), current_user, version()")
        row = cursor.fetchone()
        info["database"] = row[0]
        info["user"] = row[1]
        info["pg_version"] = row[2][:80]

        # Check enum type
        cursor.execute("SELECT typname FROM pg_type WHERE typname LIKE '%maturity%'")
        info["matching_types"] = [r[0] for r in cursor.fetchall()]

        # Check enum values
        cursor.execute("""
            SELECT e.enumlabel FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = 'changematurity'
            ORDER BY e.enumsortorder
        """)
        info["enum_values"] = [r[0] for r in cursor.fetchall()]

        # Check column type
        cursor.execute("""
            SELECT data_type, udt_name FROM information_schema.columns
            WHERE table_name = 'changes' AND column_name = 'change_maturity'
        """)
        col = cursor.fetchone()
        info["column_type"] = {"data_type": col[0], "udt_name": col[1]} if col else None

        # Check if tables exist
        cursor.execute("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename LIKE 'changes%'
        """)
        info["changes_tables"] = [r[0] for r in cursor.fetchall()]

        # Row count
        try:
            cursor.execute("SELECT COUNT(*) FROM changes")
            info["changes_count"] = cursor.fetchone()[0]
        except Exception:
            info["changes_count"] = "table not accessible"

        cursor.close()
        return info
    finally:
        raw_conn.close()


@app.post("/debug/fix-enum")
async def fix_enum_manual():
    """Manually run the enum-to-VARCHAR migration with step-by-step results"""
    from app.db.database import engine
    steps = []
    raw_conn = engine.raw_connection()
    try:
        raw_conn.autocommit = True
        cursor = raw_conn.cursor()

        # Step 1: Check current column type
        cursor.execute("""
            SELECT data_type, udt_name FROM information_schema.columns
            WHERE table_name = 'changes' AND column_name = 'change_maturity'
        """)
        col = cursor.fetchone()
        steps.append({"step": "check_column", "result": f"data_type={col[0]}, udt_name={col[1]}" if col else "no column found"})

        if col is None or col[0] != 'USER-DEFINED':
            steps.append({"step": "skip", "result": "Column is already VARCHAR or table missing — nothing to do"})
            cursor.close()
            return {"steps": steps, "status": "already_clean"}

        # Step 2: Archive existing rows
        try:
            cursor.execute("DROP TABLE IF EXISTS changes_archive")
            steps.append({"step": "drop_old_archive", "result": "OK"})
        except Exception as e:
            steps.append({"step": "drop_old_archive", "result": f"FAILED: {e}"})

        try:
            cursor.execute("CREATE TABLE changes_archive AS SELECT * FROM changes")
            cursor.execute("SELECT COUNT(*) FROM changes_archive")
            count = cursor.fetchone()[0]
            steps.append({"step": "archive_rows", "result": f"OK — {count} rows archived"})
        except Exception as e:
            steps.append({"step": "archive_rows", "result": f"FAILED: {e}"})

        # Step 3: Drop changes table
        try:
            cursor.execute("DROP TABLE IF EXISTS changes CASCADE")
            steps.append({"step": "drop_table", "result": "OK"})
        except Exception as e:
            steps.append({"step": "drop_table", "result": f"FAILED: {e}"})

        # Step 4: Drop enum type
        try:
            cursor.execute("DROP TYPE IF EXISTS changematurity CASCADE")
            steps.append({"step": "drop_type", "result": "OK"})
        except Exception as e:
            steps.append({"step": "drop_type", "result": f"FAILED: {e}"})

        cursor.close()

        # Step 5: Recreate tables with VARCHAR column
        try:
            engine.dispose()
            from app.db.database import Base
            Base.metadata.create_all(bind=engine)
            steps.append({"step": "create_tables", "result": "OK"})
        except Exception as e:
            steps.append({"step": "create_tables", "result": f"FAILED: {e}"})

        # Step 6: Verify
        raw_conn2 = engine.raw_connection()
        try:
            raw_conn2.autocommit = True
            cursor2 = raw_conn2.cursor()
            cursor2.execute("""
                SELECT data_type, udt_name FROM information_schema.columns
                WHERE table_name = 'changes' AND column_name = 'change_maturity'
            """)
            col2 = cursor2.fetchone()
            steps.append({"step": "verify", "result": f"data_type={col2[0]}, udt_name={col2[1]}" if col2 else "column not found"})
            cursor2.execute("SELECT typname FROM pg_type WHERE typname = 'changematurity'")
            enum_check = cursor2.fetchone()
            steps.append({"step": "verify_enum_gone", "result": "enum STILL EXISTS" if enum_check else "enum removed — clean"})
            cursor2.close()
        finally:
            raw_conn2.close()

        return {"steps": steps, "status": "completed"}
    except Exception as e:
        steps.append({"step": "unexpected_error", "result": str(e)})
        return {"steps": steps, "status": "error"}
    finally:
        raw_conn.close()


@app.get("/")
async def root():
    """Serve React app on AWS, health check on Replit"""
    if is_aws:
        # On AWS, serve React frontend
        index_file = Path(__file__).parent.parent / "client" / "dist" / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
    # On Replit, return health check
    from app.services.stripe_crawler import StripeCrawler
    crawler = StripeCrawler()
    return {
        "status": "healthy",
        "service": "Gateway Monitor",
        "version": "2.0.0",
        "tiers": ["stable", "preview", "beta"],
        "monitored_endpoints": crawler.get_monitored_endpoints()
    }


@app.get("/endpoints")
async def get_monitored_endpoints():
    """Get list of all monitored Stripe API endpoints"""
    from app.services.stripe_crawler import StripeCrawler
    crawler = StripeCrawler()
    endpoints = crawler.get_monitored_endpoints()
    return {
        "gateway": "stripe",
        "endpoints": endpoints,
        "count": len(endpoints)
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


@app.post("/monitor/reset-db")
async def reset_db(db: Session = Depends(get_db)):
    """Delete all changes and snapshots for a clean baseline run"""
    changes_deleted = db.query(Change).delete()
    snapshots_deleted = db.query(Snapshot).delete()
    db.commit()
    logger.info(f"DB reset: {changes_deleted} changes, {snapshots_deleted} snapshots deleted")
    return {"status": "ok", "changes_deleted": changes_deleted, "snapshots_deleted": snapshots_deleted}


@app.get("/monitor/compare")
async def compare_tiers(
    source: str,
    target: str = "stable",
    endpoint: str = None,
    db: Session = Depends(get_db)
):
    """
    Compare two tiers to see upcoming features

    Query params:
    - source: Tier to compare from ('preview' or 'beta')
    - target: Tier to compare against (default: 'stable')
    - endpoint: Optional endpoint to filter comparison (e.g., '/v1/payment_intents')

    Examples:
    - /monitor/compare?source=preview&target=stable - See what's coming from preview to stable
    - /monitor/compare?source=beta&target=stable - See what's in beta vs stable
    - /monitor/compare?source=preview&target=stable&endpoint=/v1/charges - Compare specific endpoint
    """
    try:
        if source not in ["preview", "beta"]:
            raise HTTPException(status_code=400, detail="Source must be preview or beta")
        if target not in ["stable", "preview"]:
            raise HTTPException(status_code=400, detail="Target must be stable or preview")

        service = MonitoringService(db)
        result = await service._compare_tiers(source, target, endpoint)
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
    offset: int = 0,
    severity: str = None,
    tier: Optional[str] = None,
    maturity: Optional[str] = None,
    endpoint: Optional[str] = None,
    schema_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get recent changes with filtering and pagination

    Query params:
    - limit: Number of changes (default: 20)
    - offset: Number of changes to skip (default: 0)
    - severity: Filter by severity - 'high', 'medium', 'low', 'info'
    - tier: Filter by tier - 'stable', 'preview', 'beta'
    - maturity: Filter by maturity - 'stable_change', 'cross_tier_preview', etc.
    - endpoint: Filter by endpoint path - e.g., '/v1/payment_methods'
    - schema_type: Filter by schema type - 'object' or 'request'
    - date_from: Filter changes detected on or after this datetime (ISO format)
    - date_to: Filter changes detected on or before this datetime (ISO format)
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
        # change_maturity is now a plain String column — filter directly
        valid = {m.value for m in ChangeMaturity}
        if maturity not in valid:
            raise HTTPException(status_code=400, detail="Invalid maturity level")
        query = query.filter(Change.change_maturity == maturity)

    if endpoint:
        query = query.filter(Snapshot.endpoint_path == endpoint)

    if schema_type:
        if schema_type == "object":
            query = query.filter(Change.field_path.like("object.%") | Change.field_path.like("properties.object.%") | Change.field_path.like("required.object.%"))
        elif schema_type == "request":
            query = query.filter(Change.field_path.like("request.%") | Change.field_path.like("properties.request.%") | Change.field_path.like("required.request.%"))

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            query = query.filter(Change.detected_at >= dt_from)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from format")

    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            query = query.filter(Change.detected_at <= dt_to)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to format")

    # Get total count before pagination
    total_count = query.count()

    # Apply pagination
    changes = query.order_by(Change.detected_at.desc()).offset(offset).limit(limit).all()

    return {
        "changes": [
            {
                "id": str(c.id),
                "type": c.change_type,
                "field": c.field_path,
                "endpoint": c.snapshot.endpoint_path if c.snapshot else "N/A",
                "severity": c.severity,
                "category": c.change_category,
                "maturity": c.change_maturity,
                "tier": c.snapshot.spec_type.value,
                "summary": c.ai_summary,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "detected_at": c.detected_at.isoformat()
            }
            for c in changes
        ],
        "total": total_count,
        "offset": offset,
        "limit": limit,
        "has_more": (offset + len(changes)) < total_count
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
        # Support both Replit (AI_INTEGRATIONS_*) and local (OPENAI_API_KEY) env vars
        api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL") or None

        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        field_info = request.context.get('field', {})
        tier = field_info.get('tier', 'stable')
        endpoint = request.context.get('endpoint', '') or field_info.get('endpoint', '')

        # Format endpoint name for display
        endpoint_display = endpoint.replace('/v1/', '').replace('_', ' ').title() if endpoint else 'Unknown'

        context_str = f"""
**Field Being Discussed:**
- Field Name: `{field_info.get('name', 'Unknown')}`
- API Endpoint: {endpoint_display} (`{endpoint}`)
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


# ============================================================================
# EMAIL TEST ENDPOINT
# ============================================================================

from app.services.email_service import EmailService

@app.post("/email/test")
async def test_email(email: str, name: str = "Test User"):
    """Send a test email to verify SMTP configuration"""
    try:
        email_service = EmailService()

        if not email_service.enabled:
            return {
                "status": "error",
                "message": "Email service not configured. Check SMTP_USERNAME, SMTP_PASSWORD, and ALERT_FROM_EMAIL in .env"
            }

        # Send a test change alert
        test_changes = [
            {
                "type": "property_added",
                "field": "test_field",
                "severity": "info",
                "tier": "beta",
                "summary": "This is a test email to verify your Gateway Monitor email configuration is working correctly."
            }
        ]

        success = email_service.send_change_alert(
            to_email=email,
            to_name=name,
            changes=test_changes
        )

        if success:
            return {"status": "success", "message": f"Test email sent to {email}"}
        else:
            return {"status": "error", "message": "Failed to send email. Check server logs for details."}

    except Exception as e:
        logger.error(f"Test email failed: {e}")
        return {"status": "error", "message": str(e)}


# ============================================================================
# STATIC FILE SERVING (for AWS EB deployment)
# ============================================================================

# Serve React static files in production (AWS EB)
# The client/dist folder contains the built React app
static_dir = Path(__file__).parent.parent / "client" / "dist"

if static_dir.exists() and is_aws:
    logger.info(f"Mounting static files from: {static_dir}")

    # Mount static assets (JS, CSS, images)
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Serve index.html for all non-API routes (React SPA routing)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve React app for all non-API routes"""
        # Don't serve SPA for API documentation paths
        if full_path in ["docs", "redoc", "openapi.json"]:
            return None

        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        raise HTTPException(status_code=404, detail="Frontend not found")