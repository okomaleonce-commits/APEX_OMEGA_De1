"""
APEX_OMEGA_De1 · Odds Service — The Odds API
Plan gratuit : h2h + totals uniquement (btts non supporté)
En cas d'erreur 401/403 : retourne dict vide (DCS baisse, NO BET probable)
"""
import logging
import requests
from config.settings import ODDS_API_KEY, ODDS_API_BOOKMAKERS

logger = logging.getLogger(__name__)

BASE_URL  = "https://api.the-odds-api.com/v4"
SPORT_KEY = "soccer_germany_bundesliga"

# Bookmakers par priorité pour démarginisation
PRIORITY  = ["pinnacle", "betfair_ex_eu", "unibet", "bet365", "williamhill"]


def get_bundesliga_odds() -> list:
    """Récupère toutes les cotes Bundesliga. Retourne [] si erreur."""
    try:
        resp = requests.get(
            f"{BASE_URL}/sports/{SPORT_KEY}/odds",
            params={
                "apiKey":     ODDS_API_KEY,
                "regions":    "eu",
                "markets":    "h2h,totals",
                "oddsFormat": "decimal",
                # bookmakers param omis → utilise tous les bookmakers du plan
            },
            timeout=20,
        )
        resp.raise_for_status()
        remaining = resp.headers.get("x-requests-remaining", "?")
        data = resp.json()
        logger.info(f"Odds API: {len(data)} matchs · {remaining} req restantes")
        return data
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else "?"
        logger.warning(f"Odds API HTTP {status} — cotes indisponibles (mode dégradé)")
        return []
    except Exception as e:
        logger.warning(f"Odds API erreur: {e} — mode dégradé")
        return []


def get_match_odds(home_team: str, away_team: str) -> dict:
    """
    Cotes d'un match spécifique avec fair odds démarginalisés.
    Retourne {} si indisponible (mode dégradé — DCS G4 pénalisé).
    """
    all_events = get_bundesliga_odds()
    ht_l = home_team.lower()
    at_l = away_team.lower()

    for event in all_events:
        h = (event.get("home_team") or "").lower()
        a = (event.get("away_team") or "").lower()
        # Correspondance partielle pour gérer les variantes de noms
        if _name_match(ht_l, h) and _name_match(at_l, a):
            return _extract_fair_odds(event)

    logger.debug(f"Cotes non trouvées: {home_team} vs {away_team}")
    return {}


def build_fair_odds_dict(home_team: str, away_team: str) -> dict:
    """Alias pipeline-compatible."""
    return get_match_odds(home_team, away_team)


def _name_match(name1: str, name2: str) -> bool:
    """Correspondance partielle robuste entre noms de clubs."""
    # Nettoyage accents/variantes courants
    clean1 = _clean(name1)
    clean2 = _clean(name2)
    return clean1 in clean2 or clean2 in clean1 or clean1[:6] == clean2[:6]


def _clean(name: str) -> str:
    return (name.lower()
            .replace("ü", "u").replace("ö", "o").replace("ä", "a")
            .replace("ß", "ss").replace("fc ", "").replace("vfl ", "")
            .replace("vfb ", "").replace("sc ", "").replace("rb ", "")
            .replace("1. ", "").replace("fsv ", "").replace("sv ", "")
            .replace("borussia ", "").replace("bayer ", "")
            .strip())


def _extract_fair_odds(event: dict) -> dict:
    """Extrait et démarginise les cotes depuis les bookmakers disponibles."""
    raw = {
        "1x2_home": [], "1x2_draw": [], "1x2_away": [],
        "over_25": [],  "under_25": [],
        "over_35": [],  "under_35": [],
    }
    home_name = (event.get("home_team") or "").lower()

    bks = sorted(
        event.get("bookmakers", []),
        key=lambda b: PRIORITY.index(b.get("key", ""))
        if b.get("key", "") in PRIORITY else 99,
    )

    for bk in bks:
        for market in bk.get("markets", []):
            key  = market.get("key", "")
            outs = market.get("outcomes", [])

            if key == "h2h":
                for o in outs:
                    nm = (o.get("name") or "").lower()
                    if _name_match(nm, home_name):
                        raw["1x2_home"].append(o["price"])
                    elif nm in ("draw", "nul"):
                        raw["1x2_draw"].append(o["price"])
                    else:
                        raw["1x2_away"].append(o["price"])

            elif key == "totals":
                for o in outs:
                    pt = float(o.get("point", 0) or 0)
                    nm = (o.get("name") or "").lower()
                    if pt == 2.5:
                        raw["over_25" if nm == "over" else "under_25"].append(o["price"])
                    elif pt == 3.5:
                        raw["over_35" if nm == "over" else "under_35"].append(o["price"])

    fair = {}
    for k, prices in raw.items():
        if prices:
            fair[k] = round(sum(prices[:3]) / len(prices[:3]), 3)

    # Démarginisation 1X2
    if all(k in fair for k in ("1x2_home", "1x2_draw", "1x2_away")):
        trio = demarginalize([fair["1x2_home"], fair["1x2_draw"], fair["1x2_away"]])
        fair["1x2_home_fair"] = trio[0]
        fair["1x2_draw_fair"] = trio[1]
        fair["1x2_away_fair"] = trio[2]

    # Démarginisation Over/Under
    for ok, uk in [("over_25", "under_25"), ("over_35", "under_35")]:
        if ok in fair and uk in fair:
            pair = demarginalize([fair[ok], fair[uk]])
            fair[f"{ok}_fair"] = pair[0]
            fair[f"{uk}_fair"] = pair[1]

    return fair


def demarginalize(odds: list) -> list:
    """Shin demarginalization — supprime la marge bookmaker."""
    if not odds or any(o <= 1.0 for o in odds):
        return odds
    implied = [1 / o for o in odds]
    total   = sum(implied)
    margin  = total - 1.0
    fair_p  = [p - margin * (p ** 2 / total) for p in implied]
    return [round(1 / max(p, 0.001), 3) for p in fair_p]


def compute_edge(model_prob: float, fair_odd: float) -> float:
    """edge = (P_modèle - P_marché_fair) / P_marché_fair"""
    if fair_odd <= 1.0:
        return 0.0
    market_prob = 1 / fair_odd
    return round((model_prob - market_prob) / market_prob, 4)
