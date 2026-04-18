"""
APEX_OMEGA_De1 · Telegram Bot Interface
Format Bundesliga — DCS + λ total + Flags actifs + Verdict + Exposition
"""
import asyncio, json, logging
from datetime import datetime
from pathlib import Path
from telegram import Bot
from telegram.constants import ParseMode
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID, SIGNALS_DIR

logger = logging.getLogger(__name__)
_bot = Bot(token=TELEGRAM_BOT_TOKEN)

# ── Emojis marchés
MARKET_LABELS = {
    "over_25":  "⚽ OVER 2.5",
    "over_35":  "🔥 OVER 3.5",
    "under_25": "🔒 UNDER 2.5",
    "under_35": "🛡️ UNDER 3.5",
    "btts_yes": "✅ BTTS OUI",
    "btts_no":  "🚫 BTTS NON",
    "dnb_home": "🔵 DNB DOM.",
    "dnb_away": "🟠 DNB EXT.",
    "1x2_fav":  "🏆 1X2 FAVORI",
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
    home = match.get("home_team", "?")
    away = match.get("away_team", "?")
    ko   = match.get("kickoff", "")

    lines = [
        "═══════════════════════════════",
        f"⚽ *APEX\\-OMEGA · BUNDESLIGA · J{matchday}*",
        "═══════════════════════════════",
        "",
        f"🏟️ *{_esc(home)}* vs *{_esc(away)}*",
        f"🕐 KO : {_esc(ko[:16])} UTC",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📋 *CONFIANCE & MODÈLE*",
        "━━━━━━━━━━━━━━━━━━━━",
        f"DCS : *{dcs.get('score',0)}/100* \\({_esc(dcs.get('tier','?'))}\\)",
        f"λ total : `{probs.get('xg_total',0):.2f}` buts \\(home `{probs.get('home_xg',0):.2f}` · away `{probs.get('away_xg',0):.2f}`\\)",
        f"Ratio dom\\. : `{probs.get('ratio_xg',1):.2f}` · DominanceFactor : `{probs.get('dom_factor',1):.2f}`",
    ]

    # ── Flags actifs
    warnings = gates_result.get("warnings", [])
    if warnings:
        lines += ["", "━━━━━━━━━━━━━━━━━━━━", "⚠️ *GATES ACTIFS*", "━━━━━━━━━━━━━━━━━━━━"]
        for w in warnings[:8]:  # max 8 lignes
            lines.append(f"  • {_esc(w)}")

    # ── Probabilités clés
    lines += [
        "", "━━━━━━━━━━━━━━━━━━━━",
        "🎯 *PROBABILITÉS*", "━━━━━━━━━━━━━━━━━━━━",
        f"  P\\(Over 2\\.5\\) = `{probs.get('p_over_25',0):.1%}`",
        f"  P\\(Over 3\\.5\\) = `{probs.get('p_over_35',0):.1%}`",
        f"  P\\(Dom win\\)  = `{probs.get('p_home_win',0):.1%}`",
        f"  P\\(Away win\\) = `{probs.get('p_away_win',0):.1%}`",
        f"  P\\(BTTS Oui\\) = `{probs.get('p_btts_yes',0):.1%}`",
    ]

    # ── Signaux
    if signals:
        lines += ["", "━━━━━━━━━━━━━━━━━━━━", "💡 *SIGNAUX RETENUS*", "━━━━━━━━━━━━━━━━━━━━"]
        for s in signals:
            label   = MARKET_LABELS.get(s["market"], s["market"].upper())
            verdict = VERDICT_EMOJIS.get(s.get("verdict", "SMALL_BET"), "🟡")
            lines.append(
                f"{verdict} *{_esc(label)}* @ `{s.get('fair_odd',0):.2f}`\n"
                f"     Edge `{s.get('edge',0):.1%}` · Mise `{s.get('stake_pct',0):.1%}` BK"
            )
        total_exp = sum(s.get("stake_pct", 0) for s in signals)
        lines += [
            "",
            f"💰 *Exposition totale : `{total_exp:.1%}` / 12% max*",
        ]
    else:
        lines += ["", "🚫 *NO BET — Aucun signal valide*"]

    # ── Marchés exclus
    forbidden = gates_result.get("mods", {}).get("forbidden_markets", [])
    if forbidden:
        lines += ["", f"🔕 Exclus : {_esc(', '.join(str(f).upper() for f in forbidden))}"]

    lines += ["", "─────────────────────────────",
              "_APEX\\-OMEGA Bundesliga · Usage exclusif_"]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# FORMAT TABLEAU RÉCAPITULATIF JOURNÉE
# ═══════════════════════════════════════════════════════════════
def format_daily_summary(matchday: int, signals_list: list, passes_count: int) -> str:
    total_exp = sum(s.get("stake_pct", 0) for s in signals_list)
    lines = [
        "═══════════════════════════════",
        f"📊 *APEX BUNDESLIGA · RÉSUMÉ J{matchday}*",
        f"📅 {datetime.utcnow().strftime('%d/%m/%Y')} UTC",
        "═══════════════════════════════",
        "",
        f"Signaux joués : *{len(signals_list)}* / 4 max",
        f"Matchs passés \\(NO BET\\) : *{passes_count}*",
        f"Exposition totale : *{total_exp:.1%}* / 12% max",
        "",
    ]
    if signals_list:
        lines.append("*Détail :*")
        for s in signals_list:
            label = MARKET_LABELS.get(s.get("market", ""), s.get("market", ""))
            lines.append(
                f"  • {_esc(s.get('match','?'))} — {_esc(label)} "
                f"@ `{s.get('fair_odd',0):.2f}` \\({s.get('stake_pct',0):.1%} BK\\)"
            )
    lines += ["", "_Prochain scan : 07:00 UTC_"]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# FORMAT AUDIT POST-MATCH
# ═══════════════════════════════════════════════════════════════
def format_audit(match: dict, signals: list, score: tuple, matchday: int) -> str:
    hg, ag = score
    total  = hg + ag
    home   = match.get("home_team", "?")
    away   = match.get("away_team", "?")

    lines = [
        "═══════════════════════════════",
        f"📋 *AUDIT POST\\-MATCH · J{matchday}*",
        f"🏟️ *{_esc(home)} {hg}\\-{ag} {_esc(away)}*",
        "═══════════════════════════════", "",
    ]

    pl_total = 0.0
    for s in signals:
        won = _check_won(s["market"], hg, ag)
        if won:
            pl = s["stake_pct"] * (s.get("fair_odd", 2.0) - 1)
            v  = f"✅ GAGNÉ \\+{pl:.2%}"
        else:
            pl = -s["stake_pct"]
            v  = f"❌ PERDU \\-{s['stake_pct']:.2%}"
        pl_total += pl
        label = MARKET_LABELS.get(s["market"], s["market"])
        lines.append(f"  {_esc(label)} → {v}")

    sign = "\\+" if pl_total >= 0 else ""
    lines += ["", f"*P\\&L session : {sign}{pl_total:.2%}*"]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# ENVOI TELEGRAM
# ═══════════════════════════════════════════════════════════════
async def send(text: str) -> None:
    await _bot.send_message(
        chat_id=TELEGRAM_CHANNEL_ID,
        text=text,
        parse_mode=ParseMode.MARKDOWN_V2,
        disable_web_page_preview=True,
    )

def sync_send(text: str) -> None:
    asyncio.run(send(text))


# ═══════════════════════════════════════════════════════════════
# SAUVEGARDE JSON SIGNAL
# ═══════════════════════════════════════════════════════════════
def save_signal_json(signal: dict) -> None:
    """Sauvegarde copie JSON du signal dans /data/signals/ pour audit."""
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    path = SIGNALS_DIR / f"{date_str}.json"
    data = []
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except:
            pass
    data.append(signal)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


# ── Helpers
def _esc(text: str) -> str:
    """Échappe les caractères spéciaux MarkdownV2 Telegram."""
    specials = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in specials else c for c in str(text))

def _check_won(market: str, hg: int, ag: int) -> bool:
    t = hg + ag
    return {
        "over_25":  t > 2, "over_35":  t > 3,
        "under_25": t < 3, "under_35": t < 4,
        "btts_yes": hg > 0 and ag > 0,
        "btts_no":  hg == 0 or ag == 0,
    }.get(market, False)
