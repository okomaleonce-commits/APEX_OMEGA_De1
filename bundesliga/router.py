"""
APEX_OMEGA_De1 · Router Bundesliga
Filtre strict league_id=78 — accepte les fixtures bruts ET normalisés.
"""
import logging
from bundesliga.config_v2_3 import API_LEAGUE_ID, CLUBS, normalize_club_name

logger = logging.getLogger(__name__)


class BundesligaRouter:

    ALLOWED_IDS = {78, "De1", "Bundesliga", "bundesliga", "78"}

    def route(self, fixture: dict) -> dict | None:
        """
        Vérifie qu'un fixture appartient à la Bundesliga.
        Accepte les formats brut (API-Football) ET normalisé (après normalize_fixture).
        Retourne None si hors périmètre.
        """
        # ── Filtre league
        league    = fixture.get("league", {})
        league_id = league.get("id") or fixture.get("league_id") or fixture.get("_league_id")
        if league_id not in self.ALLOWED_IDS and str(league_id) not in self.ALLOWED_IDS:
            # Accepter aussi si déjà marqué par le router
            if fixture.get("_league_verified") != "De1":
                logger.debug(f"Router rejet: league_id={league_id}")
                return None

        # ── Récupération noms — format brut OU normalisé
        home = (
            fixture.get("home_team")                               # format normalisé
            or fixture.get("teams", {}).get("home", {}).get("name", "")  # format brut API
        )
        away = (
            fixture.get("away_team")
            or fixture.get("teams", {}).get("away", {}).get("name", "")
        )

        if not home or not away:
            logger.warning("Router: noms d'équipes manquants — ignoré")
            return None

        # ── Normaliser vers les clés CLUBS
        home_norm = normalize_club_name(home)
        away_norm = normalize_club_name(away)

        fixture["_routed_by"]       = "BundesligaRouter"
        fixture["_league_verified"] = "De1"
        logger.info(f"Router ✓ {home_norm} vs {away_norm}")
        return fixture

    def filter_batch(self, fixtures: list) -> list:
        """Filtre une liste — ne retourne que les fixtures Bundesliga valides."""
        routed = [f for f in (self.route(x) for x in fixtures) if f]
        logger.info(f"Router: {len(routed)}/{len(fixtures)} fixtures Bundesliga retenus")
        return routed
