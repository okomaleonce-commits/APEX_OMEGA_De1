"""APEX_OMEGA_De1 · FastAPI health endpoint"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from storage.calibration_repo import load_metrics

app = FastAPI(title="APEX-OMEGA De1", version="2.3.0")

@app.get("/health")
async def health():
    return JSONResponse({"status":"ok","bot":"apex-de1-v2.3"})

@app.get("/metrics")
async def metrics():
    return JSONResponse(load_metrics())
