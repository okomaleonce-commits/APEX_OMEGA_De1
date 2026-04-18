"""
APEX_OMEGA_De1 · Fixtures Service
Source : API-Football v3 (api-sports.io)
Header : x-apisports-key = API_KEY
"""
import logging
import requests
from datetime import datetime, timedelta
from config.settings import API_KEY, BUNDESLIGA_API_ID, BUNDESLIGA_SEASON

logger = logging.getLogger(__name__)
BASE_URL = "https://v3.football.api-sports.io"
HEADERS  = {"x-apisports-key": API_KEY}


def get_upcoming_fixtures(days_ahead: int = 7) -> list[dict]:
    """Matchs Bundesliga des N prochains jours (statut NS = Not Started)."""
    today = datetime.utcnow().date()
    to    = today + timedelta(days=days_ahead)
    resp  = requests.get(
        f"{BASE_URL}/fixtures",
        headers=HEADERS,
        params={
            "league":  BUNDESLIGA_API_ID,
            "season":  BUNDESLIGA_SEASON,
            "from":    str(today),
            "to":      str(to),
            "status":  "NS",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json().get("response", [])
    logger.info(f"API-Football: {len(data)} fixtures Bundesliga à venir")
    return data


def get_team_form(team_id: int, last: int = 8) -> list[dict]:
    """N derniers matchs d'une équipe (tous statuts terminés)."""
    resp = requests.get(
        f"{BASE_URL}/fixtures",
        headers=HEADERS,
        params={"team": team_id, "season": BUNDESLIGA_SEASON,
                "last": last, "status": "FT"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("response", [])


def get_h2h(home_id: int, away_id: int, last: int = 10) -> list[dict]:
    """Historique H2H entre deux équipes."""
    resp = requests.get(
        f"{BASE_URL}/fixtures/headtohead",
        headers=HEADERS,
        params={"h2h": f"{home_id}-{away_id}", "last": last},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("response", [])


def get_standings(season: int = None) -> list[dict]:
    """Classement Bundesliga (utile pour rangs UCL/Relégation)."""
    resp = requests.get(
        f"{BASE_URL}/standings",
        headers=HEADERS,
        params={"league": BUNDESLIGA_API_ID,
                "season": season or BUNDESLIGA_SEASON},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("response", [])


def get_fixture_stats(fixture_id: int) -> dict:
    """Stats post-match d'un fixture (audit)."""
    resp = requests.get(
        f"{BASE_URL}/fixtures/statistics",
        headers=HEADERS,
        params={"fixture": fixture_id},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("response", {})
