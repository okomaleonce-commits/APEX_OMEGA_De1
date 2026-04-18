"""
APEX_OMEGA_De1 · xG Service
Source : FootyStats API (footystats.org)
Header : key = FOOTYSTATS_KEY
Fournit : xG · BTTS rate · Over pct · CS pct · team stats avancées
"""
import logging
import requests
from config.settings import FOOTYSTATS_KEY

logger = logging.getLogger(__name__)
BASE_URL = "https://api.football-data-api.com"


def get_team_stats(team_id: int, season_id: int = None) -> dict:
    """Stats avancées d'une équipe sur la saison (xG, Over%, CS%)."""
    params = {"key": FOOTYSTATS_KEY, "team_id": team_id}
    if season_id:
        params["season_id"] = season_id
    try:
        resp = requests.get(f"{BASE_URL}/team", params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("data", {})
    except Exception as e:
        logger.error(f"FootyStats team {team_id}: {e}")
        return {}


def get_bundesliga_season_stats(season_id: int = 2012) -> list[dict]:
    """
    Stats de toutes les équipes de la saison Bundesliga.
    Bundesliga 2025-26 season_id : ~2012 (à vérifier sur FootyStats)
    """
    try:
        resp = requests.get(
            f"{BASE_URL}/league-teams",
            params={"key": FOOTYSTATS_KEY, "season_id": season_id},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as e:
        logger.error(f"FootyStats league teams: {e}")
        return []


def get_match_xg(match_id: int) -> dict:
    """xG d'un match spécifique (post-match ou pré-match modèle)."""
    try:
        resp = requests.get(
            f"{BASE_URL}/match",
            params={"key": FOOTYSTATS_KEY, "match_id": match_id},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return {
            "home_xg": data.get("home_xg", 0),
            "away_xg": data.get("away_xg", 0),
            "btts":    data.get("btts", False),
            "over_25": data.get("over25", False),
        }
    except Exception as e:
        logger.error(f"FootyStats match xG {match_id}: {e}")
        return {}
