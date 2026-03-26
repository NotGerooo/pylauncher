import sys
import os
import ssl

# SSL fix for PyInstaller bundled builds
ssl._create_default_https_context = ssl._create_unverified_context

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flet as ft
from utils.logger import setup_logger


def main(page: ft.Page):
    setup_logger()
    from gui.app import App
    App(page)


if __name__ == "__main__":
    ft.app(target=main)