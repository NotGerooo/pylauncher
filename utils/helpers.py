"""Utilidades unificadas: logger, archivos, hash, sistema."""
import logging, hashlib, shutil, platform
from pathlib import Path


# ── Logger ────────────────────────────────────────────────
def setup_logger():
    from config.constants import LOGS_DIR
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOGS_DIR / "launcher.log", encoding="utf-8"),
        ],
    )

def get_logger(name: str = "zen") -> logging.Logger:
    return logging.getLogger(name)


# ── Archivos ──────────────────────────────────────────────
def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def safe_remove(p: Path):
    try:
        if p.is_file(): p.unlink()
        elif p.is_dir(): shutil.rmtree(p)
    except Exception:
        pass


# ── Hash ──────────────────────────────────────────────────
def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""): h.update(chunk)
    return h.hexdigest()


# ── Sistema ───────────────────────────────────────────────
def get_os() -> str:
    return platform.system().lower()   # windows | darwin | linux

def is_windows() -> bool:
    return get_os() == "windows"

def cpu_arch() -> str:
    return platform.machine().lower()  # amd64 | arm64

def ram_mb() -> int:
    try:
        import psutil
        return psutil.virtual_memory().total // (1024 * 1024)
    except Exception:
        return 4096
