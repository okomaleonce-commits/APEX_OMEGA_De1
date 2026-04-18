"""
APEX_OMEGA_De1 · Storage — Outcomes post-match /data/outcomes/
"""
from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path
from config.settings import OUTCOMES_DIR

logger = logging.getLogger(__name__)


class OutcomesRepo:

    def __init__(self):
        OUTCOMES_DIR.mkdir(parents=True, exist_ok=True)

    def _path(self, matchday: int) -> Path:
        return OUTCOMES_DIR / f"J{matchday:02d}.json"

    def save_outcome(self, matchday: int, fixture_id: int,
                     home_goals: int, away_goals: int,
                     home_team: str, away_team: str) -> None:
        path     = self._path(matchday)
        existing = self._load(path)
        record   = {
            "fixture_id": fixture_id,
            "home_team":  home_team,
            "away_team":  away_team,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "total":      home_goals + away_goals,
            "date":       datetime.utcnow().strftime("%Y-%m-%d"),
        }
        ids = {r.get("fixture_id") for r in existing}
        if fixture_id not in ids:
            existing.append(record)
            path.write_text(json.dumps(existing, ensure_ascii=False, indent=2))

    def get_matchday(self, matchday: int) -> list[dict]:
        return self._load(self._path(matchday))

    def get_result(self, matchday: int, fixture_id: int) -> dict | None:
        for r in self.get_matchday(matchday):
            if r.get("fixture_id") == fixture_id:
                return r
        return None

    def _load(self, path: Path) -> list[dict]:
        if not path.exists(): return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"outcomes load {path}: {e}")
            return []
