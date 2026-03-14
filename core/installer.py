"""
installer.py
------------
Instalador de versiones de Minecraft vanilla.
FIX APLICADO: _download_libraries con 16 workers, _download_assets con 32 workers y reintentos.
FIX APLICADO: _download_single_library descarga natives JARs para 1.16.5.
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from config.constants import (
    MOJANG_VERSION_MANIFEST_URL,
    MOJANG_ASSETS_BASE_URL,
)
from config.settings import Settings
from core.downloader import Downloader, DownloadError
from utils.file_utils import ensure_dir
from utils.logger import get_logger
from utils.system_utils import get_os, get_architecture

log = get_logger()


class InstallationError(Exception):
    pass


class MinecraftInstaller:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._downloader = Downloader()
        self._manifest_cache: dict = {}

    def get_available_versions(self, version_type: str = "release") -> list:
        manifest = self._load_manifest()
        versions = manifest.get("versions", [])
        if version_type == "all":
            return versions
        return [v for v in versions if v.get("type") == version_type]

    def get_installed_versions(self) -> list:
        installed = []
        versions_dir = self._settings.versions_dir
        if not os.path.isdir(versions_dir):
            return installed
        for version_id in os.listdir(versions_dir):
            version_dir = os.path.join(versions_dir, version_id)
            json_path = os.path.join(version_dir, f"{version_id}.json")
            jar_path = os.path.join(version_dir, f"{version_id}.jar")
            if os.path.isfile(json_path) and os.path.isfile(jar_path):
                installed.append(version_id)
        return sorted(installed, reverse=True)

    def is_version_installed(self, version_id: str) -> bool:
        return version_id in self.get_installed_versions()

    def install_version(self, version_id: str, progress_callback=None) -> bool:
        log.info(f"=== Iniciando instalación de Minecraft {version_id} ===")
        try:
            version_info = self._get_version_info_from_manifest(version_id)
            if not version_info:
                raise InstallationError(f"Versión '{version_id}' no encontrada en el manifest")
            version_url = version_info["url"]
            version_data = self._download_version_json(version_id, version_url)
            self._download_client_jar(version_id, version_data, progress_callback)
            self._download_libraries(version_data, progress_callback)
            self._download_assets(version_data, progress_callback)
            log.info(f"=== Minecraft {version_id} instalado correctamente ===")
            return True
        except DownloadError as e:
            raise InstallationError(f"Error de descarga durante instalación: {e}")

    def get_version_data(self, version_id: str) -> dict:
        json_path = os.path.join(
            self._settings.versions_dir, version_id, f"{version_id}.json"
        )
        if not os.path.isfile(json_path):
            raise InstallationError(f"Versión {version_id} no instalada. JSON no encontrado.")
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_manifest(self) -> dict:
        if self._manifest_cache:
            return self._manifest_cache
        log.info("Descargando manifest de versiones de Mojang...")
        try:
            self._manifest_cache = self._downloader.download_json(MOJANG_VERSION_MANIFEST_URL)
            total = len(self._manifest_cache.get("versions", []))
            log.info(f"Manifest cargado: {total} versiones disponibles")
            return self._manifest_cache
        except DownloadError as e:
            raise InstallationError(f"No se pudo cargar el manifest de versiones: {e}")

    def _get_version_info_from_manifest(self, version_id: str):
        manifest = self._load_manifest()
        for version in manifest.get("versions", []):
            if version["id"] == version_id:
                return version
        return None

    def _download_version_json(self, version_id: str, version_url: str) -> dict:
        version_dir = ensure_dir(os.path.join(self._settings.versions_dir, version_id))
        json_dest = os.path.join(version_dir, f"{version_id}.json")
        if os.path.isfile(json_dest):
            with open(json_dest, "r", encoding="utf-8") as f:
                return json.load(f)
        log.info(f"Descargando JSON de versión {version_id}...")
        version_data = self._downloader.download_json(version_url)
        with open(json_dest, "w", encoding="utf-8") as f:
            json.dump(version_data, f, indent=2)
        return version_data

    def _download_client_jar(self, version_id: str, version_data: dict, progress_callback=None):
        downloads = version_data.get("downloads", {})
        client_info = downloads.get("client", {})
        if not client_info:
            raise InstallationError(f"No se encontró info del cliente en versión {version_id}")
        url = client_info["url"]
        sha1 = client_info.get("sha1", "")
        jar_dest = os.path.join(self._settings.versions_dir, version_id, f"{version_id}.jar")
        log.info(f"Descargando cliente JAR de Minecraft {version_id}...")
        if progress_callback:
            progress_callback("Descargando cliente JAR", 0, 1)
        self._downloader.download(url, jar_dest, expected_sha1=sha1)
        if progress_callback:
            progress_callback("Cliente JAR descargado", 1, 1)

    def _download_libraries(self, version_data: dict, progress_callback=None):
        """Descarga librerías en paralelo con 16 workers."""
        libraries = version_data.get("libraries", [])
        current_os = get_os()
        compatible = [lib for lib in libraries if self._is_library_compatible(lib, current_os)]
        total = len(compatible)
        completed = 0
        log.info(f"Descargando {total} librerías en paralelo...")

        def download_lib(lib):
            self._download_single_library(lib)

        with ThreadPoolExecutor(max_workers=32) as executor:
            futures = {executor.submit(download_lib, lib): lib for lib in compatible}
            for future in as_completed(futures):
                completed += 1
                if progress_callback:
                    progress_callback(f"Librerías {completed}/{total}", completed, total)
        log.info(f"✓ {total} librerías descargadas")

    def _download_single_library(self, lib: dict):
        downloads = lib.get("downloads", {})

        # Descargar artifact normal
        artifact = downloads.get("artifact", {})
        if artifact and artifact.get("url"):
            path = artifact.get("path", "")
            sha1 = artifact.get("sha1", "")
            if path:
                dest = os.path.join(self._settings.libraries_dir, *path.split("/"))
                try:
                    self._downloader.download(artifact["url"], dest, expected_sha1=sha1)
                except DownloadError as e:
                    log.warning(f"No se pudo descargar librería {path}: {e}")

        # Descargar classifiers nativos (necesario para 1.16.5 y versiones antiguas)
        current_os = get_os()
        os_key = {"windows": "windows", "linux": "linux", "macos": "osx"}.get(current_os, current_os)
        natives = lib.get("natives", {})
        if os_key not in natives:
            return
        classifier = natives[os_key].replace("${arch}", "64")
        classifiers = downloads.get("classifiers", {})
        native_info = classifiers.get(classifier, {})
        if not native_info or not native_info.get("url"):
            return
        path = native_info.get("path", "")
        sha1 = native_info.get("sha1", "")
        if not path:
            return
        dest = os.path.join(self._settings.libraries_dir, *path.split("/"))
        try:
            self._downloader.download(native_info["url"], dest, expected_sha1=sha1)
            log.debug(f"Native JAR descargado: {os.path.basename(path)}")
        except DownloadError as e:
            log.warning(f"No se pudo descargar native {path}: {e}")

    def _download_assets(self, version_data: dict, progress_callback=None):
        """Descarga assets en paralelo con 32 workers y reintentos para fallidos."""
        asset_index_info = version_data.get("assetIndex", {})
        if not asset_index_info:
            return
        asset_id = asset_index_info["id"]
        asset_url = asset_index_info["url"]
        asset_sha1 = asset_index_info.get("sha1", "")

        indexes_dir = ensure_dir(os.path.join(self._settings.assets_dir, "indexes"))
        index_dest = os.path.join(indexes_dir, f"{asset_id}.json")
        self._downloader.download(asset_url, index_dest, expected_sha1=asset_sha1)

        with open(index_dest, "r", encoding="utf-8") as f:
            asset_index = json.load(f)
        objects = asset_index.get("objects", {})
        total = len(objects)
        completed = 0
        failed = []
        log.info(f"Descargando {total} assets en paralelo...")
        objects_dir = ensure_dir(os.path.join(self._settings.assets_dir, "objects"))
        asset_list = list(objects.values())

        def download_asset(asset_info):
            asset_hash = asset_info.get("hash", "")
            if not asset_hash:
                return None
            prefix = asset_hash[:2]
            asset_dest = os.path.join(objects_dir, prefix, asset_hash)
            if os.path.isfile(asset_dest) and os.path.getsize(asset_dest) > 0:
                return None
            asset_url = f"{MOJANG_ASSETS_BASE_URL}/{prefix}/{asset_hash}"
            try:
                self._downloader.download(asset_url, asset_dest, expected_sha1=asset_hash)
                return None
            except DownloadError:
                return asset_info

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = {executor.submit(download_asset, a): a for a in asset_list}
            for future in as_completed(futures):
                completed += 1
                result = future.result()
                if result:
                    failed.append(result)
                if progress_callback and completed % 50 == 0:
                    progress_callback(f"Assets {completed}/{total}", completed, total)

        # Reintentar fallidos secuencialmente
        if failed:
            log.warning(f"Reintentando {len(failed)} assets fallidos...")
            still_failed = []
            for asset_info in failed:
                asset_hash = asset_info.get("hash", "")
                prefix = asset_hash[:2]
                asset_url = f"{MOJANG_ASSETS_BASE_URL}/{prefix}/{asset_hash}"
                asset_dest = os.path.join(objects_dir, prefix, asset_hash)
                success = False
                for attempt in range(5):
                    try:
                        time.sleep(0.5)
                        self._downloader.download(asset_url, asset_dest, expected_sha1=asset_hash)
                        success = True
                        break
                    except DownloadError:
                        time.sleep(2 * (attempt + 1))
                if not success:
                    still_failed.append(asset_hash[:8])

            if still_failed:
                log.error(f"Assets que no se pudieron descargar ({len(still_failed)}): {still_failed}")
            else:
                log.info("✓ Todos los assets fallidos se recuperaron")

        log.info(f"✓ {total} assets descargados")

    def _download_single_asset(self, asset_info: dict, objects_dir: str):
        asset_hash = asset_info.get("hash", "")
        if not asset_hash:
            return
        prefix = asset_hash[:2]
        asset_url = f"{MOJANG_ASSETS_BASE_URL}/{prefix}/{asset_hash}"
        asset_dest = os.path.join(objects_dir, prefix, asset_hash)

        if os.path.isfile(asset_dest) and os.path.getsize(asset_dest) > 0:
            return  # Ya existe y no está vacío

        for attempt in range(3):
            try:
                self._downloader.download(asset_url, asset_dest, expected_sha1=asset_hash)
                return
            except DownloadError as e:
                log.warning(f"Asset fallido intento {attempt+1}/3: {asset_hash[:8]}... — {e}")
                import time
                time.sleep(1)

    def _is_library_compatible(self, lib: dict, current_os: str) -> bool:
        rules = lib.get("rules", [])
        if not rules:
            return True
        allow = False
        for rule in rules:
            action = rule.get("action", "allow")
            os_rule = rule.get("os", {})
            if not os_rule:
                allow = (action == "allow")
            else:
                os_name = os_rule.get("name", "")
                if os_name == current_os:
                    allow = (action == "allow")
        return allow