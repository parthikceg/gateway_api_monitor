"""APScheduler configuration for periodic monitoring"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import logging

from app.config import get_settings
from app.db.database import SessionLocal
from app.services.monitoring_service import MonitoringService
from app.services.email_service import EmailService
from app.models.models import Change, AlertSubscription

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


async def weekly_digest_job():
    """Send weekly digest emails to all subscribers"""
    logger.info("Running weekly digest job...")
    db = SessionLocal()
    try:
        email_service = EmailService()

        if not email_service.enabled:
            logger.info("Email service not configured, skipping weekly digest")
            return

        # Get all active subscribers
        subscribers = db.query(AlertSubscription).filter(
            AlertSubscription.is_active == True
        ).all()

        if not subscribers:
            logger.info("No active subscribers, skipping weekly digest")
            return

        # Get changes from the past week
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_changes = db.query(Change).filter(
            Change.detected_at >= week_ago
        ).order_by(Change.detected_at.desc()).all()

        # Format changes for email
        changes_list = []
        for change in recent_changes:
            changes_list.append({
                "type": change.change_type,
                "field": change.field_path,
                "endpoint": change.snapshot.endpoint_path if change.snapshot else "N/A",
                "severity": change.severity,
                "tier": change.snapshot.spec_type.value if change.snapshot else "unknown",
                "summary": change.ai_summary or "No summary available"
            })

        # Calculate week dates
        week_end = datetime.utcnow()
        week_start = week_end - timedelta(days=7)
        week_start_str = week_start.strftime("%b %d")
        week_end_str = week_end.strftime("%b %d, %Y")

        logger.info(f"Sending weekly digest to {len(subscribers)} subscribers ({len(changes_list)} changes)...")

        for subscriber in subscribers:
            try:
                success = email_service.send_weekly_digest(
                    to_email=subscriber.email,
                    to_name=subscriber.name,
                    changes=changes_list,
                    week_start=week_start_str,
                    week_end=week_end_str
                )
                if success:
                    logger.info(f"Weekly digest sent to {subscriber.email}")
                else:
                    logger.warning(f"Failed to send digest to {subscriber.email}")
            except Exception as e:
                logger.error(f"Error sending digest to {subscriber.email}: {e}")

    except Exception as e:
        logger.error(f"Weekly digest job failed: {e}")
    finally:
        db.close()


def start_scheduler():
    """Start the scheduler"""
    # Daily monitoring job
    scheduler.add_job(
        scheduled_monitoring_job,
        trigger=IntervalTrigger(hours=settings.crawl_schedule_hours),
        id="monitoring_job",
        name="Monitor Stripe API changes",
        replace_existing=True
    )

    # Weekly digest job (default: Monday 9 AM)
    scheduler.add_job(
        weekly_digest_job,
        trigger=CronTrigger(
            day_of_week=settings.weekly_digest_day,
            hour=settings.weekly_digest_hour,
            minute=0
        ),
        id="weekly_digest_job",
        name="Send weekly digest emails",
        replace_existing=True
    )

    scheduler.start()
    logger.info(f"Scheduler started - monitoring every {settings.crawl_schedule_hours} hours")
    logger.info(f"Weekly digest scheduled for day {settings.weekly_digest_day} at {settings.weekly_digest_hour}:00")


def stop_scheduler():
    """Stop the scheduler"""
    scheduler.shutdown()
    logger.info("Scheduler stopped")
