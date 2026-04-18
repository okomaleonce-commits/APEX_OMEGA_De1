"""
APEX_OMEGA_De1 · Telegram Bot — format HTML (plus robuste que MarkdownV2)
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

MARKET_LABELS = {
    "over_25":  "⚽ OVER 2.5",
    "over_35":  "🔥 OVER 3.5",
    "under_25": "🔒 UNDER 2.5",
    "under_35": "🛡️ UNDER 3.5",
    "btts_yes": "✅ BTTS OUI",
    "btts_no":  "🚫 BTTS NON",
    "dnb_home": "🔵 DNB DOM.",
    "dnb_away": "🟠 DNB EXT.",
    "1x2_fav":  "🏆 1X2 FAV.",
    "1x2_out":  "⚡ 1X2 OUTSIDER",
    "handicap": "📐 HANDICAP",
}

VERDICT_EMOJIS = {
    "STRONG_RUPTURE": "🚀",
    "VARIANCE":       "📊",
    "SMALL_BET":      "🟡",
    "NO_BET":         "🚫",
}


# ═══════════════════════════════════════════════════════════════
# ENVOI CENTRAL — HTML uniquement
# ═══════════════════════════════════════════════════════════════
async def send(text: str) -> None:
    """Envoie un message HTML dans le canal Telegram."""
    try:
        await _bot.send_message(
            chat_id=CHAT_ID,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(f"Telegram send error: {e}")

def sync_send(text: str) -> None:
    asyncio.run(send(text))

async def send_analysis(text: str) -> None:
    await send(text)

async def send_audit(text: str) -> None:
    await send(text)

async def send_no_bet_summary(matchday=None, passes: int = 0, **kwargs) -> None:
    md = matchday or kwargs.get("matchday", "?")
    await send(
        f"🚫 <b>APEX BUNDESLIGA · J{md}</b>\n"
        f"Aucun signal retenu — {passes} match(s) analysé(s)\n\n"
        f"<i>Prochain scan : 07:00 UTC</i>"
    )


# ═══════════════════════════════════════════════════════════════
# FORMAT ANALYSE PRÉ-MATCH
# ═══════════════════════════════════════════════════════════════
def format_match_analysis(
    match: dict,
    probs: dict,
    dcs: dict,
    gates_result: dict,
    signals: list,
    matchday: int,
) -> str:
    home = h(match.get("home_team", "?"))
    away = h(match.get("away_team", "?"))
    ko   = h(match.get("kickoff", "")[:16].replace("T", " "))

    lines = [
        "═══════════════════════════════",
        f"⚽ <b>APEX-OMEGA · BUNDESLIGA · J{matchday}</b>",
        "═══════════════════════════════",
        "",
        f"🏟️ <b>{home}</b> vs <b>{away}</b>",
        f"🕐 KO : {ko} UTC",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📋 <b>CONFIANCE &amp; MODÈLE</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"DCS : <b>{dcs.get('adjusted', dcs.get('score', 0))}/70</b> ({h(dcs.get('tier','?'))})",
        f"λ total : <code>{probs.get('xg_total', 0):.2f}</code> buts"
        f"  (home <code>{probs.get('home_xg', 0):.2f}</code>"
        f" · away <code>{probs.get('away_xg', 0):.2f}</code>)",
        f"Ratio : <code>{probs.get('ratio_xg', 1):.2f}</code>"
        f" · DomFactor : <code>{probs.get('dom_factor', 1):.2f}</code>",
    ]

    # Gates / warnings
    warnings = gates_result.get("warnings", [])
    if warnings:
        lines += ["", "━━━━━━━━━━━━━━━━━━━━", "⚠️ <b>GATES ACTIFS</b>", "━━━━━━━━━━━━━━━━━━━━"]
        for w in warnings[:8]:
            lines.append(f"  • {h(w)}")

    # Probabilités
    lines += [
        "", "━━━━━━━━━━━━━━━━━━━━",
        "🎯 <b>PROBABILITÉS</b>", "━━━━━━━━━━━━━━━━━━━━",
        f"  P(Over 2.5) = <code>{probs.get('p_over_25', 0):.1%}</code>",
        f"  P(Over 3.5) = <code>{probs.get('p_over_35', 0):.1%}</code>",
        f"  P(Dom win)  = <code>{probs.get('p_home_win', 0):.1%}</code>",
        f"  P(Away win) = <code>{probs.get('p_away_win', 0):.1%}</code>",
        f"  P(BTTS Oui) = <code>{probs.get('p_btts_yes', 0):.1%}</code>",
    ]

    # Signaux
    if signals:
        lines += ["", "━━━━━━━━━━━━━━━━━━━━", "💡 <b>SIGNAUX RETENUS</b>", "━━━━━━━━━━━━━━━━━━━━"]
        for s in signals:
            label   = MARKET_LABELS.get(s["market"], s["market"].upper())
            verdict = VERDICT_EMOJIS.get(s.get("verdict", "SMALL_BET"), "🟡")
            lines.append(
                f"{verdict} <b>{label}</b> @ <code>{s.get('fair_odd', 0):.2f}</code>\n"
                f"     Edge <code>{s.get('edge', 0):.1%}</code>"
                f" · Mise <code>{s.get('stake_pct', 0):.1%}</code> BK"
            )
        total_exp = sum(s.get("stake_pct", 0) for s in signals)
        lines += ["", f"💰 <b>Exposition totale : {total_exp:.1%} / 12% max</b>"]
    else:
        lines += ["", "🚫 <b>NO BET</b> — Aucun signal valide"]

    forbidden = gates_result.get("forbidden_markets", [])
    if forbidden:
        lines += ["", f"🔕 Exclus : {h(', '.join(str(f).upper() for f in forbidden))}"]

    lines += ["", "─────────────────────────────", "<i>APEX-OMEGA Bundesliga · Usage exclusif</i>"]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# FORMAT RÉSUMÉ JOURNÉE
# ═══════════════════════════════════════════════════════════════
def format_daily_summary(matchday, all_signals: list, passes_count: int) -> str:
    total_exp = sum(s.get("stake_pct", 0) for s in all_signals)
    lines = [
        "═══════════════════════════════",
        f"📊 <b>APEX BUNDESLIGA · RÉSUMÉ J{matchday}</b>",
        f"📅 {datetime.utcnow().strftime('%d/%m/%Y')} UTC",
        "═══════════════════════════════",
        "",
        f"Signaux joués : <b>{len(all_signals)}</b> / 4 max",
        f"Matchs passés (NO BET) : <b>{passes_count}</b>",
        f"Exposition totale : <b>{total_exp:.1%}</b> / 12% max",
        "",
    ]
    if all_signals:
        lines.append("<b>Détail :</b>")
        for s in all_signals:
            label = MARKET_LABELS.get(s.get("market", ""), s.get("market", ""))
            lines.append(
                f"  • {h(s.get('match', '?'))} — {label}"
                f" @ <code>{s.get('fair_odd', 0):.2f}</code>"
                f" ({s.get('stake_pct', 0):.1%} BK)"
            )
    lines += ["", "<i>Prochain scan : 07:00 UTC</i>"]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# FORMAT AUDIT
# ═══════════════════════════════════════════════════════════════
def format_audit(match: dict, signals: list, score: tuple, matchday) -> str:
    hg, ag = score
    home   = h(match.get("home_team", "?"))
    away   = h(match.get("away_team", "?"))

    lines = [
        "═══════════════════════════════",
        f"📋 <b>AUDIT POST-MATCH · J{matchday}</b>",
        f"🏟️ <b>{home} {hg}-{ag} {away}</b>",
        "═══════════════════════════════", "",
    ]
    pl_total = 0.0
    for s in signals:
        won = _check_won(s["market"], hg, ag)
        if won:
            pl  = s["stake_pct"] * (s.get("fair_odd", 2.0) - 1)
            vtx = f"✅ GAGNÉ +{pl:.2%}"
        else:
            pl  = -s["stake_pct"]
            vtx = f"❌ PERDU -{s['stake_pct']:.2%}"
        pl_total += pl
        label = MARKET_LABELS.get(s["market"], s["market"])
        lines.append(f"  {label} → {vtx}")

    sign = "+" if pl_total >= 0 else ""
    lines += ["", f"<b>P&amp;L session : {sign}{pl_total:.2%}</b>"]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# SAUVEGARDE JSON
# ═══════════════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════
def h(text: str) -> str:
    """Échappe les caractères HTML : & < > ' " """
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))

def _check_won(market: str, hg: int, ag: int) -> bool:
    t = hg + ag
    return {
        "over_25":  t > 2,
        "over_35":  t > 3,
        "under_25": t < 3,
        "under_35": t < 4,
        "btts_yes": hg > 0 and ag > 0,
        "btts_no":  hg == 0 or ag == 0,
    }.get(market, False)
