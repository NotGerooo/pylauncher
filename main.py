import sys
import os
import ssl

# SSL fix debe ir ANTES de cualquier import del proyecto
ssl._create_default_https_context = ssl._create_unverified_context

# Asegurar que el directorio raiz del proyecto este en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ahora si importamos modulos del proyecto
from utils.logger import setup_logger
import flet as ft

def main(page: ft.Page):
    from gui.app import App
    App(page)

if __name__ == "__main__":
    setup_logger()
    ft.app(target=main)