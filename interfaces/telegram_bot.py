"""
APEX_OMEGA_De1 · Telegram Bot Interface
ParseMode.MARKDOWN (v1) — pas de MarkdownV2, pas d'échappements complexes
*bold*  _italic_  `code`  fonctionnent sans escaper . ( ) ! etc.
"""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from telegram import Bot
from telegram.constants import ParseMode

from config.settings import BOT_TOKEN, CHAT_ID, SIGNALS_DIR

logger = logging.getLogger(__name__)
_bot = Bot(token=BOT_TOKEN)

MD = ParseMode.MARKDOWN   # alias court

# ── Labels marchés
MARKET_LABELS = {
    "over_25":  "⚽ OVER 2.5",
    "over_35":  "🔥 OVER 3.5",
    "under_25": "🔒 UNDER 2.5",
    "under_35": "🛡 UNDER 3.5",
    "btts_yes": "✅ BTTS OUI",
    "btts_no":  "🚫 BTTS NON",
    "1x2_fav":  "🏆 1X2 FAVORI",
    "1x2_out":  "⚡ 1X2 OUTSIDER",
    "handicap": "📐 HANDICAP",
}
VERDICT_ICONS = {
    "STRONG_RUPTURE": "🚀",
    "VARIANCE":       "📊",
    "SMALL_BET":      "🟡",
    "NO_BET":         "🚫",
}


# ─────────────────────────────────────────────────────────────────
# ENVOI
# ─────────────────────────────────────────────────────────────────
async def send(text: str) -> None:
    """Envoi MarkdownV1 — robust, pas d'échappement requis."""
    try:
        await _bot.send_message(
            chat_id=CHAT_ID,
            text=text,
            parse_mode=MD,
            disable_web_page_preview=True,
        )
    except Exception as e:
        # Fallback texte brut si Markdown plante
        logger.warning(f"Markdown send failed ({e}), retry plain text")
        try:
            plain = text.replace("*", "").replace("_", "").replace("`", "")
            await _bot.send_message(chat_id=CHAT_ID, text=plain)
        except Exception as e2:
            logger.error(f"Send failed entirely: {e2}")

async def send_analysis(text: str) -> None:
    await send(text)

async def send_audit(text: str) -> None:
    await send(text)

async def send_no_bet_summary(matchday=None, passes: int = 0, **kwargs) -> None:
    md = matchday or kwargs.get("matchday", "?")
    await send(
        f"🚫 *APEX BUNDESLIGA · J{md}*\n"
        f"Aucun signal retenu — {passes} match(s) analysé(s)\n"
        f"_Prochain scan : 07:00 UTC_"
    )


# ─────────────────────────────────────────────────────────────────
# RAPPORT PRÉ-MATCH (alias pipeline)
# ─────────────────────────────────────────────────────────────────
def format_match_analysis(match, probs, dcs, gates_result, signals, matchday):
    """Génère le texte Telegram (MarkdownV1) d'un rapport pré-match."""
    home = match.get("home_team", "?")
    away = match.get("away_team", "?")
    ko   = match.get("kickoff", "")[:16].replace("T", " ")

    lines = [
        f"⚽ *APEX-BUNDESLIGA A-LAP v1.4 — J{matchday}*",
        f"*{home}* vs *{away}*",
        f"📅 {ko} UTC",
        "",
        f"DCS *{dcs.get('adjusted', 0)}/70* ({dcs.get('tier', '?')}) · "
        f"xG total *{probs.get('xg_total', 0)}*",
    ]

    # Gates actifs
    warnings = gates_result.get("warnings", [])
    if warnings:
        lines += ["", "⚠️ *GATES ACTIFS :*"]
        for w in warnings[:6]:
            lines.append(f"  • {w}")

    # Modèle
    lines += [
        "",
        "📊 *MODÈLE POISSON :*",
        f"  home_xg = `{probs.get('home_xg', 0):.2f}`  |  away_xg = `{probs.get('away_xg', 0):.2f}`",
        f"  Ratio dom. = `{probs.get('ratio_xg', 1):.2f}`  ·  DomFactor = `{probs.get('dom_factor', 1):.2f}`",
        "",
        "🎯 *PROBABILITÉS :*",
        f"  P(Over 2.5) = `{probs.get('p_over_25', 0):.1%}`",
        f"  P(Over 3.5) = `{probs.get('p_over_35', 0):.1%}`",
        f"  P(Home win) = `{probs.get('p_home_win', 0):.1%}`  |  P(Away win) = `{probs.get('p_away_win', 0):.1%}`",
        f"  P(BTTS Oui) = `{probs.get('p_btts_yes', 0):.1%}`",
    ]

    # Signaux
    if signals:
        lines += ["", "💡 *SIGNAUX RETENUS :*"]
        for s in signals:
            label   = MARKET_LABELS.get(s["market"], s["market"].upper())
            icon    = VERDICT_ICONS.get(s.get("verdict", "SMALL_BET"), "🟡")
            lines.append(
                f"  {icon} *{label}* @ `{s.get('fair_odd', 0):.2f}`"
                f"  —  Edge `{s.get('edge', 0):.1%}`  ·  Mise `{s.get('stake_pct', 0):.1%}` BK"
            )
        total_exp = sum(s.get("stake_pct", 0) for s in signals)
        lines += ["", f"💰 *Exposition totale : {total_exp:.1%} / 12% max*"]
    else:
        lines += ["", "🚫 *NO BET — Aucun signal valide*"]

    forbidden = gates_result.get("forbidden_markets", [])
    if forbidden:
        lines.append(f"\n🔕 Exclus : {', '.join(str(f).upper() for f in forbidden)}")

    lines += ["", "—", "_APEX-OMEGA De1 · Usage exclusif_"]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# SAUVEGARDE JSON
# ─────────────────────────────────────────────────────────────────
def save_signal_json(signal: dict) -> None:
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    path = SIGNALS_DIR / f"{date_str}.json"
    data = []
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except Exception:
            pass
    data.append(signal)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _check_won(market: str, hg: int, ag: int) -> bool:
    t = hg + ag
    return {
        "over_25": t > 2, "over_35":  t > 3,
        "under_25": t < 3, "under_35": t < 4,
        "btts_yes": hg > 0 and ag > 0,
        "btts_no":  hg == 0 or ag == 0,
    }.get(market, False)

def sync_send(text: str) -> None:
    asyncio.run(send(text))
