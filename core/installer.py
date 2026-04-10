"""
Instalador de versiones Minecraft usando minecraft-launcher-lib.
Instala: pip install minecraft-launcher-lib
"""
import minecraft_launcher_lib as mcl
from pathlib import Path
from utils.helpers import get_logger

log = get_logger("installer")


def get_versions() -> list[dict]:
    """Lista versiones release disponibles de Mojang."""
    try:
        return [v for v in mcl.utils.get_version_list() if v["type"] == "release"]
    except Exception as e:
        log.error("fetch versions: %s", e)
        return []


def install(version: str, mc_dir: Path, on_progress=None, on_status=None):
    """Instala una versión; notifica progreso y estado vía callbacks."""
    mc_dir.mkdir(parents=True, exist_ok=True)
    total, done = [0], [0]

    callbacks = {
        "setMax":      lambda n: total.__setitem__(0, n),
        "setProgress": lambda _: (
            done.__setitem__(0, done[0] + 1),
            on_progress and total[0] and on_progress(done[0] / total[0] * 100),
        ),
        "setStatus":   lambda s: on_status and on_status(s),
    }
    mcl.install.install_minecraft_version(version, str(mc_dir), callbacks)
    log.info("instalado %s", version)
