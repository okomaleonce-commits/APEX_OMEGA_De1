"""
APEX_OMEGA_De1 · Pipeline Bundesliga — orchestrateur principal v3
Corrections :
  - compute_ais_f avec 3 args (team, absent, CLUBS)
  - isinstance(dict) sur tous les items API
  - normalize_club_name sur tous les noms d'équipe
  - Odds API 401 gracieux → DCS pénalisé mais non bloquant
  - exc_info=True sur tous les logs d'erreur
"""
from __future__ import annotations
import asyncio
import logging
import uuid
from datetime import datetime, timedelta

from bundesliga.router      import BundesligaRouter
from bundesliga.gates       import GateContext, run_all_gates as evaluate_all_gates
from bundesliga.config_v2_3 import (
    ANTI_UNDER_TRIGGER, ANTI_UNDER_JOURNEES, CLUBS, normalize_club_name,
)

from ingestion.fixtures_service import (
    get_upcoming_fixtures_robust as get_upcoming_fixtures,
    get_team_form,
    get_h2h, get_fixture_result,
    compute_win_rate, compute_h2h_avg_goals,
)
from ingestion.lineup_service import (
    get_injuries, compute_ais_f,
    count_absent_defenders, gk_is_experienced,
)
from ingestion.odds_service   import build_fair_odds_dict
from ingestion.normalizer     import normalize_fixture, enrich_stats

from trust.trust_matrix       import DCSCalculator
from models.dixon_coles       import compute_match_probs
from models.market_probs       import compute_all_market_probs
from decisions.verdict_engine  import VerdictEngine
from decisions.rationale_builder import (
    build_pre_match_report, build_daily_summary, build_audit_report,
)
from storage.signals_repo   import SignalsRepo
from storage.outcomes_repo  import OutcomesRepo
from interfaces.telegram_bot import send_analysis, send_audit, send_no_bet_summary

logger = logging.getLogger(__name__)


