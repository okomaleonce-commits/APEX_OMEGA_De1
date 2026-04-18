"""APEX_OMEGA_De1 · SignalsRepo — Persistance /data/signals/ (Render Disk)"""
import json, logging
from datetime import datetime
from pathlib import Path
from config.settings import SIGNALS_DIR

logger = logging.getLogger(__name__)

class SignalsRepo:
    def __init__(self):
        SIGNALS_DIR.mkdir(parents=True, exist_ok=True)

    def _path(self, date_str: str = None) -> Path:
        return SIGNALS_DIR / f"{date_str or datetime.utcnow().strftime('%Y-%m-%d')}.json"

    def save(self, signal: dict) -> None:
        path = self._path()
        data = self._load(path)
        data.append(signal)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        logger.info(f"Signal sauvegardé: {signal.get('match','?')} {signal.get('market','?')}")

    def today(self) -> list:
        return self._load(self._path())

    def by_date(self, date_str: str) -> list:
        return self._load(self._path(date_str))

    def _load(self, path: Path) -> list:
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text())
        except:
            return []

    def update_outcome(self, signal_id: str, result: dict) -> None:
        path = self._path(result.get("date"))
        data = self._load(path)
        for s in data:
            if s.get("id") == signal_id:
                s["result"] = result
                s["audited"] = True
                break
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
