"""
APEX_OMEGA_De1 · Point d'entrée principal
Lance le bot Bundesliga + l'API FastAPI + le scheduler APScheduler.
"""
import asyncio
import logging
import sys
from threading import Thread

import uvicorn

from pipeline             import ApexBundesligaPipeline
from interfaces.scheduler import ApexScheduler
from interfaces.api_server import app
from config.settings      import LOG_LEVEL, PORT, DEBUG

# ── Logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run_api() -> None:
    """Lance FastAPI en thread séparé (health check Render)."""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="warning",
        access_log=False,
    )


async def run_bot() -> None:
    """Lance le pipeline + scheduler dans le loop asyncio principal."""
    pipeline  = ApexBundesligaPipeline()
    scheduler = ApexScheduler(pipeline)
    scheduler.start()

    logger.info("=" * 55)
    logger.info("  APEX-OMEGA Bundesliga Bot v1.4 — DÉMARRÉ ✓")
    logger.info(f"  API Health : http://0.0.0.0:{PORT}/health")
    logger.info("=" * 55)

    # Scan immédiat au démarrage (optionnel en prod — commenter si besoin)
    if DEBUG:
        logger.info("Mode DEBUG : scan immédiat au démarrage")
        await pipeline.daily_scan()

    # Garder le loop actif indéfiniment
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        scheduler.stop()
        logger.info("Bot arrêté proprement")


if __name__ == "__main__":
    # API dans un thread daemon
    api_thread = Thread(target=run_api, daemon=True, name="api-server")
    api_thread.start()

    # Bot dans le loop principal
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Arrêt manuel (KeyboardInterrupt)")