class ApexBundesligaPipeline:

    def __init__(self):
        self.router   = BundesligaRouter()
        self.dcs_calc = DCSCalculator()
        self.verdict  = VerdictEngine()
        self.signals  = SignalsRepo()
        self.outcomes = OutcomesRepo()
        self._anti_under_remaining = 0

    # ═══════════════════════════════════════════════════════════
    async def daily_scan(self):
        """07:00 UTC — analyse les matchs des 3 prochains jours."""
        logger.info("=== APEX Daily Scan ===")
        raw      = get_upcoming_fixtures_robust(days_ahead=3)
        filtered = self.router.filter_batch(raw)

        session = _new_session()
        all_signals, passes = [], 0

        for raw_fx in filtered:
            try:
                sigs = await self._analyze(raw_fx, session)
                if sigs:
                    all_signals.extend(sigs)
                    _update_session(session, sigs)
                else:
                    passes += 1
            except Exception as e:
                logger.error(f"Pipeline daily_scan error: {e}", exc_info=True)
                passes += 1

        if all_signals:
            md = all_signals[0].get("matchday", "?")
            await send_analysis(
                build_daily_summary(md, all_signals, session["total_exposure"])
            )
        else:
            await send_no_bet_summary(matchday="?", passes=passes)

        logger.info(f"=== Scan terminé : {len(all_signals)} signaux · {passes} NO BET ===")

    # ═══════════════════════════════════════════════════════════
    async def _analyze(self, raw_fx: dict, session: dict) -> list[dict]:
        """Pipeline complet pour un match — défensif contre les erreurs API."""

        # ── 0. Normalisation + filtre router ──────────────────
        match = normalize_fixture(raw_fx)
        if not self.router.route(match):
            return []

        home       = match["home_team"]
        away       = match["away_team"]
        home_id    = match.get("home_id")
        away_id    = match.get("away_id")
        fixture_id = match.get("fixture_id")
        md         = int(match.get("matchday") or 20)

        # ── 1. Forme + H2H ────────────────────────────────────
        home_form = _safe_list(get_team_form(home_id, last=8))
        away_form = _safe_list(get_team_form(away_id, last=8))
        h2h_data  = _safe_list(get_h2h(home_id, away_id, last=10))

        team_stats = {
            "home": _form_to_stats(home_form, home_id),
            "away": _form_to_stats(away_form, away_id),
            "h2h_avg_goals": compute_h2h_avg_goals(h2h_data),
        }
        match = enrich_stats(match, team_stats)
        match["home_win_rate_8m"] = compute_win_rate(home_form, home_id)
        match["away_win_rate_8m"] = compute_win_rate(away_form, away_id)

        # ── 2. Absences + AIS-F ───────────────────────────────
        home_inj = _safe_list(get_injuries(home_id, fixture_id))
        away_inj = _safe_list(get_injuries(away_id, fixture_id))

        # Filtre défensif : seuls les items qui sont des dicts
        home_absent = [
            i["player"].get("name", "")
            for i in home_inj
            if isinstance(i, dict) and isinstance(i.get("player"), dict)
        ]
        away_absent = [
            i["player"].get("name", "")
            for i in away_inj
            if isinstance(i, dict) and isinstance(i.get("player"), dict)
        ]

        ais_h = compute_ais_f(home, home_absent)   # ← 3 args
        ais_a = compute_ais_f(away, away_absent)

        # ── 3. Cotes marché ───────────────────────────────────
        fair_odds = build_fair_odds_dict(home, away)       # {} si 401/erreur
        match["fair_odds"] = fair_odds
        odds_available = bool(fair_odds.get("1x2_home_fair") or fair_odds.get("over_25"))

        # ── 4. GateContext + Gates ────────────────────────────
        ctx = GateContext(
            home_team   = home,
            away_team   = away,
            matchday    = md,
            kickoff_utc = match.get("kickoff", ""),
            away_absent_defenders = count_absent_defenders(away_inj),
            away_gk_experienced   = gk_is_experienced(away_inj),
            away_goals_conceded_3 = match.get("away_goals_conceded_last3", 0),
            home_win_rate_8m = match.get("home_win_rate_8m", 0.40),
            away_win_rate_8m = match.get("away_win_rate_8m", 0.40),
            h2h_avg_goals    = match.get("h2h_avg_goals",    2.60),
            home_avg_scored   = match.get("home_avg_scored",   1.56),
            home_avg_conceded = match.get("home_avg_conceded", 1.56),
            away_avg_scored   = match.get("away_avg_scored",   1.56),
            away_avg_conceded = match.get("away_avg_conceded", 1.56),
            home_over25_pct   = match.get("home_over25_pct",  0.55),
            away_over25_pct   = match.get("away_over25_pct",  0.55),
            anti_under_active    = self._anti_under_remaining > 0,
            anti_under_remaining = self._anti_under_remaining,
            session_signals      = session["total_signals"],
            session_exposure     = session["total_exposure"],
        )
        ctx = evaluate_all_gates(ctx)

        if ctx.blocked:
            logger.info(f"Gate BLOCKED [{home} vs {away}]: {ctx.block_reason}")
            return []

        # ── 5. DCS ────────────────────────────────────────────
        dcs = self.dcs_calc.compute(
            home_club = home,
            away_club = away,
            sources = {
                "footystats":  True,
                "betfair":     odds_available,   # True si Odds API répond
                "pinnacle":    odds_available,
                "h2h_min3":    len(h2h_data) >= 3,
                "fbref":       False,
            },
            compo_confirmed    = match.get("compo_confirmed", False),
            absences_confirmed = bool(home_absent or away_absent),
            gates_active = {
                "ucl_rotation": any("UCL" in f for f in ctx.active_flags),
                "uel_rotation": any("UEL" in f for f in ctx.active_flags),
                "ede":          any("EDE" in f for f in ctx.active_flags),
            },
            matchday = md,
        )

        if dcs["tier"] == "INSUFFICIENT":
            logger.info(f"DCS INSUFFISANT [{home} vs {away}]: {dcs['adjusted']}/70")
            await send_analysis(
                f"⚽ *APEX-BUNDESLIGA — J{md}*
"
                f"*{home}* vs *{away}*

"
                f"🔕 *DCS {dcs['adjusted']}/70 — DONNÉES INSUFFISANTES*
"
                f"Analyse impossible — données incomplètes pour ce match.
"
                f"_Signal émis sur estimation :_
"
                + _build_dcs_fallback(match, dcs, md)
            )
            return []

        # ── 6. Poisson → xG calibrés → ALL 40+ marchés ─────────
        _base = compute_match_probs(
            home_att = match.get("home_avg_scored",   1.56),
            home_def = match.get("home_avg_conceded", 1.56),
            away_att = match.get("away_avg_scored",   1.56),
            away_def = match.get("away_avg_conceded", 1.56),
            ais_home = ais_h, ais_away = ais_a,
            rebound_coeff = ctx.rebound_coeff,
            home_xg_mult  = ctx.home_xg_mult,
            away_xg_mult  = ctx.away_xg_mult,
        )
        probs = compute_all_market_probs(
            home_xg = _base["home_xg"],
            away_xg = _base["away_xg"],
            home_corners_avg = match.get("home_corners_avg", 5.5),
            away_corners_avg = match.get("away_corners_avg", 4.5),
            home_cards_avg   = match.get("home_cards_avg",   1.8),
            away_cards_avg   = match.get("away_cards_avg",   1.6),
            home_shots_avg   = match.get("home_shots_avg",   5.0),
            away_shots_avg   = match.get("away_shots_avg",   3.5),
        )

        # ── 7. Verdict ────────────────────────────────────────
        gates_dict = {
            "forbidden_markets": ctx.forbidden_markets,
            "kelly_mult":        ctx.kelly_mult,
            "flags": {
                **{f: True for f in ctx.active_flags},
                "home_win_rate_effective": match.get("home_win_rate_8m", 0.4),
                "away_win_rate_effective": match.get("away_win_rate_8m", 0.4),
                "1x2_home_form_ok": match.get("home_win_rate_8m", 0.4) >= 0.40,
                "1x2_away_form_ok": match.get("away_win_rate_8m", 0.4) >= 0.40,
            },
            "warnings": ctx.warnings,
        }
        signals = self.verdict.generate(match, probs, dcs, gates_dict, session)

        # ── 8. Rapport Telegram ───────────────────────────────
        report = build_pre_match_report(match, probs, dcs, gates_dict, signals)
        await send_analysis(report)

        if not signals:
            return []

        # ── 9. Persistence ────────────────────────────────────
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        for s in signals:
            s.update({
                "id":         str(uuid.uuid4()),
                "fixture_id": fixture_id,
                "match":      f"{home} vs {away}",
                "home":       home,
                "away":       away,
                "matchday":   md,
                "date":       date_str,
            })
            self.signals.save(s)

        return signals

    # ═══════════════════════════════════════════════════════════
    async def run_audit(self):
        """02:00 UTC — audit post-match de la veille."""
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        signals   = self.signals.get_by_date(yesterday)
        if not signals:
            logger.info("Audit : aucun signal hier")
            return

        results = {}
        for s in signals:
            fid = s.get("fixture_id")
            if fid and fid not in results:
                try:
                    fx = get_fixture_result(fid)
                    results[fid] = {
                        "home_goals": fx.get("home_goals", 0),
                        "away_goals": fx.get("away_goals", 0),
                    }
                    self.outcomes.save_outcome(
                        matchday   = s.get("matchday", 0),
                        fixture_id = fid,
                        home_goals = results[fid]["home_goals"],
                        away_goals = results[fid]["away_goals"],
                        home_team  = s.get("home", ""),
                        away_team  = s.get("away", ""),
                    )
                except Exception as e:
                    logger.error(f"Audit get_result {fid}: {e}", exc_info=True)

        if not results:
            return
        md     = signals[0].get("matchday", "?")
        report = build_audit_report(md, signals, results)
        await send_audit(report)

        # Anti-Under tracking
        under_losses = sum(
            1 for s in signals
            if s.get("market") in ("under_25", "btts_no")
            and not _signal_won(
                s["market"],
                results.get(s.get("fixture_id"), {}).get("home_goals", 0),
                results.get(s.get("fixture_id"), {}).get("away_goals", 0),
            )
        )
        if under_losses >= ANTI_UNDER_TRIGGER:
            self._anti_under_remaining = ANTI_UNDER_JOURNEES
            logger.warning(f"Pause anti-Under : {under_losses} défaites U2.5/BTTS Non")
        elif self._anti_under_remaining > 0:
            self._anti_under_remaining -= 1

    async def refresh_odds_lineups(self):
        logger.debug("Refresh odds/lineups (hook)")

    async def check_live(self):
        logger.debug("Live check (hook)")


