"""APEX_OMEGA_De1 · Lineups & Injuries"""
import requests
from config.settings import API_FOOTBALL_KEY
from bundesliga.config_v2_3 import AIS_F, AIS_F_DEFAULT

HDR = {"x-apisports-key": API_FOOTBALL_KEY}
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
