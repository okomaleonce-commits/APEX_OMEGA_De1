"""
APEX_OMEGA_De1 · Commandes Telegram /scan
ParseMode.MARKDOWN (v1) uniquement — aucun échappement complexe requis.

  /scan today      — matchs aujourd'hui
  /scan 24h        — 24 prochaines heures
  /scan Nh         — N prochaines heures (ex: /scan 48h)
  /scan week       — 7 prochains jours
  /scan month      — 30 prochains jours
  /scan next       — 5 prochains matchs + analyse
  /scan status     — état session du jour
  /scan help       — aide
"""
from __future__ import annotations
import logging
import re
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

from config.settings import BOT_TOKEN, CHAT_ID

logger = logging.getLogger(__name__)
MD = ParseMode.MARKDOWN

_pipeline = None

def set_pipeline(pipeline) -> None:
    global _pipeline
    _pipeline = pipeline


# ═══════════════════════════════════════════════════════════════
# HANDLER PRINCIPAL
# ═══════════════════════════════════════════════════════════════
async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:

    if not _pipeline:
        await _reply(update, "❌ Pipeline non initialisé.")
        return

    args = " ".join(ctx.args).strip().lower() if ctx.args else "today"

    try:
        if args in ("today", "aujourd'hui", ""):
            await _run_scan(update, days=1, label="aujourd'hui")

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
            n    = int(args[:-1])
            days = max(1, round(n / 24))
            await _run_scan(update, days=days, label=f"{n} prochaines heures")

        else:
            await _reply(update,
                f"❓ Argument non reconnu : `{args}`\n"
                f"Utilise `/scan help` pour la liste des commandes."
            )

    except Exception as e:
        logger.error(f"Erreur /scan {args}: {e}", exc_info=True)
        await _reply(update, f"❌ Erreur : `{e}`")


# ═══════════════════════════════════════════════════════════════
# SCAN PAR FENÊTRE TEMPORELLE
# ═══════════════════════════════════════════════════════════════
async def _run_scan(update: Update, days: int, label: str) -> None:
    from ingestion.fixtures_service import get_upcoming_fixtures

    await _reply(update, f"🔍 Scan lancé — *{label}*...")

    raw      = get_upcoming_fixtures(days_ahead=days + 1)
    filtered = _pipeline.router.filter_batch(raw)

    # Filtre fenêtre exacte
    now    = datetime.utcnow()
    cutoff = now + timedelta(days=days)
    in_window = _filter_window(filtered, now, cutoff)

    if not in_window:
        await _reply(update, f"📭 Aucun match Bundesliga trouvé — {label}.")
        return

    await _reply(update,
        f"⚽ *{len(in_window)} match(s)* trouvé(s) — {label}\n"
        f"_Analyse en cours..._"
    )

    session = _new_session()
    all_signals, passes = [], 0

    for raw_fx in in_window:
        try:
            sigs = await _pipeline._analyze(raw_fx, session)
            if sigs:
                all_signals.extend(sigs)
                _update_session(session, sigs)
            else:
                passes += 1
        except Exception as e:
            logger.error(f"Analyse {raw_fx}: {e}")
            passes += 1

    await _reply(update,
        f"✅ *Scan terminé — {label}*\n\n"
        f"📊 Matchs analysés : *{len(in_window)}*\n"
        f"💡 Signaux retenus : *{len(all_signals)}*\n"
        f"🚫 NO BET         : *{passes}*\n"
        f"💰 Exposition     : *{session['total_exposure']:.1%}*"
    )


# ═══════════════════════════════════════════════════════════════
# 5 PROCHAINS MATCHS
# ═══════════════════════════════════════════════════════════════
async def _scan_next(update: Update) -> None:
    from ingestion.fixtures_service import get_upcoming_fixtures

    raw      = get_upcoming_fixtures(days_ahead=14)
    filtered = _pipeline.router.filter_batch(raw)

    if not filtered:
        await _reply(update, "📭 Aucun prochain match BL trouvé sur 14 jours.")
        return

    filtered.sort(key=lambda fx: fx.get("fixture", {}).get("date", "9999"))
    next5 = filtered[:5]

    lines = ["⚽ *5 PROCHAINS MATCHS BUNDESLIGA*\n"]
    for fx in next5:
        f   = fx.get("fixture", {})
        h   = fx.get("teams", {}).get("home", {}).get("name", "?")
        a   = fx.get("teams", {}).get("away", {}).get("name", "?")
        ko  = f.get("date", "")[:16].replace("T", " ")
        rnd = fx.get("league", {}).get("round", "").replace("Regular Season - ", "J")
        lines.append(f"  🏟 *{h}* vs *{a}*  ·  {ko}  ·  {rnd}")

    await _reply(update, "\n".join(lines))
    await _reply(update, "_Lancement analyse des 5 matchs..._")

    session = _new_session()
    all_sigs = []
    for raw_fx in next5:
        try:
            sigs = await _pipeline._analyze(raw_fx, session)
            all_sigs.extend(sigs)
            _update_session(session, sigs)
        except Exception as e:
            logger.error(f"Analyse next: {e}")

    await _reply(update,
        f"✅ *Analyse terminée*\n"
        f"  Signaux : *{len(all_sigs)}* sur {len(next5)} matchs\n"
        f"  Exposition : *{session['total_exposure']:.1%}*"
    )