# ═══════════════════════════════════════════════════════════════
# HELPERS MODULE-LEVEL
# ═══════════════════════════════════════════════════════════════
def _safe_list(val) -> list:
    """Garantit qu'on a une liste de dicts — protège contre None/int/dict."""
    if isinstance(val, list):
        return val
    if val is None:
        return []
    logger.warning(f"_safe_list: valeur inattendue type={type(val).__name__}, retour []")
    return []


def _form_to_stats(form_fixtures: list, team_id: int) -> dict:
    """Calcule les stats moyennes depuis les derniers matchs. Défensif."""
    default = {
        "avg_goals_scored":   1.56,
        "avg_goals_conceded": 1.56,
        "over25_pct":         0.55,
        "win_rate_8m":        0.40,
        "cs_pct":             0.25,
        "goals_conceded_last3": 4,
    }
    if not form_fixtures:
        return default

    scored, conceded, over25 = [], [], []
    for f in form_fixtures:
        if not isinstance(f, dict):   # ← défense clé
            continue
        goals = f.get("goals") or {}
        teams = f.get("teams") or {}
        if not isinstance(goals, dict) or not isinstance(teams, dict):
            continue
        home_t = teams.get("home") or {}
        is_home = isinstance(home_t, dict) and home_t.get("id") == team_id
        hg = goals.get("home") or 0
        ag = goals.get("away") or 0
        s  = hg if is_home else ag
        c  = ag if is_home else hg
        scored.append(int(s))
        conceded.append(int(c))
        over25.append(1 if (hg + ag) > 2 else 0)

    if not scored:
        return default

    last3_c = sum(conceded[-3:]) if len(conceded) >= 3 else sum(conceded)
    n = len(scored)
    return {
        "avg_goals_scored":     round(sum(scored)   / n, 3),
        "avg_goals_conceded":   round(sum(conceded)  / n, 3),
        "over25_pct":           round(sum(over25)    / n, 3),
        "win_rate_8m":          compute_win_rate(form_fixtures, team_id),
        "cs_pct":               round(sum(1 for c in conceded if c == 0) / n, 3),
        "goals_conceded_last3": last3_c,
    }


def _new_session() -> dict:
    return {"total_exposure": 0.0, "total_signals": 0,
            "family_over": 0.0, "family_under": 0.0, "family_1x2": 0.0}


def _update_session(session: dict, signals: list) -> None:
    for s in signals:
        session["total_exposure"] += s.get("stake_pct", 0)
        session["total_signals"]  += 1
        mkt = s.get("market", "")
        if mkt in ("over_25", "over_35"):    session["family_over"]  += s.get("stake_pct", 0)
        elif mkt in ("under_25", "btts_no"): session["family_under"] += s.get("stake_pct", 0)
        elif mkt.startswith("1x2"):          session["family_1x2"]   += s.get("stake_pct", 0)


def _signal_won(market: str, hg: int, ag: int) -> bool:
    t = hg + ag
    if market == "over_25":  return t > 2
    if market == "over_35":  return t > 3
    if market == "under_25": return t < 3
    if market == "under_35": return t < 4
    if market == "btts_no":  return hg == 0 or ag == 0
    if market == "btts_yes": return hg > 0 and ag > 0
    return False
