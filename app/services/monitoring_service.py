"""Multi-tier monitoring service orchestrator"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import logging
import json

from app.services.stripe_crawler import StripeCrawler
from app.services.diff_engine import DiffEngine
from app.services.ai_analyzer import AIAnalyzer
from app.services.email_service import EmailService
from app.models.models import Snapshot, Change, AlertSubscription, SpecType, ChangeMaturity

logger = logging.getLogger(__name__)

class MonitoringService:
    """Orchestrates multi-tier monitoring workflow"""

    def __init__(self, db: Session):
        self.db = db
        self.crawler = StripeCrawler()
        self.diff_engine = DiffEngine()
        self.ai_analyzer = AIAnalyzer()
        self.email_service = EmailService()

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

        # Send email alerts if changes detected
        all_changes = self._collect_all_changes(results)
        if all_changes:
            await self._send_change_alerts(all_changes)

        return results

    def _collect_all_changes(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect all changes from monitoring results for email alerts"""
        all_changes = []

        # Collect changes from each tier
        for tier in ["stable", "preview", "beta"]:
            tier_result = results.get(tier, {})
            for change in tier_result.get("changes", []):
                all_changes.append({
                    "type": change.get("change_type", "unknown"),
                    "field": change.get("field_path", "N/A"),
                    "endpoint": change.get("endpoint", "N/A"),
                    "severity": change.get("severity", "info"),
                    "tier": tier,
                    "summary": change.get("ai_summary", "No summary available")
                })

        # Collect tier comparison changes
        for comparison in ["preview_vs_stable", "beta_vs_stable"]:
            comp_result = results.get(comparison, {})
            for item in comp_result.get("changes", []):
                change = item.get("change", {})
                all_changes.append({
                    "type": change.get("change_type", "unknown"),
                    "field": change.get("field_path", "N/A"),
                    "endpoint": item.get("endpoint", change.get("endpoint", "N/A")),
                    "severity": change.get("severity", "info"),
                    "tier": item.get("maturity", "preview"),
                    "summary": item.get("ai_summary", "No summary available")
                })

        return all_changes

    async def _send_change_alerts(self, changes: List[Dict[str, Any]]) -> None:
        """Send email alerts to all subscribers"""
        if not self.email_service.enabled:
            logger.info("Email service not configured, skipping alerts")
            return

        # Get all active subscribers
        subscribers = self.db.query(AlertSubscription).filter(
            AlertSubscription.is_active == True
        ).all()

        if not subscribers:
            logger.info("No active subscribers, skipping email alerts")
            return

        logger.info(f"Sending change alerts to {len(subscribers)} subscribers...")

        for subscriber in subscribers:
            try:
                success = self.email_service.send_change_alert(
                    to_email=subscriber.email,
                    to_name=subscriber.name,
                    changes=changes
                )
                if success:
                    logger.info(f"Alert sent to {subscriber.email}")
                else:
                    logger.warning(f"Failed to send alert to {subscriber.email}")
            except Exception as e:
                logger.error(f"Error sending alert to {subscriber.email}: {e}")
    
    async def _monitor_tier(self, spec_type: str) -> Dict[str, Any]:
        """Monitor a single tier for all endpoints"""
        logger.info(f"Monitoring {spec_type} tier...")

        all_changes_detected = []
        snapshot_ids = []
        endpoints_monitored = []

        # Monitor all configured endpoints
        for endpoint_path in self.crawler.MONITORED_ENDPOINTS:
            try:
                result = await self._monitor_endpoint(endpoint_path, spec_type)
                snapshot_ids.append(result["snapshot_id"])
                all_changes_detected.extend(result["changes"])
                endpoints_monitored.append(endpoint_path)
                logger.info(f"Monitored {endpoint_path} ({spec_type}): {result['changes_count']} changes")
            except Exception as e:
                logger.error(f"Failed to monitor {endpoint_path} ({spec_type}): {e}")

        return {
            "spec_type": spec_type,
            "endpoints_monitored": endpoints_monitored,
            "snapshot_ids": snapshot_ids,
            "changes_count": len(all_changes_detected),
            "changes": all_changes_detected
        }

    async def _monitor_endpoint(self, endpoint_path: str, spec_type: str) -> Dict[str, Any]:
        """Monitor a single endpoint within a tier"""
        # Fetch current schema
        current_schema = await self.crawler.get_endpoint_snapshot(endpoint_path, spec_type)

        # Get previous snapshot for this endpoint and tier
        previous_snapshot = self._get_latest_snapshot(spec_type, endpoint_path)

        # Create new snapshot
        spec_type_enum = SpecType[spec_type.upper()]
        new_snapshot = Snapshot(
            gateway="stripe",
            endpoint_path=endpoint_path,
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

                old_val = change_data.get("old_value")
                new_val = change_data.get("new_value")
                if isinstance(old_val, dict):
                    old_val = json.dumps(old_val)
                elif old_val is not None:
                    old_val = str(old_val)
                if isinstance(new_val, dict):
                    new_val = json.dumps(new_val)
                elif new_val is not None:
                    new_val = str(new_val)

                # Add endpoint info to change data for email context
                change_data["endpoint"] = endpoint_path

                change_record = Change(
                    snapshot_id=new_snapshot.id,
                    change_type=change_data["change_type"],
                    field_path=change_data["field_path"],
                    old_value=old_val,
                    new_value=new_val,
                    severity=change_data.get("severity", "medium"),
                    change_category=category,
                    change_maturity=ChangeMaturity.STABLE_CHANGE if spec_type == "stable" else None,
                    ai_summary=ai_summary
                )
                self.db.add(change_record)
                changes_detected.append(change_data)

            self.db.commit()

        return {
            "endpoint": endpoint_path,
            "spec_type": spec_type,
            "snapshot_id": str(new_snapshot.id),
            "changes_count": len(changes_detected),
            "changes": changes_detected
        }
    
    async def _compare_tiers(self, source_tier: str, target_tier: str, endpoint_filter: str = None) -> Dict[str, Any]:
        """Compare two tiers to find differences across all endpoints or a specific endpoint"""
        logger.info(f"Comparing {source_tier} vs {target_tier}..." + (f" (endpoint: {endpoint_filter})" if endpoint_filter else ""))

        all_analyzed_changes = []
        maturity = ChangeMaturity.NEW_PREVIEW if source_tier == "preview" else ChangeMaturity.NEW_BETA

        # Determine which endpoints to compare
        endpoints_to_compare = [endpoint_filter] if endpoint_filter else self.crawler.MONITORED_ENDPOINTS

        # Compare each endpoint
        for endpoint_path in endpoints_to_compare:
            source_snapshot = self._get_latest_snapshot(source_tier, endpoint_path)
            target_snapshot = self._get_latest_snapshot(target_tier, endpoint_path)

            if not source_snapshot or not target_snapshot:
                logger.warning(f"Missing snapshots for {endpoint_path} comparison")
                continue

            # Find what's in source but not in target (upcoming features)
            changes = self.diff_engine.compare_schemas(
                target_snapshot.schema_data,
                source_snapshot.schema_data
            )

            for change_data in changes:
                change_data["endpoint"] = endpoint_path
                ai_summary = await self.ai_analyzer.analyze_change(change_data)

                # Save change to database (associated with source snapshot since it's the newer one)
                old_val = str(change_data.get("old_value", ""))[:500]
                new_val = str(change_data.get("new_value", ""))[:500]

                # Check if this change already exists for this snapshot
                existing_change = self.db.query(Change).filter(
                    Change.snapshot_id == source_snapshot.id,
                    Change.field_path == change_data["field_path"],
                    Change.change_type == change_data["change_type"]
                ).first()

                if not existing_change:
                    change_record = Change(
                        snapshot_id=source_snapshot.id,
                        change_type=change_data["change_type"],
                        field_path=change_data["field_path"],
                        old_value=old_val,
                        new_value=new_val,
                        severity=change_data.get("severity", "info"),
                        change_category=change_data.get("category"),
                        change_maturity=maturity,
                        ai_summary=ai_summary
                    )
                    self.db.add(change_record)

                all_analyzed_changes.append({
                    "change": change_data,
                    "endpoint": endpoint_path,
                    "maturity": maturity.value,
                    "ai_summary": ai_summary,
                    "timeline": "4-10 weeks" if source_tier == "preview" else "Unknown"
                })

            # Commit changes for this endpoint
            self.db.commit()

        return {
            "comparison": f"{source_tier}_vs_{target_tier}",
            "upcoming_features_count": len(all_analyzed_changes),
            "changes": all_analyzed_changes
        }
    
    def _get_latest_snapshot(self, spec_type: str, endpoint_path: str = "/v1/payment_intents") -> Optional[Snapshot]:
        """Get the most recent snapshot for a spec type and endpoint"""
        spec_type_enum = SpecType[spec_type.upper()]
        return self.db.query(Snapshot) \
            .filter(Snapshot.gateway == "stripe") \
            .filter(Snapshot.endpoint_path == endpoint_path) \
            .filter(Snapshot.spec_type == spec_type_enum) \
            .order_by(Snapshot.created_at.desc()) \
            .first()