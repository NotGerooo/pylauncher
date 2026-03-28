"""
gui/views/discover_view.py
Diseño completo inspirado en Modrinth:
 - Tabs: Mods / Resource Packs / Shaders / Modpacks
 - Búsqueda en vivo con debounce (400 ms)
 - Filtros: Versión MC, Loader, Ordenar por
 - Scroll infinito (lazy loading) con ft.ListView
 - Spinner / skeleton mientras carga
 - Botón "Instalar" / "✓ Instalado" por tarjeta
 - Popup de detalle con lista de versiones
"""

import threading
import os
import json
import re
import time
import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV, ACCENT_RED,
)
from utils.logger import get_logger

log = get_logger()

# ── Constantes ────────────────────────────────────────────────────────────────
LOADERS        = ["fabric", "forge", "neoforge", "quilt"]
SORT_OPTIONS   = ["relevance", "downloads", "follows", "newest", "updated"]
SORT_LABELS    = {
    "relevance": "Relevancia",
    "downloads": "Más descargados",
    "follows":   "Más seguidos",
    "newest":    "Más recientes",
    "updated":   "Última actualización",
}
PAGE_SIZE      = 20
DEBOUNCE_MS    = 400          # ms de espera tras escribir antes de buscar

# project_type por cada tab
TAB_PROJECT_TYPES = ["mod", "resourcepack", "shader", "modpack"]
TAB_LABELS        = ["Mods", "Resource Packs", "Shaders", "Modpacks"]

_PALETTE = [
    "#2d6a4f", "#1e3a5f", "#5c2a2a", "#3a3a1e",
    "#2a1e5c", "#1e5c4a", "#4a3a1e", "#5c3a4a",
]


# ── Helper: widget de icono ────────────────────────────────────────────────────
def _icon(url: str, title: str, size: int = 52) -> ft.Control:
    color    = _PALETTE[abs(hash(title)) % len(_PALETTE)]
    initial  = (title[0] if title else "?").upper()
    fallback = ft.Container(
        width=size, height=size, border_radius=10,
        bgcolor=color, alignment=ft.alignment.center,
        content=ft.Text(initial, color="#ffffff",
                         size=int(size * 0.40), weight=ft.FontWeight.BOLD),
    )
    if not url:
        return fallback
    return ft.Image(
        src=url, width=size, height=size,
        border_radius=10, fit=ft.ImageFit.COVER,
        error_content=fallback,
    )


# ── Chip de categoría ─────────────────────────────────────────────────────────
def _chip(label: str) -> ft.Container:
    return ft.Container(
        bgcolor="#1f2937", border_radius=4,
        padding=ft.padding.symmetric(horizontal=8, vertical=3),
        content=ft.Text(label, color=TEXT_DIM, size=8),
    )


# ── Skeleton de carga ─────────────────────────────────────────────────────────
def _skeleton_card() -> ft.Container:
    """Tarjeta gris animada para mostrar mientras cargan los datos."""
    def _bar(w, h=10, opacity=0.18):
        return ft.Container(
            width=w, height=h, border_radius=4,
            bgcolor="#ffffff", opacity=opacity,
        )
    return ft.Container(
        bgcolor=CARD_BG, border_radius=12,
        padding=ft.padding.symmetric(horizontal=16, vertical=14),
        content=ft.Row([
            ft.Container(width=52, height=52, border_radius=10,
                          bgcolor="#ffffff", opacity=0.12),
            ft.Container(width=16),
            ft.Column([
                _bar(200, 12, 0.22),
                ft.Container(height=4),
                _bar(120, 9),
                ft.Container(height=4),
                _bar(320, 9),
                ft.Container(height=6),
                ft.Row([_bar(60, 8), ft.Container(width=6), _bar(70, 8)]),
            ], spacing=0, expand=True),
        ], vertical_alignment=ft.CrossAxisAlignment.START),
    )


