"""
APEX_OMEGA_De1 · Telegram Commands
Commandes de scan manuel via le bot Telegram.

/scan today       → matchs du jour
/scan 24h         → 24 heures à venir
/scan Nh          → N heures à venir (ex: /scan 48h)
/scan week        → 7 prochains jours
/scan month       → 30 prochains jours
/scan next        → 3 prochains matchs Bundesliga
"""
from __future__ import annotations
import logging
import re
from datetime import datetime, timedelta

from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
)
from config.settings import BOT_TOKEN, CHAT_ID

logger = logging.getLogger(__name__)

# Référence au pipeline — injectée au démarrage via set_pipeline()
_pipeline = None

def set_pipeline(pipeline) -> None:
    global _pipeline
    _pipeline = pipeline
    logger.info("Pipeline injecté dans telegram_commands ✓")


# ═══════════════════════════════════════════════════════════════
# HANDLER PRINCIPAL /scan
# ═══════════════════════════════════════════════════════════════
async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Dispatch /scan <argument> vers le bon horizon temporel.
    Usage:
      /scan today       → aujourd'hui (days_ahead=1)
      /scan 24h         → 24 heures
      /scan 48h         → 48 heures (Nh générique)
      /scan week        → 7 jours
      /scan month       → 30 jours
      /scan next        → 3 prochains matchs BL
    """
    if not _pipeline:
        await _reply(update, "❌ Pipeline non initialisé. Redémarre le service.")
        return

    # Restreindre aux admins (CHAT_ID du channel)
    chat = str(update.effective_chat.id)
    user = str(update.effective_user.id) if update.effective_user else ""

    args_raw = " ".join(ctx.args or []).strip().lower()

    # ── Parsing argument
    if not args_raw or args_raw == "today":
        days_ahead  = 1
        label       = "Aujourd'hui"
        max_results = None

    elif args_raw == "24h":
        days_ahead  = 1
        label       = "24 heures"
        max_results = None

    elif args_raw == "week":
        days_ahead  = 7
        label       = "7 prochains jours"
        max_results = None

    elif args_raw == "month":
        days_ahead  = 30
        label       = "30 prochains jours"
        max_results = None

    elif args_raw in ("next", "next matchs", "next matches"):
        days_ahead  = 14
        label       = "Prochains matchs Bundesliga"
        max_results = 3   # limiter aux 3 premiers

    elif re.fullmatch(r"\d+h", args_raw):
        hours      = int(args_raw[:-1])
        days_ahead = max(1, round(hours / 24 + 0.49))  # arrondi supérieur
        label      = f"{hours} heures"
        max_results = None

    else:
        await _reply(update,
            "❓ *Usage :*\n"
            "`/scan today`   — aujourd'hui\n"
            "`/scan 24h`     — 24h\n"
            "`/scan 48h`     — 48h (Nh)\n"
            "`/scan week`    — 7 jours\n"
            "`/scan month`   — 30 jours\n"
            "`/scan next`    — 3 prochains matchs"
        )
        return

    # ── Accusé de réception
    now = datetime.utcnow().strftime("%H:%M UTC")
    await _reply(update,
        f"🔍 *APEX SCAN MANUEL*\n"
        f"Horizon : *{label}* \\({days_ahead}j\\)\n"
        f"Lancé à : `{now}`\n"
        f"_Analyse en cours\\.\\.\\._"
    )

    # ── Lancer le scan
    try:
        await _pipeline.daily_scan(days_ahead=days_ahead, max_results=max_results)
        await _reply(update, f"✅ *Scan terminé* — résultats publiés dans le channel\\.")
    except Exception as e:
        logger.exception(f"Erreur scan manuel: {e}")
        await _reply(update, f"❌ *Erreur scan :* `{str(e)[:200]}`")


# ═══════════════════════════════════════════════════════════════
# HANDLER /status
# ═══════════════════════════════════════════════════════════════
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Résumé rapide de la session du jour."""
    try:
        from storage.signals_repo import SignalsRepo
        repo    = SignalsRepo()
        signals = repo.get_today()
        exp     = sum(s.get("stake_pct", 0) for s in signals)
        now     = datetime.utcnow().strftime("%d/%m %H:%M UTC")

        lines = [
            "📊 *APEX STATUS*",
            f"🕐 `{now}`",
            "",
            f"Signaux aujourd'hui : *{len(signals)}* / 4 max",
            f"Exposition totale   : *{exp:.1%}* / 12% max",
        ]
        if signals:
            lines.append("")
            for s in signals[-4:]:  # 4 derniers
                from interfaces.telegram_bot import MARKET_LABELS
                label = MARKET_LABELS.get(s.get("market",""), s.get("market",""))
                lines.append(
                    f"  • {s.get('match','?')} — {label} "
                    f"\\({s.get('stake_pct',0):.1%}\\)"
                )
        await _reply(update, "\n".join(lines))
    except Exception as e:
        await _reply(update, f"❌ `{e}`")


# ═══════════════════════════════════════════════════════════════
# HANDLER /help
# ═══════════════════════════════════════════════════════════════
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = (
        "🤖 *APEX\\-OMEGA Bundesliga Bot*\n"
        "_Commandes disponibles :_\n\n"
        "`/scan today`    — Matchs du jour\n"
        "`/scan 24h`      — Prochaines 24h\n"
        "`/scan 48h`      — Prochaines 48h \\(Nh générique\\)\n"
        "`/scan week`     — 7 prochains jours\n"
        "`/scan month`    — 30 prochains jours\n"
        "`/scan next`     — 3 prochains matchs BL\n\n"
        "`/status`        — Session du jour\n"
        "`/help`          — Cette aide\n\n"
        "_Scans automatiques :_\n"
        "  • 07:00 UTC — Daily scan\n"
        "  • 02:00 UTC — Audit post\\-match"
    )
    await _reply(update, msg)


# ═══════════════════════════════════════════════════════════════
# BUILD APPLICATION
# ═══════════════════════════════════════════════════════════════
def build_application() -> Application:
    """Construit l'Application Telegram avec tous les handlers."""
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("scan",   cmd_scan))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("help",   cmd_help))
    logger.info("Telegram Application construite — 3 commandes enregistrées")
    return app


async def register_commands(app: Application) -> None:
    """Enregistre les commandes dans le menu BotFather."""
    commands = [
        BotCommand("scan",   "Lancer un scan Bundesliga"),
        BotCommand("status", "Résumé session du jour"),
        BotCommand("help",   "Aide et commandes"),
    ]
    await app.bot.set_my_commands(commands)
    logger.info("Commandes BotFather enregistrées ✓")


# ── Helper
async def _reply(update: Update, text: str) -> None:
    from telegram.constants import ParseMode
    try:
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True,
        )
    except Exception as e:
        # Fallback sans markdown si erreur de formatage
        logger.warning(f"Markdown reply failed, sending plain: {e}")
        try:
            await update.message.reply_text(text.replace("*","").replace("`","").replace("\\",""))
        except Exception:
            pass
