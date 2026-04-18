"""
APEX_OMEGA_De1 · Risk — Stake Policy Bundesliga v1.4
Règles strictes : caps famille, session, bankroll journalière max 12%.
"""
from __future__ import annotations
from bundesliga.config_v2_3 import (
    EDGE_THRESHOLDS, KELLY_DIVISORS, MAX_STAKE,
    FAMILY_CAPS, SESSION_MAX_EXPOSURE, SESSION_MAX_EXPOSURE_SR,
    SESSION_MAX_SIGNALS, FORM_WIN_RATE_MIN, VERDICTS,
    CLUBS,
)


def compute_stake(
    market:        str,
    edge:          float,
    kelly_mult:    float,
    verdict_type:  str = "SMALL_BET",
    fair_odd:      float = 2.0,
) -> float:
    """
    Calcule la mise finale en % bankroll via Kelly fractionné.
    Applique les plafonds par marché et verdict.
    """
    divisor    = KELLY_DIVISORS.get(market, 4)
    kelly_raw  = edge / divisor
    kelly_adj  = kelly_raw * kelly_mult
    max_market = MAX_STAKE.get(market, 0.03)
    max_verdict = VERDICTS.get(verdict_type, {}).get("max_bankroll", 0.05)
    return round(min(kelly_adj, max_market, max_verdict), 4)


def apply_family_caps(
    candidates: list[dict],
    session:    dict,
) -> list[dict]:
    """
    Applique les caps famille et la limite globale session.
    Trie par edge décroissant avant application.
    """
    candidates = sorted(candidates, key=lambda x: x.get("edge", 0), reverse=True)

    total_exp = float(session.get("total_exposure", 0))
    n_signals = int(session.get("total_signals",  0))
    f_over    = float(session.get("family_over",   0))
    f_under   = float(session.get("family_under",  0))
    f_1x2     = float(session.get("family_1x2",   0))

    # Vérifier si on est en mode STRONG_RUPTURE
    is_sr_mode = session.get("has_strong_rupture", False)
    max_exp    = SESSION_MAX_EXPOSURE_SR if is_sr_mode else SESSION_MAX_EXPOSURE

    selected = []
    for s in candidates:
        stake = s.get("stake_pct", 0.0)
        mkt   = s.get("market", "")

        if n_signals >= SESSION_MAX_SIGNALS: break
        if total_exp + stake > max_exp:      continue

        if mkt in ("over_25", "over_35"):
            if f_over + stake > FAMILY_CAPS["over_family"]: continue
            f_over += stake
        elif mkt in ("under_25", "btts_no"):
            if f_under + stake > FAMILY_CAPS["under_family"]: continue
            f_under += stake
        elif mkt.startswith("1x2"):
            if f_1x2 + stake > FAMILY_CAPS["1x2_family"]: continue
            f_1x2 += stake

        total_exp += stake
        n_signals += 1
        selected.append(s)

    return selected


def is_1x2_form_ok(
    home_team:      str,
    away_team:      str,
    home_win_rate:  float,
    away_win_rate:  float,
    fav_is_home:    bool,
) -> bool:
    """Règle forme ≥40%/8m pour signal 1X2."""
    # Amendement v1.5-B : promos/Tier C edge min augmenté
    for team in (home_team, away_team):
        p = CLUBS.get(team, {})
        if p.get("promoted") or p.get("tier") == "C":
            return fav_is_home and home_win_rate >= FORM_WIN_RATE_MIN
    fav_rate = home_win_rate if fav_is_home else away_win_rate
    return fav_rate >= FORM_WIN_RATE_MIN


def determine_verdict(edge: float, dcs_tier: str, flags: dict) -> str:
    """
    Détermine le type de verdict selon edge + contexte.
    """
    has_variance = "VARIANCE" in flags
    has_rupture  = "RUPTURE" in flags

    if dcs_tier == "INSUFFICIENT":                  return "NO_BET"
    if edge <= 0:                                   return "NO_BET"
    if has_rupture and edge >= 0.30 and dcs_tier == "SOLID":
        return "STRONG_RUPTURE"
    if has_variance or dcs_tier == "ACCEPTABLE":
        return "VARIANCE"
    if edge >= 0.10 and dcs_tier in ("SOLID", "VALID"):
        return "VARIANCE" if has_variance else "SMALL_BET"
    return "SMALL_BET"
