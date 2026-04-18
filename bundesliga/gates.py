"""
APEX-OMEGA Bundesliga — Gates analytiques v2.3
12 gates séquentiels B-0 à B-11
Chaque gate est un filtre binaire ou un modificateur de coefficients.
Un gate BLOQUANT (retourne False) stoppe l'analyse immédiatement.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from bundesliga.config_v2_3 import (
    CLUBS, MORATORIUMS_FIXED, FLAGS,
    LAMBDA_UCL_SAM_AFTER_WED, LAMBDA_UCL_FRI_AFTER_WED,
    LAMBDA_UCL_ELIMINATION, LAMBDA_UCL_BIG_WIN_WE,
    LAMBDA_UEL_SAM_AFTER_WED, LAMBDA_UEL_FRI_AFTER_WED,
    LAMBDA_EDE_2_DEF, LAMBDA_EDE_3_DEF,
    LAMBDA_ENJEU_UCL_J25, LAMBDA_ENJEU_UCL_J29, LAMBDA_ENJEU_REL,
    LAMBDA_REBOUND_HOME, LAMBDA_REBOUND_SERIE,
    ANTI_UNDER_TRIGGER,
    DCS_THRESHOLDS, SESSION_MAX_SIGNALS, SESSION_MAX_EXPOSURE,
    OVER35_PRINCIPAL,
)


@dataclass
class GateContext:
    """Contexte complet d'un match transmis à tous les gates."""
    # ── Match
    home_team:          str = ""
    away_team:          str = ""
    matchday:           int = 0
    kickoff_utc:        str = ""

    # ── Gates UCL/UEL
    home_days_since_ucl:    Optional[int] = None
    away_days_since_ucl:    Optional[int] = None
    home_days_since_uel:    Optional[int] = None
    away_days_since_uel:    Optional[int] = None
    home_ucl_eliminated:    bool = False
    away_ucl_eliminated:    bool = False
    home_ucl_big_win:       bool = False   # victoire large (≥3 buts) en UCL

    # ── Absences
    away_absent_defenders:  int  = 0
    away_gk_experienced:    bool = True    # GK tit. disponible
    away_goals_conceded_3:  int  = 0       # buts concédés 3 derniers matchs away

    # ── Enjeux
    away_ucl_position:      bool = False   # dans Top 4 UCL à J25+
    away_attackers_8g:      int  = 0       # attaquants avec ≥8 buts
    away_relegation_direct: bool = False   # relégation directe J28+
    home_relegation_direct: bool = False

    # ── Forme
    home_win_rate_8m:       float = 1.0
    away_win_rate_8m:       float = 1.0
    home_rebound_rate:      float = 0.0    # taux rebond après défaite
    home_winless_streak:    int   = 0      # série sans victoire

    # ── Session
    anti_under_active:      bool  = False
    anti_under_remaining:   int   = 0
    session_signals:        int   = 0
    session_exposure:       float = 0.0

    # ── H2H & stats
    h2h_avg_goals:          float = 0.0
    home_over25_pct:        float = 0.0
    away_over25_pct:        float = 0.0
    home_avg_conceded:      float = 1.56
    away_avg_conceded:      float = 1.56
    home_avg_scored:        float = 1.56
    away_avg_scored:        float = 1.56

    # ── Résultats calculés (remplis par les gates)
    home_xg_mult:     float = 1.0
    away_xg_mult:     float = 1.0
    kelly_mult:       float = 1.0
    rebound_coeff:    float = 0.0
    ais_def_away_mult:float = 1.0
    enjeu_att_away_mult: float = 1.0

    forbidden_markets: list = field(default_factory=list)
    active_flags:      list = field(default_factory=list)
    warnings:          list = field(default_factory=list)
    blocked:           bool = False
    block_reason:      str  = ""


def run_all_gates(ctx: GateContext) -> GateContext:
    """
    Exécute les 12 gates séquentiellement.
    Retourne le contexte enrichi ou bloqué.
    """
    gates = [
        gate_b0_perimetre,
        gate_b1_session_cap,
        gate_b2_calendrier,
        gate_b3_h2h_trauma,
        gate_b4_rotation_ucl,
        gate_b5_rotation_uel,
        gate_b6_moratoriums_fixes,
        gate_b7_enjeu_actifs,
        gate_b8_ede,
        gate_b9_rebound,
        gate_b10_anti_under,
        gate_b11_close_gap_top3,
    ]
    for gate_fn in gates:
        ctx = gate_fn(ctx)
        if ctx.blocked:
            return ctx
    return ctx


