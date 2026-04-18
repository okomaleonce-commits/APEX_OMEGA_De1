"""APEX_OMEGA_De1 · Settings — Variables d'environnement"""
import os
from pathlib import Path

# ── Stockage persistant (Render Disk)
BASE_DATA_DIR     = Path(os.getenv("DATA_DIR", "/data"))
SIGNALS_DIR       = BASE_DATA_DIR / "signals"
OUTCOMES_DIR      = BASE_DATA_DIR / "outcomes"
CALIBRATION_DIR   = BASE_DATA_DIR / "calibration"

# ── Telegram
TELEGRAM_BOT_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]

# ── APIs données foot
API_FOOTBALL_KEY  = os.environ["API_FOOTBALL_KEY"]
BETFAIR_APP_KEY   = os.environ.get("BETFAIR_APP_KEY", "")
BETFAIR_SESSION   = os.environ.get("BETFAIR_SESSION_TOKEN", "")
PINNACLE_KEY      = os.environ.get("PINNACLE_API_KEY", "")
FOOTYSTATS_KEY    = os.environ.get("FOOTYSTATS_KEY", "")

# ── Bundesliga
BUNDESLIGA_API_ID = 78
BUNDESLIGA_SEASON = int(os.getenv("SEASON", "2025"))

# ── Scheduler (heures UTC)
DAILY_SCAN_HOUR     = int(os.getenv("DAILY_SCAN_HOUR", "7"))
PRE_MATCH_HOURS     = 2
POST_MATCH_DELAY_MIN = 90

# ── Runtime
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
