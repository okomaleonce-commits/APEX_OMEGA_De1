"""
APEX_OMEGA_De1 · Pipeline — orchestrateur principal Bundesliga
"""
from __future__ import annotations
import asyncio
import logging
import uuid
from datetime import datetime, timedelta

from bundesliga.router     import BundesligaRouter
from bundesliga.gates      import evaluate_all_gates

from ingestion.fixtures_service import (
    get_upcoming_fixtures, get_team_form,
    get_h2h, get_fixture_result,
    compute_win_rate, compute_h2h_avg_goals,
)
from ingestion.lineup_service   import (
    get_injuries, compute_ais_f,
    count_absent_defenders, gk_is_experienced,
)
from ingestion.odds_service     import build_fair_odds_dict
from ingestion.normalizer       import normalize_fixture, enrich_stats

from trust.trust_matrix         import DCSCalculator
from models.dixon_coles         import compute_match_probs
from decisions.verdict_engine   import VerdictEngine
from decisions.rationale_builder import (
    build_pre_match_report, build_daily_summary, build_audit_report,
)

from storage.signals_repo  import SignalsRepo
from storage.outcomes_repo import OutcomesRepo
from interfaces.telegram_bot import send_analysis, send_audit, send_no_bet_summary

from bundesliga.config_v2_3 import (
    ANTI_UNDER_TRIGGER, ANTI_UNDER_JOURNEES,
)

logger = logging.getLogger(__name__)


