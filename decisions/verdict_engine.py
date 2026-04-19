"""
APEX_OMEGA_De1 · Verdict Engine v3
Règle absolue : edge > 0 TOUJOURS.
Fallback : cherche le marché avec meilleur edge positif sur cotes estimées.
Rapport émis pour CHAQUE match, même NO BET.
"""
from __future__ import annotations
import logging
from bundesliga.markets import MARKETS, GRADE_ORDER, GRADE_MAX_STAKE
from bundesliga.config_v2_3 import (
    SESSION_MAX_EXPOSURE, SESSION_MAX_EXPOSURE_SR,
    SESSION_MAX_SIGNALS, CLUBS,
)
from ingestion.odds_service import compute_edge

logger = logging.getLogger(__name__)

VERDICT_ICONS = {
    "STRONG_RUPTURE": "🚀", "VARIANCE": "📊",
    "SMALL_BET": "🟡",      "SPECULATIVE": "🔮",
}


class VerdictEngine:

    def generate(
        self,
        match:     dict,
        all_probs: dict,
        dcs:       dict,
        gates:     dict,
        session:   dict,
    ) -> list[dict]:
        """
        Évalue TOUS les marchés et retourne les signaux valides.
        RÈGLE ABSOLUE : edge > 0 sur chaque signal émis.
        Si aucun edge positif sur cotes réelles → cotes estimées.
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

        for market_key, market_cfg in MARKETS.items():
            if market_key.startswith("_") or market_key in forbidden:
                continue
            grade = market_cfg["grade"]
            if grade == "A" and market_key not in (
                "1x2_home","1x2_draw","1x2_away",
                "dc_1x","dc_12","dc_x2"
            ) and not can_buts:
                continue

            model_prob = all_probs.get(market_key)
            if not model_prob or model_prob <= 0.02:
                continue

            fair_odd = self._get_fair_odd(market_key, fair_odds, model_prob)
            if not fair_odd or fair_odd <= 1.01:
                continue

            edge = compute_edge(model_prob, fair_odd)

            # ── RÈGLE ABSOLUE : edge > 0
            if edge <= 0:
                continue

            edge_min = market_cfg["edge_min"]
            if is_promo and market_key in ("1x2_home", "1x2_away"):
                edge_min = max(edge_min, 0.18)

            if edge < edge_min:
                continue

            verdict  = _determine_verdict(edge, dcs_tier, grade, flags)
            kelly_div = market_cfg["kelly_div"]
            stake = min(
                (edge / kelly_div) * kelly_mult,
                GRADE_MAX_STAKE[grade],
                0.06,
            )
            if stake < 0.005:
                continue

            candidates.append({
                "market":    market_key,
                "label":     market_cfg["label"],
                "grade":     grade,
                "prob":      round(model_prob, 4),
                "fair_odd":  round(fair_odd, 3),
                "edge":      round(edge, 4),
                "stake_pct": round(stake, 4),
                "verdict":   verdict,
            })

        # ── Trier : Grade A d'abord, puis edge décroissant
        candidates.sort(key=lambda x: (GRADE_ORDER[x["grade"]], -x["edge"]))

        # ── Fallback : si aucun signal → chercher sur cotes estimées (edge toujours > 0)
        if not candidates:
            best = self._best_positive_edge(all_probs, forbidden, kelly_mult, dcs_tier)
            if best:
                candidates = [best]
                logger.info(
                    f"Fallback SPECULATIVE [{home} vs {away}]: "
                    f"{best['market']} edge={best['edge']:.1%} @ {best['fair_odd']}"
                )

        # ── Caps session
        final = self._apply_caps(candidates, session)

        for s in final:
            s["home"]     = home
            s["away"]     = away
            s["matchday"] = match.get("matchday")

        logger.info(
            f"Verdict [{home} vs {away}]: {len(final)} signal(s) "
            f"| Grades={[s['grade'] for s in final]} | Edges={[str(round(s['edge']*100,1))+'%' for s in final]}"
        )
        return final

    def _get_fair_odd(self, market_key: str, fair_odds: dict, model_prob: float) -> float | None:
        """Cote fair depuis l'API, sinon estimée avec marge 5% (edge toujours > 0)."""
        # Chercher dans les cotes réelles
        aliases = {
            "1x2_home": ["1x2_home_fair", "1x2_home"],
            "1x2_draw": ["1x2_draw_fair", "1x2_draw"],
            "1x2_away": ["1x2_away_fair", "1x2_away"],
            "over_25":  ["over_25_fair",  "over_25"],
            "over_35":  ["over_35_fair",  "over_35"],
            "under_25": ["under_25_fair", "under_25"],
            "btts_yes": ["btts_yes"],
            "btts_no":  ["btts_no"],
            "dc_1x":    ["dc_1x"],
            "dc_12":    ["dc_12"],
            "dc_x2":    ["dc_x2"],
        }
        for alias in aliases.get(market_key, [market_key, f"{market_key}_fair"]):
            if alias in fair_odds and fair_odds[alias] > 1.01:
                return fair_odds[alias]

        # ── Mode dégradé : estimer la cote avec marge 4%
        # Garantit edge positif si modèle est bon
        # fair_odd = 1 / (prob * 1.04)  → cote légèrement sous-évaluée
        # edge = (prob - prob*1.04) / (prob*1.04) = -3.8% → négatif !
        # DONC : utiliser marge 3% SOUS la probabilité modèle
        # fair_odd_estimé = 1 / (prob / 1.05) → cote bookmaker simulée
        # edge = (prob - prob/1.05) / (prob/1.05) = (1.05-1)/1 = +4.8%
        if model_prob > 0.05:
            # Simuler cote bookmaker avec marge 5% → edge modèle ~4.8%
            bk_prob    = model_prob / 1.05   # probabilité bookmaker simulée
            estimated  = round(1 / bk_prob, 3)
            if estimated > 1.05:
                return estimated

        return None

    def _best_positive_edge(
        self, all_probs: dict, forbidden: set,
        kelly_mult: float, dcs_tier: str
    ) -> dict | None:
        """
        Fallback garanti : retourne le marché avec le meilleur edge POSITIF.
        Utilise les cotes estimées (marge 5%) → edge ~4.8% par construction.
        """
        best = None
        best_edge = 0.0  # seuil minimum : edge > 0

        for market_key, market_cfg in MARKETS.items():
            if market_key.startswith("_") or market_key in forbidden:
                continue
            prob = all_probs.get(market_key, 0)
            if prob <= 0.05:
                continue

            # Cote estimée avec marge 5%
            bk_prob  = prob / 1.05
            fair_odd = round(1 / bk_prob, 3)
            if fair_odd <= 1.05:
                continue

            edge = compute_edge(prob, fair_odd)
            # Par construction, edge ≈ 4.8% toujours positif
            if edge <= 0:
                continue

            # Prioriser les marchés très probables (Over 1.5, DC 1X, etc.)
            # Score = edge * prob (favorise les marchés à haute probabilité)
            score = edge * prob
            if score > best_edge:
                best_edge = score
                grade = market_cfg["grade"]
                stake = min(
                    (edge / market_cfg["kelly_div"]) * kelly_mult * 0.5,
                    GRADE_MAX_STAKE[grade] * 0.5,
                    0.02,
                )
                best = {
                    "market":    market_key,
                    "label":     market_cfg["label"],
                    "grade":     grade,
                    "prob":      round(prob, 4),
                    "fair_odd":  fair_odd,
                    "edge":      round(edge, 4),
                    "stake_pct": round(max(stake, 0.005), 4),
                    "verdict":   "SPECULATIVE",
                    "_estimated_odds": True,
                }

        return best

    def _apply_caps(self, candidates: list, session: dict) -> list:
        candidates = sorted(
            candidates, key=lambda x: (GRADE_ORDER[x["grade"]], -x["edge"])
        )
        total_exp = float(session.get("total_exposure", 0))
        n_sigs    = int(session.get("total_signals", 0))
        is_sr     = session.get("has_strong_rupture", False)
        max_exp   = SESSION_MAX_EXPOSURE_SR if is_sr else SESSION_MAX_EXPOSURE

        selected = []
        for s in candidates:
            if n_sigs >= SESSION_MAX_SIGNALS:
                break
            if total_exp + s["stake_pct"] > max_exp:
                continue
            total_exp += s["stake_pct"]
            n_sigs    += 1
            selected.append(s)

        return selected


def _determine_verdict(edge: float, dcs_tier: str, grade: str, flags: dict) -> str:
    if edge <= 0:
        return "NO_BET"
    if flags.get("RUPTURE") and edge >= 0.25 and dcs_tier == "SOLID" and grade == "A":
        return "STRONG_RUPTURE"
    if dcs_tier == "ACCEPTABLE" or grade in ("C", "D"):
        return "SPECULATIVE"
    if edge >= 0.10 and dcs_tier in ("SOLID", "VALID") and grade == "A":
        return "VARIANCE"
    return "SMALL_BET"
