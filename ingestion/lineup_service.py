"""
APEX_OMEGA_De1 · Lineups & Injuries — robuste, gère les variations API
"""
import logging
import requests
from config.settings import API_KEY
from bundesliga.config_v2_3 import AIS_F, AIS_F_DEFAULT

logger = logging.getLogger(__name__)
HDR  = {"x-apisports-key": API_KEY}
BASE = "https://v3.football.api-sports.io"


def get_injuries(team_id: int, fixture_id: int) -> list:
    """
    Retourne la liste des blessés/suspendus pour un match.
    Gère les variations de format API-Football (dict ou liste dans 'player').
    """
    try:
        r = requests.get(
            f"{BASE}/injuries", headers=HDR, timeout=15,
            params={"fixture": fixture_id, "team": team_id},
        )
        r.raise_for_status()
        raw = r.json().get("response", [])
        # Normaliser : s'assurer que chaque entrée est un dict avec "player" dict
        return [_normalize_injury(e) for e in raw if isinstance(e, dict)]
    except Exception as e:
        logger.warning(f"get_injuries {team_id}/{fixture_id}: {e}")
        return []


def _normalize_injury(entry: dict) -> dict:
    """Normalise une entrée injury — 'player' peut être dict ou liste."""
    player = entry.get("player", {})
    if isinstance(player, list):
        player = player[0] if player else {}
    return {
        "player": player if isinstance(player, dict) else {},
        "team":   entry.get("team", {}),
        "reason": entry.get("reason", ""),
    }


def compute_ais_f(club_name: str, absent_players: list) -> dict:
    """
    Calcule le coefficient AIS-F composite pour une équipe.
    Utilise le profil AIS_F du club si disponible, sinon valeurs par défaut.
    Returns: {"att_mult": float, "def_mult": float}
    """
    # Support appel avec 3 args (club_name, absent_list, CLUBS) → ignorer 3e arg
    profile  = AIS_F.get(club_name, {})
    att, deff = 1.0, 1.0

    for player_name in absent_players:
        if not player_name:
            continue
        impact = profile.get(player_name)
        if impact and isinstance(impact, dict):
            att  *= (1 + impact.get("off", 0))
            deff *= (1 + impact.get("def", 0))
        # else: joueur non répertorié → impact négligeable

    return {"att_mult": round(att, 3), "def_mult": round(deff, 3)}


def count_absent_defenders(injuries: list) -> int:
    """Compte les défenseurs absents."""
    count = 0
    for entry in injuries:
        if not isinstance(entry, dict):
            continue
        player = entry.get("player", {})
        if not isinstance(player, dict):
            continue
        pos = player.get("type", "").lower()
        if "defender" in pos or pos == "d":
            count += 1
    return count


def gk_is_experienced(injuries: list) -> bool:
    """Retourne False si le GK titulaire est absent (remplaçant inexpérimenté)."""
    for entry in injuries:
        if not isinstance(entry, dict):
            continue
        player = entry.get("player", {})
        if not isinstance(player, dict):
            continue
        pos = player.get("type", "").lower()
        if "goalkeeper" in pos or pos == "g":
            return False
    return True
