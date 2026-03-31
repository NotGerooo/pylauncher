"""
updater.py
----------
Auto-updater para Gero's Launcher.

Al iniciar, consulta un endpoint JSON con la versión más reciente.
Si hay una versión nueva, descarga el .exe, escribe un .bat que
reemplaza el ejecutable actual y reinicia el launcher.

Endpoint esperado:
{
    "version": "1.0.1",
    "url": "https://ejemplo.com/GerosLauncher.exe"
}
"""

import os
import sys
import json
import tempfile
import subprocess
import threading
import requests
from utils.logger import get_logger

log = get_logger()

CURRENT_VERSION = "1.0.0"
UPDATE_CHECK_URL = "https://tu-servidor.com/gerosLauncher_version.json"


def _parse_version(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0,)


def check_for_update() -> dict | None:
    """
    Consulta el endpoint de versión.
    Retorna el dict con 'version' y 'url' si hay actualización,
    o None si ya está al día o hay error de red.
    """
    try:
        resp = requests.get(UPDATE_CHECK_URL, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        remote_ver = data.get("version", "0.0.0")
        if _parse_version(remote_ver) > _parse_version(CURRENT_VERSION):
            log.info(f"Actualización disponible: {CURRENT_VERSION} → {remote_ver}")
            return data
        log.info(f"Launcher al día (v{CURRENT_VERSION})")
        return None
    except Exception as e:
        log.warning(f"No se pudo verificar actualizaciones: {e}")
        return None


def download_update(url: str, progress_callback=None) -> str:
    """
    Descarga el nuevo .exe a una carpeta temporal.

    Args:
        url: URL directa del nuevo ejecutable
        progress_callback: función(percent: float) opcional

    Returns:
        Ruta al archivo descargado
    """
    tmp_path = os.path.join(tempfile.gettempdir(), "GerosLauncher_update.exe")
    log.info(f"Descargando actualización desde {url}...")

    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(tmp_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total > 0:
                        progress_callback((downloaded / total) * 100)

    log.info(f"Actualización descargada en: {tmp_path}")
    return tmp_path


def _write_replace_bat(new_exe: str, current_exe: str) -> str:
    """
    Escribe el .bat que espera a que el launcher se cierre,
    reemplaza el .exe y lo reinicia.

    Returns:
        Ruta al .bat generado
    """
    bat_path = os.path.join(tempfile.gettempdir(), "geros_update.bat")
    bat_content = f"""@echo off
timeout /t 2 /nobreak >nul
move /y "{new_exe}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
"""
    with open(bat_path, "w") as f:
        f.write(bat_content)
    return bat_path


def apply_update(new_exe_path: str):
    """
    Escribe el .bat de reemplazo y cierra el launcher.
    El .bat tomará el control, reemplazará el .exe y lo relanzará.
    """
    current_exe = sys.executable if getattr(sys, "frozen", False) else sys.executable
    bat_path = _write_replace_bat(new_exe_path, current_exe)
    log.info(f"Aplicando actualización con script: {bat_path}")
    subprocess.Popen(
        ["cmd.exe", "/c", bat_path],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True,
    )
    sys.exit(0)


def run_update_check_async(on_update_available):
    """
    Ejecuta la verificación en un hilo separado para no bloquear la UI.

    Args:
        on_update_available: callback(update_info: dict) llamado en el hilo principal
                             si hay una actualización disponible.
    """
    def _worker():
        info = check_for_update()
        if info:
            on_update_available(info)

    threading.Thread(target=_worker, daemon=True).start()