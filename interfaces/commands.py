"""
APEX_OMEGA_De1 · Commandes Telegram — HTML uniquement
/scan today | 24h | Nh | week | month | next | status | help
"""
from __future__ import annotations
import asyncio
import logging
import re
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

from config.settings import BOT_TOKEN, CHAT_ID

logger = logging.getLogger(__name__)
_pipeline = None

def set_pipeline(pipeline) -> None:
    global _pipeline
    _pipeline = pipeline


# ═══════════════════════════════════════════════════════════════
# DISPATCHER /scan
# ═══════════════════════════════════════════════════════════════
async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _pipeline:
        await _reply(update, "❌ Pipeline non initialisé.")
        return

    args = " ".join(ctx.args).strip().lower() if ctx.args else "today"

    await _reply(update, f"🔍 <b>Scan lancé</b> : <code>{h(args)}</code> — analyse en cours...")

    try:
        if args == "today":
            await _run_scan(update, days=_days_until_midnight(), label="aujourd'hui")

        elif args == "24h":
            await _run_scan(update, days=1, label="24 prochaines heures")

        elif args in ("week", "semaine"):
            await _run_scan(update, days=7, label="7 prochains jours")

        elif args in ("month", "mois"):
            await _run_scan(update, days=30, label="30 prochains jours")

        elif args in ("next", "next matchs", "prochains"):
            await _scan_next(update)

        elif args == "status":
            await _scan_status(update)

        elif args == "help":
            await _scan_help(update)

        elif re.match(r"^\d+h$", args):
            n = int(args[:-1])
            days = max(0.5, n / 24)
            await _run_scan(update, days=days, label=f"{n} prochaines heures")

        else:
            await _reply(update,
                "❓ Argument non reconnu.\n"
                "Utilise <code>/scan help</code> pour la liste des commandes."
            )

    except Exception as e:
        logger.error(f"Erreur /scan {args}: {e}", exc_info=True)
        await _reply(update, f"❌ Erreur : <code>{h(str(e))}</code>")


# ═══════════════════════════════════════════════════════════════
# SCAN FENÊTRE TEMPORELLE
# ═══════════════════════════════════════════════════════════════
async def _run_scan(update: Update, days: float, label: str) -> None:
    from ingestion.fixtures_service import get_upcoming_fixtures_robust as get_upcoming_fixtures

    raw      = get_upcoming_fixtures(days_ahead=int(days) + 1)
    filtered = _pipeline.router.filter_batch(raw)

    now    = datetime.utcnow()
    cutoff = now + timedelta(days=days)
    in_window = []
    for fx in filtered:
        ko_str = fx.get("fixture", {}).get("date", "")
        try:
            ko = datetime.fromisoformat(ko_str.replace("Z", "")).replace(tzinfo=None)
            if now <= ko <= cutoff:
                in_window.append(fx)
        except Exception:
            in_window.append(fx)

    if not in_window:
        await _reply(update, f"📭 <b>Aucun match Bundesliga</b> pour : {h(label)}.")
        return

    await _reply(update,
        f"⚽ <b>{len(in_window)} match(s)</b> trouvé(s) — {h(label)}\n"
        f"<i>Analyse en cours...</i>"
    )

    session = {"total_exposure": 0.0, "total_signals": 0,
               "family_over": 0.0, "family_under": 0.0, "family_1x2": 0.0}
    all_signals, passes = [], 0

    for raw_fx in in_window:
        try:
            sigs = await _pipeline._analyze(raw_fx, session)
            if sigs:
                all_signals.extend(sigs)
            else:
                passes += 1
        except Exception as e:
            logger.error(f"Analyse échouée: {e}")
            passes += 1

    total_exp = sum(s.get("stake_pct", 0) for s in all_signals)  # recalcul réel
    await _reply(update,
        f"✅ <b>Scan terminé — {h(label)}</b>\n\n"
        f"📊 Matchs analysés : <b>{len(in_window)}</b>\n"
        f"💡 Signaux retenus : <b>{len(all_signals)}</b>\n"
        f"🚫 NO BET : <b>{passes}</b>\n"
        f"💰 Exposition totale : <b>{total_exp:.1%}</b>"
    )


