# utils/icon_cache.py
import os
import json
import threading
from collections import deque

_CACHE_FILE = os.path.join(os.path.expanduser("~"), ".pylauncher", "icon_cache.json")
_lock = threading.Lock()


def _load() -> dict:
    try:
        with open(_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict):
    try:
        os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
        tmp = _CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, _CACHE_FILE)
    except Exception:
        pass


def _migrate(data: dict) -> dict:
    """Elimina entradas con formato viejo (sin prefijo mod:/author:)."""
    return {k: v for k, v in data.items() 
            if k.startswith("mod:") or k.startswith("author:")}

_MEM: dict = _migrate(_load())


def _get_snapshot():
    with _lock:
        return dict(_MEM)


def _write_async():
    """Guarda en background sin bloquear."""
    threading.Thread(target=_save, args=(_get_snapshot(),), daemon=True).start()


# ── Iconos de mods (keyed by sha1) ───────────────────────────────────────────
def get(sha1: str) -> dict | None:
    with _lock:
        return _MEM.get(f"mod:{sha1}")


def set(sha1: str, icon_url: str | None, project_id: str = ""):
    with _lock:
        _MEM[f"mod:{sha1}"] = {"icon_url": icon_url, "project_id": project_id}
    _write_async()


def has(sha1: str) -> bool:
    with _lock:
        return f"mod:{sha1}" in _MEM


# ── Avatares de autores ───────────────────────────────────────────────────────
def get_author(key: str) -> dict | None:
    with _lock:
        return _MEM.get(f"author:{key}")


def set_author(key: str, avatar_url: str | None, extra: dict = None):
    with _lock:
        _MEM[f"author:{key}"] = {"avatar_url": avatar_url, **(extra or {})}
    _write_async()