class ApexBundesligaPipeline:

    def __init__(self):
        self.router    = BundesligaRouter()
        self.dcs_calc  = DCSCalculator()
        self.verdict   = VerdictEngine()
        self.signals   = SignalsRepo()
        self.outcomes  = OutcomesRepo()
        self._anti_under_count     = 0
        self._anti_under_remaining = 0

    # ─────────────────────────────────────────────
    async def daily_scan(self):
        """07:00 UTC — analyse les matchs des 3 prochains jours."""
        logger.info("=== APEX Daily Scan ===")
        raw      = get_upcoming_fixtures(days_ahead=3)
        filtered = self.router.filter_fixtures(raw)

        session = {
            "total_exposure": 0.0, "total_signals": 0,
            "family_over": 0.0, "family_under": 0.0, "family_1x2": 0.0,
            "has_strong_rupture": False,
        }
        all_signals = []

        for raw_fx in filtered:
            try:
                sigs = await self._analyze(raw_fx, session)
                all_signals.extend(sigs)
            except Exception as e:
                logger.error(f"Pipeline error: {e}", exc_info=True)

        if all_signals:
            summary = build_daily_summary(
                matchday=all_signals[0].get("matchday", "?"),
                all_signals=all_signals,
                total_exp=session["total_exposure"],
            )
            await send_analysis(summary)

        logger.info(f"=== Scan terminé : {len(all_signals)} signaux ===")

    # ─────────────────────────────────────────────
    async def _analyze(self, raw_fx: dict, session: dict) -> list[dict]:
        match = normalize_fixture(raw_fx)
        if not self.router.is_valid_match(match):
            return []

        home_id = match["home_id"]
        away_id = match["away_id"]
        md      = int(match.get("matchday") or 20)

        # 1. Forme + H2H
        home_form = get_team_form(home_id, last=8)
        away_form = get_team_form(away_id, last=8)
        h2h_data  = get_h2h(home_id, away_id, last=10)
        match = enrich_stats(match, home_form, away_form, home_id, away_id)
        match["h2h_avg_goals"] = compute_h2h_avg_goals(h2h_data)
        match["home_win_rate_8m"] = compute_win_rate(home_form, home_id)
        match["away_win_rate_8m"] = compute_win_rate(away_form, away_id)

        # 2. Absences + AIS-F
        home_inj = get_injuries(match["fixture_id"])
        away_inj = get_injuries(match["fixture_id"])

        home_absent = [i.get("player", {}).get("name", "") for i in home_inj]
        away_absent = [i.get("player", {}).get("name", "") for i in away_inj]

        ais_h = compute_ais_f(match["home_team"], home_absent)
        ais_a = compute_ais_f(match["away_team"], away_absent)

        match.update({
            "ais_home_att_mult": ais_h["att_mult"],
            "ais_home_def_mult": ais_h["def_mult"],
            "ais_away_att_mult": ais_a["att_mult"],
            "ais_away_def_mult": ais_a["def_mult"],
            "away_absent_defenders": count_absent_defenders(away_inj),
            "away_gk_experienced":   gk_is_experienced(away_inj),
            "anti_under_active":     self._anti_under_remaining > 0,
            "anti_under_remaining":  self._anti_under_remaining,
        })

        # 3. Gates
        gate_result = evaluate_all_gates(match)

        # 4. DCS
        dcs = self.dcs_calc.compute(
            home_club=match["home_team"],
            away_club=match["away_team"],
            sources={"footystats": True, "betfair": bool(match.get("fair_odds")),
                     "h2h_min3": len(h2h_data) >= 3},
            compo_confirmed=match.get("compo_confirmed", False),
            absences_confirmed=bool(home_absent or away_absent),
            gates_active={
                "ucl_rotation": "B-1:UCL_HOME" in gate_result["gates_active"],
                "uel_rotation": "B-1:UEL_HOME" in gate_result["gates_active"]
                                or "B-1:UEL_AWAY" in gate_result["gates_active"],
                "ede": any("B-3:EDE" in g for g in gate_result["gates_active"]),
            },
            matchday=md,
        )
        dcs["adjusted"] += gate_result.get("dcs_seasonal_adj", 0)

        if dcs["tier"] == "INSUFFICIENT":
            logger.info(f"NO BET DCS [{match['home_team']} vs {match['away_team']}]: {dcs['adjusted']}/70")
            await send_no_bet_summary(
                match["home_team"], match["away_team"], md,
                f"DCS insuffisant ({dcs['adjusted']}/70)",
            )
            return []

        # 5. Poisson
        probs = compute_match_probs(
            home_att=match.get("home_avg_scored") or 1.56,
            home_def=match.get("home_avg_conceded") or 1.56,
            away_att=match.get("away_avg_scored") or 1.56,
            away_def=match.get("away_avg_conceded") or 1.56,
            gate_mods={
                "home_xg_mult":  gate_result["home_xg_mult"],
                "away_xg_mult":  gate_result["away_xg_mult"],
                "rebound_coeff": gate_result["rebound_coeff"],
                "flags":         gate_result["flags"],
            },
        )

        # 6. Signaux
        signals = self.verdict.generate(match, probs, dcs, gate_result, session)

        # 7. Rapport Telegram
        gate_for_report = {
            "warnings":         gate_result["warnings"],
            "flags":            gate_result["flags"],
            "gates_active":     gate_result["gates_active"],
            "forbidden_markets": gate_result["forbidden_markets"],
            "kelly_mult":       gate_result["kelly_mult"],
        }
        report = build_pre_match_report(match, probs, dcs, gate_for_report, signals)
        await send_analysis(report)

        # 8. Persistence
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        for s in signals:
            s.update({
                "id":          str(uuid.uuid4()),
                "fixture_id":  match["fixture_id"],
                "home":        match["home_team"],
                "away":        match["away_team"],
                "matchday":    md,
                "date":        date_str,
            })
            self.signals.save(s)

        # 9. Update session
        for s in signals:
            session["total_exposure"] += s["stake_pct"]
            session["total_signals"]  += 1
            if s.get("verdict") == "STRONG_RUPTURE":
                session["has_strong_rupture"] = True
            mkt = s["market"]
            if mkt in ("over_25", "over_35"):  session["family_over"]  += s["stake_pct"]
            elif mkt in ("under_25", "btts_no"): session["family_under"] += s["stake_pct"]
            elif mkt.startswith("1x2"):          session["family_1x2"]   += s["stake_pct"]

        return signals

    # ─────────────────────────────────────────────
    async def run_audit(self):
        """02:00 UTC — audit des matchs de la veille."""
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        signals   = self.signals.get_by_date(yesterday)
        if not signals:
            logger.info("Audit : aucun signal hier")
            return

        # Récupérer les scores réels
        results = {}
        for s in signals:
            fid = s.get("fixture_id")
            if fid and fid not in results:
                fx = get_fixture_result(fid)
                g  = fx.get("goals", {}) if fx else {}
                results[fid] = {
                    "home_goals": g.get("home") or 0,
                    "away_goals": g.get("away") or 0,
                }
                self.outcomes.save_outcome(
                    matchday=s.get("matchday", 0),
                    fixture_id=fid,
                    home_goals=results[fid]["home_goals"],
                    away_goals=results[fid]["away_goals"],
                    home_team=s.get("home", ""),
                    away_team=s.get("away", ""),
                )

        # Rapport audit
        md      = signals[0].get("matchday", "?")
        report  = build_audit_report(md, signals, results)
        await send_audit(report)

        # Mise à jour anti-Under
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
            logger.warning(f"Pause anti-Under déclenchée ({under_losses} défaites U2.5/BTTS Non)")

        elif self._anti_under_remaining > 0:
            self._anti_under_remaining -= 1

    async def refresh_odds_lineups(self):
        """Refresh cotes + compos toutes les 2h."""
        logger.debug("Refresh odds/lineups — hook à implémenter avec Betfair")

    async def check_live(self):
        """Check matchs en direct toutes les 30min."""
        logger.debug("Live check — hook à implémenter")


def _signal_won(market: str, hg: int, ag: int) -> bool:
    t = hg + ag
    if market == "over_25":  return t > 2
    if market == "under_25": return t < 3
    if market == "btts_no":  return hg == 0 or ag == 0
    return False
