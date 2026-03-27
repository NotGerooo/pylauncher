"""
gui/views/discover_view.py — Descubrir contenido en Modrinth
Iconos reales (ft.Image), tarjetas con autor + versión + filename,
layout inspirado en la app oficial de Modrinth.
"""
import threading
import os
import json
import re
import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV, ACCENT_RED,
)
from utils.logger import get_logger

log   = get_logger()
LOADERS = ["fabric", "forge", "neoforge", "quilt", "optifine"]

# ── Paleta para iconos de respaldo ────────────────────────────────────────────
_PALETTE = [
    "#2d6a4f", "#1e3a5f", "#5c2a2a", "#3a3a1e",
    "#2a1e5c", "#1e5c4a", "#4a3a1e", "#5c3a4a",
]


def _icon_widget(icon_url: str, title: str, size: int = 48) -> ft.Control:
    """
    Devuelve un widget de icono para un mod:
    - Si hay icon_url: ft.Image que carga desde la red.
    - Si no hay URL o falla: caja de color con la inicial del nombre.
    """
    color    = _PALETTE[abs(hash(title)) % len(_PALETTE)]
    initial  = (title[0] if title else "?").upper()
    fallback = ft.Container(
        width=size, height=size, border_radius=8,
        bgcolor=color, alignment=ft.alignment.center,
        content=ft.Text(initial, color="#ffffff",
                         size=int(size * 0.38),
                         weight=ft.FontWeight.BOLD),
    )
    if not icon_url:
        return fallback
    return ft.Image(
        src=icon_url,
        width=size, height=size,
        border_radius=8,
        fit=ft.ImageFit.COVER,
        error_content=fallback,   # si la imagen falla → fallback
    )


