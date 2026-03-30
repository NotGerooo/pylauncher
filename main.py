import sys
import os
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flet as ft

def main(page: ft.Page):
    from gui.app import App
    App(page)

ft.app(target=main)