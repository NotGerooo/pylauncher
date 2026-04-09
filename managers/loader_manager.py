"""
managers/loader_manager.py — Gero's Launcher
Instala mod loaders: Fabric, Forge, NeoForge, Quilt, Vanilla.
Guarda loader_meta.json dentro del game_dir del perfil.
"""
import json
import os
import re
import subprocess
import shutil
import urllib.request
import urllib.error

from utils.logger import get_logger
from config.constants import HTTP_TIMEOUT_SECONDS, USER_AGENT

log = get_logger()

LOADERS = ["vanilla", "fabric", "forge", "neoforge", "quilt"]


# ── Red ───────────────────────────────────────────────────────────────────────

def _get_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as r:
        return json.loads(r.read().decode())


def _download_file(url: str, dest: str):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as r:
        with open(dest, "wb") as f:
            while chunk := r.read(65536):
                f.write(chunk)


# ── Versiones disponibles ─────────────────────────────────────────────────────

def get_fabric_versions(mc_version: str) -> list[str]:
    try:
        data = _get_json(
            f"https://meta.fabricmc.net/v2/versions/loader/{mc_version}")
        return [v["loader"]["version"] for v in data]
    except Exception as e:
        log.warning(f"Fabric versions: {e}")
        return []


def get_quilt_versions(mc_version: str) -> list[str]:
    try:
        data = _get_json(
            f"https://meta.quiltmc.org/v3/versions/loader/{mc_version}")
        return [v["loader"]["version"] for v in data]
    except Exception as e:
        log.warning(f"Quilt versions: {e}")
        return []


def get_forge_versions(mc_version: str) -> list[str]:
    try:
        data = _get_json(
            "https://files.minecraftforge.net/net/minecraftforge/forge/maven-metadata.json")
        return data.get(mc_version, [])
    except Exception as e:
        log.warning(f"Forge versions: {e}")
        return []


def get_neoforge_versions(mc_version: str) -> list[str]:
    try:
        raw = urllib.request.urlopen(
            "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml",
            timeout=HTTP_TIMEOUT_SECONDS,
        ).read().decode()
        versions = re.findall(r"<version>([^<]+)</version>", raw)
        short = ".".join(mc_version.split(".")[1:])  # "1.21.1" -> "21.1"
        filtered = [v for v in versions if v.startswith(short + ".")]
        return list(reversed(filtered))
    except Exception as e:
        log.warning(f"NeoForge versions: {e}")
        return []


def get_loader_versions(loader: str, mc_version: str) -> list[str]:
    if loader == "fabric":   return get_fabric_versions(mc_version)
    if loader == "quilt":    return get_quilt_versions(mc_version)
    if loader == "forge":    return get_forge_versions(mc_version)
    if loader == "neoforge": return get_neoforge_versions(mc_version)
    return []


# ── OptiFine helpers (requeridos por optifine_service) ────────────────────────