# ═══════════════════════════════════════════════════════════════
# STATUS SESSION
# ═══════════════════════════════════════════════════════════════
async def _scan_status(update: Update) -> None:
    from storage.signals_repo import SignalsRepo
    today     = SignalsRepo().get_today()
    total_exp = sum(s.get("stake_pct", 0) for s in today)
    anti      = getattr(_pipeline, "_anti_under_remaining", 0)
    date_str  = datetime.utcnow().strftime("%d/%m/%Y")

    if not today:
        await _reply(update,
            f"📊 *STATUS APEX — {date_str}*\n\n"
            f"Aucun signal joué aujourd'hui.\n"
            f"Prochain scan auto : 07:00 UTC"
        )
        return

    lines = [
        f"📊 *STATUS APEX — {date_str}*\n",
        f"Signaux joués : *{len(today)}* / 4 max",
        f"Exposition    : *{total_exp:.1%}* / 12% max",
        f"Anti-Under    : *{'ACTIF' if anti > 0 else 'OFF'}*",
        "",
        "*Détail :*",
    ]
    for s in today:
        market  = MARKET_ICONS.get(s.get("market", ""), "•")
        match   = s.get("match", "?")
        odd     = s.get("fair_odd", 0)
        stake   = s.get("stake_pct", 0)
        result  = s.get("result", {})
        icon    = ("✅" if result.get("won") else "❌") if result else "⏳"
        lines.append(f"  {icon} {market} {match} @ `{odd:.2f}` ({stake:.1%})")

    await _reply(update, "\n".join(lines))


# ═══════════════════════════════════════════════════════════════
# AIDE
# ═══════════════════════════════════════════════════════════════
async def _scan_help(update: Update) -> None:
    await _reply(update,
        "📖 *APEX-OMEGA BUNDESLIGA — Commandes /scan*\n\n"
        "`/scan today`    — matchs d'aujourd'hui\n"
        "`/scan 24h`      — matchs dans les 24h\n"
        "`/scan 48h`      — matchs dans les 48h (Nh = N heures)\n"
        "`/scan week`     — matchs des 7 prochains jours\n"
        "`/scan month`    — matchs des 30 prochains jours\n"
        "`/scan next`     — 5 prochains matchs BL + analyse\n"
        "`/scan status`   — état session du jour\n"
        "`/scan help`     — cette aide\n\n"
        "_Scan automatique : 07:00 UTC_\n"
        "_Audit post-match : 02:00 UTC_"
    )


# ═══════════════════════════════════════════════════════════════
# UTILS
# ═══════════════════════════════════════════════════════════════
MARKET_ICONS = {
    "over_25": "⚽", "over_35": "🔥",
    "under_25": "🔒", "btts_no": "🚫",
    "btts_yes": "✅", "1x2_fav": "🏆",
    "1x2_out": "⚡",
}

def _filter_window(fixtures: list, now: datetime, cutoff: datetime) -> list:
    result = []
    for fx in fixtures:
        ko_str = fx.get("fixture", {}).get("date", "")
        if not ko_str:
            result.append(fx)
            continue
        try:
            ko = datetime.fromisoformat(ko_str.replace("Z", "+00:00")).replace(tzinfo=None)
            if now <= ko <= cutoff:
                result.append(fx)
        except Exception:
            result.append(fx)
    return result

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

async def _reply(update: Update, text: str) -> None:
    try:
        await update.effective_message.reply_text(
            text, parse_mode=MD, disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"Markdown reply failed ({e}), fallback plain")
        plain = text.replace("*", "").replace("_", "").replace("`", "")
        await update.effective_message.reply_text(plain)


# ═══════════════════════════════════════════════════════════════
# BUILD APPLICATION
# ═══════════════════════════════════════════════════════════════
def build_application(pipeline) -> Application:
    set_pipeline(pipeline)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("scan", cmd_scan))
    logger.info("✅ Handler /scan enregistré (MARKDOWN v1)")
    return app
