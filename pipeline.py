"""
APEX_OMEGA_De1 · Pipeline Bundesliga — orchestrateur principal
Version alignée sur les signatures réelles de tous les modules.
"""
from __future__ import annotations
import asyncio
import logging
import uuid
from datetime import datetime, timedelta

from bundesliga.router      import BundesligaRouter
from bundesliga.gates       import GateContext, run_all_gates as evaluate_all_gates
from bundesliga.config_v2_3 import (
    ANTI_UNDER_TRIGGER, ANTI_UNDER_JOURNEES, CLUBS,
)

from ingestion.fixtures_service import (
    get_upcoming_fixtures, get_team_form,
    get_h2h, get_fixture_result,
    compute_win_rate, compute_h2h_avg_goals,
)
from ingestion.lineup_service import (
    get_injuries, compute_ais_f,
    count_absent_defenders, gk_is_experienced,
)
from ingestion.odds_service  import build_fair_odds_dict
from ingestion.normalizer    import normalize_fixture, enrich_stats

from trust.trust_matrix      import DCSCalculator
from models.dixon_coles      import compute_match_probs
from decisions.verdict_engine import VerdictEngine
from decisions.rationale_builder import (
    build_pre_match_report, build_daily_summary, build_audit_report,
)
from storage.signals_repo    import SignalsRepo
from storage.outcomes_repo   import OutcomesRepo
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
        raw      = get_upcoming_fixtures(days_ahead=3)
        filtered = self.router.filter_batch(raw)           # ← filter_batch

        session = {
            "total_exposure": 0.0, "total_signals": 0,
            "family_over": 0.0, "family_under": 0.0, "family_1x2": 0.0,
        }
        all_signals = []
        passes      = 0

        for raw_fx in filtered:
            try:
                sigs = await self._analyze(raw_fx, session)
                if sigs:
                    all_signals.extend(sigs)
                else:
                    passes += 1
            except Exception as e:
                logger.error(f"Pipeline error: {e}", exc_info=True)

        if all_signals:
            md = all_signals[0].get("matchday", "?")
            summary = build_daily_summary(
                matchday=md,
                all_signals=all_signals,
                total_exp=session["total_exposure"],
            )
            await send_analysis(summary)
        else:
            await send_no_bet_summary(matchday="?", passes=passes)

        logger.info(f"=== Scan terminé : {len(all_signals)} signaux · {passes} NO BET ===")

    # ═══════════════════════════════════════════════════════════
    async def _analyze(self, raw_fx: dict, session: dict) -> list[dict]:
        """Pipeline complet pour un match."""

        # ── 0. Normalisation + filtre router
        match = normalize_fixture(raw_fx)
        if not self.router.route(match):               # ← route() retourne None si hors BL
            return []

        home      = match["home_team"]
        away      = match["away_team"]
        home_id   = match["home_id"]
        away_id   = match["away_id"]
        fixture_id = match["fixture_id"]
        md        = int(match.get("matchday") or 20)

        # ── 1. Forme + H2H + stats
        home_form = get_team_form(home_id, last=8)
        away_form = get_team_form(away_id, last=8)
        h2h_data  = get_h2h(home_id, away_id, last=10)

        team_stats = {
            "home": _extract_team_stats(home_form, home_id),
            "away": _extract_team_stats(away_form, away_id),
            "h2h_avg_goals": compute_h2h_avg_goals(h2h_data),
        }
        match = enrich_stats(match, team_stats)          # ← signature (match, team_stats_dict)
        match["home_win_rate_8m"] = compute_win_rate(home_form, home_id)
        match["away_win_rate_8m"] = compute_win_rate(away_form, away_id)

        # ── 2. Absences + AIS-F
        home_inj = get_injuries(home_id, fixture_id)    # ← team_id + fixture_id
        away_inj = get_injuries(away_id, fixture_id)

        home_absent = [i.get("player", {}).get("name", "") for i in home_inj]
        away_absent = [i.get("player", {}).get("name", "") for i in away_inj]

        ais_h = compute_ais_f(home, home_absent, CLUBS)  # ← 3 args
        ais_a = compute_ais_f(away, away_absent, CLUBS)

        # ── 3. Cotes marché
        fair_odds = build_fair_odds_dict(home, away)
        match["fair_odds"] = fair_odds

        # ── 4. Construct GateContext + évaluation des gates
        ctx = GateContext(
            home_team=home,
            away_team=away,
            matchday=md,
            kickoff_utc=match.get("kickoff", ""),
            # absences
            away_absent_defenders=count_absent_defenders(away_inj),
            away_gk_experienced=gk_is_experienced(away_inj),
            away_goals_conceded_3=match.get("away_goals_conceded_last3", 0),
            # forme
            home_win_rate_8m=match.get("home_win_rate_8m", 0.4),
            away_win_rate_8m=match.get("away_win_rate_8m", 0.4),
            # stats
            home_avg_scored=match.get("home_avg_scored", 1.56),
            home_avg_conceded=match.get("home_avg_conceded", 1.56),
            away_avg_scored=match.get("away_avg_scored", 1.56),
            away_avg_conceded=match.get("away_avg_conceded", 1.56),
            home_over25_pct=match.get("home_over25_pct", 0.55),
            away_over25_pct=match.get("away_over25_pct", 0.55),
            h2h_avg_goals=match.get("h2h_avg_goals", 2.6),
            # session
            anti_under_active=self._anti_under_remaining > 0,
            anti_under_remaining=self._anti_under_remaining,
            session_signals=session["total_signals"],
            session_exposure=session["total_exposure"],
        )
        ctx = evaluate_all_gates(ctx)                    # ← GateContext → GateContext

        if ctx.blocked:
            logger.info(f"Gate BLOCKED [{home} vs {away}]: {ctx.block_reason}")
            return []

        # ── 5. DCS
        dcs = self.dcs_calc.compute(
            home_club=home,
            away_club=away,
            sources={
                "footystats":  True,
                "betfair":     bool(fair_odds.get("1x2_home_fair")),
                "pinnacle":    bool(fair_odds.get("1x2_home_fair")),  # via The Odds API
                "h2h_min3":    len(h2h_data) >= 3,
                "fbref":       False,
            },
            compo_confirmed=match.get("compo_confirmed", False),
            absences_confirmed=bool(home_absent or away_absent),
            gates_active={
                "ucl_rotation": any("UCL" in f for f in ctx.active_flags),
                "uel_rotation": any("UEL" in f for f in ctx.active_flags),
                "ede":          any("EDE" in f for f in ctx.active_flags),
            },
            matchday=md,
        )

        if dcs["tier"] == "INSUFFICIENT":
            logger.info(f"NO BET DCS [{home} vs {away}]: {dcs['adjusted']}/70")
            return []

        # ── 6. Poisson Dixon-Coles
        probs = compute_match_probs(
            home_att=match.get("home_avg_scored", 1.56),
            home_def=match.get("home_avg_conceded", 1.56),
            away_att=match.get("away_avg_scored", 1.56),
            away_def=match.get("away_avg_conceded", 1.56),
            ais_home=ais_h,
            ais_away=ais_a,
            rebound_coeff=ctx.rebound_coeff,
            home_xg_mult=ctx.home_xg_mult,
            away_xg_mult=ctx.away_xg_mult,
        )

        # ── 7. Verdict — gate_dict aligné sur VerdictEngine.generate()
        gate_dict = {
            "forbidden_markets": ctx.forbidden_markets,
            "kelly_mult":        ctx.kelly_mult,
            "flags":             {f: True for f in ctx.active_flags},
            "warnings":          ctx.warnings,
        }
        signals = self.verdict.generate(match, probs, dcs, gate_dict, session)

        # ── 8. Rapport Telegram (toujours envoyé, même NO BET pour ce match)
        report = build_pre_match_report(match, probs, dcs, gate_dict, signals)
        await send_analysis(report)

        if not signals:
            return []

        # ── 9. Persistence
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        for s in signals:
            s.update({
                "id":         str(uuid.uuid4()),
                "fixture_id": fixture_id,
                "match":      f"{home} vs {away}",
                "matchday":   md,
                "date":       date_str,
            })
            self.signals.save(s)

        # ── 10. Update session caps
        for s in signals:
            session["total_exposure"] += s["stake_pct"]
            session["total_signals"]  += 1
            mkt = s["market"]
            if mkt in ("over_25", "over_35"):    session["family_over"]  += s["stake_pct"]
            elif mkt in ("under_25", "btts_no"): session["family_under"] += s["stake_pct"]
            elif mkt.startswith("1x2"):          session["family_1x2"]   += s["stake_pct"]

        return signals

    # ═══════════════════════════════════════════════════════════
    async def run_audit(self):
        """02:00 UTC — audit matchs de la veille."""
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        signals   = self.signals.by_date(yesterday)       # ← by_date

        if not signals:
            logger.info("Audit : aucun signal hier")
            return

        results = {}
        for s in signals:
            fid = s.get("fixture_id")
            if fid and fid not in results:
                fx = get_fixture_result(fid)
                results[fid] = {
                    "home_goals": fx.get("home_goals", 0),
                    "away_goals": fx.get("away_goals", 0),
                }
                self.outcomes.save_outcome(
                    matchday=s.get("matchday", 0),
                    fixture_id=fid,
                    home_goals=results[fid]["home_goals"],
                    away_goals=results[fid]["away_goals"],
                    home_team=s.get("match", "").split(" vs ")[0],
                    away_team=s.get("match", "").split(" vs ")[-1],
                )

        md     = signals[0].get("matchday", "?")
        report = build_audit_report(md, signals, results)
        await send_audit(report)

        # Anti-Under tracking
        under_losses = sum(
            1 for s in signals
            if s.get("market") in ("under_25", "btts_no")
            and not _signal_won(
                s["market"],
                results.get(s["fixture_id"], {}).get("home_goals", 0),
                results.get(s["fixture_id"], {}).get("away_goals", 0),
            )
        )
        if under_losses >= ANTI_UNDER_TRIGGER:
            self._anti_under_remaining = ANTI_UNDER_JOURNEES
            logger.warning(f"Pause anti-Under: {under_losses} défaites consécutives")
        elif self._anti_under_remaining > 0:
            self._anti_under_remaining -= 1

    async def refresh_odds_lineups(self):
        logger.debug("Refresh odds/lineups (hook)")

    async def check_live(self):
        logger.debug("Live check (hook)")


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════
def _extract_team_stats(fixtures: list, team_id: int) -> dict:
    """Extrait avg_scored, avg_conceded, over25_pct, cs_pct d'une liste de fixtures."""
    if not fixtures:
        return {}
    scored, conceded, over25, cs = [], [], 0, 0
    for f in fixtures:
        teams = f.get("teams", {})
        goals = f.get("goals", {})
        is_home = teams.get("home", {}).get("id") == team_id
        if is_home:
            gf = goals.get("home") or 0
            ga = goals.get("away") or 0
        else:
            gf = goals.get("away") or 0
            ga = goals.get("home") or 0
        scored.append(gf)
        conceded.append(ga)
        if gf + ga > 2: over25 += 1
        if ga == 0:     cs += 1
    n = len(fixtures)
    return {
        "avg_goals_scored":   round(sum(scored)   / n, 2),
        "avg_goals_conceded": round(sum(conceded)  / n, 2),
        "over25_pct":         round(over25 / n,       2),
        "cs_pct":             round(cs    / n,         2),
        "win_rate_8m":        0.40,  # calculé séparément via compute_win_rate
    }


def _signal_won(market: str, hg: int, ag: int) -> bool:
    t = hg + ag
    if market == "over_25":  return t > 2
    if market == "over_35":  return t > 3
    if market == "under_25": return t < 3
    if market == "under_35": return t < 4
    if market == "btts_no":  return hg == 0 or ag == 0
    if market == "btts_yes": return hg > 0 and ag > 0
    return False
