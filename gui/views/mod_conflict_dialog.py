# -*- coding: utf-8 -*-
"""
gui/views/mod_conflict_dialog.py
Diálogo que se muestra cuando un mod no tiene ninguna versión
compatible con los mods ya instalados en el perfil.
"""
import flet as ft

from gui.theme import CARD_BG, CARD2_BG, BORDER, TEXT_PRI, TEXT_SEC, TEXT_DIM, ACCENT_RED


def _mini_icon(url: str, title: str) -> ft.Control:
    fallback = ft.Container(
        width=32, height=32, border_radius=8,
        bgcolor=CARD2_BG, alignment=ft.alignment.center,
        content=ft.Text(
            (title[0] if title else "?").upper(),
            color=TEXT_DIM, size=13, weight=ft.FontWeight.BOLD,
        ),
    )
    if not url:
        return fallback
    return ft.Image(
        src=url, width=32, height=32,
        border_radius=8, fit=ft.ImageFit.COVER,
        error_content=fallback,
    )


def show_mod_conflict_dialog(page: ft.Page, new_mod_title: str, conflicting_projects: list):
    rows = []
    for proj in conflicting_projects:
        rows.append(
            ft.Container(
                bgcolor=CARD2_BG,
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=10, vertical=8),
                content=ft.Row(
                    [
                        _mini_icon(getattr(proj, "icon_url", ""), getattr(proj, "title", "?")),
                        ft.Container(width=10),
                        ft.Text(getattr(proj, "title", "Mod desconocido"),
                                color=TEXT_PRI, size=12, weight=ft.FontWeight.W_500),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )

    dlg = ft.AlertDialog(
        bgcolor=CARD_BG,
        shape=ft.RoundedRectangleBorder(radius=14),
        title=ft.Row(
            [
                ft.Icon(ft.icons.WARNING_ROUNDED, color=ACCENT_RED, size=20),
                ft.Container(width=8),
                ft.Text("Mod incompatible", color=TEXT_PRI, size=15,
                        weight=ft.FontWeight.W_700),
            ],
            spacing=0, tight=True,
        ),
        content=ft.Container(
            width=380,
            content=ft.Column(
                [
                    ft.Text(
                        f"'{new_mod_title}' no tiene ninguna versión compatible "
                        f"con los siguientes mods que ya tenés instalados:",
                        color=TEXT_SEC, size=12,
                    ),
                    ft.Container(height=12),
                    ft.Column(rows, spacing=6),
                    ft.Container(height=8),
                    ft.Text(
                        "Desinstalá o deshabilitá alguno de estos mods "
                        "para poder instalar el nuevo.",
                        color=TEXT_DIM, size=11,
                    ),
                ],
                spacing=0, tight=True,
            ),
        ),
        actions=[
            ft.TextButton(
                "Entendido",
                style=ft.ButtonStyle(color=TEXT_SEC),
                on_click=lambda e: page.close(dlg),
            ),
        ],
    )
    page.open(dlg)