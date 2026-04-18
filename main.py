"""
APEX_OMEGA_De1 · Point d'entrée principal
FastAPI (health + endpoints) + APScheduler + Pipeline Bundesliga
"""
import asyncio
import logging
import sys
from threading import Thread

import uvicorn

from pipeline              import ApexBundesligaPipeline
from interfaces.scheduler  import ApexScheduler
from interfaces.api_server import app, set_pipeline
from config.settings       import LOG_LEVEL, PORT, DEBUG

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run_api() -> None:
    uvicorn.run(app, host="0.0.0.0", port=PORT,
                log_level="warning", access_log=False)


async def run_bot() -> None:
    pipeline  = ApexBundesligaPipeline()
    scheduler = ApexScheduler(pipeline)

    # Injecter pipeline dans l'API pour les endpoints /scan et /audit
    set_pipeline(pipeline)

    scheduler.start()

    logger.info("=" * 55)
    logger.info("  APEX-OMEGA Bundesliga Bot v1.4 — DÉMARRÉ ✓")
    logger.info(f"  API  : https://apex-omega-de1.onrender.com")
    logger.info(f"  Port : {PORT}")
    logger.info("  Endpoints : /health /status /scan /audit /perf")
    logger.info("=" * 55)

    # Scan immédiat en mode DEBUG
    if DEBUG:
        logger.info("DEBUG : scan immédiat")
        await pipeline.daily_scan()

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        scheduler.stop()
        logger.info("Bot arrêté proprement")


if __name__ == "__main__":
    Thread(target=run_api, daemon=True, name="api-server").start()
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Arrêt manuel")
