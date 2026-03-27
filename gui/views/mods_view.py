"""
gui/views/mods_view.py — Gestión de mods instalados por perfil
Cada mod muestra: icono con inicial · nombre (bold) / filename · versión · toggle · borrar
Incluye filtro en tiempo real y diálogo de búsqueda en Modrinth.
"""
import threading
import re
import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV, ACCENT_RED,
)
from utils.logger import get_logger

log = get_logger()

# ── Paleta de colores para iconos de mods ─────────────────────────────────────
_PALETTE = [
    "#2d6a4f", "#1e3a5f", "#5c2a2a", "#3a3a1e",
    "#2a1e5c", "#1e5c4a", "#4a3a1e", "#5c3a4a",
]


def _mod_icon(name: str, size: int = 42) -> ft.Container:
    """Caja cuadrada redondeada con la inicial del nombre del mod."""
    color   = _PALETTE[abs(hash(name)) % len(_PALETTE)]
    initial = (name[0] if name else "?").upper()
    return ft.Container(
        width=size, height=size,
        border_radius=8, bgcolor=color,
        alignment=ft.alignment.center,
        content=ft.Text(initial, color="#ffffff",
                         size=int(size * 0.4),
                         weight=ft.FontWeight.BOLD),
    )


def _parse_version(filename: str) -> str:
    """
    Extrae la versión del nombre de archivo de un mod JAR.
    
    Ejemplos:
      sodium-fabric-0.5.11+mc1.21.1.jar      →  0.5.11+mc1.21.1
      jei-1.21.1-forge-18.0.0.1.jar          →  18.0.0.1
      appleskin-fabric-mc1.21.11-3.0.8.jar   →  3.0.8
      cloth-config-21.11.153+fabric.jar      →  21.11.153+fabric
    """
    # Quitar extensión
    name  = re.sub(r'\.(jar|disabled)$', '', filename, flags=re.IGNORECASE)
    parts = name.split('-')
    # Recorrer de atrás hacia adelante buscando un segmento que empiece con digit.digit
    for part in reversed(parts):
        if re.match(r'^\d+\.\d+', part):
            return part
    return ""


