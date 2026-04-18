"""
APEX_OMEGA_De1 · Odds Service
Source : The Odds API (https://the-odds-api.com)
Remplace Betfair/Pinnacle directs — agrège plusieurs bookmakers
Marchés : h2h (1X2) · totals (Over/Under) · btts
"""
import logging
import requests
from config.settings import ODDS_API_KEY, ODDS_API_BOOKMAKERS

logger = logging.getLogger(__name__)

BASE_URL  = "https://api.the-odds-api.com/v4"
SPORT_KEY = "soccer_germany_bundesliga"

# ── Correspondance marchés Odds API → APEX
MARKET_MAP = {
    "h2h":    ["1x2_home", "1x2_draw", "1x2_away"],
    "totals":  ["over_25", "under_25", "over_35", "under_35"],
    "btts":    ["btts_yes", "btts_no"],
}

def get_bundesliga_odds(fixture_date: str = None) -> list[dict]:
    """
    Récupère toutes les cotes Bundesliga disponibles sur The Odds API.
    Retourne une liste de matchs avec cotes par bookmaker.

    Args:
        fixture_date : "YYYY-MM-DD" optionnel pour filtrer

    Returns:
        [{"home_team": str, "away_team": str, "commence_time": str,
          "bookmakers": [...], "fair_odds": {...}}]
    """
    params = {
        "apiKey":     ODDS_API_KEY,
        "regions":    "eu",
        "markets":    "h2h,totals,btts",
        "oddsFormat": "decimal",
        "bookmakers": ODDS_API_BOOKMAKERS,
    }
    if fixture_date:
        params["commenceTimeTo"] = f"{fixture_date}T23:59:00Z"

    try:
        resp = requests.get(
            f"{BASE_URL}/sports/{SPORT_KEY}/odds",
            params=params,
            timeout=20,
        )
        resp.raise_for_status()
        remaining = resp.headers.get("x-requests-remaining", "?")
        logger.info(f"Odds API: {len(resp.json())} matchs · {remaining} requêtes restantes")

        results = []
        for event in resp.json():
            fair = _extract_fair_odds(event)
            results.append({
                "event_id":      event.get("id"),
                "home_team":     event.get("home_team"),
                "away_team":     event.get("away_team"),
                "commence_time": event.get("commence_time"),
                "bookmakers":    event.get("bookmakers", []),
                "fair_odds":     fair,
            })
        return results

    except requests.RequestException as e:
        logger.error(f"Odds API erreur: {e}")
        return []


def get_match_odds(home_team: str, away_team: str) -> dict:
    """
    Récupère les cotes pour un match spécifique.
    Retourne un dict APEX-normalisé avec fair odds.
    """
    all_odds = get_bundesliga_odds()
    for event in all_odds:
        h = event["home_team"].lower()
        a = event["away_team"].lower()
        if home_team.lower() in h and away_team.lower() in a:
            return event["fair_odds"]
    logger.warning(f"Cotes introuvables: {home_team} vs {away_team}")
    return {}


def _extract_fair_odds(event: dict) -> dict:
    """
    Extrait et démarginise les cotes depuis les bookmakers disponibles.
    Priorité : Pinnacle > Betfair > autres
    Retourne dict: {market_key: fair_odd}
    """
    # Collecte toutes les cotes par marché
    raw = {
        "1x2_home": [], "1x2_draw": [], "1x2_away": [],
        "over_25": [], "under_25": [],
        "over_35": [], "under_35": [],
        "btts_yes": [], "btts_no": [],
    }

    priority_order = ["pinnacle", "betfair_ex_eu", "unibet", "bet365", "williamhill"]
    bookmakers_sorted = sorted(
        event.get("bookmakers", []),
        key=lambda b: priority_order.index(b["key"])
        if b["key"] in priority_order else 99,
    )

    for bk in bookmakers_sorted:
        for market in bk.get("markets", []):
            key  = market["key"]
            outs = market.get("outcomes", [])

            if key == "h2h" and len(outs) >= 2:
                for o in outs:
                    name = o["name"].lower()
                    if name == event["home_team"].lower():
                        raw["1x2_home"].append(o["price"])
                    elif name == "draw":
                        raw["1x2_draw"].append(o["price"])
                    else:
                        raw["1x2_away"].append(o["price"])

            elif key == "totals":
                for o in outs:
                    pt = o.get("point", 0)
                    nm = o["name"].lower()
                    if pt == 2.5:
                        if nm == "over":  raw["over_25"].append(o["price"])
                        else:             raw["under_25"].append(o["price"])
                    elif pt == 3.5:
                        if nm == "over":  raw["over_35"].append(o["price"])
                        else:             raw["under_35"].append(o["price"])

            elif key in ("btts", "both_teams_to_score"):
                for o in outs:
                    nm = o["name"].lower()
                    if nm in ("yes", "oui"):  raw["btts_yes"].append(o["price"])
                    elif nm in ("no", "non"): raw["btts_no"].append(o["price"])

    # Moyenne pondérée (top-3 bookmakers) + démarginisation
    fair = {}
    for market_key, prices in raw.items():
        if prices:
            avg = sum(prices[:3]) / len(prices[:3])  # top-3 bookmakers
            fair[market_key] = round(avg, 3)

    # Démarginisation sur le trio 1X2
    if all(k in fair for k in ("1x2_home", "1x2_draw", "1x2_away")):
        trio = [fair["1x2_home"], fair["1x2_draw"], fair["1x2_away"]]
        fair_trio = demarginalize(trio)
        fair["1x2_home_fair"] = round(fair_trio[0], 3)
        fair["1x2_draw_fair"] = round(fair_trio[1], 3)
        fair["1x2_away_fair"] = round(fair_trio[2], 3)

    # Démarginisation Over/Under 2.5
    for over_k, under_k in [("over_25", "under_25"), ("over_35", "under_35")]:
        if over_k in fair and under_k in fair:
            pair = [fair[over_k], fair[under_k]]
            fp   = demarginalize(pair)
            fair[f"{over_k}_fair"]  = round(fp[0], 3)
            fair[f"{under_k}_fair"] = round(fp[1], 3)

    return fair


def demarginalize(odds: list[float]) -> list[float]:
    """
    Démarginisation Shin approximée.
    Retourne les fair odds sans marge bookmaker.
    """
    if not odds or any(o <= 1.0 for o in odds):
        return odds
    implied = [1 / o for o in odds]
    total   = sum(implied)
    margin  = total - 1.0
    fair_implied = [p - margin * (p ** 2 / total) for p in implied]
    # Éviter division par zéro
    return [round(1 / max(p, 0.001), 3) for p in fair_implied]


def compute_edge(model_prob: float, fair_odd: float) -> float:
    """
    Edge value betting : (P_modèle - P_marché_fair) / P_marché_fair
    Valeur positive = value bet détecté.
    """
    if fair_odd <= 1.0:
        return 0.0
    market_prob = 1 / fair_odd
    return round((model_prob - market_prob) / market_prob, 4)
