"""
managers/loader_manager.py — Gero's Launcher
Instala mod loaders: Fabric, Forge, NeoForge, Quilt, OptiFine, Vanilla.
Guarda loader_meta.json dentro del game_dir del perfil.
"""
import json
import os
import re
import urllib.request
import urllib.error

from utils.logger import get_logger
from config.constants import HTTP_TIMEOUT_SECONDS, USER_AGENT

log = get_logger()

LOADERS = ["vanilla", "fabric", "forge", "neoforge", "quilt", "optifine"]


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


def get_optifine_versions(mc_version: str) -> list[str]:
    known = {
        "1.21.1": ["HD_U_J1"], "1.20.4": ["HD_U_I7"], "1.20.1": ["HD_U_I6"],
        "1.19.4": ["HD_U_H9"], "1.19.2": ["HD_U_H8"], "1.18.2": ["HD_U_H7"],
        "1.17.1": ["HD_U_G9"], "1.16.5": ["HD_U_G8"], "1.12.2": ["HD_U_F5"],
    }
    return known.get(mc_version, ["(instala manualmente)"])


def get_loader_versions(loader: str, mc_version: str) -> list[str]:
    if loader == "fabric":   return get_fabric_versions(mc_version)
    if loader == "quilt":    return get_quilt_versions(mc_version)
    if loader == "forge":    return get_forge_versions(mc_version)
    if loader == "neoforge": return get_neoforge_versions(mc_version)
    if loader == "optifine": return get_optifine_versions(mc_version)
    return []


# ── Instalación ───────────────────────────────────────────────────────────────

class LoaderInstallError(Exception):
    pass

def get_profiles(self):
    return self._profiles

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
    if loader == "optifine":
        return _install_optifine(mc_version, loader_version, game_dir, versions_dir, prog)
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
        name  = lib.get("name", "")
        url   = lib.get("url", "https://maven.fabricmc.net/")
        parts = name.split(":")
        if len(parts) < 3:
            continue
        group, artifact, version = parts[0], parts[1], parts[2]
        path   = f"{group.replace('.','/')}/{artifact}/{version}/{artifact}-{version}.jar"
        dest   = os.path.join(libraries_dir, *path.split("/"))
        dl_url = url.rstrip("/") + "/" + path
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
        name  = lib.get("name", "")
        url   = lib.get("url", "https://maven.quiltmc.org/repository/release/")
        parts = name.split(":")
        if len(parts) < 3:
            continue
        group, artifact, version = parts[0], parts[1], parts[2]
        path   = f"{group.replace('.','/')}/{artifact}/{version}/{artifact}-{version}.jar"
        dest   = os.path.join(libraries_dir, *path.split("/"))
        dl_url = url.rstrip("/") + "/" + path
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
    prog(f"Descargando instalador Forge {mc_version}-{loader_version}…")
    forge_id = f"{mc_version}-{loader_version}"
    url = (f"https://maven.minecraftforge.net/net/minecraftforge/forge"
           f"/{forge_id}/forge-{forge_id}-installer.jar")
    installer = os.path.join(versions_dir, f"forge-{forge_id}-installer.jar")
    try:
        _download_file(url, installer)
    except Exception as e:
        raise LoaderInstallError(f"No se pudo descargar instalador Forge: {e}")

    prog("Ejecutando instalador Forge (puede tardar 1-2 min)…")
    import subprocess, shutil
    java = shutil.which("java") or "java"
    subprocess.run([java, "-jar", installer, "--installClient", versions_dir],
                   capture_output=True, timeout=300)

    meta = {"loader": "forge", "mc_version": mc_version,
            "loader_version": loader_version, "main_class": None,
            "extra_libs": [], "args": []}
    _save_loader_meta(game_dir, meta)
    prog("Forge instalado.")
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
    import subprocess, shutil
    java = shutil.which("java") or "java"
    subprocess.run([java, "-jar", installer, "--installClient", versions_dir],
                   capture_output=True, timeout=300)

    meta = {"loader": "neoforge", "mc_version": mc_version,
            "loader_version": loader_version, "main_class": None,
            "extra_libs": [], "args": []}
    _save_loader_meta(game_dir, meta)
    prog("NeoForge instalado.")
    return meta


def _install_optifine(mc_version, loader_version, game_dir, versions_dir, prog):
    prog("OptiFine: guardando metadata…")
    mods_dir = os.path.join(game_dir, "mods")
    os.makedirs(mods_dir, exist_ok=True)
    meta = {
        "loader": "optifine",
        "mc_version": mc_version,
        "loader_version": loader_version,
        "main_class": None,
        "extra_libs": [],
        "args": [],
        "mods_dir": mods_dir,
        "note": f"Coloca el jar de OptiFine en: {mods_dir}",
    }
    _save_loader_meta(game_dir, meta)
    prog(f"OptiFine listo. Coloca el jar en:\n{mods_dir}")
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