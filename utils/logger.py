"""
logger.py
---------
Sistema de logging centralizado para todo el launcher.
Una sola instancia compartida. Escribe a consola y a archivo .log

Cuando corre como .exe (PyInstaller), los logs van a:
  %APPDATA%\\GerosLauncher\\logs\\

En desarrollo normal van a:
  logs\   (carpeta local del proyecto)
"""
import logging
import os
import sys
from datetime import datetime

def setup_logger() -> logging.Logger:
    # Si está corriendo como .exe compilado, usar AppData
    if getattr(sys, "frozen", False):
        log_dir = os.path.join(os.environ.get("APPDATA", ""), "GerosLauncher", "logs")
    else:
        log_dir = "logs"

    os.makedirs(log_dir, exist_ok=True)

    log_filename = os.path.join(
        log_dir,
        f"launcher_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    logger = logging.getLogger("MinecraftLauncher")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)-8s] [%(module)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info(f"Logger iniciado. Archivo de log: {log_filename}")
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("MinecraftLauncher")