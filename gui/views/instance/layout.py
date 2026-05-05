# -*- coding: utf-8 -*-
"""
gui/views/instance/layout.py
Funciones que construyen la UI de InstanceView.
Todas reciben `self` como primer argumento para poder ser inyectadas
como métodos de la clase vía asignación directa en __init__.py.
"""
from typing import Optional

import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, BORDER,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV,
)
from gui.views.instance.helpers import (
    _read_loader, _check_optifine_installed, _fmt_last_played,
    _read_instance_setting, _write_instance_setting,
    _VALID_TABS,
)


# ---------------------------------------------------------------------------
# count_items — estadísticas para los badges de las pestañas
# ---------------------------------------------------------------------------
def _count_items(self) -> dict[str, int]:
    """Cuenta ítems por categoría para los badges del tab bar (U2)."""
    import os
    counts: dict[str, int] = {"Mods": 0, "Resource Packs": 0, "Shaders": 0}
    specs = {
        "Mods":           ("mods",          (".jar", ".jar.disabled")),
        "Resource Packs": ("resourcepacks", (".zip", ".zip.disabled")),
        "Shaders":        ("shaderpacks",   (".zip", ".zip.disabled")),
    }
    for cat, (dirname, exts) in specs.items():
        d = os.path.join(self.profile.game_dir, dirname)
        if os.path.isdir(d):
            counts[cat] = sum(
                1 for fn in os.listdir(d)
                if any(fn.lower().endswith(x) for x in exts)
            )
    return counts


# ---------------------------------------------------------------------------
# make_tab_btn — botón de pestaña animado
# ---------------------------------------------------------------------------
def _make_tab_btn(
    self,
    tid: str,
    label: str,
    icon,
    count: Optional[int],
) -> ft.Container:
    active     = tid == self._active_tab
    label_text = label if not count else f"{label}  {count}"
    btn = ft.Container(
        bgcolor=GREEN if active else "transparent",
        border_radius=20,
        padding=ft.padding.symmetric(horizontal=16, vertical=8),
        animate=ft.animation.Animation(150, ft.AnimationCurve.EASE_OUT),
        on_click=lambda e, t=tid: self._switch_tab(t),
        content=ft.Row([
            ft.Icon(icon, size=14, color=TEXT_INV if active else TEXT_SEC),
            ft.Container(width=6),
            ft.Text(label_text,
                    color=TEXT_INV if active else TEXT_SEC,
                    size=11, weight=ft.FontWeight.W_600),
        ], spacing=0, tight=True),
    )
    btn.on_hover = lambda e, b=btn, t=tid: (
        None if t == self._active_tab else (
            setattr(b, "bgcolor", CARD2_BG if e.data == "true" else "transparent")
            or b.update()
        )
    )
    return btn


# ---------------------------------------------------------------------------
# build — construye el árbol visual completo de InstanceView
# ---------------------------------------------------------------------------
def _build(self) -> None:
    loader      = _read_loader(self.profile.game_dir)
    last_played = _fmt_last_played(
        _read_instance_setting(self.profile.game_dir, "last_played", None)
    )
    notes = _read_instance_setting(self.profile.game_dir, "notes", "")

    # U4: Botón Play — texto actualizado en vivo durante el lanzamiento
    self._play_btn = ft.ElevatedButton(
        "Play",
        icon=ft.icons.PLAY_ARROW_ROUNDED,
        bgcolor=GREEN, color=TEXT_INV,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
            padding=ft.padding.symmetric(horizontal=24, vertical=14),
        ),
        on_click=self._on_play,
    )

    optifine_installed = _check_optifine_installed(
        self.profile.version_id,
        self.profile.game_dir,
        self.app.settings.versions_dir,
    )
    self._optifine_btn = ft.OutlinedButton(
        "OptiFine ✓" if optifine_installed else "OptiFine",
        icon=ft.icons.SPEED_ROUNDED,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
            side=ft.BorderSide(1, GREEN if optifine_installed else BORDER),
            color=GREEN if optifine_installed else TEXT_SEC,
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
        ),
        tooltip="Instalar / gestionar OptiFine",
        on_click=lambda e: self._open_optifine_dialog(),
    )

    notes_row = ft.Container(
        visible=bool(notes),
        content=ft.Text(notes, color=TEXT_DIM, size=10, italic=True),
    )

    header = ft.Container(
        bgcolor=CARD_BG,
        padding=ft.padding.symmetric(horizontal=28, vertical=20),
        border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
        content=ft.Row([
            ft.Container(
                width=64, height=64, border_radius=14,
                bgcolor=CARD2_BG, alignment=ft.alignment.center,
                content=ft.Icon(ft.icons.WIDGETS_ROUNDED, size=32, color=TEXT_SEC),
            ),
            ft.Container(width=18),
            ft.Column([
                ft.Text(self.profile.name, color=TEXT_PRI, size=20, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Text(loader.capitalize(), color=GREEN, size=11, weight=ft.FontWeight.W_500),
                    ft.Text("  •  ", color=TEXT_DIM, size=11),
                    ft.Text(f"Minecraft {self.profile.version_id}", color=TEXT_SEC, size=11),
                    ft.Text("  •  ", color=TEXT_DIM, size=11),
                    ft.Text(last_played, color=TEXT_DIM, size=11),
                ], spacing=0),
                notes_row,
            ], spacing=4, expand=True),
            ft.Container(expand=True),
            self._optifine_btn,
            ft.Container(width=6),
            ft.IconButton(
                icon=ft.icons.SETTINGS_ROUNDED,
                icon_color=TEXT_DIM, icon_size=20,
                tooltip="Editar instancia",
                on_click=lambda e: self._open_edit(),
            ),
            ft.Container(width=4),
            self._play_btn,
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
    )

    # U2: contar ítems para los badges de las pestañas
    counts = self._count_items()

    tabs_data = [
        ("content", "Content", ft.icons.EXTENSION_ROUNDED,  sum(counts.values()) or None),
        ("files",   "Files",   ft.icons.FOLDER_ROUNDED,     None),
        ("worlds",  "Worlds",  ft.icons.PUBLIC_ROUNDED,     None),
        ("logs",    "Logs",    ft.icons.TERMINAL_ROUNDED,   None),
    ]
    self._tab_btns: dict[str, ft.Container] = {}
    tab_row = ft.Row(spacing=6, controls=[
        ft.IconButton(
            icon=ft.icons.ARROW_BACK_IOS_NEW_ROUNDED,
            icon_color=TEXT_DIM, icon_size=16,
            tooltip="Volver a Biblioteca",
            on_click=lambda e: self.app._show_view("library"),
        ),
        ft.Container(width=4),
    ])
    for tid, tlabel, ticon, tcount in tabs_data:
        btn = self._make_tab_btn(tid, tlabel, ticon, tcount)
        self._tab_btns[tid] = btn
        tab_row.controls.append(btn)

    tab_bar = ft.Container(
        bgcolor=CARD_BG,
        border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
        padding=ft.padding.symmetric(horizontal=20, vertical=10),
        content=tab_row,
    )

    # U3: contenedor con fade de opacidad entre pestañas
    self._tab_area = ft.Container(
        expand=True, bgcolor=BG,
        animate_opacity=ft.animation.Animation(130, ft.AnimationCurve.EASE_OUT),
    )

    self.root = ft.Column(
        spacing=0, expand=True,
        controls=[header, tab_bar, self._tab_area],
    )
