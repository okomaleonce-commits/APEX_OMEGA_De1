"""
APEX_OMEGA_De1 · Pipeline Principal
Orchestre toutes les étapes : ingestion → gates → modèle → verdict → Telegram
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta

from bundesliga.router import BundesligaRouter
from bundesliga.gates  import evaluate_all_gates
from bundesliga.config_v2_3 import ANTI_UNDER_TRIGGER_N, ANTI_UNDER_PAUSE_DAYS

from ingestion.fixtures_service import get_upcoming, get_result
from ingestion.lineup_service   import get_injuries, compute_ais_f
from ingestion.normalizer        import normalize_fixture

from trust.trust_matrix   import TrustMatrix
from models.dixon_coles   import compute_match_probs
from decisions.verdict_engine    import generate_signals
from decisions.rationale_builder import (
    build_match_report, build_daily_header,
    build_daily_summary, build_audit_report,
)
from storage.signals_repo    import SignalsRepo
from storage.calibration_repo import load_metrics, save_metrics
from interfaces.telegram_bot import send

logger = logging.getLogger(__name__)


class ApexBundesligaPipeline:

    def __init__(self):
        self.router  = BundesligaRouter()
        self.trust   = TrustMatrix()
        self.repo    = SignalsRepo()
        self._metrics = load_metrics()

    # ─── Propriétés anti-under ─────────────────────────────────
    @property
    def anti_under_active(self) -> bool:
        return self._metrics.get("anti_under_remaining", 0) > 0

    # ─── Ingestion fixtures ────────────────────────────────────
    async def ingest_fixtures(self):
        logger.info("Ingestion fixtures De1...")
        raw = get_upcoming(days=7)
        eligible = self.router.route([normalize_fixture(f) for f in raw])
        logger.info(f"Ingestion : {len(eligible)} matchs éligibles")

    # ─── Scan quotidien ────────────────────────────────────────
    async def daily_scan(self):
        logger.info("APEX Daily Scan De1")
        raw = get_upcoming(days=4)
        matches = self.router.route([normalize_fixture(f) for f in raw])
        if not matches:
            logger.info("Aucun match éligible")
            return

        matchday = matches[0].get("matchday", 0)
        await send(build_daily_header(matchday, len(matches)))

        session = {"total_exposure":0.0,"total_signals":0,
                   "fam_over":0.0,"fam_under":0.0,"fam_1x2":0.0,
                   "strong_rupture_today": False}
        all_signals = []

        for match in matches:
            sigs = await self._analyze_match(match, session)
            all_signals.extend(sigs)

        await send(build_daily_summary(all_signals, session))

    # ─── Analyse d'un match ────────────────────────────────────
    async def _analyze_match(self, match: dict, session: dict) -> list[dict]:
        home = match.get("home_team","?")
        away = match.get("away_team","?")
        matchday = match.get("matchday", 0)
        logger.info(f"Analyse : {home} vs {away} J{matchday}")

        try:
            # 1. Absences
            home_inj = get_injuries(match["home_id"], match["fixture_id"])
            away_inj = get_injuries(match["away_id"], match["fixture_id"])
            home_abs = [p.get("player",{}).get("name","") for p in home_inj]
            away_abs = [p.get("player",{}).get("name","") for p in away_inj]
            match["home_absent_players"] = home_abs
            match["away_absent_players"] = away_abs
            match["away_absent_defenders"] = sum(
                1 for p in away_inj
                if p.get("player",{}).get("type") in ("Defender","Centre-Back","Full-Back")
            )

            # 2. AIS-F → injecter dans match pour gate B-2
            ais_home = compute_ais_f(home, home_abs)
            ais_away = compute_ais_f(away, away_abs)
            match["ais_home"] = ais_home
            match["ais_away"] = ais_away

            # 3. Probabilités brutes (avant gates)
            probs_raw = compute_match_probs(
                match.get("home_avg_scored",   1.56),
                match.get("home_avg_conceded", 1.56),
                match.get("away_avg_scored",   1.56),
                match.get("away_avg_conceded", 1.56),
            )

            # 4. Gates
            gate_result = evaluate_all_gates(match, probs_raw, matchday,
                                             self.anti_under_active)
            gate_mods = gate_result["mods"]

            # 5. Probabilités finales (avec gates)
            probs = compute_match_probs(
                match.get("home_avg_scored",   1.56) * ais_home["att_mult"],
                match.get("home_avg_conceded", 1.56) * ais_away["def_mult"],
                match.get("away_avg_scored",   1.56) * ais_away["att_mult"],
                match.get("away_avg_conceded", 1.56) * ais_home["def_mult"],
                gate_mods,
            )

            # 6. DCS
            sources = {
                "fbref":        False,
                "footystats":   bool(match.get("home_avg_scored")),
                "soccer_rating":False,
                "betfair":      bool(match.get("fair_odds")),
                "pinnacle":     False,
                "h2h_min3":     True,
            }
            dcs = self.trust.compute(
                home_club=home, away_club=away,
                sources=sources,
                compo_confirmed=bool(match.get("home_absent_players")),
                absences_confirmed=bool(home_abs or away_abs),
                gate_mods=gate_mods,
                matchday=matchday,
            )

            # 7. Signaux
            signals = generate_signals(
                match=match, probs=probs,
                fair_odds=match.get("fair_odds", {}),
                dcs=dcs, gate_mods=gate_mods,
                matchday=matchday, session=session,
            )

            # 8. Rapport Telegram
            report = build_match_report(match, probs, dcs, gate_mods,
                                        signals, matchday, session)
            await send(report)

            # 9. Persistence + update session
            for s in signals:
                s["id"]        = str(uuid.uuid4())
                s["match"]     = f"{home} vs {away}"
                s["fixture_id"]= match.get("fixture_id")
                s["date"]      = datetime.utcnow().strftime("%Y-%m-%d")
                s["matchday"]  = matchday
                self.repo.save(s)
                session["total_exposure"]  += s["stake_pct"]
                session["total_signals"]   += 1
                if s["market"] in ("over_25","over_35"):
                    session["fam_over"]  += s["stake_pct"]
                elif s["market"] in ("under_25","btts_no"):
                    session["fam_under"] += s["stake_pct"]
                elif s["market"].startswith("1x2") or s["market"].startswith("dnb"):
                    session["fam_1x2"]   += s["stake_pct"]
                if s["verdict"] == "STRONG_RUPTURE":
                    session["strong_rupture_today"] = True

            return signals

        except Exception as e:
            logger.error(f"Erreur analyse {home}-{away}: {e}", exc_info=True)
            return []

    # ─── Run analysis (appelé par scheduler) ───────────────────
    async def run_analysis(self):
        await self.daily_scan()

    # ─── Refresh cotes ─────────────────────────────────────────
    async def refresh_odds(self):
        logger.info("Refresh odds De1 — placeholder")

    # ─── Audit post-match ──────────────────────────────────────
    async def post_match_audit(self):
        yesterday = (datetime.utcnow()-timedelta(days=1)).strftime("%Y-%m-%d")
        signals   = self.repo.get_by_date(yesterday)
        under_losses = sum(
            1 for s in signals
            if s.get("market") in ("under_25","btts_no")
            and s.get("result",{}).get("won") is False
        )
        m = self._metrics
        if under_losses >= ANTI_UNDER_TRIGGER_N:
            m["anti_under_count"]     += 1
            m["anti_under_remaining"] = ANTI_UNDER_PAUSE_DAYS
            logger.warning(f"Pause anti-Under déclenchée ({under_losses} défaites)")
        elif m.get("anti_under_remaining",0) > 0:
            m["anti_under_remaining"] -= 1
        save_metrics(m)

    # ─── Audit hebdomadaire ────────────────────────────────────
    async def weekly_audit(self):
        logger.info("Audit hebdomadaire De1")
        m = load_metrics()
        if m["total_signals"] > 0:
            wr = m["wins"] / m["total_signals"]
            msg = (f"📊 *AUDIT HEBDO APEX‑De1*\n"
                   f"  Signaux : {m['total_signals']}\n"
                   f"  Wins    : {m['wins']} ({wr:.1%})\n"
                   f"  P&L     : {m['pl_total']:+.2%}")
            await send(msg)
