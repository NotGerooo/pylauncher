"""
gui/views/library_view.py — Biblioteca de instancias
Grid de cards estilo Modrinth. Permite crear, editar y navegar a instancias.
"""
import os
import threading
import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER, BORDER_BRIGHT,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV, ACCENT_RED,
)
from utils.logger import get_logger

log = get_logger()

LOADER_ICONS = {
    "vanilla":  "🎮",
    "fabric":   "🪡",
    "neoforge": "🔷",
    "forge":    "🔨",
    "quilt":    "🪢",
}

LOADER_LIST = [
    ("vanilla",  "Vanilla"),
    ("fabric",   "Fabric"),
    ("neoforge", "NeoForge"),
    ("forge",    "Forge"),
    ("quilt",    "Quilt"),
]


class LibraryView:
    def __init__(self, page: ft.Page, app):
        self.page = page
        self.app  = app
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self):
        # Filtros superiores
        self._filter_tabs = _FilterTabs(
            ["Todas", "Modpacks", "Servers", "Custom"],
            on_change=lambda _: self._refresh(),
        )

        self._search_field = ft.TextField(
            hint_text="Buscar…",
            hint_style=ft.TextStyle(color=TEXT_DIM),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=20, width=260, height=40,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=8),
            prefix_icon=ft.icons.SEARCH,
            on_change=lambda e: self._refresh(),
        )

        self._sort_dd = ft.Dropdown(
            label="Ordenar", color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, width=160, height=40,
            label_style=ft.TextStyle(color=TEXT_DIM, size=9),
            options=[
                ft.dropdown.Option("name", "Por nombre"),
                ft.dropdown.Option("date", "Última vez jugada"),
                ft.dropdown.Option("version", "Versión MC"),
            ],
            value="name",
            content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
            on_change=lambda e: self._refresh(),
        )

        toolbar = ft.Container(
            bgcolor=BG,
            padding=ft.padding.only(bottom=16),
            content=ft.Row([
                self._filter_tabs.root,
                ft.Container(expand=True),
                self._search_field,
                ft.Container(width=10),
                self._sort_dd,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        self._grid = ft.GridView(
            runs_count=3,
            max_extent=320,
            child_aspect_ratio=1.7,
            spacing=14,
            run_spacing=14,
            expand=True,
        )

        self._empty_state = ft.Container(
            visible=False,
            expand=True,
            alignment=ft.alignment.center,
            content=ft.Column([
                ft.Text("📦", size=52, text_align=ft.TextAlign.CENTER),
                ft.Container(height=8),
                ft.Text("Sin instancias", color=TEXT_SEC, size=16,
                        weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Text("Crea tu primera instancia con el botón '+'",
                        color=TEXT_DIM, size=10, text_align=ft.TextAlign.CENTER),
                ft.Container(height=14),
                ft.Row([
                    ft.ElevatedButton(
                        "+ Nueva instancia", bgcolor=GREEN, color=TEXT_INV,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda e: self.open_create_dialog(),
                    )
                ], alignment=ft.MainAxisAlignment.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )

        self.root = ft.Container(
            expand=True, bgcolor=BG,
            padding=ft.padding.all(28),
            content=ft.Column([
                ft.Row([
                    ft.Column([
                        ft.Text("Biblioteca", color=TEXT_PRI, size=22,
                                weight=ft.FontWeight.BOLD),
                        ft.Text("Tus instancias de Minecraft",
                                color=TEXT_DIM, size=10),
                    ], spacing=2),
                    ft.Container(expand=True),
                    ft.ElevatedButton(
                        "+ Nueva instancia", bgcolor=GREEN, color=TEXT_INV,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.padding.symmetric(horizontal=16, vertical=10),
                        ),
                        on_click=lambda e: self.open_create_dialog(),
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=16),
                toolbar,
                ft.Stack([self._grid, self._empty_state], expand=True),
            ], spacing=0, expand=True),
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    def on_show(self):
        self._refresh()

    def _refresh(self):
        profiles = self.app.profile_manager.get_all_profiles()
        query    = (self._search_field.value or "").strip().lower()
        sort_by  = self._sort_dd.value or "name"

        # Filtrar
        if query:
            profiles = [p for p in profiles if query in p.name.lower()]

        # Ordenar
        if sort_by == "name":
            profiles = sorted(profiles, key=lambda p: p.name.lower())
        elif sort_by == "date":
            profiles = sorted(profiles, key=lambda p: p.last_used, reverse=True)
        elif sort_by == "version":
            profiles = sorted(profiles, key=lambda p: p.version_id, reverse=True)

        self._grid.controls.clear()
        self._empty_state.visible = (len(profiles) == 0)
        self._grid.visible        = (len(profiles) > 0)

        for p in profiles:
            self._grid.controls.append(self._make_card(p))

        try:
            self._grid.update()
            self._empty_state.update()
        except Exception:
            pass

    # ── Card de instancia ─────────────────────────────────────────────────────
    def _make_card(self, profile) -> ft.Container:
        loader  = self._read_loader(profile)
        icon    = LOADER_ICONS.get(loader, "🎮")
        last    = profile.last_used[:10] if profile.last_used else "—"

        badge = ft.Container(
            bgcolor=CARD2_BG, border_radius=4,
            padding=ft.padding.symmetric(horizontal=6, vertical=2),
            content=ft.Text(
                loader.capitalize(),
                color=GREEN if loader != "vanilla" else TEXT_DIM,
                size=8, weight=ft.FontWeight.BOLD,
            ),
        )

        card = ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            border=ft.border.all(1, BORDER),
            padding=ft.padding.all(16),
            on_hover=lambda e: (
                setattr(e.control, "border",
                        ft.border.all(1, BORDER_BRIGHT if e.data=="true" else BORDER))
                or e.control.update()),
            on_click=lambda e, p=profile: self.app._show_instance(p),
            content=ft.Column([
                # Header: icono + badge + menú
                ft.Row([
                    ft.Container(
                        width=44, height=44, border_radius=10,
                        bgcolor=CARD2_BG, alignment=ft.alignment.center,
                        content=ft.Text(icon, size=20),
                    ),
                    ft.Container(width=10),
                    ft.Column([
                        ft.Row([
                            ft.Text(profile.name, color=TEXT_PRI, size=12,
                                    weight=ft.FontWeight.BOLD,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True),
                        ]),
                        badge,
                    ], spacing=4, expand=True),
                    ft.PopupMenuButton(
                        icon=ft.icons.MORE_VERT,
                        icon_color=TEXT_DIM,
                        items=[
                            ft.PopupMenuItem(
                                text="Abrir",
                                on_click=lambda e, p=profile: self.app._show_instance(p),
                            ),
                            ft.PopupMenuItem(
                                text="Editar",
                                on_click=lambda e, p=profile: self._open_edit(p),
                            ),
                            ft.PopupMenuItem(
                                text="Eliminar",
                                on_click=lambda e, p=profile: self._on_delete(p),
                            ),
                        ],
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Container(expand=True),
                # Footer: versión + última vez
                ft.Row([
                    ft.Column([
                        ft.Text("Minecraft", color=TEXT_DIM, size=8),
                        ft.Text(profile.version_id, color=TEXT_SEC, size=10,
                                weight=ft.FontWeight.BOLD),
                    ], spacing=1),
                    ft.Container(expand=True),
                    ft.Column([
                        ft.Text("Última vez", color=TEXT_DIM, size=8),
                        ft.Text(last, color=TEXT_SEC, size=9),
                    ], spacing=1, horizontal_alignment=ft.CrossAxisAlignment.END),
                ]),
                ft.Container(height=8),
                # Botón play
                ft.ElevatedButton(
                    "▶ Jugar",
                    bgcolor=GREEN, color=TEXT_INV,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=6),
                        padding=ft.padding.symmetric(horizontal=12, vertical=6),
                    ),
                    on_click=lambda e, p=profile: self._launch_instance(p),
                ),
            ], spacing=6, expand=True),
        )
        return card

    # ── Acciones ──────────────────────────────────────────────────────────────
    def open_create_dialog(self):
        _CreateInstanceDialog(self.page, self.app, profile=None,
                              on_done=self._on_instance_saved)

    def _open_edit(self, profile):
        _CreateInstanceDialog(self.page, self.app, profile=profile,
                              on_done=self._on_instance_saved)

    def _on_instance_saved(self):
        self.app._refresh_instance_icons()
        # Invalidar caché de la instancia si fue editada
        self._refresh()

    def _on_delete(self, profile):
        def confirm(e):
            self.page.close(dlg)
            if e.control.text == "Eliminar":
                try:
                    self.app.profile_manager.delete_profile(profile.id)
                    self.app.invalidate_instance(profile.id)
                    self._refresh()
                    self.app.snack(f"'{profile.name}' eliminada.")
                except Exception as ex:
                    self.app.snack(str(ex), error=True)

        dlg = ft.AlertDialog(
            modal=True, bgcolor=CARD_BG,
            title=ft.Text("Eliminar instancia", color=TEXT_PRI),
            content=ft.Text(
                f"¿Eliminar '{profile.name}'?\nEsto no borra los archivos del juego.",
                color=TEXT_SEC),
            actions=[
                ft.TextButton("Cancelar", on_click=confirm),
                ft.TextButton("Eliminar",
                              style=ft.ButtonStyle(color=ACCENT_RED),
                              on_click=confirm),
            ],
        )
        self.page.open(dlg)

    def _launch_instance(self, profile):
        """Lanza la instancia directamente sin abrir el view."""
        self.app._show_instance(profile)
        # La instancia se lanza desde su propio view

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _read_loader(profile) -> str:
        meta_path = os.path.join(profile.game_dir, "loader_meta.json")
        if os.path.isfile(meta_path):
            try:
                import json
                with open(meta_path) as f:
                    meta = json.load(f)
                entries = meta if isinstance(meta, list) else [meta]
                if entries:
                    return (entries[0].get("loader_type")
                            or entries[0].get("loader", "vanilla"))
            except Exception:
                pass
        return "vanilla"


# ── Filtros superiores (pills) ────────────────────────────────────────────────
class _FilterTabs:
    def __init__(self, options: list[str], on_change):
        self._options   = options
        self._on_change = on_change
        self._active    = options[0]
        self._btns: dict[str, ft.Container] = {}
        self.root = ft.Row(spacing=6)
        for opt in options:
            self.root.controls.append(self._make(opt))

    def _make(self, label: str) -> ft.Container:
        active = label == self._active
        txt = ft.Text(label, color=GREEN if active else TEXT_SEC,
                      size=10, weight=ft.FontWeight.W_500)
        btn = ft.Container(
            bgcolor="#1a2e1a" if active else CARD2_BG,
            border=ft.border.all(1, GREEN if active else BORDER),
            border_radius=20,
            padding=ft.padding.symmetric(horizontal=14, vertical=7),
            content=txt,
            on_click=lambda e, l=label: self._select(l),
        )
        btn._txt = txt
        self._btns[label] = btn
        return btn

    def _select(self, label: str):
        self._active = label
        for l, btn in self._btns.items():
            active = l == label
            btn.bgcolor = "#1a2e1a" if active else CARD2_BG
            btn.border  = ft.border.all(1, GREEN if active else BORDER)
            btn._txt.color = GREEN if active else TEXT_SEC
            try: btn.update()
            except Exception: pass
        self._on_change(label)


# ══════════════════════════════════════════════════════════════════════════════
# Diálogo crear / editar instancia
# ══════════════════════════════════════════════════════════════════════════════
class _CreateInstanceDialog:
    """
    Diálogo de 2 pasos para crear/editar instancias.
    Paso 0: selección de tipo (Custom / más adelante Modpack)
    Paso 1: formulario (nombre, loader, versión MC, RAM)
    Al crear: instala automáticamente la versión si no está instalada.
    """

    def __init__(self, page: ft.Page, app, profile, on_done):
        self.page    = page
        self.app     = app
        self.profile = profile  # None = crear, Profile = editar
        self.on_done = on_done

        # Estado
        self._step        = 0
        self._sel_loader  = "vanilla"
        self._sel_mc      = ""
        self._available_versions: list[str] = []

        if profile:
            self._sel_loader = self._read_loader(profile)
            self._sel_mc     = profile.version_id
            self._step       = 1  # editar va directo al formulario

        self._loader_btns: dict[str, ft.Container] = {}

        # Controles del diálogo
        self._content_area = ft.Container(expand=True)
        self._back_btn = ft.TextButton(
            "← Atrás",
            style=ft.ButtonStyle(color=TEXT_DIM),
            visible=False,
            on_click=self._go_back,
        )
        self._primary_btn = ft.ElevatedButton(
            "Continuar" if not profile else "Guardar",
            bgcolor=GREEN, color=TEXT_INV,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=22, vertical=12),
            ),
            on_click=self._on_primary,
        )

        self._dlg = ft.AlertDialog(
            modal=True, bgcolor="#0f1117",
            title=ft.Row([
                ft.Text(
                    ("Editar instancia" if profile else "Nueva instancia"),
                    color=TEXT_PRI, size=16, weight=ft.FontWeight.BOLD, expand=True),
                ft.IconButton(
                    icon=ft.icons.CLOSE, icon_color=TEXT_DIM, icon_size=18,
                    on_click=lambda e: self.page.close(self._dlg),
                    style=ft.ButtonStyle(shape=ft.CircleBorder()),
                ),
            ]),
            content=ft.Container(width=600, content=ft.Column([
                self._content_area,
            ], spacing=0)),
            actions=[
                self._back_btn,
                ft.Container(expand=True),
                ft.TextButton("Cancelar",
                              style=ft.ButtonStyle(color=TEXT_DIM),
                              on_click=lambda e: self.page.close(self._dlg)),
                ft.Container(width=8),
                self._primary_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.START,
        )

        if profile:
            self._render_step1()
        else:
            self._render_step0()

        self.page.open(self._dlg)
        threading.Thread(target=self._load_versions, daemon=True).start()

    # ── Paso 0 ────────────────────────────────────────────────────────────────
    def _render_step0(self):
        self._step = 0
        self._back_btn.visible   = False
        self._primary_btn.text   = "Continuar"
        self._primary_btn.disabled = False

        def type_card(type_id, icon, title, desc, disabled=False):
            alpha = 0.35 if disabled else 1.0

            def hover(e):
                if disabled: return
                e.control.bgcolor = "#1e2530" if e.data=="true" else "#161b22"
                e.control.border  = ft.border.all(1, GREEN if e.data=="true" else BORDER)
                e.control.update()

            def click(e):
                if disabled: return
                self._render_step1()

            return ft.Container(
                bgcolor="#161b22", border_radius=10,
                border=ft.border.all(1, BORDER),
                padding=ft.padding.symmetric(horizontal=18, vertical=16),
                opacity=alpha,
                on_hover=hover, on_click=click,
                content=ft.Row([
                    ft.Container(
                        width=40, height=40, border_radius=10, bgcolor="#1f2937",
                        alignment=ft.alignment.center,
                        content=ft.Text(icon, size=20),
                    ),
                    ft.Container(width=14),
                    ft.Column([
                        ft.Row([
                            ft.Text(title, color=TEXT_PRI if not disabled else TEXT_DIM,
                                    size=12, weight=ft.FontWeight.BOLD),
                            ft.Container(
                                visible=disabled, bgcolor="#1f2937", border_radius=4,
                                padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                content=ft.Text("Próximamente", color=TEXT_DIM, size=8),
                            ),
                        ], spacing=8),
                        ft.Text(desc, color=TEXT_SEC, size=9),
                    ], spacing=3, expand=True),
                    ft.Icon(ft.icons.CHEVRON_RIGHT_ROUNDED,
                             color=TEXT_DIM if not disabled else "transparent", size=18),
                ]),
            )

        self._content_area.content = ft.Column([
            type_card("custom",  "🎮", "Custom Setup",
                      "Elige tu versión, loader y mods libremente."),
            type_card("modpack", "📦", "Modpack",
                      "Importa un modpack desde Modrinth.", disabled=True),
            type_card("import",  "📂", "Importar",
                      "Importa una instancia existente.", disabled=True),
        ], spacing=10)

        self._refresh_content()

    # ── Paso 1 ────────────────────────────────────────────────────────────────
    def _render_step1(self):
        self._step = 1
        self._back_btn.visible = (self.profile is None)
        self._primary_btn.text = ("Guardar" if self.profile else "+ Crear instancia")
        self._primary_btn.disabled = True

        # Nombre
        self._name_field = ft.TextField(
            label="Nombre de la instancia",
            value=self.profile.name if self.profile else "",
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN, border_radius=8,
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            on_change=self._check_ready,
        )

        # Loader pills
        self._loader_btns = {}
        loader_row = ft.Row(spacing=8, wrap=True)
        for lid, lname in LOADER_LIST:
            btn = self._make_loader_pill(lid, lname)
            self._loader_btns[lid] = btn
            loader_row.controls.append(btn)

        # Versión MC
        self._version_dd = ft.Dropdown(
            label="Versión de Minecraft",
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN, border_radius=8,
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            options=[], hint_text="Cargando…",
            on_change=self._on_version_change,
        )
        if self._available_versions:
            self._populate_versions()

        # RAM
        self._ram_dd = ft.Dropdown(
            label="RAM (MB)", color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN, border_radius=8,
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            value=str(self.profile.ram_mb) if self.profile else "2048",
            options=[ft.dropdown.Option(str(x))
                     for x in [1024, 2048, 3072, 4096, 6144, 8192]],
        )

        # Progreso
        self._prog_bar  = ft.ProgressBar(color=GREEN, bgcolor=CARD2_BG, visible=False)
        self._prog_text = ft.Text("", color=TEXT_DIM, size=9)

        self._content_area.content = ft.Column([
            self._name_field,
            ft.Container(height=16),
            ft.Text("Loader", color=TEXT_PRI, size=11, weight=ft.FontWeight.BOLD),
            ft.Container(height=8),
            loader_row,
            ft.Container(height=16),
            ft.Text("Versión del juego", color=TEXT_PRI, size=11,
                    weight=ft.FontWeight.BOLD),
            ft.Container(height=8),
            self._version_dd,
            ft.Container(height=16),
            ft.Text("Memoria RAM", color=TEXT_PRI, size=11, weight=ft.FontWeight.BOLD),
            ft.Container(height=8),
            self._ram_dd,
            ft.Container(height=10),
            self._prog_bar,
            self._prog_text,
        ], spacing=0, scroll=ft.ScrollMode.AUTO)

        self._refresh_content()

    # ── Loader pills ──────────────────────────────────────────────────────────
    def _make_loader_pill(self, lid: str, lname: str) -> ft.Container:
        active = (lid == self._sel_loader)
        txt = ft.Text(
            ("✓ " if active else "") + lname,
            color=GREEN if active else TEXT_SEC, size=10,
        )
        btn = ft.Container(
            bgcolor="#1a2e1a" if active else CARD2_BG,
            border=ft.border.all(1, GREEN if active else BORDER),
            border_radius=20,
            padding=ft.padding.symmetric(horizontal=14, vertical=7),
            content=txt,
            on_click=lambda e, l=lid: self._select_loader(l),
        )
        btn._txt = txt
        return btn

    def _select_loader(self, lid: str):
        self._sel_loader = lid
        for l, btn in self._loader_btns.items():
            active = l == lid
            btn.bgcolor = "#1a2e1a" if active else CARD2_BG
            btn.border  = ft.border.all(1, GREEN if active else BORDER)
            btn._txt.color = GREEN if active else TEXT_SEC
            btn._txt.value = ("✓ " if active else "") + dict(LOADER_LIST)[l]
            try: btn.update()
            except Exception: pass

    # ── Versiones ─────────────────────────────────────────────────────────────
    def _load_versions(self):
        try:
            versions = self.app.version_manager.get_available_versions("release")
            self._available_versions = [v.id for v in versions]
        except Exception:
            self._available_versions = self.app.version_manager.get_installed_version_ids()
        if self._step == 1:
            self.page.run_thread(self._populate_versions)

    def _populate_versions(self):
        versions = self._available_versions or self.app.version_manager.get_installed_version_ids()
        self._version_dd.options   = [ft.dropdown.Option(v) for v in versions]
        self._version_dd.hint_text = None
        cur = self._sel_mc
        self._version_dd.value = cur if cur in versions else (versions[0] if versions else None)
        self._sel_mc = self._version_dd.value or ""
        try: self._version_dd.update()
        except Exception: pass
        self._check_ready(None)

    def _on_version_change(self, e):
        self._sel_mc = e.control.value or ""
        self._check_ready(e)

    def _check_ready(self, e):
        name_ok    = bool(getattr(self, "_name_field", None)
                          and self._name_field.value.strip())
        version_ok = bool(self._sel_mc)
        enabled    = (name_ok and version_ok) if self._step == 1 else True
        self._primary_btn.disabled = not enabled
        try: self._primary_btn.update()
        except Exception: pass

    # ── Navegación ────────────────────────────────────────────────────────────
    def _go_back(self, e):
        self._render_step0()

    def _on_primary(self, e):
        if self._step == 0:
            self._render_step1()
        else:
            self._do_save()

    # ── Guardar ───────────────────────────────────────────────────────────────
    def _do_save(self):
        name    = (self._name_field.value or "").strip()
        version = self._sel_mc
        ram     = int(self._ram_dd.value) if self._ram_dd.value else 2048

        if not name or not version:
            self.app.snack("Nombre y versión son obligatorios.", error=True)
            return

        self._primary_btn.disabled = True
        self._prog_bar.visible     = True
        self._prog_text.value      = "Preparando…"
        try:
            self._primary_btn.update()
            self._prog_bar.update()
            self._prog_text.update()
        except Exception: pass

        def worker():
            try:
                def prog(msg):
                    self._prog_text.value = msg
                    try: self._prog_text.update()
                    except Exception: pass

                # Instalar versión si no está instalada
                installed = self.app.version_manager.get_installed_version_ids()
                if version not in installed:
                    prog(f"Descargando Minecraft {version}…")
                    self.app.version_manager.install_version(version)

                # Crear / actualizar perfil
                if self.profile:
                    self.app.profile_manager.update_profile(
                        self.profile.id, name=name, version_id=version, ram_mb=ram)
                    pobj = self.app.profile_manager.get_profile(self.profile.id)
                    self.app.invalidate_instance(self.profile.id)
                else:
                    pobj = self.app.profile_manager.create_profile(
                        name, version, ram_mb=ram)

                # Guardar loader_meta
                from managers.loader_manager import _save_loader_meta
                if self._sel_loader != "vanilla":
                    from managers.loader_manager import install_loader, get_loader_versions
                    prog(f"Instalando {self._sel_loader}…")
                    lv_list  = get_loader_versions(self._sel_loader, version)
                    lv       = lv_list[0] if lv_list else "latest"
                    install_loader(
                        loader=self._sel_loader,
                        mc_version=version,
                        loader_version=lv,
                        game_dir=pobj.game_dir,
                        libraries_dir=self.app.settings.libraries_dir,
                        versions_dir=self.app.settings.versions_dir,
                        progress_callback=prog,
                    )
                else:
                    _save_loader_meta(pobj.game_dir, {
                        "loader": "vanilla", "mc_version": version,
                        "loader_version": None, "main_class": None,
                        "extra_libs": [], "args": [],
                    })

                def finish():
                    self.page.close(self._dlg)
                    self.on_done()
                    self.app._refresh_instance_icons()
                    self.app.snack("Instancia guardada correctamente.")

                self.page.run_thread(finish)

            except Exception as ex:
                log.error(f"Error guardando instancia: {ex}")
                def err():
                    self.app.snack(str(ex), error=True)
                    self._primary_btn.disabled = False
                    self._prog_bar.visible     = False
                    self._prog_text.value      = ""
                    try:
                        self._primary_btn.update()
                        self._prog_bar.update()
                        self._prog_text.update()
                    except Exception: pass
                self.page.run_thread(err)

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_content(self):
        try:
            self._content_area.update()
            self._back_btn.update()
            self._primary_btn.update()
        except Exception: pass

    @staticmethod
    def _read_loader(profile) -> str:
        meta_path = os.path.join(profile.game_dir, "loader_meta.json")
        if os.path.isfile(meta_path):
            try:
                import json
                with open(meta_path) as f:
                    meta = json.load(f)
                entries = meta if isinstance(meta, list) else [meta]
                if entries:
                    return (entries[0].get("loader_type")
                            or entries[0].get("loader", "vanilla"))
            except Exception:
                pass
        return "vanilla"