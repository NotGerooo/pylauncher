"""
Sync silenciosa con GitHub — pull al iniciar, push tras sesión.
Usa subprocess git; falla silenciosamente si git no está disponible.
"""
import subprocess, threading
from pathlib import Path
from utils.helpers import get_logger

log = get_logger("sync")


def _git(args: list[str], cwd: Path) -> bool:
    """Ejecuta un comando git silenciosamente. Devuelve True si OK."""
    try:
        r = subprocess.run(
            ["git", *args], cwd=cwd,
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            log.debug("git %s: %s", args[0], r.stderr.strip())
        return r.returncode == 0
    except Exception as e:
        log.debug("git no disponible: %s", e)
        return False


def pull(cwd: Path, on_done=None):
    """Pull silencioso en background thread."""
    def _w():
        ok = _git(["pull", "--ff-only", "origin", "main"], cwd)
        log.info("git pull → %s", "ok" if ok else "skipped")
        if on_done: on_done(ok)
    threading.Thread(target=_w, daemon=True, name="git-pull").start()


def push(cwd: Path, msg: str = "sync", on_done=None):
    """Stage all + commit + push en background thread."""
    def _w():
        _git(["add", "-A"], cwd)
        _git(["commit", "-m", msg, "--allow-empty"], cwd)
        ok = _git(["push", "origin", "main"], cwd)
        log.info("git push → %s", "ok" if ok else "failed")
        if on_done: on_done(ok)
    threading.Thread(target=_w, daemon=True, name="git-push").start()


def auto_sync(cwd: Path):
    """Llama al iniciar la app: hace pull si el directorio es un repo."""
    if (cwd / ".git").is_dir():
        pull(cwd)
