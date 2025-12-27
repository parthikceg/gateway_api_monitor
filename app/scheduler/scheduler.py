"""APScheduler configuration for periodic monitoring"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging

from app.config import get_settings
from app.db.database import SessionLocal
from app.services.monitoring_service import MonitoringService

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


def start_scheduler():
    """Start the scheduler"""
    scheduler.add_job(
        scheduled_monitoring_job,
        trigger=IntervalTrigger(hours=settings.crawl_schedule_hours),
        id="monitoring_job",
        name="Monitor Stripe API changes",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"Scheduler started - monitoring every {settings.crawl_schedule_hours} hours")


def stop_scheduler():
    """Stop the scheduler"""
    scheduler.shutdown()
    logger.info("Scheduler stopped")
