"""APEX_OMEGA_De1 · Normalizer — API-Football → APEX format"""
def normalize_fixture(raw):
    f  = raw.get("fixture",{})
    lg = raw.get("league",{})
    h  = raw.get("teams",{}).get("home",{})
    a  = raw.get("teams",{}).get("away",{})
    return {
        "fixture_id": f.get("id"),
        "matchday":   int(str(lg.get("round","0")).replace("Regular Season - ","")),
        "kickoff":    f.get("date",""),
        "home_team":  h.get("name",""),
        "away_team":  a.get("name",""),
        "home_id":    h.get("id"),
        "away_id":    a.get("id"),
        "league_id":  lg.get("id", 78),
        "venue":      f.get("venue",{}).get("name",""),
        # Stats (à enrichir)
        "home_avg_scored":   1.56, "home_avg_conceded": 1.56,
        "away_avg_scored":   1.56, "away_avg_conceded": 1.56,
        "home_absent_players":[], "away_absent_players":[],
        "away_absent_defenders": 0,
        "home_win_rate_8m":  0.50, "away_win_rate_8m":  0.50,
        "h2h_avg_goals":     2.80,
        "home_days_since_euro": None, "away_days_since_euro": None,
        "home_ucl_eliminated": False,"away_ucl_contender":  False,
        "odds_movements":    {},
        "fair_odds":         {},
        "home_league_position": 9, "away_league_position": 9,
        "home_points": 40, "away_points": 40,
    }


def enrich_stats(fixture: dict, team_stats: dict) -> dict:
    """
    Enrichit un fixture normalisé avec les stats API-Football / FootyStats.
    team_stats: {"home": {...}, "away": {...}}
    """
    home_s = team_stats.get("home", {})
    away_s = team_stats.get("away", {})

    fixture["home_avg_scored"]        = home_s.get("avg_goals_scored",   1.56)
    fixture["home_avg_conceded"]      = home_s.get("avg_goals_conceded", 1.56)
    fixture["home_over25_pct"]        = home_s.get("over25_pct",         0.55)
    fixture["home_win_rate_8m"]       = home_s.get("win_rate_8m",        0.40)
    fixture["home_cs_pct"]            = home_s.get("cs_pct",             0.25)

    fixture["away_avg_scored"]        = away_s.get("avg_goals_scored",   1.56)
    fixture["away_avg_conceded"]      = away_s.get("avg_goals_conceded", 1.56)
    fixture["away_over25_pct"]        = away_s.get("over25_pct",         0.55)
    fixture["away_win_rate_8m"]       = away_s.get("win_rate_8m",        0.40)
    fixture["away_cs_pct"]            = away_s.get("cs_pct",             0.20)

    # H2H
    fixture["h2h_avg_goals"]          = team_stats.get("h2h_avg_goals",  2.60)
    fixture["away_goals_conceded_last3"] = away_s.get("goals_conceded_last3", 3)

    return fixture
