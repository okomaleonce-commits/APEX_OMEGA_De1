"""
APEX_OMEGA_De1 · Verdict Engine — génération signaux v1.4
"""
from __future__ import annotations
import logging
from bundesliga.config_v2_3 import (
    EDGE_THRESHOLDS, OVER35_PRINCIPAL, CLUBS,
    DCS_THRESHOLDS, VERDICTS,
)
from risk.stake_policy import (
    compute_stake, apply_family_caps,
    is_1x2_form_ok, determine_verdict,
)
from ingestion.odds_service import compute_edge

logger = logging.getLogger(__name__)


class VerdictEngine:

    def generate(
        self,
        match:   dict,
        probs:   dict,
        dcs:     dict,
        gates:   dict,
        session: dict,
    ) -> list[dict]:
        """
        Génère et classe les signaux APEX pour un match.
        Retourne la liste triée (par edge) des signaux retenus après caps.
        """
        if dcs["tier"] == "INSUFFICIENT":
            return []

        forbidden  = set(gates.get("forbidden_markets", []))
        kelly_mult = gates.get("kelly_mult", 1.0)
        flags      = gates.get("flags", {})
        fair_odds  = match.get("fair_odds", {})
        home       = match["home_team"]
        away       = match["away_team"]
        hp, ap     = CLUBS.get(home, {}), CLUBS.get(away, {})
        can_buts   = dcs["market_ok"]

        candidates = []

        def try_signal(market, prob, odd_key, extra_check=True):
            if market in forbidden:        return
            if not extra_check:            return
            if not can_buts and market not in ("1x2_fav", "1x2_out"): return

            fair_odd = fair_odds.get(odd_key or market)
            if not fair_odd or fair_odd <= 1.01: return

            edge_min = EDGE_THRESHOLDS.get(market, 0.05)
            # Règle promu/Tier C
            is_promo = hp.get("promoted") or ap.get("promoted")
            if market in ("1x2_fav",) and is_promo:
                edge_min = max(edge_min, EDGE_THRESHOLDS.get("1x2_promo", 0.18))

            edge = compute_edge(prob, fair_odd)
            if edge < edge_min: return

            verdict  = determine_verdict(edge, dcs["tier"], flags)
            if verdict == "NO_BET": return

            stake = compute_stake(market, edge, kelly_mult, verdict, fair_odd)
            candidates.append({
                "market":    market,
                "prob":      round(prob, 4),
                "fair_odd":  round(fair_odd, 3),
                "edge":      round(edge, 4),
                "stake_pct": round(stake, 4),
                "verdict":   verdict,
            })

        # ── Over 2.5
        try_signal("over_25", probs["p_over_25"], "over_25")

        # ── Over 3.5 — vérification signal principal (3 critères)
        xg_ok  = probs["xg_total"] >= OVER35_PRINCIPAL["xg_min"]
        h2h_ok = (match.get("h2h_avg_goals") or 0) >= OVER35_PRINCIPAL["h2h_min"]
        try_signal("over_35", probs["p_over_35"], "over_35",
                   extra_check=can_buts and (xg_ok or dcs["tier"] == "SOLID"))

        # ── Under 2.5 — filtre double défense obligatoire
        if "under_25" not in forbidden and can_buts:
            dbl = (
                (match.get("home_avg_conceded") or 99) <= 1.2
                and (match.get("home_over25_pct") or 1) <= 0.45
                and (match.get("away_avg_conceded") or 99) <= 1.2
                and (match.get("away_over25_pct") or 1) <= 0.45
            )
            try_signal("under_25", probs["p_under_25"], "under_25", extra_check=dbl)

        # ── 1X2 favori
        fav_home = probs["p_home_win"] >= probs["p_away_win"]
        fav_prob = probs["p_home_win"] if fav_home else probs["p_away_win"]
        fav_odd  = "1x2_home" if fav_home else "1x2_away"
        form_ok  = is_1x2_form_ok(
            home, away,
            flags.get("home_win_rate_effective", 0.5),
            flags.get("away_win_rate_effective", 0.5),
            fav_home,
        ) and flags.get(f"1x2_{'home' if fav_home else 'away'}_form_ok", True)
        try_signal("1x2_fav", fav_prob, fav_odd, extra_check=form_ok)

        # ── 1X2 outsider (cote > 4.0)
        out_prob = probs["p_away_win"] if fav_home else probs["p_home_win"]
        out_odd_key = "1x2_away" if fav_home else "1x2_home"
        out_fair = fair_odds.get(out_odd_key, 0)
        if out_fair and out_fair > 4.0:
            try_signal("1x2_out", out_prob, out_odd_key)

        # ── BTTS Non
        try_signal("btts_no", probs["p_btts_no"], "btts_no")

        # ── Application caps
        final = apply_family_caps(candidates, session)

        for s in final:
            s["home"] = home
            s["away"] = away
            s["matchday"] = match.get("matchday")

        logger.info(
            f"Verdict [{home} vs {away}]: {len(final)}/{len(candidates)} signaux retenus"
        )
        return final
