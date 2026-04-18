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