# ══════════════════════════════════════════════════════════════════
# B-0 : PÉRIMÈTRE — filtrage ligue Bundesliga uniquement
# ══════════════════════════════════════════════════════════════════
def gate_b0_perimetre(ctx: GateContext) -> GateContext:
    """
    Gate B-0 : Vérification que home et away sont bien
    des clubs Bundesliga 2025-26 connus.
    BLOQUANT si club inconnu.
    """
    if ctx.home_team not in CLUBS:
        ctx.blocked     = True
        ctx.block_reason = f"B-0 : Club inconnu — {ctx.home_team}"
        return ctx
    if ctx.away_team not in CLUBS:
        ctx.blocked     = True
        ctx.block_reason = f"B-0 : Club inconnu — {ctx.away_team}"
        return ctx
    return ctx


# ══════════════════════════════════════════════════════════════════
# B-1 : CAP SESSION — 4 paris max, 12% exposition
# ══════════════════════════════════════════════════════════════════
def gate_b1_session_cap(ctx: GateContext) -> GateContext:
    """
    Gate B-1 : Cap global de session atteint → blocage immédiat.
    BLOQUANT si cap déjà atteint.
    """
    if ctx.session_signals >= SESSION_MAX_SIGNALS:
        ctx.blocked     = True
        ctx.block_reason = f"B-1 : Cap session atteint ({ctx.session_signals} signaux)"
        return ctx
    if ctx.session_exposure >= SESSION_MAX_EXPOSURE:
        ctx.blocked     = True
        ctx.block_reason = f"B-1 : Exposition maximale atteinte ({ctx.session_exposure:.1%})"
        return ctx
    return ctx


# ══════════════════════════════════════════════════════════════════
# B-2 : CALENDRIER — J34 / post-Winterpause
# ══════════════════════════════════════════════════════════════════
def gate_b2_calendrier(ctx: GateContext) -> GateContext:
    """
    Gate B-2 : Ajustements saisonniers.
    NON BLOQUANT — modifie Kelly mult et ajoute flags.
    """
    md = ctx.matchday
    if md == 34:
        ctx.kelly_mult *= 0.5
        ctx.active_flags.append("J34_SIMULTANEOUS")
        ctx.warnings.append("J34 : stake ×0.5 (matchs simultanés)")

    if 17 <= md <= 19:
        ctx.active_flags.append("WINTERPAUSE_POST")
        ctx.warnings.append("Post-Winterpause J17-19 : DCS −5 pts auto")

    return ctx


# ══════════════════════════════════════════════════════════════════
# B-3 : H2H TRAUMA — Effets psychologiques H2H historiques
# ══════════════════════════════════════════════════════════════════
def gate_b3_h2h_trauma(ctx: GateContext) -> GateContext:
    """
    Gate B-3 : Détecte les dynamiques H2H extrêmes.
    Si H2H moyen ≥ 4.2G → flag RUPTURE + Over 3.5 priorisé.
    Si H2H moyen ≤ 1.5G → flag VARIANCE + U2.5 surveillé.
    NON BLOQUANT.
    """
    avg = ctx.h2h_avg_goals
    if avg >= 4.2:
        ctx.active_flags.append("RUPTURE")
        ctx.warnings.append(
            f"B-3 H2H TRAUMA : avg {avg:.1f}G/match — Over 3.5 prioritaire"
        )
    elif avg <= 1.5 and avg > 0:
        ctx.active_flags.append("VARIANCE")
        ctx.warnings.append(
            f"B-3 H2H TRAUMA : avg {avg:.1f}G/match — profil très fermé"
        )
    return ctx


