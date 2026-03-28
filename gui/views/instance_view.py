"""
gui/views/instance_view.py — Vista de instancia individual
Tabs: Content | Files | Worlds | Logs
Content unifica Mods, Resource Packs y Shaders.
"""
import os
import re
import threading
import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER, BORDER_BRIGHT,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV, ACCENT_RED,
)
from utils.logger import get_logger

log = get_logger()

_PALETTE = [
    "#2d6a4f", "#1e3a5f", "#5c2a2a", "#3a3a1e",
    "#2a1e5c", "#1e5c4a", "#4a3a1e", "#5c3a4a",
]

LOADER_ICONS = {
    "vanilla":  "🎮",
    "fabric":   "🪡",
    "neoforge": "🔷",
    "forge":    "🔨",
    "quilt":    "🪢",
}


def _initial_icon(name: str, size: int = 40) -> ft.Container:
    color   = _PALETTE[abs(hash(name)) % len(_PALETTE)]
    initial = (name[0] if name else "?").upper()
    return ft.Container(
        width=size, height=size, border_radius=8,
        bgcolor=color, alignment=ft.alignment.center,
        content=ft.Text(initial, color="#fff", size=int(size * 0.4),
                        weight=ft.FontWeight.BOLD),
    )


def _parse_version(filename: str) -> str:
    name  = re.sub(r'\.(jar|zip|disabled)$', '', filename, flags=re.IGNORECASE)
    parts = name.split('-')
    for part in reversed(parts):
        if re.match(r'^\d+\.\d+', part):
            return part
    return ""


