"""
services/optifine_service.py — Gero's Launcher
Soporte para OptiFine en dos modos:
  - installer: ejecuta el .jar de OptiFine para crear una versión standalone
  - mod:       copia el .jar de OptiFine dentro de /mods (requiere Forge)
"""
import json
import os
import re
import shutil
import subprocess
import urllib.request
import urllib.error
from typing import Callable

from utils.logger import get_logger
from config.constants import HTTP_TIMEOUT_SECONDS, USER_AGENT

log = get_logger()

# URL de la página de descargas de OptiFine (scraping del listado público)
_OPTIFINE_BASE  = "https://optifine.net"
_OPTIFINE_ADFLY = "https://optifine.net/adloadx?f=OptiFine_"

# Headers estándar para requests
_HEADERS = {"User-Agent": USER_AGENT}


class OptiFineError(Exception):
    pass


# ── Red ───────────────────────────────────────────────────────────────────────

def _fetch_text(url: str, timeout: int = HTTP_TIMEOUT_SECONDS) -> str:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def _download_file(url: str, dest: str,
                   progress: Callable[[int, int], None] | None = None):
    """Descarga url → dest con callback opcional (bytes_descargados, total)."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as r:
        total = int(r.headers.get("Content-Length") or 0)
        downloaded = 0
        with open(dest, "wb") as f:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress:
                    progress(downloaded, total)


# ── Listar versiones de OptiFine disponibles ──────────────────────────────────

def get_optifine_versions(mc_version: str) -> list[dict]:
    """
    Devuelve lista de versiones OptiFine disponibles para mc_version.
    Cada elemento: {"name": "OptiFine_1.20.1_HD_U_I6.jar", "url": "...", "label": "HD U I6"}
    Usa el listado público de optifine.net.
    """
    try:
        html = _fetch_text(f"{_OPTIFINE_BASE}/downloads", timeout=10)
    except Exception as e:
        log.warning(f"OptiFine: no se pudo obtener listado: {e}")
        return []

    # Buscamos bloques del tipo:
    # <a href='adloadx?f=OptiFine_1.20.1_HD_U_I6.jar'>... I6 ...</a>
    pattern = re.compile(
        r"adloadx\?f=(OptiFine_" + re.escape(mc_version) + r"_[^'\"]+\.jar)",
        re.IGNORECASE,
    )
    matches = pattern.findall(html)

    results = []
    seen = set()
    for filename in matches:
        if filename in seen:
            continue
        seen.add(filename)
        # Extraer etiqueta legible: "OptiFine_1.20.1_HD_U_I6.jar" → "HD U I6"
        label = filename.replace(f"OptiFine_{mc_version}_", "").replace(".jar", "").replace("_", " ")
        results.append({
            "name":  filename,
            "url":   f"{_OPTIFINE_BASE}/adloadx?f={filename}",
            "label": label,
        })

    if not results:
        log.warning(f"OptiFine: sin versiones para MC {mc_version}")

    return results


def get_optifine_direct_url(filename: str) -> str:
    """
    Resuelve la URL de descarga directa del .jar a partir de la página adloadx.
    OptiFine usa una redirección — extraemos el link directo del HTML.
    """
    try:
        html = _fetch_text(
            f"{_OPTIFINE_BASE}/adloadx?f={filename}", timeout=10)
        # Buscar: <a href="https://optifine.net/downloadx?f=...&x=...">
        m = re.search(
            r'href=["\']([^"\']*downloadx\?f=[^"\']+)["\']', html, re.IGNORECASE)
        if m:
            url = m.group(1)
            if not url.startswith("http"):
                url = _OPTIFINE_BASE + "/" + url.lstrip("/")
            return url
    except Exception as e:
        log.warning(f"OptiFine: no se pudo resolver URL directa para {filename}: {e}")
    # Fallback: intentar URL directa conocida
    return f"https://optifine.net/downloadx?f={filename}"


# ── Instalación ───────────────────────────────────────────────────────────────

def install_optifine_standalone(
    mc_version: str,
    optifine_filename: str,
    versions_dir: str,
    java_path: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> str:
    """
    Modo instalador: descarga OptiFine y ejecuta su .jar para crear
    una versión en versions_dir (ej: "1.20.1-OptiFine_HD_U_I6").
    Devuelve el ID de la versión creada.
    """
    def prog(msg: str):
        log.info(f"[OptiFine] {msg}")
        if progress_callback:
            progress_callback(msg)

    # 1. Verificar Java
    java = java_path or shutil.which("java")
    if not java or not os.path.isfile(java) and not shutil.which(java):
        raise OptiFineError(
            "Java no encontrado. Instala Java o configura la ruta en Ajustes.")

    # 2. Descargar el .jar
    prog(f"Descargando {optifine_filename}…")
    direct_url = get_optifine_direct_url(optifine_filename)
    dest_jar   = os.path.join(versions_dir, optifine_filename)
    try:
        def _prog_cb(dl, total):
            if total > 0:
                pct = int(dl / total * 100)
                prog(f"Descargando… {pct}%")
        _download_file(direct_url, dest_jar, progress=_prog_cb)
    except Exception as e:
        raise OptiFineError(f"Error al descargar OptiFine: {e}")

    if not os.path.isfile(dest_jar) or os.path.getsize(dest_jar) < 1000:
        raise OptiFineError(
            "Descarga incompleta o bloqueada. "
            "Descarga el .jar manualmente desde optifine.net e instálalo desde archivo.")

    # 3. Ejecutar el instalador de OptiFine
    prog("Ejecutando instalador OptiFine (puede tardar unos segundos)…")
    try:
        result = subprocess.run(
            [java, "-jar", dest_jar],
            capture_output=True,
            timeout=120,
            cwd=versions_dir,
        )
        log.debug(f"OptiFine stdout: {result.stdout.decode(errors='replace')}")
        if result.returncode != 0:
            log.warning(
                f"OptiFine installer returncode={result.returncode}: "
                f"{result.stderr.decode(errors='replace')}"
            )
    except subprocess.TimeoutExpired:
        raise OptiFineError("El instalador de OptiFine tardó demasiado (timeout 120s).")
    except Exception as e:
        raise OptiFineError(f"Error al ejecutar el instalador de OptiFine: {e}")

    # 4. Detectar la versión OptiFine creada en versions_dir
    prog("Detectando versión instalada…")
    version_id = _detect_optifine_version(
        mc_version, optifine_filename, versions_dir)

    if not version_id:
        raise OptiFineError(
            "OptiFine se instaló pero no se detectó la versión en versions/. "
            "Verifica que el directorio de versiones sea correcto.")

    prog(f"OptiFine instalado: {version_id}")
    return version_id


def install_optifine_as_mod(
    optifine_filename: str,
    mods_dir: str,
    versions_dir: str,
    progress_callback: Callable[[str], None] | None = None,
) -> str:
    """
    Modo mod: descarga OptiFine y lo coloca en mods_dir.
    Requiere Forge en la instancia.
    Devuelve la ruta al .jar copiado.
    """
    def prog(msg: str):
        log.info(f"[OptiFine-mod] {msg}")
        if progress_callback:
            progress_callback(msg)

    prog(f"Descargando {optifine_filename}…")
    direct_url = get_optifine_direct_url(optifine_filename)
    tmp_jar    = os.path.join(versions_dir, optifine_filename)

    try:
        def _prog_cb(dl, total):
            if total > 0:
                prog(f"Descargando… {int(dl/total*100)}%")
        _download_file(direct_url, tmp_jar, progress=_prog_cb)
    except Exception as e:
        raise OptiFineError(f"Error al descargar OptiFine: {e}")

    if not os.path.isfile(tmp_jar) or os.path.getsize(tmp_jar) < 1000:
        raise OptiFineError(
            "Descarga incompleta. Descarga el .jar manualmente desde optifine.net.")

    # Copiar a /mods
    os.makedirs(mods_dir, exist_ok=True)
    dest = os.path.join(mods_dir, optifine_filename)
    shutil.copy2(tmp_jar, dest)
    prog(f"OptiFine copiado a mods/: {optifine_filename}")
    return dest


def install_optifine_from_file(
    jar_path: str,
    mode: str,           # "installer" | "mod"
    mods_dir: str,
    versions_dir: str,
    mc_version: str,
    java_path: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> str:
    """
    Instala OptiFine desde un .jar local (el usuario lo descargó manualmente).
    mode='installer' → ejecuta el jar
    mode='mod'       → copia a mods_dir
    """
    def prog(msg: str):
        log.info(f"[OptiFine-file] {msg}")
        if progress_callback:
            progress_callback(msg)

    if not os.path.isfile(jar_path):
        raise OptiFineError(f"Archivo no encontrado: {jar_path}")

    filename = os.path.basename(jar_path)

    if mode == "mod":
        os.makedirs(mods_dir, exist_ok=True)
        dest = os.path.join(mods_dir, filename)
        shutil.copy2(jar_path, dest)
        prog(f"OptiFine copiado a mods/: {filename}")
        return dest
    else:
        # Copiar al versions_dir para ejecutarlo desde allí
        dest_jar = os.path.join(versions_dir, filename)
        if not os.path.samefile(jar_path, dest_jar) if os.path.isfile(dest_jar) else True:
            shutil.copy2(jar_path, dest_jar)

        java = java_path or shutil.which("java")
        if not java:
            raise OptiFineError("Java no encontrado.")

        prog("Ejecutando instalador OptiFine…")
        try:
            result = subprocess.run(
                [java, "-jar", dest_jar],
                capture_output=True, timeout=120, cwd=versions_dir,
            )
            if result.returncode != 0:
                log.warning(f"OptiFine installer: {result.stderr.decode(errors='replace')}")
        except subprocess.TimeoutExpired:
            raise OptiFineError("Timeout ejecutando OptiFine.")
        except Exception as e:
            raise OptiFineError(f"Error ejecutando OptiFine: {e}")

        version_id = _detect_optifine_version(mc_version, filename, versions_dir)
        if not version_id:
            raise OptiFineError("Instalación completada pero versión no detectada.")
        prog(f"OptiFine instalado: {version_id}")
        return version_id


# ── Detección de versión instalada ────────────────────────────────────────────

def _detect_optifine_version(
    mc_version: str,
    optifine_filename: str,
    versions_dir: str,
) -> str | None:
    """
    Busca en versions_dir carpetas cuyo nombre contenga mc_version y OptiFine.
    El instalador de OptiFine crea algo como:
      versions/1.20.1-OptiFine_HD_U_I6/1.20.1-OptiFine_HD_U_I6.json
    """
    if not os.path.isdir(versions_dir):
        return None

    # Primero intentar coincidencia exacta con el nombre del .jar
    # "OptiFine_1.20.1_HD_U_I6.jar" → buscar "1.20.1-OptiFine_HD_U_I6"
    jar_name  = optifine_filename.replace(".jar", "").replace(
        f"OptiFine_{mc_version}_", "")
    candidate = f"{mc_version}-OptiFine_{jar_name}"
    candidate_path = os.path.join(versions_dir, candidate, f"{candidate}.json")
    if os.path.isfile(candidate_path):
        return candidate

    # Búsqueda fuzzy: cualquier carpeta que contenga mc_version + OptiFine
    pattern = re.compile(
        re.escape(mc_version) + r".*[Oo]pt[Ii][Ff]ine", re.IGNORECASE)
    try:
        for entry in os.listdir(versions_dir):
            if pattern.search(entry):
                json_path = os.path.join(versions_dir, entry, f"{entry}.json")
                if os.path.isfile(json_path):
                    return entry
    except OSError:
        pass

    return None


def is_optifine_installed(
    mc_version: str,
    profile_game_dir: str,
    versions_dir: str,
) -> bool:
    """
    Retorna True si OptiFine ya está instalado para esta instancia:
    - Como mod en mods_dir, o
    - Como versión standalone en versions_dir
    """
    mods_dir = os.path.join(profile_game_dir, "mods")
    # Verificar modo mod
    if os.path.isdir(mods_dir):
        for f in os.listdir(mods_dir):
            if "optifine" in f.lower() or "OptiFine" in f:
                return True
    # Verificar modo standalone
    version_id = _detect_optifine_version(mc_version, "", versions_dir)
    return version_id is not None