# ══════════════════════════════════════════════════════════════════
# B-4 : ROTATION UCL
# ══════════════════════════════════════════════════════════════════
def gate_b4_rotation_ucl(ctx: GateContext) -> GateContext:
    """
    Gate B-4 : Ajustement xG selon proximité UCL.
    NON BLOQUANT — modifie home_xg_mult ou away_xg_mult.
    """
    # ── Domicile
    if ctx.home_days_since_ucl is not None:
        days = ctx.home_days_since_ucl
        if days <= 3:
            cut = LAMBDA_UCL_FRI_AFTER_WED
            ctx.warnings.append(f"B-4 Gate UCL home CRITIQUE (72h) : xG ×{1+cut:.2f}")
        elif days <= 4:
            cut = LAMBDA_UCL_SAM_AFTER_WED
            ctx.warnings.append(f"B-4 Gate UCL home actif (96h) : xG ×{1+cut:.2f}")
        else:
            cut = 0.0
        ctx.home_xg_mult *= (1 + cut)

        if ctx.home_ucl_eliminated:
            ctx.kelly_mult *= 0.75
            ctx.active_flags.append("UCL_ELIMINATION")
            ctx.warnings.append(
                "B-4 Élimination UCL home : Kelly ×0.75 | risque effondrement MT2"
            )
        elif ctx.home_ucl_big_win:
            ctx.home_xg_mult *= (1 + LAMBDA_UCL_BIG_WIN_WE)
            ctx.warnings.append("B-4 Victoire UCL large → rotation partielle probable")

    # ── Extérieur
    if ctx.away_days_since_ucl is not None:
        days = ctx.away_days_since_ucl
        cut  = LAMBDA_UCL_FRI_AFTER_WED if days <= 3 else LAMBDA_UCL_SAM_AFTER_WED
        ctx.away_xg_mult *= (1 + cut)
        if ctx.away_ucl_eliminated:
            ctx.kelly_mult *= 0.75
            ctx.active_flags.append("UCL_ELIMINATION")

    return ctx


# ══════════════════════════════════════════════════════════════════
# B-5 : ROTATION UEL / UECL
# ══════════════════════════════════════════════════════════════════
def gate_b5_rotation_uel(ctx: GateContext) -> GateContext:
    """
    Gate B-5 : Ajustement xG selon proximité UEL/UECL.
    NON BLOQUANT.
    """
    home_p = CLUBS.get(ctx.home_team, {})
    away_p = CLUBS.get(ctx.away_team, {})

    if ctx.home_days_since_uel is not None and (
        home_p.get("uel_rotation") or home_p.get("uecl_rotation")
    ):
        days = ctx.home_days_since_uel
        cut  = LAMBDA_UEL_FRI_AFTER_WED if days <= 3 else LAMBDA_UEL_SAM_AFTER_WED
        ctx.home_xg_mult *= (1 + cut)
        ctx.active_flags.append("UEL_FATIGUE")
        ctx.warnings.append(f"B-5 Gate UEL home : xG ×{1+cut:.2f}")

    if ctx.away_days_since_uel is not None and (
        away_p.get("uel_rotation") or away_p.get("uecl_rotation")
    ):
        days = ctx.away_days_since_uel
        cut  = LAMBDA_UEL_FRI_AFTER_WED if days <= 3 else LAMBDA_UEL_SAM_AFTER_WED
        ctx.away_xg_mult *= (1 + cut)
        ctx.active_flags.append("UEL_FATIGUE")
        ctx.warnings.append(f"B-5 Gate UEL away : xG ×{1+cut:.2f}")

    return ctx


