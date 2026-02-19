"""Multi-tier monitoring service orchestrator"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio
import logging
import json

from sqlalchemy import text
from app.services.stripe_crawler import StripeCrawler
from app.services.diff_engine import DiffEngine
from app.services.ai_analyzer import AIAnalyzer
from app.services.email_service import EmailService
from app.models.models import Snapshot, Change, AlertSubscription, SpecType, ChangeMaturity
from app.db.database import SessionLocal

logger = logging.getLogger(__name__)

class MonitoringService:
    """Orchestrates multi-tier monitoring workflow"""

    def __init__(self, db: Session):
        self.db = db
        self.crawler = StripeCrawler()
        self.diff_engine = DiffEngine()
        self.ai_analyzer = AIAnalyzer()
        self.email_service = EmailService()

    def _ensure_db_connection(self):
        """Check if DB connection is alive; reconnect if stale"""
        try:
            self.db.execute(text("SELECT 1"))
        except Exception:
            logger.warning("DB connection stale, reconnecting...")
            try:
                self.db.close()
            except Exception:
                pass
            self.db = SessionLocal()
            logger.info("DB reconnected successfully")

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

        # Batch AI summarization for ALL changes across all tiers
        await self._batch_summarize_all(results)

        # Send email alerts if changes detected
        all_changes = self._collect_all_changes(results)
        if all_changes:
            await self._send_change_alerts(all_changes)

        return results

    async def _batch_summarize_all(self, results: Dict[str, Any]) -> None:
        """Collect all unsummarized changes and summarize in one batch AI call"""
        all_change_records = []

        # Gather change record IDs from tier monitoring
        for tier in ["stable", "preview", "beta"]:
            tier_result = results.get(tier, {})
            all_change_records.extend(tier_result.get("_change_record_ids", []))

        # Gather from tier comparisons
        for comparison in ["preview_vs_stable", "beta_vs_stable"]:
            comp_result = results.get(comparison, {})
            all_change_records.extend(comp_result.get("_change_record_ids", []))

        if not all_change_records:
            logger.info("No changes to summarize")
            return

        # Load the Change records from DB
        change_ids = [r["id"] for r in all_change_records]
        change_data_list = [r["data"] for r in all_change_records]

        logger.info(f"Batch summarizing {len(change_ids)} changes with AI...")

        # One batch AI call for all changes
        summaries = await self.ai_analyzer.batch_summarize(change_data_list)

        # Ensure DB connection is alive (AI calls can take minutes)
        self._ensure_db_connection()

        # Bulk update all summaries in one query instead of N individual queries
        update_mappings = [
            {"id": cid, "ai_summary": summary}
            for cid, summary in zip(change_ids, summaries)
            if summary
        ]
        if update_mappings:
            self.db.bulk_update_mappings(Change, update_mappings)
            self.db.commit()
        logger.info(f"Bulk updated {len(update_mappings)} changes with AI summaries")

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
        all_change_record_ids = []
        snapshot_ids = []
        endpoints_monitored = []

        # Monitor all configured endpoints
        for endpoint_path in self.crawler.MONITORED_ENDPOINTS:
            try:
                result = await self._monitor_endpoint(endpoint_path, spec_type)
                snapshot_ids.append(result["snapshot_id"])
                all_changes_detected.extend(result["changes"])
                all_change_record_ids.extend(result["_change_record_ids"])
                endpoints_monitored.append(endpoint_path)
                logger.info(f"Monitored {endpoint_path} ({spec_type}): {result['changes_count']} changes")
            except Exception as e:
                logger.error(f"Failed to monitor {endpoint_path} ({spec_type}): {e}")
                self.db.rollback()  # Reset DB session so next endpoint can proceed

        return {
            "spec_type": spec_type,
            "endpoints_monitored": endpoints_monitored,
            "snapshot_ids": snapshot_ids,
            "changes_count": len(all_changes_detected),
            "changes": all_changes_detected,
            "_change_record_ids": all_change_record_ids
        }

    async def _monitor_endpoint(self, endpoint_path: str, spec_type: str) -> Dict[str, Any]:
        """Monitor a single endpoint within a tier"""
        # Fetch current schema
        current_schema = await self.crawler.get_endpoint_snapshot(endpoint_path, spec_type)

        # Ensure DB connection is alive (schema fetch can take a long time)
        self._ensure_db_connection()

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
        change_record_ids = []
        if previous_snapshot:
            changes = self.diff_engine.compare_schemas(
                previous_snapshot.schema_data,
                current_schema
            )

            # Save changes with rule-based severity (no AI calls)
            for change_data in changes:
                severity = self.ai_analyzer.classify_severity(change_data)
                category = self.ai_analyzer.categorize_change(change_data)

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
                change_data["severity"] = severity

                change_record = Change(
                    snapshot_id=new_snapshot.id,
                    change_type=change_data["change_type"],
                    field_path=change_data["field_path"],
                    old_value=old_val,
                    new_value=new_val,
                    severity=severity,
                    change_category=category,
                    change_maturity={
                        "stable": ChangeMaturity.STABLE_CHANGE.value,
                        "preview": ChangeMaturity.PREVIEW_CHANGE.value,
                        "beta": ChangeMaturity.BETA_CHANGE.value,
                    }[spec_type],
                    ai_summary=None  # Will be filled by batch summarization
                )
                self.db.add(change_record)
                self.db.flush()  # Get the ID without committing

                changes_detected.append(change_data)
                change_record_ids.append({"id": change_record.id, "data": change_data})

            self.db.commit()

        return {
            "endpoint": endpoint_path,
            "spec_type": spec_type,
            "snapshot_id": str(new_snapshot.id),
            "changes_count": len(changes_detected),
            "changes": changes_detected,
            "_change_record_ids": change_record_ids
        }

    async def _compare_tiers(self, source_tier: str, target_tier: str, endpoint_filter: str = None) -> Dict[str, Any]:
        """Compare two tiers to find differences across all endpoints or a specific endpoint.

        Cross-tier differences are saved to the Changes table with CROSS_TIER_PREVIEW
        or CROSS_TIER_BETA maturity. To avoid duplicate accumulation, old cross-tier
        records for the same maturity are deleted before inserting fresh ones.
        """
        logger.info(f"Comparing {source_tier} vs {target_tier}..." + (f" (endpoint: {endpoint_filter})" if endpoint_filter else ""))

        all_analyzed_changes = []
        all_change_record_ids = []
        maturity = ChangeMaturity.CROSS_TIER_PREVIEW.value if source_tier == "preview" else ChangeMaturity.CROSS_TIER_BETA.value

        # Determine which endpoints to compare
        endpoints_to_compare = [endpoint_filter] if endpoint_filter else self.crawler.MONITORED_ENDPOINTS

        # Delete old cross-tier records for this maturity to avoid duplicates
        # Use raw SQL with ::text cast to bypass PG enum type validation
        self._ensure_db_connection()
        result = self.db.execute(
            text("DELETE FROM changes WHERE change_maturity::text = :m"),
            {"m": maturity}
        )
        old_count = result.rowcount
        self.db.commit()
        if old_count:
            logger.info(f"Cleared {old_count} old {maturity} cross-tier records")

        # Compare each endpoint
        for endpoint_path in endpoints_to_compare:
            try:
                self._ensure_db_connection()
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
                    severity = self.ai_analyzer.classify_severity(change_data)
                    change_data["severity"] = severity

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

                    category = self.ai_analyzer.categorize_change(change_data)

                    # Use raw SQL INSERT to bypass PG enum type validation
                    import uuid
                    record_id = uuid.uuid4()
                    self.db.execute(
                        text("""
                            INSERT INTO changes (id, snapshot_id, change_type, field_path,
                                old_value, new_value, severity, change_category,
                                change_maturity, ai_summary, detected_at)
                            VALUES (:id, :snapshot_id, :change_type, :field_path,
                                :old_value, :new_value, :severity, :change_category,
                                :change_maturity, :ai_summary, :detected_at)
                        """),
                        {
                            "id": str(record_id),
                            "snapshot_id": str(source_snapshot.id),
                            "change_type": change_data["change_type"],
                            "field_path": change_data["field_path"],
                            "old_value": old_val,
                            "new_value": new_val,
                            "severity": severity,
                            "change_category": category,
                            "change_maturity": maturity,
                            "ai_summary": None,
                            "detected_at": datetime.utcnow(),
                        }
                    )

                    all_change_record_ids.append({"id": record_id, "data": change_data})
                    all_analyzed_changes.append({
                        "change": change_data,
                        "endpoint": endpoint_path,
                        "maturity": maturity,
                        "timeline": "4-10 weeks" if source_tier == "preview" else "Unknown"
                    })

                self.db.commit()
                logger.info(f"Compared {endpoint_path}: {len(changes)} cross-tier differences")

            except Exception as e:
                logger.error(f"Failed to compare {endpoint_path} ({source_tier} vs {target_tier}): {e}")
                self.db.rollback()

        return {
            "comparison": f"{source_tier}_vs_{target_tier}",
            "upcoming_features_count": len(all_analyzed_changes),
            "changes": all_analyzed_changes,
            "_change_record_ids": all_change_record_ids
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
