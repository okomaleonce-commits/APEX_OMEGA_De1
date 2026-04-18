"""
APEX-OMEGA Bundesliga — Config v2.3
Paramètres métier spécifiques Bundesliga 2025-2026
Basé sur : A-LAP v1.4 + audits empiriques J26-J29
"""

# ══════════════════════════════════════════════════════
# 1. IDENTITÉ LIGUE
# ══════════════════════════════════════════════════════
LEAGUE_ID   = "De1"
LEAGUE_NAME = "1. Bundesliga"
SEASON      = "2025-2026"
API_LEAGUE_ID = 78           # API-Football league ID
TOTAL_MATCHDAYS = 34

# ══════════════════════════════════════════════════════
# 2. PARAMÈTRES POISSON / DIXON-COLES
# ══════════════════════════════════════════════════════
LEAGUE_AVG_GOALS_PER_TEAM = 1.56   # buts/équipe/match historique 10 saisons
HOME_ADV                  = 1.08   # avantage domicile BL (inférieur à la moyenne top5)
DIXON_COLES_RHO           = 0.06   # correction scores faibles (moins de 0-0 en BL)
MONTE_CARLO_ITER          = 50_000

# ══════════════════════════════════════════════════════
# 3. DCS — GRILLE DE CONFIANCE /70
# ══════════════════════════════════════════════════════
DCS_MINIMUM             = 85   # seuil d'entrée général (version v2.3 — recalibré)

# NOTE : DCS est calculé sur /70 points (grille A-LAP v1.4)
# Le seuil 85 correspond à une normalisation interne (/100)
# mapping : 62/70 = 88.6 => SOLID ; 55/70 = 78.6 => VALID

DCS_THRESHOLDS = {
    "SOLID":        62,    # ≥ 62/70 — tous marchés autorisés
    "VALID":        55,    # ≥ 55/70 — marchés principaux
    "ACCEPTABLE":   48,    # ≥ 48/70 — 1X2 uniquement
    "INSUFFICIENT":  0,    # < 48/70 — NO BET absolu
}
DCS_TIER_C_BUTS_MIN     = 55   # promus/Tier C : DCS ≥ 55 pour marchés buts
DCS_PROMOTED_G2_CAP     = 10   # plafond G2 pour clubs promus (données limitées)

# Pénalités gates sur G6 (max 8 pts)
DCS_PENALTY_UCL_GATE    = -4
DCS_PENALTY_UEL_GATE    = -3
DCS_PENALTY_EDE_GATE    = -5

# Ajustements saisonniers DCS
DCS_SEASONAL = {
    "J01_J05":  -5,
    "J17_J19":  -5,    # post-Winterpause
    "J31_J33":  -3,
    "J34":      -10,   # + stake ×0.5
}

# ══════════════════════════════════════════════════════
# 4. COEFFICIENTS LAMBDA (λ) — AJUSTEMENTS xG
# ══════════════════════════════════════════════════════

# ── Poids blessures
LAMBDA_INJURY_WEIGHT    = 1.50   # amplificateur AIS-F quand plusieurs absences cumulées

# ── AIS-F par défaut Tier B (joueur non listé)
AIS_F_DEFAULT_STRIKER   = -0.08
AIS_F_DEFAULT_GK        = +0.10
AIS_F_DEFAULT_DEFENDER  = +0.06
AIS_F_DEFAULT_MIDFIELDER= -0.05