# ══════════════════════════════════════════════════════════════════
# B-6 : MORATORIUMS FIXES — clubs + enjeux relégation
# ══════════════════════════════════════════════════════════════════
def gate_b6_moratoriums_fixes(ctx: GateContext) -> GateContext:
    """
    Gate B-6 : Applique les moratoriums permanents par club.
    NON BLOQUANT — interdit certains marchés.
    """
    home = ctx.home_team
    away = ctx.away_team
    md   = ctx.matchday
    fm   = ctx.forbidden_markets

    # U2.5 domicile interdit
    if home in MORATORIUMS_FIXED["u25_home_forbidden"]:
        if "under_25" not in fm:
            fm.append("under_25")
            ctx.warnings.append(f"B-6 U2.5 INTERDIT domicile ({home})")

    # U2.5 global interdit
    if away in MORATORIUMS_FIXED["u25_global_forbidden"]:
        if "under_25" not in fm:
            fm.append("under_25")
            ctx.warnings.append(f"B-6 U2.5 INTERDIT ({away})")

    # U2.5 fortement déconseillé
    if home in MORATORIUMS_FIXED["u25_strongly_discouraged"] or \
       away in MORATORIUMS_FIXED["u25_strongly_discouraged"]:
        ctx.warnings.append("B-6 U2.5 FORTEMENT DÉCONSEILLÉ — edge ≥15% obligatoire")

    # BTTS Non interdit
    for team in [home, away]:
        if team in MORATORIUMS_FIXED["btts_no_forbidden"]:
            if "btts_no" not in fm:
                fm.append("btts_no")
                ctx.warnings.append(f"B-6 BTTS Non INTERDIT ({team})")

    # Enjeu relégation J28+ → BTTS Non interdit + ENJEU flag
    home_p = CLUBS.get(home, {})
    away_p = CLUBS.get(away, {})
    if md >= 28 and (home_p.get("relegation_zone") or away_p.get("relegation_zone")):
        if "btts_no" not in fm:
            fm.append("btts_no")
        ctx.active_flags.append("RELEGATION_TERROR")
        ctx.warnings.append("B-6 BTTS Non INTERDIT — enjeu relégation directe J28+")

    # J34 : interdire BTTS Non
    if md == 34:
        if "btts_no" not in fm:
            fm.append("btts_no")

    return ctx


# ══════════════════════════════════════════════════════════════════
# B-7 : ENJEU_ATT_AWAY — boost offensif équipes en lutte UCL
# ══════════════════════════════════════════════════════════════════
def gate_b7_enjeu_actifs(ctx: GateContext) -> GateContext:
    """
    Gate B-7 : Détecte l'enjeu UCL/relégation côté extérieur.
    NON BLOQUANT — booste away_xg et interdit U2.5.
    """
    md = ctx.matchday

    if md >= 25 and ctx.away_ucl_position and ctx.away_attackers_8g >= 2:
        boost = LAMBDA_ENJEU_UCL_J29 if md >= 29 else LAMBDA_ENJEU_UCL_J25
        ctx.enjeu_att_away_mult = 1 + boost
        ctx.active_flags.append("UCL_CHASER")
        if "under_25" not in ctx.forbidden_markets:
            ctx.forbidden_markets.append("under_25")
        ctx.warnings.append(
            f"B-7 ENJEU_ATT_AWAY UCL : away_xg ×{ctx.enjeu_att_away_mult:.2f} | U2.5 INTERDIT"
        )

    if md >= 28 and ctx.away_relegation_direct:
        ctx.enjeu_att_away_mult = max(ctx.enjeu_att_away_mult, 1 + LAMBDA_ENJEU_REL)
        ctx.active_flags.append("RELEGATION_TERROR")
        ctx.warnings.append(
            f"B-7 ENJEU_ATT_AWAY relégation : away_xg ×{1+LAMBDA_ENJEU_REL:.2f}"
        )

    return ctx


# ══════════════════════════════════════════════════════════════════
# B-8 : EDE — Effondrement Défensif Extérieur
# ══════════════════════════════════════════════════════════════════
def gate_b8_ede(ctx: GateContext) -> GateContext:
    """
    Gate B-8 : Détecte l'effondrement défensif de l'équipe away.
    Conditions : 2/3 parmi (≥2 DC absents, GK pas expérimenté, ≥9 buts concédés/3m away)
    NON BLOQUANT — booste home_xg et interdit U2.5.
    """
    conditions = 0
    if ctx.away_absent_defenders >= 2: conditions += 1
    if not ctx.away_gk_experienced:   conditions += 1
    if ctx.away_goals_conceded_3 >= 9: conditions += 1

    if conditions >= 2:
        boost = (LAMBDA_EDE_3_DEF
                 if ctx.away_absent_defenders >= 3
                 else LAMBDA_EDE_2_DEF)
        ctx.ais_def_away_mult = 1 + boost
        ctx.active_flags.append("EDE_ACTIVE")
        if "under_25" not in ctx.forbidden_markets:
            ctx.forbidden_markets.append("under_25")
        ctx.warnings.append(
            f"B-8 Gate EDE ACTIF ({conditions}/3) : home_xg ×{ctx.ais_def_away_mult:.2f} | U2.5 INTERDIT"
        )

    return ctx


