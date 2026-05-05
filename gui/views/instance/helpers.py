# -*- coding: utf-8 -*-
"""
gui/views/instance/helpers.py
Constantes, tamaños de pool de hilos y funciones utilitarias puras
para el paquete de la vista de instancia.
"""
import os
import re
import json
import time
import datetime
from typing import Optional

import flet as ft

from gui.theme import CARD2_BG, TEXT_DIM
from utils.logger import get_logger

log = get_logger()

# ---------------------------------------------------------------------------
# C3: Constantes de Modrinth cargadas una sola vez al importar el módulo
# ---------------------------------------------------------------------------
try:
    from config.constants import MODRINTH_API_BASE_URL, HTTP_TIMEOUT_SECONDS, USER_AGENT
    _MODRINTH_BASE = MODRINTH_API_BASE_URL
    _HTTP_TIMEOUT  = HTTP_TIMEOUT_SECONDS
    _USER_AGENT    = USER_AGENT
except ImportError:
    _MODRINTH_BASE = "https://api.modrinth.com/v2"
    _HTTP_TIMEOUT  = 15
    _USER_AGENT    = "PyLauncher/1.0"

# ---------------------------------------------------------------------------
# P4: Tamaños de pool de hilos configurables via variables de entorno
# ---------------------------------------------------------------------------
SHA1_WORKERS  = int(os.environ.get("PYLAUNCHER_SHA1_WORKERS", "8"))
ICON_WORKERS  = int(os.environ.get("PYLAUNCHER_ICON_WORKERS", "6"))
AUTH_WORKERS  = int(os.environ.get("PYLAUNCHER_AUTH_WORKERS", "8"))
MAX_UPLOAD_MB = int(os.environ.get("PYLAUNCHER_MAX_UPLOAD_MB", "500"))

LOADER_ICONS = {
    "vanilla":  "Game",
    "fabric":   "Fabric",
    "neoforge": "NeoForge",
    "forge":    "Forge",
    "quilt":    "Quilt",
}

_VALID_LOADERS = ("vanilla", "fabric", "forge", "neoforge", "quilt")
_VALID_TABS    = ("content", "files", "worlds", "logs")

# S1: guard de metacaracteres de shell
_SHELL_META = re.compile(r"[;&|`\n\r]")
_MIN_RAM_MB = 256
_MAX_RAM_MB = 32_768


# =============================================================================
# C1: helper de loader (era duplicado 5 veces en el archivo original)
# =============================================================================
def _read_loader(game_dir: str) -> str:
    """Devuelve el tipo de mod-loader de un directorio de instancia."""
    meta_path = os.path.join(game_dir, "loader_meta.json")
    if os.path.isfile(meta_path):
        try:
            with open(meta_path) as f:
                meta = json.load(f)
            entries = meta if isinstance(meta, list) else [meta]
            if entries:
                return (
                    entries[0].get("loader_type")
                    or entries[0].get("loader", "vanilla")
                )
        except Exception:
            pass
    return "vanilla"


# =============================================================================
# C2: helper de OptiFine (era duplicado en 3 clases)
# =============================================================================
def _check_optifine_installed(
    version_id: str,
    game_dir: str,
    versions_dir: str,
) -> bool:
    try:
        from services.optifine_service import is_optifine_installed
        return is_optifine_installed(version_id, game_dir, versions_dir)
    except Exception:
        return False


# =============================================================================
# S1: sanitizador de configuración de instancia
# =============================================================================
def _sanitize_settings(data: dict) -> dict:
    """Devuelve una copia saneada de los datos de configuración de instancia."""
    out: dict = {}

    try:
        ram = int(data.get("ram_mb", 4096))
    except (TypeError, ValueError):
        ram = 4096
    out["ram_mb"] = max(_MIN_RAM_MB, min(_MAX_RAM_MB, ram))

    java = str(data.get("java_path", "")).strip()
    out["java_path"] = "" if _SHELL_META.search(java) else java

    jvm = str(data.get("jvm_args", "")).strip()
    out["jvm_args"] = _SHELL_META.sub("", jvm)

    for key in ("pre_launch", "post_exit"):
        out[key] = str(data.get(key, ""))[:2048].strip()

    loader = str(data.get("loader", "vanilla")).lower()
    if loader not in _VALID_LOADERS:
        loader = "vanilla"
    out["loader"] = loader

    out["notes"] = str(data.get("notes", ""))[:512]

    tab = str(data.get("active_tab", "content"))
    if tab not in _VALID_TABS:
        tab = "content"
    out["active_tab"] = tab

    return out


# =============================================================================
# Helpers varios
# =============================================================================
def _fmt_last_played(ts: Optional[float]) -> str:
    """Formatea un timestamp Unix como texto legible 'última vez jugada'."""
    if not ts:
        return "Never played"
    try:
        dt    = datetime.datetime.fromtimestamp(ts)
        now   = datetime.datetime.now()
        delta = now - dt
        if delta.days == 0:
            h = delta.seconds // 3600
            if h == 0:
                m = delta.seconds // 60
                return f"{m}m ago" if m else "Just now"
            return f"{h}h ago"
        if delta.days == 1:
            return "Yesterday"
        if delta.days < 7:
            return f"{delta.days} days ago"
        return dt.strftime("%d %b %Y")
    except Exception:
        return "Never played"


def _parse_version(filename: str) -> str:
    name = re.sub(r'\.(jar|zip|disabled)$', '', filename, flags=re.IGNORECASE)
    for part in reversed(name.split('-')):
        if re.match(r'^\d+\.\d+', part):
            return part
    return ""


def _icon(url: str, title: str, size: int = 40) -> ft.Control:
    fallback = ft.Container(
        width=size, height=size, border_radius=8,
        bgcolor=CARD2_BG, alignment=ft.alignment.center,
        content=ft.Icon(ft.icons.EXTENSION_ROUNDED,
                        color=TEXT_DIM, size=int(size * 0.50)),
    )
    if not url:
        return fallback
    return ft.Image(
        src=url, width=size, height=size,
        border_radius=8, fit=ft.ImageFit.COVER,
        error_content=fallback,
    )


def _read_instance_setting(game_dir: str, key: str, default):
    """Lee un valor del archivo instance_settings.json de la instancia."""
    path = os.path.join(game_dir, "instance_settings.json")
    try:
        if os.path.isfile(path):
            with open(path) as f:
                return json.load(f).get(key, default)
    except Exception:
        pass
    return default


def _write_instance_setting(game_dir: str, key: str, value) -> None:
    """Escribe un valor en instance_settings.json de la instancia."""
    path = os.path.join(game_dir, "instance_settings.json")
    data: dict = {}
    try:
        if os.path.isfile(path):
            with open(path) as f:
                data = json.load(f)
    except Exception:
        pass
    data[key] = value
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