# ── AIS-F Tier S/A — joueurs clés référencés
AIS_F_PLAYERS = {
    "Harry Kane":        {"team": "Bayern Munich",     "pos": "ST", "off": -0.18},
    "Jamal Musiala":     {"team": "Bayern Munich",     "pos": "MF", "off": -0.12},
    "Manuel Neuer":      {"team": "Bayern Munich",     "pos": "GK", "def": +0.18},
    "Jonathan Tah":      {"team": "Bayern Munich",     "pos": "DC", "def": +0.08},
    "Luis Diaz":         {"team": "Bayern Munich",     "pos": "AI", "off": -0.08},
    "Michael Olise":     {"team": "Bayern Munich",     "pos": "AI", "off": -0.10},
    "Joshua Kimmich":    {"team": "Bayern Munich",     "pos": "MF", "off": -0.08},
    "Florian Wirtz":     {"team": "Bayer Leverkusen",  "pos": "MF", "off": -0.20},
    "Aleix Garcia":      {"team": "Bayer Leverkusen",  "pos": "MF", "off": -0.12},
    "Serhou Guirassy":   {"team": "Borussia Dortmund", "pos": "ST", "off": -0.15},
    "Gregor Kobel":      {"team": "Borussia Dortmund", "pos": "GK", "def": +0.15},
    "Xavi Simons":       {"team": "RB Leipzig",        "pos": "MF", "off": -0.14},
    "Yan Diomande":      {"team": "RB Leipzig",        "pos": "AI", "off": -0.12},
    "Christoph Baumgartner": {"team": "RB Leipzig",   "pos": "MF", "off": -0.10},
    "Ermedin Demirovic": {"team": "VfB Stuttgart",     "pos": "ST", "off": -0.15},
    "Deniz Undav":       {"team": "VfB Stuttgart",     "pos": "ST", "off": -0.12},
    "Hugo Ekitike":      {"team": "Eintracht Frankfurt","pos": "ST", "off": -0.13},
    "Arnaud Kalimuendo": {"team": "Eintracht Frankfurt","pos": "ST", "off": -0.10},
    "Andrej Kramaric":   {"team": "Hoffenheim",        "pos": "ST", "off": -0.18},
    "Fisnik Asllani":    {"team": "Hoffenheim",        "pos": "ST", "off": -0.10},
    "Vincenzo Grifo":    {"team": "SC Freiburg",       "pos": "MF", "off": -0.10},
}

# ── Bonus de rupture (REBOUND_COEFF)
LAMBDA_REBOUND_HOME     = +0.10   # additif sur home_xg si rebond ≥ 65%/8m
LAMBDA_REBOUND_SERIE    = +0.15   # série noire ≥ 6 matchs + adversaire faible

# ── Gate ENJEU_ATT_AWAY
LAMBDA_ENJEU_UCL_J25    = +0.20   # +20% away_att J25+ Top 4 UCL + 2 attaquants ≥8G
LAMBDA_ENJEU_UCL_J29    = +0.25   # +25% away_att J29+
LAMBDA_ENJEU_REL        = +0.15   # relégation directe J28+

# ── Gate EDE (Effondrement Défensif Extérieur)
LAMBDA_EDE_2_DEF        = +0.15   # +15% home_xg si 2 défenseurs absents
LAMBDA_EDE_3_DEF        = +0.22   # +22% home_xg si 3+ défenseurs absents

# ── Gates Rotation UCL/UEL
LAMBDA_UCL_SAM_AFTER_WED = -0.20
LAMBDA_UCL_FRI_AFTER_WED = -0.25   # critique : 72h
LAMBDA_UCL_ELIMINATION   = 0.0     # Kelly ×0.75 appliqué — Gate partiel MT1/MT2
LAMBDA_UCL_BIG_WIN_WE    = -0.08
LAMBDA_UEL_SAM_AFTER_WED = -0.12
LAMBDA_UEL_FRI_AFTER_WED = -0.15

# ── DOMINANCE_FACTOR (correction P(BTTS))
DOMINANCE_FACTOR_TABLE = [
    (2.20, 0.75),
    (1.80, 0.84),
    (1.40, 0.92),
]

# ── Pondération Clean Sheet par qualité adversaire
CS_WEIGHT_TABLE = {
    "mostly_tier_c": 0.70,
    "mix_b_c":       0.85,
    "includes_a_s":  1.00,
}

# ── Away_att plancher pour Tier A/S
AWAY_ATT_FLOOR_TIER_AS  = 0.80   # min 80% de la moy. saison (v1.4)

