"""
mod_manager.py
--------------
Gestión de mods locales para un perfil específico.
"""
import os
import shutil
from managers.profile_manager import Profile
from utils.file_utils import ensure_dir
from utils.logger import get_logger
log = get_logger()

_MOD_EXTENSION = "jar"
_DISABLED_EXTENSION = "jar.disabled"


class ModError(Exception):
    pass


class ModInfo:
    def __init__(self, path: str):
        self.path = path
        self.filename = os.path.basename(path)
        self.is_enabled = (
            path.endswith(f".{_MOD_EXTENSION}") and
            not path.endswith(f".{_DISABLED_EXTENSION}")
        )
        self.size_mb = round(os.path.getsize(path) / (1024 * 1024), 2)

    @property
    def display_name(self) -> str:
        name = self.filename
        if name.endswith(f".{_DISABLED_EXTENSION}"):
            name = name[: -len(f".{_DISABLED_EXTENSION}")]
        elif name.endswith(f".{_MOD_EXTENSION}"):
            name = name[: -len(f".{_MOD_EXTENSION}")]
        return name

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "display_name": self.display_name,
            "path": self.path,
            "is_enabled": self.is_enabled,
            "size_mb": self.size_mb,
        }


class ModManager:
    def __init__(self, profile: Profile):
        self._profile = profile
        self._mods_dir = profile.mods_dir
        ensure_dir(self._mods_dir)

    def list_mods(self) -> list:
        result = []
        if not os.path.isdir(self._mods_dir):
            return result
        for filename in os.listdir(self._mods_dir):
            full_path = os.path.join(self._mods_dir, filename)
            if not os.path.isfile(full_path):
                continue
            is_mod = filename.endswith(f".{_MOD_EXTENSION}")
            is_disabled = filename.endswith(f".{_DISABLED_EXTENSION}")
            if is_mod or is_disabled:
                result.append(ModInfo(full_path))
        result.sort(key=lambda m: m.display_name.lower())
        return result

    def install_mod_from_file(self, source_path: str) -> ModInfo:
        if not os.path.isfile(source_path):
            raise ModError(f"Archivo no encontrado: {source_path}")
        if not source_path.lower().endswith(".jar"):
            raise ModError(f"El archivo debe ser un .jar: {source_path}")
        filename = os.path.basename(source_path)
        dest_path = os.path.join(self._mods_dir, filename)
        if os.path.exists(dest_path):
            raise ModError(f"Ya existe un mod con ese nombre: {filename}")
        shutil.copy2(source_path, dest_path)
        return ModInfo(dest_path)

    def install_mod_from_bytes(self, filename: str, data: bytes) -> ModInfo:
        if not filename.lower().endswith(".jar"):
            raise ModError(f"El archivo debe ser un .jar: {filename}")
        dest_path = os.path.join(self._mods_dir, filename)
        if os.path.exists(dest_path):
            raise ModError(f"Ya existe un mod con ese nombre: {filename}")
        with open(dest_path, "wb") as f:
            f.write(data)
        return ModInfo(dest_path)

    def delete_mod(self, filename: str) -> bool:
        path = self._resolve_mod_path(filename)
        if not path:
            raise ModError(f"Mod no encontrado: {filename}")
        os.remove(path)
        return True

    def enable_mod(self, filename: str) -> bool:
        path = self._resolve_mod_path(filename)
        if not path:
            raise ModError(f"Mod no encontrado: {filename}")
        if not path.endswith(f".{_DISABLED_EXTENSION}"):
            raise ModError(f"El mod ya está habilitado: {filename}")
        new_path = path[: -len(f".{_DISABLED_EXTENSION}")] + f".{_MOD_EXTENSION}"
        os.rename(path, new_path)
        return True

    def disable_mod(self, filename: str) -> bool:
        path = self._resolve_mod_path(filename)
        if not path:
            raise ModError(f"Mod no encontrado: {filename}")
        if path.endswith(f".{_DISABLED_EXTENSION}"):
            raise ModError(f"El mod ya está deshabilitado: {filename}")
        os.rename(path, path + ".disabled")
        return True

    def get_mod_count(self) -> dict:
        mods = self.list_mods()
        enabled = sum(1 for m in mods if m.is_enabled)
        return {"total": len(mods), "enabled": enabled, "disabled": len(mods) - enabled}

    def _resolve_mod_path(self, filename: str):
        direct = os.path.join(self._mods_dir, filename)
        if os.path.isfile(direct):
            return direct
        disabled = direct + ".disabled"
        if os.path.isfile(disabled):
            return disabled
        return None
