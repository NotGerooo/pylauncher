"""
version_manager.py
------------------
Gestión de versiones de Minecraft disponibles e instaladas.
"""
import os
from config.settings import Settings
from core.installer import MinecraftInstaller, InstallationError
from utils.logger import get_logger
log = get_logger()


class VersionError(Exception):
    pass


class VersionInfo:
    def __init__(self, version_id, version_type, release_time, url="", is_installed=False):
        self.id = version_id
        self.type = version_type
        self.release_time = release_time
        self.url = url
        self.is_installed = is_installed

    @property
    def is_release(self): return self.type == "release"

    @property
    def is_snapshot(self): return self.type == "snapshot"

    @property
    def display_name(self):
        suffix = " ✓" if self.is_installed else ""
        return f"{self.id}{suffix}"

    def to_dict(self):
        return {"id": self.id, "type": self.type, "release_time": self.release_time,
                "url": self.url, "is_installed": self.is_installed}

    def __repr__(self):
        installed = "instalada" if self.is_installed else "no instalada"
        return f"VersionInfo({self.id!r}, {self.type!r}, {installed})"


class VersionManager:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._installer = MinecraftInstaller(settings)
        self._available_cache: list = []

    def get_available_versions(self, version_type: str = "release", force_refresh: bool = False) -> list:
        if not self._available_cache or force_refresh:
            self._refresh_available_cache()
        installed_ids = set(self.get_installed_version_ids())
        filtered = [
            v for v in self._available_cache
            if version_type == "all" or v.type == version_type
        ]
        for v in filtered:
            v.is_installed = v.id in installed_ids
        return filtered

    def get_installed_versions(self) -> list:
        installed_ids = self._installer.get_installed_versions()
        result = []
        cache_map = {v.id: v for v in self._available_cache}
        for version_id in installed_ids:
            if version_id in cache_map:
                v = cache_map[version_id]
                v.is_installed = True
                result.append(v)
            else:
                result.append(VersionInfo(version_id=version_id, version_type="release",
                                          release_time="", is_installed=True))
        return result

    def get_installed_version_ids(self) -> list:
        return self._installer.get_installed_versions()

    def get_latest_release(self):
        try:
            releases = self.get_available_versions(version_type="release")
            return releases[0] if releases else None
        except VersionError:
            return None

    def get_version_info(self, version_id: str):
        for v in self._available_cache:
            if v.id == version_id:
                v.is_installed = self.is_installed(version_id)
                return v
        if self.is_installed(version_id):
            return VersionInfo(version_id=version_id, version_type="release",
                               release_time="", is_installed=True)
        return None

    def is_installed(self, version_id: str) -> bool:
        return self._installer.is_version_installed(version_id)

    def install_version(self, version_id: str, progress_callback=None) -> bool:
        if self.is_installed(version_id):
            log.info(f"Versión {version_id} ya está instalada, omitiendo")
            return True
        try:
            return self._installer.install_version(version_id, progress_callback)
        except InstallationError as e:
            raise VersionError(f"No se pudo instalar {version_id}: {e}")

    def uninstall_version(self, version_id: str) -> bool:
        if not self.is_installed(version_id):
            raise VersionError(f"La versión {version_id} no está instalada")
        version_dir = os.path.join(self._settings.versions_dir, version_id)
        import shutil
        shutil.rmtree(version_dir)
        return True

    def get_version_data(self, version_id: str) -> dict:
        try:
            return self._installer.get_version_data(version_id)
        except InstallationError as e:
            raise VersionError(str(e))

    def _refresh_available_cache(self):
        log.info("Actualizando caché de versiones disponibles...")
        try:
            raw_versions = self._installer.get_available_versions(version_type="all")
        except InstallationError as e:
            raise VersionError(f"No se pudo conectar con Mojang: {e}")
        self._available_cache = [
            VersionInfo(
                version_id=v["id"],
                version_type=v.get("type", "release"),
                release_time=v.get("releaseTime", ""),
                url=v.get("url", ""),
            )
            for v in raw_versions
        ]
        log.info(f"Caché actualizado: {len(self._available_cache)} versiones disponibles")
