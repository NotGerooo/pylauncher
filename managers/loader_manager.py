"""
loader_manager.py
-----------------
Gestiona la descarga e instalación de mod loaders para cada instancia/perfil.

Loaders soportados:
- Vanilla     → Sin loader (solo Mojang)
- Fabric      → fabric-installer desde fabricmc.net
- Forge       → forge-installer desde files.minecraftforge.net
- NeoForge    → neoforge-installer desde neoforged.net
- Quilt       → quilt-installer desde quiltmc.org
- OptiFine    → OptiFine desde optifine.net (scraping directo)

Cada loader se instala como una versión independiente dentro de
la carpeta versions/ del launcher, igual que hace el launcher oficial.
"""

import json
import os
import re
import subprocess
import urllib.request
import urllib.error
import urllib.parse

from config.constants import HTTP_TIMEOUT_SECONDS, USER_AGENT
from config.settings import Settings
from core.downloader import Downloader, DownloadError
from utils.file_utils import ensure_dir
from utils.logger import get_logger

log = get_logger()


# ─── URLs base de cada loader ─────────────────────────────────────────────────

FABRIC_META_URL      = "https://meta.fabricmc.net/v2"
FORGE_MAVEN_URL      = "https://files.minecraftforge.net/net/minecraftforge/forge"
NEOFORGE_MAVEN_URL   = "https://maven.neoforged.net/releases/net/neoforged/neoforge"
QUILT_META_URL       = "https://meta.quiltmc.org/v3"
OPTIFINE_BASE_URL    = "https://optifine.net"


# ─── Excepciones ──────────────────────────────────────────────────────────────

class LoaderError(Exception):
    """Error durante la instalación de un loader."""
    pass

class LoaderNotSupportedError(LoaderError):
    """El loader solicitado no es compatible con esa versión de Minecraft."""
    pass


# ─── Modelos de datos ─────────────────────────────────────────────────────────

class LoaderVersion:
    """
    Representa una versión disponible de un loader.

    Atributos:
        loader_type : "fabric" | "forge" | "neoforge" | "quilt" | "optifine" | "vanilla"
        mc_version  : Versión de Minecraft destino, ej: "1.20.4"
        loader_ver  : Versión del loader en sí, ej: "0.15.7"
        stable      : True si es release estable
        install_id  : ID que usará la versión instalada en /versions,
                      ej: "1.20.4-fabric-0.15.7"
    """

    def __init__(
        self,
        loader_type: str,
        mc_version: str,
        loader_ver: str,
        stable: bool = True,
    ):
        self.loader_type = loader_type
        self.mc_version  = mc_version
        self.loader_ver  = loader_ver
        self.stable      = stable
        self.install_id  = f"{mc_version}-{loader_type}-{loader_ver}"

    def __repr__(self) -> str:
        tag = "stable" if self.stable else "beta"
        return f"LoaderVersion({self.loader_type} {self.loader_ver} / MC {self.mc_version} [{tag}])"


# ─── Manager principal ────────────────────────────────────────────────────────

