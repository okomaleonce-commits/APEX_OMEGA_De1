"""
APEX_OMEGA_De1 · Point d'entrée principal
FastAPI health + APScheduler + Telegram Bot (polling) + Pipeline Bundesliga
"""
import asyncio
import logging
import sys
from threading import Thread

import uvicorn

from pipeline                    import ApexBundesligaPipeline
from interfaces.scheduler        import ApexScheduler
from interfaces.api_server       import app as fastapi_app
from interfaces.telegram_commands import (
    build_application, register_commands, set_pipeline,
)
from config.settings import LOG_LEVEL, PORT, DEBUG

# ── Logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run_api() -> None:
    """Lance FastAPI en thread daemon (health check Render)."""
    uvicorn.run(
        fastapi_app,
        host="0.0.0.0",
        port=PORT,
        log_level="warning",
        access_log=False,
    )


async def run_bot() -> None:
    """
    Boucle principale :
      - Pipeline APEX + Scheduler APScheduler
      - Application Telegram (polling) avec commandes /scan /status /help
    """
    # ── Pipeline
    pipeline  = ApexBundesligaPipeline()
    scheduler = ApexScheduler(pipeline)
    scheduler.start()

    # ── Telegram Application (commandes)
    tg_app = build_application()
    set_pipeline(pipeline)            # injecte pipeline dans les handlers

    await register_commands(tg_app)   # enregistre /scan /status /help
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(
        allowed_updates=["message"],
        drop_pending_updates=True,    # ignore les commandes envoyées hors ligne
    )

    logger.info("=" * 55)
    logger.info("  APEX-OMEGA Bundesliga Bot v1.4 — DÉMARRÉ ✓")
    logger.info(f"  API Health  : http://0.0.0.0:{PORT}/health")
    logger.info("  Commandes   : /scan /status /help")
    logger.info("=" * 55)

    # ── Scan immédiat en mode DEBUG
    if DEBUG:
        logger.info("Mode DEBUG : scan immédiat")
        await pipeline.daily_scan()

    # ── Garder le loop actif
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await tg_app.updater.stop()
        await tg_app.stop()
        await tg_app.shutdown()
        scheduler.stop()
        logger.info("Bot arrêté proprement")


if __name__ == "__main__":
    # API FastAPI dans un thread daemon
    Thread(target=run_api, daemon=True, name="api-server").start()

    # Bot dans le loop asyncio principal
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Arrêt manuel")
