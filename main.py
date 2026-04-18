"""
APEX_OMEGA_De1 · Point d'entrée principal
FastAPI (health) + APScheduler + Telegram Bot (polling) + Pipeline Bundesliga
"""
import asyncio
import logging
import sys
from threading import Thread

import uvicorn

from pipeline              import ApexBundesligaPipeline
from interfaces.scheduler  import ApexScheduler
from interfaces.api_server import app as fastapi_app
from interfaces.commands   import build_application
from config.settings       import LOG_LEVEL, PORT, DEBUG

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run_api() -> None:
    """FastAPI en thread daemon pour le health check Render."""
    uvicorn.run(
        fastapi_app,
        host="0.0.0.0",
        port=PORT,
        log_level="warning",
        access_log=False,
    )


async def run_bot() -> None:
    """Loop principal : pipeline + scheduler + Telegram polling."""
    pipeline  = ApexBundesligaPipeline()
    scheduler = ApexScheduler(pipeline)
    scheduler.start()

    # ── Telegram Application (polling des commandes /scan)
    tg_app = build_application(pipeline)
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(
        allowed_updates=["message"],
        drop_pending_updates=True,
    )

    logger.info("=" * 55)
    logger.info("  APEX-OMEGA Bundesliga Bot v1.4 — DÉMARRÉ ✓")
    logger.info(f"  API Health  : http://0.0.0.0:{PORT}/health")
    logger.info("  Commandes   : /scan today|24h|Nh|week|month|next|status|help")
    logger.info("=" * 55)

    if DEBUG:
        logger.info("Mode DEBUG : scan immédiat au démarrage")
        await pipeline.daily_scan()

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
        logger.info("Bot arrêté proprement ✓")


if __name__ == "__main__":
    Thread(target=run_api, daemon=True, name="api-server").start()
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Arrêt manuel (KeyboardInterrupt)")
