"""Multi-tier monitoring service orchestrator"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.services.stripe_crawler import StripeCrawler
from app.services.diff_engine import DiffEngine
from app.services.ai_analyzer import AIAnalyzer
from app.models.models import Snapshot, Change, SpecType, ChangeMaturity

logger = logging.getLogger(__name__)

class MonitoringService:
    """Orchestrates multi-tier monitoring workflow"""
    
    def __init__(self, db: Session):
        self.db = db
        self.crawler = StripeCrawler()
        self.diff_engine = DiffEngine()
        self.ai_analyzer = AIAnalyzer()
    
    async def run_monitoring(self) -> Dict[str, Any]:
        """Run complete multi-tier monitoring cycle"""
        logger.info("Starting multi-tier monitoring cycle...")
        
        results = {
            "stable": await self._monitor_tier("stable"),
            "preview": await self._monitor_tier("preview"),
            "beta": await self._monitor_tier("beta")
        }
        
        # Compare preview vs stable
        preview_vs_stable = await self._compare_tiers("preview", "stable")
        results["preview_vs_stable"] = preview_vs_stable
        
        # Compare beta vs stable
        beta_vs_stable = await self._compare_tiers("beta", "stable")
        results["beta_vs_stable"] = beta_vs_stable
        
        return results
    
    async def _monitor_tier(self, spec_type: str) -> Dict[str, Any]:
        """Monitor a single tier"""
        logger.info(f"Monitoring {spec_type} tier...")
        
        # Fetch current schema
        current_schema = await self.crawler.get_payment_intents_snapshot(spec_type)
        
        # Get previous snapshot for this tier
        previous_snapshot = self._get_latest_snapshot(spec_type)
        
        # Create new snapshot
        spec_type_enum = SpecType[spec_type.upper()]
        new_snapshot = Snapshot(
            gateway="stripe",
            endpoint_path="/v1/payment_intents",
            spec_type=spec_type_enum,
            spec_url=self.crawler.SPEC_URLS[spec_type],
            schema_data=current_schema
        )
        self.db.add(new_snapshot)
        self.db.commit()
        self.db.refresh(new_snapshot)
        
        # Compare if previous exists
        changes_detected = []
        if previous_snapshot:
            changes = self.diff_engine.compare_schemas(
                previous_snapshot.schema_data,
                current_schema
            )
            
            # Analyze and save changes
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
                    change_maturity=ChangeMaturity.STABLE_CHANGE if spec_type == "stable" else None,
                    ai_summary=ai_summary
                )
                self.db.add(change_record)
                changes_detected.append(change_data)
            
            self.db.commit()
        
        return {
            "spec_type": spec_type,
            "snapshot_id": str(new_snapshot.id),
            "changes_count": len(changes_detected),
            "changes": changes_detected
        }
    
    async def _compare_tiers(self, source_tier: str, target_tier: str) -> Dict[str, Any]:
        """Compare two tiers to find differences"""
        logger.info(f"Comparing {source_tier} vs {target_tier}...")
        
        source_snapshot = self._get_latest_snapshot(source_tier)
        target_snapshot = self._get_latest_snapshot(target_tier)
        
        if not source_snapshot or not target_snapshot:
            return {"error": "Missing snapshots for comparison"}
        
        # Find what's in source but not in target (upcoming features)
        changes = self.diff_engine.compare_schemas(
            target_snapshot.schema_data,
            source_snapshot.schema_data
        )
        
        # Categorize by maturity
        maturity = ChangeMaturity.NEW_PREVIEW if source_tier == "preview" else ChangeMaturity.NEW_BETA
        
        analyzed_changes = []
        for change_data in changes:
            ai_summary = await self.ai_analyzer.analyze_change(change_data)
            analyzed_changes.append({
                "change": change_data,
                "maturity": maturity.value,
                "ai_summary": ai_summary,
                "timeline": "4-10 weeks" if source_tier == "preview" else "Unknown"
            })
        
        return {
            "comparison": f"{source_tier}_vs_{target_tier}",
            "upcoming_features_count": len(analyzed_changes),
            "changes": analyzed_changes
        }
    
    def _get_latest_snapshot(self, spec_type: str) -> Optional[Snapshot]:
        """Get the most recent snapshot for a spec type"""
        spec_type_enum = SpecType[spec_type.upper()]
        return self.db.query(Snapshot) \
            .filter(Snapshot.gateway == "stripe") \
            .filter(Snapshot.endpoint_path == "/v1/payment_intents") \
            .filter(Snapshot.spec_type == spec_type_enum) \
            .order_by(Snapshot.created_at.desc()) \
            .first()