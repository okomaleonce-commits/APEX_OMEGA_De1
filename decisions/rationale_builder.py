"""
APEX_OMEGA_De1 · Rationale Builder — rapports Telegram
Format HTML (parse_mode=HTML) — robuste, pas de caractères à échapper.
"""
from __future__ import annotations
from datetime import datetime
from bundesliga.config_v2_3 import FLAGS

MARKET_LABELS = {
    "over_25":  "⚽ OVER 2.5",
    "over_35":  "🔥 OVER 3.5",
    "under_25": "🔒 UNDER 2.5",
    "under_35": "🛡️ UNDER 3.5",
    "btts_yes": "✅ BTTS OUI",
    "btts_no":  "🚫 BTTS NON",
    "1x2_fav":  "🏆 1X2 FAVORI",
    "1x2_out":  "⚡ 1X2 OUTSIDER",
}

VERDICT_LABELS = {
    "STRONG_RUPTURE": "🚀 FORTE RUPTURE",
    "VARIANCE":       "📊 VARIANCE",
    "SMALL_BET":      "🟡 SMALL BET",
    "NO_BET":         "🚫 NO BET",
}


def _h(text) -> str:
    """Échappe les entités HTML."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


# ═══════════════════════════════════════════════════════════════
def build_pre_match_report(
    match:   dict,
    probs:   dict,
    dcs:     dict,
    gates:   dict,
    signals: list[dict],
) -> str:
    home = _h(match["home_team"])
    away = _h(match["away_team"])
    md   = match.get("matchday", "?")
    ko   = _h(match.get("kickoff", "")[:16].replace("T", " "))

    lines = [
        "═══════════════════════════════",
        f"⚽ <b>APEX-BUNDESLIGA v1.4 — J{md}</b>",
        f"<b>{home}</b> vs <b>{away}</b>",
        f"📅 {ko} UTC",
        "",
        f"DCS <b>{dcs.get('adjusted', '?')}/70</b> ({_h(dcs.get('tier','?'))})"
        f" · xG total <b>{probs.get('xg_total','?')}</b>",
    ]

    # Gates / warnings
    warnings = gates.get("warnings", [])
    if warnings:
        lines += ["", "⚠️ <b>GATES ACTIFS :</b>"]
        for w in warnings[:6]:
            lines.append(f"  • {_h(w)}")

    # Flags
    active_flags = [k for k in gates.get("flags", {}) if k in FLAGS and gates["flags"][k] is True]
    if active_flags:
        lines += ["", f"🚩 <b>FLAGS :</b> {_h(' · '.join(active_flags[:4]))}"]

    # Modèle Poisson
    lines += [
        "",
        "📊 <b>MODÈLE POISSON :</b>",
        f"  home_xg = <code>{probs.get('home_xg', 0):.3f}</code>"
        f"  |  away_xg = <code>{probs.get('away_xg', 0):.3f}</code>",
        f"  Ratio = <code>{probs.get('ratio_xg', 1):.2f}</code>"
        f"  ·  DomFactor = <code>{probs.get('dom_factor', 1):.2f}</code>",
    ]

    # Probabilités
    lines += [
        "",
        "🎯 <b>PROBABILITÉS :</b>",
        f"  P(Over 2.5) = <code>{probs.get('p_over_25', 0):.1%}</code>",
        f"  P(Over 3.5) = <code>{probs.get('p_over_35', 0):.1%}</code>",
        f"  P(Home win) = <code>{probs.get('p_home_win', 0):.1%}</code>"
        f"  |  P(Away win) = <code>{probs.get('p_away_win', 0):.1%}</code>",
        f"  P(BTTS Oui) = <code>{probs.get('p_btts_yes', 0):.1%}</code>"
        f"  |  P(BTTS Non) = <code>{probs.get('p_btts_no', 0):.1%}</code>",
    ]

    # DCS détail
    g = [dcs.get(f"g{i}", "?") for i in range(1, 7)]
    lines += ["", f"📋 <b>DCS :</b> G1={g[0]} G2={g[1]} G3={g[2]} G4={g[3]} G5={g[4]} G6={g[5]}"]

    # Signaux
    if signals:
        lines += ["", "💡 <b>SIGNAUX RETENUS :</b>"]
        total_exp = 0.0
        for s in signals:
            label   = MARKET_LABELS.get(s["market"], s["market"].upper())
            verdict = VERDICT_LABELS.get(s.get("verdict", ""), s.get("verdict", ""))
            lines.append(
                f"  {label} @ <code>{s.get('fair_odd', 0):.2f}</code>\n"
                f"     {verdict} · Edge: <code>{s.get('edge', 0):.1%}</code>"
                f" · Mise: <code>{s.get('stake_pct', 0):.1%}</code>"
            )
            total_exp += s.get("stake_pct", 0)
        lines += ["", f"💰 <b>Exposition totale : {total_exp:.1%} / 12% max</b>"]
    else:
        lines += ["", "🚫 <b>NO BET</b> — Aucun signal valide"]

    # Marchés interdits
    forbidden = gates.get("forbidden_markets", [])
    if forbidden:
        lines += ["", f"🔕 <b>Exclus :</b> <code>{_h(' · '.join(f.upper() for f in forbidden))}</code>"]

    lines += ["", "—", "<i>APEX-OMEGA De1 Bot · Usage exclusif</i>"]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
def build_daily_summary(matchday: int, all_signals: list[dict], total_exp: float) -> str:
    lines = [
        f"📊 <b>RÉSUMÉ SESSION APEX — J{matchday}</b>",
        f"📅 {datetime.utcnow().strftime('%d/%m/%Y')} UTC",
        "",
        f"Signaux joués : <b>{len(all_signals)}</b>",
        f"Exposition totale : <b>{total_exp:.1%}</b>",
        "",
    ]
    for s in all_signals:
        label = MARKET_LABELS.get(s.get("market", ""), s.get("market", ""))
        match = _h(s.get("match", s.get("home", "?") + " vs " + s.get("away", "?")))
        lines.append(
            f"  {label} [{match}]"
            f" @ <code>{s.get('fair_odd', 0):.2f}</code>"
            f" → <code>{s.get('stake_pct', 0):.1%}</code>"
        )
    lines += ["", "<i>Prochain scan : 07:00 UTC</i>"]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
def build_audit_report(
    matchday: int,
    signals:  list[dict],
    results:  dict,
) -> str:
    lines = [
        f"📋 <b>AUDIT POST-MATCH — J{matchday}</b>",
        f"📅 {datetime.utcnow().strftime('%d/%m/%Y')} UTC",
        "",
    ]
    pl_total, wins = 0.0, 0

    for s in signals:
        fid = s.get("fixture_id")
        res = results.get(fid, {})
        hg  = res.get("home_goals", 0) or 0
        ag  = res.get("away_goals", 0) or 0
        won = _signal_won(s.get("market", ""), hg, ag)
        match = _h(s.get("match", "?"))

        if won:
            pl  = s.get("stake_pct", 0) * (s.get("fair_odd", 2.0) - 1)
            wins += 1
            vstr = f"✅ +{pl:.2%}"
        else:
            pl   = -s.get("stake_pct", 0)
            vstr = f"❌ -{s.get('stake_pct', 0):.2%}"

        pl_total += pl
        label = MARKET_LABELS.get(s.get("market", ""), s.get("market", ""))
        lines.append(f"  {label} [{match} {hg}-{ag}] {vstr}")

    rate = wins / len(signals) * 100 if signals else 0
    sign = "+" if pl_total >= 0 else ""
    lines += [
        "",
        f"<b>Résultat :</b> {wins}V / {len(signals)-wins}D — {rate:.0f}% taux",
        f"<b>P&amp;L session :</b> <code>{sign}{pl_total:.2%}</code>",
    ]
    return "\n".join(lines)


def _signal_won(market: str, hg: int, ag: int) -> bool:
    t = hg + ag
    return {
        "over_25": t > 2, "over_35": t > 3,
        "under_25": t < 3, "under_35": t < 4,
        "btts_yes": hg > 0 and ag > 0,
        "btts_no":  hg == 0 or ag == 0,
    }.get(market, False)
