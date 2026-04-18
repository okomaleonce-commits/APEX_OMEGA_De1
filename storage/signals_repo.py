"""
APEX_OMEGA_De1 · Storage — Signaux persistants sur /data/signals/
Format JSON par journée.
"""
from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from config.settings import SIGNALS_DIR

logger = logging.getLogger(__name__)


class SignalsRepo:

    def __init__(self):
        SIGNALS_DIR.mkdir(parents=True, exist_ok=True)

    def _path(self, date_str: str | None = None) -> Path:
        date_str = date_str or datetime.utcnow().strftime("%Y-%m-%d")
        return SIGNALS_DIR / f"{date_str}.json"

    def save(self, signal: dict) -> str:
        """Sauvegarde un signal, retourne l'ID généré."""
        if not signal.get("id"):
            signal["id"] = str(uuid.uuid4())
        signal.setdefault("created_at", datetime.utcnow().isoformat())
        path     = self._path(signal.get("date"))
        existing = self._load(path)
        # éviter les doublons
        ids = {s.get("id") for s in existing}
        if signal["id"] not in ids:
            existing.append(signal)
            self._write(path, existing)
        return signal["id"]

    def get_by_date(self, date_str: str | None = None) -> list[dict]:
        return self._load(self._path(date_str))

    def get_today(self) -> list[dict]:
        return self._load(self._path())

    def update_result(self, signal_id: str, home_goals: int, away_goals: int,
                      date_str: str | None = None) -> None:
        """Enregistre le score réel pour l'audit post-match."""
        path    = self._path(date_str)
        signals = self._load(path)
        for s in signals:
            if s.get("id") == signal_id:
                s["result"] = {
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "audited_at": datetime.utcnow().isoformat(),
                }
                break
        self._write(path, signals)

    def list_dates(self) -> list[str]:
        return sorted(p.stem for p in SIGNALS_DIR.glob("*.json"))

    def _load(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error {path}: {e}")
            return []

    def _write(self, path: Path, data: list) -> None:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
