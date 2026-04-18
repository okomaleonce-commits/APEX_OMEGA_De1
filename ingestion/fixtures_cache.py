"""
APEX_OMEGA_De1 · Cache fixtures — protège le quota API-Football
Plan gratuit : 100 req/jour → cache TTL 2h sur /data/cache/
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from config.settings import BASE_DATA_DIR

logger = logging.getLogger(__name__)
CACHE_DIR = BASE_DATA_DIR / "cache"
CACHE_TTL_HOURS = 2   # refrais toutes les 2h max


def _cache_path(key: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{key}.json"


def get_cached(key: str) -> list | None:
    """Retourne les données cachées si elles sont encore fraîches."""
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        cached_at = datetime.fromisoformat(data["cached_at"])
        if datetime.utcnow() - cached_at < timedelta(hours=CACHE_TTL_HOURS):
            logger.info(f"Cache HIT [{key}] — {len(data['fixtures'])} fixtures "
                        f"(cached {cached_at.strftime('%H:%M')} UTC)")
            return data["fixtures"]
        logger.info(f"Cache EXPIRED [{key}]")
        return None
    except Exception:
        return None


def set_cache(key: str, fixtures: list) -> None:
    """Sauvegarde les fixtures en cache."""
    path = _cache_path(key)
    try:
        path.write_text(json.dumps({
            "cached_at": datetime.utcnow().isoformat(),
            "fixtures":  fixtures,
        }, ensure_ascii=False))
        logger.info(f"Cache SET [{key}] — {len(fixtures)} fixtures")
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")


def clear_cache(key: str = None) -> None:
    """Vide le cache (un fichier ou tout)."""
    if key:
        p = _cache_path(key)
        if p.exists():
            p.unlink()
    else:
        for p in CACHE_DIR.glob("*.json"):
            p.unlink()
        logger.info("Cache vidé")
