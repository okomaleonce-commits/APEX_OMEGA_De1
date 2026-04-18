"""
APEX_OMEGA_De1 · Router Bundesliga
Filtre strict sur De1 (league_id=78) — aucun autre championnat accepté.
"""
import logging
from bundesliga.config_v2_3 import API_LEAGUE_ID, CLUBS

logger = logging.getLogger(__name__)


class BundesligaRouter:
    """
    Router principal Bundesliga.
    Entrée : fixture brut API-Football.
    Sortie : fixture normalisé ou None si hors périmètre.
    """
    ALLOWED_IDS   = {78, "De1", "Bundesliga", "bundesliga"}
    ALLOWED_NAMES = set(CLUBS.keys())

    def route(self, fixture: dict) -> dict | None:
        league    = fixture.get("league", {})
        league_id = league.get("id") or fixture.get("league_id")
        if league_id not in self.ALLOWED_IDS:
            logger.debug(f"Router rejet: league_id={league_id} hors Bundesliga")
            return None
        home = fixture.get("teams", {}).get("home", {}).get("name", "")
        away = fixture.get("teams", {}).get("away", {}).get("name", "")
        if not home or not away:
            logger.warning("Router: noms d'équipes manquants — ignoré")
            return None
        fixture["_routed_by"]       = "BundesligaRouter"
        fixture["_league_verified"] = "De1"
        logger.info(f"Router ✓ {home} vs {away}")
        return fixture

    def filter_batch(self, fixtures: list) -> list:
        routed = [f for f in (self.route(x) for x in fixtures) if f]
        logger.info(f"Router: {len(routed)}/{len(fixtures)} fixtures Bundesliga retenus")
        return routed
