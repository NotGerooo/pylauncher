"""
gui/views/mods_view.py — Deprecado
La gestión de mods ahora está dentro de cada instancia (instance_view.py → _ContentTab).
Este archivo se mantiene por compatibilidad pero no está en el sidebar.
"""
import flet as ft
from gui.theme import BG, TEXT_SEC, TEXT_DIM


class ModsView:
    def __init__(self, page: ft.Page, app):
        self.page = page
        self.app  = app
        self.root = ft.Container(
            expand=True,
            bgcolor=BG,
            content=ft.Column(
                [
                    ft.Text("🧩", size=48, text_align=ft.TextAlign.CENTER),
                    ft.Text("Gestión de Mods", color=TEXT_SEC, size=16,
                            weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                    ft.Text(
                        "Los mods ahora se gestionan dentro de cada instancia.\n"
                        "Ve a Biblioteca → abre una instancia → pestaña Content.",
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