# ═══════════════════════════════════════════════════════════════
# SCAN NEXT 5 MATCHS
# ═══════════════════════════════════════════════════════════════
async def _scan_next(update: Update) -> None:
    from ingestion.fixtures_service import get_upcoming_fixtures_robust as get_upcoming_fixtures

    raw      = get_upcoming_fixtures(days_ahead=14)
    filtered = _pipeline.router.filter_batch(raw)

    if not filtered:
        await _reply(update, "📭 Aucun prochain match Bundesliga sur 14 jours.")
        return

    filtered.sort(key=lambda fx: fx.get("fixture", {}).get("date", "9999"))
    next5 = filtered[:5]

    lines = ["⚽ <b>5 PROCHAINS MATCHS BUNDESLIGA</b>", ""]
    for fx in next5:
        f   = fx.get("fixture", {})
        hm  = h(fx.get("teams", {}).get("home", {}).get("name", "?"))
        aw  = h(fx.get("teams", {}).get("away", {}).get("name", "?"))
        ko  = h(f.get("date", "")[:16].replace("T", " "))
        rnd = h(fx.get("league", {}).get("round", "").replace("Regular Season - ", "J"))
        lines.append(f"  🏟️ <b>{hm}</b> vs <b>{aw}</b> · {ko} UTC · {rnd}")

    await _reply(update, "\n".join(lines))
    await _reply(update, "<i>Lancement analyse des 5 matchs...</i>")

    session = {"total_exposure": 0.0, "total_signals": 0,
               "family_over": 0.0, "family_under": 0.0, "family_1x2": 0.0}
    all_sigs = []
    for raw_fx in next5:
        try:
            sigs = await _pipeline._analyze(raw_fx, session)
            all_sigs.extend(sigs or [])
        except Exception as e:
            logger.error(f"Analyse next: {e}")

    await _reply(update,
        f"✅ <b>Analyse terminée</b> : "
        f"<b>{len(all_sigs)}</b> signal(s) sur {len(next5)} matchs"
    )


# ═══════════════════════════════════════════════════════════════
# STATUS SESSION
# ═══════════════════════════════════════════════════════════════
async def _scan_status(update: Update) -> None:
    from storage.signals_repo import SignalsRepo
    repo      = SignalsRepo()
    today     = repo.get_today()
    total_exp = sum(s.get("stake_pct", 0) for s in today)
    anti_under = getattr(_pipeline, "_anti_under_remaining", 0)
    date_str  = datetime.utcnow().strftime("%d/%m/%Y")

    if not today:
        await _reply(update,
            f"📊 <b>STATUS APEX — {date_str}</b>\n\n"
            f"Aucun signal joué aujourd'hui.\n"
            f"<i>Prochain scan auto : 07:00 UTC</i>"
        )
        return

    lines = [
        f"📊 <b>STATUS APEX — {date_str}</b>", "",
        f"Signaux joués  : <b>{len(today)}</b> / 4 max",
        f"Exposition     : <b>{total_exp:.1%}</b> / 12% max",
        f"Anti-Under     : <b>{'🔴 ACTIF' if anti_under > 0 else '🟢 OFF'}</b>",
        "",
        "<b>Détail signaux :</b>",
    ]
    for s in today:
        market = MARKET_LABELS.get(s.get("market", ""), s.get("market", "?").upper())
        match  = h(s.get("match", "?"))
        odd    = s.get("fair_odd", 0)
        stake  = s.get("stake_pct", 0)
        result = s.get("result")
        icon   = ("✅" if result.get("won") else "❌") if result else "⏳"
        lines.append(f"  {icon} {match} — {market} @ <code>{odd:.2f}</code> ({stake:.1%})")

    await _reply(update, "\n".join(lines))

MARKET_LABELS = {
    "over_25": "⚽ OVER 2.5", "over_35": "🔥 OVER 3.5",
    "under_25": "🔒 UNDER 2.5", "under_35": "🛡️ UNDER 3.5",
    "btts_yes": "✅ BTTS OUI", "btts_no": "🚫 BTTS NON",
    "1x2_fav":  "🏆 1X2 FAV.", "1x2_out": "⚡ 1X2 OUTSIDER",
}

# ═══════════════════════════════════════════════════════════════
# AIDE
# ═══════════════════════════════════════════════════════════════
async def _scan_help(update: Update) -> None:
    await _reply(update,
        "📖 <b>APEX-OMEGA BUNDESLIGA — Commandes /scan</b>\n\n"
        "<code>/scan today</code>    — matchs d'aujourd'hui\n"
        "<code>/scan 24h</code>      — matchs dans les 24h\n"
        "<code>/scan 48h</code>      — matchs dans les 48h (Nh = N heures)\n"
        "<code>/scan week</code>     — matchs des 7 prochains jours\n"
        "<code>/scan month</code>    — matchs des 30 prochains jours\n"
        "<code>/scan next</code>     — 5 prochains matchs BL + analyse\n"
        "<code>/scan status</code>   — état session du jour\n"
        "<code>/scan help</code>     — cette aide\n\n"
        "<i>Scan automatique : 07:00 UTC · Audit : 02:00 UTC</i>"
    )


# ═══════════════════════════════════════════════════════════════
# UTILS
# ═══════════════════════════════════════════════════════════════
def _days_until_midnight() -> float:
    now = datetime.utcnow()
    midnight = now.replace(hour=23, minute=59, second=59)
    return max(0.1, (midnight - now).total_seconds() / 86400)

def h(text: str) -> str:
    """Échappe les entités HTML."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))

async def _reply(update: Update, text: str) -> None:
    await update.effective_message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


# ═══════════════════════════════════════════════════════════════
# BUILD APPLICATION
# ═══════════════════════════════════════════════════════════════
def build_application(pipeline) -> Application:
    set_pipeline(pipeline)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("scan", cmd_scan))
    logger.info("✅ Handler /scan enregistré (HTML mode)")
    return app
