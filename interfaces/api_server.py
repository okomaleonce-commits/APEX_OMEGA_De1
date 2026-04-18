"""
APEX_OMEGA_De1 · API FastAPI
Endpoints : health · status · scan manuel · audit manuel · signaux historiques
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
app = FastAPI(title="APEX-OMEGA Bundesliga", version="1.4.0")

# Pipeline instance partagée (injectée depuis main.py)
_pipeline = None

def set_pipeline(pipeline) -> None:
    global _pipeline
    _pipeline = pipeline


# ═══════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════
@app.get("/")
async def root():
    return {
        "bot":     "APEX-OMEGA-De1",
        "version": "1.4.0",
        "league":  "Bundesliga (De1)",
        "status":  "running",
        "ts":      datetime.utcnow().isoformat(),
    }


@app.get("/health")
async def health():
    return JSONResponse({
        "status": "ok",
        "ts":     datetime.utcnow().isoformat(),
    })


# ═══════════════════════════════════════════════════════
# STATUS — signaux du jour
# ═══════════════════════════════════════════════════════
@app.get("/status")
async def status():
    try:
        from storage.signals_repo import SignalsRepo
        repo   = SignalsRepo()
        today  = repo.get_today()
        exp    = sum(s.get("stake_pct", 0) for s in today)
        return JSONResponse({
            "date":             datetime.utcnow().strftime("%Y-%m-%d"),
            "signals_today":    len(today),
            "exposure_today":   f"{exp:.1%}",
            "anti_under_pause": _pipeline._anti_under_remaining if _pipeline else 0,
            "last_signal":      today[-1].get("created_at", "") if today else None,
            "signals":          [
                {
                    "match":   s.get("match"),
                    "market":  s.get("market"),
                    "edge":    f"{s.get('edge', 0):.1%}",
                    "stake":   f"{s.get('stake_pct', 0):.1%}",
                    "verdict": s.get("verdict"),
                    "odd":     s.get("fair_odd"),
                }
                for s in today
            ],
        })
    except Exception as e:
        logger.error(f"/status error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ═══════════════════════════════════════════════════════
# SCAN MANUEL — déclenche daily_scan() immédiatement
# ═══════════════════════════════════════════════════════
@app.post("/scan")
async def trigger_scan(background_tasks: BackgroundTasks):
    """
    Déclenche manuellement le daily_scan() en tâche de fond.
    Utile pour tester sans attendre 07:00 UTC.
    """
    if not _pipeline:
        raise HTTPException(status_code=503, detail="Pipeline non initialisé")
    background_tasks.add_task(_run_scan)
    return JSONResponse({
        "status":  "scan lancé en arrière-plan",
        "ts":      datetime.utcnow().isoformat(),
        "check":   "GET /status dans 60s pour voir les signaux",
    })

async def _run_scan():
    try:
        await _pipeline.daily_scan()
    except Exception as e:
        logger.error(f"Scan manuel erreur: {e}", exc_info=True)


# ═══════════════════════════════════════════════════════
# AUDIT MANUEL — déclenche run_audit() immédiatement
# ═══════════════════════════════════════════════════════
@app.post("/audit")
async def trigger_audit(background_tasks: BackgroundTasks):
    """Déclenche l'audit post-match de la veille manuellement."""
    if not _pipeline:
        raise HTTPException(status_code=503, detail="Pipeline non initialisé")
    background_tasks.add_task(_run_audit)
    return JSONResponse({
        "status": "audit lancé en arrière-plan",
        "ts":     datetime.utcnow().isoformat(),
    })

async def _run_audit():
    try:
        await _pipeline.run_audit()
    except Exception as e:
        logger.error(f"Audit manuel erreur: {e}", exc_info=True)


# ═══════════════════════════════════════════════════════
# HISTORIQUE — signaux d'une date
# ═══════════════════════════════════════════════════════
@app.get("/signals/{date_str}")
async def get_signals(date_str: str):
    """
    Retourne les signaux d'une date.
    Format date : YYYY-MM-DD
    """
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Format date invalide. Attendu: YYYY-MM-DD")
    try:
        from storage.signals_repo import SignalsRepo
        signals = SignalsRepo().get_by_date(date_str)
        pl = sum(
            s.get("stake_pct", 0) * (s.get("fair_odd", 2) - 1)
            if s.get("result", {}).get("won") else -s.get("stake_pct", 0)
            for s in signals
            if "result" in s
        )
        return JSONResponse({
            "date":    date_str,
            "count":   len(signals),
            "pl":      f"{pl:+.2%}" if any("result" in s for s in signals) else "en attente",
            "signals": signals,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ═══════════════════════════════════════════════════════
# BACKTEST RAPIDE — 7 derniers jours
# ═══════════════════════════════════════════════════════
@app.get("/perf")
async def performance():
    """Résumé de performance des 7 derniers jours."""
    try:
        from storage.signals_repo import SignalsRepo
        repo   = SignalsRepo()
        dates  = repo.list_dates()[-7:]
        total_signals, wins, pl = 0, 0, 0.0

        rows = []
        for d in dates:
            sigs = repo.get_by_date(d)
            for s in sigs:
                total_signals += 1
                res = s.get("result", {})
                if res.get("won"):
                    gain = s.get("stake_pct", 0) * (s.get("fair_odd", 2) - 1)
                    wins += 1
                    pl   += gain
                elif "won" in res:
                    pl -= s.get("stake_pct", 0)
            rows.append({"date": d, "signals": len(sigs)})

        rate = wins / max(total_signals, 1) * 100
        return JSONResponse({
            "period":         f"7 derniers jours",
            "total_signals":  total_signals,
            "win_rate":       f"{rate:.0f}%",
            "pl_total":       f"{pl:+.2%}",
            "by_day":         rows,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