# ── Vista principal ───────────────────────────────────────────────────────────
class DiscoverView:
    def __init__(self, page: ft.Page, app):
        self.page       = page
        self.app        = app

        self._results   : list  = []       # acumulado de la página actual
        self._offset    : int   = 0        # offset Modrinth
        self._loading   : bool  = False
        self._more_avail: bool  = False    # hay más páginas
        self._tab_index : int   = 0        # tab seleccionado
        self._debounce_timer = None        # threading.Timer para debounce

        self._installed_set: set = set()   # IDs/slugs ya instalados

        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self):
        # ── Tabs de tipo de contenido ──────────────────────────────────────
        self._tab_buttons = []
        tab_row = ft.Row(spacing=4)
        for i, label in enumerate(TAB_LABELS):
            btn = ft.TextButton(
                label,
                style=ft.ButtonStyle(
                    color={ft.ControlState.DEFAULT: TEXT_DIM,
                           ft.ControlState.HOVERED: TEXT_PRI},
                    padding=ft.padding.symmetric(horizontal=14, vertical=8),
                    shape=ft.RoundedRectangleBorder(radius=8),
                ),
                on_click=lambda e, idx=i: self._switch_tab(idx),
                data=i,
            )
            self._tab_buttons.append(btn)
            tab_row.controls.append(btn)

        # ── Campo de búsqueda ──────────────────────────────────────────────
        self._search_field = ft.TextField(
            hint_text="Busca mods, shaders, packs…",
            hint_style=ft.TextStyle(color=TEXT_DIM),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, expand=True,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            prefix_icon=ft.icons.SEARCH,
            on_change=self._on_search_change,
        )

        # ── Dropdown: perfil ───────────────────────────────────────────────
        self._profile_dd = ft.Dropdown(
            label="Perfil", width=180,
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, options=[],
            label_style=ft.TextStyle(color=TEXT_DIM, size=9),
            on_change=self._on_filter_change,
        )

        # ── Dropdown: loader ───────────────────────────────────────────────
        self._loader_dd = ft.Dropdown(
            label="Loader", width=148,
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8,
            options=[ft.dropdown.Option("(todos)")] +
                    [ft.dropdown.Option(l) for l in LOADERS],
            value="(todos)",
            label_style=ft.TextStyle(color=TEXT_DIM, size=9),
            on_change=self._on_filter_change,
        )

        # ── Dropdown: ordenar ──────────────────────────────────────────────
        self._sort_dd = ft.Dropdown(
            label="Ordenar", width=165,
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8,
            options=[ft.dropdown.Option(key=k, text=v)
                     for k, v in SORT_LABELS.items()],
            value="relevance",
            label_style=ft.TextStyle(color=TEXT_DIM, size=9),
            on_change=self._on_filter_change,
        )

        filter_bar = ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.symmetric(horizontal=20, vertical=14),
            content=ft.Column([
                ft.Row([self._search_field], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=10),
                ft.Row(
                    [self._profile_dd, self._loader_dd, self._sort_dd],
                    spacing=10,
                    wrap=True,
                ),
            ], spacing=0),
        )

        # ── Spinner central ────────────────────────────────────────────────
        self._spinner = ft.Container(
            visible=False,
            alignment=ft.alignment.center,
            padding=ft.padding.only(top=32),
            content=ft.Column([
                ft.ProgressRing(width=36, height=36, color=GREEN, stroke_width=3),
                ft.Container(height=10),
                ft.Text("Cargando…", color=TEXT_DIM, size=10),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )

        # ── Estado vacío / error ───────────────────────────────────────────
        self._empty_lbl = ft.Container(
            visible=False,
            alignment=ft.alignment.center,
            padding=ft.padding.only(top=60),
            content=ft.Column([
                ft.Icon(ft.icons.SEARCH_OFF_ROUNDED, size=48, color=TEXT_DIM),
                ft.Container(height=8),
                ft.Text("Sin resultados", color=TEXT_SEC, size=14,
                         weight=ft.FontWeight.BOLD),
                ft.Text("Prueba con otro término o cambia los filtros.",
                         color=TEXT_DIM, size=10),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )

        # ── Contador de resultados ─────────────────────────────────────────
        self._count_lbl = ft.Text("", color=TEXT_DIM, size=10)

        # ── Lista principal (ListView para scroll nativo) ──────────────────
        self._list_view = ft.ListView(
            expand=True, spacing=8,
            padding=ft.padding.only(bottom=16),
        )

        # ── Botón "cargar más" al final de la lista ────────────────────────
        self._load_more_btn = ft.Container(
            visible=False, alignment=ft.alignment.center,
            padding=ft.padding.only(top=12, bottom=16),
            content=ft.OutlinedButton(
                "Cargar más resultados",
                style=ft.ButtonStyle(
                    color=TEXT_SEC,
                    side=ft.BorderSide(1, BORDER),
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.padding.symmetric(horizontal=24, vertical=12),
                ),
                icon=ft.icons.EXPAND_MORE,
                on_click=self._on_load_more,
            ),
        )

        self.root = ft.Container(
            expand=True, bgcolor=BG,
            padding=ft.padding.only(left=32, right=32, top=28, bottom=0),
            content=ft.Column([
                # Encabezado
                ft.Text("Descubrir", color=TEXT_PRI, size=26,
                        weight=ft.FontWeight.BOLD),
                ft.Text("Explora mods, shaders y más desde Modrinth",
                        color=TEXT_SEC, size=11),
                ft.Container(height=16),
                # Tabs
                ft.Container(
                    bgcolor=CARD_BG, border_radius=10,
                    padding=ft.padding.symmetric(horizontal=8, vertical=6),
                    content=tab_row,
                ),
                ft.Container(height=12),
                filter_bar,
                ft.Container(height=12),
                # Contador
                ft.Row([self._count_lbl]),
                ft.Container(height=6),
                # Spinner + lista + botón "más"
                ft.Stack([
                    ft.Column([
                        self._list_view,
                        self._load_more_btn,
                    ], expand=True, scroll=ft.ScrollMode.AUTO),
                    self._spinner,
                    self._empty_lbl,
                ], expand=True),
            ], spacing=0, expand=True),
        )

        # Marcar tab inicial
        self._highlight_tab(0)

    # ── Ciclo de vida ─────────────────────────────────────────────────────────
    def on_show(self):
        self._refresh_profiles()
        self._trigger_search(reset=True)

    def _refresh_profiles(self):
        profiles = self.app.profile_manager.get_all_profiles()
        self._profile_dd.options = [ft.dropdown.Option(p.name) for p in profiles]
        if profiles:
            last  = self.app.settings.last_profile
            names = [p.name for p in profiles]
            self._profile_dd.value = last if last in names else names[0]
        try: self._profile_dd.update()
        except Exception: pass

    # ── Tabs ──────────────────────────────────────────────────────────────────
    def _switch_tab(self, idx: int):
        self._tab_index = idx
        self._highlight_tab(idx)
        self._trigger_search(reset=True)

    def _highlight_tab(self, active: int):
        for i, btn in enumerate(self._tab_buttons):
            is_active = (i == active)
            btn.style.bgcolor = {ft.ControlState.DEFAULT: GREEN if is_active else "transparent"}
            btn.style.color   = {
                ft.ControlState.DEFAULT: TEXT_INV if is_active else TEXT_DIM,
                ft.ControlState.HOVERED: TEXT_PRI,
            }
            try: btn.update()
            except Exception: pass

    # ── Debounce & disparar búsqueda ──────────────────────────────────────────
    def _on_search_change(self, e):
        if self._debounce_timer:
            self._debounce_timer.cancel()
        self._debounce_timer = threading.Timer(
            DEBOUNCE_MS / 1000.0,
            lambda: self._trigger_search(reset=True),
        )
        self._debounce_timer.start()

    def _on_filter_change(self, e):
        self._trigger_search(reset=True)

    def _on_load_more(self, e):
        self._trigger_search(reset=False)

    def _trigger_search(self, reset: bool):
        if self._loading:
            return
        if reset:
            self._offset  = 0
            self._results = []
        threading.Thread(target=self._fetch, daemon=True).start()

    # ── Fetch en hilo secundario ──────────────────────────────────────────────
    def _fetch(self):
        self._loading = True
        self.page.run_thread(self._show_spinner)

        query   = (self._search_field.value or "").strip()
        profile = self._active_profile()
        mc_ver  = profile.version_id if profile else None
        project_type = TAB_PROJECT_TYPES[self._tab_index]
        # Loaders solo aplican a mods; shaders/resourcepacks/modpacks ignoran el loader
        loader  = self._active_loader() if project_type in ("mod", "modpack") else None
        sort_by = self._sort_dd.value or "relevance"

        # Actualizar installed_set para el perfil activo
        self._installed_set = self._get_installed_set(profile)

        try:
            results = self.app.modrinth_service.search_mods(
                query      = query if query else "",
                mc_version = mc_ver,
                loader     = loader,
                limit      = PAGE_SIZE,
                offset     = self._offset,
                sort_by    = sort_by,
                project_type = project_type,
            )
            self._offset  += len(results)
            self._results += results
            more = len(results) >= PAGE_SIZE

            def _render():
                self._hide_spinner()
                if not self._results:
                    self._show_empty()
                else:
                    self._render_results(results, more)
            self.page.run_thread(_render)

        except Exception as err:
            log.warning(f"DiscoverView fetch error: {err}")
            def _err():
                self._hide_spinner()
                self._count_lbl.value = f"Error de red: {err}"
                try: self._count_lbl.update()
                except Exception: pass
            self.page.run_thread(_err)

        finally:
            self._loading = False

    # ── Render en hilo principal ──────────────────────────────────────────────
    def _render_results(self, new_results, more: bool):
        # Si es la primera página (offset == len(new_results)) limpiar lista
        if self._offset == len(new_results):
            self._list_view.controls.clear()

        for proj in new_results:
            self._list_view.controls.append(
                self._make_card(proj, self._is_installed(proj))
            )

        total = len(self._results)
        self._count_lbl.value = (
            f"{total} resultado{'s' if total != 1 else ''}"
            + (" · Cargando más…" if more else "")
        )
        self._load_more_btn.visible = more
        self._empty_lbl.visible     = False

        try:
            self._list_view.update()
            self._count_lbl.update()
            self._load_more_btn.update()
            self._empty_lbl.update()
        except Exception: pass

    # ── Helpers de estado UI ──────────────────────────────────────────────────
    def _show_spinner(self):
        # Mostrar skeletons mientras carga la primera página
        if self._offset == 0:
            self._list_view.controls.clear()
            for _ in range(6):
                self._list_view.controls.append(_skeleton_card())
            self._empty_lbl.visible = False
            try:
                self._list_view.update()
                self._empty_lbl.update()
            except Exception: pass
        self._spinner.visible = False          # spinner grande deshabilitado
        try: self._spinner.update()
        except Exception: pass

    def _hide_spinner(self):
        self._spinner.visible = False
        try: self._spinner.update()
        except Exception: pass

    def _show_empty(self):
        self._list_view.controls.clear()
        self._load_more_btn.visible = False
        self._empty_lbl.visible     = True
        self._count_lbl.value       = "0 resultados"
        try:
            self._list_view.update()
            self._load_more_btn.update()
            self._empty_lbl.update()
            self._count_lbl.update()
        except Exception: pass

    # ── Helpers de datos ─────────────────────────────────────────────────────
    def _active_profile(self):
        name = self._profile_dd.value
        return self.app.profile_manager.get_profile_by_name(name) if name else None

    def _active_loader(self) -> str | None:
        val = self._loader_dd.value
        if val and val != "(todos)":
            return val
        profile = self._active_profile()
        if profile:
            meta_path = os.path.join(profile.game_dir, "loader_meta.json")
            if os.path.isfile(meta_path):
                try:
                    with open(meta_path, "r") as f:
                        meta = json.load(f)
                    entries = meta if isinstance(meta, list) else [meta]
                    if entries:
                        return entries[0].get("loader_type")
                except Exception:
                    pass
        return None

    def _get_installed_set(self, profile) -> set:
        if not profile or not os.path.isdir(profile.mods_dir):
            return set()
        result = set()
        for fn in os.listdir(profile.mods_dir):
            key = re.sub(r"[-_. ]", "", fn.lower()
                         .replace(".jar", "").replace(".disabled", ""))
            result.add(key)
        return result

    def _is_installed(self, proj) -> bool:
        slug_key  = re.sub(r"[-_. ]", "", proj.slug.lower())
        title_key = re.sub(r"[-_. ]", "", proj.title.lower())
        return slug_key in self._installed_set or title_key in self._installed_set

    def _target_dir(self, profile) -> str:
        """Devuelve el directorio de destino según el tipo de contenido del tab activo."""
        project_type = TAB_PROJECT_TYPES[self._tab_index]
        if project_type == "resourcepack":
            return profile.resourcepacks_dir
        elif project_type == "shader":
            return profile.shaderpacks_dir
        else:  # "mod" y "modpack"
            return profile.mods_dir

    # ── Tarjeta de mod ────────────────────────────────────────────────────────
    def _make_card(self, proj, is_installed: bool) -> ft.Container:
        author = getattr(proj, "author", "")

        # Botón de instalación / estado instalado
        if is_installed:
            action_btn = ft.Container(
                bgcolor="#1a3d2a", border_radius=6,
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                content=ft.Row([
                    ft.Icon(ft.icons.CHECK_CIRCLE_ROUNDED, size=13, color=GREEN),
                    ft.Container(width=5),
                    ft.Text("Instalado", color=GREEN, size=9,
                             weight=ft.FontWeight.BOLD),
                ], spacing=0, tight=True),
            )
        else:
            action_btn = ft.Container(
                bgcolor=GREEN, border_radius=6,
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                on_click=lambda e, p=proj: self._quick_install(p),
                on_hover=lambda e: (
                    setattr(e.control, "bgcolor",
                            "#17c45e" if e.data == "true" else GREEN)
                    or e.control.update()
                ),
                content=ft.Row([
                    ft.Icon(ft.icons.DOWNLOAD_FOR_OFFLINE, size=13,
                             color=TEXT_INV),
                    ft.Container(width=5),
                    ft.Text("Instalar", color=TEXT_INV, size=9,
                             weight=ft.FontWeight.BOLD),
                ], spacing=0, tight=True),
            )

        # Fila de meta: autor · descargas
        meta_controls = []
        if author:
            meta_controls += [
                ft.Text(f"por {author}", color=GREEN, size=9),
                ft.Text("  ·  ", color=TEXT_DIM, size=9),
            ]
        meta_controls.append(
            ft.Text(f"⬇ {proj.downloads:,}", color=TEXT_DIM, size=9)
        )

        # Chips
        chips = ft.Row(
            [_chip(c) for c in proj.categories[:4]],
            spacing=5, wrap=True,
        ) if proj.categories else ft.Container(height=0)

        card = ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.symmetric(horizontal=16, vertical=14),
            on_click=lambda e, p=proj: self._open_detail(p),
            on_hover=lambda e: (
                setattr(e.control, "bgcolor",
                        "#1e2029" if e.data == "true" else CARD_BG)
                or e.control.update()
            ),
            content=ft.Row([
                _icon(proj.icon_url, proj.title, size=54),
                ft.Container(width=16),
                ft.Column([
                    ft.Row([
                        ft.Text(proj.title, color=TEXT_PRI, size=12,
                                weight=ft.FontWeight.BOLD, expand=True,
                                overflow=ft.TextOverflow.ELLIPSIS),
                        action_btn,
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row(meta_controls, spacing=0),
                    ft.Text(
                        proj.description[:120] + "…"
                        if len(proj.description) > 120 else proj.description,
                        color=TEXT_SEC, size=9,
                        overflow=ft.TextOverflow.ELLIPSIS, max_lines=2,
                    ),
                    ft.Container(height=5),
                    chips,
                ], spacing=4, expand=True),
            ], vertical_alignment=ft.CrossAxisAlignment.START),
        )
        return card

    # ── Instalación rápida desde la tarjeta ───────────────────────────────────
    def _quick_install(self, project):
        profile = self._active_profile()
        if not profile:
            self.app.snack("Selecciona un perfil primero.", error=True)
            return
        loader = self._active_loader()

        def do_install():
            try:
                version = self.app.modrinth_service.get_latest_version(
                    project.project_id,
                    mc_version=profile.version_id,
                    loader=loader,
                )
                if not version:
                    self.page.run_thread(lambda: self.app.snack(
                        "Sin versión compatible con este perfil.", error=True))
                    return
                self.app.modrinth_service.download_mod_version(
                    version, profile.mods_dir)
                # Actualizar set de instalados y re-renderizar
                self._installed_set = self._get_installed_set(profile)
                self.page.run_thread(lambda: self.app.snack(
                    f"{project.title} instalado en {profile.name}. ✓"))
                # Refrescar la tarjeta en la lista
                self.page.run_thread(self._refresh_installed_badges)
            except Exception as err:
                self.page.run_thread(
                    lambda: self.app.snack(f"Error: {err}", error=True))

        threading.Thread(target=do_install, daemon=True).start()

    def _refresh_installed_badges(self):
        """Reconstruye todas las tarjetas para actualizar badges Instalado."""
        controls = []
        for proj in self._results:
            controls.append(self._make_card(proj, self._is_installed(proj)))
        self._list_view.controls.clear()
        self._list_view.controls.extend(controls)
        try: self._list_view.update()
        except Exception: pass

    # ── Abrir detalle ─────────────────────────────────────────────────────────
    def _open_detail(self, project):
        ModDetailDialog(
            self.page, self.app, project,
            active_profile=self._active_profile(),
            active_loader=self._active_loader(),
            on_installed=lambda: self._on_mod_installed(project),
        )

    def _on_mod_installed(self, project):
        profile = self._active_profile()
        self._installed_set = self._get_installed_set(profile)
        self._refresh_installed_badges()


# ── Diálogo de detalle ─────────────────────────────────────────────────────────
class ModDetailDialog:
    """
    Popup completo del mod:
    - Tabs: Versiones / Descripción
    - Versiones compatibles (verde) vs incompatibles (gris)
    - Botón Instalar activo solo para versiones compatibles
    """

    def __init__(self, page, app, project, active_profile,
                 active_loader, on_installed=None):
        self.page           = page
        self.app            = app
        self.project        = project
        self.active_profile = active_profile
        self.active_loader  = active_loader
        self.on_installed   = on_installed
        self._versions      = []
        self._selected_ver  = None
        self._build()
        threading.Thread(target=self._fetch_versions, daemon=True).start()

    def _build(self):
        author    = getattr(self.project, "author", "")
        prof_name = self.active_profile.name if self.active_profile else "—"

        # Header del popup
        header = ft.Row([
            _icon(self.project.icon_url, self.project.title, size=60),
            ft.Container(width=18),
            ft.Column([
                ft.Text(self.project.title, color=TEXT_PRI, size=16,
                        weight=ft.FontWeight.BOLD),
                ft.Text(f"por {author}" if author else "",
                         color=GREEN, size=10),
                ft.Text(
                    self.project.description[:160] + "…"
                    if len(self.project.description) > 160
                    else self.project.description,
                    color=TEXT_SEC, size=10, max_lines=3,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Container(height=4),
                ft.Row([
                    ft.Container(
                        bgcolor=INPUT_BG, border_radius=6,
                        padding=ft.padding.symmetric(horizontal=10, vertical=4),
                        content=ft.Text(f"⬇ {self.project.downloads:,}",
                                         color=TEXT_SEC, size=9),
                    ),
                    ft.Container(width=8),
                    ft.Container(
                        bgcolor=INPUT_BG, border_radius=6,
                        padding=ft.padding.symmetric(horizontal=10, vertical=4),
                        content=ft.Text(f"Perfil: {prof_name}",
                                         color=TEXT_SEC, size=9),
                    ),
                ]),
            ], spacing=3, expand=True),
        ], vertical_alignment=ft.CrossAxisAlignment.START)

        self._status_lbl = ft.Text(
            "Cargando versiones…", color=TEXT_DIM, size=9)
        self._spinner_row = ft.Row(
            [ft.ProgressRing(width=18, height=18, color=GREEN, stroke_width=2),
             ft.Container(width=8),
             self._status_lbl],
            visible=True,
        )

        self._versions_lv = ft.ListView(
            spacing=6, height=280, padding=ft.padding.only(right=6))

        self._install_btn = ft.ElevatedButton(
            "⬇  Instalar versión seleccionada",
            bgcolor=GREEN, color=TEXT_INV, disabled=True,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=20, vertical=12),
            ),
            icon=ft.icons.DOWNLOAD_FOR_OFFLINE,
            on_click=self._do_install,
        )

        self._dlg = ft.AlertDialog(
            bgcolor=CARD_BG,
            title=ft.Container(),
            content=ft.Container(
                width=720,
                content=ft.Column([
                    header,
                    ft.Divider(height=1, color=BORDER),
                    self._spinner_row,
                    ft.Container(height=4),
                    self._versions_lv,
                ], spacing=10),
            ),
            actions=[
                ft.TextButton(
                    "Cerrar", style=ft.ButtonStyle(color=TEXT_SEC),
                    on_click=lambda e: self.page.close(self._dlg),
                ),
                self._install_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        self.page.open(self._dlg)

    # ── Fetch versiones ───────────────────────────────────────────────────────
    def _fetch_versions(self):
        try:
            mc_ver   = (self.active_profile.version_id
                        if self.active_profile else None)
            versions = self.app.modrinth_service.get_project_versions(
                self.project.project_id,
                mc_version=None,          # traemos todas, filtramos visualmente
                loader=self.active_loader,
            )
            self.page.run_thread(lambda: self._render_versions(versions, mc_ver))
        except Exception as err:
            def _e():
                self._spinner_row.visible = False
                self._status_lbl.value = f"Error: {err}"
                try:
                    self._spinner_row.update()
                    self._status_lbl.update()
                except Exception: pass
            self.page.run_thread(_e)

    def _render_versions(self, versions, mc_ver):
        self._versions      = versions
        self._spinner_row.visible = False

        if not versions:
            self._status_lbl.value   = "Sin versiones disponibles."
            self._status_lbl.visible = True
            try:
                self._spinner_row.update()
                self._status_lbl.update()
                self._versions_lv.update()
            except Exception: pass
            return

        self._status_lbl.visible = False
        count_compat = sum(
            1 for v in versions if (not mc_ver or mc_ver in v.game_versions))

        self._versions_lv.controls.clear()

        # Encabezado de columnas
        self._versions_lv.controls.append(
            ft.Container(
                padding=ft.padding.symmetric(horizontal=14, vertical=6),
                content=ft.Row([
                    ft.Container(width=18),
                    ft.Text("Versión del mod", color=TEXT_DIM, size=8,
                             weight=ft.FontWeight.BOLD, expand=True),
                    ft.Text("MC compatible", color=TEXT_DIM, size=8, width=120),
                    ft.Text("Loaders",       color=TEXT_DIM, size=8, width=100),
                    ft.Text("Archivo",        color=TEXT_DIM, size=8, width=160),
                ]),
            )
        )
        self._versions_lv.controls.append(
            ft.Divider(height=1, color=BORDER))

        for v in versions:
            compatible = not mc_ver or mc_ver in v.game_versions
            primary    = v.get_primary_file()
            filename   = primary.get("filename", "—") if primary else "—"
            dot_color  = GREEN if compatible else TEXT_DIM
            text_color = TEXT_PRI if compatible else TEXT_DIM

            row = ft.Container(
                bgcolor=INPUT_BG if compatible else CARD2_BG,
                border_radius=8, data=v.version_id,
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                on_click=(lambda e, ver=v: self._select_version(ver)) if compatible else None,
                on_hover=(
                    lambda e: (
                        setattr(e.control, "bgcolor",
                                "#202633" if e.data == "true" else INPUT_BG)
                        or e.control.update()
                    )
                ) if compatible else None,
                content=ft.Column([
                    ft.Row([
                        ft.Container(
                            width=8, height=8, border_radius=4, bgcolor=dot_color),
                        ft.Container(width=10),
                        ft.Text(v.name, color=text_color, size=10,
                                weight=ft.FontWeight.BOLD, expand=True),
                        ft.Text(", ".join(v.game_versions[:3]),
                                 color=TEXT_DIM, size=8, width=120),
                        ft.Text(", ".join(v.loaders[:2]),
                                 color=TEXT_DIM, size=8, width=100),
                        ft.Text(filename, color=TEXT_DIM, size=8,
                                width=160, overflow=ft.TextOverflow.ELLIPSIS),
                    ]),
                ], spacing=0),
            )
            self._versions_lv.controls.append(row)

        self._status_lbl.value   = (
            f"{len(versions)} versiones · {count_compat} compatibles "
            f"con {mc_ver or 'este perfil'}"
        )
        self._status_lbl.visible = True

        try:
            self._spinner_row.update()
            self._status_lbl.update()
            self._versions_lv.update()
        except Exception: pass

    def _select_version(self, version):
        self._selected_ver           = version
        self._install_btn.disabled   = False
        for c in self._versions_lv.controls:
            if hasattr(c, "data"):
                c.bgcolor = "#1a2a20" if c.data == version.version_id else INPUT_BG
                try: c.update()
                except Exception: pass
        try: self._install_btn.update()
        except Exception: pass

    def _do_install(self, e):
        if not self._selected_ver or not self.active_profile:
            self.app.snack("Selecciona un perfil activo.", error=True)
            return
        self._install_btn.disabled = True
        self._status_lbl.value     = f"Descargando {self._selected_ver.name}…"
        try:
            self._install_btn.update()
            self._status_lbl.update()
        except Exception: pass

        ver  = self._selected_ver
        prof = self.active_profile

        def do():
            try:
                self.app.modrinth_service.download_mod_version(ver, prof.mods_dir)
                def done():
                    self._status_lbl.value   = "✓ Instalado correctamente"
                    self._install_btn.disabled = False
                    try:
                        self._status_lbl.update()
                        self._install_btn.update()
                    except Exception: pass
                    self.app.snack(
                        f"{self.project.title} instalado en {prof.name}. ✓")
                    if self.on_installed:
                        self.on_installed()
                self.page.run_thread(done)
            except Exception as err:
                def _e():
                    self._status_lbl.value   = f"Error: {err}"
                    self._install_btn.disabled = False
                    try:
                        self._status_lbl.update()
                        self._install_btn.update()
                    except Exception: pass
                self.page.run_thread(_e)

        threading.Thread(target=do, daemon=True).start()