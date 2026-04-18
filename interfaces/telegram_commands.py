"""
APEX_OMEGA_De1 · Commandes Telegram
/scan today | /scan 24h | /scan Nh | /scan week | /scan month | /scan next
"""
from __future__ import annotations
import logging
import re
from datetime import datetime, timedelta

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

from config.settings import BOT_TOKEN, CHAT_ID

logger = logging.getLogger(__name__)

# Pipeline injecté depuis main.py
_pipeline = None

def set_pipeline(pipeline) -> None:
    global _pipeline
    _pipeline = pipeline


# ═══════════════════════════════════════════════════════════════
# PARSEUR DE COMMANDE /scan
# ═══════════════════════════════════════════════════════════════

def _parse_scan_args(args: list[str]) -> dict:
    """
    Interprète les arguments de /scan.
    Retourne : {days_ahead: int, label: str}
    """
    raw = " ".join(args).lower().strip()

    if not raw or raw in ("today", "aujourd'hui", "auj"):
        return {"days_ahead": 1,  "label": "aujourd'hui"}

    if raw in ("next", "next matchs", "next match", "prochain", "prochains"):
        return {"days_ahead": 3,  "label": "3 prochains jours"}

    if raw == "week" or raw == "semaine":
        return {"days_ahead": 7,  "label": "7 prochains jours"}

    if raw == "month" or raw == "mois":
        return {"days_ahead": 30, "label": "30 prochains jours"}

    # Pattern Nh (ex: 24h, 48h, 72h)
    m = re.fullmatch(r"(\d+)h?", raw)
    if m:
        hours = int(m.group(1))
        days  = max(1, round(hours / 24))
        return {"days_ahead": days, "label": f"{hours}h (~{days}j)"}

    return {"days_ahead": 3, "label": "3 prochains jours"}  # défaut


# ═══════════════════════════════════════════════════════════════
# HANDLERS
# ═══════════════════════════════════════════════════════════════

async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler principal /scan [argument]"""
    chat_id = str(update.effective_chat.id)

    # Sécurité — autoriser seulement le CHAT_ID configuré
    allowed = str(CHAT_ID).lstrip("@")
    if allowed and allowed not in chat_id and CHAT_ID not in chat_id:
        await update.message.reply_text("⛔ Accès non autorisé.")
        logger.warning(f"Tentative /scan depuis chat non autorisé: {chat_id}")
        return

    if _pipeline is None:
        await update.message.reply_text("⚠️ Pipeline non initialisé.")
        return

    params = _parse_scan_args(ctx.args or [])
    days   = params["days_ahead"]
    label  = params["label"]

    await update.message.reply_text(
        f"🔍 *APEX Scan* — {label}\n"
        f"_Analyse en cours... patiente quelques secondes._",
        parse_mode=ParseMode.MARKDOWN,
    )

    logger.info(f"/scan déclenché : days_ahead={days} ({label})")

    try:
        await _pipeline.manual_scan(days_ahead=days)
    except Exception as e:
        logger.error(f"/scan error: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ *Erreur scan* : `{str(e)[:200]}`",
            parse_mode=ParseMode.MARKDOWN,
        )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/status — état de la session en cours"""
    if _pipeline is None:
        await update.message.reply_text("⚠️ Pipeline non initialisé.")
        return

    try:
        from storage.signals_repo import SignalsRepo
        repo    = SignalsRepo()
        today   = repo.get_today()
        exp     = sum(s.get("stake_pct", 0) for s in today)
        n_won   = sum(1 for s in today if s.get("result", {}).get("won"))
        anti_u  = _pipeline._anti_under_remaining

        lines = [
            "📊 *APEX STATUS — session en cours*",
            f"📅 {datetime.utcnow().strftime('%d/%m/%Y')} UTC",
            "",
            f"Signaux joués   : *{len(today)}* / 4 max",
            f"Exposition totale : *{exp:.1%}* / 12% max",
            f"Anti-Under restant : *{anti_u}J*" if anti_u > 0 else "Anti-Under : ✅ inactif",
        ]
        if today:
            lines += ["", "*Derniers signaux :*"]
            for s in today[-4:]:
                result = s.get("result")
                if result:
                    icon = "✅" if result.get("won") else "❌"
                else:
                    icon = "⏳"
                lines.append(
                    f"  {icon} {s.get('match','?')} — "
                    f"{s.get('market','?').upper()} @ `{s.get('fair_odd', '?')}`"
                )

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur status: {e}")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/help — liste des commandes"""
    msg = (
        "🤖 *APEX-OMEGA Bundesliga Bot*\n"
        "_Commandes disponibles :_\n\n"
        "*Scans manuels :*\n"
        "  `/scan today`   — matchs d'aujourd'hui\n"
        "  `/scan 24h`     — prochaines 24 heures\n"
        "  `/scan 48h`     — prochaines 48 heures (idem Nh)\n"
        "  `/scan week`    — 7 prochains jours\n"
        "  `/scan month`   — 30 prochains jours\n"
        "  `/scan next`    — 3 prochains jours (défaut)\n\n"
        "*Informations :*\n"
        "  `/status`       — état de la session en cours\n"
        "  `/help`         — cette aide\n\n"
        "_Scans automatiques : 07:00 UTC · Audit : 02:00 UTC_"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════════
# APPLICATION TELEGRAM
# ═══════════════════════════════════════════════════════════════

def build_application() -> Application:
    """Construit l'Application python-telegram-bot avec tous les handlers."""
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("scan",   cmd_scan))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("start",  cmd_help))

    return app


async def register_commands(app: Application) -> None:
    """Enregistre les commandes dans le menu Telegram (@BotFather)."""
    commands = [
        BotCommand("scan",   "Lancer un scan manuel Bundesliga"),
        BotCommand("status", "État de la session en cours"),
        BotCommand("help",   "Liste des commandes"),
    ]
    await app.bot.set_my_commands(commands)
    logger.info("Commandes Telegram enregistrées ✓")