class DiscoverView:
    def __init__(self, page: ft.Page, app):
        self.page      = page
        self.app       = app
        self._results  = []    # lista acumulada de ModrinthProject
        self._page_num = 0
        self._loading  = False
        self._build()

    # ── Construcción del layout ───────────────────────────────────────────────
    def _build(self):
        # Barra de búsqueda
        self._search_field = ft.TextField(
            hint_text="Buscar mods, modpacks, shaders…",
            hint_style=ft.TextStyle(color=TEXT_DIM),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, expand=True,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            on_submit=self._do_search,
            prefix_icon=ft.icons.SEARCH,
        )

        self._profile_dd = ft.Dropdown(
            label="Perfil",
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, width=190, options=[],
            label_style=ft.TextStyle(color=TEXT_DIM, size=9),
        )

        self._loader_dd = ft.Dropdown(
            label="Loader",
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, width=155,
            label_style=ft.TextStyle(color=TEXT_DIM, size=9),
            options=[ft.dropdown.Option("(todos)")] +
                    [ft.dropdown.Option(l) for l in LOADERS],
            value="(todos)",
        )

        search_bar = ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.symmetric(horizontal=20, vertical=14),
            content=ft.Row([
                self._search_field,
                ft.Container(width=12),
                self._profile_dd,
                ft.Container(width=10),
                self._loader_dd,
                ft.Container(width=10),
                ft.ElevatedButton(
                    "Buscar",
                    bgcolor=GREEN, color=TEXT_INV,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.padding.symmetric(horizontal=18, vertical=12),
                    ),
                    on_click=lambda e: self._do_search(None),
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        # Área de resultados
        self._status_lbl = ft.Text("Busca mods para empezar",
                                    color=TEXT_DIM, size=11)
        # Lista vertical (más parecido a Modrinth que un grid)
        self._results_col = ft.Column(
            spacing=8, scroll=ft.ScrollMode.AUTO, expand=True,
        )
        self._load_more_btn = ft.ElevatedButton(
            "Cargar más",
            bgcolor=CARD2_BG, color=TEXT_PRI,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            visible=False,
            on_click=self._load_more,
        )

        self.root = ft.Container(
            expand=True, bgcolor=BG,
            padding=ft.padding.all(32),
            content=ft.Column([
                ft.Text("Descubrir", color=TEXT_PRI, size=26,
                        weight=ft.FontWeight.BOLD),
                ft.Text("Encuentra mods directamente desde Modrinth",
                        color=TEXT_SEC, size=11),
                ft.Container(height=20),
                search_bar,
                ft.Container(height=16),
                self._status_lbl,
                ft.Container(height=8),
                self._results_col,
                ft.Container(
                    alignment=ft.alignment.center,
                    content=self._load_more_btn,
                    padding=ft.padding.only(top=16),
                ),
            ], spacing=0, expand=True),
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    def on_show(self):
        self._refresh_profiles()

    def _refresh_profiles(self):
        profiles = self.app.profile_manager.get_all_profiles()
        self._profile_dd.options = [ft.dropdown.Option(p.name) for p in profiles]
        if profiles:
            last  = self.app.settings.last_profile
            names = [p.name for p in profiles]
            self._profile_dd.value = last if last in names else names[0]
        try: self._profile_dd.update()
        except Exception: pass

    # ── Búsqueda ──────────────────────────────────────────────────────────────
    def _do_search(self, e):
        """Resetea los resultados y lanza una búsqueda nueva."""
        self._page_num = 0
        self._results  = []
        self._results_col.controls.clear()
        self._load_more_btn.visible = False
        self._status_lbl.value = "Buscando…"
        try:
            self._status_lbl.update()
            self._results_col.update()
            self._load_more_btn.update()
        except Exception: pass
        threading.Thread(target=self._fetch_results, daemon=True).start()

    def _load_more(self, e):
        if self._loading:
            return
        self._page_num += 1
        threading.Thread(target=self._fetch_results, daemon=True).start()

    # ── Helpers de estado ─────────────────────────────────────────────────────
    def _active_profile(self):
        name = self._profile_dd.value
        return self.app.profile_manager.get_profile_by_name(name) if name else None

    def _active_loader(self) -> str | None:
        """Loader del dropdown; si es '(todos)' intenta inferirlo desde loader_meta.json."""
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
        """
        Conjunto de identificadores normalizados de mods instalados.
        Normalizar = quitar guiones/guiones bajos y pasar a minúsculas.
        """
        if not profile or not os.path.isdir(profile.mods_dir):
            return set()
        result = set()
        for fn in os.listdir(profile.mods_dir):
            key = re.sub(r'[-_.]', '', fn.lower()
                         .replace(".jar", "").replace(".disabled", ""))
            result.add(key)
        return result

    # ── Fetch en hilo secundario ──────────────────────────────────────────────
    def _fetch_results(self):
        self._loading = True
        query   = self._search_field.value.strip() or "popular"
        profile = self._active_profile()
        mc_ver  = profile.version_id if profile else None
        loader  = self._active_loader()
        offset  = self._page_num * 20

        try:
            results  = self.app.modrinth_service.search_mods(
                query=query, mc_version=mc_ver,
                loader=loader, limit=20, offset=offset,
            )
            self._results.extend(results)
            installed = self._get_installed_set(profile)
            self.page.run_thread(lambda: self._render_results(results, installed))
        except Exception as err:
            def _err():
                self._status_lbl.value = f"Error de red: {err}"
                try: self._status_lbl.update()
                except Exception: pass
            self.page.run_thread(_err)
        finally:
            self._loading = False

    # ── Render en hilo principal ──────────────────────────────────────────────
    def _render_results(self, new_results, installed: set):
        for proj in new_results:
            slug_key  = re.sub(r'[-_.]', '', proj.slug.lower())
            title_key = re.sub(r'[-_. ]', '', proj.title.lower())
            is_inst   = slug_key in installed or title_key in installed
            self._results_col.controls.append(self._make_card(proj, is_inst))

        total = len(self._results)
        self._status_lbl.value      = f"{total} resultado{'s' if total != 1 else ''}"
        self._load_more_btn.visible = len(new_results) >= 20

        try:
            self._results_col.update()
            self._status_lbl.update()
            self._load_more_btn.update()
        except Exception: pass

    # ── Tarjeta de mod ────────────────────────────────────────────────────────
    def _make_card(self, proj, is_installed: bool) -> ft.Container:
        """
        Layout de tarjeta:
          [ICONO 52x52]  Título (bold)              [✓ Instalado]
                         por Autor · ⬇ descargas
                         descripción breve
                         [chip cat1] [chip cat2]
        """
        author = getattr(proj, "author", "")

        # Badge "Instalado"
        badge = ft.Container(
            visible=is_installed,
            bgcolor="#1a3d2a", border_radius=6,
            padding=ft.padding.symmetric(horizontal=10, vertical=4),
            content=ft.Text("✓ Instalado", color=GREEN, size=8,
                             weight=ft.FontWeight.BOLD),
        )

        # Fila autor + descargas
        author_part = ft.Text(f"por {author}", color=GREEN, size=9) \
                      if author else ft.Container(width=0)
        sep         = ft.Text("  ·  ", color=TEXT_DIM, size=9) if author else ft.Container(width=0)
        meta_row    = ft.Row([
            author_part, sep,
            ft.Text(f"⬇ {proj.downloads:,}", color=TEXT_DIM, size=9),
        ], spacing=0)

        # Chips de categorías
        cat_row = ft.Row([
            ft.Container(
                bgcolor=INPUT_BG, border_radius=4,
                padding=ft.padding.symmetric(horizontal=8, vertical=3),
                content=ft.Text(c, color=TEXT_DIM, size=8),
            ) for c in proj.categories[:3]
        ], spacing=6) if proj.categories else ft.Container(height=0)

        return ft.Container(
            bgcolor=CARD_BG, border_radius=10,
            padding=ft.padding.symmetric(horizontal=16, vertical=14),
            on_click=lambda e, p=proj: self._open_detail(p),
            on_hover=lambda e: (
                setattr(e.control, "bgcolor",
                        CARD2_BG if e.data == "true" else CARD_BG)
                or e.control.update()),
            content=ft.Row([
                _icon_widget(proj.icon_url, proj.title, size=52),
                ft.Container(width=16),
                ft.Column([
                    ft.Row([
                        ft.Text(proj.title, color=TEXT_PRI, size=12,
                                weight=ft.FontWeight.BOLD, expand=True,
                                overflow=ft.TextOverflow.ELLIPSIS),
                        badge,
                    ]),
                    meta_row,
                    ft.Text(proj.description[:100] + "…"
                             if len(proj.description) > 100 else proj.description,
                             color=TEXT_SEC, size=9,
                             overflow=ft.TextOverflow.ELLIPSIS, max_lines=2),
                    ft.Container(height=4),
                    cat_row,
                ], spacing=3, expand=True),
            ], vertical_alignment=ft.CrossAxisAlignment.START),
        )

    # ── Detalle ───────────────────────────────────────────────────────────────
    def _open_detail(self, project):
        ModDetailDialog(
            self.page, self.app, project,
            active_profile=self._active_profile(),
            active_loader=self._active_loader(),
        )


# ── Diálogo de detalle de un mod ──────────────────────────────────────────────
class ModDetailDialog:
    """
    Popup con el detalle completo de un mod:
    - Header con icono, título y autor
    - Lista de versiones con nombre, MC version, loader y nombre de archivo
    - Botón de instalación para la versión seleccionada
    """

    def __init__(self, page, app, project, active_profile, active_loader):
        self.page           = page
        self.app            = app
        self.project        = project
        self.active_profile = active_profile
        self.active_loader  = active_loader
        self._versions      = []
        self._selected_ver  = None
        self._build()
        threading.Thread(target=self._fetch_versions, daemon=True).start()

    def _build(self):
        self._status_lbl   = ft.Text("Cargando versiones…",
                                      color=TEXT_DIM, size=9)
        self._versions_col = ft.Column(spacing=6,
                                        scroll=ft.ScrollMode.AUTO, height=300)
        self._install_btn  = ft.ElevatedButton(
            "⬇  Instalar versión seleccionada",
            bgcolor=GREEN, color=TEXT_INV,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            disabled=True, on_click=self._do_install,
        )

        author    = getattr(self.project, "author", "")
        prof_name = self.active_profile.name if self.active_profile else "—"

        # Header del diálogo
        header = ft.Row([
            _icon_widget(self.project.icon_url, self.project.title, size=56),
            ft.Container(width=16),
            ft.Column([
                ft.Text(self.project.title, color=TEXT_PRI, size=14,
                        weight=ft.FontWeight.BOLD),
                ft.Text(f"por {author}" if author else "",
                         color=GREEN, size=9),
                ft.Text(self.project.description[:130] + "…"
                         if len(self.project.description) > 130
                         else self.project.description,
                         color=TEXT_SEC, size=9),
            ], spacing=3, expand=True),
        ], vertical_alignment=ft.CrossAxisAlignment.START)

        self._dlg = ft.AlertDialog(
            title=ft.Container(),          # header va dentro del content
            bgcolor=CARD_BG,
            content=ft.Container(
                width=700,
                content=ft.Column([
                    header,
                    ft.Text(f"Perfil destino: {prof_name}",
                             color=TEXT_DIM, size=9),
                    ft.Divider(height=1, color=BORDER),
                    self._status_lbl,
                    ft.Container(height=6),
                    self._versions_col,
                ], spacing=8),
            ),
            actions=[
                ft.TextButton("Cerrar",
                               on_click=lambda e: self.page.close(self._dlg)),
                self._install_btn,
            ],
        )
        self.page.open(self._dlg)

    def _fetch_versions(self):
        try:
            mc_ver   = (self.active_profile.version_id
                        if self.active_profile else None)
            versions = self.app.modrinth_service.get_project_versions(
                self.project.project_id,
                mc_version=mc_ver,
                loader=self.active_loader,
            )
            self.page.run_thread(lambda: self._render_versions(versions))
        except Exception as err:
            def _e():
                self._status_lbl.value = f"Error: {err}"
                try: self._status_lbl.update()
                except Exception: pass
            self.page.run_thread(_e)

    def _render_versions(self, versions):
        self._versions = versions
        mc_ver         = (self.active_profile.version_id
                          if self.active_profile else None)
        self._versions_col.controls.clear()

        if not versions:
            self._status_lbl.value = "Sin versiones compatibles con este perfil."
            try:
                self._status_lbl.update()
                self._versions_col.update()
            except Exception: pass
            return

        self._status_lbl.value = f"{len(versions)} versiones disponibles"

        for v in versions:
            compatible = not mc_ver or (mc_ver in v.game_versions)
            primary    = v.get_primary_file()
            filename   = primary.get("filename", "—") if primary else "—"
            bg         = INPUT_BG if compatible else CARD2_BG

            row = ft.Container(
                bgcolor=bg, border_radius=8, data=v.version_id,
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                on_click=(lambda e, ver=v: self._select_version(ver))
                          if compatible else None,
                on_hover=(lambda e: (
                    setattr(e.control, "bgcolor",
                            CARD2_BG if e.data == "true" else INPUT_BG)
                    or e.control.update())) if compatible else None,
                content=ft.Column([
                    ft.Row([
                        # Dot indicador
                        ft.Container(width=8, height=8, border_radius=4,
                                      bgcolor=GREEN if compatible else TEXT_DIM),
                        ft.Container(width=10),
                        # Nombre de la versión del mod (bold)
                        ft.Text(v.name,
                                color=TEXT_PRI if compatible else TEXT_DIM,
                                size=10, weight=ft.FontWeight.BOLD, expand=True),
                        # Versiones de MC compatibles
                        ft.Text(", ".join(v.game_versions[:3]),
                                 color=TEXT_DIM, size=8, width=110),
                        # Loaders compatibles
                        ft.Text(", ".join(v.loaders[:2]),
                                 color=TEXT_DIM, size=8, width=80),
                    ]),
                    # Nombre del archivo a descargar
                    ft.Row([
                        ft.Container(width=18),
                        ft.Text(filename, color=TEXT_DIM, size=8, italic=True),
                    ]),
                ], spacing=4),
            )
            self._versions_col.controls.append(row)

        try:
            self._versions_col.update()
            self._status_lbl.update()
        except Exception: pass

    def _select_version(self, version):
        self._selected_ver         = version
        self._install_btn.disabled = False
        for c in self._versions_col.controls:
            c.bgcolor = "#1a2520" if c.data == version.version_id else INPUT_BG
            try: c.update()
            except Exception: pass
        try: self._install_btn.update()
        except Exception: pass

    def _do_install(self, e):
        if not self._selected_ver or not self.active_profile:
            self.app.snack("Selecciona un perfil activo.", error=True)
            return

        self._install_btn.disabled = True
        self._status_lbl.value = f"Descargando {self._selected_ver.name}…"
        try:
            self._install_btn.update()
            self._status_lbl.update()
        except Exception: pass

        ver  = self._selected_ver
        prof = self.active_profile

        def download():
            try:
                self.app.modrinth_service.download_mod_version(ver, prof.mods_dir)
                def done():
                    self._status_lbl.value = "✓ Instalado correctamente"
                    self._install_btn.disabled = False
                    try:
                        self._status_lbl.update()
                        self._install_btn.update()
                    except Exception: pass
                    self.app.snack(f"{self.project.title} instalado en {prof.name}.")
                self.page.run_thread(done)
            except Exception as err:
                def _e():
                    self._status_lbl.value = f"Error: {err}"
                    self._install_btn.disabled = False
                    try:
                        self._status_lbl.update()
                        self._install_btn.update()
                    except Exception: pass
                self.page.run_thread(_e)

        threading.Thread(target=download, daemon=True).start()