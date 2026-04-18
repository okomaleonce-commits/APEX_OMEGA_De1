"""APEX_OMEGA_De1 · APScheduler"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from config.settings import SCAN_HOUR_UTC, ODDS_REFRESH_HOURS, AUDIT_HOUR_UTC

logger = logging.getLogger(__name__)

class ApexScheduler:
    def __init__(self, pipeline):
        self.pipeline  = pipeline
        self.scheduler = AsyncIOScheduler(timezone="UTC")

    def setup(self):
        # Scan quotidien 07:00 UTC
        self.scheduler.add_job(self.pipeline.daily_scan,
            CronTrigger(hour=SCAN_HOUR_UTC, minute=0),
            id="daily_scan", replace_existing=True)
        # Refresh cotes toutes les 2h
        self.scheduler.add_job(self.pipeline.refresh_odds,
            IntervalTrigger(hours=ODDS_REFRESH_HOURS),
            id="odds_refresh", replace_existing=True)
        # Audit post-match 02:00 UTC
        self.scheduler.add_job(self.pipeline.post_match_audit,
            CronTrigger(hour=AUDIT_HOUR_UTC, minute=0),
            id="audit", replace_existing=True)
        # Ingestion mardi + vendredi 06:00 UTC
        self.scheduler.add_job(self.pipeline.ingest_fixtures,
            CronTrigger(day_of_week="tue,fri", hour=6, minute=0),
            id="ingest", replace_existing=True)
        # Analyse mardi + vendredi 09:30 UTC
        self.scheduler.add_job(self.pipeline.run_analysis,
            CronTrigger(day_of_week="tue,fri", hour=9, minute=30),
            id="analyze", replace_existing=True)
        # Audit dimanche 23:00 UTC
        self.scheduler.add_job(self.pipeline.weekly_audit,
            CronTrigger(day_of_week="sun", hour=23, minute=0),
            id="weekly_audit", replace_existing=True)

    def start(self):
        self.setup()
        self.scheduler.start()
        logger.info("APEX Scheduler started")

    def stop(self):
        self.scheduler.shutdown()
