"""
gui/views/profiles_view.py — Deprecado
La creación/edición de instancias está en library_view.py.
Este archivo se mantiene por compatibilidad.
"""
import flet as ft
from gui.theme import BG, TEXT_SEC, TEXT_DIM


class ProfilesView:
    def __init__(self, page: ft.Page, app):
        self.page = page
        self.app  = app
        self.root = ft.Container(
            expand=True,
            bgcolor=BG,
            content=ft.Column(
                [
                    ft.Text("📦", size=48, text_align=ft.TextAlign.CENTER),
                    ft.Text("Instancias", color=TEXT_SEC, size=16,
                            weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                    ft.Text(
                        "Gestiona tus instancias desde la Biblioteca.",
                        color=TEXT_DIM, size=10, text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=12),
                    ft.Row(
                        [ft.ElevatedButton(
                            "Ir a Biblioteca",
                            on_click=lambda e: app._show_view("library"),
                        )],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                expand=True,
                spacing=10,
            ),
        )

    def on_show(self):
        pass