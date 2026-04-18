"""
APEX_OMEGA_De1 · Point d'entrée principal
FastAPI (health) + APScheduler + Pipeline + Bot Telegram (commandes manuelles)
"""
import asyncio
import logging
import sys
from threading import Thread

import uvicorn

from pipeline              import ApexBundesligaPipeline
from interfaces.scheduler  import ApexScheduler
from interfaces.api_server import app
from interfaces.bot_commands import build_application, set_pipeline
from config.settings       import LOG_LEVEL, PORT, DEBUG, BOT_TOKEN

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run_api() -> None:
    """FastAPI en thread séparé — health check Render."""
    uvicorn.run(app, host="0.0.0.0", port=PORT,
                log_level="warning", access_log=False)


async def run_bot() -> None:
    """Pipeline + Scheduler + Bot Telegram dans le loop asyncio principal."""
    pipeline  = ApexBundesligaPipeline()
    scheduler = ApexScheduler(pipeline)
    scheduler.start()

    # Injecter pipeline dans les commandes Telegram
    set_pipeline(pipeline)

    # Démarrer le bot Telegram (commandes manuelles)
    tg_app = build_application()
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(
        allowed_updates=["message"],
        drop_pending_updates=True,
    )

    logger.info("=" * 55)
    logger.info("  APEX-OMEGA Bundesliga Bot v1.4 — DÉMARRÉ ✓")
    logger.info(f"  API Health  : http://0.0.0.0:{PORT}/health")
    logger.info("  Bot Telegram: /scan /status /audit /help actifs")
    logger.info("=" * 55)

    if DEBUG:
        logger.info("Mode DEBUG — scan immédiat au démarrage")
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
        logger.info("Bot arrêté proprement")


if __name__ == "__main__":
    Thread(target=run_api, daemon=True, name="api-server").start()
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Arrêt manuel")
