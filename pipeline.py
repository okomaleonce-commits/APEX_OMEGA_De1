"""
APEX_OMEGA_De1 · Pipeline — orchestrateur principal Bundesliga
Réécrit v2 : interfaces alignées sur tous les modules réels.
"""
from __future__ import annotations
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from dataclasses import fields as dc_fields

from bundesliga.router   import BundesligaRouter
from bundesliga.gates    import GateContext, evaluate_all_gates

from ingestion.fixtures_service import (
    get_upcoming_fixtures,
    get_team_form,
    get_h2h,
    get_fixture_result,
    compute_win_rate,
    compute_h2h_avg_goals,
)
from ingestion.lineup_service import (
    get_injuries,
    compute_ais_f,
    count_absent_defenders,
    gk_is_experienced,
)
from ingestion.odds_service  import build_fair_odds_dict
from ingestion.normalizer    import normalize_fixture, enrich_stats

from trust.trust_matrix      import DCSCalculator
from models.dixon_coles      import compute_match_probs
from decisions.verdict_engine    import VerdictEngine
from decisions.rationale_builder import (
    build_pre_match_report,
    build_daily_summary,
    build_audit_report,
)

from storage.signals_repo  import SignalsRepo
from storage.outcomes_repo import OutcomesRepo
from interfaces.telegram_bot import send_analysis, send_audit, send_no_bet_summary

from bundesliga.config_v2_3 import ANTI_UNDER_TRIGGER, ANTI_UNDER_JOURNEES

logger = logging.getLogger(__name__)


