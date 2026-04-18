"""
APEX_OMEGA_De1 · Rapport Telegram — tous marchés v2
"""
from datetime import datetime

VERDICT_ICONS = {
    "STRONG_RUPTURE": "🚀", "VARIANCE": "📊",
    "SMALL_BET": "🟡",      "SPECULATIVE": "🔮",
    "NO_BET": "🚫",
}
GRADE_ICONS = {"A": "⭐", "B": "🔵", "C": "🟠", "D": "⚪"}


def build_pre_match_report(match, all_probs, dcs, gates, signals) -> str:
    home = match.get("home_team","?")
    away = match.get("away_team","?")
    md   = match.get("matchday","?")
    ko   = match.get("kickoff","")[:16].replace("T"," ")

    hxg  = all_probs.get("_home_xg", 0)
    axg  = all_probs.get("_away_xg", 0)
    tot  = all_probs.get("_xg_total", 0)
    dom  = all_probs.get("_dom_factor", 1)

    lines = [
        f"⚽ *APEX-BUNDESLIGA v1.4 — J{md}*",
        f"*{home}* vs *{away}*",
        f"📅 {ko} UTC",
        "",
        f"DCS *{dcs.get('adjusted',0)}/70* ({dcs.get('tier','?')})  |  xG *{tot}* ({hxg} / {axg})",
        f"DomFactor *{dom}*  |  Ratio *{all_probs.get('_ratio_xg',1)}*",
    ]

    # Gates warnings
    warnings = gates.get("warnings", [])
    if warnings:
        lines += ["", "⚠️ *GATES :*"]
        for w in warnings[:5]:
            lines.append(f"  • {w}")

    # Tableau probabilités clés
    lines += [
        "", "📊 *MARCHÉS :*",
        f"  1 gagne    `{all_probs.get('1x2_home',0):.0%}`  |  Nul `{all_probs.get('1x2_draw',0):.0%}`  |  2 gagne `{all_probs.get('1x2_away',0):.0%}`",
        f"  DC 1X      `{all_probs.get('dc_1x',0):.0%}`  |  DC X2 `{all_probs.get('dc_x2',0):.0%}`  |  DC 12 `{all_probs.get('dc_12',0):.0%}`",
        f"  Over 1.5   `{all_probs.get('over_15',0):.0%}`  |  Over 2.5 `{all_probs.get('over_25',0):.0%}`  |  Over 3.5 `{all_probs.get('over_35',0):.0%}`",
        f"  GG         `{all_probs.get('btts_yes',0):.0%}`  |  NG `{all_probs.get('btts_no',0):.0%}`",
        f"  MT 1       `{all_probs.get('ht_home',0):.0%}`  |  MT X `{all_probs.get('ht_draw',0):.0%}`  |  MT 2 `{all_probs.get('ht_away',0):.0%}`",
        f"  Corners +9.5 `{all_probs.get('corners_over_95',0):.0%}`  |  Cartons +2.5 `{all_probs.get('cards_over_25',0):.0%}`",
    ]

    # Signaux
    if signals:
        lines += ["", f"💡 *{len(signals)} SIGNAL(S) RETENU(S) :*"]
        for s in signals:
            gicon   = GRADE_ICONS.get(s.get("grade","B"), "🔵")
            vicon   = VERDICT_ICONS.get(s.get("verdict","SMALL_BET"), "🟡")
            lines.append(
                f"  {gicon} {vicon} *{s['label']}* @ `{s['fair_odd']:.2f}`\n"
                f"     P={s['prob']:.0%}  Edge=`{s['edge']:.1%}`  Mise=`{s['stake_pct']:.1%}` BK  [{s.get('verdict','?')}]"
            )
        total_exp = sum(s.get("stake_pct",0) for s in signals)
        lines += ["", f"💰 *Exposition : {total_exp:.1%} / 12% max*"]
    else:
        lines += ["", "🚫 *Aucun signal — DCS insuffisant*"]

    lines += ["", "—", "_APEX-OMEGA De1_"]
    return "\n".join(lines)


def build_daily_summary(matchday, all_signals, total_exp) -> str:
    lines = [
        f"📊 *RÉSUMÉ APEX BL — J{matchday}*",
        f"📅 {datetime.utcnow().strftime('%d/%m/%Y')}",
        "",
        f"Signaux   : *{len(all_signals)}* / 4 max",
        f"Exposition: *{total_exp:.1%}* / 12% max",
        "",
    ]
    for s in all_signals:
        lines.append(
            f"  {GRADE_ICONS.get(s.get('grade','B'),'🔵')} "
            f"{s['label']} [{s.get('home','?')} vs {s.get('away','?')}] "
            f"@ `{s.get('fair_odd',0):.2f}` ({s.get('stake_pct',0):.1%})"
        )
    lines += ["", "_Prochain scan : 07:00 UTC_"]
    return "\n".join(lines)


def build_audit_report(matchday, signals, results) -> str:
    lines = [
        f"📋 *AUDIT POST-MATCH — J{matchday}*",
        f"📅 {datetime.utcnow().strftime('%d/%m/%Y')}", "",
    ]
    pl_total, wins = 0.0, 0
    for s in signals:
        fid = s.get("fixture_id")
        res = results.get(fid, {})
        hg, ag = res.get("home_goals",0), res.get("away_goals",0)
        won = _signal_won(s["market"], hg, ag)
        if won:
            pl = s["stake_pct"] * (s.get("fair_odd",2) - 1)
            wins += 1
            r = f"✅ +{pl:.2%}"
        else:
            pl = -s["stake_pct"]
            r  = f"❌ -{s['stake_pct']:.2%}"
        pl_total += pl
        lines.append(
            f"  {GRADE_ICONS.get(s.get('grade','B'),'•')} "
            f"{s['label']} [{s.get('home','?')} {hg}-{ag} {s.get('away','?')}] {r}"
        )
    n = len(signals)
    sign = "+" if pl_total >= 0 else ""
    lines += [
        "",
        f"*Résultat : {wins}V/{n-wins}D — {wins/n*100:.0f}%* taux de réussite" if n else "*Aucun signal*",
        f"*P&L : {sign}{pl_total:.2%}*",
    ]
    return "\n".join(lines)


def _signal_won(market, hg, ag):
    t = hg + ag
    m = {
        "1x2_home":hg>ag, "1x2_draw":hg==ag, "1x2_away":ag>hg,
        "dc_1x":hg>=ag,   "dc_x2":ag>=hg,    "dc_12":hg!=ag,
        "over_05":t>0, "over_15":t>1, "over_25":t>2, "over_35":t>3, "over_45":t>4,
        "under_05":t<1,"under_15":t<2,"under_25":t<3,"under_35":t<4,
        "btts_yes":hg>0 and ag>0, "btts_no":hg==0 or ag==0,
        "dnb_home":hg>ag, "dnb_away":ag>hg,
        "home_over_05":hg>0,"home_over_15":hg>1,"away_over_05":ag>0,"away_over_15":ag>1,
        "ht_home":hg>ag,"ht_draw":hg==ag,"ht_away":ag>hg,
    }
    return m.get(market, False)
