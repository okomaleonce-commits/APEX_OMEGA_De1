"""
APEX_OMEGA_De1 · Scheduler APScheduler — tâches automatisées
"""
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class ApexScheduler:

    def __init__(self, pipeline):
        self.pipeline  = pipeline
        self.scheduler = AsyncIOScheduler(timezone="UTC")

    def setup(self) -> None:
        jobs = [
            # 07:00 UTC — scan quotidien fixtures 7 jours
            ("daily_scan",    self.pipeline.daily_scan,
             CronTrigger(hour=7, minute=0)),
            # Toutes les 2h — refresh cotes + compos
            ("odds_refresh",  self.pipeline.refresh_odds_lineups,
             IntervalTrigger(hours=2)),
            # Toutes les 30min — check matchs en direct
            ("live_check",    self.pipeline.check_live,
             IntervalTrigger(minutes=30)),
            # 02:00 UTC — audit post-match journée précédente
            ("post_audit",    self.pipeline.run_audit,
             CronTrigger(hour=2, minute=0)),
        ]
        for jid, func, trigger in jobs:
            self.scheduler.add_job(
                func, trigger,
                id=jid, name=jid, replace_existing=True,
                misfire_grace_time=120,
            )
        logger.info("APEX Scheduler : 4 jobs configurés")

    def start(self) -> None:
        self.setup()
        self.scheduler.start()
        logger.info("APEX Scheduler démarré ✓")

    def stop(self) -> None:
        self.scheduler.shutdown(wait=False)
        logger.info("APEX Scheduler arrêté")
