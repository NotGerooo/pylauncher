"""
utils/app_restart.py — Reinicia el launcher.

Se usa cuando un cambio (como el tema de colores) necesita que el
programa vuelva a arrancar desde cero para aplicarse.
"""
import os
import sys
import subprocess
import threading


def restart_app(page=None):
    """
    Abre una copia nueva del launcher y cierra la actual de forma prolija.

    Antes esto solo hacía os._exit(0), pero en Flet la ventana (la parte
    visual) corre separada del proceso de Python — si matás el Python de
    golpe sin avisarle, la ventana se puede quedar colgada en vez de
    cerrarse. Por eso ahora, si se le pasa `page`, primero le pedimos
    que cierre la ventana de forma normal (page.window.close()), y recién
    si eso no alcanza en 1.5 segundos, forzamos el cierre del proceso
    como red de seguridad.
    """
    if getattr(sys, "frozen", False):
        # Empaquetado como .exe (PyInstaller): sys.executable YA es el launcher.
        args = [sys.executable] + sys.argv[1:]
    else:
        # Corriendo como script de Python: hay que volver a pasar el script.
        args = [sys.executable] + sys.argv

    # 1) Lanzar la copia nueva primero, para que siempre haya un launcher abierto.
    subprocess.Popen(args, close_fds=True)

    # 2) Pedirle a la ventana actual que se cierre de forma prolija.
    if page is not None:
        try:
            page.window.close()
        except Exception:
            pass

    # 3) Red de seguridad: si el proceso no terminó solo, lo forzamos.
    threading.Timer(1.5, lambda: os._exit(0)).start()
