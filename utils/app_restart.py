"""
utils/app_restart.py — Reinicia el launcher.

Se usa cuando un cambio (como el tema de colores) necesita que el
programa vuelva a arrancar desde cero para aplicarse.
"""
import os
import sys
import subprocess


def restart_app():
    """Cierra el proceso actual y abre uno nuevo del launcher."""
    if getattr(sys, "frozen", False):
        # Empaquetado como .exe (PyInstaller): sys.executable YA es el launcher.
        args = [sys.executable] + sys.argv[1:]
    else:
        # Corriendo como script de Python: hay que volver a pasar el script.
        args = [sys.executable] + sys.argv

    subprocess.Popen(args, close_fds=True)
    os._exit(0)
