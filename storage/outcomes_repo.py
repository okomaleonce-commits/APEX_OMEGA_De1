"""APEX_OMEGA_De1 · Outcomes Repo — /data/outcomes/"""
import json
from datetime import datetime
from pathlib import Path
from config.settings import OUTCOMES_DIR

class OutcomesRepo:
    def _path(self, d=None):
        return OUTCOMES_DIR / f"{d or datetime.utcnow().strftime('%Y-%m-%d')}.json"
    def _load(self, p):
        return json.loads(p.read_text()) if p.exists() else []
    def save(self, outcome):
        p = self._path()
        data = self._load(p)
        data.append({**outcome, "ts": datetime.utcnow().isoformat()})
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    def get_all(self):
        results = []
        for f in sorted(OUTCOMES_DIR.glob("*.json")):
            results.extend(self._load(f))
        return results