def save_optifine_version_id(game_dir: str, version_id: str):
    """Persiste el version-id de OptiFine instalado en game_dir."""
    os.makedirs(game_dir, exist_ok=True)
    path = os.path.join(game_dir, "optifine_version.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"version_id": version_id}, f, indent=2)


def load_optifine_version_id(game_dir: str) -> str | None:
    """Devuelve el version-id de OptiFine guardado, o None si no existe."""
    path = os.path.join(game_dir, "optifine_version.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("version_id")
    except Exception:
        return None


def clear_optifine_version_id(game_dir: str):
    """Elimina el archivo optifine_version.json si existe."""
    path = os.path.join(game_dir, "optifine_version.json")
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


# ── Instalación ───────────────────────────────────────────────────────────────

class LoaderInstallError(Exception):
    pass


def install_loader(
    loader: str,
    mc_version: str,
    loader_version: str,
    game_dir: str,
    libraries_dir: str,
    versions_dir: str,
    progress_callback=None,
) -> dict:
    def prog(msg: str):
        log.info(msg)
        if progress_callback:
            progress_callback(msg)

    if loader == "vanilla" or not loader:
        meta = {"loader": "vanilla", "mc_version": mc_version,
                "loader_version": None, "main_class": None,
                "extra_libs": [], "args": []}
        _save_loader_meta(game_dir, meta)
        return meta
    if loader == "fabric":
        return _install_fabric(mc_version, loader_version, game_dir, libraries_dir, prog)
    if loader == "quilt":
        return _install_quilt(mc_version, loader_version, game_dir, libraries_dir, prog)
    if loader == "forge":
        return _install_forge(mc_version, loader_version, game_dir, libraries_dir, versions_dir, prog)
    if loader == "neoforge":
        return _install_neoforge(mc_version, loader_version, game_dir, libraries_dir, versions_dir, prog)
    raise LoaderInstallError(f"Loader desconocido: {loader}")


def _install_fabric(mc_version, loader_version, game_dir, libraries_dir, prog):
    prog(f"Descargando perfil Fabric {loader_version}…")
    try:
        profile = _get_json(
            f"https://meta.fabricmc.net/v2/versions/loader/{mc_version}/{loader_version}/profile/json")
    except Exception as e:
        raise LoaderInstallError(f"No se pudo obtener perfil Fabric: {e}")

    main_class = profile.get("mainClass", "")
    extra_libs = []
    libs = profile.get("libraries", [])
    for i, lib in enumerate(libs, 1):
        prog(f"Fabric: lib {i}/{len(libs)}")
        name    = lib.get("name", "")
        url     = lib.get("url", "https://maven.fabricmc.net/")
        parts   = name.split(":")
        if len(parts) < 3:
            continue
        group, artifact, version = parts[0], parts[1], parts[2]
        path    = f"{group.replace('.','/')}/{artifact}/{version}/{artifact}-{version}.jar"
        dest    = os.path.join(libraries_dir, *path.split("/"))
        dl_url  = url.rstrip("/") + "/" + path
        if not os.path.isfile(dest):
            try:
                _download_file(dl_url, dest)
            except Exception as ex:
                log.warning(f"Fabric lib fallida {name}: {ex}")
        extra_libs.append(dest)

    meta = {"loader": "fabric", "mc_version": mc_version,
            "loader_version": loader_version, "main_class": main_class,
            "extra_libs": extra_libs, "args": []}
    _save_loader_meta(game_dir, meta)
    prog("Fabric instalado.")
    return meta


def _install_quilt(mc_version, loader_version, game_dir, libraries_dir, prog):
    prog(f"Descargando perfil Quilt {loader_version}…")
    try:
        profile = _get_json(
            f"https://meta.quiltmc.org/v3/versions/loader/{mc_version}/{loader_version}/profile/json")
    except Exception as e:
        raise LoaderInstallError(f"No se pudo obtener perfil Quilt: {e}")

    main_class = profile.get("mainClass", "")
    extra_libs = []
    libs = profile.get("libraries", [])
    for i, lib in enumerate(libs, 1):
        prog(f"Quilt: lib {i}/{len(libs)}")
        name    = lib.get("name", "")
        url     = lib.get("url", "https://maven.quiltmc.org/repository/release/")
        parts   = name.split(":")
        if len(parts) < 3:
            continue
        group, artifact, version = parts[0], parts[1], parts[2]
        path    = f"{group.replace('.','/')}/{artifact}/{version}/{artifact}-{version}.jar"
        dest    = os.path.join(libraries_dir, *path.split("/"))
        dl_url  = url.rstrip("/") + "/" + path
        if not os.path.isfile(dest):
            try:
                _download_file(dl_url, dest)
            except Exception as ex:
                log.warning(f"Quilt lib fallida {name}: {ex}")
        extra_libs.append(dest)

    meta = {"loader": "quilt", "mc_version": mc_version,
            "loader_version": loader_version, "main_class": main_class,
            "extra_libs": extra_libs, "args": []}
    _save_loader_meta(game_dir, meta)
    prog("Quilt instalado.")
    return meta


def _install_forge(mc_version, loader_version, game_dir, libraries_dir, versions_dir, prog):
    if loader_version.startswith(mc_version + "-"):
        forge_id = loader_version
    else:
        forge_id = f"{mc_version}-{loader_version}"

    install_id = f"{mc_version}-forge-{forge_id.split(mc_version + '-')[1]}"

    prog(f"Descargando instalador Forge {forge_id}…")

    urls_to_try = [
        f"https://maven.minecraftforge.net/net/minecraftforge/forge/{forge_id}/forge-{forge_id}-installer.jar",
        f"https://files.minecraftforge.net/maven/net/minecraftforge/forge/{forge_id}/forge-{forge_id}-installer.jar",
    ]

    installer  = os.path.join(versions_dir, f"forge-{forge_id}-installer.jar")
    downloaded = False
    for url in urls_to_try:
        try:
            _download_file(url, installer)
            downloaded = True
            break
        except Exception as e:
            log.warning(f"URL Forge fallida: {url} — {e}")

    if not downloaded:
        raise LoaderInstallError(f"No se pudo descargar el instalador de Forge {forge_id}.")

    prog("Ejecutando instalador Forge (puede tardar 1-2 min)…")

    minecraft_dir = os.path.dirname(versions_dir)
    runtime_dir   = os.path.join(minecraft_dir, "runtime")
    java = None
    if os.path.isdir(runtime_dir):
        for root, dirs, files in os.walk(runtime_dir):
            for fn in files:
                if fn.lower() == "java.exe":
                    java = os.path.join(root, fn)
                    break
            if java:
                break
    if not java:
        java = shutil.which("java") or "java"

    log.info(f"Forge installer usando Java: {java}")

    # Forge legacy (≤1.12.2) usa --install-client, moderno usa --installClient
    mc_parts = [int(x) for x in mc_version.split(".") if x.isdigit()]
    is_legacy = mc_parts < [1, 13]  # 1.12.2 y anteriores

    if is_legacy:
        cmd_args = ["--install-client", minecraft_dir]
    else:
        cmd_args = ["--installClient", minecraft_dir]

    result = subprocess.run(
        [java, "-jar", installer] + cmd_args,
        capture_output=True, timeout=300,
    )

    stdout = result.stdout.decode(errors="replace")
    stderr = result.stderr.decode(errors="replace")
    log.info(f"Forge installer stdout: {stdout[-500:]}")

    if result.returncode != 0:
        log.warning(f"Forge installer returncode: {result.returncode}")
        log.warning(f"Forge installer stderr: {stderr[-500:]}")
        raise LoaderInstallError(
            f"El instalador de Forge falló (código {result.returncode}).\n"
            f"Detalle: {stderr[-300:]}"
        )

    # Verificar que la carpeta fue creada
    expected_dir = os.path.join(versions_dir, install_id)
    if not os.path.isdir(expected_dir):
        # Buscar qué carpeta nueva apareció (por si el nombre difiere)
        existing = set(os.listdir(versions_dir))
        raise LoaderInstallError(
            f"Forge instaló pero la carpeta '{install_id}' no fue creada.\n"
            f"Carpetas en versions/: {existing}"
        )

    meta = {
        "loader":         "forge",
        "mc_version":     mc_version,
        "loader_version": forge_id,
        "install_id":     install_id,
        "main_class":     None,
        "extra_libs":     [],
        "args":           [],
    }
    _save_loader_meta(game_dir, meta)
    prog(f"Forge instalado: {install_id}")
    return meta

def _install_neoforge(mc_version, loader_version, game_dir, libraries_dir, versions_dir, prog):
    prog(f"Descargando instalador NeoForge {loader_version}…")
    url = (f"https://maven.neoforged.net/releases/net/neoforged/neoforge"
           f"/{loader_version}/neoforge-{loader_version}-installer.jar")
    installer = os.path.join(versions_dir, f"neoforge-{loader_version}-installer.jar")
    try:
        _download_file(url, installer)
    except Exception as e:
        raise LoaderInstallError(f"No se pudo descargar instalador NeoForge: {e}")

    prog("Ejecutando instalador NeoForge (puede tardar 1-2 min)…")
    java          = shutil.which("java") or "java"
    minecraft_dir = os.path.dirname(versions_dir)  # .minecraft/, no versions/
    result = subprocess.run(
        [java, "-jar", installer, "--installClient", minecraft_dir],
        capture_output=True, timeout=300,
    )
    if result.returncode != 0:
        log.warning(f"Instalador NeoForge salió con código {result.returncode}")
        log.debug(result.stderr.decode(errors="replace"))

    meta = {
        "loader": "neoforge",
        "mc_version": mc_version,
        "loader_version": loader_version,
        "install_id": f"neoforge-{loader_version}",   # ← NUEVO
        "main_class": None,
        "extra_libs": [],
        "args": [],
    }
    _save_loader_meta(game_dir, meta)
    prog("NeoForge instalado.")
    return meta


# ── loader_meta.json ──────────────────────────────────────────────────────────

def _save_loader_meta(game_dir: str, meta: dict):
    os.makedirs(game_dir, exist_ok=True)
    with open(os.path.join(game_dir, "loader_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def load_loader_meta(game_dir: str) -> dict:
    path = os.path.join(game_dir, "loader_meta.json")
    if not os.path.isfile(path):
        return {"loader": "vanilla"}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {"loader": "vanilla"}
    except Exception:
        return {"loader": "vanilla"}