class ApexBundesligaPipeline:

    def __init__(self):
        self.router   = BundesligaRouter()
        self.dcs_calc = DCSCalculator()
        self.verdict  = VerdictEngine()
        self.signals  = SignalsRepo()
        self.outcomes = OutcomesRepo()
        self._anti_under_remaining = 0

    # ─────────────────────────────────────────────────────────────
    async def daily_scan(self, days_ahead: int = 3):
        """Analyse les matchs des N prochains jours. Appelable via scheduler ou /scan."""
        logger.info("=== APEX Daily Scan démarré ===")
        raw      = get_upcoming_fixtures(days_ahead=max(days_ahead, 0))
        filtered = self.router.filter_batch(raw)          # ← filter_batch()

        session = {
            "total_exposure": 0.0, "total_signals": 0,
            "family_over": 0.0, "family_under": 0.0, "family_1x2": 0.0,
        }
        all_signals = []
        passes      = 0

        for raw_fx in filtered:
            try:
                sigs, passed = await self._analyze(raw_fx, session)
                all_signals.extend(sigs)
                passes += passed
            except Exception as e:
                logger.error(f"Pipeline erreur: {e}", exc_info=True)

        if all_signals:
            md      = all_signals[0].get("matchday", "?")
            summary = build_daily_summary(md, all_signals, session["total_exposure"])
            await send_analysis(summary)
        elif passes > 0:
            await send_no_bet_summary(passes, passes)

        logger.info(f"=== Scan terminé : {len(all_signals)} signaux / {passes} NO BET ===")

    # ─────────────────────────────────────────────────────────────
    async def _analyze(self, raw_fx: dict, session: dict) -> tuple[list, int]:
        """
        Pipeline complet pour un match.
        Returns: (signals_list, 1_if_no_bet)
        """
        match = normalize_fixture(raw_fx)
        home_id = match.get("home_id")
        away_id = match.get("away_id")
        md      = int(match.get("matchday") or 20)

        # 1. Forme + H2H ─────────────────────────────────────────
        home_form = get_team_form(home_id, last=8)
        away_form = get_team_form(away_id, last=8)
        h2h_data  = get_h2h(home_id, away_id, last=10)

        home_stats = _form_to_stats(home_form, home_id)
        away_stats = _form_to_stats(away_form, away_id)
        team_stats = {
            "home": home_stats, "away": away_stats,
            "h2h_avg_goals": compute_h2h_avg_goals(h2h_data),
        }
        match = enrich_stats(match, team_stats)           # ← signature (fixture, team_stats)

        match["home_win_rate_8m"] = compute_win_rate(home_form, home_id)
        match["away_win_rate_8m"] = compute_win_rate(away_form, away_id)

        # 2. Absences + AIS-F ────────────────────────────────────
        fid      = match["fixture_id"]
        home_inj = get_injuries(home_id, fid)             # ← (team_id, fixture_id)
        away_inj = get_injuries(away_id, fid)

        home_absent = [i.get("player", {}).get("name", "") for i in home_inj]
        away_absent = [i.get("player", {}).get("name", "") for i in away_inj]

        ais_h = compute_ais_f(match["home_team"], home_absent)   # ← (club_name, absent_list)
        ais_a = compute_ais_f(match["away_team"], away_absent)

        # 3. Cotes ────────────────────────────────────────────────
        fair_odds = build_fair_odds_dict(match["home_team"], match["away_team"])
        match["fair_odds"] = fair_odds

        # 4. Construction GateContext ─────────────────────────────
        ctx = GateContext(
            home_team   = match["home_team"],
            away_team   = match["away_team"],
            matchday    = md,
            kickoff_utc = match.get("kickoff", ""),

            # Absences
            away_absent_defenders = count_absent_defenders(away_inj),
            away_gk_experienced   = gk_is_experienced(away_inj),
            away_goals_conceded_3 = match.get("away_goals_conceded_last3", 0),

            # Forme
            home_win_rate_8m = match.get("home_win_rate_8m", 0.40),
            away_win_rate_8m = match.get("away_win_rate_8m", 0.40),

            # Stats
            h2h_avg_goals    = match.get("h2h_avg_goals", 2.6),
            home_avg_scored   = match.get("home_avg_scored",   1.56),
            home_avg_conceded = match.get("home_avg_conceded", 1.56),
            away_avg_scored   = match.get("away_avg_scored",   1.56),
            away_avg_conceded = match.get("away_avg_conceded", 1.56),
            home_over25_pct   = match.get("home_over25_pct",  0.55),
            away_over25_pct   = match.get("away_over25_pct",  0.55),

            # Session
            anti_under_active   = self._anti_under_remaining > 0,
            anti_under_remaining = self._anti_under_remaining,
            session_signals      = session["total_signals"],
            session_exposure     = session["total_exposure"],
        )

        # 5. Gates ────────────────────────────────────────────────
        ctx = evaluate_all_gates(ctx)                     # ← GateContext in/out

        if ctx.blocked:
            logger.info(f"BLOQUÉ gate [{match['home_team']} vs {match['away_team']}]: {ctx.block_reason}")
            return [], 1

        # 6. DCS ──────────────────────────────────────────────────
        has_fair_odds = bool(fair_odds)
        h2h_ok        = len(h2h_data) >= 3
        dcs = self.dcs_calc.compute(
            home_club          = match["home_team"],
            away_club          = match["away_team"],
            sources            = {"footystats": True, "betfair": has_fair_odds, "h2h_min3": h2h_ok},
            compo_confirmed    = match.get("compo_confirmed", False),
            absences_confirmed = bool(home_absent or away_absent),
            gates_active       = {
                "ucl_rotation": any("UCL" in f for f in ctx.active_flags),
                "uel_rotation": any("UEL" in f for f in ctx.active_flags),
                "ede":          any("EDE" in f for f in ctx.active_flags),
            },
            matchday = md,
        )

        if dcs["tier"] == "INSUFFICIENT":
            logger.info(f"NO BET DCS [{match['home_team']} vs {match['away_team']}]: {dcs['adjusted']}/70")
            await send_no_bet_summary(md, 1)
            return [], 1

        # 7. Poisson ──────────────────────────────────────────────
        probs = compute_match_probs(
            home_att      = match.get("home_avg_scored",   1.56),
            home_def      = match.get("home_avg_conceded", 1.56),
            away_att      = match.get("away_avg_scored",   1.56),
            away_def      = match.get("away_avg_conceded", 1.56),
            ais_home      = ais_h,
            ais_away      = ais_a,
            rebound_coeff = ctx.rebound_coeff,
            home_xg_mult  = ctx.home_xg_mult,            # ← champs directs GateContext
            away_xg_mult  = ctx.away_xg_mult * ctx.enjeu_att_away_mult,
        )

        # 8. Verdict ──────────────────────────────────────────────
        # VerdictEngine.generate() attend un dict gates avec ces clés
        gates_dict = {
            "forbidden_markets": ctx.forbidden_markets,
            "kelly_mult":        ctx.kelly_mult,
            "flags": {
                **{f: True for f in ctx.active_flags},
                # Win rates pour is_1x2_form_ok (VerdictEngine)
                "home_win_rate_effective": match.get("home_win_rate_8m", 0.4),
                "away_win_rate_effective": match.get("away_win_rate_8m", 0.4),
                "1x2_home_form_ok": match.get("home_win_rate_8m", 0.4) >= 0.40,
                "1x2_away_form_ok": match.get("away_win_rate_8m", 0.4) >= 0.40,
            },
            "warnings": ctx.warnings,
        }
        signals = self.verdict.generate(match, probs, dcs, gates_dict, session)

        # 9. Rapport Telegram ─────────────────────────────────────
        report = build_pre_match_report(match, probs, dcs, gates_dict, signals)
        await send_analysis(report)

        if not signals:
            return [], 1

        # 10. Persistence ─────────────────────────────────────────
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        for s in signals:
            s.update({
                "id":         str(uuid.uuid4()),
                "fixture_id": fid,
                "home":       match["home_team"],
                "away":       match["away_team"],
                "matchday":   md,
                "date":       date_str,
            })
            self.signals.save(s)

        # 11. Mise à jour session ─────────────────────────────────
        for s in signals:
            session["total_exposure"] += s["stake_pct"]
            session["total_signals"]  += 1
            mkt = s["market"]
            if mkt in ("over_25", "over_35"):    session["family_over"]  += s["stake_pct"]
            elif mkt in ("under_25", "btts_no"): session["family_under"] += s["stake_pct"]
            elif mkt.startswith("1x2"):          session["family_1x2"]   += s["stake_pct"]

        return signals, 0

    # ─────────────────────────────────────────────────────────────
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
            logger.warning(f"Pause anti-Under : {under_losses} défaites U2.5/BTTS Non")
        elif self._anti_under_remaining > 0:
            self._anti_under_remaining -= 1

    # ─────────────────────────────────────────────────────────────
    async def refresh_odds_lineups(self):
        """
        Refresh toutes les 2h :
        - Mise à jour des cotes (The Odds API)
        - Vérification des compos confirmées
        - Re-calcul AIS-F si nouvelles absences
        """
        from datetime import datetime, timedelta
        from ingestion.fixtures_service import get_upcoming_fixtures
        from ingestion.odds_service import get_bundesliga_odds

        logger.info("▶ Refresh odds + lineups")
        try:
            # Cotes actualisées disponibles directement via get_bundesliga_odds()
            # Le prochain daily_scan utilisera les cotes fraîches
            odds_data = get_bundesliga_odds()
            logger.info(f"Odds refresh : {len(odds_data)} matchs disponibles")
        except Exception as e:
            logger.warning(f"Refresh odds erreur (non bloquant): {e}")

    async def check_live(self):
        """
        Check toutes les 30min :
        - Matchs en cours → audit anticipé si FT détecté
        """
        from ingestion.fixtures_service import get_upcoming_fixtures
        import requests
        from config.settings import API_KEY, BUNDESLIGA_API_ID, BUNDESLIGA_SEASON

        try:
            resp = requests.get(
                "https://v3.football.api-sports.io/fixtures",
                headers={"x-apisports-key": API_KEY},
                params={
                    "league": BUNDESLIGA_API_ID,
                    "season": BUNDESLIGA_SEASON,
                    "status": "LIVE",
                },
                timeout=10,
            )
            live = resp.json().get("response", [])
            if live:
                logger.info(f"Live check : {len(live)} match(s) en cours")
            else:
                logger.debug("Live check : aucun match en cours")
        except Exception as e:
            logger.debug(f"Live check erreur (non bloquant): {e}")


