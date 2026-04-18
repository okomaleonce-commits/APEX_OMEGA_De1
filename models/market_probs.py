"""
APEX_OMEGA_De1 · Calcul probabilités pour TOUS les marchés
À partir des xG Poisson, dérive les P() de chaque marché disponible.
Principe : sur 20+ marchés, UN edge positif existe toujours.
"""
import math
from models.dixon_coles import compute_match_probs, poisson_pmf

MAX_GOALS = 7


def compute_all_market_probs(
    home_xg: float,
    away_xg: float,
    home_corners_avg: float = 5.5,
    away_corners_avg: float = 4.5,
    home_cards_avg: float   = 1.8,
    away_cards_avg: float   = 1.6,
    home_shots_avg: float   = 5.0,
    away_shots_avg: float   = 3.5,
    home_fouls_avg: float   = 11.0,
    away_fouls_avg: float   = 10.5,
) -> dict:
    """
    Calcule les probabilités de TOUS les marchés disponibles.
    Entrée : xG home + away (après application des gates).
    Retourne : dict {market_key: probability}
    """
    # ── Matrice Poisson Dixon-Coles
    from bundesliga.config_v2_3 import DIXON_COLES_RHO
    matrix = {}
    total  = 0.0
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            tau = _tau(i, j, home_xg, away_xg, DIXON_COLES_RHO)
            p   = poisson_pmf(i, home_xg) * poisson_pmf(j, away_xg) * tau
            matrix[(i, j)] = p
            total += p
    if total > 0:
        matrix = {k: v / total for k, v in matrix.items()}

    # ── 1X2
    p_home = sum(v for (i,j),v in matrix.items() if i > j)
    p_draw = sum(v for (i,j),v in matrix.items() if i == j)
    p_away = sum(v for (i,j),v in matrix.items() if i < j)

    # ── Double Chance
    p_1x = p_home + p_draw
    p_12 = p_home + p_away
    p_x2 = p_draw + p_away

    # ── Over/Under totaux
    p_over_05  = 1 - matrix.get((0,0), 0)
    p_over_15  = sum(v for (i,j),v in matrix.items() if i+j > 1)
    p_over_25  = sum(v for (i,j),v in matrix.items() if i+j > 2)
    p_over_35  = sum(v for (i,j),v in matrix.items() if i+j > 3)
    p_over_45  = sum(v for (i,j),v in matrix.items() if i+j > 4)

    # ── BTTS
    p_home_scores = 1 - sum(v for (i,j),v in matrix.items() if i == 0)
    p_away_scores = 1 - sum(v for (i,j),v in matrix.items() if j == 0)
    # Dominance Factor déjà appliqué dans home_xg/away_xg via gates
    ratio = home_xg / max(away_xg, 0.01)
    dom   = 0.75 if ratio>=2.20 else 0.84 if ratio>=1.80 else 0.92 if ratio>=1.40 else 1.0
    p_btts_yes = p_home_scores * p_away_scores * dom
    p_btts_no  = 1 - p_btts_yes

    # ── DNB
    p_dnb_home = p_home / max(p_home + p_away, 0.001)
    p_dnb_away = p_away / max(p_home + p_away, 0.001)

    # ── Team Totals (buts par équipe)
    p_home_over_05 = 1 - sum(v for (i,j),v in matrix.items() if i == 0)
    p_home_over_15 = sum(v for (i,j),v in matrix.items() if i > 1)
    p_home_over_25 = sum(v for (i,j),v in matrix.items() if i > 2)
    p_away_over_05 = 1 - sum(v for (i,j),v in matrix.items() if j == 0)
    p_away_over_15 = sum(v for (i,j),v in matrix.items() if j > 1)
    p_home_under_05 = sum(v for (i,j),v in matrix.items() if i == 0)
    p_away_under_05 = sum(v for (i,j),v in matrix.items() if j == 0)

    # ── Mi-Temps 1X2 (approx : 45% des buts en 1ère mi-temps)
    ht_home_xg = home_xg * 0.45
    ht_away_xg = away_xg * 0.45
    ht_matrix  = _build_matrix(ht_home_xg, ht_away_xg, rho=0.03)
    p_ht_home  = sum(v for (i,j),v in ht_matrix.items() if i > j)
    p_ht_draw  = sum(v for (i,j),v in ht_matrix.items() if i == j)
    p_ht_away  = sum(v for (i,j),v in ht_matrix.items() if i < j)

    # ── Mi-Temps Over/Under
    p_ht_over_05  = 1 - ht_matrix.get((0,0), 0)
    p_ht_over_15  = sum(v for (i,j),v in ht_matrix.items() if i+j > 1)
    p_ht_under_05 = ht_matrix.get((0,0), 0)
    p_ht_under_15 = 1 - p_ht_over_15

    # ── Corners (Poisson indépendant)
    c_total_avg = home_corners_avg + away_corners_avg
    p_corners_over_85  = 1 - sum(poisson_pmf(k, c_total_avg) for k in range(9))
    p_corners_over_95  = 1 - sum(poisson_pmf(k, c_total_avg) for k in range(10))
    p_corners_over_105 = 1 - sum(poisson_pmf(k, c_total_avg) for k in range(11))
    p_corners_under_85 = 1 - p_corners_over_85
    p_corners_under_95 = 1 - p_corners_over_95

    # ── Cartons (Poisson indépendant)
    cards_total = home_cards_avg + away_cards_avg
    p_cards_over_25  = 1 - sum(poisson_pmf(k, cards_total) for k in range(3))
    p_cards_over_35  = 1 - sum(poisson_pmf(k, cards_total) for k in range(4))
    p_cards_under_25 = 1 - p_cards_over_25

    # ── Tirs cadrés (Poisson)
    p_shots_home_over = 1 - sum(poisson_pmf(k, home_shots_avg) for k in range(5))
    p_shots_away_over = 1 - sum(poisson_pmf(k, away_shots_avg) for k in range(4))

    # ── Fautes (Poisson)
    fouls_total = home_fouls_avg + away_fouls_avg
    p_fouls_over_20  = 1 - sum(poisson_pmf(k, fouls_total) for k in range(21))
    p_fouls_under_20 = 1 - p_fouls_over_20

    return {
        # 1X2
        "1x2_home":    round(p_home, 4),
        "1x2_draw":    round(p_draw, 4),
        "1x2_away":    round(p_away, 4),
        # Double Chance
        "dc_1x":       round(p_1x, 4),
        "dc_12":       round(p_12, 4),
        "dc_x2":       round(p_x2, 4),
        # Over/Under goals
        "over_05":     round(p_over_05, 4),
        "over_15":     round(p_over_15, 4),
        "over_25":     round(p_over_25, 4),
        "over_35":     round(p_over_35, 4),
        "over_45":     round(p_over_45, 4),
        "under_05":    round(1 - p_over_05, 4),
        "under_15":    round(1 - p_over_15, 4),
        "under_25":    round(1 - p_over_25, 4),
        "under_35":    round(1 - p_over_35, 4),
        # BTTS
        "btts_yes":    round(p_btts_yes, 4),
        "btts_no":     round(p_btts_no,  4),
        # DNB
        "dnb_home":    round(p_dnb_home, 4),
        "dnb_away":    round(p_dnb_away, 4),
        # Team totals
        "home_over_05": round(p_home_over_05, 4),
        "home_over_15": round(p_home_over_15, 4),
        "home_over_25": round(p_home_over_25, 4),
        "away_over_05": round(p_away_over_05, 4),
        "away_over_15": round(p_away_over_15, 4),
        "home_under_05":round(p_home_under_05, 4),
        "away_under_05":round(p_away_under_05, 4),
        # HT 1X2
        "ht_home":     round(p_ht_home, 4),
        "ht_draw":     round(p_ht_draw, 4),
        "ht_away":     round(p_ht_away, 4),
        # HT Over/Under
        "ht_over_05":  round(p_ht_over_05, 4),
        "ht_over_15":  round(p_ht_over_15, 4),
        "ht_under_05": round(p_ht_under_05, 4),
        "ht_under_15": round(p_ht_under_15, 4),
        # Corners
        "corners_over_85":  round(p_corners_over_85, 4),
        "corners_over_95":  round(p_corners_over_95, 4),
        "corners_over_105": round(p_corners_over_105, 4),
        "corners_under_85": round(p_corners_under_85, 4),
        "corners_under_95": round(p_corners_under_95, 4),
        # Cartons
        "cards_over_25":  round(p_cards_over_25, 4),
        "cards_over_35":  round(p_cards_over_35, 4),
        "cards_under_25": round(p_cards_under_25, 4),
        # Tirs
        "shots_home_over": round(p_shots_home_over, 4),
        "shots_away_over": round(p_shots_away_over, 4),
        # Fautes
        "fouls_over_20":  round(p_fouls_over_20, 4),
        "fouls_under_20": round(p_fouls_under_20, 4),
        # Méta
        "_home_xg": round(home_xg, 3),
        "_away_xg": round(away_xg, 3),
        "_xg_total": round(home_xg + away_xg, 3),
        "_dom_factor": dom,
        "_ratio_xg": round(ratio, 3),
    }


def _tau(x, y, mu, nu, rho):
    if x==0 and y==0: return 1 - mu*nu*rho
    if x==0 and y==1: return 1 + mu*rho
    if x==1 and y==0: return 1 + nu*rho
    if x==1 and y==1: return 1 - rho
    return 1.0

def _build_matrix(hxg, axg, rho=0.06):
    mat = {}
    tot = 0.0
    for i in range(MAX_GOALS+1):
        for j in range(MAX_GOALS+1):
            p = poisson_pmf(i, hxg) * poisson_pmf(j, axg) * _tau(i, j, hxg, axg, rho)
            mat[(i,j)] = p
            tot += p
    return {k: v/tot for k,v in mat.items()} if tot > 0 else mat
