import sys
import os
import ssl

# SSL fix for PyInstaller bundled builds
ssl._create_default_https_context = ssl._create_unverified_context

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import traceback
import flet as ft

def main(page: ft.Page):
    try:
        from gui.app import App
        App(page)
    except Exception as e:
        traceback.print_exc()
        # También mostrarlo en pantalla
        page.add(ft.Text(str(e), color="red", size=12))
        page.add(ft.Text(traceback.format_exc(), color="red", size=10))
        page.update()

ft.app(target=main)