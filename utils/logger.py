"""
logger.py
---------
Sistema de logging centralizado para todo el launcher.
Una sola instancia compartida. Escribe a consola y a archivo .log
"""
import sys
import logging
import os
from datetime import datetime


def setup_logger() -> logging.Logger:
    if getattr(sys, "frozen", False):
        base = os.path.join(os.environ.get("APPDATA", ""), "GerosLauncher", "logs")
    else:
        base = "logs"

    os.makedirs(base, exist_ok=True)
    log_filename = os.path.join(
        base,
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
    """
    Obtiene el logger ya configurado desde cualquier módulo.
    Llamar setup_logger() primero desde main.py.
    """
    return logging.getLogger("MinecraftLauncher")
