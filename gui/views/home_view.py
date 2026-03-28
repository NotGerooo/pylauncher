"""
gui/views/home_view.py — Placeholder vacío (por ahora)
"""
import flet as ft
from gui.theme import BG, TEXT_SEC, TEXT_DIM


class HomeView:
    def __init__(self, page: ft.Page, app):
        self.page = page
        self.app  = app
        self.root = ft.Container(
            expand=True,
            bgcolor=BG,
            content=ft.Column(
                [
                    ft.Text("🏠", size=52, text_align=ft.TextAlign.CENTER),
                    ft.Text("Inicio", color=TEXT_SEC, size=20,
                            weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                    ft.Text("Próximamente", color=TEXT_DIM, size=11,
                            text_align=ft.TextAlign.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                expand=True,
            ),
        )

    def on_show(self):
        pass