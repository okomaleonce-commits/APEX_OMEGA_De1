"""
APEX_OMEGA_De1 · Commandes Telegram Bot
Permet de déclencher des scans manuellement via Telegram.

Commandes disponibles :
  /scan today      → matchs d'aujourd'hui
  /scan 24h        → matchs dans les 24h
  /scan Nh         → matchs dans les N heures (ex: /scan 48h)
  /scan week       → matchs des 7 prochains jours
  /scan month      → matchs des 30 prochains jours
  /scan next       → prochain(s) match(s) Bundesliga uniquement
  /status          → état de la session en cours
  /audit           → déclenche l'audit post-match manuellement
  /help            → liste des commandes
"""
from __future__ import annotations
import logging
import re
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from config.settings import BOT_TOKEN, CHAT_ID

logger = logging.getLogger(__name__)

# Pipeline injecté au démarrage (évite import circulaire)
_pipeline = None

def set_pipeline(pipeline) -> None:
    """Injecte le pipeline dans les handlers."""
    global _pipeline
    _pipeline = pipeline


# ═══════════════════════════════════════════════════════════════
# GUARD — seuls les messages du CHAT_ID autorisé sont traités
# ═══════════════════════════════════════════════════════════════
def _authorized(update: Update) -> bool:
    chat = str(update.effective_chat.id)
    user = str(update.effective_user.id) if update.effective_user else ""
    allowed = str(CHAT_ID).lstrip("@")
    # Accepte ID numérique ou username du channel
    return chat == allowed or chat.endswith(allowed) or user == allowed


# ═══════════════════════════════════════════════════════════════
# /help
# ═══════════════════════════════════════════════════════════════
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update): return
    text = (
        "🤖 *APEX\\-OMEGA Bundesliga Bot — Commandes*\n\n"
        "`/scan today`   — matchs aujourd'hui\n"
        "`/scan 24h`     — matchs dans les 24h\n"
        "`/scan 48h`     — matchs dans les 48h \\(N = n'importe quel nb\\)\n"
        "`/scan week`    — matchs 7 prochains jours\n"
        "`/scan month`   — matchs 30 prochains jours\n"
        "`/scan next`    — prochain\\(s\\) match\\(s\\) Bundesliga\n\n"
        "`/status`       — état de la session aujourd'hui\n"
        "`/audit`        — audit post\\-match manuel \\(hier\\)\n"
        "`/help`         — cette aide\n\n"
        "_Scan auto : 07:00 UTC · Audit auto : 02:00 UTC_"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")


# ═══════════════════════════════════════════════════════════════
# /scan <mode>
# ═══════════════════════════════════════════════════════════════
async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update): return
    if not _pipeline:
        await update.message.reply_text("⚠️ Pipeline non initialisé\\.", parse_mode="MarkdownV2")
        return

    args = context.args  # liste des mots après /scan
    mode = args[0].lower().strip() if args else "today"

    # ── Résoudre le nombre de jours selon le mode
    days = _resolve_days(mode)
    if days is None:
        await update.message.reply_text(
            f"❓ Mode inconnu : `{mode}`\\. Essaie `/help`\\.",
            parse_mode="MarkdownV2",
        )
        return

    label = _mode_label(mode, days)
    await update.message.reply_text(
        f"🔍 *Scan lancé* — {label}\n_Analyse en cours…_",
        parse_mode="MarkdownV2",
    )

    try:
        await _pipeline.daily_scan(days_ahead=days)
        await update.message.reply_text(
            f"✅ *Scan terminé* — {label}",
            parse_mode="MarkdownV2",
        )
    except Exception as e:
        logger.error(f"Erreur /scan {mode}: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Erreur scan : `{str(e)[:200]}`",
            parse_mode="MarkdownV2",
        )


