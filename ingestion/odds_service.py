"""APEX_OMEGA_De1 · Odds — Betfair Exchange"""
import requests
from config.settings import BETFAIR_APP_KEY, BETFAIR_SESSION

BF_BASE = "https://api.betfair.com/exchange/betting/rest/v1.0"

def get_betfair_odds(event_id, market_types):
    hdrs = {"X-Authentication":BETFAIR_SESSION,"X-Application":BETFAIR_APP_KEY,
            "Content-Type":"application/json","Accept":"application/json"}
    payload = {"filter":{"eventIds":[event_id],"marketTypeCodes":market_types},
               "marketProjection":["RUNNER_DESCRIPTION"],
               "priceProjection":{"priceData":["EX_BEST_OFFERS"]},"maxResults":"10"}
    r = requests.post(f"{BF_BASE}/listMarketBook/", headers=hdrs, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

def demarginalize(back_odds):
    imp = [1/o for o in back_odds]
    total = sum(imp)
    margin = total - 1.0
    fair_imp = [p - margin*(p**2/total) for p in imp]
    return [round(1/p, 3) for p in fair_imp]

def compute_edge(model_prob, fair_odd):
    if not fair_odd or fair_odd <= 1.0: return -99.0
    return round((model_prob - 1/fair_odd) / (1/fair_odd), 4)