# ══════════════════════════════════════════════════════
# 5. FLAGS SPÉCIAUX BUNDESLIGA
# ══════════════════════════════════════════════════════
FLAGS = {
    # Instabilité / imprévisibilité
    "RUPTURE":           "Rupture de forme significative détectée",
    "VARIANCE":          "Variance élevée — réduire mise de 30%",
    "MID_TABLE_CHAOS":   "Match milieu de tableau — données insuffisantes",

    # Profils équipes spéciaux
    "LEIPZIG_HOME_SPECIAL":  "Leipzig domicile — profil offensif consolidé J20+",
    "BAYERN_UCL_ROTATION":   "Bayern : rotation majeure avant/après UCL",
    "BVB_OFFENSIVE_OPEN":    "Dortmund : défense poreuse — Over 2.5 structurel",
    "FREIBURG_HOME_FORTRESS":"Freiburg : bastion défensif à domicile",

    # Contextes enjeux
    "UCL_CHASER":        "Équipe en lutte Top 4 UCL (J25+)",
    "RELEGATION_TERROR": "Équipe en zone relégation directe (J28+)",
    "TITLE_COAST":       "Champion quasi-assuré → rotation probable",

    # Qualité données
    "PROMOTED_LIMITED":  "Club promu — données BL limitées (< 1 saison)",
    "EDE_ACTIVE":        "Effondrement Défensif Extérieur détecté",
    "ANTI_UNDER_PAUSE":  "Pause anti-Under active — U2.5/BTTS Non interdits",
    "WINTERPAUSE_POST":  "Post-Winterpause J17-19 — DCS −5 pts",
    "UCL_ELIMINATION":   "Équipe éliminée UCL — effet rebond MT1 / risque MT2",
    "UEL_FATIGUE":       "Match UEL/UECL dans les 72h — xG réduit",
    "J34_SIMULTANEOUS":  "Journée 34 — stake ×0.5 (tous matchs simultanés)",
}

# ══════════════════════════════════════════════════════
# 6. VERDICTS
# ══════════════════════════════════════════════════════
VERDICTS = {
    "STRONG_RUPTURE": {
        "label":        "🔥 FORTE RUPTURE",
        "max_bankroll": 0.15,   # 15% autorisé pour ce cas
        "description":  "Signal de rupture très clair — edge massif + DCS SOLID",
    },
    "VARIANCE": {
        "label":        "⚡ VARIANCE",
        "max_bankroll": 0.08,
        "description":  "Signal présent mais contexte instable — mise réduite",
    },
    "SMALL_BET": {
        "label":        "📊 SMALL BET",
        "max_bankroll": 0.05,
        "description":  "Signal faible ou marché à faible liquidité",
    },
    "NO_BET": {
        "label":        "🚫 NO BET",
        "max_bankroll": 0.0,
        "description":  "Conditions insuffisantes — aucune mise",
    },
}

# ══════════════════════════════════════════════════════
# 7. MARCHÉS — SEUILS EDGE v1.4 (BUNDESLIGA)
# ══════════════════════════════════════════════════════
EDGE_THRESHOLDS = {
    "over_25":    0.04,    # abaissé — marché phare BL (fiabilité 64%)
    "over_35":    0.08,    # signal principal si 3 critères réunis
    "under_35":   0.06,
    "under_25":   0.15,    # relevé après audit J27 (3 défaites consécutives)
    "btts_yes":   0.04,
    "btts_no":    0.14,    # quasi-interdit en BL
    "1x2_fav":    0.05,
    "1x2_out":    0.12,    # outsider > 4.0
    "1x2_promo":  0.18,    # promus/Tier C avec DCS ≤ 52 (v1.5-A)
    "handicap":   0.05,
}

KELLY_DIVISORS = {
    "over_25":   4,
    "over_35":   4,
    "under_35":  5,
    "under_25":  5,
    "btts_yes":  4,
    "btts_no":   6,
    "1x2_fav":   4,
    "1x2_out":   8,
    "handicap":  4,
}

MAX_STAKE = {
    "over_25":    0.05,
    "over_35":    0.04,
    "under_35":   0.04,
    "under_25":   0.03,
    "btts_yes":   0.04,
    "btts_no":    0.02,
    "1x2_fav":    0.05,
    "1x2_out":    0.02,
    "handicap":   0.04,
}

FAMILY_CAPS = {
    "over_family":   0.08,   # Over 2.5 + Over 3.5
    "under_family":  0.04,   # Under 2.5 + BTTS Non (ultra-restrictif)
    "1x2_family":    0.06,
}

