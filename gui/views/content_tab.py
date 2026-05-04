# -*- coding: utf-8 -*-
"""
gui/views/content_tab.py

Implements _ContentTab — the "Content" tab of InstanceView.

Features implemented (cross-referenced with instance_view.py comments):
  P2  – debounced search (300 ms timer)
  P3  – mtime-based item cache (skips re-scan when directory unchanged)
  P5  – semaphore guards icon-fetch concurrency (max 6 simultaneous)
  P6  – threading.Event cancellation signal
  B4  – _ContentTab.destroy() removes its FilePicker from page.overlay
  C4  – _ContentTab lives here (split from instance_view.py)
  C8  – ContentItem TypedDict lives here
  U1  – skeleton loader shown while items load
  U5  – visual drop-zone for drag-and-drop install
  U9  – 5-second undo after bulk-delete
  U10 – "Disabled" filter chip
  U11 – full-path tooltip on content rows
  S2  – 500 MB upload guard
"""

import os
import threading
import time
from typing import Optional, TypedDict

import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV, ACCENT_RED,
)
from utils.logger import get_logger

log = get_logger()

# ── S2: upload size guard (bytes) ─────────────────────────────────────────────
try:
    _MAX_UPLOAD_MB = int(os.environ.get("PYLAUNCHER_MAX_UPLOAD_MB", "500"))
except Exception:
    _MAX_UPLOAD_MB = 500
_MAX_UPLOAD_BYTES = _MAX_UPLOAD_MB * 1_048_576

# ── P5: icon-fetch concurrency cap ────────────────────────────────────────────
_ICON_SEMAPHORE = threading.Semaphore(
    int(os.environ.get("PYLAUNCHER_ICON_WORKERS", "6"))
)

# ── P2: debounce delay (seconds) ──────────────────────────────────────────────
_DEBOUNCE_DELAY = 0.30

# ── Categories ────────────────────────────────────────────────────────────────
_CATEGORIES = ["Mods", "Resource Packs", "Shaders"]

_CAT_DIRS: dict[str, str] = {
    "Mods":           "mods",
    "Resource Packs": "resourcepacks",
    "Shaders":        "shaderpacks",
}

_CAT_EXTS: dict[str, tuple[str, ...]] = {
    "Mods":           (".jar", ".jar.disabled"),
    "Resource Packs": (".zip", ".zip.disabled"),
    "Shaders":        (".zip", ".zip.disabled"),
}


# =============================================================================
# C8: TypedDict for a content item
# =============================================================================
class ContentItem(TypedDict):
    name:      str          # display name (filename without path)
    path:      str          # absolute path on disk
    enabled:   bool         # False if filename ends with .disabled
    size_mb:   float        # file size in MB
    icon_url:  str          # Modrinth icon URL or ""
    version:   str          # parsed version string or ""
    category:  str          # "Mods" | "Resource Packs" | "Shaders"
    mtime:     float        # os.path.getmtime at scan time


# =============================================================================
# Helpers
# =============================================================================
def _parse_version(filename: str) -> str:
    import re
    name = re.sub(r'\.(jar|zip|disabled)$', '', filename, flags=re.IGNORECASE)
    for part in reversed(name.split('-')):
        if re.match(r'^\d+\.\d+', part):
            return part
    return ""


def _file_size_mb(path: str) -> float:
    try:
        return os.path.getsize(path) / 1_048_576
    except OSError:
        return 0.0


def _is_disabled(filename: str) -> bool:
    return filename.lower().endswith(".disabled")


def _disable_path(path: str) -> str:
    return path if path.endswith(".disabled") else path + ".disabled"


def _enable_path(path: str) -> str:
    return path[:-len(".disabled")] if path.endswith(".disabled") else path



