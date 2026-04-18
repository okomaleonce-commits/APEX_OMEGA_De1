"""
APEX_OMEGA_De1 · Rationale Builder — rapports Telegram APEX v1.4
Format compatible Telegram Markdown v2 simplifié.
"""
from __future__ import annotations
from datetime import datetime
from bundesliga.config_v2_3 import VERDICTS, FLAGS

MARKET_LABELS = {
    "over_25":  "⚽ OVER 2.5",
    "over_35":  "🔥 OVER 3.5",
    "under_25": "🔒 UNDER 2.5",
    "under_35": "🔒 UNDER 3.5",
    "btts_yes": "✅ BTTS OUI",
    "btts_no":  "🚫 BTTS NON",
    "1x2_fav":  "🏆 1X2 FAVORI",
    "1x2_out":  "⚡ 1X2 OUTSIDER",
}

VERDICT_LABELS = {
    "STRONG_RUPTURE": "🔥 FORTE RUPTURE",
    "VARIANCE":        "⚡ VARIANCE",
    "SMALL_BET":       "📊 SMALL BET",
    "NO_BET":          "🚫 NO BET",
}


def build_pre_match_report(
    match:    dict,
    probs:    dict,
    dcs:      dict,
    gates:    dict,
    signals:  list[dict],
) -> str:
    home = match["home_team"]
    away = match["away_team"]
    md   = match.get("matchday", "?")
    ko   = match.get("kickoff", "")

    lines = [
        f"⚽ *APEX-BUNDESLIGA A-LAP v1.4 — J{md}*",
        f"*{home}* vs *{away}*",
        f"📅 `{ko}` UTC",
        "",
        f"DCS *{dcs['adjusted']}/70* ({dcs['tier']}) · xG total *{probs['xg_total']}*",
    ]

    # Gates actifs + warnings
    warnings = gates.get("warnings", [])
    if warnings:
        lines.append("")
        lines.append("⚠️ *GATES ACTIFS :*")
        for w in warnings:
            lines.append(f"  • {w}")

    # Flags actifs
    active_flags = [k for k in gates.get("flags", {}) if k in FLAGS]
    if active_flags:
        lines.append("")
        lines.append("🚩 *FLAGS :* " + " · ".join(active_flags[:4]))

    # Modèle Poisson
    lines += [
        "",
        "📊 *MODÈLE POISSON :*",
        f"  home\\_xg = `{probs['home_xg']}`  |  away\\_xg = `{probs['away_xg']}`",
        f"  Ratio = `{probs['ratio_xg']}`  ·  Dom.Factor = `{probs['dominance_factor']}`",
    ]

    # Probabilités
    lines += [
        "",
        "🎯 *PROBABILITÉS :*",
        f"  P(Over 2.5) = {probs['p_over_25']:.1%}",
        f"  P(Over 3.5) = {probs['p_over_35']:.1%}",
        f"  P(Home win) = {probs['p_home_win']:.1%}  |  "
        f"P(Away win) = {probs['p_away_win']:.1%}",
        f"  P(BTTS Oui) = {probs['p_btts_yes']:.1%}  |  "
        f"P(BTTS Non) = {probs['p_btts_no']:.1%}",
    ]

    # DCS détail
    lines += [
        "",
        f"📋 *DCS DÉTAIL :* G1={dcs['g1']} G2={dcs['g2']} G3={dcs['g3']} "
        f"G4={dcs['g4']} G5={dcs['g5']} G6={dcs['g6']}",
    ]

    # Signaux
    if signals:
        lines.append("")
        lines.append("💡 *SIGNAUX RETENUS :*")
        total_exp = 0.0
        for s in signals:
            label   = MARKET_LABELS.get(s["market"], s["market"].upper())
            verdict = VERDICT_LABELS.get(s["verdict"], s["verdict"])
            lines.append(
                f"  {label} @ `{s['fair_odd']:.2f}`\n"
                f"     {verdict} · Edge: `{s['edge']:.1%}` · Mise: `{s['stake_pct']:.1%}`"
            )
            total_exp += s["stake_pct"]
        lines.append("")
        lines.append(f"💰 *Exposition totale : {total_exp:.1%} / 12% max*")
    else:
        lines.append("")
        lines.append("🚫 *NO BET — Aucun signal valide*")

    # Marchés interdits
    forbidden = gates.get("forbidden_markets", [])
    if forbidden:
        lines.append("")
        lines.append(f"🔕 *Marchés exclus :* `{' · '.join(f.upper() for f in forbidden)}`")

    lines += ["", "—", "_APEX-OMEGA De1 Bot · Usage exclusif_"]
    return "\n".join(lines)


def build_daily_summary(matchday: int, all_signals: list[dict], total_exp: float) -> str:
    lines = [
        f"📊 *RÉSUMÉ SESSION APEX — J{matchday}*",
        f"📅 {datetime.utcnow().strftime('%d/%m/%Y')}",
        "",
        f"Signaux joués   : *{len(all_signals)}*",
        f"Exposition totale : *{total_exp:.1%}*",
        "",
    ]
    for s in all_signals:
        label = MARKET_LABELS.get(s["market"], s["market"])
        lines.append(
            f"  {label} [{s['home']} vs {s['away']}] "
            f"@ `{s['fair_odd']:.2f}` → `{s['stake_pct']:.1%}`"
        )
    lines += ["", "_Prochain scan : 07:00 UTC_"]
    return "\n".join(lines)


def build_audit_report(
    matchday: int,
    signals:  list[dict],
    results:  dict,   # {fixture_id: {"home_goals": int, "away_goals": int}}
) -> str:
    lines = [
        f"📋 *AUDIT POST-MATCH — J{matchday}*",
        f"📅 {datetime.utcnow().strftime('%d/%m/%Y')}",
        "",
    ]
    pl_total = 0.0
    wins = 0

    for s in signals:
        fid   = s.get("fixture_id")
        res   = results.get(fid, {})
        hg    = res.get("home_goals", 0) or 0
        ag    = res.get("away_goals", 0) or 0
        total = hg + ag
        won   = _signal_won(s["market"], hg, ag)

        if won:
            pl = s["stake_pct"] * (s["fair_odd"] - 1)
            wins += 1
            verdict_str = f"✅ +{pl:.2%}"
        else:
            pl = -s["stake_pct"]
            verdict_str = f"❌ -{s['stake_pct']:.2%}"

        pl_total += pl
        label = MARKET_LABELS.get(s["market"], s["market"])
        lines.append(
            f"  {label} [{s['home']} {hg}-{ag} {s['away']}] {verdict_str}"
        )

    rate = wins / len(signals) * 100 if signals else 0
    lines += [
        "",
        f"*Résultat :* {wins}V / {len(signals)-wins}D — {rate:.0f}% taux",
        f"*P&L session :* `{pl_total:+.2%}`",
    ]
    return "\n".join(lines)


def _signal_won(market: str, hg: int, ag: int) -> bool:
    total = hg + ag
    if market == "over_25":  return total > 2
    if market == "over_35":  return total > 3
    if market == "under_25": return total < 3
    if market == "under_35": return total < 4
    if market == "btts_yes": return hg > 0 and ag > 0
    if market == "btts_no":  return hg == 0 or ag == 0
    return False
