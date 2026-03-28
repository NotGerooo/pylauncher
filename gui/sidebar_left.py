"""
gui/sidebar_left.py — Sidebar izquierdo icon-only.
Iconos de navegación principal + instancias de perfil.
"""
import flet as ft

from gui.theme import (
    SIDEBAR_BG, CARD2_BG, BORDER,
    GREEN, TEXT_INV, TEXT_SEC, TEXT_DIM,
    NAV_ACTIVE, NAV_HOVER, AVATAR_PALETTE,
)

_SIDEBAR_W = 68


class SidebarLeft:
    def __init__(self, app):
        self.app = app
        self._nav_btns: dict[str, ft.Container] = {}
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self):
        top_items = [
            ("home",     ft.icons.HOME_ROUNDED,     "Inicio"),
            ("discover", ft.icons.EXPLORE_ROUNDED,  "Descubrir"),
            ("library",  ft.icons.LIBRARY_BOOKS_ROUNDED, "Biblioteca"),
        ]
        top_rows = []
        for vid, icon, tip in top_items:
            btn = self._make_icon_btn(vid, icon, tip)
            self._nav_btns[vid] = btn
            top_rows.append(btn)

        # Instancias (scrollable)
        self._instances_col = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO)
        self._add_instance_btn = ft.Container(
            width=40, height=40, border_radius=20,
            bgcolor=CARD2_BG,
            border=ft.border.all(1, BORDER),
            alignment=ft.alignment.center,
            tooltip="Nueva instancia",
            content=ft.Text("+", color=TEXT_SEC, size=18,
                            weight=ft.FontWeight.BOLD),
            on_click=lambda e: self.app._open_create_instance(),
            on_hover=lambda e: (
                setattr(e.control, "bgcolor",
                        NAV_HOVER if e.data == "true" else CARD2_BG)
                or e.control.update()),
        )

        bottom_items = [
            ("settings", ft.icons.SETTINGS_ROUNDED,  "Ajustes"),
            ("accounts", ft.icons.PERSON_ROUNDED,     "Cuenta"),
        ]
        bottom_rows = []
        for vid, icon, tip in bottom_items:
            btn = self._make_icon_btn(vid, icon, tip)
            self._nav_btns[vid] = btn
            bottom_rows.append(btn)

        self.root = ft.Container(
            width=_SIDEBAR_W,
            bgcolor=SIDEBAR_BG,
            content=ft.Column([
                ft.Container(height=8),
                *top_rows,
                ft.Container(height=4),
                ft.Divider(height=1, color=BORDER),
                ft.Container(height=4),
                ft.Container(
                    expand=True,
                    content=ft.Column([
                        self._instances_col,
                        ft.Container(height=6),
                        self._add_instance_btn,
                    ], spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                ),
                ft.Divider(height=1, color=BORDER),
                ft.Container(height=4),
                *bottom_rows,
                ft.Container(height=8),
            ], spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )

        self.refresh_instances()

    # ── Botón de icono ────────────────────────────────────────────────────────
    def _make_icon_btn(self, vid: str, icon, tooltip: str) -> ft.Container:
        btn = ft.Container(
            width=44, height=44,
            border_radius=10,
            bgcolor=SIDEBAR_BG,
            alignment=ft.alignment.center,
            tooltip=tooltip,
            content=ft.Icon(icon, size=22, color=TEXT_DIM),
            on_click=lambda e, v=vid: self.app._show_view(v),
            on_hover=lambda e, v=vid: self._on_hover(e, v),
        )
        btn._active = False
        btn._vid    = vid
        return btn

    def _on_hover(self, e, vid: str):
        btn = self._nav_btns.get(vid)
        if btn and not btn._active:
            btn.bgcolor = NAV_HOVER if e.data == "true" else SIDEBAR_BG
            icon = btn.content
            if isinstance(icon, ft.Icon):
                icon.color = TEXT_SEC if e.data == "true" else TEXT_DIM
            try: btn.update()
            except Exception: pass

    # ── Estado activo ─────────────────────────────────────────────────────────
    def set_active(self, vid: str):
        for v, btn in self._nav_btns.items():
            active = (v == vid)
            btn._active = active
            btn.bgcolor = NAV_ACTIVE if active else SIDEBAR_BG
            icon = btn.content
            if isinstance(icon, ft.Icon):
                icon.color = GREEN if active else TEXT_DIM
            try: btn.update()
            except Exception: pass

    # ── Instancias ────────────────────────────────────────────────────────────
    def refresh_instances(self):
        self._instances_col.controls.clear()
        profiles = self.app.profile_manager.get_all_profiles()
        for p in profiles:
            color   = AVATAR_PALETTE[abs(hash(p.name)) % len(AVATAR_PALETTE)]
            initial = (p.name[0]).upper() if p.name else "?"
            ic = ft.Container(
                width=40, height=40, border_radius=8,
                bgcolor=color,
                alignment=ft.alignment.center,
                tooltip=p.name,
                content=ft.Text(initial, color=TEXT_INV, size=14,
                                weight=ft.FontWeight.BOLD),
                on_click=lambda e, prof=p: self.app._show_instance(prof),
                on_hover=lambda e, c=color: (
                    setattr(e.control, "border",
                            ft.border.all(2, GREEN) if e.data == "true"
                            else ft.border.all(0, "transparent"))
                    or e.control.update()),
            )
            self._instances_col.controls.append(ic)
        try:
            self._instances_col.update()
            self._add_instance_btn.update()
        except Exception:
            pass