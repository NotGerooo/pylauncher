import sys
import os
import ssl
import ctypes  # 👈 AÑADE ESTO

# SSL fix
ssl._create_default_https_context = ssl._create_unverified_context

# 🔥 APP ID (AQUÍ EXACTO)
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
    'geros.launcher.minecraft.1.0'
)

# Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import setup_logger
import flet as ft

def main(page: ft.Page):
    page.title = "Gero's Launcher"
    
    # 👇 AGREGA ESTO
    page.window.icon = "Gero´s Launcher.ico"
    
    from gui.app import App
    App(page)

if __name__ == "__main__":
    setup_logger()
    ft.app(target=main)