# =============================================================================
# _ContentTab
# =============================================================================
class _ContentTab:
    """
    Displays Mods / Resource Packs / Shaders installed in the instance.

    P2  – search input debounced with a threading.Timer
    P3  – directory mtime cached; re-scan only when changed
    P5  – icon downloads throttled via _ICON_SEMAPHORE
    P6  – threading.Event(_cancel) signals workers to stop on destroy/reload
    B4  – FilePicker removed from page.overlay in destroy()
    U1  – skeleton rows shown while items load
    U5  – drag-and-drop drop-zone (Flet DragTarget)
    U9  – 5-second undo banner after bulk-delete
    U10 – "Disabled" filter chip
    U11 – full-path tooltip on each row
    S2  – files >500 MB rejected with a snack message
    """

    def __init__(self, page: ft.Page, app, profile) -> None:
        self.page    = page
        self.app     = app
        self.profile = profile

        # Active category tab
        self._active_cat: str = _CATEGORIES[0]

        # P3: cache { category: (dir_mtime, [ContentItem]) }
        self._cache: dict[str, tuple[float, list[ContentItem]]] = {}

        # P6: cancellation event – set() to abort in-flight workers
        self._cancel = threading.Event()

        # Search state
        self._search_query: str = ""
        self._debounce_timer: Optional[threading.Timer] = None

        # Filter: None = all, True = enabled only, False = disabled only
        self._filter_enabled: Optional[bool] = None

        # Multi-select
        self._selected: set[str] = set()   # set of file paths

        # U9: undo state
        self._undo_timer: Optional[threading.Timer] = None
        self._undo_items: list[tuple[str, bytes]] = []  # (original_path, data)

        # File picker (B4: tracked so we can remove it)
        self._file_picker = ft.FilePicker(on_result=self._on_files_picked)
        self.page.overlay.append(self._file_picker)
        try:
            self.page.update()
        except Exception:
            pass

        self._build()
        # Kick off initial load
        threading.Thread(target=self._load_items, daemon=True).start()

    # =========================================================================
    # Build
    # =========================================================================
    def _build(self) -> None:
        # ── Category pills ────────────────────────────────────────────────────
        self._cat_btns: dict[str, ft.Container] = {}
        cat_row = ft.Row(spacing=6)
        for cat in _CATEGORIES:
            btn = self._make_cat_pill(cat)
            self._cat_btns[cat] = btn
            cat_row.controls.append(btn)

        # ── Search ────────────────────────────────────────────────────────────
        self._search_field = ft.TextField(
            hint_text="Buscar…",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=11),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=20, height=36,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=8),
            text_size=12,
            prefix_icon=ft.icons.SEARCH_ROUNDED,
            on_change=self._on_search_change,
            expand=True,
        )

        # ── Filter chips ──────────────────────────────────────────────────────
        self._chip_all      = self._make_filter_chip("Todos",       None)
        self._chip_enabled  = self._make_filter_chip("Activos",     True)
        self._chip_disabled = self._make_filter_chip("Desactivados", False)  # U10

        filter_row = ft.Row(
            [self._chip_all, self._chip_enabled, self._chip_disabled],
            spacing=6,
        )

        # ── Toolbar ───────────────────────────────────────────────────────────
        self._add_btn = ft.ElevatedButton(
            "Añadir",
            icon=ft.icons.ADD_ROUNDED,
            bgcolor=GREEN, color=TEXT_INV,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
            ),
            on_click=self._on_add_click,
        )
        self._bulk_delete_btn = ft.OutlinedButton(
            "Eliminar selección",
            icon=ft.icons.DELETE_OUTLINE_ROUNDED,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                side=ft.BorderSide(1, ACCENT_RED), color=ACCENT_RED,
                padding=ft.padding.symmetric(horizontal=14, vertical=8),
            ),
            visible=False,
            on_click=self._on_bulk_delete,
        )
        self._item_count_lbl = ft.Text("", color=TEXT_DIM, size=10)

        toolbar = ft.Row([
            self._item_count_lbl,
            ft.Container(expand=True),
            self._bulk_delete_btn,
            ft.Container(width=8),
            self._add_btn,
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # ── Content list ──────────────────────────────────────────────────────
        self._list_col = ft.Column(
            spacing=6, scroll=ft.ScrollMode.AUTO, expand=True
        )

        # U9: undo banner (hidden by default)
        self._undo_banner = ft.Container(
            visible=False,
            bgcolor="#1a2d1a",
            border=ft.border.all(1, GREEN),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            content=ft.Row([
                ft.Icon(ft.icons.DELETE_SWEEP_ROUNDED, color=GREEN, size=16),
                ft.Container(width=10),
                ft.Text("", color=TEXT_PRI, size=11, expand=True),
                ft.TextButton(
                    "Deshacer",
                    style=ft.ButtonStyle(color=GREEN),
                    on_click=self._on_undo,
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        # U5: drop-zone overlay
        self._drop_zone = ft.DragTarget(
            group="files",
            visible=False,
            content=ft.Container(
                expand=True,
                bgcolor="#1a2d40",
                border=ft.border.all(2, GREEN),
                border_radius=12,
                alignment=ft.alignment.center,
                content=ft.Column([
                    ft.Icon(ft.icons.UPLOAD_FILE_ROUNDED, size=48, color=GREEN),
                    ft.Container(height=12),
                    ft.Text(
                        "Suelta los archivos aquí para instalar",
                        color=GREEN, size=14, weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ),
            on_accept=self._on_drop_accept,
            on_will_accept=lambda e: self._show_drop_zone(True),
            on_leave=lambda e: self._show_drop_zone(False),
        )

        list_area = ft.Stack([
            self._list_col,
            ft.Column([self._drop_zone], expand=True),
        ], expand=True)

        self.root = ft.Container(
            expand=True, bgcolor=BG,
            padding=ft.padding.symmetric(horizontal=24, vertical=20),
            content=ft.Column([
                cat_row,
                ft.Container(height=14),
                ft.Row([self._search_field], spacing=8),
                ft.Container(height=8),
                filter_row,
                ft.Container(height=12),
                toolbar,
                ft.Container(height=10),
                self._undo_banner,
                ft.Container(height=4, visible=False),
                list_area,
            ], spacing=0, expand=True),
        )

    def _fetch_modrinth_icons(self, items: list[ContentItem]) -> None:
        """Busca los iconos de los mods en Modrinth por nombre de archivo (SHA1)."""
        import urllib.request, json, hashlib

        headers = {"User-Agent": "PyLauncher/1.0"}

        for item in items:
            if self._cancel.is_set():
                return
            if not item["path"].endswith((".jar", ".zip")):
                continue
            try:
                # Calcular SHA1 del archivo
                sha1 = hashlib.sha1()
                with open(item["path"], "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        sha1.update(chunk)
                hash_str = sha1.hexdigest()

                url = f"https://api.modrinth.com/v2/version_file/{hash_str}?algorithm=sha1"
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = json.loads(r.read())

                project_id = data.get("project_id", "")
                if not project_id:
                    continue

                url2 = f"https://api.modrinth.com/v2/project/{project_id}"
                req2 = urllib.request.Request(url2, headers=headers)
                with urllib.request.urlopen(req2, timeout=8) as r2:
                    proj = json.loads(r2.read())

                item["icon_url"] = proj.get("icon_url") or ""
                self.page.run_thread(self._refresh_list)
            except Exception:
                pass

    # =========================================================================
    # Category pills
    # =========================================================================
    def _make_cat_pill(self, cat: str) -> ft.Container:
        active = cat == self._active_cat
        pill   = ft.Container(
            bgcolor=GREEN if active else "transparent",
            border=ft.border.all(1, GREEN if active else BORDER),
            border_radius=20,
            padding=ft.padding.symmetric(horizontal=18, vertical=8),
            animate=ft.animation.Animation(130, ft.AnimationCurve.EASE_OUT),
            on_click=lambda e, c=cat: self._switch_cat(c),
            content=ft.Text(
                cat,
                color=TEXT_INV if active else TEXT_SEC,
                size=11, weight=ft.FontWeight.W_600,
            ),
        )
        pill.on_hover = lambda e, p=pill, c=cat: (
            None if c == self._active_cat else (
                setattr(p, "bgcolor",
                        CARD2_BG if e.data == "true" else "transparent")
                or p.update()
            )
        )
        return pill

    def _switch_cat(self, cat: str) -> None:
        self._active_cat   = cat
        self._selected.clear()
        self._bulk_delete_btn.visible = False
        try: self._bulk_delete_btn.update()
        except Exception: pass

        for c, pill in self._cat_btns.items():
            active = c == cat
            pill.bgcolor = GREEN if active else "transparent"
            pill.border  = ft.border.all(1, GREEN if active else BORDER)
            pill.content.color = TEXT_INV if active else TEXT_SEC
            try: pill.update()
            except Exception: pass

        self._refresh_list()

    # =========================================================================
    # Filter chips
    # =========================================================================
    def _make_filter_chip(self, label: str, value: Optional[bool]) -> ft.Container:
        active = self._filter_enabled == value
        chip   = ft.Container(
            bgcolor=CARD2_BG if active else "transparent",
            border=ft.border.all(1, GREEN if active else BORDER),
            border_radius=16,
            padding=ft.padding.symmetric(horizontal=12, vertical=5),
            animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
            on_click=lambda e, v=value: self._set_filter(v),
            content=ft.Text(
                label,
                color=TEXT_PRI if active else TEXT_DIM,
                size=10, weight=ft.FontWeight.W_500,
            ),
        )
        return chip

    def _set_filter(self, value: Optional[bool]) -> None:
        self._filter_enabled = value
        for chip, v in [
            (self._chip_all,      None),
            (self._chip_enabled,  True),
            (self._chip_disabled, False),
        ]:
            active = v == value
            chip.bgcolor = CARD2_BG if active else "transparent"
            chip.border  = ft.border.all(1, GREEN if active else BORDER)
            chip.content.color = TEXT_PRI if active else TEXT_DIM
            try: chip.update()
            except Exception: pass
        self._refresh_list()

    # =========================================================================
    # P2: debounced search
    # =========================================================================
    def _on_search_change(self, e: ft.ControlEvent) -> None:
        self._search_query = e.control.value.strip().lower()
        if self._debounce_timer:
            self._debounce_timer.cancel()
        self._debounce_timer = threading.Timer(
            _DEBOUNCE_DELAY, self._refresh_list
        )
        self._debounce_timer.start()

    # =========================================================================
    # P3: load items with mtime cache
    # =========================================================================
    def _load_items(self) -> None:
        """Scan all three categories (respects mtime cache)."""
        self._cancel.clear()
        self.page.run_thread(self._show_skeleton)

        for cat in _CATEGORIES:
            if self._cancel.is_set():
                return
            self._scan_category(cat)

        self.page.run_thread(self._refresh_list)

    def _scan_category(self, cat: str) -> None:
        """Scan one category directory; use cached data if mtime unchanged."""
        d    = os.path.join(self.profile.game_dir, _CAT_DIRS[cat])
        exts = _CAT_EXTS[cat]

        if not os.path.isdir(d):
            self._cache[cat] = (0.0, [])
            return

        try:
            mtime = os.path.getmtime(d)
        except OSError:
            mtime = 0.0

        if cat in self._cache and self._cache[cat][0] == mtime:
            return  # P3: unchanged

        items: list[ContentItem] = []
        try:
            for fn in os.listdir(d):
                if self._cancel.is_set():
                    return
                if not any(fn.lower().endswith(x) for x in exts):
                    continue
                path = os.path.join(d, fn)
                item: ContentItem = {
                    "name":     fn,
                    "path":     path,
                    "enabled":  not _is_disabled(fn),
                    "size_mb":  _file_size_mb(path),
                    "icon_url": "",
                    "version":  _parse_version(fn),
                    "category": cat,
                    "mtime":    mtime,
                }
                items.append(item)
        except OSError:
            pass

        self._cache[cat] = (mtime, items)
        threading.Thread(
            target=self._fetch_modrinth_icons,
            args=(items,),
            daemon=True
        ).start()

    # =========================================================================
    # U1: skeleton loader
    # =========================================================================
    def _show_skeleton(self) -> None:
        self._list_col.controls = [self._skeleton_row() for _ in range(5)]
        try: self._list_col.update()
        except Exception: pass

    @staticmethod
    def _skeleton_row() -> ft.Container:
        def _shimmer(w: int, h: int = 12, radius: int = 4) -> ft.Container:
            return ft.Container(
                width=w, height=h,
                border_radius=radius,
                bgcolor=CARD2_BG,
                animate_opacity=ft.animation.Animation(
                    800, ft.AnimationCurve.EASE_IN_OUT
                ),
            )

        return ft.Container(
            bgcolor=INPUT_BG, border_radius=10,
            padding=ft.padding.symmetric(horizontal=16, vertical=14),
            content=ft.Row([
                _shimmer(40, 40, 8),
                ft.Container(width=14),
                ft.Column([
                    _shimmer(180),
                    ft.Container(height=6),
                    _shimmer(100, 9),
                ], spacing=0, expand=True),
                _shimmer(60),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    # =========================================================================
    # Refresh (filter + render)
    # =========================================================================
    def _refresh_list(self) -> None:
        cat   = self._active_cat
        items = self._cache.get(cat, (0.0, []))[1]

        # Apply search filter
        q = self._search_query
        if q:
            items = [i for i in items if q in i["name"].lower()]

        # Apply enabled/disabled filter (U10)
        if self._filter_enabled is True:
            items = [i for i in items if i["enabled"]]
        elif self._filter_enabled is False:
            items = [i for i in items if not i["enabled"]]

        count = len(items)
        noun  = {"Mods": "mod", "Resource Packs": "pack", "Shaders": "shader"}.get(cat, "item")
        self._item_count_lbl.value = (
            f"{count} {noun}{'s' if count != 1 else ''}"
        )
        try: self._item_count_lbl.update()
        except Exception: pass

        self._list_col.controls = (
            [self._item_row(i) for i in items]
            if items else [self._empty_state(cat)]
        )
        try: self._list_col.update()
        except Exception: pass

    def _empty_state(self, cat: str) -> ft.Container:
        verb = "mods" if cat == "Mods" else ("packs" if "Pack" in cat else "shaders")
        return ft.Container(
            expand=True, alignment=ft.alignment.center,
            padding=ft.padding.symmetric(vertical=48),
            content=ft.Column([
                ft.Icon(ft.icons.EXTENSION_OFF_ROUNDED, size=40, color=TEXT_DIM),
                ft.Container(height=12),
                ft.Text(f"Sin {verb} instalados", color=TEXT_SEC, size=13,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER),
                ft.Text(
                    "Pulsa «Añadir» o arrastra archivos aquí.",
                    color=TEXT_DIM, size=10,
                    text_align=ft.TextAlign.CENTER,
                ),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )

    # =========================================================================
    # U11: item row with full-path tooltip
    # =========================================================================
    def _item_row(self, item: ContentItem) -> ft.Container:
        selected  = item["path"] in self._selected
        is_enabled = item["enabled"]

        toggle_icon = (
            ft.icons.TOGGLE_ON_ROUNDED if is_enabled
            else ft.icons.TOGGLE_OFF_ROUNDED
        )
        toggle_color = GREEN if is_enabled else TEXT_DIM

        icon_ctrl = ft.Container(
            width=40, height=40, border_radius=8,
            bgcolor=CARD2_BG, alignment=ft.alignment.center,
            content=ft.Icon(ft.icons.EXTENSION_ROUNDED,
                            color=TEXT_DIM, size=20),
        )

        # Checkbox for multi-select
        checkbox = ft.Checkbox(
            value=selected,
            fill_color={
                ft.MaterialState.SELECTED: GREEN,
                ft.MaterialState.DEFAULT:  "transparent",
            },
            check_color=TEXT_INV,
            on_change=lambda e, p=item["path"]: self._toggle_select(p, e.control.value),
        )

        name_display = item["name"]
        if not is_enabled and name_display.endswith(".disabled"):
            name_display = name_display[:-len(".disabled")]

        size_str = (
            f"{item['size_mb']:.1f} MB"
            if item["size_mb"] >= 0.1
            else f"{int(item['size_mb'] * 1024)} KB"
        )

        row = ft.Container(
            bgcolor=CARD2_BG if selected else INPUT_BG,
            border_radius=10,
            border=ft.border.all(1, GREEN if selected else "transparent"),
            padding=ft.padding.symmetric(horizontal=14, vertical=12),
            animate=ft.animation.Animation(100, ft.AnimationCurve.EASE_OUT),
            tooltip=item["path"],   # U11
            content=ft.Row([
                checkbox,
                ft.Container(width=8),
                icon_ctrl,
                ft.Container(width=14),
                ft.Column([
                    ft.Text(
                        name_display,
                        color=TEXT_PRI if is_enabled else TEXT_DIM,
                        size=11, weight=ft.FontWeight.W_600,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Row([
                        ft.Text(item["version"] or "—",
                                color=TEXT_DIM, size=9),
                        ft.Text("  ·  ", color=TEXT_DIM, size=9),
                        ft.Text(size_str, color=TEXT_DIM, size=9),
                        *(
                            [ft.Text("  ·  ", color=TEXT_DIM, size=9),
                             ft.Text("Desactivado",
                                     color=ACCENT_RED, size=9,
                                     weight=ft.FontWeight.W_500)]
                            if not is_enabled else []
                        ),
                    ], spacing=0),
                ], spacing=3, expand=True),
                # Toggle enable/disable
                ft.IconButton(
                    icon=toggle_icon,
                    icon_color=toggle_color,
                    icon_size=22,
                    tooltip="Activar/Desactivar",
                    on_click=lambda e, i=item: self._toggle_item(i),
                ),
                # Delete
                ft.IconButton(
                    icon=ft.icons.DELETE_OUTLINE_ROUNDED,
                    icon_color=TEXT_DIM,
                    icon_size=18,
                    tooltip="Eliminar",
                    on_click=lambda e, i=item: self._delete_item(i),
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        # P5: fetch icon in background (throttled)
        if item.get("icon_url"):
            self._fetch_icon_async(item, icon_ctrl)

        return row

    # =========================================================================
    # P5: throttled icon fetch
    # =========================================================================
    def _fetch_icon_async(self, item: ContentItem, icon_ctrl: ft.Container) -> None:
        def work() -> None:
            if self._cancel.is_set():
                return
            with _ICON_SEMAPHORE:
                if self._cancel.is_set():
                    return
                try:
                    img = ft.Image(
                        src=item["icon_url"],
                        width=40, height=40,
                        border_radius=8,
                        fit=ft.ImageFit.COVER,
                        error_content=ft.Icon(
                            ft.icons.EXTENSION_ROUNDED,
                            color=TEXT_DIM, size=20,
                        ),
                    )

                    def update_icon(i=img) -> None:
                        icon_ctrl.content = i
                        try: icon_ctrl.update()
                        except Exception: pass

                    self.page.run_thread(update_icon)
                except Exception:
                    pass

        threading.Thread(target=work, daemon=True).start()

    # =========================================================================
    # Toggle enable / disable
    # =========================================================================
    def _toggle_item(self, item: ContentItem) -> None:
        old_path = item["path"]
        if item["enabled"]:
            new_path = _disable_path(old_path)
        else:
            new_path = _enable_path(old_path)
        try:
            os.rename(old_path, new_path)
        except OSError as ex:
            self.app.snack(f"Error: {ex}", error=True)
            return
        # Invalidate cache and reload
        self._invalidate_cache(item["category"])
        threading.Thread(target=self._load_items, daemon=True).start()

    # =========================================================================
    # Delete (single)
    # =========================================================================
    def _delete_item(self, item: ContentItem) -> None:
        try:
            with open(item["path"], "rb") as f:
                data = f.read()
            os.remove(item["path"])
        except OSError as ex:
            self.app.snack(f"Error al eliminar: {ex}", error=True)
            return
        self._invalidate_cache(item["category"])
        self._start_undo([(item["path"], data)], 1)  # U9
        threading.Thread(target=self._load_items, daemon=True).start()

    # =========================================================================
    # Multi-select
    # =========================================================================
    def _toggle_select(self, path: str, checked: bool) -> None:
        if checked:
            self._selected.add(path)
        else:
            self._selected.discard(path)
        self._bulk_delete_btn.visible = bool(self._selected)
        try: self._bulk_delete_btn.update()
        except Exception: pass

    def _on_bulk_delete(self, e: ft.ControlEvent) -> None:
        saved: list[tuple[str, bytes]] = []
        for path in list(self._selected):
            try:
                with open(path, "rb") as f:
                    data = f.read()
                os.remove(path)
                saved.append((path, data))
            except OSError:
                pass
        self._selected.clear()
        self._bulk_delete_btn.visible = False
        try: self._bulk_delete_btn.update()
        except Exception: pass

        if saved:
            # Invalidate caches for affected categories
            for path, _ in saved:
                for cat, dirname in _CAT_DIRS.items():
                    if os.sep + dirname + os.sep in path or \
                       path.startswith(os.path.join(self.profile.game_dir, dirname)):
                        self._invalidate_cache(cat)
            self._start_undo(saved, len(saved))
        threading.Thread(target=self._load_items, daemon=True).start()

    # =========================================================================
    # U9: 5-second undo
    # =========================================================================
    def _start_undo(self, items: list[tuple[str, bytes]], count: int) -> None:
        if self._undo_timer:
            self._undo_timer.cancel()
        self._undo_items = items
        noun = "elemento" if count == 1 else "elementos"
        banner_text: ft.Text = self._undo_banner.content.controls[1]
        banner_text.value = f"{count} {noun} eliminado{'s' if count > 1 else ''}."
        self._undo_banner.visible = True
        try:
            self._undo_banner.update()
        except Exception:
            pass
        self._undo_timer = threading.Timer(5.0, self._dismiss_undo)
        self._undo_timer.start()

    def _dismiss_undo(self) -> None:
        self._undo_items = []

        def hide() -> None:
            self._undo_banner.visible = False
            try: self._undo_banner.update()
            except Exception: pass

        self.page.run_thread(hide)

    def _on_undo(self, e: ft.ControlEvent) -> None:
        if self._undo_timer:
            self._undo_timer.cancel()
        restored = 0
        for path, data in self._undo_items:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(data)
                restored += 1
            except OSError:
                pass
        self._undo_items = []
        self._undo_banner.visible = False
        try: self._undo_banner.update()
        except Exception: pass
        if restored:
            self.app.snack(f"{restored} elemento(s) restaurados.")
        for cat in _CATEGORIES:
            self._invalidate_cache(cat)
        threading.Thread(target=self._load_items, daemon=True).start()

    # =========================================================================
    # Add files
    # =========================================================================
    def _on_add_click(self, e: ft.ControlEvent) -> None:
        cat  = self._active_cat
        exts = [x.lstrip(".").replace(".disabled", "")
                for x in _CAT_EXTS[cat] if not x.endswith(".disabled")]
        exts = list(dict.fromkeys(exts))  # deduplicate
        self._file_picker.pick_files(
            dialog_title=f"Seleccionar {cat}",
            allowed_extensions=exts,
            allow_multiple=True,
        )

    def _on_files_picked(self, e: ft.FilePickerResultEvent) -> None:
        if not e.files:
            return
        cat     = self._active_cat
        dest_d  = os.path.join(self.profile.game_dir, _CAT_DIRS[cat])
        os.makedirs(dest_d, exist_ok=True)
        installed = 0
        for f in e.files:
            # S2: size guard
            try:
                size = os.path.getsize(f.path)
            except OSError:
                size = 0
            if size > _MAX_UPLOAD_BYTES:
                self.app.snack(
                    f"'{f.name}' supera el límite de {_MAX_UPLOAD_MB} MB.",
                    error=True,
                )
                continue
            dest = os.path.join(dest_d, f.name)
            try:
                import shutil
                shutil.copy2(f.path, dest)
                installed += 1
            except Exception as ex:
                self.app.snack(f"Error al copiar '{f.name}': {ex}", error=True)

        if installed:
            self._invalidate_cache(cat)
            self.app.snack(
                f"{installed} archivo(s) instalados en {cat}."
            )
            threading.Thread(target=self._load_items, daemon=True).start()

    # =========================================================================
    # U5: drop zone
    # =========================================================================
    def _show_drop_zone(self, visible: bool) -> None:
        self._drop_zone.visible = visible
        try: self._drop_zone.update()
        except Exception: pass

    def _on_drop_accept(self, e: ft.DragTargetAcceptEvent) -> None:
        self._show_drop_zone(False)
        # Flet drag-drop data is a string path
        path = e.data
        if not path or not os.path.isfile(path):
            return
        # S2
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        if size > _MAX_UPLOAD_BYTES:
            self.app.snack(
                f"El archivo supera el límite de {_MAX_UPLOAD_MB} MB.",
                error=True,
            )
            return
        cat   = self._active_cat
        dest_d = os.path.join(self.profile.game_dir, _CAT_DIRS[cat])
        os.makedirs(dest_d, exist_ok=True)
        dest  = os.path.join(dest_d, os.path.basename(path))
        try:
            import shutil
            shutil.copy2(path, dest)
            self._invalidate_cache(cat)
            self.app.snack(f"'{os.path.basename(path)}' instalado.")
            threading.Thread(target=self._load_items, daemon=True).start()
        except Exception as ex:
            self.app.snack(f"Error: {ex}", error=True)

    # =========================================================================
    # Cache helpers
    # =========================================================================
    def _invalidate_cache(self, cat: str) -> None:
        self._cache.pop(cat, None)

    # =========================================================================
    # B4: destroy – cancel workers, remove FilePicker
    # =========================================================================
    def destroy(self) -> None:
        """Call when this tab is unmounted to stop all background workers."""
        self._cancel.set()
        if self._debounce_timer:
            self._debounce_timer.cancel()
        if self._undo_timer:
            self._undo_timer.cancel()
        if self._file_picker in self.page.overlay:
            self.page.overlay.remove(self._file_picker)
        try:
            self.page.update()
        except Exception:
            pass
