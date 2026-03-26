"""
gui/views/mods_view.py — Gestión de mods por perfil
Incluye instalación desde archivo, habilitación/deshabilitación y búsqueda en Modrinth.
"""
import threading
import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV, ACCENT_RED,
)
from utils.logger import get_logger

log = get_logger()


class ModsView:
    def __init__(self, page: ft.Page, app):
        self.page = page
        self.app  = app
        self._current_profile = None
        self._file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self.page.overlay.append(self._file_picker)
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self):
        # Toolbar
        self._profile_dd = ft.Dropdown(
            label="Perfil",
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, width=220, options=[],
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            on_change=self._on_profile_change,
        )

        toolbar = ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.symmetric(horizontal=20, vertical=14),
            content=ft.Row([
                self._profile_dd,
                ft.Container(expand=True),
                ft.ElevatedButton(
                    "📂  Instalar .jar",
                    bgcolor=CARD2_BG, color=TEXT_PRI,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.padding.symmetric(horizontal=16, vertical=10),
                    ),
                    on_click=self._on_install_local,
                ),
                ft.Container(width=10),
                ft.ElevatedButton(
                    "🔍  Buscar en Modrinth",
                    bgcolor=GREEN, color=TEXT_INV,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.padding.symmetric(horizontal=16, vertical=10),
                    ),
                    on_click=self._on_open_modrinth,
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        # Lista de mods
        self._mods_col = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, expand=True)
        self._empty_lbl = ft.Text("Sin mods instalados en este perfil.",
                                   color=TEXT_DIM, size=11, visible=False)

        mods_card = ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.all(20), expand=True,
            content=ft.Column([
                ft.Text("Mods instalados", color=TEXT_PRI, size=14,
                        weight=ft.FontWeight.BOLD),
                ft.Container(height=12),
                self._empty_lbl,
                self._mods_col,
            ], spacing=0, expand=True),
        )

        self.root = ft.Container(
            expand=True, bgcolor=BG,
            padding=ft.padding.all(32),
            content=ft.Column([
                ft.Text("Mods", color=TEXT_PRI, size=26,
                        weight=ft.FontWeight.BOLD),
                ft.Text("Administra los mods de cada perfil",
                        color=TEXT_SEC, size=11),
                ft.Container(height=20),
                toolbar,
                ft.Container(height=16),
                mods_card,
            ], spacing=8, expand=True),
        )

    # ── on_show ───────────────────────────────────────────────────────────────
    def on_show(self):
        self._refresh_profiles()

    def _refresh_profiles(self):
        profiles = self.app.profile_manager.get_all_profiles()
        self._profile_dd.options = [ft.dropdown.Option(p.name) for p in profiles]
        if profiles:
            cur = self._profile_dd.value
            names = [p.name for p in profiles]
            if cur not in names:
                self._profile_dd.value = names[0]
                self._load_mods(names[0])
        try: self._profile_dd.update()
        except Exception: pass

    def _on_profile_change(self, e):
        if self._profile_dd.value:
            self._load_mods(self._profile_dd.value)

    def _load_mods(self, profile_name: str):
        p = self.app.profile_manager.get_profile_by_name(profile_name)
        if not p:
            return
        self._current_profile = p
        self._refresh_mods()

    def _refresh_mods(self):
        from managers.mod_manager import ModManager
        self._mods_col.controls.clear()
        if not self._current_profile:
            return
        mods = ModManager(self._current_profile).list_mods()
        self._empty_lbl.visible = (len(mods) == 0)
        try: self._empty_lbl.update()
        except Exception: pass

        for mod in mods:
            is_en = mod.is_enabled
            status_color = GREEN if is_en else TEXT_DIM
            status_text  = "Activo" if is_en else "Deshabilitado"

            row = ft.Container(
                bgcolor=INPUT_BG, border_radius=8,
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
                content=ft.Row([
                    ft.Container(
                        width=8, height=8, border_radius=4,
                        bgcolor=status_color,
                    ),
                    ft.Container(width=12),
                    ft.Text(mod.display_name, color=TEXT_PRI, size=10,
                            expand=True),
                    ft.Text(status_text, color=status_color, size=9, width=90),
                    ft.Text(f"{mod.size_mb} MB", color=TEXT_DIM, size=9, width=60),
                    ft.IconButton(
                        icon=ft.icons.CHECK_CIRCLE_OUTLINE if is_en
                             else ft.icons.RADIO_BUTTON_UNCHECKED,
                        icon_color=GREEN if is_en else TEXT_DIM,
                        icon_size=16,
                        tooltip="Deshabilitar" if is_en else "Habilitar",
                        on_click=lambda e, fn=mod.filename, en=is_en: self._toggle_mod(fn, en),
                    ),
                    ft.IconButton(
                        icon=ft.icons.DELETE_OUTLINE,
                        icon_color=ACCENT_RED,
                        icon_size=16,
                        tooltip="Eliminar",
                        on_click=lambda e, fn=mod.filename: self._delete_mod(fn),
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )
            self._mods_col.controls.append(row)
        try: self._mods_col.update()
        except Exception: pass

    # ── Acciones ──────────────────────────────────────────────────────────────
    def _on_install_local(self, e):
        if not self._current_profile:
            self.app.snack("Selecciona un perfil primero.", error=True)
            return
        self._file_picker.pick_files(
            dialog_title="Seleccionar mod",
            allowed_extensions=["jar"],
        )

    def _on_file_picked(self, e: ft.FilePickerResultEvent):
        if not e.files:
            return
        path = e.files[0].path
        from managers.mod_manager import ModManager, ModError
        try:
            ModManager(self._current_profile).install_mod_from_file(path)
            self._refresh_mods()
            self.app.snack("Mod instalado correctamente.")
        except ModError as err:
            self.app.snack(str(err), error=True)

    def _toggle_mod(self, filename: str, currently_enabled: bool):
        from managers.mod_manager import ModManager, ModError
        try:
            mm = ModManager(self._current_profile)
            if currently_enabled:
                mm.disable_mod(filename)
            else:
                mm.enable_mod(filename)
            self._refresh_mods()
        except ModError as err:
            self.app.snack(str(err), error=True)

    def _delete_mod(self, filename: str):
        def confirm(e2):
            self.page.close(dlg)
            from managers.mod_manager import ModManager, ModError
            try:
                ModManager(self._current_profile).delete_mod(filename)
                self._refresh_mods()
                self.app.snack("Mod eliminado.")
            except ModError as err:
                self.app.snack(str(err), error=True)

        dlg = ft.AlertDialog(
            title=ft.Text("Confirmar eliminación", color=TEXT_PRI),
            content=ft.Text(f"¿Eliminar '{filename}'?", color=TEXT_SEC),
            bgcolor=CARD_BG,
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e2: self.page.close(dlg)),
                ft.ElevatedButton("Eliminar", bgcolor="#2d1515", color=ACCENT_RED,
                                   on_click=confirm),
            ],
        )
        self.page.open(dlg)

    def _on_open_modrinth(self, e):
        if not self._current_profile:
            self.app.snack("Selecciona un perfil primero.", error=True)
            return
        ModrinthSearchDialog(self.page, self.app, self._current_profile,
                              callback=self._refresh_mods)


# ── Diálogo de búsqueda Modrinth ──────────────────────────────────────────────
class ModrinthSearchDialog:
    def __init__(self, page: ft.Page, app, profile, callback):
        self.page     = page
        self.app      = app
        self.profile  = profile
        self.callback = callback
        self._results = []
        self._selected_project_id: str | None = None
        self._build()

    def _build(self):
        self._search_field = ft.TextField(
            label="Buscar mods…",
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, expand=True,
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            on_submit=self._do_search,
        )
        self._status_lbl = ft.Text("Escribe para buscar mods", color=TEXT_DIM, size=9)
        self._results_col = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=340)

        self._install_btn = ft.ElevatedButton(
            "⬇  Instalar seleccionado",
            bgcolor=GREEN, color=TEXT_INV,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=self._do_install,
            disabled=True,
        )

        self._dlg = ft.AlertDialog(
            title=ft.Text(f"Buscar mods  —  {self.profile.name}",
                          color=TEXT_PRI, size=14),
            bgcolor=CARD_BG,
            content=ft.Container(
                width=620,
                content=ft.Column([
                    ft.Row([
                        self._search_field,
                        ft.Container(width=10),
                        ft.ElevatedButton(
                            "Buscar",
                            bgcolor=CARD2_BG, color=TEXT_PRI,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=8)),
                            on_click=lambda e: self._do_search(None),
                        ),
                    ]),
                    self._status_lbl,
                    ft.Container(height=8),
                    self._results_col,
                ], spacing=8),
            ),
            actions=[
                ft.TextButton("Cerrar",
                               on_click=lambda e: self.page.close(self._dlg)),
                self._install_btn,
            ],
        )
        self.page.open(self._dlg)

    def _do_search(self, e):
        query = self._search_field.value.strip()
        if not query:
            return
        self._status_lbl.value = "Buscando…"
        self._results_col.controls.clear()
        try:
            self._status_lbl.update()
            self._results_col.update()
        except Exception: pass

        def search():
            try:
                results = self.app.modrinth_service.search_mods(
                    query, mc_version=self.profile.version_id)
                self.page.run_thread(lambda: self._show_results(results))
            except Exception as err:
                def show_err():
                    self._status_lbl.value = f"Error: {err}"
                    try: self._status_lbl.update()
                    except Exception: pass
                self.page.run_thread(show_err)

        threading.Thread(target=search, daemon=True).start()

    def _show_results(self, results):
        self._results = results
        self._results_col.controls.clear()
        for r in results:
            mc_v = ", ".join(r.game_versions[-3:]) if r.game_versions else "—"
            row = ft.Container(
                bgcolor=INPUT_BG, border_radius=8,
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                on_click=lambda e, pid=r.project_id: self._select(pid),
                on_hover=lambda e: (
                    setattr(e.control, "bgcolor",
                            CARD2_BG if e.data=="true" else INPUT_BG)
                    or e.control.update()),
                content=ft.Row([
                    ft.Column([
                        ft.Text(r.title, color=TEXT_PRI, size=10,
                                weight=ft.FontWeight.BOLD),
                        ft.Text(r.description[:70]+"…"
                                if len(r.description)>70 else r.description,
                                color=TEXT_SEC, size=9,
                                overflow=ft.TextOverflow.ELLIPSIS),
                    ], expand=True, spacing=2),
                    ft.Text(f"{r.downloads:,}", color=TEXT_DIM, size=9, width=80),
                    ft.Text(mc_v, color=TEXT_DIM, size=8, width=100),
                ]),
                data=r.project_id,
            )
            self._results_col.controls.append(row)

        self._status_lbl.value = f"{len(results)} resultados"
        self._selected_project_id = None
        self._install_btn.disabled = True
        try:
            self._results_col.update()
            self._status_lbl.update()
            self._install_btn.update()
        except Exception: pass

    def _select(self, project_id: str):
        self._selected_project_id = project_id
        for c in self._results_col.controls:
            c.bgcolor = "#1a2520" if c.data == project_id else INPUT_BG
            try: c.update()
            except Exception: pass
        self._install_btn.disabled = False
        try: self._install_btn.update()
        except Exception: pass

    def _do_install(self, e):
        if not self._selected_project_id:
            return
        project = next((r for r in self._results
                         if r.project_id == self._selected_project_id), None)
        if not project:
            return

        self._status_lbl.value = f"Descargando {project.title}…"
        self._install_btn.disabled = True
        try:
            self._status_lbl.update()
            self._install_btn.update()
        except Exception: pass

        def download():
            try:
                version = self.app.modrinth_service.get_latest_version(
                    self._selected_project_id,
                    mc_version=self.profile.version_id,
                )
                if not version:
                    def no_ver():
                        self._status_lbl.value = "Sin versión compatible."
                        self._install_btn.disabled = False
                        try:
                            self._status_lbl.update()
                            self._install_btn.update()
                        except Exception: pass
                    self.page.run_thread(no_ver)
                    return
                self.app.modrinth_service.download_mod_version(
                    version, self.profile.mods_dir)
                def done():
                    self._status_lbl.value = "✓ Instalado"
                    self._install_btn.disabled = False
                    try:
                        self._status_lbl.update()
                        self._install_btn.update()
                    except Exception: pass
                    self.callback()
                    self.app.snack(f"{project.title} instalado.")
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