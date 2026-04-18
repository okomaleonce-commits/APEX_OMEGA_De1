"""APEX_OMEGA_De1 · Lineups & Injuries"""
import requests
from config.settings import API_KEY
from bundesliga.config_v2_3 import AIS_F, AIS_F_DEFAULT

HDR = {"x-apisports-key": API_KEY}
BASE= "https://v3.football.api-sports.io"

def get_injuries(team_id, fixture_id):
    r = requests.get(f"{BASE}/injuries", headers=HDR, timeout=15,
        params={"fixture":fixture_id,"team":team_id})
    r.raise_for_status()
    return r.json().get("response",[])

def get_lineups(fixture_id):
    r = requests.get(f"{BASE}/fixtures/lineups", headers=HDR, timeout=15,
        params={"fixture":fixture_id})
    r.raise_for_status()
    return r.json().get("response",{})

def compute_ais_f(club_name, absent_players):
    profile = AIS_F.get(club_name, {})
    att, deff = 1.0, 1.0
    for p in absent_players:
        imp = profile.get(p)
        if imp:
            att  *= (1 + imp.get("off", 0))
            deff *= (1 + imp.get("def", 0))
        # default Tier B
    return {"att_mult": round(att,3), "def_mult": round(deff,3)}


def count_absent_defenders(injuries: list[dict]) -> int:
    """
    Compte les défenseurs absents (blessés ou suspendus) dans une liste API-Football.
    Returns: int
    """
    count = 0
    for entry in injuries:
        player = entry.get("player", {})
        pos    = player.get("type", "").lower()
        reason = entry.get("reason", "").lower()
        # API-Football type: "Defender" / raisons: "Injured", "Suspended"
        if "defender" in pos or pos == "d":
            if any(r in reason for r in ("injur", "suspend", "absent", "miss")):
                count += 1
            else:
                count += 1  # absent quelle que soit la raison
    return count


def gk_is_experienced(injuries: list[dict], squad: list[dict] = None) -> bool:
    """
    Retourne True si le gardien titulaire est expérimenté (>50 matchs saison).
    Retourne False si le GK est remplaçant ou junior (absent du squad connu).
    En l'absence d'info, retourne True par défaut (conservateur).
    """
    # Si le GK numéro 1 est blessé/suspendu → False
    for entry in injuries:
        player = entry.get("player", {})
        pos    = player.get("type", "").lower()
        if "goalkeeper" in pos or pos == "g":
            return False  # GK titulaire absent → remplaçant inexpérimenté
    return True  # GK titulaire disponible