# ══════════════════════════════════════════════════════
# 8. RÈGLES RISQUE GLOBALES
# ══════════════════════════════════════════════════════
SESSION_MAX_EXPOSURE     = 0.12   # 12% bankroll par session (journée)
SESSION_MAX_EXPOSURE_SR  = 0.15   # 15% si verdict STRONG_RUPTURE
SESSION_MAX_SIGNALS      = 4      # 4 paris maximum par journée
FORM_WIN_RATE_MIN        = 0.40   # 40%/8 matchs pour signal 1X2
FORM_WINDOW_1X2          = 8
FORM_WINDOW_MIN          = 5      # fenêtre forme minimale stricte

# ── Pause anti-Under
ANTI_UNDER_TRIGGER       = 2      # défaites U2.5 consécutives → moratoire
ANTI_UNDER_JOURNEES      = 2      # journées de pause forcée

# ── Over 3.5 "signal principal" (3 critères v1.3 confirmés)
OVER35_PRINCIPAL = {
    "xg_min":   3.50,
    "h2h_min":  3.50,
    "edge_min": 0.08,
}

# ══════════════════════════════════════════════════════
# 9. PROFILS CLUBS (18 équipes 2025-26)
# ══════════════════════════════════════════════════════
CLUBS = {
    "Bayern Munich": {
        "tier": "S", "avg_buts": 3.8, "over25_pct": 0.72,
        "ucl_rotation": True,
        "u25_home": "FORBIDDEN",
        "flags": ["BAYERN_UCL_ROTATION"],
        "special": "LEIPZIG_HOME_SPECIAL",
    },
    "Bayer Leverkusen": {
        "tier": "S", "avg_buts": 3.2, "over25_pct": 0.68,
        "ucl_rotation": True,
        "u25_all": "STRONGLY_DISCOURAGED",
        "btts_no_all": "FORBIDDEN",
        "form_1x2_rule": True,
        "flags": [],
    },
    "Borussia Dortmund": {
        "tier": "S", "avg_buts": 3.5, "over25_pct": 0.70,
        "u25_all": "FORBIDDEN",
        "flags": ["BVB_OFFENSIVE_OPEN"],
    },
    "RB Leipzig": {
        "tier": "A", "avg_buts": 2.8, "over25_pct": 0.60,
        "u25_edge_min": 0.15,
        "flags": ["LEIPZIG_HOME_SPECIAL"],
    },
    "Eintracht Frankfurt": {
        "tier": "A", "avg_buts": 3.1, "over25_pct": 0.65,
        "uel_rotation": True,
        "enjeu_att_away": True,
        "flags": ["UCL_CHASER"],
    },
    "VfB Stuttgart": {
        "tier": "A", "avg_buts": 3.0, "over25_pct": 0.63,
        "enjeu_att_away": True,
        "flags": ["UCL_CHASER"],
    },
    "Hoffenheim": {
        "tier": "A", "avg_buts": 3.1, "over25_pct": 0.65,
        "enjeu_att_away": True,
        "flags": ["UCL_CHASER"],
    },
    "SC Freiburg": {
        "tier": "B", "avg_buts": 2.4, "over25_pct": 0.50,
        "uel_rotation": True,
        "away_att_floor": True,
        "flags": ["FREIBURG_HOME_FORTRESS"],
    },
    "Borussia M'gladbach": {
        "tier": "B", "avg_buts": 2.9, "over25_pct": 0.58,
        "flags": ["MID_TABLE_CHAOS"],
    },
    "FC Augsburg": {
        "tier": "B", "avg_buts": 2.3, "over25_pct": 0.45,
        "best_u25_profile": True,
        "u25_edge_min": 0.15,
        "flags": [],
    },
    "Werder Bremen": {
        "tier": "B", "avg_buts": 2.8, "over25_pct": 0.58,
        "flags": ["MID_TABLE_CHAOS"],
    },
    "VfL Wolfsburg": {
        "tier": "B", "avg_buts": 2.7, "over25_pct": 0.55,
        "hard_to_model": True,
        "dcs_min": 58,
        "flags": ["VARIANCE"],
    },
    "1. FSV Mainz 05": {
        "tier": "B", "avg_buts": 2.2, "over25_pct": 0.44,
        "uecl_rotation": True,
        "flags": [],
    },
    "1. FC Heidenheim": {
        "tier": "C", "avg_buts": 2.2, "over25_pct": 0.42,
        "relegation_zone": True,
        "flags": ["RELEGATION_TERROR"],
    },
    "1. FC Union Berlin": {
        "tier": "C", "avg_buts": 2.5, "over25_pct": 0.50,
        "flags": [],
    },
    "FC St. Pauli": {
        "tier": "C", "avg_buts": 2.3, "over25_pct": 0.45,
        "relegation_zone": True,
        "flags": ["RELEGATION_TERROR"],
    },
    "1. FC Köln": {
        "tier": "C", "avg_buts": 2.7, "over25_pct": 0.54,
        "promoted": True,
        "dcs_g2_cap": 10,
        "edge_1x2_min": 0.18,
        "flags": ["PROMOTED_LIMITED"],
    },
    "Hamburger SV": {
        "tier": "C", "avg_buts": 2.5, "over25_pct": 0.52,
        "promoted": True,
        "dcs_g2_cap": 10,
        "edge_1x2_min": 0.18,
        "flags": ["PROMOTED_LIMITED"],
    },
}

