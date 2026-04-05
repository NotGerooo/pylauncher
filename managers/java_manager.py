"""
java_manager.py
---------------
Detecta, valida y gestiona instalaciones de Java en el sistema.
Si no hay Java válido, lo descarga automáticamente desde los servidores de Mojang.
"""
import json
import os
import platform
import re
import shutil
import subprocess
import urllib.request
import zipfile

from config.constants import JAVA_MIN_VERSION, JAVA_RECOMMENDED_VERSION
from config.settings import Settings
from utils.system_utils import find_java_executables, _get_java_version
from utils.logger import get_logger

log = get_logger()

# URL del manifest de Java de Mojang (mismo que usa el launcher oficial)
_MOJANG_JAVA_MANIFEST = "https://launchermeta.mojang.com/v1/products/java-runtime/2ec0cc96c44e5a76b9c8b7c39df7210883d12871/all.json"

# Componente de Java que usa Minecraft 1.21+
_JAVA_COMPONENT = "java-runtime-delta"  # Java 21 para MC 1.21+

# Componentes alternativos por si el principal no está disponible
_JAVA_COMPONENTS_FALLBACK = [
    "java-runtime-gamma",   # Java 21 (el que usa MC 1.21+)
    "java-runtime-delta",   # Java 21 (alternativo)  
    "java-runtime-beta",    # Java 17
    "java-runtime-alpha",   # Java 8
]

class JavaNotFoundError(Exception):
    pass


class JavaVersionError(Exception):
    pass


