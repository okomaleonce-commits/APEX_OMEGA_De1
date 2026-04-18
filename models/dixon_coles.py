"""
APEX_OMEGA_De1 · Modèle Dixon-Coles Bundesliga
Poisson implémenté en pur Python (math module) — sans scipy ni gfortran.
Paramètres : avg=1.56 · HOME_ADV=1.08 · rho=0.06
"""
import math
import numpy as np
from config.bundesliga_params import (
    LEAGUE_AVG_GOALS_PER_TEAM,
    HOME_ADV,
    DIXON_COLES_RHO,
)

MAX_GOALS = 7


# ────────────────────────────────────────────────────────────────
# PMF Poisson — pur Python, zéro dépendance Fortran
# ────────────────────────────────────────────────────────────────
def poisson_pmf(k: int, lam: float) -> float:
    """P(X = k) pour X ~ Poisson(lam). Stable pour k ≤ 20."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


# ────────────────────────────────────────────────────────────────
# Facteur de correction Dixon-Coles (faibles scores)
# ────────────────────────────────────────────────────────────────
def tau(x: int, y: int, mu: float, nu: float, rho: float) -> float:
    if   x == 0 and y == 0: return 1 - mu * nu * rho
    elif x == 0 and y == 1: return 1 + mu * rho
    elif x == 1 and y == 0: return 1 + nu * rho
    elif x == 1 and y == 1: return 1 - rho
    return 1.0


# ────────────────────────────────────────────────────────────────
# Calcul principal : toutes les probabilités de marché
# ────────────────────────────────────────────────────────────────
def compute_match_probs(
    home_att: float,
    home_def: float,
    away_att: float,
    away_def: float,
    ais_home: dict  = None,
    ais_away: dict  = None,
    rebound_coeff: float   = 0.0,
    home_xg_mult: float    = 1.0,   # Gates rotation UCL/EDE
    away_xg_mult: float    = 1.0,   # Gates ENJEU_ATT_AWAY
) -> dict:
    """
    Retourne toutes les probabilités APEX via Poisson Dixon-Coles.
    Aucune dépendance scipy — PMF calculé avec math.factorial.
    """
    ais_home = ais_home or {"att_mult": 1.0, "def_mult": 1.0}
    ais_away = ais_away or {"att_mult": 1.0, "def_mult": 1.0}

    # ── xG Bundesliga calibrés v1.4
    home_xg = (
        (home_att / LEAGUE_AVG_GOALS_PER_TEAM)
        * (away_def / LEAGUE_AVG_GOALS_PER_TEAM)
        * LEAGUE_AVG_GOALS_PER_TEAM
        * HOME_ADV
        * ais_home.get("att_mult", 1.0)
        * ais_away.get("def_mult", 1.0)   # AIS-F_DEF_away
        * home_xg_mult                     # Gate EDE / Rotation
        + rebound_coeff
    )
    away_xg = (
        (away_att / LEAGUE_AVG_GOALS_PER_TEAM)
        * (home_def / LEAGUE_AVG_GOALS_PER_TEAM)
        * LEAGUE_AVG_GOALS_PER_TEAM
        * ais_away.get("att_mult", 1.0)
        * away_xg_mult                     # Gate ENJEU_ATT_AWAY / Rotation
    )

    # ── Matrice de scores Dixon-Coles (pur Python)
    matrix = {}
    total  = 0.0
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            p = (poisson_pmf(i, home_xg)
                 * poisson_pmf(j, away_xg)
                 * tau(i, j, home_xg, away_xg, DIXON_COLES_RHO))
            matrix[(i, j)] = p
            total += p

    # Normalisation
    if total > 0:
        matrix = {k: v / total for k, v in matrix.items()}

    # ── Probabilités 1X2
    p_home = sum(v for (i, j), v in matrix.items() if i > j)
    p_draw = sum(v for (i, j), v in matrix.items() if i == j)
    p_away = sum(v for (i, j), v in matrix.items() if i < j)

    # ── Totaux
    p_over_25  = sum(v for (i, j), v in matrix.items() if i + j > 2)
    p_over_35  = sum(v for (i, j), v in matrix.items() if i + j > 3)
    p_under_25 = 1 - p_over_25
    p_under_35 = 1 - p_over_35

    # ── BTTS
    p_home_scores = 1 - sum(v for (i, j), v in matrix.items() if i == 0)
    p_away_scores = 1 - sum(v for (i, j), v in matrix.items() if j == 0)
    p_btts_raw    = p_home_scores * p_away_scores

    # ── DOMINANCE_FACTOR v1.4
    ratio = home_xg / max(away_xg, 0.01)
    if   ratio >= 2.20: dom_factor = 0.75
    elif ratio >= 1.80: dom_factor = 0.84
    elif ratio >= 1.40: dom_factor = 0.92
    else:               dom_factor = 1.00
    p_btts_yes = p_btts_raw * dom_factor
    p_btts_no  = 1 - p_btts_yes

    return {
        "home_xg":    round(home_xg,    3),
        "away_xg":    round(away_xg,    3),
        "xg_total":   round(home_xg + away_xg, 3),
        "p_home_win": round(p_home,     4),
        "p_draw":     round(p_draw,     4),
        "p_away_win": round(p_away,     4),
        "p_over_25":  round(p_over_25,  4),
        "p_over_35":  round(p_over_35,  4),
        "p_under_25": round(p_under_25, 4),
        "p_under_35": round(p_under_35, 4),
        "p_btts_yes": round(p_btts_yes, 4),
        "p_btts_no":  round(p_btts_no,  4),
        "dom_factor": dom_factor,
        "ratio_xg":   round(ratio, 3),
    }
