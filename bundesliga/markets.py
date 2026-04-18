"""
APEX_OMEGA_De1 · Catalogue complet des marchés de paris
Philosophie : sur 20+ marchés disponibles, UN signal existe toujours.
Le bot émet TOUJOURS le meilleur pari disponible, classé par GRADE.

GRADE A — Marchés principaux haute liquidité
GRADE B — Marchés secondaires fiables
GRADE C — Marchés spéciaux (corner, carton, HT)
GRADE D — Marchés exotiques (dernier recours)
"""

# ══════════════════════════════════════════════════════════════
# CATALOGUE COMPLET DES MARCHÉS
# ══════════════════════════════════════════════════════════════
MARKETS = {

    # ── GRADE A : 1X2 & Double Chance
    "1x2_home":        {"label": "🏆 1 GAGNE",       "grade": "A", "edge_min": 0.05, "kelly_div": 4},
    "1x2_draw":        {"label": "🤝 NUL",            "grade": "A", "edge_min": 0.07, "kelly_div": 5},
    "1x2_away":        {"label": "✈️ 2 GAGNE",        "grade": "A", "edge_min": 0.05, "kelly_div": 4},
    "dc_1x":           {"label": "🔵 DC 1X",          "grade": "A", "edge_min": 0.04, "kelly_div": 5},
    "dc_12":           {"label": "🟢 DC 12",          "grade": "A", "edge_min": 0.04, "kelly_div": 5},
    "dc_x2":           {"label": "🟠 DC X2",          "grade": "A", "edge_min": 0.04, "kelly_div": 5},

    # ── GRADE A : Buts totaux
    "over_05":         {"label": "⚽ OVER 0.5",       "grade": "A", "edge_min": 0.03, "kelly_div": 6},
    "over_15":         {"label": "⚽ OVER 1.5",       "grade": "A", "edge_min": 0.04, "kelly_div": 5},
    "over_25":         {"label": "⚽ OVER 2.5",       "grade": "A", "edge_min": 0.04, "kelly_div": 4},
    "over_35":         {"label": "🔥 OVER 3.5",       "grade": "A", "edge_min": 0.08, "kelly_div": 4},
    "over_45":         {"label": "🔥 OVER 4.5",       "grade": "B", "edge_min": 0.10, "kelly_div": 4},
    "under_05":        {"label": "🔒 UNDER 0.5",      "grade": "B", "edge_min": 0.08, "kelly_div": 6},
    "under_15":        {"label": "🔒 UNDER 1.5",      "grade": "B", "edge_min": 0.10, "kelly_div": 5},
    "under_25":        {"label": "🔒 UNDER 2.5",      "grade": "A", "edge_min": 0.15, "kelly_div": 5},
    "under_35":        {"label": "🔒 UNDER 3.5",      "grade": "B", "edge_min": 0.08, "kelly_div": 5},

    # ── GRADE A : BTTS
    "btts_yes":        {"label": "✅ GG (BTTS OUI)",  "grade": "A", "edge_min": 0.04, "kelly_div": 4},
    "btts_no":         {"label": "🚫 NG (BTTS NON)",  "grade": "A", "edge_min": 0.14, "kelly_div": 5},

    # ── GRADE B : Mi-Temps 1X2
    "ht_home":         {"label": "🔵 MT 1 GAGNE",     "grade": "B", "edge_min": 0.06, "kelly_div": 5},
    "ht_draw":         {"label": "🔵 MT NUL",         "grade": "B", "edge_min": 0.05, "kelly_div": 5},
    "ht_away":         {"label": "🔵 MT 2 GAGNE",     "grade": "B", "edge_min": 0.06, "kelly_div": 5},

    # ── GRADE B : Mi-Temps Over/Under
    "ht_over_05":      {"label": "⚽ MT OVER 0.5",    "grade": "B", "edge_min": 0.04, "kelly_div": 5},
    "ht_over_15":      {"label": "⚽ MT OVER 1.5",    "grade": "B", "edge_min": 0.06, "kelly_div": 5},
    "ht_under_05":     {"label": "🔒 MT UNDER 0.5",   "grade": "B", "edge_min": 0.06, "kelly_div": 6},
    "ht_under_15":     {"label": "🔒 MT UNDER 1.5",   "grade": "B", "edge_min": 0.08, "kelly_div": 6},

    # ── GRADE B : Buts par équipe (Team Totals)
    "home_over_05":    {"label": "🏠 DOM OVER 0.5",   "grade": "B", "edge_min": 0.04, "kelly_div": 5},
    "home_over_15":    {"label": "🏠 DOM OVER 1.5",   "grade": "B", "edge_min": 0.06, "kelly_div": 5},
    "home_over_25":    {"label": "🏠 DOM OVER 2.5",   "grade": "B", "edge_min": 0.08, "kelly_div": 5},
    "away_over_05":    {"label": "✈️ EXT OVER 0.5",   "grade": "B", "edge_min": 0.05, "kelly_div": 5},
    "away_over_15":    {"label": "✈️ EXT OVER 1.5",   "grade": "B", "edge_min": 0.07, "kelly_div": 5},
    "home_under_05":   {"label": "🏠 DOM UNDER 0.5",  "grade": "C", "edge_min": 0.08, "kelly_div": 6},
    "away_under_05":   {"label": "✈️ EXT UNDER 0.5",  "grade": "C", "edge_min": 0.08, "kelly_div": 6},

    # ── GRADE B : Draw No Bet
    "dnb_home":        {"label": "🔵 DNB DOM",        "grade": "B", "edge_min": 0.05, "kelly_div": 5},
    "dnb_away":        {"label": "🟠 DNB EXT",        "grade": "B", "edge_min": 0.05, "kelly_div": 5},

    # ── GRADE C : Corners
    "corners_over_85": {"label": "🚩 CORNERS +8.5",   "grade": "C", "edge_min": 0.06, "kelly_div": 5},
    "corners_over_95": {"label": "🚩 CORNERS +9.5",   "grade": "C", "edge_min": 0.08, "kelly_div": 5},
    "corners_over_105":{"label": "🚩 CORNERS +10.5",  "grade": "C", "edge_min": 0.10, "kelly_div": 5},
    "corners_under_85":{"label": "🚩 CORNERS -8.5",   "grade": "C", "edge_min": 0.08, "kelly_div": 6},
    "corners_under_95":{"label": "🚩 CORNERS -9.5",   "grade": "C", "edge_min": 0.10, "kelly_div": 6},

    # ── GRADE C : Cartons
    "cards_over_25":   {"label": "🟨 CARTONS +2.5",   "grade": "C", "edge_min": 0.06, "kelly_div": 5},
    "cards_over_35":   {"label": "🟨 CARTONS +3.5",   "grade": "C", "edge_min": 0.08, "kelly_div": 5},
    "cards_under_25":  {"label": "🟨 CARTONS -2.5",   "grade": "C", "edge_min": 0.08, "kelly_div": 6},

    # ── GRADE C : Tirs cadrés
    "shots_home_over": {"label": "🎯 TIRS DOM +4.5",  "grade": "C", "edge_min": 0.07, "kelly_div": 5},
    "shots_away_over": {"label": "🎯 TIRS EXT +3.5",  "grade": "C", "edge_min": 0.07, "kelly_div": 5},

    # ── GRADE D : Fautes
    "fouls_over_20":   {"label": "⚠️ FAUTES +20.5",   "grade": "D", "edge_min": 0.08, "kelly_div": 6},
    "fouls_under_20":  {"label": "⚠️ FAUTES -20.5",   "grade": "D", "edge_min": 0.10, "kelly_div": 6},
}

# Ordre de priorité pour sélection du "meilleur" signal
GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}

# Mise max par grade (% bankroll)
GRADE_MAX_STAKE = {
    "A": 0.06,
    "B": 0.04,
    "C": 0.025,
    "D": 0.015,
}

# Mapping marchés Odds API → clés internes
ODDS_API_MARKET_MAP = {
    # h2h → 1X2
    "h2h":                     "h2h",
    # totals → over/under goals
    "totals":                  "totals",
    # double_chance
    "double_chance":           "double_chance",
    # btts
    "both_teams_to_score":     "btts",
    "btts":                    "btts",
    # draw_no_bet
    "draw_no_bet":             "dnb",
    # halftime
    "h2h_h1":                  "ht_h2h",
    "totals_h1":               "ht_totals",
    # team totals
    "team_totals":             "team_totals",
    # corners
    "player_pass_attempts":    None,   # non utilisé
}
