"""
APEX_OMEGA_De1 · Commandes Telegram
Handlers des commandes /scan avec différentes fenêtres temporelles.

Commandes disponibles :
  /scan today      — matchs aujourd'hui
  /scan 24h        — matchs dans les 24 prochaines heures
  /scan Nh         — matchs dans les N prochaines heures (ex: /scan 48h)
  /scan week       — matchs des 7 prochains jours
  /scan month      — matchs des 30 prochains jours
  /scan next       — 5 prochains matchs Bundesliga
  /scan status     — état de la session en cours
  /scan help       — aide
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

# ── ID(s) autorisés à déclencher des commandes (le channel ou un admin)
# Render injecte CHAT_ID — accepte aussi les messages privés admin
AUTHORIZED_IDS: set[str] = set()  # rempli au démarrage depuis CHAT_ID

# Référence au pipeline injectée depuis main.py
_pipeline = None

def set_pipeline(pipeline) -> None:
    """Injecte la référence pipeline depuis main.py."""
    global _pipeline
    _pipeline = pipeline


# ═══════════════════════════════════════════════════════════════
# HANDLER PRINCIPAL /scan
# ═══════════════════════════════════════════════════════════════
async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Dispatcher /scan <argument>"""

    if not _pipeline:
        await _reply(update, "❌ Pipeline non initialisé.")
        return

    # Lecture argument
    args = " ".join(ctx.args).strip().lower() if ctx.args else "today"

    await _reply(update, f"🔍 Scan lancé : `{args}` — analyse en cours\\.\\.\\.")

    try:
        if args == "today":
            days = _days_until_midnight()
            label = "aujourd'hui"

        elif args == "24h":
            days = 1
            label = "24 prochaines heures"

        elif args in ("week", "semaine"):
            days = 7
            label = "7 prochains jours"

        elif args in ("month", "mois"):
            days = 30
            label = "30 prochains jours"

        elif args in ("next", "next matchs", "prochains"):
            await _scan_next(update)
            return

        elif args == "status":
            await _scan_status(update)
            return

        elif args == "help":
            await _scan_help(update)
            return

        elif re.match(r"^\d+h$", args):
            n = int(args[:-1])
            days = max(1, round(n / 24, 1))
            label = f"{n} prochaines heures"

        else:
            await _reply(update,
                "❓ Argument non reconnu\\. Utilise `/scan help` pour la liste des commandes\\."
            )
            return

        # Lancer le scan
        await _run_scan(update, days=days, label=label)

    except Exception as e:
        logger.error(f"Erreur commande /scan {args}: {e}", exc_info=True)
        await _reply(update, f"❌ Erreur scan : `{e}`")


# ═══════════════════════════════════════════════════════════════
# SCAN AVEC FENÊTRE TEMPORELLE
# ═══════════════════════════════════════════════════════════════
async def _run_scan(update: Update, days: float, label: str) -> None:
    """Lance un daily_scan sur une fenêtre personnalisée."""
    from ingestion.fixtures_service import get_upcoming_fixtures

    raw      = get_upcoming_fixtures(days_ahead=int(days) + 1)
    filtered = _pipeline.router.filter_batch(raw)

    # Filtre sur la fenêtre temporelle exacte
    now     = datetime.utcnow()
    cutoff  = now + timedelta(days=days)
    in_window = []
    for fx in filtered:
        ko_str = fx.get("fixture", {}).get("date", "")
        if not ko_str:
            in_window.append(fx)
            continue
        try:
            ko = datetime.fromisoformat(ko_str.replace("Z", "+00:00")).replace(tzinfo=None)
            if now <= ko <= cutoff:
                in_window.append(fx)
        except Exception:
            in_window.append(fx)

    if not in_window:
        await _reply(update,
            f"📭 *Aucun match Bundesliga trouvé* pour : {label}\\."
        )
        return

    await _reply(update,
        f"⚽ *{len(in_window)} match\\(s\\)* trouvé\\(s\\) — {label}\n"
        f"_Analyse en cours\\.\\.\\._"
    )

    session = {
        "total_exposure": 0.0, "total_signals": 0,
        "family_over": 0.0, "family_under": 0.0, "family_1x2": 0.0,
    }
    all_signals = []
    passes = 0

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

    # Résumé final
    total_exp = session["total_exposure"]
    sign_count = len(all_signals)
    summary = (
        f"✅ *Scan terminé — {label}*\n\n"
        f"📊 Matchs analysés : *{len(in_window)}*\n"
        f"💡 Signaux retenus : *{sign_count}*\n"
        f"🚫 NO BET : *{passes}*\n"
        f"💰 Exposition totale : *{total_exp:.1%}*"
    )
    await _reply(update, summary)


