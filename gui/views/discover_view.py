"""
gui/views/discover_view.py — Descubrir mods en Modrinth
Búsqueda, filtros por loader/versión, tarjetas de mods y panel de detalle.
"""
import threading
import os
import json
import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER, BORDER_BRIGHT,
    GREEN, GREEN_DIM, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV, ACCENT_RED,
)
from utils.logger import get_logger

log = get_logger()

LOADERS = ["fabric", "forge", "neoforge", "quilt"]


class DiscoverView:
    def __init__(self, page: ft.Page, app):
        self.page = page
        self.app  = app
        self._results  = []
        self._page_num = 0
        self._loading  = False
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self):
        # ── Barra de búsqueda y filtros ───────────────────────────────────────
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
            border_radius=8, width=150,
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

        # ── Grid de resultados ────────────────────────────────────────────────
        self._status_lbl = ft.Text("Busca mods para empezar",
                                    color=TEXT_DIM, size=11)
        self._grid = ft.GridView(
            expand=True,
            runs_count=3,
            max_extent=280,
            child_aspect_ratio=1.5,
            spacing=12,
            run_spacing=12,
            controls=[],
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
                self._grid,
                ft.Container(
                    alignment=ft.alignment.center,
                    content=self._load_more_btn,
                    padding=ft.padding.only(top=16),
                ),
            ], spacing=0, expand=True),
        )

    # ── on_show ───────────────────────────────────────────────────────────────
    def on_show(self):
        self._refresh_profiles()

    def _refresh_profiles(self):
        profiles = self.app.profile_manager.get_all_profiles()
        self._profile_dd.options = [ft.dropdown.Option(p.name) for p in profiles]
        if profiles:
            last = self.app.settings.last_profile
            names = [p.name for p in profiles]
            self._profile_dd.value = last if last in names else names[0]
        try: self._profile_dd.update()
        except Exception: pass

    # ── Búsqueda ──────────────────────────────────────────────────────────────
    def _do_search(self, e):
        self._page_num = 0
        self._results  = []
        self._grid.controls.clear()
        self._load_more_btn.visible = False
        self._status_lbl.value = "Buscando…"
        try:
            self._status_lbl.update()
            self._grid.update()
            self._load_more_btn.update()
        except Exception: pass
        threading.Thread(target=self._fetch_results, daemon=True).start()

    def _load_more(self, e):
        if self._loading:
            return
        self._page_num += 1
        threading.Thread(target=self._fetch_results, daemon=True).start()

    def _active_profile(self):
        name = self._profile_dd.value
        if name:
            return self.app.profile_manager.get_profile_by_name(name)
        return None

    def _active_loader(self) -> str | None:
        val = self._loader_dd.value
        if val and val != "(todos)":
            return val
        # Intentar inferir desde loader_meta.json del perfil
        profile = self._active_profile()
        if profile:
            meta_path = os.path.join(profile.game_dir, "loader_meta.json")
            if os.path.isfile(meta_path):
                try:
                    with open(meta_path, "r") as f:
                        meta = json.load(f)
                    if isinstance(meta, list) and meta:
                        return meta[0].get("loader_type")
                    elif isinstance(meta, dict):
                        return meta.get("loader_type")
                except Exception:
                    pass
        return None

    def _fetch_results(self):
        self._loading = True
        query     = self._search_field.value.strip()
        profile   = self._active_profile()
        mc_ver    = profile.version_id if profile else None
        loader    = self._active_loader()
        limit     = 20
        offset    = self._page_num * limit

        try:
            results = self.app.modrinth_service.search_mods(
                query=query if query else "fabric",
                mc_version=mc_ver,
                loader=loader,
                limit=limit,
                offset=offset,
            )
            self._results.extend(results)
            def update():
                self._render_results(results)
            self.page.run_thread(update)
        except Exception as err:
            def show_err():
                self._status_lbl.value = f"Error: {err}"
                try: self._status_lbl.update()
                except Exception: pass
            self.page.run_thread(show_err)
        finally:
            self._loading = False

    def _render_results(self, new_results):
        profile       = self._active_profile()
        installed_ids = self._get_installed_ids(profile)

        for r in new_results:
            is_installed = r.slug in installed_ids or r.title in installed_ids
            card = self._make_card(r, is_installed)
            self._grid.controls.append(card)

        count = len(self._results)
        self._status_lbl.value = f"{count} resultados"
        self._load_more_btn.visible = len(new_results) >= 20

        try:
            self._grid.update()
            self._status_lbl.update()
            self._load_more_btn.update()
        except Exception: pass

    def _get_installed_ids(self, profile) -> set:
        if not profile:
            return set()
        import os
        mods_dir = profile.mods_dir
        if not os.path.isdir(mods_dir):
            return set()
        ids = set()
        for f in os.listdir(mods_dir):
            name = f.lower().replace(".jar","").replace(".disabled","")
            ids.add(name)
        return ids

    def _make_card(self, project, is_installed: bool) -> ft.Container:
        badge = ft.Container(
            bgcolor=GREEN if is_installed else "transparent",
            border_radius=4,
            padding=ft.padding.symmetric(horizontal=8, vertical=3),
            content=ft.Text("Instalado" if is_installed else "",
                             color=TEXT_INV, size=8,
                             weight=ft.FontWeight.BOLD),
        ) if is_installed else ft.Container()

        return ft.Container(
            bgcolor=CARD_BG, border_radius=10,
            padding=ft.padding.all(14),
            on_click=lambda e, p=project: self._open_detail(p),
            on_hover=lambda e: (
                setattr(e.control, "bgcolor",
                        CARD2_BG if e.data=="true" else CARD_BG)
                or e.control.update()),
            content=ft.Column([
                ft.Row([
                    ft.Text(project.title, color=TEXT_PRI, size=11,
                            weight=ft.FontWeight.BOLD, expand=True,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    badge,
                ]),
                ft.Text(project.description[:80]+"…"
                        if len(project.description)>80 else project.description,
                        color=TEXT_SEC, size=9, max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS),
                ft.Container(expand=True),
                ft.Row([
                    ft.Text(f"⬇ {project.downloads:,}",
                            color=TEXT_DIM, size=8),
                    ft.Container(expand=True),
                    ft.Text(", ".join(project.categories[:2]),
                            color=TEXT_DIM, size=8),
                ]),
            ], spacing=4, expand=True),
        )

    # ── Detalle ───────────────────────────────────────────────────────────────
    def _open_detail(self, project):
        ModDetailDialog(self.page, self.app, project,
                         active_profile=self._active_profile(),
                         active_loader=self._active_loader())


class ModDetailDialog:
    def __init__(self, page: ft.Page, app, project,
                  active_profile, active_loader: str | None):
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
        self._status_lbl = ft.Text("Cargando versiones…",
                                    color=TEXT_DIM, size=9)
        self._versions_col = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO,
                                        height=300)
        self._install_btn = ft.ElevatedButton(
            "⬇  Instalar versión seleccionada",
            bgcolor=GREEN, color=TEXT_INV,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            disabled=True,
            on_click=self._do_install,
        )

        desc = self.project.description
        profile_name = self.active_profile.name if self.active_profile else "—"

        self._dlg = ft.AlertDialog(
            title=ft.Text(self.project.title, color=TEXT_PRI, size=14),
            bgcolor=CARD_BG,
            content=ft.Container(
                width=640,
                content=ft.Column([
                    ft.Row([
                        ft.Text(desc[:120]+"…" if len(desc)>120 else desc,
                                color=TEXT_SEC, size=9, expand=True),
                    ]),
                    ft.Text(f"Perfil destino: {profile_name}",
                             color=TEXT_DIM, size=9),
                    ft.Divider(height=1, color=BORDER),
                    self._status_lbl,
                    ft.Container(height=4),
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
            mc_ver = (self.active_profile.version_id
                      if self.active_profile else None)
            versions = self.app.modrinth_service.get_project_versions(
                self.project.project_id,
                mc_version=mc_ver,
                loader=self.active_loader,
            )
            self.page.run_thread(lambda: self._render_versions(versions))
        except Exception as err:
            def show_err():
                self._status_lbl.value = f"Error: {err}"
                try: self._status_lbl.update()
                except Exception: pass
            self.page.run_thread(show_err)

    def _render_versions(self, versions):
        self._versions = versions
        self._versions_col.controls.clear()
        if not versions:
            self._status_lbl.value = "Sin versiones compatibles."
            try: self._status_lbl.update()
            except Exception: pass
            return

        mc_ver = (self.active_profile.version_id
                  if self.active_profile else None)
        self._status_lbl.value = f"{len(versions)} versiones disponibles"

        for v in versions:
            compatible = (mc_ver is None) or (mc_ver in v.game_versions)
            row = ft.Container(
                bgcolor=INPUT_BG if compatible else CARD2_BG,
                border_radius=6,
                padding=ft.padding.symmetric(horizontal=14, vertical=8),
                on_click=(lambda e, ver=v: self._select_version(ver))
                          if compatible else None,
                on_hover=(lambda e: (
                    setattr(e.control, "bgcolor",
                            CARD2_BG if e.data=="true" else INPUT_BG)
                    or e.control.update())) if compatible else None,
                content=ft.Row([
                    ft.Container(
                        width=8, height=8, border_radius=4,
                        bgcolor=GREEN if compatible else TEXT_DIM,
                    ),
                    ft.Container(width=10),
                    ft.Text(v.name, color=TEXT_PRI if compatible else TEXT_DIM,
                            size=10, expand=True),
                    ft.Text(", ".join(v.game_versions[:3]),
                             color=TEXT_DIM, size=8, width=100),
                    ft.Text(", ".join(v.loaders[:2]),
                             color=TEXT_DIM, size=8, width=80),
                ]),
                data=v.version_id,
            )
            self._versions_col.controls.append(row)

        try:
            self._versions_col.update()
            self._status_lbl.update()
        except Exception: pass

    def _select_version(self, version):
        self._selected_ver = version
        for c in self._versions_col.controls:
            c.bgcolor = "#1a2520" if c.data == version.version_id else INPUT_BG
            try: c.update()
            except Exception: pass
        self._install_btn.disabled = False
        try: self._install_btn.update()
        except Exception: pass

    def _do_install(self, e):
        if not self._selected_ver:
            return
        if not self.active_profile:
            self.app.snack("No hay perfil activo seleccionado.", error=True)
            return

        self._install_btn.disabled = True
        self._status_lbl.value = f"Descargando {self._selected_ver.name}…"
        try:
            self._install_btn.update()
            self._status_lbl.update()
        except Exception: pass

        ver = self._selected_ver
        prof = self.active_profile

        def download():
            try:
                self.app.modrinth_service.download_mod_version(
                    ver, prof.mods_dir)
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
                def show_err():
                    self._status_lbl.value = f"Error: {err}"
                    self._install_btn.disabled = False
                    try:
                        self._status_lbl.update()
                        self._install_btn.update()
                    except Exception: pass
                self.page.run_thread(show_err)

        threading.Thread(target=download, daemon=True).start()