"""
APEX_OMEGA_De1 · Trust Matrix — DCS /70 Bundesliga v1.4
"""
from __future__ import annotations
from bundesliga.config_v2_3 import (
    DCS_THRESHOLDS, DCS_SEASONAL, DCS_TIER_C_BUTS_MIN,
    DCS_PROMOTED_G2_CAP, DCS_PENALTY_UCL_GATE,
    DCS_PENALTY_UEL_GATE, DCS_PENALTY_EDE_GATE, CLUBS,
)


class DCSCalculator:

    def compute(
        self,
        home_club:          str,
        away_club:          str,
        sources:            dict,
        compo_confirmed:    bool,
        absences_confirmed: bool,
        gates_active:       dict,
        matchday:           int,
    ) -> dict:
        """
        Calcule le DCS ajusté /70 avec grille A-LAP v1.4.
        sources keys: fbref, footystats, betfair, pinnacle, h2h_min3
        gates_active keys: ucl_rotation, uel_rotation, ede
        Returns: raw, adjusted, tier, market_ok, detail (G1-G6)
        """
        hp = CLUBS.get(home_club, {})
        ap = CLUBS.get(away_club, {})

        # G1 — Sources xG (max 15)
        g1 = 0
        if sources.get("fbref"):      g1 += 6
        if sources.get("footystats"): g1 += 5
        if sources.get("sofascore") or sources.get("soccer_rating"): g1 += 4
        g1 = min(g1, 15)

        # G2 — Stats historiques + forme + H2H (max 15)
        g2 = 15
        if hp.get("promoted") or ap.get("promoted"):
            g2 = min(g2, DCS_PROMOTED_G2_CAP)
        if not sources.get("h2h_min3"):
            g2 = min(g2, 10)
        if hp.get("hard_to_model") or ap.get("hard_to_model"):
            g2 = min(g2, 11)

        # G3 — Composition officielle connue (max 10)
        g3 = 10 if compo_confirmed else 6

        # G4 — Cotes Betfair + Pinnacle (max 12)
        g4 = 0
        if sources.get("betfair"):  g4 += 7
        if sources.get("pinnacle"): g4 += 5
        if not sources.get("betfair") and not sources.get("pinnacle"):
            g4 = 4  # agrégateurs seulement

        # G5 — Absences confirmées (max 10)
        g5 = 10 if absences_confirmed else 7

        # G6 — Périmètre / gates spéciaux (max 8)
        g6 = 8
        if gates_active.get("ucl_rotation"): g6 += DCS_PENALTY_UCL_GATE
        if gates_active.get("uel_rotation"): g6 += DCS_PENALTY_UEL_GATE
        if gates_active.get("ede"):          g6 += DCS_PENALTY_EDE_GATE
        g6 = max(g6, 0)

        raw = g1 + g2 + g3 + g4 + g5 + g6

        # Ajustement saisonnier
        if matchday <= 5:              adj_season = DCS_SEASONAL["J01_J05"]
        elif 17 <= matchday <= 19:     adj_season = DCS_SEASONAL["J17_J19"]
        elif 31 <= matchday <= 33:     adj_season = DCS_SEASONAL["J31_J33"]
        elif matchday == 34:           adj_season = DCS_SEASONAL["J34"]
        else:                          adj_season = 0

        adjusted = raw + adj_season

        # Tier
        if adjusted >= DCS_THRESHOLDS["SOLID"]:         tier = "SOLID"
        elif adjusted >= DCS_THRESHOLDS["VALID"]:        tier = "VALID"
        elif adjusted >= DCS_THRESHOLDS["ACCEPTABLE"]:   tier = "ACCEPTABLE"
        else:                                             tier = "INSUFFICIENT"

        # Marchés buts autorisés
        is_tier_c   = hp.get("tier") == "C" or ap.get("tier") == "C"
        min_buts    = DCS_TIER_C_BUTS_MIN if is_tier_c else DCS_THRESHOLDS["VALID"]
        market_ok   = adjusted >= min_buts

        return {
            "raw":       raw,
            "adjusted":  adjusted,
            "tier":      tier,
            "market_ok": market_ok,
            "g1": g1, "g2": g2, "g3": g3,
            "g4": g4, "g5": g5, "g6": g6,
            "is_tier_c": is_tier_c,
        }
