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
    """
    Matchs Bundesliga à venir.
    Stratégie double :
    1. Paramètre next=50 → API retourne les 50 prochains matchs NS directement
    2. Fallback from/to si next retourne vide (hors saison, pré-saison...)
    Filtre final : timestamp < now + days_ahead * 86400
    """
    now    = datetime.utcnow()
    cutoff = now.timestamp() + days_ahead * 86400

    # ── Stratégie 1 : paramètre next (le plus fiable)
    try:
        resp = requests.get(
            f"{BASE_URL}/fixtures",
            headers=HEADERS,
            params={
                "league":  BUNDESLIGA_API_ID,
                "season":  get_active_season(),
                "next":    50,              # 50 prochains matchs NS
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("response", [])

        if data:
            # Filtrer sur la fenêtre days_ahead
            filtered = [
                fx for fx in data
                if (fx.get("fixture", {}).get("timestamp") or 0) <= cutoff
            ]
            logger.info(
                f"API-Football (next=50): {len(filtered)}/{len(data)} "
                f"fixtures BL dans les {days_ahead}j"
            )
            return filtered
    except Exception as e:
        logger.warning(f"API next=50 échoué: {e} — fallback from/to")

    # ── Stratégie 2 : fallback from/to sans filtre status
    try:
        today = now.date()
        to    = today + timedelta(days=days_ahead)
        resp  = requests.get(
            f"{BASE_URL}/fixtures",
            headers=HEADERS,
            params={
                "league":  BUNDESLIGA_API_ID,
                "season":  get_active_season(),
                "from":    str(today),
                "to":      str(to),
            },
            timeout=15,
        )
        resp.raise_for_status()
        all_data = resp.json().get("response", [])
        upcoming = [
            fx for fx in all_data
            if (fx.get("fixture", {}).get("timestamp") or 0) > now.timestamp()
        ]
        logger.info(
            f"API-Football (from/to fallback): {len(upcoming)}/{len(all_data)} "
            f"fixtures BL à venir"
        )
        return upcoming
    except Exception as e:
        logger.error(f"get_upcoming_fixtures fallback échoué: {e}")
        return []


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


def get_fixture_result(fixture_id: int) -> dict:
    """
    Retourne le score final d'un match terminé.
    Utilisé par l'audit post-match.
    Returns: {"home_goals": int, "away_goals": int, "status": str}
    """
    resp = requests.get(
        f"{BASE_URL}/fixtures",
        headers=HEADERS,
        params={"id": fixture_id},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json().get("response", [])
    if not data:
        return {}
    f = data[0]
    goals = f.get("goals", {})
    return {
        "home_goals": goals.get("home", 0) or 0,
        "away_goals": goals.get("away", 0) or 0,
        "status":     f.get("fixture", {}).get("status", {}).get("short", "?"),
    }


def compute_win_rate(fixtures: list, team_id: int, last: int = 8) -> float:
    """
    Calcule le taux de victoire sur les N derniers matchs d'une équipe.
    Returns: float entre 0.0 et 1.0
    """
    if not fixtures:
        return 0.40  # valeur par défaut Bundesliga
    wins = 0
    valid = [f for f in fixtures[-last:] if isinstance(f, dict)]
    if not valid:
        return 0.40
    for f in valid:
        teams = f.get("teams") or {}
        if not isinstance(teams, dict):
            continue
        home  = teams.get("home") or {}
        away  = teams.get("away") or {}
        if isinstance(home, dict) and home.get("id") == team_id and home.get("winner"):
            wins += 1
        elif isinstance(away, dict) and away.get("id") == team_id and away.get("winner"):
            wins += 1
    return round(wins / len(valid), 3)


def compute_h2h_avg_goals(h2h_fixtures: list[dict]) -> float:
    """
    Calcule la moyenne de buts par match sur l'historique H2H.
    Returns: float (ex: 2.6)
    """
    if not h2h_fixtures:
        return 2.6  # moyenne Bundesliga par défaut
    totals = []
    for f in h2h_fixtures:
        goals = f.get("goals", {})
        hg = goals.get("home") or 0
        ag = goals.get("away") or 0
        totals.append(hg + ag)
    return round(sum(totals) / len(totals), 2) if totals else 2.6


def get_active_season() -> int:
    """
    Détecte la saison Bundesliga active sur API-Football.
    Bundesliga saison = année de début (2025 = saison 2025-26).
    En avril 2026 → saison 2025.
    """
    from datetime import date
    today = date.today()
    # La saison BL commence en août et se termine en mai
    # Si on est entre janvier et juillet → saison = année précédente
    if today.month < 8:
        return today.year - 1
    return today.year

def get_standings_safe() -> list:
    """Classement actuel — détecte la bonne saison automatiquement."""
    season = get_active_season()
    try:
        resp = requests.get(
            f"{BASE_URL}/standings",
            headers=HEADERS,
            params={"league": BUNDESLIGA_API_ID, "season": season},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("response", [])
    except Exception as e:
        logger.error(f"Standings: {e}")
        return []
