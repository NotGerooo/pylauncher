"""Detección de Java instalado."""
import shutil, subprocess
from pathlib import Path
from utils.helpers import get_logger

log = get_logger("java")


def find_java() -> str | None:
    """Devuelve la ruta al ejecutable java, o None si no se encuentra."""
    if path := shutil.which("java"):
        return path
    candidates = [
        Path(r"C:\Program Files\Java"),
        Path(r"C:\Program Files\Eclipse Adoptium"),
        Path(r"C:\Program Files\Microsoft"),
        Path.home() / ".zen_launcher" / "jre",
    ]
    for base in candidates:
        if base.is_dir():
            for java in base.rglob("java.exe"):
                return str(java)
    return None


def java_version(java_path: str) -> str:
    """Devuelve la versión de Java del binario dado."""
    try:
        r = subprocess.run([java_path, "-version"],
                           capture_output=True, text=True, timeout=5)
        return (r.stderr or r.stdout).split("\n")[0]
    except Exception:
        return "unknown"