class JavaManager:
    def __init__(self, settings: Settings):
        self._settings = settings

    def get_java_path(self) -> str:
        # 1. Ruta manual del perfil/settings
        manual_path = self._settings.java_path
        if manual_path:
            is_valid, version = self.validate_java_path(manual_path)
            if is_valid:
                log.info(f"Usando Java manual: {manual_path} (v{version})")
                return manual_path
            log.warning(f"Ruta manual de Java inválida: {manual_path}. Buscando automáticamente...")

        # 2. Java embebido ya descargado por el launcher
        embedded = self._get_embedded_java_path()
        if embedded:
            log.info(f"Usando Java embebido: {embedded}")
            return embedded

        # 3. Java instalado en el sistema
        try:
            return self._find_best_java()
        except (JavaNotFoundError, JavaVersionError):
            pass

        # 4. Descargar Java automáticamente desde Mojang
        log.info("No se encontró Java válido. Descargando desde Mojang...")
        return self.download_java()

    def validate_java_path(self, java_path: str) -> tuple:
        if not os.path.isfile(java_path):
            return False, "Archivo no encontrado"
        version_string = _get_java_version(java_path)
        if not version_string:
            return False, "No se pudo obtener la versión"
        major = self._parse_major_version(version_string)
        if major < JAVA_MIN_VERSION:
            return False, f"Versión {version_string} < mínimo requerido ({JAVA_MIN_VERSION})"
        return True, version_string

    def set_manual_java_path(self, java_path: str) -> bool:
        is_valid, version = self.validate_java_path(java_path)
        if is_valid:
            self._settings.java_path = java_path
            log.info(f"Ruta manual de Java guardada: {java_path} (v{version})")
            return True
        log.error(f"Ruta de Java inválida: {java_path} — {version}")
        return False

    def clear_manual_java_path(self):
        self._settings.java_path = ""

    def list_available_java(self) -> list:
        found = find_java_executables()
        result = []
        for entry in found:
            is_valid, version = self.validate_java_path(entry["path"])
            if is_valid:
                major = self._parse_major_version(version)
                result.append({
                    "path": entry["path"],
                    "version_string": version,
                    "major_version": major,
                    "is_recommended": major >= JAVA_RECOMMENDED_VERSION,
                })
        result.sort(key=lambda x: x["major_version"], reverse=True)
        log.info(f"Instalaciones de Java válidas: {len(result)}")
        return result

    def get_java_info(self) -> dict:
        try:
            path = self.get_java_path()
            _, version = self.validate_java_path(path)
            major = self._parse_major_version(version)
            source = "manual" if self._settings.java_path else "automático"
            return {
                "path": path, "version": version, "major_version": major,
                "source": source, "meets_minimum": major >= JAVA_MIN_VERSION,
                "is_recommended": major >= JAVA_RECOMMENDED_VERSION, "error": None,
            }
        except (JavaNotFoundError, JavaVersionError) as e:
            return {
                "path": None, "version": None, "major_version": 0,
                "source": None, "meets_minimum": False,
                "is_recommended": False, "error": str(e),
            }

    def download_java(self, progress_callback=None) -> str:
        """
        Descarga Java automáticamente desde los servidores de Mojang.
        Lo instala en .pylauncher/runtime/ igual que el launcher oficial.

        Returns:
            Ruta al ejecutable java.exe descargado

        Raises:
            JavaNotFoundError: Si la descarga falla
        """
        os_key = self._get_mojang_os_key()
        log.info(f"Descargando Java para {os_key} desde Mojang...")

        try:
            # Obtener manifest de componentes Java
            manifest = self._fetch_json(_MOJANG_JAVA_MANIFEST)

            # Intentar cada componente en orden de preferencia
            component = None
            component_name = None
            for comp in _JAVA_COMPONENTS_FALLBACK:
                os_data = manifest.get(os_key, {})
                comp_list = os_data.get(comp, [])
                if comp_list:
                    component = comp_list[0]
                    component_name = comp
                    break

            if not component:
                raise JavaNotFoundError(
                    f"No hay Java disponible para {os_key} en los servidores de Mojang."
                )

            log.info(f"Componente seleccionado: {component_name}")

            # Obtener manifest de archivos del componente
            manifest_url = component.get("manifest", {}).get("url", "")
            if not manifest_url:
                raise JavaNotFoundError("URL del manifest de Java no encontrada.")

            files_manifest = self._fetch_json(manifest_url)
            files = files_manifest.get("files", {})

            # Directorio destino
            runtime_dir = os.path.join(
                self._settings.minecraft_dir, "runtime", component_name
            )
            os.makedirs(runtime_dir, exist_ok=True)

            # Descargar archivos
            total = len(files)
            downloaded = 0
            errors = 0

            for file_path, file_info in files.items():
                file_type = file_info.get("type", "")
                dest = os.path.join(runtime_dir, *file_path.split("/"))

                if file_type == "directory":
                    os.makedirs(dest, exist_ok=True)
                    continue

                if file_type == "link":
                    # Symlinks — ignorar en Windows
                    continue

                if file_type != "file":
                    continue

                downloads = file_info.get("downloads", {})
                raw = downloads.get("raw", {})
                url = raw.get("url", "")
                if not url:
                    continue

                os.makedirs(os.path.dirname(dest), exist_ok=True)

                # No re-descargar si ya existe y tiene el tamaño correcto
                expected_size = raw.get("size", 0)
                if os.path.isfile(dest) and os.path.getsize(dest) == expected_size:
                    downloaded += 1
                    continue

                try:
                    req = urllib.request.Request(
                        url, headers={"User-Agent": "GeroLauncher/1.0"}
                    )
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        with open(dest, "wb") as f:
                            f.write(resp.read())
                            downloaded += 1
                            if downloaded % 50 == 0:
                                log.info(f"Java: {downloaded}/{total} archivos...")

                    # Hacer ejecutable en Linux/macOS
                    if file_info.get("executable", False) and os.name != "nt":
                        os.chmod(dest, 0o755)

                    downloaded += 1
                    if progress_callback and downloaded % 20 == 0:
                        progress_callback(f"Java ({downloaded}/{total})", downloaded, total)

                except Exception as e:
                    log.debug(f"Error descargando {file_path}: {e}")
                    errors += 1

            log.info(f"Java descargado: {downloaded} archivos, {errors} errores")

            # Buscar el ejecutable java dentro del directorio descargado
            java_exe = self._find_java_in_dir(runtime_dir)
            if not java_exe:
                raise JavaNotFoundError(
                    f"Java descargado pero no se encontró el ejecutable en {runtime_dir}"
                )

            log.info(f"Java listo en: {java_exe}")
            return java_exe

        except JavaNotFoundError:
            raise
        except Exception as e:
            raise JavaNotFoundError(f"Error descargando Java: {e}")

    def is_java_downloaded(self) -> bool:
        """Verifica si el Java embebido ya está descargado."""
        return self._get_embedded_java_path() is not None

    def get_java_path_for_component(self, component: str) -> str:
        """Obtiene Java para el componente exacto requerido por la versión de MC."""
        runtime_dir = os.path.join(self._settings.minecraft_dir, "runtime")
        comp_dir = os.path.join(runtime_dir, component)

        if os.path.isdir(comp_dir):
            java_exe = self._find_java_in_dir(comp_dir)
            if java_exe:
                is_valid, version = self.validate_java_path(java_exe)
                if is_valid:
                    log.info(f"Usando Java embebido: {java_exe}")
                    return java_exe

        # No está — descargar ese componente específico
        log.info(f"Componente {component} no encontrado, descargando...")
        os_key = self._get_mojang_os_key()
        manifest = self._fetch_json(_MOJANG_JAVA_MANIFEST)
        comp_list = manifest.get(os_key, {}).get(component, [])

        if not comp_list:
            log.warning(f"{component} no disponible para {os_key}, usando java-runtime-gamma")
            component = "java-runtime-gamma"
            comp_list = manifest.get(os_key, {}).get(component, [])

        if not comp_list:
            raise JavaNotFoundError(f"No hay Java disponible para {os_key}")

        component_data = comp_list[0]
        manifest_url = component_data.get("manifest", {}).get("url", "")
        if not manifest_url:
            raise JavaNotFoundError("URL del manifest de Java no encontrada.")

        files_manifest = self._fetch_json(manifest_url)
        files = files_manifest.get("files", {})

        runtime_dir_comp = os.path.join(self._settings.minecraft_dir, "runtime", component)
        os.makedirs(runtime_dir_comp, exist_ok=True)

        total = len(files)
        downloaded = 0
        log.info(f"Descargando Java {component}: {total} archivos...")

        for file_path, file_info in files.items():
            file_type = file_info.get("type", "")
            dest = os.path.join(runtime_dir_comp, *file_path.split("/"))

            if file_type == "directory":
                os.makedirs(dest, exist_ok=True)
                continue
            if file_type != "file":
                continue

            raw = file_info.get("downloads", {}).get("raw", {})
            url = raw.get("url", "")
            if not url:
                continue

            os.makedirs(os.path.dirname(dest), exist_ok=True)
            expected_size = raw.get("size", 0)
            if os.path.isfile(dest) and os.path.getsize(dest) == expected_size:
                continue

            try:
                req = urllib.request.Request(url, headers={"User-Agent": "GeroLauncher/1.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    with open(dest, "wb") as f:
                        f.write(resp.read())
                if file_info.get("executable", False) and os.name != "nt":
                    os.chmod(dest, 0o755)
            except Exception as e:
                log.debug(f"Error descargando {file_path}: {e}")

        java_exe = self._find_java_in_dir(runtime_dir_comp)
        if not java_exe:
            raise JavaNotFoundError(f"Java descargado pero ejecutable no encontrado en {runtime_dir_comp}")

        log.info(f"Java listo en: {java_exe}")
        return java_exe

    # ── Métodos internos ──────────────────────────────────────────────────────

    def _get_embedded_java_path(self) -> str | None:
        """Busca el Java descargado por el launcher en .pylauncher/runtime/."""
        runtime_dir = os.path.join(self._settings.minecraft_dir, "runtime")
        if not os.path.isdir(runtime_dir):
            return None

        for component in _JAVA_COMPONENTS_FALLBACK:
            comp_dir = os.path.join(runtime_dir, component)
            if not os.path.isdir(comp_dir):
                continue
            java_exe = self._find_java_in_dir(comp_dir)
            if java_exe:
                is_valid, _ = self.validate_java_path(java_exe)
                if is_valid:
                    return java_exe
        return None

    def _find_java_in_dir(self, root_dir: str) -> str | None:
        """Busca java.exe o java dentro de un directorio de runtime de Mojang."""
        # Estructura típica de Mojang: component/bin/java.exe
        candidates = []
        if os.name == "nt":
            exe_name = "java.exe"
        else:
            exe_name = "java"

        for dirpath, dirnames, filenames in os.walk(root_dir):
            if exe_name in filenames:
                candidates.append(os.path.join(dirpath, exe_name))

        if not candidates:
            return None

        # Preferir el que está en una carpeta "bin"
        for c in candidates:
            if os.sep + "bin" + os.sep in c:
                return c
        return candidates[0]

    def _find_best_java(self) -> str:
        candidates = self.list_available_java()
        if not candidates:
            raise JavaNotFoundError(
                f"No se encontró Java {JAVA_MIN_VERSION}+ instalado en el sistema."
            )
        best = candidates[0]
        if best["major_version"] < JAVA_MIN_VERSION:
            raise JavaVersionError(
                f"Java encontrado (v{best['version_string']}) es menor al mínimo requerido (v{JAVA_MIN_VERSION})"
            )
        log.info(f"Mejor Java encontrado: {best['path']} (v{best['version_string']})")
        return best["path"]

    def _get_mojang_os_key(self) -> str:
        """Devuelve la clave de OS que usa Mojang en su manifest."""
        system = platform.system().lower()
        machine = platform.machine().lower()

        if system == "windows":
            if machine in ("amd64", "x86_64"):
                return "windows-x64"
            return "windows-x86"
        elif system == "darwin":
            if machine == "arm64":
                return "mac-os-arm64"
            return "mac-os"
        else:
            if machine in ("aarch64", "arm64"):
                return "linux-arm64"
            return "linux"

    @staticmethod
    def _fetch_json(url: str) -> dict:
        req = urllib.request.Request(
            url, headers={"User-Agent": "GeroLauncher/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _parse_major_version(version_string: str) -> int:
        try:
            if version_string.startswith("1."):
                parts = version_string.split(".")
                return int(parts[1])
            match = re.match(r"(\d+)", version_string)
            if match:
                return int(match.group(1))
        except (ValueError, IndexError):
            pass
        return 0