# ═══════════════════════════════════════════════════════════════
# SCAN NEXT MATCHS (5 prochains)
# ═══════════════════════════════════════════════════════════════
async def _scan_next(update: Update) -> None:
    """Affiche les 5 prochains matchs Bundesliga et lance leur analyse."""
    from ingestion.fixtures_service import get_upcoming_fixtures

    raw      = get_upcoming_fixtures(days_ahead=14)
    filtered = _pipeline.router.filter_batch(raw)

    if not filtered:
        await _reply(update, "📭 Aucun prochain match Bundesliga trouvé sur 14 jours\\.")
        return

    # Trier par date
    def ko_sort(fx):
        return fx.get("fixture", {}).get("date", "9999")

    filtered.sort(key=ko_sort)
    next5 = filtered[:5]

    lines = ["⚽ *5 PROCHAINS MATCHS BUNDESLIGA*\n"]
    for fx in next5:
        f  = fx.get("fixture", {})
        h  = fx.get("teams", {}).get("home", {}).get("name", "?")
        a  = fx.get("teams", {}).get("away", {}).get("name", "?")
        ko = f.get("date", "")[:16].replace("T", " ")
        rnd = fx.get("league", {}).get("round", "").replace("Regular Season - ", "J")
        lines.append(f"  🏟️ *{_esc(h)}* vs *{_esc(a)}* · {_esc(ko)} · {_esc(rnd)}")

    await _reply(update, "\n".join(lines))

    # Analyser ces 5 matchs
    await _reply(update, "_Lancement analyse des 5 matchs\\.\\.\\._")
    session = {
        "total_exposure": 0.0, "total_signals": 0,
        "family_over": 0.0, "family_under": 0.0, "family_1x2": 0.0,
    }
    all_sigs = []
    for raw_fx in next5:
        try:
            sigs = await _pipeline._analyze(raw_fx, session)
            all_sigs.extend(sigs)
        except Exception as e:
            logger.error(f"Analyse next: {e}")

    await _reply(update,
        f"✅ *Analyse terminée* : *{len(all_sigs)}* signal\\(s\\) sur {len(next5)} matchs"
    )


# ═══════════════════════════════════════════════════════════════
# STATUS SESSION
# ═══════════════════════════════════════════════════════════════
async def _scan_status(update: Update) -> None:
    """Affiche l'état de la session d'aujourd'hui."""
    from storage.signals_repo import SignalsRepo
    repo   = SignalsRepo()
    today  = repo.get_today()
    total_exp = sum(s.get("stake_pct", 0) for s in today)

    if not today:
        await _reply(update,
            f"📊 *STATUS APEX — {datetime.utcnow().strftime('%d/%m/%Y')}*\n\n"
            f"Aucun signal joué aujourd'hui\\.\n"
            f"Prochain scan auto : 07:00 UTC"
        )
        return

    lines = [
        f"📊 *STATUS APEX — {datetime.utcnow().strftime('%d/%m/%Y')}*\n",
        f"Signaux joués : *{len(today)}* / 4 max",
        f"Exposition    : *{total_exp:.1%}* / 12% max",
        f"Anti\\-Under   : *{'ACTIF' if _pipeline._anti_under_remaining > 0 else 'OFF'}*",
        "",
        "*Détail signaux :*",
    ]
    for s in today:
        market = s.get("market", "?").upper()
        match  = s.get("match", "?")
        odd    = s.get("fair_odd", 0)
        stake  = s.get("stake_pct", 0)
        result = s.get("result")
        if result:
            icon = "✅" if result.get("won") else "❌"
        else:
            icon = "⏳"
        lines.append(f"  {icon} {_esc(match)} — {_esc(market)} @ `{odd:.2f}` \\({stake:.1%}\\)")

    await _reply(update, "\n".join(lines))


# ═══════════════════════════════════════════════════════════════
# AIDE
# ═══════════════════════════════════════════════════════════════
async def _scan_help(update: Update) -> None:
    msg = (
        "📖 *APEX\\-OMEGA BUNDESLIGA — Commandes /scan*\n\n"
        "`/scan today`       — matchs d'aujourd'hui\n"
        "`/scan 24h`         — matchs dans les 24h\n"
        "`/scan 48h`         — matchs dans les 48h \\(Nh = N heures\\)\n"
        "`/scan week`        — matchs des 7 prochains jours\n"
        "`/scan month`       — matchs des 30 prochains jours\n"
        "`/scan next`        — 5 prochains matchs BL \\+ analyse\n"
        "`/scan status`      — état session du jour\n"
        "`/scan help`        — cette aide\n\n"
        "_Les analyses sont automatiques à 07:00 UTC\\._\n"
        "_Audit post\\-match à 02:00 UTC\\._"
    )
    await _reply(update, msg)


# ═══════════════════════════════════════════════════════════════
# UTILS
# ═══════════════════════════════════════════════════════════════
def _days_until_midnight() -> float:
    """Nombre de jours jusqu'à minuit UTC aujourd'hui."""
    now = datetime.utcnow()
    midnight = now.replace(hour=23, minute=59, second=59)
    return max(0.1, (midnight - now).total_seconds() / 86400)

def _esc(text: str) -> str:
    """Échappe MarkdownV2 Telegram."""
    specials = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in specials else c for c in str(text))

async def _reply(update: Update, text: str) -> None:
    """Envoie une réponse MarkdownV2 à l'utilisateur."""
    await update.effective_message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        disable_web_page_preview=True,
    )


# ═══════════════════════════════════════════════════════════════
# BUILD APPLICATION
# ═══════════════════════════════════════════════════════════════
def build_application(pipeline) -> Application:
    """Construit l'Application Telegram avec tous les handlers."""
    global AUTHORIZED_IDS
    AUTHORIZED_IDS = {str(CHAT_ID), str(CHAT_ID).lstrip("@")}
    set_pipeline(pipeline)

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("scan", cmd_scan))
    logger.info("✅ Handler /scan enregistré")
    return app