# ══════════════════════════════════════════════════════
# 10. MORATORIUMS FIXES PAR CLUB
# ══════════════════════════════════════════════════════
MORATORIUMS_FIXED = {
    # U2.5 domicile INTERDIT
    "u25_home_forbidden": ["Bayern Munich", "Borussia Dortmund"],

    # U2.5 global INTERDIT
    "u25_global_forbidden": ["Borussia Dortmund"],

    # U2.5 fortement déconseillé (edge ≥15% obligatoire)
    "u25_strongly_discouraged": ["Bayer Leverkusen", "Eintracht Frankfurt"],

    # BTTS Non global INTERDIT
    "btts_no_forbidden": ["Bayer Leverkusen", "Bayern Munich", "Borussia Dortmund", "Eintracht Frankfurt"],
}

# ══════════════════════════════════════════════════════
# 11. CRON SCHEDULE (Render)
# ══════════════════════════════════════════════════════
CRON_INGESTION = "0 6 * * 2,5"    # Mardi + Vendredi 06:00 UTC
CRON_ANALYSIS  = "30 9 * * 2,5"   # Mardi + Vendredi 09:30 UTC
CRON_AUDIT     = "0 23 * * 0"     # Dimanche 23:00 UTC
CRON_REFRESH   = "0 */2 * * *"    # Toutes les 2h (cotes + compos)

# ══════════════════════════════════════════════════════
# 12. CONSTANTES POISSON — ALIASES pour dixon_coles.py
# ══════════════════════════════════════════════════════
LAMBDA_HOME      = LEAGUE_AVG_GOALS_PER_TEAM   # 1.56
LAMBDA_AWAY      = LEAGUE_AVG_GOALS_PER_TEAM   # 1.56
MAX_GOALS_MATRIX = 10   # dimension max de la matrice N×N

# Facteurs DOMINANCE_FACTOR par seuil ratio xG
LAMBDA = {
    "DOMINANCE_GTE_2_20":  0.75,
    "DOMINANCE_1_80_2_19": 0.84,
    "DOMINANCE_1_40_1_79": 0.92,

    # AIS-F amplificateurs
    "INJURY_WEIGHT":       1.50,

    # Rebond
    "REBOUND_HOME":        0.10,
    "REBOUND_SERIE_NOIRE": 0.15,
}


# ── AIS-F par défaut (joueur absent sans profil explicite)
AIS_F_DEFAULT = {
    "ST":  {"att": -0.08, "def":  0.00},
    "MF":  {"att": -0.05, "def": +0.02},
    "DC":  {"att":  0.00, "def": +0.06},
    "GK":  {"att":  0.00, "def": +0.10},
    "WB":  {"att": -0.03, "def": +0.04},
    "AI":  {"att": -0.06, "def":  0.00},
}

# ── AIS-F joueurs clés par club (extrait de CLUBS pour compatibilité import direct)
AIS_F = {
    club: data.get("ais_f", {})
    for club, data in CLUBS.items()
    if "ais_f" in data
}
