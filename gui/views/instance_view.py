# -*- coding: utf-8 -*-
"""
gui/views/instance_view.py
Tabs: Content | Files | Worlds | Logs
"""
import os
import re
import json
import hashlib
import threading
import urllib.request
import urllib.error
import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER, BORDER_BRIGHT,
    GREEN, GREEN_DIM, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV, ACCENT_RED,
)
from utils.install_detector import build_installed_set, is_installed_in
from utils.logger import get_logger
from utils.icon_cache import (
    get as cache_get, set as cache_set, has as cache_has,
    get_author as cache_get_author, set_author as cache_set_author,
)
log = get_logger()

_PALETTE = [
    "#2d6a4f", "#1e3a5f", "#5c2a2a", "#3a3a1e",
    "#2a1e5c", "#1e5c4a", "#4a3a1e", "#5c3a4a",
]

LOADER_ICONS = {
    "vanilla":  "Game",
    "fabric":   "Fabric",
    "neoforge": "NeoForge",
    "forge":    "Forge",
    "quilt":    "Quilt",
}


def _icon(url: str, title: str, size: int = 40) -> ft.Control:
    fallback = ft.Container(
        width=size, height=size, border_radius=8,
        bgcolor=CARD2_BG, alignment=ft.alignment.center,
        content=ft.Icon(ft.icons.EXTENSION_ROUNDED,
                        color=TEXT_DIM, size=int(size * 0.50)),
    )
    if not url:
        return fallback
    return ft.Image(
        src=url,
        width=size, height=size,
        border_radius=8,
        fit=ft.ImageFit.COVER,
        error_content=fallback,
    )


def _parse_version(filename):
    name = re.sub(r'\.(jar|zip|disabled)$', '', filename, flags=re.IGNORECASE)
    for part in reversed(name.split('-')):
        if re.match(r'^\d+\.\d+', part):
            return part
    return ""