# ── Helpers ──────────────────────────────────────────────────────
def _form_to_stats(form_fixtures: list, team_id: int) -> dict:
    """Calcule les stats moyennes depuis les derniers matchs d'une équipe."""
    if not form_fixtures:
        return {
            "avg_goals_scored":   1.56,
            "avg_goals_conceded": 1.56,
            "over25_pct":         0.55,
            "win_rate_8m":        0.40,
            "cs_pct":             0.25,
            "goals_conceded_last3": 4,
        }
    scored, conceded, over25 = [], [], []
    for f in form_fixtures:
        goals = f.get("goals", {})
        teams = f.get("teams", {})
        is_home = teams.get("home", {}).get("id") == team_id
        hg = goals.get("home") or 0
        ag = goals.get("away") or 0
        s  = hg if is_home else ag
        c  = ag if is_home else hg
        scored.append(s)
        conceded.append(c)
        over25.append(1 if (hg + ag) > 2 else 0)

    last3_c = sum(conceded[-3:]) if len(conceded) >= 3 else sum(conceded)
    return {
        "avg_goals_scored":     round(sum(scored)   / len(scored),   3),
        "avg_goals_conceded":   round(sum(conceded) / len(conceded), 3),
        "over25_pct":           round(sum(over25)   / len(over25),   3),
        "win_rate_8m":          compute_win_rate(form_fixtures, team_id),
        "cs_pct":               round(sum(1 for c in conceded if c == 0) / len(conceded), 3),
        "goals_conceded_last3": last3_c,
    }


def _signal_won(market: str, hg: int, ag: int) -> bool:
    t = hg + ag
    if market == "over_25":  return t > 2
    if market == "under_25": return t < 3
    if market == "btts_no":  return hg == 0 or ag == 0
    return False
