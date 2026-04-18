"""
APEX_OMEGA_De1 · Dixon-Coles Bundesliga
rho=0.06 · avg=1.56 · HOME_ADV=1.08
"""
from __future__ import annotations
import numpy as np
from scipy.stats import poisson
from bundesliga.config_v2_3 import (
    LAMBDA_HOME, LAMBDA_AWAY, HOME_ADV,
    DIXON_COLES_RHO, MAX_GOALS_MATRIX, LAMBDA,
)


def tau(x: int, y: int, mu: float, nu: float, rho: float) -> float:
    """Correction Dixon-Coles pour les faibles scores."""
    if x == 0 and y == 0: return 1 - mu * nu * rho
    if x == 0 and y == 1: return 1 + mu * rho
    if x == 1 and y == 0: return 1 + nu * rho
    if x == 1 and y == 1: return 1 - rho
    return 1.0


def compute_match_probs(
    home_att:   float,
    home_def:   float,
    away_att:   float,
    away_def:   float,
    gate_mods:  dict  | None = None,
) -> dict:
    """
    Calcule toutes les probabilités via Poisson Dixon-Coles.
    gate_mods est le dict consolidé retourné par evaluate_all_gates().
    """
    g = gate_mods or {}

    home_xg_mult   = g.get("home_xg_mult",   1.0)
    away_xg_mult   = g.get("away_xg_mult",   1.0)
    rebound_coeff  = g.get("rebound_coeff",  0.0)
    dom_factor_raw = 1.0  # sera recalculé ci-dessous

    # ── xG de base Bundesliga v1.4
    home_xg = (
        (home_att / LAMBDA_HOME)
        * (away_def / LAMBDA_HOME)
        * LAMBDA_HOME
        * HOME_ADV
        * home_xg_mult
        + rebound_coeff
    )
    away_xg = (
        (away_att / LAMBDA_AWAY)
        * (home_def / LAMBDA_AWAY)
        * LAMBDA_AWAY
        * away_xg_mult
    )
    home_xg = max(home_xg, 0.10)
    away_xg = max(away_xg, 0.10)

    # ── Matrice Dixon-Coles
    N = MAX_GOALS_MATRIX
    M = np.zeros((N + 1, N + 1))
    for i in range(N + 1):
        for j in range(N + 1):
            p = poisson.pmf(i, home_xg) * poisson.pmf(j, away_xg)
            M[i, j] = p * tau(i, j, home_xg, away_xg, DIXON_COLES_RHO)
    M /= M.sum()

    # ── 1X2
    p_home = float(np.tril(M, -1).sum())
    p_draw = float(np.trace(M))
    p_away = float(np.triu(M, 1).sum())

    # ── Totaux
    total_goals = home_xg + away_xg
    p_over25 = float(1 - sum(M[i, j] for i in range(3) for j in range(3 - i)))
    p_under25 = 1 - p_over25
    p_over35 = float(1 - sum(M[i, j] for i in range(4) for j in range(4 - i)))
    p_under35 = 1 - p_over35

    # ── BTTS brut
    p_home_scores = 1 - float(M[:, 0].sum())
    p_away_scores = 1 - float(M[0, :].sum())
    p_btts_raw = p_home_scores * p_away_scores

    # ── DOMINANCE_FACTOR
    ratio = home_xg / max(away_xg, 0.01)
    if ratio >= 2.20:   dom_factor_raw = LAMBDA["DOMINANCE_GTE_2_20"]
    elif ratio >= 1.80: dom_factor_raw = LAMBDA["DOMINANCE_1_80_2_19"]
    elif ratio >= 1.40: dom_factor_raw = LAMBDA["DOMINANCE_1_40_1_79"]
    else:               dom_factor_raw = 1.00

    # Appliquer le facteur fourni par gate B-9 s'il diffère
    dom_factor = g.get("flags", {}).get("dominance_factor", dom_factor_raw)
    p_btts_yes = p_btts_raw * dom_factor
    p_btts_no  = 1 - p_btts_yes

    return {
        "home_xg":    round(home_xg, 3),
        "away_xg":    round(away_xg, 3),
        "xg_total":   round(total_goals, 3),
        "p_home_win": round(p_home, 4),
        "p_draw":     round(p_draw, 4),
        "p_away_win": round(p_away, 4),
        "p_over_25":  round(p_over25, 4),
        "p_under_25": round(p_under25, 4),
        "p_over_35":  round(p_over35, 4),
        "p_under_35": round(p_under35, 4),
        "p_btts_yes": round(p_btts_yes, 4),
        "p_btts_no":  round(p_btts_no, 4),
        "dominance_factor": dom_factor,
        "ratio_xg":   round(ratio, 3),
    }
