"""
APEX_OMEGA_De1 · Settings
Variables d'environnement réelles disponibles sur Render
"""
import os
from pathlib import Path

# ── Stockage persistant (Render Disk mountPath: /data)
BASE_DATA_DIR   = Path(os.getenv("DATA_DIR", "/data"))
SIGNALS_DIR     = BASE_DATA_DIR / "signals"
OUTCOMES_DIR    = BASE_DATA_DIR / "outcomes"
CALIBRATION_DIR = BASE_DATA_DIR / "calibration"

# ── Telegram
BOT_TOKEN = os.environ["BOT_TOKEN"]        # @BotFather
CHAT_ID   = os.environ["CHAT_ID"]          # @channel ou -1001XXXXXXX

# ── API-Football (v3.football.api-sports.io)
API_KEY   = os.environ["API_KEY"]          # header: x-apisports-key

# ── The Odds API (https://the-odds-api.com)
ODDS_API_KEY        = os.environ["ODDS_API_KEY"]
ODDS_API_BOOKMAKERS = os.environ.get("ODDS_API_BOOKMAKERS", "pinnacle,betfair_ex_eu,unibet")

# ── FootyStats (xG + stats avancées)
FOOTYSTATS_KEY = os.environ["FOOTYSTATS_KEY"]

# ── Bundesliga
BUNDESLIGA_API_ID = 78
BUNDESLIGA_SEASON = int(os.getenv("SEASON", "2025"))

# ── Runtime
DEBUG            = os.getenv("DEBUG", "false").lower() == "true"
DAILY_SCAN_HOUR  = int(os.getenv("DAILY_SCAN_HOUR", "7"))