def _sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# =============================================================================
class InstanceView:

    def __init__(self, page, app, profile):
        self.page    = page
        self.app     = app
        self.profile = profile
        self._active_tab = "content"
        self._build()

    def _build(self):
        loader = self._read_loader()
        icon_label = LOADER_ICONS.get(loader, "Game")

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
                    ft.Text(self.profile.name, color=TEXT_PRI, size=20,
                            weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.Text(loader.capitalize(), color=GREEN, size=11,
                                weight=ft.FontWeight.W_500),
                        ft.Text("  •  ", color=TEXT_DIM, size=11),
                        ft.Text(f"Minecraft {self.profile.version_id}",
                                color=TEXT_SEC, size=11),
                        ft.Text("  •  ", color=TEXT_DIM, size=11),
                        ft.Text("Never played", color=TEXT_DIM, size=11),
                    ], spacing=0),
                ], spacing=6, expand=True),
                ft.Container(expand=True),
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

        tabs_data = [
            ("content", "Content", ft.icons.EXTENSION_ROUNDED),
            ("files",   "Files",   ft.icons.FOLDER_ROUNDED),
            ("worlds",  "Worlds",  ft.icons.PUBLIC_ROUNDED),
            ("logs",    "Logs",    ft.icons.TERMINAL_ROUNDED),
        ]
        self._tab_btns = {}
        tab_row = ft.Row(spacing=6, controls=[
            ft.IconButton(
                icon=ft.icons.ARROW_BACK_IOS_NEW_ROUNDED,
                icon_color=TEXT_DIM, icon_size=16,
                tooltip="Volver a Biblioteca",
                on_click=lambda e: self.app._show_view("library"),
            ),
            ft.Container(width=4),
        ])
        for tid, tlabel, ticon in tabs_data:
            btn = self._make_tab_btn(tid, tlabel, ticon)
            self._tab_btns[tid] = btn
            tab_row.controls.append(btn)

        tab_bar = ft.Container(
            bgcolor=CARD_BG,
            border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
            padding=ft.padding.symmetric(horizontal=20, vertical=10),
            content=tab_row,
        )

        self._tab_area = ft.Container(expand=True, bgcolor=BG)

        self.root = ft.Column(
            spacing=0, expand=True,
            controls=[header, tab_bar, self._tab_area],
        )

    def _make_tab_btn(self, tid, label, icon):
        active = tid == self._active_tab
        btn = ft.Container(
            bgcolor=GREEN if active else "transparent",
            border_radius=20,
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
            animate=ft.animation.Animation(150, ft.AnimationCurve.EASE_OUT),
            on_click=lambda e, t=tid: self._switch_tab(t),
            content=ft.Row([
                ft.Icon(icon, size=14,
                        color=TEXT_INV if active else TEXT_SEC),
                ft.Container(width=6),
                ft.Text(label,
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
    def _switch_tab(self, tid):
        self._active_tab = tid
        tabs_data = [
            ("content", "Content", ft.icons.EXTENSION_ROUNDED),
            ("files",   "Files",   ft.icons.FOLDER_ROUNDED),
            ("worlds",  "Worlds",  ft.icons.PUBLIC_ROUNDED),
            ("logs",    "Logs",    ft.icons.TERMINAL_ROUNDED),
        ]
        for (t, label, icon), btn in zip(tabs_data, self._tab_btns.values()):
            active = t == tid
            btn.bgcolor = GREEN if active else "transparent"
            row: ft.Row = btn.content
            row.controls[0].color = TEXT_INV if active else TEXT_SEC
            row.controls[2].color = TEXT_INV if active else TEXT_SEC
            try: btn.update()
            except Exception: pass
        self._render_tab()

    def on_show(self):
        self._render_tab()

    def _render_tab(self):
        if self._active_tab == "content":
            if not hasattr(self, "_content_tab_obj"):
                self._content_tab_obj = _ContentTab(self.page, self.app, self.profile)
            self._tab_area.content = self._content_tab_obj.root
        elif self._active_tab == "files":
            if not hasattr(self, "_files_tab_obj"):
                self._files_tab_obj = _FilesTab(self.page, self.app, self.profile)
            self._tab_area.content = self._files_tab_obj.root
        elif self._active_tab == "worlds":
            if not hasattr(self, "_worlds_tab_obj"):
                self._worlds_tab_obj = _WorldsTab(self.page, self.app, self.profile)
            self._tab_area.content = self._worlds_tab_obj.root
        elif self._active_tab == "logs":
            if not hasattr(self, "_logs_tab_obj"):
                self._logs_tab_obj = _LogsTab(self.page, self.app, self.profile)
            self._tab_area.content = self._logs_tab_obj.root
        try: self._tab_area.update()
        except Exception: pass

    def _on_play(self, e):
        try:
            acc = self.app.account_manager.get_active_account()
            if not acc:
                all_acc = self.app.account_manager.get_all_accounts()
                acc = all_acc[0] if all_acc else None
        except Exception:
            acc = None

        if not acc:
            self.app.snack("No hay cuenta seleccionada.", error=True)
            return

        username = acc.username
        try:
            session      = self.app.auth_service.create_offline_session(username)
            version_data = self.app.version_manager.get_version_data(self.profile.version_id)
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
                self.app.profile_manager.mark_as_used(self.profile.id)
                process.wait()
                rc = process.returncode

                def done():
                    self._play_btn.disabled = False
                    try: self._play_btn.update()
                    except Exception: pass
                    if rc != 0:
                        self.app.snack(f"Minecraft cerro con error (codigo {rc}).", error=True)
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
        self.app.snack(f"Iniciando Minecraft {self.profile.version_id} como {username}...")

    def _open_edit(self):
        def done(updated_profile=None):
            if updated_profile:
                self.profile = updated_profile
            elif True:
                updated = self.app.profile_manager.get_profile(self.profile.id)
                if updated:
                    self.profile = updated
            self._build()
            try: self.root.update()
            except Exception: pass
        _InstanceSettingsDialog(self.page, self.app, self.profile, on_done=done)



    def _read_loader(self):
        meta_path = os.path.join(self.profile.game_dir, "loader_meta.json")
        if os.path.isfile(meta_path):
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                entries = meta if isinstance(meta, list) else [meta]
                if entries:
                    return entries[0].get("loader_type") or entries[0].get("loader", "vanilla")
            except Exception:
                pass
        return "vanilla"


# =============================================================================
# Tab: Content
# =============================================================================
class _ContentTab:
    FILTERS = ["All", "Mods", "Resource Packs", "Shaders"]

    def __init__(self, page, app, profile):
        self.page      = page
        self.app       = app
        self.profile   = profile
        self._filter   = "All"
        self._sort     = "name"
        self._search_q = ""
        self._alive    = True

        self._file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self.page.overlay.append(self._file_picker)
        self.page.update()

        self._icon_cache:   dict[str, str | None]  = {}
        self._author_cache: dict[str, dict | None] = {}
        self._pid_cache:    dict[str, str]          = {}
        self._fetch_lock = threading.Lock()
        self._update_cache: dict[str, str | None] = {}  # path -> latest_version_id or None
        self._selected_paths: set[str] = set()

        # Versión del refresh — cancela redraws de fetches anteriores
        self._refresh_token = 0

        self._build()

    def _build(self):
        self._filter_chips = {}
        chip_row = ft.Row(spacing=4)
        for f in self.FILTERS:
            chip = self._make_chip(f)
            self._filter_chips[f] = chip
            chip_row.controls.append(chip)

        total = len(self._collect_items())
        self._search_field = ft.TextField(
            hint_text=f"Search {total} projects...",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=12),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, height=44, expand=True,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=10),
            prefix_icon=ft.icons.SEARCH_ROUNDED,
            text_size=12,
            on_change=self._on_search,
        )

        self._sort_dd = ft.Dropdown(
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, width=180, height=36,
            options=[
                ft.dropdown.Option("name",    "Oldest first"),
                ft.dropdown.Option("status",  "Status"),
                ft.dropdown.Option("version", "Version"),
            ],
            value="name",
            content_padding=ft.padding.symmetric(horizontal=12, vertical=6),
            text_style=ft.TextStyle(size=11),
            on_change=self._on_sort,
        )

        toolbar = ft.Container(
            bgcolor=CARD_BG,
            padding=ft.padding.symmetric(horizontal=20, vertical=14),
            border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
            content=ft.Column([
                ft.Row([
                    self._search_field,
                    ft.Container(width=8),
                    ft.ElevatedButton(
                        "Browse content",
                        icon=ft.icons.TRAVEL_EXPLORE_ROUNDED,
                        bgcolor=GREEN, color=TEXT_INV,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.padding.symmetric(horizontal=16, vertical=10),
                        ),
                        on_click=self._on_browse,
                    ),
                    ft.Container(width=6),
                    ft.OutlinedButton(
                        "Upload files",
                        icon=ft.icons.UPLOAD_FILE_ROUNDED,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            side=ft.BorderSide(1, BORDER), color=TEXT_SEC,
                            padding=ft.padding.symmetric(horizontal=14, vertical=10),
                        ),
                        on_click=self._on_upload,
                    ),
                ]),
                ft.Container(height=10),
                ft.Row([
                    chip_row,
                    ft.Container(expand=True),
                    self._sort_dd,
                    ft.Container(width=4),
                    ft.TextButton(
                        "Update all",
                        icon=ft.icons.DOWNLOAD_ROUNDED,
                        style=ft.ButtonStyle(
                            color=GREEN,
                            padding=ft.padding.symmetric(horizontal=8),
                        ),
                        on_click=lambda e: self.app.snack("Update all - proximamente"),
                    ),
                    ft.TextButton(
                        "Refresh",
                        icon=ft.icons.REFRESH_ROUNDED,
                        style=ft.ButtonStyle(
                            color=TEXT_SEC,
                            padding=ft.padding.symmetric(horizontal=8),
                        ),
                        on_click=lambda e: self._refresh(),
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=0),
        )


        self._count_lbl = ft.Text("", color=TEXT_DIM, size=9)
        self._empty_lbl = ft.Container(
            visible=False, expand=True, alignment=ft.alignment.center,
            content=ft.Column([
                ft.Icon(ft.icons.INBOX_ROUNDED, size=48, color=TEXT_DIM),
                ft.Container(height=8),
                ft.Text("No content in this instance", color=TEXT_SEC, size=13,
                        weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Text("Click 'Browse content' to add mods, shaders or resource packs.",
                        color=TEXT_DIM, size=10, text_align=ft.TextAlign.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
        )
        self._list_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

        # ── Bulk action bar (flotante) ────────────────────────────────────────
        self._bulk_count_lbl = ft.Text("0 selected", color=TEXT_PRI, size=12,
                                       weight=ft.FontWeight.W_600)
        self._bulk_bar = ft.Container(
            visible=False,
            bgcolor=CARD2_BG,
            border=ft.border.all(1, BORDER),
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=20, vertical=12),
            shadow=ft.BoxShadow(blur_radius=24, color="#66000000",
                                offset=ft.Offset(0, 6)),
            content=ft.Row([
                ft.Icon(ft.icons.CHECK_BOX_ROUNDED, size=16, color=GREEN),
                ft.Container(width=10),
                self._bulk_count_lbl,
                ft.Container(expand=True),
                ft.TextButton(
                    "Deselect all",
                    style=ft.ButtonStyle(color=TEXT_DIM),
                    on_click=lambda e: self._deselect_all(),
                ),
                ft.Container(width=4),
                ft.OutlinedButton(
                    "Enable",
                    icon=ft.icons.TOGGLE_ON_ROUNDED,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        side=ft.BorderSide(1, GREEN), color=GREEN,
                        padding=ft.padding.symmetric(horizontal=14, vertical=8),
                    ),
                    on_click=self._bulk_enable,
                ),
                ft.Container(width=6),
                ft.OutlinedButton(
                    "Disable",
                    icon=ft.icons.TOGGLE_OFF_ROUNDED,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        side=ft.BorderSide(1, BORDER), color=TEXT_SEC,
                        padding=ft.padding.symmetric(horizontal=14, vertical=8),
                    ),
                    on_click=self._bulk_disable,
                ),
                ft.Container(width=6),
                ft.ElevatedButton(
                    "Delete",
                    icon=ft.icons.DELETE_OUTLINE_ROUNDED,
                    bgcolor=ACCENT_RED, color="#ffffff",
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.padding.symmetric(horizontal=14, vertical=8),
                    ),
                    on_click=self._bulk_delete,
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        self.root = ft.Column([
            toolbar,
            ft.Container(
                expand=True,
                content=ft.Stack([
                    self._list_col,
                    self._empty_lbl,
                    ft.Container(
                        alignment=ft.alignment.bottom_center,
                        padding=ft.padding.only(bottom=20),
                        content=self._bulk_bar,
                    ),
                ]),
            ),
        ], spacing=0, expand=True)

    def _make_filter_btn(self, label):
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
    
    def _make_chip(self, label):
        active = label == self._filter
        chip = ft.Container(
            bgcolor=GREEN if active else "transparent",
            border=ft.border.all(1, GREEN if active else BORDER),
            border_radius=20,
            padding=ft.padding.symmetric(horizontal=14, vertical=6),
            animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
            on_click=lambda e, l=label: self._set_filter(l),
            content=ft.Text(label, color=TEXT_INV if active else TEXT_SEC,
                            size=10, weight=ft.FontWeight.W_600),
        )
        chip.on_hover = lambda e, c=chip, l=label: (
            None if l == self._filter else (
                setattr(c, "bgcolor", INPUT_BG if e.data == "true" else "transparent")
                or c.update()
            )
        )
        return chip
    
    def _set_filter(self, label):
        self._filter = label
        for l, chip in self._filter_chips.items():
            active = l == label
            chip.bgcolor = GREEN if active else "transparent"
            chip.border  = ft.border.all(1, GREEN if active else BORDER)
            chip.content.color = TEXT_INV if active else TEXT_SEC
            try: chip.update()
            except Exception: pass
        self._refresh()

    def _on_search(self, e):
        self._search_q = e.control.value or ""
        self._refresh()

    def _on_sort(self, e):
        self._sort = e.control.value or "name"
        self._refresh()

    def _collect_items(self):
        items = []
        if self._filter in ("All", "Mods"):
            d = os.path.join(self.profile.game_dir, "mods")
            if os.path.isdir(d):
                for fn in os.listdir(d):
                    fp = os.path.join(d, fn)
                    if not os.path.isfile(fp): continue
                    enabled  = fn.endswith(".jar") and not fn.endswith(".jar.disabled")
                    disabled = fn.endswith(".jar.disabled")
                    if not (enabled or disabled): continue
                    items.append({"type": "Mods", "filename": fn, "path": fp,
                                  "is_enabled": enabled, "version": _parse_version(fn)})

        if self._filter in ("All", "Resource Packs"):
            d = os.path.join(self.profile.game_dir, "resourcepacks")
            if os.path.isdir(d):
                for fn in os.listdir(d):
                    fp = os.path.join(d, fn)
                    if not os.path.isfile(fp): continue
                    low = fn.lower()
                    if not (low.endswith(".zip") or low.endswith(".zip.disabled")): continue
                    items.append({"type": "Resource Packs", "filename": fn, "path": fp,
                                  "is_enabled": not fn.endswith(".disabled"),
                                  "version": _parse_version(fn)})

        if self._filter in ("All", "Shaders"):
            d = os.path.join(self.profile.game_dir, "shaderpacks")
            if os.path.isdir(d):
                for fn in os.listdir(d):
                    fp = os.path.join(d, fn)
                    if not os.path.isfile(fp): continue
                    low = fn.lower()
                    if not (low.endswith(".zip") or low.endswith(".zip.disabled")): continue
                    items.append({"type": "Shaders", "filename": fn, "path": fp,
                                  "is_enabled": not fn.endswith(".disabled"),
                                  "version": _parse_version(fn)})
        return items

    def _sorted(self, items):
        q = self._search_q.strip().lower()
        if q:
            items = [i for i in items if q in i["filename"].lower()]
        if self._sort == "name":
            items.sort(key=lambda i: i["filename"].lower())
        elif self._sort == "status":
            items.sort(key=lambda i: (not i["is_enabled"], i["filename"].lower()))
        elif self._sort == "version":
            items.sort(key=lambda i: i["version"].lower())
        return items

    def _refresh(self):
        self._refresh_token += 1
        token = self._refresh_token

        # Limpiar lista inmediatamente (no bloquea)
        self._list_col.controls.clear()
        self._empty_lbl.visible = False
        try:
            self._list_col.update()
            self._empty_lbl.update()
        except Exception:
            pass

        # Todo lo pesado va al background
        def background_work():
            if token != self._refresh_token:
                return
            items = self._sorted(self._collect_items())
            if token != self._refresh_token:
                return
            self.page.run_thread(lambda: _draw(items))

        def _draw(items):
            if token != self._refresh_token:
                return
            self._list_col.controls.clear()
            self._empty_lbl.visible = (len(items) == 0)
            self._search_field.hint_text = f"Search {len(items)} projects..."
            for item in items:
                self._list_col.controls.append(self._make_row(item))
            try:
                self._list_col.update()
                self._empty_lbl.update()
                self._search_field.update()
            except Exception:
                pass

            with self._fetch_lock:
                missing_icons = [i for i in items if i["path"] not in self._icon_cache]
            if missing_icons:
                threading.Thread(
                    target=self._fetch_icons_batch,
                    args=(missing_icons, token), daemon=True
                ).start()
            else:
                self._launch_author_fetch(items, token)

            # Lanzar update checker en paralelo
            threading.Thread(
                target=self._check_updates_batch,
                args=(items, token), daemon=True
            ).start()

    def _on_check(self, path: str, checked: bool):
        if checked:
            self._selected_paths.add(path)
        else:
            self._selected_paths.discard(path)
        self._update_bulk_bar()

    def _update_bulk_bar(self):
        count = len(self._selected_paths)
        if count == 0:
            self._bulk_bar.visible = False
        else:
            self._bulk_count_lbl.value = f"{count} selected"
            self._bulk_bar.visible = True
        try:
            self._bulk_bar.update()
        except Exception:
            pass

    def _bulk_enable(self, e):
        for path in list(self._selected_paths):
            if path.endswith(".disabled"):
                new_path = path.removesuffix(".disabled")
                try:
                    os.rename(path, new_path)
                    with self._fetch_lock:
                        for cache in (self._icon_cache, self._author_cache,
                                    self._pid_cache, self._update_cache):
                            if path in cache:
                                cache[new_path] = cache.pop(path)
                except OSError:
                    pass
        self._selected_paths.clear()
        self._refresh()

    def _bulk_disable(self, e):
        for path in list(self._selected_paths):
            if not path.endswith(".disabled"):
                new_path = path + ".disabled"
                try:
                    os.rename(path, new_path)
                    with self._fetch_lock:
                        for cache in (self._icon_cache, self._author_cache,
                                    self._pid_cache, self._update_cache):
                            if path in cache:
                                cache[new_path] = cache.pop(path)
                except OSError:
                    pass
        self._selected_paths.clear()
        self._refresh()

    def _bulk_delete(self, e):
        count = len(self._selected_paths)
        paths = list(self._selected_paths)

        def confirm(e):
            self.page.close(dlg)
            if e.control.text != "Delete":
                return
            for path in paths:
                try:
                    os.remove(path)
                    with self._fetch_lock:
                        for cache in (self._icon_cache, self._author_cache,
                                    self._pid_cache, self._update_cache):
                            cache.pop(path, None)
                except OSError:
                    pass
            self._selected_paths.clear()
            self._refresh()
            self.app.snack(f"{count} item(s) deleted.")

        dlg = ft.AlertDialog(
            modal=True, bgcolor=CARD_BG,
            title=ft.Text("Delete selected?", color=TEXT_PRI,
                        weight=ft.FontWeight.BOLD),
            content=ft.Text(
                f"This will permanently delete {count} item(s). Cannot be undone.",
                color=TEXT_SEC, size=12),
            actions=[
                ft.TextButton("Cancel", on_click=confirm),
                ft.ElevatedButton(
                    "Delete",
                    bgcolor=ACCENT_RED, color="#ffffff",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=confirm,
                ),
            ],
        )
        self.page.open(dlg)

    def _install_update(self, path: str, pid: str, latest_ver: str):
        loader  = self._read_loader()
        mc_ver  = self.profile.version_id
        dest_dir = os.path.dirname(path)

        def do():
            try:
                version = self.app.modrinth_service.get_latest_version(
                    pid, mc_version=mc_ver, loader=loader)
                if not version:
                    self.page.run_thread(lambda: self.app.snack(
                        "No compatible version found.", error=True))
                    return
                # Borrar el archivo viejo
                try: os.remove(path)
                except OSError: pass
                with self._fetch_lock:
                    for cache in (self._icon_cache, self._author_cache,
                                self._pid_cache, self._update_cache):
                        cache.pop(path, None)
                self.app.modrinth_service.download_mod_version(version, dest_dir)
                self.page.run_thread(lambda: (
                    self.app.snack(f"Updated to {latest_ver} ✓"),
                    self._refresh(),
                ))
            except Exception as ex:
                self.page.run_thread(
                    lambda: self.app.snack(str(ex), error=True))

        threading.Thread(target=do, daemon=True).start()
        self.app.snack(f"Installing update {latest_ver}…")

    @staticmethod
    def _open_folder(path: str):
        import subprocess, sys
        os.makedirs(path, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _deselect_all(self):
        self._selected_paths.clear()
        self._update_bulk_bar()
        token = self._refresh_token
        try:
            items = self._sorted(self._collect_items())
            self._list_col.controls.clear()
            for item in items:
                self._list_col.controls.append(self._make_row(item))
            self._list_col.update()
        except Exception:
            pass

    def _draw_list(self, items, token=None):
        if token is not None and token != self._refresh_token:
            return
        self._list_col.controls.clear()
        self._empty_lbl.visible = len(items) == 0
        self._search_field.hint_text = f"Search {len(items)} projects..."
        for item in items:
            self._list_col.controls.append(self._make_row(item))
        try:
            self._list_col.update()
            self._empty_lbl.update()
            self._search_field.update()
        except Exception:
            pass

        # Fetch de iconos solo si hay items
        if items:
            with self._fetch_lock:
                missing = [i for i in items if i["path"] not in self._icon_cache]
            if missing:
                threading.Thread(
                    target=self._fetch_icons_batch,
                    args=(missing, token or self._refresh_token),
                    daemon=True
                ).start()
            else:
                self._launch_author_fetch(
                    items, token or self._refresh_token)

    def _redraw_list(self, token: int):
        """Llamado desde hilo de background via page.run_thread. Ignora tokens viejos."""
        if not self._alive or token != self._refresh_token:
            return
        try:
            items = self._sorted(self._collect_items())
            self._list_col.controls.clear()
            for item in items:
                self._list_col.controls.append(self._make_row(item))
            self._list_col.update()
        except Exception:
            pass

    def _skeleton_card(self) -> ft.Container:
        def _bar(w, h=10, op=0.10):
            return ft.Container(
                width=w, height=h, border_radius=4,
                bgcolor="#ffffff", opacity=op,
            )
        return ft.Container(
            bgcolor=CARD_BG,
            border=ft.border.all(1, BORDER),
            border_radius=14,
            padding=ft.padding.all(20),
            content=ft.Row([
                ft.Container(
                    width=20, bgcolor="transparent"),
                ft.Container(width=14),
                ft.Container(
                    width=72, height=72, border_radius=12,
                    bgcolor="#ffffff", opacity=0.07),
                ft.Container(width=20),
                ft.Column([
                    _bar(200, 14, 0.16),
                    ft.Container(height=6),
                    _bar(120, 10),
                    ft.Container(height=10),
                    _bar(360, 9),
                    ft.Container(height=10),
                    ft.Row([
                        _bar(70, 18), ft.Container(width=6),
                        _bar(80, 18), ft.Container(width=6),
                        _bar(60, 18),
                    ]),
                ], spacing=4, expand=True),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    def _launch_author_fetch(self, items, token: int):
        with self._fetch_lock:
            need = [
                (i["path"], self._pid_cache[i["path"]])
                for i in items
                if i["path"] not in self._author_cache
                and i["path"] in self._pid_cache
            ]
            for path, _ in need:
                self._author_cache[path] = None

        if need:
            threading.Thread(
                target=self._fetch_authors_for_projects,
                args=(need, token), daemon=True
            ).start()

    # ── Fetch iconos ──────────────────────────────────────────────────────────
    def _fetch_icons_batch(self, items, token: int):
        if not self._alive:
            return
        try:
            from config.constants import MODRINTH_API_BASE_URL, HTTP_TIMEOUT_SECONDS, USER_AGENT
            base = MODRINTH_API_BASE_URL; timeout = HTTP_TIMEOUT_SECONDS; ua = USER_AGENT
        except Exception:
            base = "https://api.modrinth.com/v2"; timeout = 15; ua = "PyLauncher/1.0"

        def post(url, payload):
            data = json.dumps(payload).encode()
            req  = urllib.request.Request(url, data=data, headers={
                "User-Agent": ua, "Accept": "application/json",
                "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())

        def get(url):
            req = urllib.request.Request(url, headers={
                "User-Agent": ua, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())

        from concurrent.futures import ThreadPoolExecutor

        # 1. SHA1 en paralelo
        def sha1_of(item):
            try:    return item["path"], _sha1(item["path"])
            except: return item["path"], None

        path_to_sha1 = {}
        with ThreadPoolExecutor(max_workers=8) as ex:
            for path, sha1 in ex.map(sha1_of, items):
                if sha1:
                    path_to_sha1[path] = sha1

        if not self._alive or token != self._refresh_token:
            return

        # 2. Hits del caché de disco
        hits     = {}
        need_api = {}
        for path, sha1 in path_to_sha1.items():
            cached = cache_get(sha1)
            if cached is not None:
                hits[path] = cached.get("icon_url")
                pid = cached.get("project_id", "")
                if pid:
                    with self._fetch_lock:
                        self._pid_cache[path] = pid
            else:
                need_api[sha1] = path

        if hits:
            with self._fetch_lock:
                self._icon_cache.update(hits)
            if self._alive and token == self._refresh_token:
                self.page.run_thread(lambda t=token: self._redraw_list(t))

        self._launch_author_fetch_paths(list(hits.keys()), token)

        if not need_api or not self._alive or token != self._refresh_token:
            return

        # 3. Batch hashes → project_ids
        try:
            ver_results = post(f"{base}/version_files", {
                "hashes": list(need_api.keys()), "algorithm": "sha1"})
        except Exception as ex:
            log.debug(f"[ICON] version_files: {ex}")
            for sha1 in need_api:
                cache_set(sha1, None)
            return

        sha1_to_pid = {}
        project_ids = {}
        for sha1, vdata in ver_results.items():
            pid  = vdata.get("project_id", "")
            path = need_api.get(sha1)
            if pid and path:
                sha1_to_pid[sha1] = pid
                project_ids[pid]  = path

        for sha1 in need_api:
            if sha1 not in sha1_to_pid:
                cache_set(sha1, None)
                with self._fetch_lock:
                    self._icon_cache[need_api[sha1]] = None

        if not project_ids or not self._alive or token != self._refresh_token:
            return

        # 4. Batch proyectos → icon_url
        try:
            projects = get(f"{base}/projects?ids=" +
                           urllib.request.quote(json.dumps(list(project_ids.keys()))))
        except Exception as ex:
            log.debug(f"[ICON] projects: {ex}")
            return

        pid_to_icon = {p.get("id", ""): p.get("icon_url") or None for p in projects}
        found_any   = False

        with self._fetch_lock:
            for sha1, pid in sha1_to_pid.items():
                path     = need_api[sha1]
                icon_url = pid_to_icon.get(pid)
                self._icon_cache[path] = icon_url
                self._pid_cache[path]  = pid
                cache_set(sha1, icon_url, pid)
                if icon_url:
                    found_any = True

        if found_any and self._alive and token == self._refresh_token:
            self.page.run_thread(lambda t=token: self._redraw_list(t))

        self._launch_author_fetch_paths([need_api[s] for s in sha1_to_pid], token)

    def _launch_author_fetch_paths(self, paths, token: int):
        with self._fetch_lock:
            need = [
                (path, self._pid_cache[path])
                for path in paths
                if path in self._pid_cache
                and path not in self._author_cache
            ]
            for path, _ in need:
                self._author_cache[path] = None

        if need:
            threading.Thread(
                target=self._fetch_authors_for_projects,
                args=(need, token), daemon=True
            ).start()

    def _check_updates_batch(self, items, token: int):
        if not self._alive or token != self._refresh_token:
            return
        try:
            from config.constants import MODRINTH_API_BASE_URL, HTTP_TIMEOUT_SECONDS, USER_AGENT
            base = MODRINTH_API_BASE_URL; timeout = HTTP_TIMEOUT_SECONDS; ua = USER_AGENT
        except Exception:
            base = "https://api.modrinth.com/v2"; timeout = 15; ua = "PyLauncher/1.0"

        def post(url, payload):
            data = json.dumps(payload).encode()
            req  = urllib.request.Request(url, data=data, headers={
                "User-Agent": ua, "Content-Type": "application/json",
                "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())

        def get(url):
            req = urllib.request.Request(url, headers={
                "User-Agent": ua, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())

        # Solo items que tienen pid en caché y no han sido chequeados
        with self._fetch_lock:
            to_check = [
                i for i in items
                if i["path"] in self._pid_cache
                and i["path"] not in self._update_cache
            ]

        if not to_check:
            return

        mc_ver = self.profile.version_id
        loader = self._read_loader()

        from concurrent.futures import ThreadPoolExecutor, as_completed

        def check_one(item):
            path = item["path"]
            pid  = self._pid_cache.get(path)
            if not pid:
                return path, None
            try:
                # Obtener la última versión compatible
                url = (f"{base}/project/{pid}/version"
                    f"?game_versions=[\"{mc_ver}\"]"
                    f"&loaders=[\"{loader}\"]")
                versions = get(url)
                if not versions:
                    return path, None
                latest = versions[0]  # Modrinth devuelve newest first
                latest_id = latest.get("id", "")

                # Comparar con SHA1 del archivo instalado
                installed_sha1 = _sha1(path)
                for vfile in latest.get("files", []):
                    if vfile.get("hashes", {}).get("sha1") == installed_sha1:
                        return path, None  # Ya está actualizado
                # SHA1 no coincide → hay update disponible
                latest_number = latest.get("version_number", "")
                return path, latest_number or latest_id
            except Exception:
                return path, None

        found_updates = False
        with ThreadPoolExecutor(max_workers=6) as ex:
            futures = [ex.submit(check_one, i) for i in to_check]
            for future in as_completed(futures):
                if not self._alive or token != self._refresh_token:
                    return
                path, update_ver = future.result()
                with self._fetch_lock:
                    self._update_cache[path] = update_ver
                if update_ver:
                    found_updates = True

        if found_updates and self._alive and token == self._refresh_token:
            self.page.run_thread(lambda t=token: self._redraw_list(t))

    # ── Fetch autores ─────────────────────────────────────────────────────────
    def _fetch_authors_for_projects(self, path_pid_list, token: int):
        if not self._alive or token != self._refresh_token:
            return
        try:
            from config.constants import MODRINTH_API_BASE_URL, HTTP_TIMEOUT_SECONDS, USER_AGENT
            base = MODRINTH_API_BASE_URL; timeout = HTTP_TIMEOUT_SECONDS; ua = USER_AGENT
        except Exception:
            base = "https://api.modrinth.com/v2"; timeout = 15; ua = "PyLauncher/1.0"

        def get(url):
            req = urllib.request.Request(url, headers={
                "User-Agent": ua, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())

        need_fetch = []
        for path, pid in path_pid_list:
            cached = cache_get_author(f"pid:{pid}")
            if cached is not None:
                with self._fetch_lock:
                    self._author_cache[path] = cached
            else:
                need_fetch.append((path, pid))

        if len(need_fetch) < len(path_pid_list) and self._alive and token == self._refresh_token:
            self.page.run_thread(lambda t=token: self._redraw_list(t))

        if not need_fetch:
            return

        from concurrent.futures import ThreadPoolExecutor, as_completed

        def fetch_one(path_pid):
            path, pid = path_pid
            try:
                members = get(f"{base}/project/{pid}/members")
                owner   = next(
                    (m for m in members if m.get("role") == "Owner"),
                    members[0] if members else None,
                )
                if owner:
                    user = owner.get("user", {})
                    return path, pid, {
                        "username":   user.get("username", ""),
                        "avatar_url": user.get("avatar_url") or None,
                    }
            except Exception as ex:
                log.debug(f"[AUTHOR] {pid}: {ex}")
            return path, pid, {"username": "", "avatar_url": None}

        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(fetch_one, item) for item in need_fetch]
            for future in as_completed(futures):
                if not self._alive or token != self._refresh_token:
                    break
                path, pid, result = future.result()
                cache_set_author(f"pid:{pid}", result.get("avatar_url"), extra=result)
                if result.get("username"):
                    cache_set_author(result["username"], result.get("avatar_url"), extra=result)
                with self._fetch_lock:
                    self._author_cache[path] = result
                if result.get("username") and self._alive and token == self._refresh_token:
                    self.page.run_thread(lambda t=token: self._redraw_list(t))

    # ── Fila de mod ───────────────────────────────────────────────────────────
    def _make_row(self, item):
        fn    = item["filename"]
        path  = item["path"]
        is_en = item["is_enabled"]
        disp  = re.sub(r'\.(jar|zip)(\.disabled)?$', '', fn, flags=re.IGNORECASE)

        with self._fetch_lock:
            icon_url    = self._icon_cache.get(path)
            author_data = self._author_cache.get(path)
            pid         = self._pid_cache.get(path)
            update_ver  = self._update_cache.get(path)   # None = ok, str = update available

        icon_widget  = _icon(icon_url or "", disp, size=46)
        version_str  = item["version"] or "—"
        filename_str = fn if len(fn) <= 42 else fn[:40] + "…"

        # ── Author ────────────────────────────────────────────────────────────────
        if author_data and author_data.get("username"):
            username   = author_data["username"]
            avatar_url = author_data.get("avatar_url")
            av = (
                ft.Image(src=avatar_url, width=15, height=15,
                        border_radius=8, fit=ft.ImageFit.COVER)
                if avatar_url else
                ft.Container(
                    width=15, height=15, border_radius=8,
                    bgcolor=CARD2_BG, alignment=ft.alignment.center,
                    content=ft.Text(username[0].upper(), size=7, color=TEXT_DIM),
                )
            )
            author_row = ft.GestureDetector(
                mouse_cursor=ft.MouseCursor.CLICK,
                on_tap=lambda e, u=f"https://modrinth.com/user/{username}":
                    self.page.launch_url(u),
                content=ft.Row([
                    av, ft.Container(width=5),
                    ft.Text(username, color=GREEN, size=10,
                            weight=ft.FontWeight.W_500),
                ], spacing=0, tight=True),
            )
        else:
            author_row = ft.Container(height=14)

        # ── Update badge ──────────────────────────────────────────────────────────
        if update_ver:
            update_badge = ft.Container(
                bgcolor="#1a2d1a",
                border=ft.border.all(1, "#2d5a2d"),
                border_radius=5,
                padding=ft.padding.symmetric(horizontal=8, vertical=3),
                tooltip=f"Update available: {update_ver}",
                content=ft.Row([
                    ft.Icon(ft.icons.DOWNLOAD_ROUNDED, size=10, color=GREEN),
                    ft.Container(width=4),
                    ft.Text(update_ver, color=GREEN, size=9,
                            weight=ft.FontWeight.W_600),
                ], spacing=0, tight=True),
            )
            version_col = ft.Column([
                ft.Row([
                    ft.Text(version_str, color=TEXT_DIM, size=10,
                            weight=ft.FontWeight.W_400,
                            style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH)),
                    ft.Container(width=6),
                    update_badge,
                ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text(filename_str, color=TEXT_DIM, size=9,
                        overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=2, width=280)
        else:
            version_col = ft.Column([
                ft.Text(version_str, color=TEXT_PRI, size=11,
                        weight=ft.FontWeight.W_500),
                ft.Text(filename_str, color=TEXT_DIM, size=9,
                        overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=2, width=280)

        # ── Checkbox con tracking ─────────────────────────────────────────────────
        chk = ft.Checkbox(
            value=path in self._selected_paths,
            fill_color={"selected": GREEN},
            check_color=TEXT_INV, width=20,
            on_change=lambda e, p=path: self._on_check(p, e.control.value),
        )

        # ── Swap ──────────────────────────────────────────────────────────────────
        def on_swap(e, _pid=pid, _disp=disp):
            if not _pid:
                self.app.snack("No encontrado en Modrinth.", error=True)
                return
            class _FakeProject:
                def __init__(self, pid, title, icon):
                    self.project_id = pid; self.title = title
                    self.icon_url = icon or ""; self.description = ""
                    self.downloads = 0; self.author = ""; self.follows = 0
                    self.slug = pid
            from gui.views.discover_view import ModDetailDialog
            ModDetailDialog(
                self.page, self.app,
                project=_FakeProject(_pid, _disp, icon_url),
                active_profile=self.profile,
                active_loader=self._read_loader(),
                target_dir=os.path.dirname(path),
                on_installed=lambda: self._refresh(),
            )

        # ── More ──────────────────────────────────────────────────────────────────
        def on_more(e, _path=path, _pid=pid, _disp=disp):
            def _hoverable(icon, label, action, color=TEXT_PRI):
                item = ft.Container(
                    bgcolor="transparent", border_radius=8,
                    padding=ft.padding.symmetric(horizontal=16, vertical=12),
                    on_click=action,
                    content=ft.Row([
                        ft.Icon(icon, size=18,
                                color=GREEN if color == TEXT_PRI else color),
                        ft.Container(width=14),
                        ft.Text(label, color=color, size=13),
                    ], spacing=0, tight=True),
                )
                item.on_hover = lambda ev, c=item: (
                    setattr(c, "bgcolor",
                            INPUT_BG if ev.data == "true" else "transparent")
                    or c.update()
                )
                return item

            # Botón "Install update" solo si hay update disponible
            update_item = None
            if update_ver and _pid:
                def install_update(e):
                    self.page.close(sheet)
                    self._install_update(_path, _pid, update_ver)
                update_item = _hoverable(
                    ft.icons.SYSTEM_UPDATE_ROUNDED,
                    f"Install update  ({update_ver})",
                    install_update, color=GREEN,
                )

            items_list = []
            if update_item:
                items_list.append(update_item)
                items_list.append(ft.Divider(height=1, color=BORDER))

            items_list += [
                _hoverable(ft.icons.FOLDER_OPEN_ROUNDED, "Open folder",
                    lambda e: (self.page.close(sheet), self._open_folder(os.path.dirname(_path)))),
                _hoverable(ft.icons.OPEN_IN_NEW_ROUNDED, "View on Modrinth",
                    lambda e: (self.page.close(sheet),
                        self.page.launch_url(f"https://modrinth.com/mod/{_pid}")
                        if _pid else self.app.snack("Not found on Modrinth.", error=True))),
                ft.Divider(height=1, color=BORDER),
                _hoverable(ft.icons.COPY_ROUNDED, "Copy filename",
                    lambda e: (self.page.close(sheet),
                        self.page.set_clipboard(os.path.basename(_path)),
                        self.app.snack("Filename copied."))),
                _hoverable(ft.icons.ROUTE_ROUNDED, "Copy full path",
                    lambda e: (self.page.close(sheet),
                        self.page.set_clipboard(_path),
                        self.app.snack("Path copied."))),
                ft.Divider(height=1, color=BORDER),
                _hoverable(ft.icons.DELETE_OUTLINE_ROUNDED, "Delete",
                    lambda e: (self.page.close(sheet),
                        self._delete(item)), color=ACCENT_RED),
            ]

            sheet = ft.BottomSheet(
                bgcolor=CARD_BG,
                content=ft.Container(
                    padding=ft.padding.symmetric(horizontal=12, vertical=16),
                    content=ft.Column([
                        ft.Container(
                            padding=ft.padding.symmetric(horizontal=16, vertical=8),
                            content=ft.Row([
                                _icon(icon_url or "", _disp, size=36),
                                ft.Container(width=12),
                                ft.Column([
                                    ft.Text(_disp, color=TEXT_PRI, size=13,
                                            weight=ft.FontWeight.BOLD,
                                            overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Text(version_str, color=TEXT_DIM, size=10),
                                ], spacing=2, expand=True),
                            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ),
                        ft.Divider(height=1, color=BORDER),
                        ft.Container(height=4),
                        *items_list,
                        ft.Container(height=8),
                    ], spacing=2, tight=True),
                ),
            )
            self.page.open(sheet)

        return ft.Container(
            bgcolor="transparent",
            border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            on_hover=lambda e: (
                setattr(e.control, "bgcolor",
                        INPUT_BG if e.data == "true" else "transparent")
                or e.control.update()
            ),
            content=ft.Row([
                chk,
                ft.Container(width=12),
                icon_widget,
                ft.Container(width=16),
                ft.Column([
                    ft.Text(disp, color=TEXT_PRI, size=12,
                            weight=ft.FontWeight.BOLD,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    author_row,
                ], spacing=3, expand=True),
                version_col,
                ft.Row([
                    ft.IconButton(
                        icon=ft.icons.SWAP_HORIZ_ROUNDED,
                        icon_color=TEXT_DIM, icon_size=20,
                        tooltip="Change version",
                        on_click=on_swap,
                    ),
                    ft.IconButton(
                        icon=ft.icons.TOGGLE_ON if is_en else ft.icons.TOGGLE_OFF,
                        icon_color=GREEN if is_en else TEXT_DIM,
                        icon_size=34,
                        tooltip="Disable" if is_en else "Enable",
                        on_click=lambda e, i=item: self._toggle(i),
                    ),
                    ft.IconButton(
                        icon=ft.icons.DELETE_OUTLINE_ROUNDED,
                        icon_color=TEXT_DIM, icon_size=18,
                        tooltip="Delete",
                        on_click=lambda e, i=item: self._delete(i),
                    ),
                    ft.IconButton(
                        icon=ft.icons.MORE_VERT_ROUNDED,
                        icon_color=TEXT_DIM, icon_size=18,
                        tooltip="More options",
                        on_click=on_more,
                    ),
                ], spacing=0, tight=True),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    def _toggle(self, item):
        path = item["path"]
        try:
            if item["is_enabled"]:
                new_path = path + ".disabled"
            else:
                new_path = path.removesuffix(".disabled")
            os.rename(path, new_path)
            with self._fetch_lock:
                for cache in (self._icon_cache, self._author_cache, self._pid_cache):
                    if path in cache:
                        cache[new_path] = cache.pop(path)
            self._refresh()
        except OSError as ex:
            self.app.snack(str(ex), error=True)

    def _delete(self, item):
        def confirm(e):
            self.page.close(dlg)
            if e.control.text == "Eliminar":
                try:
                    os.remove(item["path"])
                    with self._fetch_lock:
                        for cache in (self._icon_cache, self._author_cache, self._pid_cache):
                            cache.pop(item["path"], None)
                    self._refresh()
                    self.app.snack("Eliminado.")
                except OSError as ex:
                    self.app.snack(str(ex), error=True)

        dlg = ft.AlertDialog(
            modal=True, bgcolor=CARD_BG,
            title=ft.Text("Eliminar", color=TEXT_PRI),
            content=ft.Text(f"Eliminar '{item['filename']}'?", color=TEXT_SEC),
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

    def _on_file_picked(self, e):
        if not e.files:
            return
        src = e.files[0].path
        fn  = os.path.basename(src)
        dest_dir = os.path.join(
            self.profile.game_dir,
            "mods" if fn.lower().endswith(".jar") else "resourcepacks"
        )
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
        discover = self.app._views.get("discover")
        if not discover:
            from gui.views.discover_view import DiscoverView
            discover = DiscoverView(self.page, self.app)
            self.app._views["discover"] = discover
        discover.set_source_profile(self.profile)
        self.app._show_view("discover")

    def _read_loader(self):
        meta_path = os.path.join(self.profile.game_dir, "loader_meta.json")
        if os.path.isfile(meta_path):
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                entries = meta if isinstance(meta, list) else [meta]
                if entries:
                    return entries[0].get("loader_type") or entries[0].get("loader", "vanilla")
            except Exception:
                pass
        return "vanilla"

# =============================================================================
# Instance Settings Dialog
# =============================================================================
class _InstanceSettingsDialog:
    _SECTIONS = [
        ("general",     ft.icons.TUNE_ROUNDED,           "General"),
        ("installation",ft.icons.EXTENSION_ROUNDED,      "Installation"),
        ("java",        ft.icons.MEMORY_ROUNDED,         "Java & Memory"),
        ("hooks",       ft.icons.CODE_ROUNDED,           "Launch Hooks"),
    ]
    _LOADERS = ["Vanilla", "Fabric", "NeoForge", "Forge", "Quilt"]

    def __init__(self, page, app, profile, on_done=None):
        self.page     = page
        self.app      = app
        self.profile  = profile
        self.on_done  = on_done
        self._section = "general"
        self._dirty   = False

        # Estado editable
        self._name_val    = profile.name
        self._loader_val  = self._detect_loader()
        self._version_val = profile.version_id
        self._ram_val     = self._read_meta("ram_mb", 4096)
        self._java_val    = self._read_meta("java_path", "")
        self._jvm_val     = self._read_meta("jvm_args", "")
        self._pre_val     = self._read_meta("pre_launch", "")
        self._post_val    = self._read_meta("post_exit", "")

        self._build()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _detect_loader(self):
        import json as _json
        meta_path = os.path.join(self.profile.game_dir, "loader_meta.json")
        if os.path.isfile(meta_path):
            try:
                with open(meta_path) as f:
                    meta = _json.load(f)
                entries = meta if isinstance(meta, list) else [meta]
                if entries:
                    ld = entries[0].get("loader_type") or entries[0].get("loader", "vanilla")
                    return ld.capitalize()
            except Exception:
                pass
        return "Vanilla"

    def _read_meta(self, key, default):
        import json as _json
        meta_path = os.path.join(self.profile.game_dir, "instance_settings.json")
        if os.path.isfile(meta_path):
            try:
                with open(meta_path) as f:
                    data = _json.load(f)
                return data.get(key, default)
            except Exception:
                pass
        return default

    def _write_meta(self, updates: dict):
        import json as _json
        meta_path = os.path.join(self.profile.game_dir, "instance_settings.json")
        data = {}
        if os.path.isfile(meta_path):
            try:
                with open(meta_path) as f:
                    data = _json.load(f)
            except Exception:
                pass
        data.update(updates)
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w") as f:
            _json.dump(data, f, indent=2)

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self):
        # ── Sidebar ───────────────────────────────────────────────────────────
        self._nav_items = {}
        nav_col = ft.Column(spacing=2)
        for sid, icon, label in self._SECTIONS:
            item = self._make_nav_item(sid, icon, label)
            self._nav_items[sid] = item
            nav_col.controls.append(item)

        sidebar = ft.Container(
            width=200,
            bgcolor=CARD2_BG,
            border=ft.border.only(right=ft.BorderSide(1, BORDER)),
            padding=ft.padding.symmetric(horizontal=10, vertical=16),
            content=nav_col,
        )

        # ── Content area ──────────────────────────────────────────────────────
        self._content_area = ft.Container(
            expand=True,
            padding=ft.padding.all(28),
            content=self._render_section(self._section),
        )

        # ── Save / Cancel ─────────────────────────────────────────────────────
        self._save_btn = ft.ElevatedButton(
            "Save changes",
            bgcolor=GREEN, color=TEXT_INV,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=24, vertical=12),
            ),
            on_click=self._on_save,
        )

        # ── Breadcrumb header ─────────────────────────────────────────────────
        self._breadcrumb = ft.Text(
            "General", color=TEXT_PRI, size=15,
            weight=ft.FontWeight.BOLD,
        )

        header = ft.Container(
            bgcolor=CARD_BG,
            padding=ft.padding.symmetric(horizontal=24, vertical=16),
            border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
            content=ft.Row([
                ft.Text(self.profile.name, color=TEXT_DIM, size=13),
                ft.Icon(ft.icons.CHEVRON_RIGHT_ROUNDED, size=14, color=TEXT_DIM),
                self._breadcrumb,
                ft.Container(expand=True),
                ft.TextButton(
                    "Cancel",
                    style=ft.ButtonStyle(color=TEXT_SEC),
                    on_click=lambda e: self.page.close(self._dlg),
                ),
                ft.Container(width=8),
                self._save_btn,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        self._dlg = ft.AlertDialog(
            modal=True,
            bgcolor=CARD_BG,
            title=ft.Container(),      # header custom dentro del content
            content_padding=ft.padding.all(0),
            content=ft.Container(
                width=820,
                height=520,
                bgcolor=CARD_BG,
                border_radius=12,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                content=ft.Column([
                    header,
                    ft.Row([
                        sidebar,
                        self._content_area,
                    ], spacing=0, expand=True),
                ], spacing=0, expand=True),
            ),
            actions=[],
        )
        self.page.open(self._dlg)

    def _make_nav_item(self, sid, icon, label):
        active = sid == self._section
        item = ft.Container(
            bgcolor=GREEN if active else "transparent",
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
            on_click=lambda e, s=sid: self._switch_section(s),
            content=ft.Row([
                ft.Icon(icon, size=16,
                        color=TEXT_INV if active else TEXT_DIM),
                ft.Container(width=10),
                ft.Text(label, size=12,
                        color=TEXT_INV if active else TEXT_SEC,
                        weight=ft.FontWeight.W_600 if active
                               else ft.FontWeight.NORMAL),
            ], spacing=0, tight=True),
        )
        item.on_hover = lambda e, b=item, s=sid: (
            None if s == self._section else (
                setattr(b, "bgcolor",
                        INPUT_BG if e.data == "true" else "transparent")
                or b.update()
            )
        )
        return item

    def _switch_section(self, sid):
        self._section = sid
        # Update nav highlight
        for s, icon, label in self._SECTIONS:
            item = self._nav_items[s]
            active = s == sid
            item.bgcolor = GREEN if active else "transparent"
            row: ft.Row = item.content
            row.controls[0].color = TEXT_INV if active else TEXT_DIM
            row.controls[2].color = TEXT_INV if active else TEXT_SEC
            row.controls[2].weight = (ft.FontWeight.W_600 if active
                                      else ft.FontWeight.NORMAL)
            try: item.update()
            except Exception: pass
        # Update breadcrumb
        label_map = {s: l for s, _, l in self._SECTIONS}
        self._breadcrumb.value = label_map[sid]
        try: self._breadcrumb.update()
        except Exception: pass
        # Render section
        self._content_area.content = self._render_section(sid)
        try: self._content_area.update()
        except Exception: pass

    # ── Section renderers ─────────────────────────────────────────────────────
    def _render_section(self, sid):
        if sid == "general":   return self._section_general()
        if sid == "installation": return self._section_installation()
        if sid == "java":      return self._section_java()
        if sid == "hooks":     return self._section_hooks()
        return ft.Container()

    # ── General ───────────────────────────────────────────────────────────────
    def _section_general(self):
        def _heading(text):
            return ft.Text(text, color=TEXT_PRI, size=13,
                           weight=ft.FontWeight.BOLD)
        def _subtext(text):
            return ft.Text(text, color=TEXT_DIM, size=10)

        self._name_field = ft.TextField(
            value=self._name_val,
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, height=42,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            text_size=12,
            on_change=lambda e: setattr(self, "_name_val", e.control.value),
        )

        # Instance icon display
        icon_box = ft.Container(
            width=80, height=80, border_radius=14,
            bgcolor=CARD2_BG, alignment=ft.alignment.center,
            border=ft.border.all(1, BORDER),
            content=ft.Icon(ft.icons.WIDGETS_ROUNDED, size=36, color=TEXT_DIM),
        )

        # Duplicate
        def on_duplicate(e):
            self.page.close(self._dlg)
            self._duplicate_instance()

        dup_btn = ft.OutlinedButton(
            "Duplicate",
            icon=ft.icons.COPY_ALL_ROUNDED,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                side=ft.BorderSide(1, BORDER), color=TEXT_SEC,
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
            ),
            on_click=on_duplicate,
        )

        # Delete
        def on_delete(e):
            self.page.close(self._dlg)
            self._confirm_delete()

        del_btn = ft.ElevatedButton(
            "Delete instance",
            icon=ft.icons.DELETE_FOREVER_ROUNDED,
            bgcolor=ACCENT_RED, color="#ffffff",
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
            ),
            on_click=on_delete,
        )

        return ft.Column([
            ft.Row([
                ft.Column([
                    _heading("Instance name"),
                    ft.Container(height=6),
                    self._name_field,
                ], spacing=0, expand=True),
                ft.Container(width=20),
                icon_box,
            ], vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            _heading("Duplicate instance"),
            ft.Container(height=4),
            _subtext("Creates a copy of this instance, including worlds, configs, mods, etc."),
            ft.Container(height=10),
            dup_btn,
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            _heading("Delete instance"),
            ft.Container(height=4),
            _subtext(
                "Permanently deletes this instance from your device, including worlds, configs,\n"
                "and all installed content. This action cannot be undone."
            ),
            ft.Container(height=10),
            del_btn,
        ], spacing=0, scroll=ft.ScrollMode.AUTO)

    # ── Installation ──────────────────────────────────────────────────────────
    def _section_installation(self):
        def _heading(text):
            return ft.Text(text, color=TEXT_PRI, size=13,
                           weight=ft.FontWeight.BOLD)
        def _subtext(text):
            return ft.Text(text, color=TEXT_DIM, size=10)

        # Loader pills
        self._loader_btns = {}
        loader_row = ft.Row(spacing=8, wrap=True)
        for ld in self._LOADERS:
            btn = self._loader_pill(ld)
            self._loader_btns[ld] = btn
            loader_row.controls.append(btn)

        # Version dropdown — load versions from version_manager
        versions = ["(current) " + self.profile.version_id]
        try:
            all_v = self.app.version_manager.get_available_versions()
            versions = [v.id if hasattr(v, "id") else str(v) for v in all_v]
            if not versions:
                versions = [self.profile.version_id]
        except Exception:
            versions = [self.profile.version_id]

        self._version_dd = ft.Dropdown(
            value=self._version_val,
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, height=42,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=8),
            text_style=ft.TextStyle(size=12),
            options=[ft.dropdown.Option(v) for v in versions],
            on_change=lambda e: setattr(self, "_version_val", e.control.value),
        )

        return ft.Column([
            _heading("Mod loader"),
            ft.Container(height=4),
            _subtext("Select the loader for this instance."),
            ft.Container(height=12),
            loader_row,
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            _heading("Game version"),
            ft.Container(height=4),
            _subtext("Minecraft version used by this instance."),
            ft.Container(height=12),
            self._version_dd,
        ], spacing=0, scroll=ft.ScrollMode.AUTO)

    def _loader_pill(self, label):
        active = label.lower() == self._loader_val.lower()
        pill = ft.Container(
            bgcolor=GREEN if active else INPUT_BG,
            border=ft.border.all(1, GREEN if active else BORDER),
            border_radius=20,
            padding=ft.padding.symmetric(horizontal=18, vertical=9),
            animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
            content=ft.Text(label,
                            color=TEXT_INV if active else TEXT_SEC,
                            size=11, weight=ft.FontWeight.W_600),
        )
        def on_click(e, lbl=label, p=pill):
            self._loader_val = lbl
            for l2, b in self._loader_btns.items():
                a = l2.lower() == lbl.lower()
                b.bgcolor = GREEN if a else INPUT_BG
                b.border  = ft.border.all(1, GREEN if a else BORDER)
                b.content.color = TEXT_INV if a else TEXT_SEC
                try: b.update()
                except Exception: pass
        pill.on_click = on_click
        pill.on_hover = lambda e, p=pill, lbl=label: (
            None if lbl.lower() == self._loader_val.lower() else (
                setattr(p, "bgcolor", CARD2_BG if e.data == "true" else INPUT_BG)
                or p.update()
            )
        )
        return pill

    # ── Java & Memory ─────────────────────────────────────────────────────────
    def _section_java(self):
        def _heading(text):
            return ft.Text(text, color=TEXT_PRI, size=13,
                           weight=ft.FontWeight.BOLD)
        def _subtext(text):
            return ft.Text(text, color=TEXT_DIM, size=10)

        ram_opts = [512, 1024, 2048, 3072, 4096, 6144, 8192, 12288, 16384]
        self._ram_dd = ft.Dropdown(
            value=str(self._ram_val),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, height=42,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=8),
            text_style=ft.TextStyle(size=12),
            options=[ft.dropdown.Option(str(r),
                     f"{r} MB  ({r//1024} GB)" if r >= 1024 else f"{r} MB")
                     for r in ram_opts],
            on_change=lambda e: setattr(self, "_ram_val",
                                        int(e.control.value or 4096)),
        )

        self._java_field = ft.TextField(
            value=self._java_val,
            hint_text="Leave empty to use system default",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=11),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, height=42, expand=True,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            text_size=12,
            on_change=lambda e: setattr(self, "_java_val", e.control.value),
        )

        def browse_java(e):
            # Abrir file picker para seleccionar java executable
            fp = ft.FilePicker(on_result=lambda r: (
                setattr(self, "_java_val",
                        r.files[0].path if r.files else self._java_val)
                or setattr(self._java_field, "value",
                           r.files[0].path if r.files else self._java_val)
                or self._java_field.update()
            ))
            self.page.overlay.append(fp)
            self.page.update()
            fp.pick_files(dialog_title="Select Java executable",
                         allowed_extensions=["exe", ""])

        browse_btn = ft.OutlinedButton(
            "Browse",
            icon=ft.icons.FOLDER_OPEN_ROUNDED,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                side=ft.BorderSide(1, BORDER), color=TEXT_SEC,
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
            ),
            on_click=browse_java,
        )

        self._jvm_field = ft.TextField(
            value=self._jvm_val,
            hint_text="e.g.  -XX:+UseG1GC -XX:MaxGCPauseMillis=50",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=11),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, min_lines=2, max_lines=4,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            text_size=12,
            on_change=lambda e: setattr(self, "_jvm_val", e.control.value),
        )

        return ft.Column([
            _heading("Memory (RAM)"),
            ft.Container(height=4),
            _subtext("Amount of RAM allocated to this Minecraft instance."),
            ft.Container(height=12),
            self._ram_dd,
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            _heading("Java executable"),
            ft.Container(height=4),
            _subtext("Path to the java binary. Leave empty to use the system default."),
            ft.Container(height=12),
            ft.Row([self._java_field, ft.Container(width=8), browse_btn],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            _heading("JVM arguments"),
            ft.Container(height=4),
            _subtext("Additional arguments passed to the JVM. Advanced users only."),
            ft.Container(height=12),
            self._jvm_field,
        ], spacing=0, scroll=ft.ScrollMode.AUTO)

    # ── Launch Hooks ──────────────────────────────────────────────────────────
    def _section_hooks(self):
        def _heading(text):
            return ft.Text(text, color=TEXT_PRI, size=13,
                           weight=ft.FontWeight.BOLD)
        def _subtext(text):
            return ft.Text(text, color=TEXT_DIM, size=10)

        self._pre_field = ft.TextField(
            value=self._pre_val,
            hint_text="Command to run before launching Minecraft",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=11),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, min_lines=2, max_lines=4,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            text_size=12,
            on_change=lambda e: setattr(self, "_pre_val", e.control.value),
        )

        self._post_field = ft.TextField(
            value=self._post_val,
            hint_text="Command to run after Minecraft exits",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=11),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, min_lines=2, max_lines=4,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            text_size=12,
            on_change=lambda e: setattr(self, "_post_val", e.control.value),
        )

        return ft.Column([
            _heading("Pre-launch command"),
            ft.Container(height=4),
            _subtext(
                "Runs before Minecraft starts. Use $INSTANCE_DIR for the instance path.\n"
                "Example:  echo 'Starting' >> $INSTANCE_DIR/launch.log"
            ),
            ft.Container(height=12),
            self._pre_field,
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            _heading("Post-exit command"),
            ft.Container(height=4),
            _subtext(
                "Runs after Minecraft exits. $EXIT_CODE contains the process exit code.\n"
                "Example:  notify-send 'Minecraft closed with code $EXIT_CODE'"
            ),
            ft.Container(height=12),
            self._post_field,
            ft.Container(height=24),
            ft.Container(
                bgcolor="#1a2a1a",
                border=ft.border.all(1, "#2a4a2a"),
                border_radius=8,
                padding=ft.padding.all(14),
                content=ft.Row([
                    ft.Icon(ft.icons.INFO_OUTLINE_ROUNDED, size=16, color=GREEN),
                    ft.Container(width=10),
                    ft.Text(
                        "Commands run in a shell (bash on Linux/macOS, cmd on Windows).\n"
                        "The instance directory is passed as $INSTANCE_DIR.",
                        color=TEXT_SEC, size=10,
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.START),
            ),
        ], spacing=0, scroll=ft.ScrollMode.AUTO)

    # ── Save ──────────────────────────────────────────────────────────────────
    def _on_save(self, e):
        self._save_btn.disabled = True
        self._save_btn.text = "Saving…"
        try: self._save_btn.update()
        except Exception: pass

        try:
            # 1. Rename profile if name changed
            if self._name_val.strip() and self._name_val != self.profile.name:
                self.app.profile_manager.rename_profile(
                    self.profile.id, self._name_val.strip())

            # 2. Update version if changed
            if self._version_val != self.profile.version_id:
                self.app.profile_manager.update_profile_version(
                    self.profile.id, self._version_val)

            # 3. Write instance settings JSON
            self._write_meta({
                "ram_mb":     self._ram_val,
                "java_path":  self._java_val.strip(),
                "jvm_args":   self._jvm_val.strip(),
                "pre_launch": self._pre_val.strip(),
                "post_exit":  self._post_val.strip(),
                "loader":     self._loader_val.lower(),
            })

            self.page.close(self._dlg)
            self.app.snack("Instance settings saved.")
            if self.on_done:
                self.on_done()
        except Exception as ex:
            self._save_btn.disabled = False
            self._save_btn.text = "Save changes"
            try: self._save_btn.update()
            except Exception: pass
            self.app.snack(str(ex), error=True)

    # ── Duplicate ─────────────────────────────────────────────────────────────
    def _duplicate_instance(self):
        import shutil, time

        def do_dup():
            try:
                new_name = f"{self.profile.name} (copy)"
                new_dir  = self.profile.game_dir + "_copy_" + str(int(time.time()))
                shutil.copytree(self.profile.game_dir, new_dir)
                self.app.profile_manager.create_profile(
                    name=new_name,
                    version_id=self.profile.version_id,
                    game_dir=new_dir,
                )
                self.page.run_thread(lambda: self.app.snack(
                    f"'{new_name}' created."))
                if self.on_done:
                    self.page.run_thread(self.on_done)
            except Exception as ex:
                self.page.run_thread(
                    lambda: self.app.snack(str(ex), error=True))

        threading.Thread(target=do_dup, daemon=True).start()
        self.app.snack("Duplicating instance…")

    # ── Delete ────────────────────────────────────────────────────────────────
    def _confirm_delete(self):
        def on_action(e):
            self.page.close(confirm_dlg)
            if e.control.data == "delete":
                self._do_delete()

        confirm_dlg = ft.AlertDialog(
            modal=True, bgcolor=CARD_BG,
            title=ft.Text("Delete instance?", color=TEXT_PRI,
                          weight=ft.FontWeight.BOLD),
            content=ft.Text(
                f"This will permanently delete '{self.profile.name}' "
                f"and all its worlds, configs and mods.\nThis cannot be undone.",
                color=TEXT_SEC, size=12,
            ),
            actions=[
                ft.TextButton("Cancel",
                              style=ft.ButtonStyle(color=TEXT_SEC),
                              on_click=on_action),
                ft.ElevatedButton(
                    "Delete forever",
                    data="delete",
                    bgcolor=ACCENT_RED, color="#ffffff",
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=on_action,
                ),
            ],
        )
        self.page.open(confirm_dlg)

    def _do_delete(self):
        import shutil

        def do():
            try:
                self.app.profile_manager.delete_profile(self.profile.id)
                try:
                    shutil.rmtree(self.profile.game_dir, ignore_errors=True)
                except Exception:
                    pass
                self.page.run_thread(lambda: (
                    self.app.snack("Instance deleted."),
                    self.app._show_view("library"),
                ))
            except Exception as ex:
                self.page.run_thread(
                    lambda: self.app.snack(str(ex), error=True))

        threading.Thread(target=do, daemon=True).start()

    def _do_search(self, project_type):
        query = self._search_field.value.strip()
        if not query:
            return
        self._status_lbl.value     = "Buscando..."
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
                    query, mc_version=mc_ver,
                    loader=loader if project_type == "mod" else None,
                    project_type=project_type,
                )
                self.page.run_thread(lambda: self._show_results(results))
            except Exception as err:
                self.page.run_thread(lambda: self._set_status(f"Error: {err}"))

        threading.Thread(target=search, daemon=True).start()

    def _show_results(self, results):
        self._results = results
        self._results_col.controls.clear()

        for r in results:
            mc_v      = ", ".join(r.game_versions[-3:]) if r.game_versions else "-"
            author    = getattr(r, "author", "")
            installed = is_installed_in(r.slug, r.title, self._installed_set)

            icon_w = _icon(getattr(r, "icon_url", None) or "", r.title, size=42)

            badge = (
                ft.Container(
                    bgcolor="#1a3d2a", border_radius=4,
                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                    content=ft.Row([
                        ft.Icon(ft.icons.CHECK_CIRCLE_ROUNDED, size=10, color=GREEN),
                        ft.Container(width=4),
                        ft.Text("Instalado", color=GREEN, size=8,
                                weight=ft.FontWeight.BOLD),
                    ], spacing=0, tight=True),
                ) if installed else
                ft.Container(
                    bgcolor=CARD2_BG, border_radius=4,
                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                    content=ft.Text("No instalado", color=TEXT_DIM, size=8),
                )
            )

            row = ft.Container(
                bgcolor=INPUT_BG, border_radius=8,
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                data=r.project_id,
                on_click=((lambda e, pid=r.project_id: self._select(pid))
                          if not installed else None),
                on_hover=(lambda e: (
                    setattr(e.control, "bgcolor",
                            CARD2_BG if e.data == "true" else INPUT_BG)
                    or e.control.update())
                ) if not installed else None,
                opacity=0.6 if installed else 1.0,
                content=ft.Row([
                    icon_w,
                    ft.Container(width=14),
                    ft.Column([
                        ft.Text(r.title, color=TEXT_PRI, size=10,
                                weight=ft.FontWeight.BOLD,
                                overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(
                            f"por {author}" if author
                            else (r.description[:60] + "..."
                                  if len(r.description) > 60 else r.description),
                            color=TEXT_SEC, size=9,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=2, expand=True),
                    ft.Column([
                        badge,
                        ft.Container(height=4),
                        ft.Text(mc_v, color=TEXT_DIM, size=8,
                                text_align=ft.TextAlign.RIGHT),
                        ft.Text(f"v {r.downloads:,}", color=TEXT_DIM, size=8,
                                text_align=ft.TextAlign.RIGHT),
                    ], spacing=0, width=130,
                       horizontal_alignment=ft.CrossAxisAlignment.END),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )
            self._results_col.controls.append(row)

        installed_count = sum(
            1 for r in results
            if is_installed_in(r.slug, r.title, self._installed_set)
        )
        self._status_lbl.value = (
            f"{len(results)} resultados"
            + (f" - {installed_count} ya instalados" if installed_count else "")
        )
        try:
            self._results_col.update()
            self._status_lbl.update()
        except Exception: pass

    def _select(self, pid):
        self._selected_id          = pid
        self._install_btn.disabled = False
        for c in self._results_col.controls:
            if not getattr(c, "data", None): continue
            if c.opacity == 0.6: continue
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

        self._status_lbl.value     = f"Descargando {proj.title}..."
        self._install_btn.disabled = True
        try:
            self._status_lbl.update()
            self._install_btn.update()
        except Exception: pass

        project_type = self._TYPE_MAP.get(self.content_type, "mod")
        dest_folder  = self._DEST_FOLDER.get(project_type, "mods")
        dest_dir     = os.path.join(self.profile.game_dir, dest_folder)
        os.makedirs(dest_dir, exist_ok=True)

        def download():
            try:
                version = self.app.modrinth_service.get_latest_version(
                    self._selected_id,
                    mc_version=self.profile.version_id,
                    loader=self.loader,
                )
                if not version:
                    self.page.run_thread(lambda: self._set_status("Sin version compatible."))
                    return
                self.app.modrinth_service.download_mod_version(version, dest_dir)
                self._installed_set = build_installed_set(dest_dir)

                def done():
                    self._status_lbl.value     = f"OK {proj.title} instalado"
                    self._install_btn.disabled = False
                    try:
                        self._status_lbl.update()
                        self._install_btn.update()
                    except Exception: pass
                    self.on_install()
                    self.app.snack(f"{proj.title} instalado.")
                    self.page.run_thread(lambda: self._show_results(self._results))
                self.page.run_thread(done)
            except Exception as err:
                self.page.run_thread(lambda: self._set_status(f"Error: {err}"))

        threading.Thread(target=download, daemon=True).start()

    def _set_status(self, msg):
        self._status_lbl.value     = msg
        self._install_btn.disabled = False
        try:
            self._status_lbl.update()
            self._install_btn.update()
        except Exception: pass


# =============================================================================
# Tab: Files
# =============================================================================
class _FilesTab:
    def __init__(self, page, app, profile):
        self.page    = page
        self.app     = app
        self.profile = profile
        self._build()

    def _build(self):
        game_dir = self.profile.game_dir

        def folder_row(name, path):
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
                    ft.Text(f"{size:.1f} MB" if exists else "Vacia",
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

        self.root = ft.Container(
            expand=True, padding=ft.padding.all(28),
            content=ft.Column([
                ft.Text("Archivos", color=TEXT_PRI, size=16,
                        weight=ft.FontWeight.BOLD),
                ft.Text("Carpetas de la instancia", color=TEXT_DIM, size=9),
                ft.Container(height=16),
                ft.Column([folder_row(n, p) for n, p in folders],
                          spacing=8, scroll=ft.ScrollMode.AUTO, expand=True),
            ], spacing=0, expand=True),
        )

    @staticmethod
    def _folder_size(path):
        total = 0
        for dp, _, files in os.walk(path):
            for fn in files:
                try: total += os.path.getsize(os.path.join(dp, fn))
                except OSError: pass
        return total / 1048576

    @staticmethod
    def _open_folder(path):
        os.makedirs(path, exist_ok=True)
        import subprocess, sys
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])


# =============================================================================
# Tab: Worlds
# =============================================================================
class _WorldsTab:
    def __init__(self, page, app, profile):
        self.page    = page
        self.app     = app
        self.profile = profile
        self._build()

    def _build(self):
        saves_dir = os.path.join(self.profile.game_dir, "saves")
        worlds = []
        if os.path.isdir(saves_dir):
            worlds = [d for d in os.listdir(saves_dir)
                      if os.path.isdir(os.path.join(saves_dir, d))]

        if worlds:
            rows = [
                ft.Container(
                    bgcolor=INPUT_BG, border_radius=8,
                    padding=ft.padding.symmetric(horizontal=16, vertical=12),
                    content=ft.Row([
                        ft.Text("W", color=TEXT_DIM, size=22),
                        ft.Container(width=14),
                        ft.Text(w, color=TEXT_PRI, size=11,
                                weight=ft.FontWeight.BOLD, expand=True),
                    ]),
                )
                for w in sorted(worlds)
            ]
            content = ft.Column(rows, spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
        else:
            content = ft.Container(
                expand=True, alignment=ft.alignment.center,
                content=ft.Column([
                    ft.Text("Sin mundos guardados", color=TEXT_SEC, size=14,
                            text_align=ft.TextAlign.CENTER,
                            weight=ft.FontWeight.BOLD),
                    ft.Text("Los mundos apareceran aqui despues de jugar.",
                            color=TEXT_DIM, size=10, text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            )

        self.root = ft.Container(
            expand=True, padding=ft.padding.all(28),
            content=ft.Column([
                ft.Text("Mundos", color=TEXT_PRI, size=16, weight=ft.FontWeight.BOLD),
                ft.Text(
                    f"{len(worlds)} mundo{'s' if len(worlds) != 1 else ''} "
                    f"guardado{'s' if len(worlds) != 1 else ''}",
                    color=TEXT_DIM, size=9),
                ft.Container(height=16),
                content,
            ], spacing=0, expand=True),
        )


# =============================================================================
# Tab: Logs
# =============================================================================
class _LogsTab:
    def __init__(self, page, app, profile):
        self.page    = page
        self.app     = app
        self.profile = profile

        self.root = ft.Container(
            expand=True, padding=ft.padding.all(28),
            content=ft.Column([
                ft.Text("Logs", color=TEXT_PRI, size=16, weight=ft.FontWeight.BOLD),
                ft.Text("Registros del juego en tiempo real", color=TEXT_DIM, size=9),
                ft.Container(height=16),
                ft.Container(
                    expand=True, bgcolor=INPUT_BG, border_radius=8,
                    padding=ft.padding.all(16),
                    content=ft.Text(
                        "Los logs apareceran aqui durante la ejecucion del juego.",
                        color=TEXT_DIM, size=10,
                    ),
                ),
            ], spacing=0, expand=True),
        )