"""
APEX_OMEGA_De1 · Point d'entrée principal
FastAPI (health) + APScheduler (tâches auto) + Pipeline Bundesliga
"""
import asyncio, logging
from threading import Thread
import uvicorn

from pipeline            import ApexBundesligaPipeline
from interfaces.scheduler import ApexScheduler
from interfaces.api_server import app
from config.settings      import PORT, LOG_LEVEL

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("apex.main")


def run_api():
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")


async def run_bot():
    pipeline  = ApexBundesligaPipeline()
    scheduler = ApexScheduler(pipeline)
    scheduler.start()
    logger.info("✅ APEX-OMEGA De1 Bot démarré — Bundesliga Only")
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    Thread(target=run_api, daemon=True).start()
    asyncio.run(run_bot())
