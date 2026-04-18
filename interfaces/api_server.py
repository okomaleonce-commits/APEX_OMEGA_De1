"""
APEX_OMEGA_De1 · API FastAPI — health + status
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from datetime import datetime

app = FastAPI(title="APEX-OMEGA Bundesliga", version="1.4.0")


@app.get("/")
async def root():
    return {"bot": "APEX-OMEGA-De1", "version": "1.4.0", "status": "running"}


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "ts": datetime.utcnow().isoformat()})


@app.get("/status")
async def status():
    try:
        from storage.signals_repo import SignalsRepo
        repo   = SignalsRepo()
        today  = repo.get_today()
        exp    = sum(s.get("stake_pct", 0) for s in today)
        return JSONResponse({
            "signals_today":    len(today),
            "exposure_today":   round(exp, 4),
            "last_signal_time": today[-1].get("created_at") if today else None,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
