"""
settings.py
-----------
Clase Settings: configuración persistente del launcher.
"""
import json
import os
from config.constants import MC_DEFAULT_MAX_RAM_MB
from utils.logger import get_logger
log = get_logger()

_SETTINGS_FILE = os.path.join("data", "launcher_settings.json")
_DEFAULT_SETTINGS = {
    "minecraft_dir": os.path.join(os.path.expanduser("~"), ".minecraft"),
    "java_path": "",
    "default_ram_mb": MC_DEFAULT_MAX_RAM_MB,
    "last_profile": "",
    "theme": "dark",
    "close_on_launch": False,
    "keep_launcher_open": True,
}


class Settings:
    def __init__(self, settings_file: str = _SETTINGS_FILE):
        self._settings_file = settings_file
        self._data: dict = {}
        self._load()

    @property
    def minecraft_dir(self) -> str:
        return self._data["minecraft_dir"]

    @property
    def versions_dir(self) -> str:
        return os.path.join(self.minecraft_dir, "versions")

    @property
    def libraries_dir(self) -> str:
        return os.path.join(self.minecraft_dir, "libraries")

    @property
    def assets_dir(self) -> str:
        return os.path.join(self.minecraft_dir, "assets")

    @property
    def profiles_dir(self) -> str:
        return os.path.join(self.minecraft_dir, "profiles")

    @property
    def mods_dir(self) -> str:
        return os.path.join(self.minecraft_dir, "mods")

    @property
    def java_path(self) -> str:
        return self._data.get("java_path", "")

    @java_path.setter
    def java_path(self, value: str):
        self._data["java_path"] = value
        self._save()

    @property
    def default_ram_mb(self) -> int:
        return int(self._data.get("default_ram_mb", MC_DEFAULT_MAX_RAM_MB))

    @default_ram_mb.setter
    def default_ram_mb(self, value: int):
        self._data["default_ram_mb"] = value
        self._save()

    @property
    def last_profile(self) -> str:
        return self._data.get("last_profile", "")

    @last_profile.setter
    def last_profile(self, value: str):
        self._data["last_profile"] = value
        self._save()

    @property
    def close_on_launch(self) -> bool:
        return bool(self._data.get("close_on_launch", False))

    @close_on_launch.setter
    def close_on_launch(self, value: bool):
        self._data["close_on_launch"] = value
        self._save()

    def _load(self):
        if os.path.isfile(self._settings_file):
            try:
                with open(self._settings_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data = {**_DEFAULT_SETTINGS, **saved}
                log.debug(f"Configuración cargada desde {self._settings_file}")
                return
            except (json.JSONDecodeError, OSError) as e:
                log.warning(f"Error cargando settings ({e}), usando valores por defecto")
        self._data = dict(_DEFAULT_SETTINGS)
        log.info("Usando configuración por defecto")
        self._save()

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._settings_file), exist_ok=True)
            with open(self._settings_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=4, ensure_ascii=False)
        except OSError as e:
            log.error(f"No se pudo guardar la configuración: {e}")

    def get_all(self) -> dict:
        return dict(self._data)

    def reset_to_defaults(self):
        self._data = dict(_DEFAULT_SETTINGS)
        self._save()

    def __repr__(self) -> str:
        return f"Settings(minecraft_dir={self.minecraft_dir!r})"