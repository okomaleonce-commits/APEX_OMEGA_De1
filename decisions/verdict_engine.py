"""
APEX_OMEGA_De1 · Verdict Engine v2 — TOUJOURS un signal
Philosophie : avec 40+ marchés disponibles, un edge positif existe toujours.
Le bot émet TOUJOURS au moins 1 signal par match analysé.
Signaux classés par GRADE (A > B > C > D) puis par edge décroissant.
"""
from __future__ import annotations
import logging
from bundesliga.markets import MARKETS, GRADE_ORDER, GRADE_MAX_STAKE
from bundesliga.config_v2_3 import (
    KELLY_DIVISORS, FAMILY_CAPS,
    SESSION_MAX_EXPOSURE, SESSION_MAX_EXPOSURE_SR,
    SESSION_MAX_SIGNALS, CLUBS, VERDICTS,
)
from ingestion.odds_service import compute_edge

logger = logging.getLogger(__name__)


class VerdictEngine:

    def generate(
        self,
        match:    dict,
        all_probs: dict,   # sortie de compute_all_market_probs()
        dcs:      dict,
        gates:    dict,
        session:  dict,
    ) -> list[dict]:
        """
        Évalue TOUS les marchés disponibles et retourne les signaux classés.
        GARANTIE : retourne toujours ≥1 signal si DCS ≥ ACCEPTABLE.
        """
        forbidden  = set(gates.get("forbidden_markets", []))
        kelly_mult = gates.get("kelly_mult", 1.0)
        flags      = gates.get("flags", {})
        fair_odds  = match.get("fair_odds", {})
        home       = match["home_team"]
        away       = match["away_team"]
        hp, ap     = CLUBS.get(home, {}), CLUBS.get(away, {})
        is_promo   = hp.get("promoted") or ap.get("promoted")
        dcs_tier   = dcs.get("tier", "INSUFFICIENT")
        can_buts   = dcs.get("market_ok", False)

        if dcs_tier == "INSUFFICIENT":
            return []

        candidates = []

        # ── Évaluation de chaque marché du catalogue
        for market_key, market_cfg in MARKETS.items():
            if market_key in forbidden:
                continue

            # Restrictions DCS : marchés buts Grade A requis DCS valid
            grade = market_cfg["grade"]
            if grade == "A" and market_key not in ("1x2_home","1x2_draw","1x2_away","dc_1x","dc_12","dc_x2") and not can_buts:
                continue

            # Récupérer la proba modèle
            model_prob = all_probs.get(market_key)
            if model_prob is None or model_prob <= 0.01:
                continue

            # Récupérer la cote fair (du marché ou estimée)
            fair_odd = self._get_fair_odd(market_key, fair_odds, model_prob)
            if fair_odd is None or fair_odd <= 1.01:
                continue

            # Calcul edge
            edge = compute_edge(model_prob, fair_odd)

            # Seuil edge minimal par marché
            edge_min = market_cfg["edge_min"]
            if is_promo and market_key in ("1x2_home", "1x2_away"):
                edge_min = max(edge_min, 0.18)

            if edge < edge_min:
                continue

            # Verdict et mise
            verdict = _determine_verdict(edge, dcs_tier, grade, flags)
            if verdict == "NO_BET":
                continue

            kelly_div = market_cfg["kelly_div"]
            max_stake = GRADE_MAX_STAKE[grade]
            stake = min(
                (edge / kelly_div) * kelly_mult,
                max_stake,
            )

            candidates.append({
                "market":     market_key,
                "label":      market_cfg["label"],
                "grade":      grade,
                "prob":       round(model_prob, 4),
                "fair_odd":   round(fair_odd, 3),
                "edge":       round(edge, 4),
                "stake_pct":  round(stake, 4),
                "verdict":    verdict,
            })

        # ── Trier : Grade A d'abord, puis edge décroissant
        candidates.sort(key=lambda x: (GRADE_ORDER[x["grade"]], -x["edge"]))

        # ── Garantie signal : si aucun edge suffisant, prendre le meilleur disponible
        if not candidates:
            best = self._best_fallback(all_probs, fair_odds, forbidden, kelly_mult)
            if best:
                candidates = [best]
                logger.info(f"Fallback signal [{home} vs {away}]: {best['market']} edge={best['edge']:.1%}")

        # ── Application caps famille + session
        final = self._apply_caps(candidates, session)

        # ── Enrichissement des signaux
        for s in final:
            s["home"]     = home
            s["away"]     = away
            s["matchday"] = match.get("matchday")

        logger.info(
            f"Verdict [{home} vs {away}]: {len(final)}/{len(candidates)} signaux "
            f"| Grades: {[s['grade'] for s in final]}"
        )
        return final

    def _get_fair_odd(self, market_key: str, fair_odds: dict, model_prob: float) -> float | None:
        """
        Récupère la cote fair du marché depuis The Odds API.
        Si indisponible, estime à partir de la proba modèle (mode dégradé).
        """
        # Chercher la clé exacte ou la variante _fair
        odd = (fair_odds.get(f"{market_key}_fair")
               or fair_odds.get(market_key))

        # Mapping des clés Odds API → clés internes
        if odd is None:
            aliases = {
                "1x2_home": ["1x2_home_fair", "1x2_home"],
                "1x2_draw": ["1x2_draw_fair", "1x2_draw"],
                "1x2_away": ["1x2_away_fair", "1x2_away"],
                "over_25":  ["over_25_fair", "over_25"],
                "over_35":  ["over_35_fair", "over_35"],
                "under_25": ["under_25_fair", "under_25"],
                "btts_yes": ["btts_yes"],
                "btts_no":  ["btts_no"],
                "dc_1x":    ["dc_1x"],
                "dc_12":    ["dc_12"],
                "dc_x2":    ["dc_x2"],
            }
            for alias in aliases.get(market_key, []):
                if alias in fair_odds:
                    odd = fair_odds[alias]
                    break

        # Mode dégradé : estimer la cote depuis la proba modèle
        # avec une marge bookmaker simulée de 5%
        if odd is None and model_prob > 0.05:
            estimated = 1 / model_prob * 0.95  # 5% marge simulée
            if estimated > 1.05:
                return round(estimated, 3)
            return None

        return odd

    def _best_fallback(
        self, all_probs: dict, fair_odds: dict,
        forbidden: set, kelly_mult: float
    ) -> dict | None:
        """
        Fallback : retourne le marché avec le meilleur edge disponible,
        sans condition de seuil minimum.
        """
        best = None
        best_edge = -999

        for market_key, market_cfg in MARKETS.items():
            if market_key in forbidden or market_key.startswith("_"):
                continue
            prob = all_probs.get(market_key, 0)
            if prob <= 0.02:
                continue
            fair_odd = self._get_fair_odd(market_key, fair_odds, prob)
            if fair_odd is None or fair_odd <= 1.01:
                continue
            edge = compute_edge(prob, fair_odd)
            if edge > best_edge:
                best_edge = edge
                grade = market_cfg["grade"]
                best = {
                    "market":    market_key,
                    "label":     market_cfg["label"],
                    "grade":     grade,
                    "prob":      round(prob, 4),
                    "fair_odd":  round(fair_odd, 3),
                    "edge":      round(edge, 4),
                    "stake_pct": round(min(max(edge / market_cfg["kelly_div"] * kelly_mult, 0.005), GRADE_MAX_STAKE[grade] * 0.5), 4),
                    "verdict":   "SPECULATIVE",
                }
        return best

    def _apply_caps(self, candidates: list, session: dict) -> list:
        """Applique caps session + limite 4 signaux."""
        candidates = sorted(candidates, key=lambda x: (GRADE_ORDER[x["grade"]], -x["edge"]))
        total_exp  = float(session.get("total_exposure", 0))
        n_sigs     = int(session.get("total_signals", 0))
        is_sr      = session.get("has_strong_rupture", False)
        max_exp    = SESSION_MAX_EXPOSURE_SR if is_sr else SESSION_MAX_EXPOSURE

        selected = []
        for s in candidates:
            if n_sigs >= SESSION_MAX_SIGNALS: break
            if total_exp + s["stake_pct"] > max_exp: continue
            total_exp += s["stake_pct"]
            n_sigs    += 1
            selected.append(s)

        return selected


def _determine_verdict(edge: float, dcs_tier: str, grade: str, flags: dict) -> str:
    if edge <= 0: return "NO_BET"
    if flags.get("RUPTURE") and edge >= 0.25 and dcs_tier == "SOLID" and grade == "A":
        return "STRONG_RUPTURE"
    if dcs_tier == "ACCEPTABLE" or grade in ("C","D"):
        return "SPECULATIVE" if edge >= 0.05 else "NO_BET"
    if edge >= 0.10 and dcs_tier in ("SOLID","VALID") and grade == "A":
        return "VARIANCE"
    return "SMALL_BET"