# ═══════════════════════════════════════════════════════════════
# /status
# ═══════════════════════════════════════════════════════════════
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update): return
    try:
        from storage.signals_repo import SignalsRepo
        repo    = SignalsRepo()
        signals = repo.get_today()
        exp     = sum(s.get("stake_pct", 0) for s in signals)
        wins    = sum(1 for s in signals if s.get("result", {}).get("won"))
        audited = sum(1 for s in signals if s.get("result"))

        text = (
            f"📊 *APEX STATUS — {datetime.utcnow().strftime('%d/%m/%Y')}*\n\n"
            f"Signaux aujourd'hui : *{len(signals)}* / 4 max\n"
            f"Exposition : *{exp:.1%}* / 12% max\n"
        )
        if audited:
            text += f"Résultats audités : *{wins}V / {audited - wins}D*\n"
        if _pipeline:
            au = _pipeline._anti_under_remaining
            if au > 0:
                text += f"\n⚠️ Pause anti\\-Under active : *{au} journée\\(s\\)*\n"

        if signals:
            text += "\n*Signaux :*\n"
            for s in signals:
                mkt  = s.get("market","?").upper()
                match = s.get("match","?")
                odd  = s.get("fair_odd", 0)
                mise = s.get("stake_pct", 0)
                res  = "✅" if s.get("result",{}).get("won") else ("❌" if s.get("result") else "⏳")
                text += f"  {res} {mkt} \\[{match}\\] @ `{odd}` · `{mise:.1%}`\n"

        await update.message.reply_text(text, parse_mode="MarkdownV2")

    except Exception as e:
        await update.message.reply_text(f"❌ Erreur status: `{e}`", parse_mode="MarkdownV2")


# ═══════════════════════════════════════════════════════════════
# /audit
# ═══════════════════════════════════════════════════════════════
async def cmd_audit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update): return
    if not _pipeline:
        await update.message.reply_text("⚠️ Pipeline non initialisé\\.", parse_mode="MarkdownV2")
        return

    await update.message.reply_text("📋 *Audit manuel lancé…*", parse_mode="MarkdownV2")
    try:
        await _pipeline.run_audit()
        await update.message.reply_text("✅ *Audit terminé*", parse_mode="MarkdownV2")
    except Exception as e:
        logger.error(f"Erreur /audit: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Erreur audit: `{e}`", parse_mode="MarkdownV2")


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════
def _resolve_days(mode: str) -> int | None:
    """Convertit le mode textuel en nombre de jours."""
    if mode in ("today", "0"):    return 0
    if mode in ("24h", "1d"):     return 1
    if mode in ("week", "7d"):    return 7
    if mode in ("month", "30d"):  return 30
    if mode in ("next", "next matchs", "nextmatch"): return 3

    # Pattern Nh (ex: 48h, 72h, 6h)
    m = re.fullmatch(r"(\d+)h", mode)
    if m:
        hours = int(m.group(1))
        # Convertir heures → jours (arrondi supérieur, min 1)
        return max(1, -(-hours // 24))  # ceil division

    # Pattern Nd (ex: 3d, 5d)
    m = re.fullmatch(r"(\d+)d", mode)
    if m:
        return max(1, int(m.group(1)))

    return None


def _mode_label(mode: str, days: int) -> str:
    labels = {
        "today":  "matchs aujourd'hui",
        "24h":    "matchs dans les 24h",
        "week":   "matchs 7 prochains jours",
        "month":  "matchs 30 prochains jours",
        "next":   "prochain\\(s\\) match\\(s\\) BL",
    }
    if mode in labels:
        return labels[mode]
    if re.fullmatch(r"\d+h", mode):
        return f"matchs dans les {mode}"
    return f"matchs {days} jour\\(s\\)"


# ═══════════════════════════════════════════════════════════════
# Construction de l'Application Telegram
# ═══════════════════════════════════════════════════════════════
def build_application() -> Application:
    """Construit et configure l'Application python-telegram-bot."""
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("scan",   cmd_scan))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("audit",  cmd_audit))

    logger.info("Bot Telegram : commandes /help /scan /status /audit enregistrées")
    return app
