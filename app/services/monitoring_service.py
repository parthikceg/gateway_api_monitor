"""Main monitoring service orchestrator"""
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
        return self.db.query(Snapshot)            .filter(Snapshot.gateway == "stripe")            .filter(Snapshot.endpoint_path == "/v1/payment_intents")            .order_by(Snapshot.created_at.desc())            .first()
    
    def get_recent_changes(self, limit: int = 20) -> List[Change]:
        """Get recent changes"""
        return self.db.query(Change)            .order_by(Change.detected_at.desc())            .limit(limit)            .all()
