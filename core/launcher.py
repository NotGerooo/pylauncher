"""Lanza Minecraft usando minecraft-launcher-lib."""
import subprocess
import minecraft_launcher_lib as mcl
from pathlib import Path
from services.auth import Account
from config.settings import Settings
from utils.helpers import get_logger, is_windows

log = get_logger("launcher")


def launch(version: str, account: Account, settings: Settings, mc_dir: Path):
    """Construye el comando y lanza el proceso de Minecraft."""
    opts: dict = {
        "username":     account.username,
        "uuid":         account.uuid,
        "token":        account.access_token or "0",
        "jvmArguments": [f"-Xmx{settings.ram_mb}M", "-Xms512M"],
    }
    if settings.java_path:
        opts["executablePath"] = settings.java_path

    cmd = mcl.command.get_minecraft_command(version, str(mc_dir), opts)
    log.info("lanzando %s como %s", version, account.username)

    flags = {"creationflags": 0x00000008} if is_windows() else {}  # DETACHED_PROCESS
    subprocess.Popen(cmd, **flags)