class LoaderManager:
    """
    Descarga e instala mod loaders para una instancia de Minecraft.

    Uso básico:
        settings = Settings()
        lm = LoaderManager(settings)

        # Ver versiones de Fabric disponibles para 1.20.4
        versions = lm.get_available_versions("fabric", "1.20.4")

        # Instalar el loader en una instancia/perfil
        lm.install_loader("fabric", "1.20.4", "0.15.7", profile_game_dir)

        # Ver qué loaders tiene instalada una instancia
        loaders = lm.get_installed_loaders(profile_game_dir)
    """

    def __init__(self, settings: Settings):
        self._settings  = settings
        self._downloader = Downloader()

    # ── API Pública ───────────────────────────────────────────────────────────

    def get_available_versions(
        self,
        loader_type: str,
        mc_version: str,
        stable_only: bool = True,
    ) -> list[LoaderVersion]:
        """
        Retorna las versiones disponibles del loader para una versión de Minecraft.

        Args:
            loader_type : "fabric" | "forge" | "neoforge" | "quilt" | "optifine" | "vanilla"
            mc_version  : Versión de MC destino, ej: "1.20.4"
            stable_only : Si True, filtra solo versiones estables

        Returns:
            Lista de LoaderVersion, de más nueva a más vieja

        Raises:
            LoaderError: Si falla la conexión o el loader no soporta esa versión
        """
        loader_type = loader_type.lower()

        if loader_type == "vanilla":
            return [LoaderVersion("vanilla", mc_version, mc_version)]

        fetchers = {
            "fabric":   self._fetch_fabric_versions,
            "forge":    self._fetch_forge_versions,
            "neoforge": self._fetch_neoforge_versions,
            "quilt":    self._fetch_quilt_versions,
            "optifine": self._fetch_optifine_versions,
        }

        if loader_type not in fetchers:
            raise LoaderError(
                f"Loader '{loader_type}' no soportado. "
                f"Opciones: {', '.join(fetchers)} , vanilla"
            )

        versions = fetchers[loader_type](mc_version)

        if stable_only:
            versions = [v for v in versions if v.stable]

        log.info(
            f"{loader_type.capitalize()}: {len(versions)} versiones "
            f"disponibles para MC {mc_version}"
        )
        return versions

    def install_loader(
        self,
        loader_type: str,
        mc_version: str,
        loader_ver: str,
        profile_game_dir: str,
        java_path: str = "java",
        progress_callback=None,
    ) -> str:
        """
        Descarga e instala un loader en la instancia del perfil dado.

        Args:
            loader_type      : "fabric" | "forge" | "neoforge" | "quilt" | "optifine" | "vanilla"
            mc_version       : Versión de Minecraft, ej: "1.20.4"
            loader_ver       : Versión del loader, ej: "0.15.7"
            profile_game_dir : Carpeta raíz del perfil (contiene /mods, /saves, etc.)
            java_path        : Ejecutable de Java (para loaders que necesiten instalador .jar)
            progress_callback: función(step: str, current: int, total: int)

        Returns:
            version_id instalado, ej: "1.20.4-fabric-0.15.7"

        Raises:
            LoaderError: Si falla la instalación
        """
        loader_type = loader_type.lower()

        log.info(
            f"=== Instalando {loader_type} {loader_ver} para MC {mc_version} ==="
        )

        if loader_type == "vanilla":
            log.info("Vanilla seleccionado — no requiere loader adicional.")
            return mc_version

        installers = {
            "fabric":   self._install_fabric,
            "forge":    self._install_forge,
            "neoforge": self._install_neoforge,
            "quilt":    self._install_quilt,
            "optifine": self._install_optifine,
        }

        if loader_type not in installers:
            raise LoaderError(f"Loader '{loader_type}' no soportado.")

        version_id = installers[loader_type](
            mc_version, loader_ver, profile_game_dir, java_path, progress_callback
        )

        # Registrar el loader en el perfil
        self._save_loader_metadata(profile_game_dir, loader_type, mc_version, loader_ver)

        log.info(f"=== {loader_type.capitalize()} instalado como '{version_id}' ===")
        return version_id

    def get_installed_loaders(self, profile_game_dir: str) -> list[dict]:
        """
        Lee el archivo loader_meta.json del perfil y retorna los loaders instalados.

        Returns:
            Lista de dicts con keys: loader_type, mc_version, loader_ver, install_id
        """
        meta_file = os.path.join(profile_game_dir, "loader_meta.json")
        if not os.path.isfile(meta_file):
            return []
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"Error leyendo loader_meta.json: {e}")
            return []

    def is_loader_installed(
        self, profile_game_dir: str, loader_type: str, mc_version: str
    ) -> bool:
        """
        Verifica si ya existe un loader del tipo dado para esa versión en el perfil.
        """
        for entry in self.get_installed_loaders(profile_game_dir):
            if (
                entry.get("loader_type") == loader_type
                and entry.get("mc_version") == mc_version
            ):
                return True
        return False

    # ── Fabric ────────────────────────────────────────────────────────────────

    def _fetch_fabric_versions(self, mc_version: str) -> list[LoaderVersion]:
        """
        Consulta la meta API de FabricMC para versiones del loader.
        Endpoint: GET /v2/versions/loader/{mc_version}
        """
        url = f"{FABRIC_META_URL}/versions/loader/{urllib.parse.quote(mc_version)}"
        try:
            data = self._get_json(url)
        except LoaderError as e:
            raise LoaderNotSupportedError(
                f"Fabric no soporta MC {mc_version}: {e}"
            )

        versions = []
        for entry in data:
            loader_info = entry.get("loader", {})
            ver    = loader_info.get("version", "")
            stable = loader_info.get("stable", True)
            if ver:
                versions.append(LoaderVersion("fabric", mc_version, ver, stable))
        return versions

    def _install_fabric(self, mc_version, loader_ver, profile_game_dir,
                        java_path, progress_callback) -> str:
        version_id   = f"{mc_version}-fabric-{loader_ver}"
        versions_dir = ensure_dir(
            os.path.join(self._settings.versions_dir, version_id))
        json_path = os.path.join(versions_dir, f"{version_id}.json")

        if progress_callback:
            progress_callback("Descargando perfil Fabric", 1, 4)

        if not os.path.isfile(json_path):
            url = (
                f"{FABRIC_META_URL}/versions/loader/"
                f"{urllib.parse.quote(mc_version)}/"
                f"{urllib.parse.quote(loader_ver)}/profile/json"
            )
            try:
                profile_data = self._get_json(url)
            except LoaderError as e:
                raise LoaderError(f"No se pudo descargar el perfil Fabric: {e}")
            profile_data["id"] = version_id
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(profile_data, f, indent=2)
        else:
            with open(json_path, "r", encoding="utf-8") as f:
                profile_data = json.load(f)

        if progress_callback:
            progress_callback("Descargando librerías Fabric", 2, 4)

        self._download_loader_libraries(profile_data)

        if progress_callback:
            progress_callback("Fabric instalado", 4, 4)

        log.info(f"Fabric {loader_ver} instalado para MC {mc_version}")
        return version_id

    def _download_loader_libraries(self, version_data: dict):
        libraries = version_data.get("libraries", [])
        log.info(f"Descargando {len(libraries)} librerías del loader...")

        for lib in libraries:
            # Intentar formato estándar (downloads.artifact)
            artifact = lib.get("downloads", {}).get("artifact", {})
            url  = artifact.get("url", "")
            path = artifact.get("path", "")

            # Formato Fabric/Quilt: "name" + "url" (repositorio base)
            if not url or not path:
                name     = lib.get("name", "")
                base_url = lib.get("url", "https://libraries.minecraft.net/")
                if not name:
                    continue
                parts = name.split(":")
                if len(parts) < 3:
                    continue
                group, artifact_id, version = parts[0], parts[1], parts[2]
                classifier = f"-{parts[3]}" if len(parts) > 3 else ""
                group_path = group.replace(".", "/")
                filename   = f"{artifact_id}-{version}{classifier}.jar"
                path = f"{group_path}/{artifact_id}/{version}/{filename}"
                url  = base_url.rstrip("/") + "/" + path

            if not url or not path:
                continue

            dest = os.path.join(self._settings.libraries_dir, *path.split("/"))

            if os.path.isfile(dest):
                continue

            try:
                self._downloader.download(url, dest)
                log.info(f"✓ {os.path.basename(dest)}")
            except DownloadError as e:
                log.warning(f"No se pudo descargar {path}: {e}")

    def _fetch_forge_versions(self, mc_version: str) -> list[LoaderVersion]:
        url = f"{FORGE_MAVEN_URL}/promotions_slim.json"
        try:
            data = self._get_json(url)
        except LoaderError as e:
            raise LoaderError(f"No se pudo cargar el manifest de Forge: {e}")

        promos = data.get("promos", {})
        versions = []
        for key, forge_ver in promos.items():
            if key.startswith(mc_version + "-"):
                tag    = key.split("-", 1)[1]
                stable = tag == "recommended"
                full_ver = f"{mc_version}-{forge_ver}"
                versions.append(LoaderVersion("forge", mc_version, full_ver, stable))

        if not versions:
            versions = self._fetch_forge_maven_versions(mc_version)

        return versions

    def _fetch_forge_maven_versions(self, mc_version: str) -> list[LoaderVersion]:
        """Fallback: scrapea el Maven de Forge buscando versiones para mc_version."""
        url = f"{FORGE_MAVEN_URL}/maven-metadata.json"
        try:
            data = self._get_json(url)
        except LoaderError:
            return []

        all_versions = data.get("versions", [])
        result = []
        for v in all_versions:
            if v.startswith(mc_version + "-"):
                result.append(LoaderVersion("forge", mc_version, v, stable=True))
        return list(reversed(result))

    def _install_forge(
        self,
        mc_version: str,
        loader_ver: str,
        profile_game_dir: str,
        java_path: str,
        progress_callback,
    ) -> str:
        """
        Descarga el installer .jar de Forge y lo ejecuta con Java.
        El installer de Forge crea la versión en la carpeta estándar de Minecraft,
        así que apuntamos al versions_dir del launcher.
        """
        version_id   = f"{mc_version}-forge-{loader_ver}"
        installer_url = (
            f"{FORGE_MAVEN_URL}/{loader_ver}/"
            f"forge-{loader_ver}-installer.jar"
        )

        tmp_dir      = ensure_dir(os.path.join(self._settings.minecraft_dir, "tmp"))
        installer_jar = os.path.join(tmp_dir, f"forge-{loader_ver}-installer.jar")

        if progress_callback:
            progress_callback("Descargando installer Forge", 1, 4)

        try:
            self._downloader.download(installer_url, installer_jar)
        except DownloadError as e:
            raise LoaderError(f"No se pudo descargar el installer de Forge: {e}")

        if progress_callback:
            progress_callback("Ejecutando installer Forge", 2, 4)

        self._run_installer(
            java_path,
            installer_jar,
            self._settings.minecraft_dir,
            progress_callback,
        )

        if progress_callback:
            progress_callback("Forge instalado", 4, 4)

        return version_id

    # ── NeoForge ──────────────────────────────────────────────────────────────

    def _fetch_neoforge_versions(self, mc_version: str) -> list[LoaderVersion]:
        """
        Consulta el Maven de NeoForged para listar versiones compatibles.
        NeoForge usa versiones como "21.1.x" (MC 1.21.1 → NeoForge 21.1.x)
        """
        url = f"{NEOFORGE_MAVEN_URL}/maven-metadata.json"
        try:
            data = self._get_json(url)
        except LoaderError as e:
            raise LoaderError(f"No se pudo cargar el manifest de NeoForge: {e}")

        # NeoForge numera sus versiones como MC_MAJOR.MC_MINOR.patch
        # ej: MC 1.21.1 → NeoForge 21.1.*
        parts = mc_version.split(".")
        prefix = f"{parts[1]}.{parts[2]}." if len(parts) >= 3 else f"{parts[1]}."

        all_versions = data.get("versions", [])
        result = []
        for v in all_versions:
            if v.startswith(prefix):
                result.append(LoaderVersion("neoforge", mc_version, v, stable=True))
        return list(reversed(result))

    def _install_neoforge(
        self,
        mc_version: str,
        loader_ver: str,
        profile_game_dir: str,
        java_path: str,
        progress_callback,
    ) -> str:
        """
        Descarga y ejecuta el installer .jar de NeoForge.
        Idéntico al flujo de Forge.
        """
        version_id    = f"{mc_version}-neoforge-{loader_ver}"
        installer_url = (
            f"{NEOFORGE_MAVEN_URL}/{loader_ver}/"
            f"neoforge-{loader_ver}-installer.jar"
        )

        tmp_dir       = ensure_dir(os.path.join(self._settings.minecraft_dir, "tmp"))
        installer_jar = os.path.join(tmp_dir, f"neoforge-{loader_ver}-installer.jar")

        if progress_callback:
            progress_callback("Descargando installer NeoForge", 1, 4)

        try:
            self._downloader.download(installer_url, installer_jar)
        except DownloadError as e:
            raise LoaderError(f"No se pudo descargar el installer de NeoForge: {e}")

        if progress_callback:
            progress_callback("Ejecutando installer NeoForge", 2, 4)

        self._run_installer(
            java_path,
            installer_jar,
            self._settings.minecraft_dir,
            progress_callback,
        )

        if progress_callback:
            progress_callback("NeoForge instalado", 4, 4)

        return version_id

    # ── Quilt ─────────────────────────────────────────────────────────────────

    def _fetch_quilt_versions(self, mc_version: str) -> list[LoaderVersion]:
        """
        Consulta la meta API de QuiltMC.
        Endpoint: GET /v3/versions/loader/{mc_version}
        """
        url = f"{QUILT_META_URL}/versions/loader/{urllib.parse.quote(mc_version)}"
        try:
            data = self._get_json(url)
        except LoaderError as e:
            raise LoaderNotSupportedError(
                f"Quilt no soporta MC {mc_version}: {e}"
            )

        versions = []
        for entry in data:
            loader_info = entry.get("loader", {})
            ver    = loader_info.get("version", "")
            # Quilt no tiene campo "stable" en su meta, se deduce del nombre
            stable = "-beta" not in ver and "-alpha" not in ver
            if ver:
                versions.append(LoaderVersion("quilt", mc_version, ver, stable))
        return versions

    def _install_quilt(
        self,
        mc_version: str,
        loader_ver: str,
        profile_game_dir: str,
        java_path: str,
        progress_callback,
    ) -> str:
        """
        Instala Quilt descargando su JSON de perfil directamente desde la meta API,
        igual que Fabric (sin ejecutar instalador .jar).

        Endpoint: GET /v3/versions/loader/{mc}/{loader}/profile/json
        """
        version_id   = f"{mc_version}-quilt-{loader_ver}"
        versions_dir = ensure_dir(
            os.path.join(self._settings.versions_dir, version_id)
        )
        json_path = os.path.join(versions_dir, f"{version_id}.json")

        if os.path.isfile(json_path):
            log.info(f"Quilt ya instalado: {version_id}")
            return version_id

        url = (
            f"{QUILT_META_URL}/versions/loader/"
            f"{urllib.parse.quote(mc_version)}/"
            f"{urllib.parse.quote(loader_ver)}/profile/json"
        )

        if progress_callback:
            progress_callback("Descargando perfil Quilt", 1, 3)

        try:
            profile_data = self._get_json(url)
        except LoaderError as e:
            raise LoaderError(f"No se pudo descargar el perfil Quilt: {e}")

        profile_data["id"] = version_id

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, indent=2)

        if progress_callback:
            progress_callback("Quilt instalado", 3, 3)

        log.info(f"Quilt {loader_ver} instalado para MC {mc_version}")
        return version_id

    # ── OptiFine ──────────────────────────────────────────────────────────────

    def _fetch_optifine_versions(self, mc_version: str) -> list[LoaderVersion]:
        """
        Scrapea la página de descargas de OptiFine para obtener versiones disponibles.
        OptiFine no tiene API oficial — se extrae del HTML de la página.
        """
        url = f"{OPTIFINE_BASE_URL}/adloadx?f=OptiFine_{mc_version}"
        try:
            html = self._get_html(url)
        except LoaderError as e:
            raise LoaderNotSupportedError(
                f"No se encontraron versiones de OptiFine para MC {mc_version}: {e}"
            )

        # Busca patrones como: OptiFine_1.20.4_HD_U_I7.jar
        pattern = re.compile(
            r"OptiFine_" + re.escape(mc_version) + r"_HD_U_([A-Z0-9_]+)\.jar"
        )
        matches = pattern.findall(html)

        seen = set()
        versions = []
        for match in matches:
            ver = f"HD_U_{match}"
            if ver not in seen:
                seen.add(ver)
                versions.append(LoaderVersion("optifine", mc_version, ver, stable=True))
        return versions

    def _install_optifine(
        self,
        mc_version: str,
        loader_ver: str,
        profile_game_dir: str,
        java_path: str,
        progress_callback,
    ) -> str:
        """
        Descarga el .jar de OptiFine desde optifine.net y lo ejecuta como instalador.
        OptiFine se instala como versión independiente en /versions.
        """
        version_id    = f"{mc_version}-optifine-{loader_ver}"
        jar_name      = f"OptiFine_{mc_version}_{loader_ver}.jar"
        download_url  = f"{OPTIFINE_BASE_URL}/downloadx?f={jar_name}&x=adloadx"

        tmp_dir       = ensure_dir(os.path.join(self._settings.minecraft_dir, "tmp"))
        installer_jar = os.path.join(tmp_dir, jar_name)

        if progress_callback:
            progress_callback("Descargando OptiFine", 1, 4)

        try:
            self._downloader.download(download_url, installer_jar)
        except DownloadError as e:
            raise LoaderError(f"No se pudo descargar OptiFine: {e}")

        if progress_callback:
            progress_callback("Ejecutando installer OptiFine", 2, 4)

        self._run_installer(
            java_path,
            installer_jar,
            self._settings.minecraft_dir,
            progress_callback,
        )

        if progress_callback:
            progress_callback("OptiFine instalado", 4, 4)

        return version_id

    # ── Helpers internos ──────────────────────────────────────────────────────

    def _run_installer(
        self,
        java_path: str,
        installer_jar: str,
        mc_dir: str,
        progress_callback,
    ):
        """
        Ejecuta un instalador .jar en modo headless (sin GUI).
        Forge, NeoForge y OptiFine usan este flujo.

        Args:
            java_path    : Ruta al ejecutable java
            installer_jar: Ruta al .jar descargado
            mc_dir       : Directorio de Minecraft destino (--installDir)
        """
        cmd = [
            java_path,
            "-jar", installer_jar,
            "--installClient",
            f"--installDir={mc_dir}",
        ]

        log.info(f"Ejecutando instalador: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,   # 5 minutos máximo
            )
            if result.returncode != 0:
                log.error(f"Installer stderr: {result.stderr}")
                raise LoaderError(
                    f"El instalador terminó con error (código {result.returncode}): "
                    f"{result.stderr[:300]}"
                )
            log.debug(f"Installer stdout: {result.stdout[:500]}")
        except subprocess.TimeoutExpired:
            raise LoaderError("El instalador tardó demasiado (>5 min) y fue cancelado.")
        except FileNotFoundError:
            raise LoaderError(
                f"Java no encontrado en '{java_path}'. "
                "Configura la ruta de Java en Settings."
            )

    def _save_loader_metadata(
        self,
        profile_game_dir: str,
        loader_type: str,
        mc_version: str,
        loader_ver: str,
    ):
        """
        Guarda un registro del loader instalado en loader_meta.json dentro del perfil.
        Permite saber qué loaders tiene cada instancia sin consultar /versions.
        """
        meta_file = os.path.join(profile_game_dir, "loader_meta.json")
        entries   = self.get_installed_loaders(profile_game_dir)

        new_entry = {
            "loader_type": loader_type,
            "mc_version":  mc_version,
            "loader_ver":  loader_ver,
            "install_id":  f"{mc_version}-{loader_type}-{loader_ver}",
        }

        # Reemplaza si ya existía una entrada para ese loader + mc_version
        entries = [
            e for e in entries
            if not (
                e.get("loader_type") == loader_type
                and e.get("mc_version") == mc_version
            )
        ]
        entries.append(new_entry)

        ensure_dir(profile_game_dir)
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)

        log.debug(f"Metadata de loaders actualizada en {meta_file}")

    def _get_json(self, url: str) -> dict | list:
        """Descarga y parsea un JSON desde una URL. Lanza LoaderError si falla."""
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise LoaderError(f"HTTP {e.code} al consultar {url}")
        except urllib.error.URLError as e:
            raise LoaderError(f"Error de red al consultar {url}: {e.reason}")

    def _get_html(self, url: str) -> str:
        """Descarga el HTML de una URL. Usado para OptiFine (sin API oficial)."""
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            raise LoaderError(f"Error al obtener HTML de {url}: {e}")