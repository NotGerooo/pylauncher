"""profile_manager.py — Gestión de perfiles del launcher."""
import json
import os
import uuid
from datetime import datetime

from config.settings import Settings
from utils.file_utils import ensure_dir
from utils.logger import get_logger

log = get_logger()

_PROFILES_FILE = os.path.join("data", "profiles.json")


class ProfileError(Exception):
    pass


class Profile:
    def __init__(self, name, version_id, game_dir, ram_mb=2048,
                 java_path="", icon="grass", profile_id=None,
                 created_at=None, last_used=None):
        self.id         = profile_id or str(uuid.uuid4())
        self.name       = name
        self.version_id = version_id
        self.game_dir   = game_dir
        self.ram_mb     = ram_mb
        self.java_path  = java_path
        self.icon       = icon
        self.created_at = created_at or datetime.now().isoformat()
        self.last_used  = last_used  or self.created_at

    @property
    def mods_dir(self):    return os.path.join(self.game_dir, "mods")
    @property
    def saves_dir(self):   return os.path.join(self.game_dir, "saves")
    @property
    def config_dir(self):  return os.path.join(self.game_dir, "config")
    @property
    def resourcepacks_dir(self): return os.path.join(self.game_dir, "resourcepacks")
    @property
    def shaderpacks_dir(self):   return os.path.join(self.game_dir, "shaderpacks")
    
    def to_dict(self):
        return {
            "id": self.id, "name": self.name,
            "version_id": self.version_id, "game_dir": self.game_dir,
            "ram_mb": self.ram_mb, "java_path": self.java_path,
            "icon": self.icon, "created_at": self.created_at,
            "last_used": self.last_used,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            name=d["name"], version_id=d["version_id"],
            game_dir=d["game_dir"], ram_mb=d.get("ram_mb", 2048),
            java_path=d.get("java_path", ""), icon=d.get("icon", "grass"),
            profile_id=d.get("id"), created_at=d.get("created_at"),
            last_used=d.get("last_used"),
        )

    def __repr__(self):
        return f"Profile(name={self.name!r}, version={self.version_id!r})"


class ProfileManager:
    def __init__(self, settings: Settings,
                 profiles_file: str = _PROFILES_FILE):
        self._settings      = settings
        self._profiles_file = profiles_file
        self._profiles: dict = {}
        self._load()

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def create_profile(self, name, version_id, ram_mb=None,
                       java_path="", icon="grass",
                       loader_type="vanilla", loader_ver="") -> Profile:
        if self.get_profile_by_name(name):
            raise ProfileError(f"Ya existe un perfil con el nombre '{name}'")

        ram_mb    = ram_mb or self._settings.default_ram_mb
        safe_name = self._sanitize_folder_name(name)
        game_dir  = os.path.join(self._settings.profiles_dir, safe_name)

        profile = Profile(name=name, version_id=version_id,
                          game_dir=game_dir, ram_mb=ram_mb,
                          java_path=java_path, icon=icon)
        self._create_profile_dirs(profile)
        self._profiles[profile.id] = profile
        self._save()
        log.info(f"Perfil creado: '{name}' — MC {version_id}")

        if loader_type and loader_type.lower() != "vanilla":
            self._install_loader_for_profile(profile, loader_type, loader_ver)

        return profile

    def get_profile(self, profile_id: str):
        return self._profiles.get(profile_id)

    def get_profile_by_name(self, name: str):
        nl = name.lower()
        return next((p for p in self._profiles.values()
                     if p.name.lower() == nl), None)

    def get_all_profiles(self) -> list:
        return sorted(self._profiles.values(),
                      key=lambda p: p.last_used, reverse=True)

    def update_profile(self, profile_id: str, **kwargs) -> Profile:
        profile = self._profiles.get(profile_id)
        if not profile:
            raise ProfileError(f"Perfil no encontrado: {profile_id}")
        if "name" in kwargs and kwargs["name"] != profile.name:
            if self.get_profile_by_name(kwargs["name"]):
                raise ProfileError(
                    f"Ya existe un perfil con el nombre '{kwargs['name']}'")
        for key in {"name", "version_id", "ram_mb", "java_path", "icon"}:
            if key in kwargs:
                setattr(profile, key, kwargs[key])
        self._save()
        log.info(f"Perfil actualizado: '{profile.name}'")
        return profile

    def delete_profile(self, profile_id: str,
                       delete_files: bool = False) -> bool:
        profile = self._profiles.get(profile_id)
        if not profile:
            raise ProfileError(f"Perfil no encontrado: {profile_id}")
        if delete_files and os.path.isdir(profile.game_dir):
            import shutil
            shutil.rmtree(profile.game_dir)
        del self._profiles[profile_id]
        self._save()
        log.info(f"Perfil eliminado: '{profile.name}'")
        return True

    def mark_as_used(self, profile_id: str):
        profile = self._profiles.get(profile_id)
        if profile:
            profile.last_used = datetime.now().isoformat()
            self._save()

    # ── Loaders ───────────────────────────────────────────────────────────────

    def update_loader(self, profile_id: str,
                      loader_type: str, loader_ver: str = "") -> str:
        profile = self.get_profile(profile_id)
        if not profile:
            raise ProfileError(f"Perfil '{profile_id}' no encontrado")
        if loader_type.lower() == "vanilla":
            return profile.version_id
        return self._install_loader_for_profile(profile, loader_type, loader_ver)

    def _install_loader_for_profile(self, profile, loader_type, loader_ver) -> str:
        from managers.loader_manager import LoaderManager, LoaderError
        lm = LoaderManager(self._settings)
        if not loader_ver:
            available = lm.get_available_versions(
                loader_type, profile.version_id, stable_only=True)
            if not available:
                raise LoaderError(
                    f"No hay versiones de {loader_type} "
                    f"para MC {profile.version_id}")
            loader_ver = available[0].loader_ver
            log.info(f"Loader: usando versión más reciente → {loader_ver}")
        install_id = lm.install_loader(
            loader_type, profile.version_id, loader_ver, profile.game_dir)
        log.info(f"Loader '{install_id}' instalado en '{profile.name}'")
        return install_id

    # ── Persistencia ──────────────────────────────────────────────────────────

    def _load(self):
        if not os.path.isfile(self._profiles_file):
            return
        try:
            with open(self._profiles_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for pd in data.get("profiles", []):
                p = Profile.from_dict(pd)
                self._profiles[p.id] = p
            log.info(f"Perfiles cargados: {len(self._profiles)}")
        except (json.JSONDecodeError, KeyError, OSError) as e:
            log.error(f"Error cargando perfiles: {e}")

    def _save(self):
        try:
            ensure_dir(os.path.dirname(self._profiles_file))
            with open(self._profiles_file, "w", encoding="utf-8") as f:
                json.dump({
                    "version": "1.0",
                    "profiles": [p.to_dict() for p in self._profiles.values()]
                }, f, indent=4, ensure_ascii=False)
        except OSError as e:
            log.error(f"Error guardando perfiles: {e}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _create_profile_dirs(self, profile: Profile):
        for folder in [
            profile.game_dir,
            profile.mods_dir,
            profile.saves_dir,
            profile.config_dir,
            profile.resourcepacks_dir,   # ← antes era os.path.join(...)
            profile.shaderpacks_dir,     # ← nueva
            os.path.join(profile.game_dir, "screenshots"),
        ]:
            ensure_dir(folder)

    @staticmethod
    def _sanitize_folder_name(name: str) -> str:
        invalid = r'\/:*?"<>|'
        return "".join(c if c not in invalid else "_"
                       for c in name).strip().replace(" ", "_")