class ModsView:
    def __init__(self, page: ft.Page, app):
        self.page             = page
        self.app              = app
        self._current_profile = None
        self._file_picker     = ft.FilePicker(on_result=self._on_file_picked)
        self.page.overlay.append(self._file_picker)
        self._build()

    # ── Construcción del layout ───────────────────────────────────────────────
    def _build(self):
        # Selector de perfil activo
        self._profile_dd = ft.Dropdown(
            label="Perfil",
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, width=220, options=[],
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            on_change=self._on_profile_change,
        )

        # Campo de filtro rápido dentro de mods instalados
        self._filter_field = ft.TextField(
            hint_text="Filtrar mods…",
            hint_style=ft.TextStyle(color=TEXT_DIM),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, width=200,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=8),
            on_change=self._on_filter_change,
            prefix_icon=ft.icons.FILTER_LIST,
        )

        toolbar = ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.symmetric(horizontal=20, vertical=14),
            content=ft.Row([
                self._profile_dd,
                ft.Container(width=12),
                self._filter_field,
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
                    "🔍  Modrinth",
                    bgcolor=GREEN, color=TEXT_INV,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.padding.symmetric(horizontal=16, vertical=10),
                    ),
                    on_click=self._on_open_modrinth,
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        # Encabezado de columnas de la lista
        col_header = ft.Container(
            padding=ft.padding.only(left=16, right=16, bottom=6),
            content=ft.Row([
                ft.Container(width=42 + 14),     # ancho icono + gap
                ft.Text("Mod / Archivo", color=TEXT_DIM, size=9, expand=True),
                ft.Text("Versión", color=TEXT_DIM, size=9, width=140,
                         text_align=ft.TextAlign.CENTER),
                ft.Text("Estado", color=TEXT_DIM, size=9, width=72),
                ft.Container(width=84),            # botones acción
            ]),
        )

        self._count_lbl = ft.Text("", color=TEXT_DIM, size=9)
        self._empty_lbl = ft.Text(
            "Sin mods instalados en este perfil.",
            color=TEXT_DIM, size=11, visible=False,
        )
        self._mods_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)

        mods_card = ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.all(20), expand=True,
            content=ft.Column([
                ft.Row([
                    ft.Text("Mods instalados", color=TEXT_PRI, size=14,
                            weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    self._count_lbl,
                ]),
                ft.Container(height=10),
                col_header,
                ft.Divider(height=1, color=BORDER),
                ft.Container(height=4),
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

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    def on_show(self):
        self._refresh_profiles()

    def _refresh_profiles(self):
        profiles = self.app.profile_manager.get_all_profiles()
        self._profile_dd.options = [ft.dropdown.Option(p.name) for p in profiles]
        if profiles:
            names = [p.name for p in profiles]
            cur   = self._profile_dd.value
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
        self._current_profile    = p
        self._filter_field.value = ""
        try: self._filter_field.update()
        except Exception: pass
        self._refresh_mods()

    def _on_filter_change(self, e):
        """Filtra la lista visible en tiempo real sin tocar disco."""
        self._refresh_mods(filter_text=self._filter_field.value or "")

    # ── Renderizado de la lista ───────────────────────────────────────────────
    def _refresh_mods(self, filter_text: str = ""):
        from managers.mod_manager import ModManager
        self._mods_col.controls.clear()
        if not self._current_profile:
            return

        all_mods = ModManager(self._current_profile).list_mods()

        # Filtro por nombre (case-insensitive)
        query = filter_text.strip().lower()
        mods  = ([m for m in all_mods if query in m.display_name.lower()]
                  if query else all_mods)

        # Actualizar contador y estado vacío
        self._empty_lbl.visible = (len(mods) == 0)
        self._count_lbl.value   = (
            f"{len(mods)}/{len(all_mods)} mods" if query else f"{len(mods)} mods"
        )
        try:
            self._empty_lbl.update()
            self._count_lbl.update()
        except Exception: pass

        for mod in mods:
            self._mods_col.controls.append(self._make_mod_row(mod))
        try: self._mods_col.update()
        except Exception: pass

    def _make_mod_row(self, mod) -> ft.Container:
        """
        Layout de cada fila:
          [ICONO]  Nombre (bold)          │  v1.2.3   │  ● Activo  │  [⏻] [🗑]
                   archivo.jar (dim)      │           │            │
        """
        is_en   = mod.is_enabled
        version = _parse_version(mod.filename)

        return ft.Container(
            bgcolor=INPUT_BG, border_radius=8,
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
            on_hover=lambda e: (
                setattr(e.control, "bgcolor",
                        CARD2_BG if e.data == "true" else INPUT_BG)
                or e.control.update()),
            content=ft.Row([
                # Icono con inicial
                _mod_icon(mod.display_name, size=42),
                ft.Container(width=14),

                # Nombre y archivo (expand para ocupar espacio libre)
                ft.Column([
                    ft.Text(mod.display_name, color=TEXT_PRI, size=10,
                            weight=ft.FontWeight.BOLD,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(mod.filename, color=TEXT_DIM, size=8,
                            italic=True,
                            overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=2, expand=True),

                # Versión del mod
                ft.Text(version or "—", color=TEXT_SEC, size=9,
                         width=140, text_align=ft.TextAlign.CENTER),

                # Estado (dot + texto)
                ft.Row([
                    ft.Container(width=8, height=8, border_radius=4,
                                  bgcolor=GREEN if is_en else TEXT_DIM),
                    ft.Container(width=6),
                    ft.Text("Activo" if is_en else "Off",
                             color=GREEN if is_en else TEXT_DIM,
                             size=9),
                ], spacing=0, width=72),

                # Botones de acción
                ft.Row([
                    ft.IconButton(
                        icon=(ft.icons.TOGGLE_ON if is_en
                               else ft.icons.TOGGLE_OFF),
                        icon_color=GREEN if is_en else TEXT_DIM,
                        icon_size=20,
                        tooltip="Deshabilitar" if is_en else "Habilitar",
                        on_click=lambda e, fn=mod.filename, en=is_en:
                            self._toggle_mod(fn, en),
                    ),
                    ft.IconButton(
                        icon=ft.icons.DELETE_OUTLINE,
                        icon_color=ACCENT_RED,
                        icon_size=18,
                        tooltip="Eliminar",
                        on_click=lambda e, fn=mod.filename:
                            self._delete_mod(fn),
                    ),
                ], spacing=0, width=84),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    # ── Acciones ──────────────────────────────────────────────────────────────
    def _on_install_local(self, e):
        if not self._current_profile:
            self.app.snack("Selecciona un perfil primero.", error=True)
            return
        self._file_picker.pick_files(
            dialog_title="Seleccionar mod (.jar)",
            allowed_extensions=["jar"],
        )

    def _on_file_picked(self, e: ft.FilePickerResultEvent):
        if not e.files:
            return
        from managers.mod_manager import ModManager, ModError
        try:
            ModManager(self._current_profile).install_mod_from_file(e.files[0].path)
            self._refresh_mods(filter_text=self._filter_field.value or "")
            self.app.snack("Mod instalado correctamente.")
        except ModError as err:
            self.app.snack(str(err), error=True)

    def _toggle_mod(self, filename: str, currently_enabled: bool):
        from managers.mod_manager import ModManager, ModError
        try:
            mm = ModManager(self._current_profile)
            mm.disable_mod(filename) if currently_enabled else mm.enable_mod(filename)
            self._refresh_mods(filter_text=self._filter_field.value or "")
        except ModError as err:
            self.app.snack(str(err), error=True)

    def _delete_mod(self, filename: str):
        def confirm(e2):
            self.page.close(dlg)
            from managers.mod_manager import ModManager, ModError
            try:
                ModManager(self._current_profile).delete_mod(filename)
                self._refresh_mods(filter_text=self._filter_field.value or "")
                self.app.snack("Mod eliminado.")
            except ModError as err:
                self.app.snack(str(err), error=True)

        dlg = ft.AlertDialog(
            title=ft.Text("Eliminar mod", color=TEXT_PRI),
            bgcolor=CARD_BG,
            content=ft.Text(
                f"¿Eliminar '{filename}'?\nEsta acción no se puede deshacer.",
                color=TEXT_SEC,
            ),
            actions=[
                ft.TextButton("Cancelar",
                               on_click=lambda e2: self.page.close(dlg)),
                ft.ElevatedButton("Eliminar", bgcolor="#2d1515", color=ACCENT_RED,
                                   on_click=confirm),
            ],
        )
        self.page.open(dlg)

    def _on_open_modrinth(self, e):
        if not self._current_profile:
            self.app.snack("Selecciona un perfil primero.", error=True)
            return
        ModrinthSearchDialog(
            self.page, self.app, self._current_profile,
            callback=lambda: self._refresh_mods(
                filter_text=self._filter_field.value or ""),
        )


# ── Diálogo de búsqueda en Modrinth ──────────────────────────────────────────
class ModrinthSearchDialog:
    """
    Popup para buscar mods en Modrinth e instalar directamente en el perfil activo.
    Muestra icono + nombre + autor a la izquierda, versiones MC y descargas a la derecha.
    """

    def __init__(self, page, app, profile, callback):
        self.page          = page
        self.app           = app
        self.profile       = profile
        self.callback      = callback
        self._results      = []
        self._selected_id: str | None = None
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
        self._status_lbl  = ft.Text("Escribe para buscar mods",
                                     color=TEXT_DIM, size=9)
        self._results_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO,
                                       height=380)
        self._install_btn = ft.ElevatedButton(
            "⬇  Instalar seleccionado",
            bgcolor=GREEN, color=TEXT_INV,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            disabled=True, on_click=self._do_install,
        )

        self._dlg = ft.AlertDialog(
            title=ft.Text(f"Buscar mods  —  {self.profile.name}",
                          color=TEXT_PRI, size=14),
            bgcolor=CARD_BG,
            content=ft.Container(
                width=680,
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
        self._selected_id          = None
        self._install_btn.disabled = True
        try:
            self._status_lbl.update()
            self._results_col.update()
            self._install_btn.update()
        except Exception: pass

        def search():
            try:
                results = self.app.modrinth_service.search_mods(
                    query, mc_version=self.profile.version_id)
                self.page.run_thread(lambda: self._show_results(results))
            except Exception as err:
                def _e():
                    self._status_lbl.value = f"Error: {err}"
                    try: self._status_lbl.update()
                    except Exception: pass
                self.page.run_thread(_e)

        threading.Thread(target=search, daemon=True).start()

    def _show_results(self, results):
        from gui.views.discover_view import _icon_widget   # reutilizar helper de iconos
        self._results = results
        self._results_col.controls.clear()

        for r in results:
            mc_v   = ", ".join(r.game_versions[-3:]) if r.game_versions else "—"
            author = getattr(r, "author", "")
            row = ft.Container(
                bgcolor=INPUT_BG, border_radius=8,
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                data=r.project_id,
                on_click=lambda e, pid=r.project_id: self._select(pid),
                on_hover=lambda e: (
                    setattr(e.control, "bgcolor",
                            CARD2_BG if e.data == "true" else INPUT_BG)
                    or e.control.update()),
                content=ft.Row([
                    # Icono
                    _icon_widget(r.icon_url, r.title, size=42),
                    ft.Container(width=14),
                    # Nombre y autor
                    ft.Column([
                        ft.Text(r.title, color=TEXT_PRI, size=10,
                                weight=ft.FontWeight.BOLD,
                                overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(f"por {author}" if author
                                 else r.description[:60] + "…",
                                 color=TEXT_SEC, size=9,
                                 overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=2, expand=True),
                    # Versión MC + descargas (derecha)
                    ft.Column([
                        ft.Text(mc_v, color=TEXT_DIM, size=8,
                                text_align=ft.TextAlign.RIGHT),
                        ft.Text(f"⬇ {r.downloads:,}", color=TEXT_DIM, size=8,
                                text_align=ft.TextAlign.RIGHT),
                    ], spacing=2, width=120,
                       horizontal_alignment=ft.CrossAxisAlignment.END),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )
            self._results_col.controls.append(row)

        self._status_lbl.value = f"{len(results)} resultados"
        try:
            self._results_col.update()
            self._status_lbl.update()
        except Exception: pass

    def _select(self, project_id: str):
        self._selected_id          = project_id
        self._install_btn.disabled = False
        for c in self._results_col.controls:
            c.bgcolor = "#1a2520" if c.data == project_id else INPUT_BG
            try: c.update()
            except Exception: pass
        try: self._install_btn.update()
        except Exception: pass

    def _do_install(self, e):
        proj = next((r for r in self._results
                      if r.project_id == self._selected_id), None)
        if not proj:
            return

        self._status_lbl.value     = f"Descargando {proj.title}…"
        self._install_btn.disabled = True
        try:
            self._status_lbl.update()
            self._install_btn.update()
        except Exception: pass

        def download():
            try:
                version = self.app.modrinth_service.get_latest_version(
                    self._selected_id, mc_version=self.profile.version_id)
                if not version:
                    def _nv():
                        self._status_lbl.value = "Sin versión compatible."
                        self._install_btn.disabled = False
                        try:
                            self._status_lbl.update()
                            self._install_btn.update()
                        except Exception: pass
                    self.page.run_thread(_nv)
                    return
                self.app.modrinth_service.download_mod_version(
                    version, self.profile.mods_dir)
                def done():
                    self._status_lbl.value = "✓ Instalado correctamente"
                    self._install_btn.disabled = False
                    try:
                        self._status_lbl.update()
                        self._install_btn.update()
                    except Exception: pass
                    self.callback()
                    self.app.snack(f"{proj.title} instalado.")
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