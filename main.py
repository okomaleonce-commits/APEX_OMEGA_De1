"""
APEX_OMEGA_De1 · Point d'entrée principal
FastAPI (health) + APScheduler + Telegram Bot (polling + commandes)
"""
import asyncio
import logging
import sys
from threading import Thread

import uvicorn

from pipeline                     import ApexBundesligaPipeline
from interfaces.scheduler         import ApexScheduler
from interfaces.api_server        import app as fastapi_app
from interfaces.telegram_commands import (
    build_application, register_commands, set_pipeline,
)
from config.settings import LOG_LEVEL, PORT, DEBUG

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run_api() -> None:
    """Lance FastAPI dans un thread daemon (health check Render)."""
    uvicorn.run(
        fastapi_app,
        host="0.0.0.0",
        port=PORT,
        log_level="warning",
        access_log=False,
    )


async def run_bot() -> None:
    """Lance pipeline + scheduler + Telegram polling dans le loop principal."""
    # ── Pipeline
    pipeline  = ApexBundesligaPipeline()

    # ── Scheduler APScheduler
    scheduler = ApexScheduler(pipeline)
    scheduler.start()

    # ── Telegram Application (polling + commandes)
    tg_app = build_application()
    set_pipeline(pipeline)                   # injecter pipeline dans les handlers
    await register_commands(tg_app)          # enregistrer menu BotFather

    logger.info("=" * 55)
    logger.info("  APEX-OMEGA Bundesliga Bot v1.4 — DÉMARRÉ ✓")
    logger.info(f"  API Health : http://0.0.0.0:{PORT}/health")
    logger.info("  Commandes Telegram : /scan /status /help")
    logger.info("=" * 55)

    # ── Scan immédiat en mode DEBUG
    if DEBUG:
        logger.info("Mode DEBUG : scan immédiat au démarrage")
        await pipeline.daily_scan(days_ahead=3)

    # ── Démarrer le polling Telegram (non-bloquant via initialize+start)
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(
        drop_pending_updates=True,     # ignorer les commandes accumulées hors-ligne
        allowed_updates=["message"],
    )

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
        logger.info("Arrêt manuel (KeyboardInterrupt)")
