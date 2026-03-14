"""
file_utils.py
-------------
Operaciones seguras de sistema de archivos.
"""
import os
import shutil
from utils.logger import get_logger
log = get_logger()


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def safe_delete_file(path: str) -> bool:
    try:
        if os.path.isfile(path):
            os.remove(path)
            log.debug(f"Archivo eliminado: {path}")
            return True
        return False
    except OSError as e:
        log.error(f"Error al eliminar archivo {path}: {e}")
        return False


def safe_delete_dir(path: str) -> bool:
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
            log.debug(f"Directorio eliminado: {path}")
            return True
        return False
    except OSError as e:
        log.error(f"Error al eliminar directorio {path}: {e}")
        return False


def copy_file(src: str, dst: str) -> bool:
    try:
        ensure_dir(os.path.dirname(dst))
        shutil.copy2(src, dst)
        log.debug(f"Archivo copiado: {src} -> {dst}")
        return True
    except OSError as e:
        log.error(f"Error al copiar {src} -> {dst}: {e}")
        return False


def list_files_by_extension(directory: str, extension: str) -> list:
    results = []
    if not os.path.isdir(directory):
        return results
    for filename in os.listdir(directory):
        if filename.lower().endswith(f".{extension.lower()}"):
            results.append(os.path.join(directory, filename))
    return results


def get_file_size_mb(path: str) -> float:
    try:
        return os.path.getsize(path) / (1024 * 1024)
    except OSError:
        return 0.0
