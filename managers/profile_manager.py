"""Gestión de perfiles (versión + usuario + RAM)."""
import json, uuid
from dataclasses import dataclass, field, asdict
from config.constants import DATA_DIR
from utils.helpers import get_logger

log = get_logger("profiles")
_FILE = DATA_DIR / "profiles.json"


@dataclass
class Profile:
    id:       str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name:     str = "Default"
    version:  str = "1.20.4"
    username: str = "Player"
    ram_mb:   int = 2048


class ProfileManager:
    def __init__(self):
        self._profiles:  list[Profile] = []
        self._active_id: str = ""
        self._load()

    def _load(self):
        try:
            data = json.loads(_FILE.read_text())
            self._profiles  = [Profile(**p) for p in data.get("profiles", [])]
            self._active_id = data.get("active", "")
        except Exception:
            pass

    def save(self):
        _FILE.parent.mkdir(parents=True, exist_ok=True)
        _FILE.write_text(json.dumps({
            "profiles": [asdict(p) for p in self._profiles],
            "active":   self._active_id,
        }, indent=2))

    # ── API ───────────────────────────────────────────────
    def all(self) -> list[Profile]:
        return self._profiles

    def active(self) -> Profile | None:
        return next((p for p in self._profiles if p.id == self._active_id), None)

    def add(self, profile: Profile):
        self._profiles.append(profile)
        if not self._active_id:
            self._active_id = profile.id
        self.save()

    def set_active(self, pid: str):
        self._active_id = pid
        self.save()

    def ensure_default(self) -> Profile:
        """Si no hay perfiles, crea uno por defecto."""
        if not self._profiles:
            p = Profile()
            self.add(p)
        return self.active()