# ══════════════════════════════════════════════════════════════════
# B-9 : REBOUND — Effet rebond domicile
# ══════════════════════════════════════════════════════════════════
def gate_b9_rebound(ctx: GateContext) -> GateContext:
    """
    Gate B-9 : Détecte l'effet rebond post-défaite en domicile.
    REBOUND_COEFF est additif sur home_xg (pas multiplicatif).
    NON BLOQUANT.
    """
    if ctx.home_rebound_rate >= 0.65:
        ctx.rebound_coeff += LAMBDA_REBOUND_HOME
        ctx.warnings.append(
            f"B-9 REBOUND home : +{LAMBDA_REBOUND_HOME} xG additif (rebond {ctx.home_rebound_rate:.0%}/8m)"
        )

    # Série noire ≥ 6 matchs
    if ctx.home_winless_streak >= 6:
        ctx.active_flags.append("VARIANCE")
        ctx.warnings.append(
            f"B-9 SÉRIE NOIRE {ctx.home_winless_streak}M sans victoire — stake réduit"
        )
        ctx.kelly_mult *= 0.80

    return ctx


# ══════════════════════════════════════════════════════════════════
# B-10 : ANTI-UNDER — Pause forcée marchés Under/BTTS Non
# ══════════════════════════════════════════════════════════════════
def gate_b10_anti_under(ctx: GateContext) -> GateContext:
    """
    Gate B-10 : Pause anti-Under active → interdire U2.5 et BTTS Non.
    NON BLOQUANT.
    """
    if ctx.anti_under_active:
        for mkt in ["under_25", "btts_no"]:
            if mkt not in ctx.forbidden_markets:
                ctx.forbidden_markets.append(mkt)
        ctx.active_flags.append("ANTI_UNDER_PAUSE")
        ctx.warnings.append(
            f"B-10 Pause anti-Under ACTIVE — {ctx.anti_under_remaining}J restantes"
        )
    return ctx


# ══════════════════════════════════════════════════════════════════
# B-11 : CLOSE GAP TOP3 — Enjeu titre/Top 3 domicile
# ══════════════════════════════════════════════════════════════════
def gate_b11_close_gap_top3(ctx: GateContext) -> GateContext:
    """
    Gate B-11 : Détecte si l'équipe domicile est en lutte serrée Top 3
    (≤ 3 pts du Top 3 à J27+) → boost motivation offensive.
    NON BLOQUANT — signale le flag UCL_CHASER côté domicile.
    """
    home_p = CLUBS.get(ctx.home_team, {})
    md     = ctx.matchday
    home_in_ucl_race = home_p.get("enjeu_att_away") or home_p.get("tier") in ("S", "A")

    if md >= 27 and home_in_ucl_race:
        ctx.active_flags.append("UCL_CHASER")
        ctx.warnings.append(
            "B-11 CLOSE GAP TOP3 : enjeu UCL domicile détecté — motivation élevée"
        )
    return ctx


# ══════════════════════════════════════════════════════════════════
# HELPER : Résumé gates pour rapport Telegram
# ══════════════════════════════════════════════════════════════════
def gates_summary(ctx: GateContext) -> str:
    """Génère un résumé texte des gates actifs pour le rapport."""
    lines = []
    if ctx.blocked:
        lines.append(f"🚫 BLOQUÉ : {ctx.block_reason}")
        return "\n".join(lines)

    if ctx.active_flags:
        lines.append(f"🚩 Flags : {', '.join(set(ctx.active_flags))}")
    if ctx.forbidden_markets:
        lines.append(f"🔕 Marchés exclus : {', '.join(ctx.forbidden_markets).upper()}")
    for w in ctx.warnings:
        lines.append(f"  ⚠️ {w}")
    lines.append(
        f"📐 Mult. : home ×{ctx.home_xg_mult:.3f} | away ×{ctx.away_xg_mult:.3f} "
        f"| Kelly ×{ctx.kelly_mult:.2f}"
    )
    return "\n".join(lines)


# Alias pour compatibilité pipeline.py
evaluate_all_gates = run_all_gates
