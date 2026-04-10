"""Zen Launcher — entry point."""
import sys, os, ssl

ssl._create_default_https_context = ssl._create_unverified_context
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("zen.launcher.1.0")
except Exception:
    pass

import flet as ft
from utils.helpers import setup_logger


def main(page: ft.Page):
    from gui.app import App
    App(page)


if __name__ == "__main__":
    setup_logger()
    ft.app(target=main, assets_dir="assets")
