"""APEX_OMEGA_De1 · Calibration Repo — métriques perf"""
import json
from pathlib import Path
from config.settings import CALIBRATION_DIR

METRICS_FILE = CALIBRATION_DIR / "metrics.json"

def load_metrics():
    return json.loads(METRICS_FILE.read_text()) if METRICS_FILE.exists() else {
        "total_signals":0,"wins":0,"losses":0,"pl_total":0.0,
        "anti_under_count":0,"anti_under_remaining":0,
    }

def save_metrics(m):
    METRICS_FILE.write_text(json.dumps(m, indent=2))

def update_after_signal(won: bool, pl: float):
    m = load_metrics()
    m["total_signals"] += 1
    if won: m["wins"] += 1
    else:   m["losses"] += 1
    m["pl_total"] = round(m["pl_total"] + pl, 6)
    save_metrics(m)
