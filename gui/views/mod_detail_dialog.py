# -*- coding: utf-8 -*-
"""
mod_detail_dialog.py
Dialog de detalle de mod estilo Modrinth App — versión premium.

Mejoras respecto al original:
  • Descripción real (body del proyecto) con scroll y renderizado de Markdown básico
  • Galería real con imágenes del proyecto (grid responsivo)
  • version_type y downloads correctamente leídos desde la API
  • Header con banner de color, stats con iconos y animaciones
  • Versiones: canal, plataforma, fecha y descargas reales
  • Sidebar con chips animados y links funcionales
  • Animaciones de hover y selección en toda la UI
"""

import os
import threading
import hashlib
import urllib.request
from datetime import datetime, timezone

import flet as ft

from gui.theme import (
    CARD_BG, CARD2_BG, INPUT_BG, BORDER, BORDER_BRIGHT,
    GREEN, GREEN_DIM, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV,
ROW_SELECTED, ROW_HOVER_INCOMPATIBLE,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_IMG_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache", "images")
os.makedirs(_IMG_CACHE_DIR, exist_ok=True)


def _human(n: int) -> str:
    """Convierte un número grande en formato legible: 1.2M, 34.5K, etc."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _rel_date(iso: str) -> str:
    """Convierte una fecha ISO a 'hace X días/meses'."""
    if not iso:
        return ""
    try:
        dt   = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        diff = (datetime.now(timezone.utc) - dt).days
        if diff == 0:
            return "hoy"
        if diff == 1:
            return "ayer"
        if diff < 30:
            return f"hace {diff}d"
        if diff < 365:
            return f"hace {diff // 30}m"
        return f"hace {diff // 365}a"
    except Exception:
        return iso[:10]


def _icon_widget(url: str, title: str, size: int = 48) -> ft.Control:
    """Ícono del mod con fallback de letras si no hay imagen."""
    fallback = ft.Container(
        width=size, height=size, border_radius=size // 5,
        bgcolor=INPUT_BG,
        border=ft.border.all(1, BORDER),
        alignment=ft.alignment.center,
        content=ft.Text(
            (title[:2] if title else "??").upper(),
            color=TEXT_SEC, size=size // 3,
            weight=ft.FontWeight.BOLD,
        ),
    )
    if not url:
        return fallback
    return ft.Container(
        width=size, height=size, border_radius=size // 5,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        shadow=[ft.BoxShadow(
            spread_radius=0, blur_radius=12,
            color=ft.colors.with_opacity(0.25, GREEN),
            offset=ft.Offset(0, 4),
        )],
        content=ft.Image(
            src=url, width=size, height=size,
            fit=ft.ImageFit.COVER,
            error_content=fallback,
        ),
    )


def _cat_chip(label: str) -> ft.Container:
    return ft.Container(
        bgcolor=ft.colors.with_opacity(0.08, GREEN),
        border=ft.border.all(1, ft.colors.with_opacity(0.25, GREEN)),
        border_radius=5,
        padding=ft.padding.symmetric(horizontal=7, vertical=3),
        content=ft.Text(label.capitalize(), color=GREEN, size=9,
                        weight=ft.FontWeight.W_600),
    )


# ── Colores de canal ──────────────────────────────────────────────────────────
_CHANNEL_COLORS = {
    "release": "#27ae60",
    "beta":    "#e67e22",
    "alpha":   "#e74c3c",
}

_LOADER_ICONS = {
    "fabric":   ft.icons.TEXTURE_ROUNDED,
    "forge":    ft.icons.HARDWARE_ROUNDED,
    "neoforge": ft.icons.CONSTRUCTION_ROUNDED,
    "quilt":    ft.icons.GRID_4X4_ROUNDED,
}

_LOADER_COLORS = {
    "fabric":   "#dbb68a",
    "forge":    "#6c8ebf",
    "neoforge": "#e8a87c",
    "quilt":    "#b39ddb",
}


# ══════════════════════════════════════════════════════════════════════════════
#  ModDetailDialog
# ══════════════════════════════════════════════════════════════════════════════
class ModDetailDialog:
    """
    Dialog de detalle de mod al estilo Modrinth — diseño premium.

    Pestañas:
      • Versiones  — tabla con filtros de plataforma, versión MC y canal
      • Descripción — body completo del proyecto con scroll
      • Galería    — grid de imágenes del proyecto

    Sidebar:
      • Compatibilidad (chips de versiones MC)
      • Plataformas (loaders)
      • Entornos soportados
      • Links (Modrinth, issues, source)
    """

    def __init__(self, page, app, project, active_profile,
                 active_loader, target_dir=None, on_installed=None):
        self.page           = page
        self.app            = app
        self.project        = project
        self.active_profile = active_profile
        self.active_loader  = active_loader
        self.target_dir     = target_dir
        self.on_installed   = on_installed

        self._versions: list  = []
        self._selected_ver    = None
        self._active_tab: int = 0   # 0=Versions 1=Description 2=Gallery

        # Estado de filtros
        self._filter_platform: str | None = None
        self._filter_mcver:    str | None = None
        self._filter_channel:  str | None = None

        self._build()
        threading.Thread(target=self._fetch_versions,       daemon=True).start()
        threading.Thread(target=self._fetch_project_details, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    #  BUILD
    # ══════════════════════════════════════════════════════════════════════════
    def _build(self):
        cats      = getattr(self.project, "categories", []) or []
        follows   = getattr(self.project, "follows", 0)

        # ── HEADER ────────────────────────────────────────────────────────────
        #   Banda de color superior + icono + metadatos + botón instalar
        accent_bar = ft.Container(
            height=3,
            border_radius=ft.border_radius.only(top_left=12, top_right=12),
            gradient=ft.LinearGradient(
                begin=ft.alignment.center_left,
                end=ft.alignment.center_right,
                colors=[GREEN, ft.colors.with_opacity(0.3, GREEN)],
            ),
        )

        header_content = ft.Container(
            padding=ft.padding.only(left=24, right=24, top=20, bottom=16),
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left,
                end=ft.alignment.bottom_right,
                colors=[ft.colors.with_opacity(0.08, GREEN), "transparent"],
            ),
            content=ft.Row([
                _icon_widget(self.project.icon_url, self.project.title, size=72),
                ft.Container(width=20),
                ft.Column([
                    # Título
                    ft.Text(self.project.title,
                            color=TEXT_PRI, size=22,
                            weight=ft.FontWeight.BOLD),
                    ft.Container(height=3),
                    # Descripción corta
                    ft.Text(
                        (self.project.description[:160] + "…"
                         if len(self.project.description) > 160
                         else self.project.description),
                        color=TEXT_SEC, size=11, max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Container(height=10),
                    # Stats row
                    ft.Row([
                        # Descargas
                        ft.Container(
                            bgcolor=ft.colors.with_opacity(0.07, GREEN),
                            border=ft.border.all(1, ft.colors.with_opacity(0.2, GREEN)),
                            border_radius=6,
                            padding=ft.padding.symmetric(horizontal=9, vertical=4),
                            content=ft.Row([
                                ft.Icon(ft.icons.DOWNLOAD_ROUNDED,
                                        size=12, color=GREEN),
                                ft.Container(width=5),
                                ft.Text(_human(self.project.downloads),
                                        color=GREEN, size=11,
                                        weight=ft.FontWeight.W_600),
                            ], spacing=0, tight=True),
                        ),
                        ft.Container(width=8),
                        # Followers
                        ft.Container(
                            bgcolor=INPUT_BG,
                            border=ft.border.all(1, BORDER),
                            border_radius=6,
                            padding=ft.padding.symmetric(horizontal=9, vertical=4),
                            content=ft.Row([
                                ft.Icon(ft.icons.FAVORITE_BORDER_ROUNDED,
                                        size=12, color=TEXT_DIM),
                                ft.Container(width=5),
                                ft.Text(_human(follows) if follows else "—",
                                        color=TEXT_SEC, size=11,
                                        weight=ft.FontWeight.W_600),
                            ], spacing=0, tight=True),
                        ),
                        ft.Container(width=12),
                        # Categorías
                        *[_cat_chip(c) for c in cats[:3]],
                    ], spacing=0, tight=True, wrap=False),
                ], spacing=0, expand=True),
                ft.Container(width=16),
                # Botón instalar rápido
                self._make_install_btn(),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        header = ft.Column([accent_bar, header_content], spacing=0)

        # ── TABS ──────────────────────────────────────────────────────────────
        self._tab_labels = ["Versiones", "Descripción", "Galería"]
        self._tab_btns   = []
        tab_controls     = []

        for i, lbl in enumerate(self._tab_labels):
            txt = ft.Text(lbl, size=12, weight=ft.FontWeight.W_600,
                          color=TEXT_PRI if i == 0 else TEXT_SEC)
            bar = ft.Container(
                height=2, border_radius=2,
                bgcolor=GREEN if i == 0 else "transparent",
                animate=ft.animation.Animation(160, ft.AnimationCurve.EASE_OUT),
            )
            btn = ft.Container(
                padding=ft.padding.symmetric(horizontal=18, vertical=8),
                on_click=lambda e, idx=i: self._switch_tab(idx),
                animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
                content=ft.Column(
                    [txt, ft.Container(height=5), bar],
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                data={"txt": txt, "bar": bar},
            )
            btn.on_hover = lambda e, b=btn: (
                setattr(b, "bgcolor",
                        ft.colors.with_opacity(0.04, GREEN)
                        if e.data == "true" else "transparent")
                or b.update()
            )
            self._tab_btns.append(btn)
            tab_controls.append(btn)

        tabs_row = ft.Row(tab_controls, spacing=0)

        # ── FILTROS — dropdown con valor "__all__" para Todos ────────────────
        # Usar value="__all__" en lugar de hint_text para que on_change
        # siempre dispare correctamente al volver a "Todos".
        def _dd(prefix, width):
            return ft.Dropdown(
                prefix_text=f"{prefix}  ",
                prefix_style=ft.TextStyle(color=TEXT_SEC, size=11),
                value="__all__",
                width=width, height=36, color=TEXT_PRI,
                bgcolor=INPUT_BG,
                border_color=BORDER,
                focused_border_color=GREEN,
                border_radius=7,
                content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
                text_style=ft.TextStyle(size=11),
            )

        self._platform_dd = _dd("Plataforma", 185)
        self._mcver_dd    = _dd("MC Versión", 215)
        self._channel_dd  = _dd("Canal", 155)
        self._platform_dd.on_change = self._on_platform_change
        self._mcver_dd.on_change    = self._on_mcver_change
        self._channel_dd.on_change  = self._on_channel_change

        self._filter_row = ft.Container(
            visible=False,
            padding=ft.padding.only(top=12, bottom=6),
            content=ft.Row([
                ft.Container(
                    bgcolor=INPUT_BG, border=ft.border.all(1, BORDER),
                    border_radius=7,
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    content=ft.Icon(ft.icons.FILTER_LIST_ROUNDED,
                                    size=14, color=TEXT_DIM),
                ),
                ft.Container(width=10),
                self._platform_dd,
                ft.Container(width=8),
                self._mcver_dd,
                ft.Container(width=8),
                self._channel_dd,
            ], spacing=0, tight=True),
        )

        # ── TABLA DE VERSIONES ────────────────────────────────────────────────
        def _th(label, width=None, expand=False):
            return ft.Container(
                width=width, expand=expand,
                content=ft.Text(label, color=TEXT_DIM, size=9,
                                weight=ft.FontWeight.BOLD),
            )

        table_header = ft.Container(
            padding=ft.padding.symmetric(horizontal=16, vertical=9),
            bgcolor=ft.colors.with_opacity(0.03, GREEN),
            border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
            content=ft.Row([
                ft.Container(width=20),   # dot canal
                ft.Container(width=10),
                _th("NOMBRE",        expand=True),
                _th("MC VERSIÓN",    width=110),
                _th("PLATAFORMAS",   width=120),
                _th("PUBLICADO",     width=110),
                _th("DESCARGAS",     width=80),
                ft.Container(width=60),
            ], spacing=0),
        )

        self._spinner_row = ft.Row([
            ft.ProgressRing(width=16, height=16, color=GREEN, stroke_width=2),
            ft.Container(width=10),
            ft.Text("Cargando versiones…", color=TEXT_DIM, size=11),
        ], visible=True)

        self._status_lbl = ft.Text("", color=TEXT_DIM, size=10, visible=False)
        self._versions_col = ft.Column([], spacing=0)

        self._versions_lv = ft.ListView(
            height=400,
            padding=ft.padding.only(right=4),
            controls=[
                table_header,
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=20, vertical=14),
                    content=self._spinner_row,
                ),
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=20, vertical=4),
                    content=self._status_lbl,
                ),
                self._versions_col,
            ],
        )

        # ── PANEL DESCRIPCIÓN ─────────────────────────────────────────────────
        # Spinner inicial; se rellena cuando llegue _fetch_project_details
        self._desc_spinner = ft.Container(
            padding=ft.padding.all(24),
            alignment=ft.alignment.center,
            content=ft.Row([
                ft.ProgressRing(width=14, height=14, color=GREEN, stroke_width=2),
                ft.Container(width=10),
                ft.Text("Cargando descripción…", color=TEXT_DIM, size=11),
            ], tight=True),
        )
        self._desc_body = ft.Column(
            [self._desc_spinner],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
        )
        self._desc_panel = ft.Container(
            visible=False,
            height=400,
            padding=ft.padding.only(right=4),
            content=self._desc_body,
        )

        # ── PANEL GALERÍA ─────────────────────────────────────────────────────
        self._gallery_spinner = ft.Container(
            padding=ft.padding.all(24),
            alignment=ft.alignment.center,
            content=ft.Row([
                ft.ProgressRing(width=14, height=14, color=GREEN, stroke_width=2),
                ft.Container(width=10),
                ft.Text("Cargando galería…", color=TEXT_DIM, size=11),
            ], tight=True),
        )
        self._gallery_body = ft.Column(
            [self._gallery_spinner],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
        )
        self._gallery_panel = ft.Container(
            visible=False,
            height=400,
            padding=ft.padding.only(right=4),
            content=self._gallery_body,
        )

        # ── COLUMNA IZQUIERDA ─────────────────────────────────────────────────
        left_col = ft.Column([
            header,
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=2),
            tabs_row,
            ft.Divider(height=1, color=BORDER),
            self._filter_row,
            self._versions_lv,
            self._desc_panel,
            self._gallery_panel,
        ], spacing=0, expand=True)

        # ── SIDEBAR ───────────────────────────────────────────────────────────
        self._compat_versions_row = ft.Row([], wrap=True, spacing=6, run_spacing=6)
        self._compat_loaders_row  = ft.Row([], wrap=True, spacing=6, run_spacing=6)
        self._compat_env_row      = ft.Row([], wrap=True, spacing=6, run_spacing=6)

        def _sidebar_section(title: str, body: ft.Control) -> ft.Column:
            return ft.Column([
                ft.Row([
                    ft.Container(
                        width=3, height=12, border_radius=2,
                        bgcolor=GREEN,
                        shadow=[ft.BoxShadow(
                            spread_radius=0, blur_radius=6,
                            color=ft.colors.with_opacity(0.5, GREEN),
                            offset=ft.Offset(0, 0),
                        )],
                    ),
                    ft.Container(width=8),
                    ft.Text(title.upper(), color=TEXT_DIM, size=8,
                            weight=ft.FontWeight.BOLD),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=10),
                body,
                ft.Container(height=18),
            ], spacing=0)

        def _link_btn(icon, label: str, url: str) -> ft.Container:
            txt = ft.Text(label, color=TEXT_SEC, size=11)
            c = ft.Container(
                border_radius=7,
                padding=ft.padding.symmetric(horizontal=8, vertical=6),
                on_click=lambda e, u=url: self.page.launch_url(u),
                animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
                content=ft.Row([
                    ft.Container(
                        width=26, height=26, border_radius=6,
                        bgcolor=INPUT_BG,
                        border=ft.border.all(1, BORDER),
                        alignment=ft.alignment.center,
                        content=ft.Icon(icon, size=12, color=TEXT_DIM),
                    ),
                    ft.Container(width=9),
                    txt,
                    ft.Container(expand=True),
                    ft.Icon(ft.icons.OPEN_IN_NEW_ROUNDED,
                            size=10, color=TEXT_DIM),
                ], spacing=0, tight=False),
            )

            def _hov(e, cc=c, t=txt):
                if e.data == "true":
                    cc.bgcolor = ft.colors.with_opacity(0.06, GREEN)
                    t.color    = GREEN
                else:
                    cc.bgcolor = "transparent"
                    t.color    = TEXT_SEC
                try:
                    cc.update(); t.update()
                except Exception:
                    pass

            c.on_hover = _hov
            return c

        slug     = getattr(self.project, "slug", "")
        proj_url = f"https://modrinth.com/mod/{slug}"

        sidebar = ft.Container(
            width=210,
            padding=ft.padding.only(left=22),
            border=ft.border.only(left=ft.BorderSide(1, BORDER)),
            content=ft.Column([
                _sidebar_section("Compatibilidad", ft.Column([
                    ft.Text("Minecraft: Java Edition",
                            color=TEXT_DIM, size=9,
                            weight=ft.FontWeight.W_500),
                    ft.Container(height=8),
                    self._compat_versions_row,
                ], spacing=0)),
                _sidebar_section("Plataformas", self._compat_loaders_row),
                _sidebar_section("Entornos", self._compat_env_row),
                _sidebar_section("Links", ft.Column([
                    _link_btn(ft.icons.BUG_REPORT_ROUNDED,
                              "Reportar bugs", f"{proj_url}"),
                    _link_btn(ft.icons.CODE_ROUNDED,
                              "Ver código", proj_url),
                    _link_btn(ft.icons.OPEN_IN_BROWSER_ROUNDED,
                              "Ver en Modrinth", proj_url),
                ], spacing=2)),
            ], spacing=0, scroll=ft.ScrollMode.AUTO),
        )

        # ── BOTÓN INSTALAR SELECCIONADO ───────────────────────────────────────
        self._install_sel_btn = ft.ElevatedButton(
            "Instalar versión seleccionada",
            bgcolor=GREEN, color=TEXT_INV,
            disabled=True,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=22, vertical=13),
                elevation=0,
                overlay_color=ft.colors.with_opacity(0.15, "#ffffff"),
            ),
            icon=ft.icons.DOWNLOAD_ROUNDED,
            on_click=self._do_install,
        )

        # ── DIALOG ────────────────────────────────────────────────────────────
        self._dlg = ft.AlertDialog(
            bgcolor=CARD_BG,
            shape=ft.RoundedRectangleBorder(radius=14),
            title=ft.Container(),
            content_padding=ft.padding.all(0),
            content=ft.Container(
                width=1060,
                content=ft.Row([
                    ft.Container(content=left_col, expand=True),
                    sidebar,
                ], vertical_alignment=ft.CrossAxisAlignment.START, spacing=0),
            ),
            actions=[
                ft.TextButton(
                    "Cerrar",
                    style=ft.ButtonStyle(color=TEXT_SEC),
                    on_click=lambda e: self.page.close(self._dlg),
                ),
                self._install_sel_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        self.page.open(self._dlg)

    # ── Botón instalar rápido (header) ────────────────────────────────────────
    def _make_install_btn(self) -> ft.Container:
        already = False
        if self.target_dir:
            from utils.install_detector import build_installed_set, is_installed_in
            s = build_installed_set(self.target_dir)
            already = is_installed_in(
                getattr(self.project, "slug", ""),
                self.project.title, s,
            )

        if already:
            return ft.Container(
                bgcolor="transparent",
                border=ft.border.all(1.5, GREEN),
                border_radius=9,
                padding=ft.padding.symmetric(horizontal=22, vertical=11),
                content=ft.Row([
                    ft.Icon(ft.icons.CHECK_ROUNDED, size=16, color=GREEN),
                    ft.Container(width=8),
                    ft.Text("Instalado", color=GREEN, size=13,
                            weight=ft.FontWeight.W_700),
                ], spacing=0, tight=True),
            )

        btn = ft.Container(
            bgcolor=GREEN, border_radius=9,
            padding=ft.padding.symmetric(horizontal=22, vertical=11),
            animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
            shadow=[ft.BoxShadow(
                spread_radius=0, blur_radius=12,
                color=ft.colors.with_opacity(0.35, GREEN),
                offset=ft.Offset(0, 4),
            )],
            on_click=lambda e: self._quick_install_latest(),
            content=ft.Row([
                ft.Icon(ft.icons.DOWNLOAD_ROUNDED, size=16, color=TEXT_INV),
                ft.Container(width=8),
                ft.Text("Instalar", color=TEXT_INV, size=13,
                        weight=ft.FontWeight.W_700),
            ], spacing=0, tight=True),
        )
        btn.on_hover = lambda e, b=btn: (
            setattr(b, "bgcolor", GREEN_DIM if e.data == "true" else GREEN)
            or setattr(b, "shadow", [ft.BoxShadow(
                spread_radius=0,
                blur_radius=18 if e.data == "true" else 12,
                color=ft.colors.with_opacity(
                    0.5 if e.data == "true" else 0.35, GREEN),
                offset=ft.Offset(0, 4),
            )])
            or b.update()
        )
        return btn

    # ══════════════════════════════════════════════════════════════════════════
    #  TABS
    # ══════════════════════════════════════════════════════════════════════════
    def _switch_tab(self, idx: int):
        self._active_tab = idx
        for i, btn in enumerate(self._tab_btns):
            d = btn.data
            active = (i == idx)
            d["txt"].color  = TEXT_PRI if active else TEXT_SEC
            d["bar"].bgcolor = GREEN if active else "transparent"
            try:
                d["txt"].update()
                d["bar"].update()
            except Exception:
                pass

        self._versions_lv.visible   = (idx == 0)
        self._filter_row.visible    = (idx == 0) and bool(self._versions)
        self._desc_panel.visible    = (idx == 1)
        self._gallery_panel.visible = (idx == 2)
        try:
            self._versions_lv.update()
            self._filter_row.update()
            self._desc_panel.update()
            self._gallery_panel.update()
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    #  FETCH — versiones
    # ══════════════════════════════════════════════════════════════════════════
    def _fetch_versions(self):
        try:
            mc_ver   = (getattr(self.active_profile, "version_id", None)
                        if self.active_profile else None)
            versions = self.app.modrinth_service.get_project_versions(
                self.project.project_id,
                mc_version=None,
                loader=self.active_loader,
            )
            self.page.run_thread(lambda: self._on_versions_loaded(versions, mc_ver))
        except Exception as err:
            def _e():
                self._spinner_row.visible = False
                self._status_lbl.value    = f"Error al cargar versiones: {err}"
                self._status_lbl.visible  = True
                try:
                    self._spinner_row.update()
                    self._status_lbl.update()
                except Exception:
                    pass
            self.page.run_thread(_e)

    # ══════════════════════════════════════════════════════════════════════════
    #  FETCH — detalles del proyecto (body + gallery)
    # ══════════════════════════════════════════════════════════════════════════
    def _fetch_project_details(self):
        try:
            full = self.app.modrinth_service.get_project(self.project.project_id)
            self.page.run_thread(lambda: self._on_project_details_loaded(full))
        except Exception as err:
            def _e():
                self._desc_body.controls = [
                    ft.Container(
                        padding=ft.padding.all(24),
                        alignment=ft.alignment.center,
                        content=ft.Column([
                            ft.Icon(ft.icons.ERROR_OUTLINE_ROUNDED,
                                    size=32, color=TEXT_DIM),
                            ft.Container(height=8),
                            ft.Text(f"Error: {err}", color=TEXT_DIM, size=11),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    )
                ]
                self._gallery_body.controls = self._desc_body.controls.copy()
                try:
                    self._desc_body.update()
                    self._gallery_body.update()
                except Exception:
                    pass
            self.page.run_thread(_e)

    # ══════════════════════════════════════════════════════════════════════════
    #  CALLBACK — versiones cargadas
    # ══════════════════════════════════════════════════════════════════════════
    def _on_versions_loaded(self, versions, mc_ver: str | None):
        self._versions            = versions
        self._spinner_row.visible = False

        if not versions:
            self._status_lbl.value   = "No hay versiones disponibles."
            self._status_lbl.visible = True
            try:
                self._spinner_row.update()
                self._status_lbl.update()
            except Exception:
                pass
            return

        # Chips del sidebar
        all_mc_vers  = sorted({gv for v in versions for gv in v.game_versions},
                               reverse=True)
        all_loaders  = sorted({ld for v in versions for ld in v.loaders})
        all_channels = sorted({getattr(v, "version_type", "release") for v in versions})

        def _compat_chip(label: str, active: bool = False) -> ft.Container:
            return ft.Container(
                bgcolor=ft.colors.with_opacity(0.12, GREEN) if active else INPUT_BG,
                border=ft.border.all(1, GREEN if active else BORDER),
                border_radius=5,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                content=ft.Text(label,
                                color=TEXT_INV if active else TEXT_SEC,
                                size=10, weight=ft.FontWeight.W_500),
            )

        def _loader_chip(label: str) -> ft.Container:
            ico   = _LOADER_ICONS.get(label.lower(), ft.icons.EXTENSION_ROUNDED)
            color = _LOADER_COLORS.get(label.lower(), TEXT_SEC)
            return ft.Container(
                bgcolor=ft.colors.with_opacity(0.08, color),
                border=ft.border.all(1, ft.colors.with_opacity(0.3, color)),
                border_radius=5,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                content=ft.Row([
                    ft.Icon(ico, size=11, color=color),
                    ft.Container(width=5),
                    ft.Text(label.capitalize(), color=color,
                            size=10, weight=ft.FontWeight.W_500),
                ], spacing=0, tight=True),
            )

        self._compat_versions_row.controls = [
            _compat_chip(v, active=(v == mc_ver)) for v in all_mc_vers[:8]
        ]
        self._compat_loaders_row.controls = [
            _loader_chip(ld) for ld in all_loaders
        ]
        self._compat_env_row.controls = [
            _compat_chip("Cliente"),
            _compat_chip("Servidor"),
        ]

        try:
            self._compat_versions_row.update()
            self._compat_loaders_row.update()
            self._compat_env_row.update()
        except Exception:
            pass

        # Filtros
        self._platform_dd.options = (
            [ft.dropdown.Option("__all__", "Todos")] +
            [ft.dropdown.Option(ld, ld.capitalize()) for ld in all_loaders]
        )
        self._mcver_dd.options = (
            [ft.dropdown.Option("__all__", "Todos")] +
            [ft.dropdown.Option(v, v) for v in all_mc_vers]
        )
        self._channel_dd.options = (
            [ft.dropdown.Option("__all__", "Todos")] +
            [ft.dropdown.Option(c, c.capitalize()) for c in all_channels]
        )

        if mc_ver and mc_ver in all_mc_vers:
            self._mcver_dd.value  = mc_ver
            self._filter_mcver    = mc_ver
        else:
            self._mcver_dd.value  = "__all__"
        if self.active_loader and self.active_loader in all_loaders:
            self._platform_dd.value = self.active_loader
            self._filter_platform   = self.active_loader
        else:
            self._platform_dd.value = "__all__"
        self._channel_dd.value = "__all__"

        self._filter_row.visible = True

        try:
            self._platform_dd.update()
            self._mcver_dd.update()
            self._channel_dd.update()
            self._filter_row.update()
        except Exception:
            pass

        # Etiqueta de estado
        compat = sum(1 for v in versions
                     if not mc_ver or mc_ver in v.game_versions)
        self._status_lbl.value = (
            f"{len(versions)} versiones  ·  "
            f"{compat} compatibles con {mc_ver or 'cualquier versión'}"
        )
        self._status_lbl.visible = True

        try:
            self._spinner_row.update()
            self._status_lbl.update()
        except Exception:
            pass

        self._render_version_rows()

    # ══════════════════════════════════════════════════════════════════════════
    #  CALLBACK — detalles del proyecto cargados
    # ══════════════════════════════════════════════════════════════════════════
    def _on_project_details_loaded(self, full):
        # ── Descripción ───────────────────────────────────────────────────────
        body = getattr(full, "body", "") or self.project.description or ""
        desc_controls = self._render_markdown(body)
        self._desc_body.controls = desc_controls
        try:
            self._desc_body.update()
        except Exception:
            pass

        # ── Galería ───────────────────────────────────────────────────────────
        gallery = getattr(full, "gallery", []) or []
        if not gallery:
            self._gallery_body.controls = [
                ft.Container(
                    padding=ft.padding.all(40),
                    alignment=ft.alignment.center,
                    content=ft.Column([
                        ft.Container(
                            width=64, height=64, border_radius=32,
                            bgcolor=INPUT_BG,
                            border=ft.border.all(1, BORDER),
                            alignment=ft.alignment.center,
                            content=ft.Icon(ft.icons.PHOTO_LIBRARY_ROUNDED,
                                            size=28, color=TEXT_DIM),
                        ),
                        ft.Container(height=12),
                        ft.Text("Sin imágenes en la galería",
                                color=TEXT_DIM, size=12),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0),
                )
            ]
        else:
            # Grid de 2 columnas — pares de imágenes en filas
            valid = [e for e in gallery if e.get("url", "")]
            rows  = []

            def _img_tile(entry) -> ft.Container:
                url   = entry.get("url", "")
                title = entry.get("title", "") or entry.get("description", "")

                tile = ft.Container(
                    expand=True,
                    border_radius=9,
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    border=ft.border.all(1, BORDER),
                    animate=ft.animation.Animation(150, ft.AnimationCurve.EASE_OUT),
                    on_click=lambda e, u=url: self.page.launch_url(u),
                    shadow=[ft.BoxShadow(
                        spread_radius=0, blur_radius=8,
                        color=ft.colors.with_opacity(0.18, "#000000"),
                        offset=ft.Offset(0, 3),
                    )],
                    content=ft.Stack([
                        ft.Image(
                            src=url,
                            width=400, height=180,
                            fit=ft.ImageFit.COVER,
                            error_content=ft.Container(
                                height=180, bgcolor=INPUT_BG,
                                alignment=ft.alignment.center,
                                content=ft.Column([
                                    ft.Icon(ft.icons.BROKEN_IMAGE_ROUNDED,
                                            color=TEXT_DIM, size=24),
                                    ft.Container(height=4),
                                    ft.Text("No disponible",
                                            color=TEXT_DIM, size=9),
                                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=0),
                            ),
                        ),
                        # Overlay con título abajo si existe
                        *([ft.Container(
                            alignment=ft.alignment.bottom_left,
                            content=ft.Container(
                                padding=ft.padding.symmetric(
                                    horizontal=10, vertical=6),
                                gradient=ft.LinearGradient(
                                    begin=ft.alignment.bottom_center,
                                    end=ft.alignment.top_center,
                                    colors=[
                                        ft.colors.with_opacity(0.85, "#000000"),
                                        "transparent",
                                    ],
                                ),
                                content=ft.Text(
                                    title, color="#ffffff", size=10,
                                    weight=ft.FontWeight.W_500,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ),
                        )] if title else []),
                    ]),
                )

                def _hov(e, t=tile):
                    t.border = ft.border.all(
                        1,
                        ft.colors.with_opacity(0.7, GREEN)
                        if e.data == "true" else BORDER,
                    )
                    try:
                        t.update()
                    except Exception:
                        pass

                tile.on_hover = _hov
                return tile

            # Agrupa de 2 en 2
            for i in range(0, len(valid), 2):
                pair = valid[i:i + 2]
                row_controls = [_img_tile(pair[0])]
                if len(pair) == 2:
                    row_controls += [ft.Container(width=10), _img_tile(pair[1])]
                else:
                    # Imagen sola: ocupa la mitad izquierda, espacio vacío a la derecha
                    row_controls += [ft.Container(expand=True)]
                rows.append(
                    ft.Container(
                        padding=ft.padding.only(bottom=10),
                        content=ft.Row(row_controls, spacing=0,
                                       vertical_alignment=ft.CrossAxisAlignment.START),
                    )
                )

            # Contador en el tope
            count_lbl = ft.Container(
                padding=ft.padding.only(bottom=14),
                content=ft.Row([
                    ft.Icon(ft.icons.PHOTO_LIBRARY_ROUNDED,
                            size=13, color=TEXT_DIM),
                    ft.Container(width=6),
                    ft.Text(f"{len(valid)} imagen{'es' if len(valid) != 1 else ''}",
                            color=TEXT_DIM, size=10),
                ], tight=True),
            )

            self._gallery_body.controls = [count_lbl] + rows

        try:
            self._gallery_body.update()
        except Exception:
            pass

    # ── Renderizado de Markdown básico ────────────────────────────────────────
    def _render_markdown(self, text: str) -> list:
        if not text.strip():
            return [ft.Container(
                padding=ft.padding.all(24),
                alignment=ft.alignment.center,
                content=ft.Text("Sin descripción disponible.",
                                color=TEXT_DIM, size=11),
            )]
        return [
            ft.Container(
                padding=ft.padding.only(right=8, bottom=8),
                content=ft.Markdown(
                    text,
                    selectable=True,
                    extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                    on_tap_link=lambda e: self.page.launch_url(e.data),
                    code_theme="atom-one-dark",
                    code_style=ft.TextStyle(font_family="monospace", size=11),
                ),
            )
        ]

    # ══════════════════════════════════════════════════════════════════════════
    #  RENDER filas de versión
    # ══════════════════════════════════════════════════════════════════════════
    def _render_version_rows(self):
        mc_ver = (getattr(self.active_profile, "version_id", None)
                  if self.active_profile else None)

        def _passes(v) -> bool:
            if self._filter_platform:
                if self._filter_platform not in v.loaders:
                    return False
            if self._filter_mcver:
                if self._filter_mcver not in v.game_versions:
                    return False
            if self._filter_channel:
                if getattr(v, "version_type", "release") != self._filter_channel:
                    return False
            return True

        filtered = [v for v in self._versions if _passes(v)]
        self._versions_col.controls.clear()

        if not filtered:
            self._versions_col.controls.append(
                ft.Container(
                    padding=ft.padding.symmetric(vertical=30),
                    alignment=ft.alignment.center,
                    content=ft.Column([
                        ft.Icon(ft.icons.SEARCH_OFF_ROUNDED,
                                size=32, color=TEXT_DIM),
                        ft.Container(height=8),
                        ft.Text("Ninguna versión coincide con los filtros.",
                                color=TEXT_DIM, size=11),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0),
                )
            )
        else:
            for v in filtered:
                self._versions_col.controls.append(
                    self._make_version_row(v, mc_ver))

        try:
            self._versions_col.update()
        except Exception:
            pass

    def _make_version_row(self, v, mc_ver: str | None) -> ft.Container:
        compatible = not mc_ver or mc_ver in v.game_versions
        primary    = v.get_primary_file()
        filename   = primary.get("filename", "—") if primary else "—"
        ver_type   = getattr(v, "version_type", "release")
        chan_color  = _CHANNEL_COLORS.get(ver_type, TEXT_DIM)
        date_str   = _rel_date(getattr(v, "date_published", ""))
        downloads  = getattr(v, "downloads", 0)

        loader_pills = ft.Row(
            [self._mini_loader_chip(ld) for ld in (v.loaders or [])[:2]],
            spacing=4, tight=True,
        )

        # Indicador de compatibilidad
        compat_indicator = ft.Container(
            width=3, height=28, border_radius=2,
            bgcolor=ft.colors.with_opacity(0.6, GREEN)
                    if compatible else "transparent",
        ) if compatible else ft.Container(width=3)

        row = ft.Container(
            bgcolor="transparent",
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            animate=ft.animation.Animation(100, ft.AnimationCurve.EASE_OUT),
            data=v.version_id,
            on_click=(lambda e, ver=v: self._select_version(ver))
                     if compatible else None,
            content=ft.Row([
                compat_indicator,
                ft.Container(width=6),
                # Dot de canal
                ft.Container(
                    width=8, height=8, border_radius=4,
                    bgcolor=chan_color,
                    tooltip=ver_type.capitalize(),
                    shadow=[ft.BoxShadow(
                        spread_radius=0, blur_radius=5,
                        color=ft.colors.with_opacity(0.5, chan_color),
                        offset=ft.Offset(0, 0),
                    )],
                ),
                ft.Container(width=12),
                # Nombre + archivo
                ft.Column([
                    ft.Text(v.name,
                            color=TEXT_PRI if compatible else TEXT_DIM,
                            size=12, weight=ft.FontWeight.W_600),
                    ft.Text(filename, color=TEXT_DIM, size=9,
                            overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=1, expand=True),
                # MC Versión
                ft.Container(
                    width=110,
                    content=ft.Text(
                        ", ".join(v.game_versions[:2]),
                        color=TEXT_DIM, size=10,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ),
                # Plataformas
                ft.Container(width=120, content=loader_pills),
                # Publicado
                ft.Container(
                    width=110,
                    content=ft.Text(date_str or "—",
                                    color=TEXT_DIM, size=10),
                ),
                # Descargas
                ft.Container(
                    width=80,
                    content=ft.Row([
                        ft.Icon(ft.icons.DOWNLOAD_ROUNDED,
                                size=10, color=TEXT_DIM),
                        ft.Container(width=3),
                        ft.Text(_human(downloads), color=TEXT_DIM, size=10),
                    ], spacing=0, tight=True),
                ),
                # Acciones
                ft.Container(
                    width=60,
                    content=ft.Row([
                        ft.IconButton(
                            icon=ft.icons.DOWNLOAD_ROUNDED,
                            icon_color=TEXT_DIM,
                            icon_size=16,
                            tooltip="Descargar",
                            on_click=(lambda e, ver=v: self._select_and_install(ver))
                                     if compatible else None,
                        ),
                        ft.IconButton(
                            icon=ft.icons.OPEN_IN_NEW_ROUNDED,
                            icon_color=TEXT_DIM,
                            icon_size=14,
                            tooltip="Abrir en Modrinth",
                            on_click=lambda e, s=getattr(self.project, "slug", ""):
                                self.page.launch_url(
                                    f"https://modrinth.com/mod/{s}"),
                        ),
                    ], spacing=0, tight=True),
                ),
            ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        def _hover(e, r=row):
            if e.data == "true":
                r.bgcolor = ft.colors.with_opacity(0.06, GREEN) if compatible \
                            else ROW_HOVER_INCOMPATIBLE
            else:
                # Mantener fondo si está seleccionado
                is_sel = (self._selected_ver is not None and
                          self._selected_ver.version_id == r.data)
                r.bgcolor = ROW_SELECTED if is_sel else "transparent"
            try:
                r.update()
            except Exception:
                pass

        if compatible:
            row.on_hover = _hover

        return row

    def _mini_loader_chip(self, label: str) -> ft.Container:
        color = _LOADER_COLORS.get(label.lower(), TEXT_DIM)
        return ft.Container(
            bgcolor=ft.colors.with_opacity(0.1, color),
            border=ft.border.all(1, ft.colors.with_opacity(0.25, color)),
            border_radius=4,
            padding=ft.padding.symmetric(horizontal=6, vertical=2),
            content=ft.Text(label.capitalize(), color=color,
                            size=9, weight=ft.FontWeight.W_500),
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  FILTROS
    # ══════════════════════════════════════════════════════════════════════════
    def _on_platform_change(self, e):
        if not self._versions:
            return
        v = self._platform_dd.value
        self._filter_platform = None if (not v or v == "__all__") else v
        self._render_version_rows()

    def _on_mcver_change(self, e):
        if not self._versions:
            return
        v = self._mcver_dd.value
        self._filter_mcver = None if (not v or v == "__all__") else v
        self._render_version_rows()

    def _on_channel_change(self, e):
        if not self._versions:
            return
        v = self._channel_dd.value
        self._filter_channel = None if (not v or v == "__all__") else v
        self._render_version_rows()

    # ══════════════════════════════════════════════════════════════════════════
    #  SELECCIÓN + INSTALACIÓN
    # ══════════════════════════════════════════════════════════════════════════
    def _select_version(self, version):
        self._selected_ver             = version
        self._install_sel_btn.disabled = False
        for c in self._versions_col.controls:
            if hasattr(c, "data") and c.data:
                is_sel = c.data == version.version_id
                c.bgcolor = "#162820" if is_sel else "transparent"
                try:
                    c.update()
                except Exception:
                    pass
        try:
            self._install_sel_btn.update()
        except Exception:
            pass

    def _select_and_install(self, version):
        self._select_version(version)
        self._do_install(None)

    def _quick_install_latest(self):
        """Instala la primera versión compatible directamente."""
        if not self._versions:
            self.app.snack("Las versiones aún se están cargando.", error=True)
            return
        mc_ver = (getattr(self.active_profile, "version_id", None)
                  if self.active_profile else None)
        best = next(
            (v for v in self._versions
             if not mc_ver or mc_ver in v.game_versions),
            self._versions[0],
        )
        self._select_and_install(best)

    def _do_install(self, e):
        if not self._selected_ver or not self.active_profile:
            self.app.snack("Selecciona un perfil activo primero.", error=True)
            return

        self._install_sel_btn.disabled = True
        self._status_lbl.value         = f"⬇  Descargando {self._selected_ver.name}…"
        self._status_lbl.visible       = True
        try:
            self._install_sel_btn.update()
            self._status_lbl.update()
        except Exception:
            pass

        ver  = self._selected_ver
        prof = self.active_profile

        def do():
            try:
                target = self.target_dir or getattr(prof, "mods_dir", None)
                os.makedirs(target, exist_ok=True)
                self.app.modrinth_service.download_mod_version(ver, target)

                def done():
                    self._status_lbl.value         = "✓  Instalado correctamente"
                    self._install_sel_btn.disabled = False
                    try:
                        self._status_lbl.update()
                        self._install_sel_btn.update()
                    except Exception:
                        pass
                    self.app.snack(
                        f"{self.project.title} instalado en {prof.name}. ✓")
                    if self.on_installed:
                        self.on_installed()

                self.page.run_thread(done)

            except Exception as err:
                def _e(err=err):
                    self._status_lbl.value         = f"✗  Error: {err}"
                    self._install_sel_btn.disabled = False
                    try:
                        self._status_lbl.update()
                        self._install_sel_btn.update()
                    except Exception:
                        pass
                self.page.run_thread(_e)

        threading.Thread(target=do, daemon=True).start()