# ══════════════════════════════════════════════════════════════════════════════
class InstanceView:
    """Vista completa de una instancia con tabs."""

    def __init__(self, page: ft.Page, app, profile):
        self.page    = page
        self.app     = app
        self.profile = profile
        self._active_tab = "content"
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self):
        loader = self._read_loader()
        icon   = LOADER_ICONS.get(loader, "🎮")

        # ── Header ────────────────────────────────────────────────────────────
        self._play_btn = ft.ElevatedButton(
            "▶  Play",
            bgcolor=GREEN, color=TEXT_INV,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=20, vertical=12),
            ),
            on_click=self._on_play,
        )

        header = ft.Container(
            bgcolor=CARD_BG,
            padding=ft.padding.symmetric(horizontal=28, vertical=16),
            border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
            content=ft.Row([
                # Back button
                ft.IconButton(
                    icon=ft.icons.ARROW_BACK_IOS_NEW_ROUNDED,
                    icon_color=TEXT_DIM, icon_size=18,
                    tooltip="Volver a Biblioteca",
                    on_click=lambda e: self.app._show_view("library"),
                ),
                ft.Container(width=8),
                # Icono instancia
                ft.Container(
                    width=44, height=44, border_radius=10,
                    bgcolor=CARD2_BG, alignment=ft.alignment.center,
                    content=ft.Text(icon, size=22),
                ),
                ft.Container(width=14),
                ft.Column([
                    ft.Text(self.profile.name, color=TEXT_PRI, size=16,
                            weight=ft.FontWeight.BOLD),
                    ft.Text(
                        f"{loader.capitalize()}  •  Minecraft {self.profile.version_id}"
                        f"  •  {self.profile.ram_mb} MB RAM",
                        color=TEXT_DIM, size=9),
                ], spacing=3),
                ft.Container(expand=True),
                # Settings
                ft.IconButton(
                    icon=ft.icons.SETTINGS_OUTLINED,
                    icon_color=TEXT_DIM, icon_size=20,
                    tooltip="Editar instancia",
                    on_click=lambda e: self._open_edit(),
                ),
                ft.Container(width=8),
                self._play_btn,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        # ── Tab bar ───────────────────────────────────────────────────────────
        tabs_data = [
            ("content", "📦 Content"),
            ("files",   "📁 Files"),
            ("worlds",  "🌍 Worlds"),
            ("logs",    "📄 Logs"),
        ]
        self._tab_btns: dict[str, ft.Container] = {}
        tab_row = ft.Row(spacing=0)
        for tid, tlabel in tabs_data:
            btn = self._make_tab_btn(tid, tlabel)
            self._tab_btns[tid] = btn
            tab_row.controls.append(btn)

        tab_bar = ft.Container(
            bgcolor=CARD_BG,
            border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
            padding=ft.padding.only(left=24, right=24),
            content=tab_row,
        )

        # ── Tab content area ──────────────────────────────────────────────────
        self._tab_area = ft.Container(expand=True, bgcolor=BG)

        self.root = ft.Column(
            spacing=0,
            expand=True,
            controls=[header, tab_bar, self._tab_area],
        )

    def _make_tab_btn(self, tid: str, label: str) -> ft.Container:
        active = tid == self._active_tab
        text   = ft.Text(label, color=GREEN if active else TEXT_SEC, size=10,
                         weight=ft.FontWeight.BOLD if active else ft.FontWeight.NORMAL)
        ind    = ft.Container(
            height=2, border_radius=1,
            bgcolor=GREEN if active else "transparent",
        )
        btn = ft.Container(
            padding=ft.padding.symmetric(horizontal=18, vertical=12),
            on_click=lambda e, t=tid: self._switch_tab(t),
            content=ft.Column([text, ind], spacing=4, tight=True),
        )
        btn._text = text
        btn._ind  = ind
        return btn

    def _switch_tab(self, tid: str):
        self._active_tab = tid
        for t, btn in self._tab_btns.items():
            active = t == tid
            btn._text.color  = GREEN if active else TEXT_SEC
            btn._text.weight = ft.FontWeight.BOLD if active else ft.FontWeight.NORMAL
            btn._ind.bgcolor = GREEN if active else "transparent"
            try: btn.update()
            except Exception: pass
        self._render_tab()

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    def on_show(self):
        self._render_tab()

    def _render_tab(self):
        if self._active_tab == "content":
            self._tab_area.content = _ContentTab(self.page, self.app, self.profile).root
        elif self._active_tab == "files":
            self._tab_area.content = _FilesTab(self.page, self.app, self.profile).root
        elif self._active_tab == "worlds":
            self._tab_area.content = _WorldsTab(self.page, self.app, self.profile).root
        elif self._active_tab == "logs":
            self._tab_area.content = _LogsTab(self.page, self.app, self.profile).root
        try: self._tab_area.update()
        except Exception: pass

    # ── Play ──────────────────────────────────────────────────────────────────
    def _on_play(self, e):
        # Obtener cuenta activa
        try:
            acc = self.app.account_manager.get_active_account()
            if not acc:
                all_acc = self.app.account_manager.get_all_accounts()
                acc = all_acc[0] if all_acc else None
        except Exception:
            acc = None

        if not acc:
            self.app.snack("No hay cuenta seleccionada. Ve a Cuentas.", error=True)
            return

        username = acc.username

        try:
            session      = self.app.auth_service.create_offline_session(username)
            version_data = self.app.version_manager.get_version_data(
                self.profile.version_id)
        except Exception as ex:
            self.app.snack(str(ex), error=True)
            return

        self._play_btn.disabled = True
        try: self._play_btn.update()
        except Exception: pass

        def run():
            try:
                process = self.app.launcher_engine.launch(
                    self.profile, session, version_data,
                    on_output=lambda line: log.info(f"[MC] {line}"))
                self.app.settings.last_profile = self.profile.name
                log.info(f"Minecraft PID={process.pid}")
                self.app.profile_manager.mark_as_used(self.profile.id)
                process.wait()
                rc = process.returncode
                log.info(f"Minecraft cerrado código={rc}")

                def done():
                    self._play_btn.disabled = False
                    try: self._play_btn.update()
                    except Exception: pass
                    if rc != 0:
                        self.app.snack(
                            f"Minecraft cerró con error (código {rc}). Revisa logs.",
                            error=True)
                self.page.run_thread(done)
            except Exception as ex:
                log.error(f"Launch error: {ex}")
                def err():
                    self._play_btn.disabled = False
                    try: self._play_btn.update()
                    except Exception: pass
                    self.app.snack(str(ex), error=True)
                self.page.run_thread(err)

        threading.Thread(target=run, daemon=True).start()
        self.app.snack(f"Iniciando Minecraft {self.profile.version_id} como {username}…")

    # ── Edit ──────────────────────────────────────────────────────────────────
    def _open_edit(self):
        from gui.views.library_view import _CreateInstanceDialog
        def done():
            # Recargar perfil actualizado
            updated = self.app.profile_manager.get_profile(self.profile.id)
            if updated:
                self.profile = updated
            self._build()   # reconstruir con datos actualizados
        _CreateInstanceDialog(self.page, self.app, self.profile, on_done=done)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _read_loader(self) -> str:
        meta_path = os.path.join(self.profile.game_dir, "loader_meta.json")
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


# ══════════════════════════════════════════════════════════════════════════════
# Tab: Content (Mods + Resource Packs + Shaders unificados)
# ══════════════════════════════════════════════════════════════════════════════
class _ContentTab:
    FILTERS = ["All", "Mods", "Resource Packs", "Shaders"]

    def __init__(self, page, app, profile):
        self.page         = page
        self.app          = app
        self.profile      = profile
        self._filter      = "All"
        self._sort        = "name"
        self._search_q    = ""
        self._file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self.page.overlay.append(self._file_picker)
        self._build()

    def _build(self):
        # Barra de filtros
        self._filter_btns: dict[str, ft.Container] = {}
        filter_row = ft.Row(spacing=6)
        for f in self.FILTERS:
            btn = self._make_filter(f)
            self._filter_btns[f] = btn
            filter_row.controls.append(btn)

        # Barra de búsqueda + sort + acciones
        self._search_field = ft.TextField(
            hint_text="Buscar proyectos…",
            hint_style=ft.TextStyle(color=TEXT_DIM),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=20, height=38, width=240,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=6),
            prefix_icon=ft.icons.SEARCH,
            on_change=self._on_search,
        )
        self._sort_dd = ft.Dropdown(
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, width=170, height=38,
            options=[
                ft.dropdown.Option("name",    "Alphabetical"),
                ft.dropdown.Option("status",  "Status"),
                ft.dropdown.Option("version", "Version"),
            ],
            value="name",
            content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
            on_change=self._on_sort,
        )

        toolbar = ft.Container(
            bgcolor=CARD_BG,
            padding=ft.padding.symmetric(horizontal=24, vertical=12),
            border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
            content=ft.Row([
                filter_row,
                ft.Container(expand=True),
                self._search_field,
                ft.Container(width=8),
                self._sort_dd,
                ft.Container(width=12),
                ft.ElevatedButton(
                    "🔍 Browse content",
                    bgcolor=GREEN, color=TEXT_INV,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.padding.symmetric(horizontal=14, vertical=8),
                    ),
                    on_click=self._on_browse,
                ),
                ft.Container(width=8),
                ft.OutlinedButton(
                    "📂 Upload files",
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        side=ft.BorderSide(1, BORDER),
                        color=TEXT_SEC,
                        padding=ft.padding.symmetric(horizontal=14, vertical=8),
                    ),
                    on_click=self._on_upload,
                ),
                ft.Container(width=8),
                ft.OutlinedButton(
                    "⬆ Update all",
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        side=ft.BorderSide(1, BORDER),
                        color=TEXT_SEC,
                        padding=ft.padding.symmetric(horizontal=14, vertical=8),
                    ),
                    on_click=lambda e: self.app.snack("Update all — próximamente"),
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        # Encabezado de columnas
        col_hdr = ft.Container(
            bgcolor=CARD_BG,
            padding=ft.padding.only(left=80, right=24, top=6, bottom=6),
            content=ft.Row([
                ft.Text("Project", color=TEXT_DIM, size=9, expand=True),
                ft.Text("Version", color=TEXT_DIM, size=9, width=160,
                        text_align=ft.TextAlign.CENTER),
                ft.Text("Actions", color=TEXT_DIM, size=9, width=120,
                        text_align=ft.TextAlign.RIGHT),
            ]),
        )

        self._count_lbl = ft.Text("", color=TEXT_DIM, size=9)
        self._empty_lbl = ft.Text("Sin contenido en esta categoría.",
                                   color=TEXT_DIM, size=11, visible=False,
                                   text_align=ft.TextAlign.CENTER)
        self._list_col  = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO, expand=True)

        self.root = ft.Column([
            toolbar,
            col_hdr,
            ft.Container(
                expand=True,
                padding=ft.padding.symmetric(horizontal=16, vertical=12),
                content=ft.Column([
                    ft.Row([self._count_lbl]),
                    ft.Container(height=6),
                    self._empty_lbl,
                    self._list_col,
                ], spacing=0, expand=True),
            ),
        ], spacing=0, expand=True)

        self._refresh()

    # ── Filtros pills ─────────────────────────────────────────────────────────
    def _make_filter(self, label: str) -> ft.Container:
        active = label == self._filter
        txt = ft.Text(label, color=TEXT_PRI if active else TEXT_SEC, size=10,
                      weight=ft.FontWeight.BOLD if active else ft.FontWeight.NORMAL)
        ind = ft.Container(height=2, border_radius=1,
                            bgcolor=GREEN if active else "transparent")
        btn = ft.Container(
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            on_click=lambda e, l=label: self._set_filter(l),
            content=ft.Column([txt, ind], spacing=4, tight=True),
        )
        btn._txt = txt
        btn._ind = ind
        return btn

    def _set_filter(self, label: str):
        self._filter = label
        for l, btn in self._filter_btns.items():
            active = l == label
            btn._txt.color  = TEXT_PRI if active else TEXT_SEC
            btn._txt.weight = ft.FontWeight.BOLD if active else ft.FontWeight.NORMAL
            btn._ind.bgcolor = GREEN if active else "transparent"
            try: btn.update()
            except Exception: pass
        self._refresh()

    def _on_search(self, e):
        self._search_q = e.control.value or ""
        self._refresh()

    def _on_sort(self, e):
        self._sort = e.control.value or "name"
        self._refresh()

    # ── Recolección de items ──────────────────────────────────────────────────
    def _collect_items(self) -> list[dict]:
        """Recolecta mods, resource packs y shaders del perfil."""
        items = []

        # MODS
        if self._filter in ("All", "Mods"):
            mods_dir = os.path.join(self.profile.game_dir, "mods")
            if os.path.isdir(mods_dir):
                for fn in os.listdir(mods_dir):
                    fp = os.path.join(mods_dir, fn)
                    if not os.path.isfile(fp):
                        continue
                    is_enabled = fn.endswith(".jar") and not fn.endswith(".jar.disabled")
                    is_disabled = fn.endswith(".jar.disabled")
                    if not (is_enabled or is_disabled):
                        continue
                    items.append({
                        "type":       "Mods",
                        "filename":   fn,
                        "path":       fp,
                        "folder":     mods_dir,
                        "is_enabled": is_enabled,
                        "size_mb":    round(os.path.getsize(fp) / 1048576, 2),
                        "version":    _parse_version(fn),
                    })

        # RESOURCE PACKS
        if self._filter in ("All", "Resource Packs"):
            rp_dir = os.path.join(self.profile.game_dir, "resourcepacks")
            if os.path.isdir(rp_dir):
                for fn in os.listdir(rp_dir):
                    fp = os.path.join(rp_dir, fn)
                    if not os.path.isfile(fp): continue
                    low = fn.lower()
                    if not (low.endswith(".zip") or low.endswith(".zip.disabled")):
                        continue
                    enabled = not fn.endswith(".disabled")
                    items.append({
                        "type":       "Resource Packs",
                        "filename":   fn,
                        "path":       fp,
                        "folder":     rp_dir,
                        "is_enabled": enabled,
                        "size_mb":    round(os.path.getsize(fp) / 1048576, 2),
                        "version":    _parse_version(fn),
                    })

        # SHADERS
        if self._filter in ("All", "Shaders"):
            sh_dir = os.path.join(self.profile.game_dir, "shaderpacks")
            if os.path.isdir(sh_dir):
                for fn in os.listdir(sh_dir):
                    fp = os.path.join(sh_dir, fn)
                    if not os.path.isfile(fp): continue
                    low = fn.lower()
                    if not (low.endswith(".zip") or low.endswith(".zip.disabled")):
                        continue
                    enabled = not fn.endswith(".disabled")
                    items.append({
                        "type":       "Shaders",
                        "filename":   fn,
                        "path":       fp,
                        "folder":     sh_dir,
                        "is_enabled": enabled,
                        "size_mb":    round(os.path.getsize(fp) / 1048576, 2),
                        "version":    _parse_version(fn),
                    })

        return items

    # ── Refresh lista ─────────────────────────────────────────────────────────
    def _refresh(self):
        items = self._collect_items()

        # Filtrar por búsqueda
        q = self._search_q.strip().lower()
        if q:
            items = [i for i in items
                     if q in i["filename"].lower()]

        # Ordenar
        if self._sort == "name":
            items.sort(key=lambda i: i["filename"].lower())
        elif self._sort == "status":
            items.sort(key=lambda i: (not i["is_enabled"], i["filename"].lower()))
        elif self._sort == "version":
            items.sort(key=lambda i: i["version"].lower())

        self._list_col.controls.clear()
        self._empty_lbl.visible = (len(items) == 0)
        self._count_lbl.value   = f"{len(items)} proyecto{'s' if len(items)!=1 else ''}"

        for item in items:
            self._list_col.controls.append(self._make_row(item))

        try:
            self._list_col.update()
            self._empty_lbl.update()
            self._count_lbl.update()
        except Exception: pass

    # ── Fila de item ──────────────────────────────────────────────────────────
    def _make_row(self, item: dict) -> ft.Container:
        fn      = item["filename"]
        is_en   = item["is_enabled"]
        disp    = re.sub(r'\.(jar|zip)(\.disabled)?$', '', fn, flags=re.IGNORECASE)

        type_badge = ft.Container(
            bgcolor=CARD2_BG, border_radius=4,
            padding=ft.padding.symmetric(horizontal=5, vertical=2),
            content=ft.Text(item["type"], color=TEXT_DIM, size=7),
        )

        return ft.Container(
            bgcolor=INPUT_BG, border_radius=8,
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            on_hover=lambda e: (
                setattr(e.control, "bgcolor",
                        CARD2_BG if e.data=="true" else INPUT_BG)
                or e.control.update()),
            content=ft.Row([
                # Checkbox placeholder (para selección futura)
                ft.Checkbox(value=False,
                            fill_color={"selected": GREEN},
                            check_color=TEXT_INV,
                            width=20),
                ft.Container(width=10),

                # Icono
                _initial_icon(disp, size=40),
                ft.Container(width=14),

                # Nombre + badge de tipo
                ft.Column([
                    ft.Row([
                        ft.Text(disp, color=TEXT_PRI, size=10,
                                weight=ft.FontWeight.BOLD,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                expand=True),
                        type_badge,
                    ], spacing=6),
                    ft.Text(fn, color=TEXT_DIM, size=8, italic=True,
                            overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=2, expand=True),

                # Versión
                ft.Text(item["version"] or "—", color=TEXT_SEC, size=9,
                        width=160, text_align=ft.TextAlign.CENTER),

                # Acciones
                ft.Row([
                    ft.IconButton(
                        icon=(ft.icons.TOGGLE_ON if is_en else ft.icons.TOGGLE_OFF),
                        icon_color=GREEN if is_en else TEXT_DIM,
                        icon_size=22,
                        tooltip="Deshabilitar" if is_en else "Habilitar",
                        on_click=lambda e, i=item: self._toggle(i),
                    ),
                    ft.IconButton(
                        icon=ft.icons.DELETE_OUTLINE,
                        icon_color=ACCENT_RED, icon_size=18,
                        tooltip="Eliminar",
                        on_click=lambda e, i=item: self._delete(i),
                    ),
                ], spacing=0, width=90),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    # ── Acciones ──────────────────────────────────────────────────────────────
    def _toggle(self, item: dict):
        path = item["path"]
        try:
            if item["is_enabled"]:
                os.rename(path, path + ".disabled")
            else:
                new_path = path.removesuffix(".disabled")
                os.rename(path, new_path)
            self._refresh()
        except OSError as ex:
            self.app.snack(str(ex), error=True)

    def _delete(self, item: dict):
        def confirm(e):
            self.page.close(dlg)
            if e.control.text == "Eliminar":
                try:
                    os.remove(item["path"])
                    self._refresh()
                    self.app.snack("Eliminado.")
                except OSError as ex:
                    self.app.snack(str(ex), error=True)

        dlg = ft.AlertDialog(
            modal=True, bgcolor=CARD_BG,
            title=ft.Text("Eliminar", color=TEXT_PRI),
            content=ft.Text(f"¿Eliminar '{item['filename']}'?", color=TEXT_SEC),
            actions=[
                ft.TextButton("Cancelar", on_click=confirm),
                ft.TextButton("Eliminar",
                              style=ft.ButtonStyle(color=ACCENT_RED),
                              on_click=confirm),
            ],
        )
        self.page.open(dlg)

    def _on_upload(self, e):
        self._file_picker.pick_files(
            dialog_title="Seleccionar archivo",
            allowed_extensions=["jar", "zip"],
        )

    def _on_file_picked(self, e: ft.FilePickerResultEvent):
        if not e.files:
            return
        src  = e.files[0].path
        fn   = os.path.basename(src)
        low  = fn.lower()

        # Determinar carpeta destino según tipo de archivo
        if low.endswith(".jar"):
            dest_dir = os.path.join(self.profile.game_dir, "mods")
        else:
            dest_dir = os.path.join(self.profile.game_dir, "resourcepacks")

        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, fn)

        if os.path.exists(dest):
            self.app.snack(f"'{fn}' ya existe.", error=True)
            return
        try:
            import shutil
            shutil.copy2(src, dest)
            self._refresh()
            self.app.snack(f"'{fn}' instalado.")
        except OSError as ex:
            self.app.snack(str(ex), error=True)

    def _on_browse(self, e):
        """Abre el buscador de Modrinth filtrado por la instancia."""
        loader = self._read_loader()
        _BrowseContentDialog(
            self.page, self.app, self.profile,
            content_type=self._filter,
            loader=loader if loader != "vanilla" else None,
            on_install=self._refresh,
        )

    def _read_loader(self) -> str:
        meta_path = os.path.join(self.profile.game_dir, "loader_meta.json")
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


# ══════════════════════════════════════════════════════════════════════════════
# Browse Content Dialog
# ══════════════════════════════════════════════════════════════════════════════
class _BrowseContentDialog:
    """Búsqueda de contenido en Modrinth filtrado por instancia."""

    _TYPE_MAP = {
        "All":            "mod",
        "Mods":           "mod",
        "Resource Packs": "resourcepack",
        "Shaders":        "shader",
    }

    def __init__(self, page, app, profile, content_type, loader, on_install):
        self.page         = page
        self.app          = app
        self.profile      = profile
        self.content_type = content_type
        self.loader       = loader
        self.on_install   = on_install
        self._results     = []
        self._selected_id = None
        self._build()

    def _build(self):
        project_type = self._TYPE_MAP.get(self.content_type, "mod")

        self._search_field = ft.TextField(
            label=f"Buscar {self.content_type.lower()}…",
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, expand=True,
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            on_submit=lambda e: self._do_search(project_type),
        )

        self._status_lbl  = ft.Text(
            f"Busca {self.content_type.lower()} compatibles con "
            f"Minecraft {self.profile.version_id}"
            + (f" + {self.loader}" if self.loader else ""),
            color=TEXT_DIM, size=9,
        )
        self._results_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=380)
        self._install_btn = ft.ElevatedButton(
            "⬇ Instalar seleccionado",
            bgcolor=GREEN, color=TEXT_INV,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            disabled=True, on_click=self._do_install,
        )

        self._dlg = ft.AlertDialog(
            modal=True, bgcolor=CARD_BG,
            title=ft.Text(
                f"Browse {self.content_type}  —  {self.profile.name}",
                color=TEXT_PRI, size=14),
            content=ft.Container(width=720, content=ft.Column([
                ft.Row([
                    self._search_field,
                    ft.Container(width=10),
                    ft.ElevatedButton(
                        "Buscar", bgcolor=CARD2_BG, color=TEXT_PRI,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda e: self._do_search(project_type),
                    ),
                ]),
                self._status_lbl,
                ft.Container(height=8),
                self._results_col,
            ], spacing=8)),
            actions=[
                ft.TextButton("Cerrar",
                              on_click=lambda e: self.page.close(self._dlg)),
                self._install_btn,
            ],
        )
        self.page.open(self._dlg)

    def _do_search(self, project_type: str):
        query = self._search_field.value.strip()
        if not query:
            return
        self._status_lbl.value     = "Buscando…"
        self._results_col.controls.clear()
        self._selected_id          = None
        self._install_btn.disabled = True
        try:
            self._status_lbl.update()
            self._results_col.update()
            self._install_btn.update()
        except Exception: pass

        mc_ver = self.profile.version_id
        loader = self.loader

        def search():
            try:
                results = self.app.modrinth_service.search_mods(
                    query,
                    mc_version=mc_ver,
                    loader=loader if project_type == "mod" else None,
                    project_type=project_type,
                )
                self.page.run_thread(lambda: self._show_results(results))
            except TypeError:
                # Fallback si modrinth_service no acepta project_type
                try:
                    results = self.app.modrinth_service.search_mods(
                        query, mc_version=mc_ver, loader=loader)
                    self.page.run_thread(lambda: self._show_results(results))
                except Exception as err:
                    self.page.run_thread(
                        lambda: self._set_status(f"Error: {err}"))
            except Exception as err:
                self.page.run_thread(lambda: self._set_status(f"Error: {err}"))

        threading.Thread(target=search, daemon=True).start()

    def _show_results(self, results):
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
                            CARD2_BG if e.data=="true" else INPUT_BG)
                    or e.control.update()),
                content=ft.Row([
                    _initial_icon(r.title, size=42),
                    ft.Container(width=14),
                    ft.Column([
                        ft.Text(r.title, color=TEXT_PRI, size=10,
                                weight=ft.FontWeight.BOLD,
                                overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(f"por {author}" if author
                                 else (r.description[:60] + "…"
                                       if len(r.description) > 60
                                       else r.description),
                                color=TEXT_SEC, size=9,
                                overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=2, expand=True),
                    ft.Column([
                        ft.Text(mc_v, color=TEXT_DIM, size=8,
                                text_align=ft.TextAlign.RIGHT),
                        ft.Text(f"⬇ {r.downloads:,}", color=TEXT_DIM, size=8,
                                text_align=ft.TextAlign.RIGHT),
                    ], spacing=2, width=130,
                       horizontal_alignment=ft.CrossAxisAlignment.END),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )
            self._results_col.controls.append(row)

        self._status_lbl.value = f"{len(results)} resultados"
        try:
            self._results_col.update()
            self._status_lbl.update()
        except Exception: pass

    def _select(self, pid: str):
        self._selected_id          = pid
        self._install_btn.disabled = False
        for c in self._results_col.controls:
            c.bgcolor = "#1a2520" if c.data == pid else INPUT_BG
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

        # Determinar carpeta destino según content_type
        type_folder = {
            "mod":          "mods",
            "resourcepack": "resourcepacks",
            "shader":       "shaderpacks",
        }.get(self._TYPE_MAP.get(self.content_type, "mod"), "mods")
        dest_dir = os.path.join(self.profile.game_dir, type_folder)
        os.makedirs(dest_dir, exist_ok=True)

        def download():
            try:
                version = self.app.modrinth_service.get_latest_version(
                    self._selected_id, mc_version=self.profile.version_id,
                    loader=self.loader)
                if not version:
                    self.page.run_thread(lambda: self._set_status(
                        "Sin versión compatible."))
                    return
                self.app.modrinth_service.download_mod_version(version, dest_dir)

                def done():
                    self._status_lbl.value     = f"✓ {proj.title} instalado"
                    self._install_btn.disabled = False
                    try:
                        self._status_lbl.update()
                        self._install_btn.update()
                    except Exception: pass
                    self.on_install()
                    self.app.snack(f"{proj.title} instalado.")
                self.page.run_thread(done)
            except Exception as err:
                self.page.run_thread(
                    lambda: self._set_status(f"Error: {err}"))

        threading.Thread(target=download, daemon=True).start()

    def _set_status(self, msg: str):
        self._status_lbl.value     = msg
        self._install_btn.disabled = False
        try:
            self._status_lbl.update()
            self._install_btn.update()
        except Exception: pass


# ══════════════════════════════════════════════════════════════════════════════
# Tab: Files
# ══════════════════════════════════════════════════════════════════════════════
class _FilesTab:
    def __init__(self, page, app, profile):
        self.page    = page
        self.app     = app
        self.profile = profile
        self._build()

    def _build(self):
        game_dir = self.profile.game_dir

        def folder_row(name: str, path: str) -> ft.Container:
            exists = os.path.isdir(path)
            size   = self._folder_size(path) if exists else 0
            return ft.Container(
                bgcolor=INPUT_BG, border_radius=8,
                padding=ft.padding.symmetric(horizontal=16, vertical=12),
                content=ft.Row([
                    ft.Icon(ft.icons.FOLDER_ROUNDED,
                            color=GREEN if exists else TEXT_DIM, size=20),
                    ft.Container(width=14),
                    ft.Column([
                        ft.Text(name, color=TEXT_PRI, size=10,
                                weight=ft.FontWeight.BOLD),
                        ft.Text(path, color=TEXT_DIM, size=8,
                                overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=2, expand=True),
                    ft.Text(f"{size:.1f} MB" if exists else "Vacía",
                            color=TEXT_SEC, size=9),
                    ft.Container(width=12),
                    ft.OutlinedButton(
                        "Abrir",
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=6),
                            side=ft.BorderSide(1, BORDER), color=TEXT_SEC,
                            padding=ft.padding.symmetric(horizontal=12, vertical=6),
                        ),
                        on_click=lambda e, p=path: self._open_folder(p),
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )

        folders = [
            ("Mods",           os.path.join(game_dir, "mods")),
            ("Resource Packs", os.path.join(game_dir, "resourcepacks")),
            ("Shader Packs",   os.path.join(game_dir, "shaderpacks")),
            ("Saves / Worlds", os.path.join(game_dir, "saves")),
            ("Config",         os.path.join(game_dir, "config")),
            ("Screenshots",    os.path.join(game_dir, "screenshots")),
        ]

        rows = [folder_row(name, path) for name, path in folders]

        self.root = ft.Container(
            expand=True,
            padding=ft.padding.all(28),
            content=ft.Column([
                ft.Text("Archivos", color=TEXT_PRI, size=16,
                        weight=ft.FontWeight.BOLD),
                ft.Text("Carpetas de la instancia", color=TEXT_DIM, size=9),
                ft.Container(height=16),
                ft.Column(rows, spacing=8, scroll=ft.ScrollMode.AUTO, expand=True),
            ], spacing=0, expand=True),
        )

    @staticmethod
    def _folder_size(path: str) -> float:
        total = 0
        for dirpath, _, filenames in os.walk(path):
            for fn in filenames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, fn))
                except OSError:
                    pass
        return total / 1048576

    @staticmethod
    def _open_folder(path: str):
        os.makedirs(path, exist_ok=True)
        import subprocess, sys
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])


# ══════════════════════════════════════════════════════════════════════════════
# Tab: Worlds
# ══════════════════════════════════════════════════════════════════════════════
class _WorldsTab:
    def __init__(self, page, app, profile):
        self.page    = page
        self.app     = app
        self.profile = profile
        self._build()

    def _build(self):
        saves_dir = os.path.join(self.profile.game_dir, "saves")
        worlds    = []
        if os.path.isdir(saves_dir):
            worlds = [d for d in os.listdir(saves_dir)
                      if os.path.isdir(os.path.join(saves_dir, d))]

        if worlds:
            rows = []
            for w in sorted(worlds):
                rows.append(ft.Container(
                    bgcolor=INPUT_BG, border_radius=8,
                    padding=ft.padding.symmetric(horizontal=16, vertical=12),
                    content=ft.Row([
                        ft.Text("🌍", size=22),
                        ft.Container(width=14),
                        ft.Text(w, color=TEXT_PRI, size=11,
                                weight=ft.FontWeight.BOLD, expand=True),
                    ]),
                ))
            content = ft.Column(rows, spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
        else:
            content = ft.Container(
                expand=True, alignment=ft.alignment.center,
                content=ft.Column([
                    ft.Text("🌍", size=48, text_align=ft.TextAlign.CENTER),
                    ft.Container(height=8),
                    ft.Text("Sin mundos guardados", color=TEXT_SEC, size=14,
                            text_align=ft.TextAlign.CENTER, weight=ft.FontWeight.BOLD),
                    ft.Text("Los mundos aparecerán aquí después de jugar.",
                            color=TEXT_DIM, size=10, text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            )

        self.root = ft.Container(
            expand=True, padding=ft.padding.all(28),
            content=ft.Column([
                ft.Text("Mundos", color=TEXT_PRI, size=16,
                        weight=ft.FontWeight.BOLD),
                ft.Text(f"{len(worlds)} mundo{'s' if len(worlds) != 1 else ''} guardado{'s' if len(worlds) != 1 else ''}",
                        color=TEXT_DIM, size=9),
                ft.Container(height=16),
                content,
            ], spacing=0, expand=True),
        )


# ══════════════════════════════════════════════════════════════════════════════
# Tab: Logs (placeholder)
# ══════════════════════════════════════════════════════════════════════════════
class _LogsTab:
    def __init__(self, page, app, profile):
        self.page    = page
        self.app     = app
        self.profile = profile

        self.root = ft.Container(
            expand=True, padding=ft.padding.all(28),
            content=ft.Column([
                ft.Text("Logs", color=TEXT_PRI, size=16,
                        weight=ft.FontWeight.BOLD),
                ft.Text("Registros del juego en tiempo real",
                        color=TEXT_DIM, size=9),
                ft.Container(height=16),
                ft.Container(
                    expand=True,
                    bgcolor=INPUT_BG, border_radius=8,
                    padding=ft.padding.all(16),
                    content=ft.Text(
                        "Los logs aparecerán aquí durante la ejecución del juego.",
                        color=TEXT_DIM, size=10,
                    ),
                ),
            ], spacing=0, expand=True),
        )