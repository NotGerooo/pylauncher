"""Settings — JSON-backed, sin boilerplate."""
import json
from config.constants import DATA_DIR

_DEFAULTS = {
    "ram_mb":       2048,
    "java_path":    "",
    "username":     "Player",
    "last_version": "1.20.4",
    "github_sync":  True,
    "sync_dir":     "",    # ruta local del repo git a sincronizar
}

_FILE = DATA_DIR / "settings.json"


class Settings:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._d = {**_DEFAULTS, **self._load()}

    def _load(self) -> dict:
        try:
            return json.loads(_FILE.read_text())
        except Exception:
            return {}

    def save(self):
        _FILE.write_text(json.dumps(self._d, indent=2))

    def get(self, key: str, default=None):
        return self._d.get(key, default)

    def set(self, key: str, val):
        self._d[key] = val
        self.save()

    def __getattr__(self, key):
        if key.startswith("_"): raise AttributeError(key)
        return self._d.get(key)
