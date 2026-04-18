"""APEX_OMEGA_De1 · Fixtures — API-Football"""
import requests
from config.settings import API_FOOTBALL_KEY, BUNDESLIGA_LEAGUE_ID, BUNDESLIGA_SEASON
from datetime import datetime, timedelta

BASE = "https://v3.football.api-sports.io"
HDR  = {"x-apisports-key": API_FOOTBALL_KEY}

def get_upcoming(days=7):
    today = datetime.utcnow().date()
    r = requests.get(f"{BASE}/fixtures", headers=HDR, timeout=15,
        params={"league":BUNDESLIGA_LEAGUE_ID,"season":BUNDESLIGA_SEASON,
                "from":str(today),"to":str(today+timedelta(days=days)),"status":"NS"})
    r.raise_for_status()
    return r.json().get("response",[])

def get_result(fixture_id):
    r = requests.get(f"{BASE}/fixtures", headers=HDR, timeout=15,
        params={"id": fixture_id})
    r.raise_for_status()
    data = r.json().get("response",[])
    return data[0] if data else {}

def get_h2h(home_id, away_id, last=10):
    r = requests.get(f"{BASE}/fixtures/headtohead", headers=HDR, timeout=15,
        params={"h2h":f"{home_id}-{away_id}","last":last})
    r.raise_for_status()
    return r.json().get("response",[])

def get_team_form(team_id, last=8):
    r = requests.get(f"{BASE}/fixtures", headers=HDR, timeout=15,
        params={"team":team_id,"season":BUNDESLIGA_SEASON,"last":last,"status":"FT"})
    r.raise_for_status()
    return r.json().get("response",[])
