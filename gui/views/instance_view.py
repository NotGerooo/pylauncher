# -*- coding: utf-8 -*-
"""
gui/views/instance_view.py  –  Refactored
Tabs: Content | Files | Worlds | Logs

Changes applied:
  P1  – batch UI updates, reduce redundant run_thread calls
  P2  – debounce search (content_tab.py)
  P3  – mtime-based item cache (content_tab.py)
  P4  – configurable SHA1/icon worker counts via env-vars
  P5  – semaphore guards icon-fetch concurrency (content_tab.py)
  P6  – threading.Event cancellation signal (content_tab.py)
  B1  – removed dead _do_search/_show_results/_select/_do_install/_set_status
        from _InstanceSettingsDialog
  B2  – _rebuild_header no longer calls .update() on stale self.root
  B3  – _OptiFineDialog cleans its FilePicker from page.overlay on close
  B4  – _ContentTab.destroy() removes its FilePicker (content_tab.py)
  B5  – profile.game_dir is created when missing
  B6  – closure defaults explicitly captured in on_more / on_swap
  C1  – _read_loader() is a single module-level helper (no more 5× duplicates)
  C2  – _check_optifine_installed() module-level helper
  C3  – Modrinth constants imported once at module level with fallback
  C4  – _ContentTab lives in content_tab.py
  C5  – on_change callbacks use named setters (in _InstanceSettingsDialog)
  C6  – public methods carry type hints throughout
  C7  – removed dead _make_filter_btn
  C8  – ContentItem TypedDict lives in content_tab.py
  U1  – skeleton loader (content_tab.py)
  U2  – per-tab item-count badge in tab bar
  U3  – opacity fade transition between tabs
  U4  – Play button shows launch stage in real time
  U5  – visual drop-zone (content_tab.py)
  U6  – per-instance notes field shown in header
  U7  – "last played" read from instance_settings.json
  U8  – OptiFine reinstall confirmation dialog
  U9  – 5-second undo after bulk-delete (content_tab.py)
  U10 – 'Disabled' filter chip (content_tab.py)
  U11 – full-path tooltip on content rows (content_tab.py)
  U12 – world size + last-modified date in WorldsTab
  U13 – tail of logs/latest.log in LogsTab
  S1  – sanitise / validate instance_settings.json values on write
  S2  – 500 MB upload guard (content_tab.py)
  S3  – active tab persisted in instance_settings.json
"""

import os
import re
import json
import time
import threading
import datetime
import shutil
from typing import Optional

import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV, ACCENT_RED,
)
from utils.logger import get_logger
from gui.views.content_tab import _ContentTab

log = get_logger()

# ── C3: Modrinth constants loaded once at module level ────────────────────────
try:
    from config.constants import MODRINTH_API_BASE_URL, HTTP_TIMEOUT_SECONDS, USER_AGENT
    _MODRINTH_BASE = MODRINTH_API_BASE_URL
    _HTTP_TIMEOUT  = HTTP_TIMEOUT_SECONDS
    _USER_AGENT    = USER_AGENT
except ImportError:
    _MODRINTH_BASE = "https://api.modrinth.com/v2"
    _HTTP_TIMEOUT  = 15
    _USER_AGENT    = "PyLauncher/1.0"

# ── P4: configurable thread-pool sizes ────────────────────────────────────────
SHA1_WORKERS = int(os.environ.get("PYLAUNCHER_SHA1_WORKERS", "8"))
ICON_WORKERS = int(os.environ.get("PYLAUNCHER_ICON_WORKERS", "6"))
AUTH_WORKERS = int(os.environ.get("PYLAUNCHER_AUTH_WORKERS", "8"))

# ── S2: upload size guard ─────────────────────────────────────────────────────
MAX_UPLOAD_MB = int(os.environ.get("PYLAUNCHER_MAX_UPLOAD_MB", "500"))

LOADER_ICONS = {
    "vanilla":  "Game",
    "fabric":   "Fabric",
    "neoforge": "NeoForge",
    "forge":    "Forge",
    "quilt":    "Quilt",
}

_VALID_LOADERS = ("vanilla", "fabric", "forge", "neoforge", "quilt")
_VALID_TABS    = ("content", "files", "worlds", "logs")

# ── S1: shell-metacharacter guard ─────────────────────────────────────────────
_SHELL_META = re.compile(r"[;&|`\n\r]")
_MIN_RAM_MB = 256
_MAX_RAM_MB = 32_768


# =============================================================================
# C1: module-level loader helper (was duplicated 5×)
# =============================================================================
def _read_loader(game_dir: str) -> str:
    """Return the mod loader type for a given instance directory."""
    meta_path = os.path.join(game_dir, "loader_meta.json")
    if os.path.isfile(meta_path):
        try:
            with open(meta_path) as f:
                meta = json.load(f)
            entries = meta if isinstance(meta, list) else [meta]
            if entries:
                return (
                    entries[0].get("loader_type")
                    or entries[0].get("loader", "vanilla")
                )
        except Exception:
            pass
    return "vanilla"


# =============================================================================
# C2: module-level OptiFine helper (was duplicated in 3 classes)
# =============================================================================
def _check_optifine_installed(
    version_id: str,
    game_dir: str,
    versions_dir: str,
) -> bool:
    try:
        from services.optifine_service import is_optifine_installed
        return is_optifine_installed(version_id, game_dir, versions_dir)
    except Exception:
        return False


# =============================================================================
# S1: settings sanitiser
# =============================================================================
def _sanitize_settings(data: dict) -> dict:
    """Return a sanitised copy of instance-settings data (S1)."""
    out: dict = {}

    # RAM
    try:
        ram = int(data.get("ram_mb", 4096))
    except (TypeError, ValueError):
        ram = 4096
    out["ram_mb"] = max(_MIN_RAM_MB, min(_MAX_RAM_MB, ram))

    # Java path – reject shell metacharacters
    java = str(data.get("java_path", "")).strip()
    out["java_path"] = "" if _SHELL_META.search(java) else java

    # JVM args – strip dangerous characters
    jvm = str(data.get("jvm_args", "")).strip()
    out["jvm_args"] = _SHELL_META.sub("", jvm)

    # Launch hooks – user-trusted, just length-cap
    for key in ("pre_launch", "post_exit"):
        out[key] = str(data.get(key, ""))[:2048].strip()

    # Loader
    loader = str(data.get("loader", "vanilla")).lower()
    if loader not in _VALID_LOADERS:
        loader = "vanilla"
    out["loader"] = loader

    # Notes (U6)
    out["notes"] = str(data.get("notes", ""))[:512]

    # Active tab (S3)
    tab = str(data.get("active_tab", "content"))
    if tab not in _VALID_TABS:
        tab = "content"
    out["active_tab"] = tab

    return out


# =============================================================================
# Misc helpers
# =============================================================================
def _fmt_last_played(ts: Optional[float]) -> str:
    """Format a Unix timestamp as a human-readable 'last played' string (U7)."""
    if not ts:
        return "Never played"
    try:
        dt    = datetime.datetime.fromtimestamp(ts)
        now   = datetime.datetime.now()
        delta = now - dt
        if delta.days == 0:
            h = delta.seconds // 3600
            if h == 0:
                m = delta.seconds // 60
                return f"{m}m ago" if m else "Just now"
            return f"{h}h ago"
        if delta.days == 1:
            return "Yesterday"
        if delta.days < 7:
            return f"{delta.days} days ago"
        return dt.strftime("%d %b %Y")
    except Exception:
        return "Never played"


def _parse_version(filename: str) -> str:
    name = re.sub(r'\.(jar|zip|disabled)$', '', filename, flags=re.IGNORECASE)
    for part in reversed(name.split('-')):
        if re.match(r'^\d+\.\d+', part):
            return part
    return ""


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
        src=url, width=size, height=size,
        border_radius=8, fit=ft.ImageFit.COVER,
        error_content=fallback,
    )


def _read_instance_setting(game_dir: str, key: str, default):
    path = os.path.join(game_dir, "instance_settings.json")
    try:
        if os.path.isfile(path):
            with open(path) as f:
                return json.load(f).get(key, default)
    except Exception:
        pass
    return default


def _write_instance_setting(game_dir: str, key: str, value) -> None:
    path = os.path.join(game_dir, "instance_settings.json")
    data: dict = {}
    try:
        if os.path.isfile(path):
            with open(path) as f:
                data = json.load(f)
    except Exception:
        pass
    data[key] = value
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# =============================================================================
# InstanceView
# =============================================================================
class InstanceView:

    def __init__(self, page: ft.Page, app, profile) -> None:
        self.page    = page
        self.app     = app
        self.profile = profile

        # B5: ensure game_dir exists so all sub-tabs can write freely
        os.makedirs(profile.game_dir, exist_ok=True)

        # S3: restore last-active tab
        self._active_tab: str = _read_instance_setting(
            profile.game_dir, "active_tab", "content"
        )
        if self._active_tab not in _VALID_TABS:
            self._active_tab = "content"

        self._build()

    # ── Build ──────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        loader      = _read_loader(self.profile.game_dir)
        last_played = _fmt_last_played(
            _read_instance_setting(self.profile.game_dir, "last_played", None)
        )
        notes = _read_instance_setting(self.profile.game_dir, "notes", "")

        # U4: Play button – text updated live during launch stages
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

        optifine_installed = _check_optifine_installed(
            self.profile.version_id,
            self.profile.game_dir,
            self.app.settings.versions_dir,
        )
        self._optifine_btn = ft.OutlinedButton(
            "OptiFine ✓" if optifine_installed else "OptiFine",
            icon=ft.icons.SPEED_ROUNDED,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                side=ft.BorderSide(1, GREEN if optifine_installed else BORDER),
                color=GREEN if optifine_installed else TEXT_SEC,
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
            ),
            tooltip="Instalar / gestionar OptiFine",
            on_click=lambda e: self._open_optifine_dialog(),
        )

        # U6: inline notes below subtitle row
        notes_row = ft.Container(
            visible=bool(notes),
            content=ft.Text(notes, color=TEXT_DIM, size=10, italic=True),
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
                        ft.Text(last_played, color=TEXT_DIM, size=11),   # U7
                    ], spacing=0),
                    notes_row,                                             # U6
                ], spacing=4, expand=True),
                ft.Container(expand=True),
                self._optifine_btn,
                ft.Container(width=6),
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

        # U2: count content items for tab badges
        counts = self._count_items()

        tabs_data = [
            ("content", "Content", ft.icons.EXTENSION_ROUNDED,
             sum(counts.values()) or None),
            ("files",   "Files",   ft.icons.FOLDER_ROUNDED,    None),
            ("worlds",  "Worlds",  ft.icons.PUBLIC_ROUNDED,    None),
            ("logs",    "Logs",    ft.icons.TERMINAL_ROUNDED,  None),
        ]
        self._tab_btns: dict[str, ft.Container] = {}
        tab_row = ft.Row(spacing=6, controls=[
            ft.IconButton(
                icon=ft.icons.ARROW_BACK_IOS_NEW_ROUNDED,
                icon_color=TEXT_DIM, icon_size=16,
                tooltip="Volver a Biblioteca",
                on_click=lambda e: self.app._show_view("library"),
            ),
            ft.Container(width=4),
        ])
        for tid, tlabel, ticon, tcount in tabs_data:
            btn = self._make_tab_btn(tid, tlabel, ticon, tcount)
            self._tab_btns[tid] = btn
            tab_row.controls.append(btn)

        tab_bar = ft.Container(
            bgcolor=CARD_BG,
            border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
            padding=ft.padding.symmetric(horizontal=20, vertical=10),
            content=tab_row,
        )

        # U3: opacity-animated container for fade transition between tabs
        self._tab_area = ft.Container(
            expand=True, bgcolor=BG,
            animate_opacity=ft.animation.Animation(130, ft.AnimationCurve.EASE_OUT),
        )

        self.root = ft.Column(
            spacing=0, expand=True,
            controls=[header, tab_bar, self._tab_area],
        )

    def _count_items(self) -> dict[str, int]:
        """Count items per content category for tab badges (U2)."""
        counts: dict[str, int] = {"Mods": 0, "Resource Packs": 0, "Shaders": 0}
        specs = {
            "Mods":           ("mods",          (".jar", ".jar.disabled")),
            "Resource Packs": ("resourcepacks", (".zip", ".zip.disabled")),
            "Shaders":        ("shaderpacks",   (".zip", ".zip.disabled")),
        }
        for cat, (dirname, exts) in specs.items():
            d = os.path.join(self.profile.game_dir, dirname)
            if os.path.isdir(d):
                counts[cat] = sum(
                    1 for fn in os.listdir(d)
                    if any(fn.lower().endswith(x) for x in exts)
                )
        return counts

    # ── Tab buttons ────────────────────────────────────────────────────────────
    def _make_tab_btn(
        self,
        tid: str,
        label: str,
        icon,
        count: Optional[int],
    ) -> ft.Container:
        active     = tid == self._active_tab
        label_text = label if not count else f"{label}  {count}"
        btn = ft.Container(
            bgcolor=GREEN if active else "transparent",
            border_radius=20,
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
            animate=ft.animation.Animation(150, ft.AnimationCurve.EASE_OUT),
            on_click=lambda e, t=tid: self._switch_tab(t),
            content=ft.Row([
                ft.Icon(icon, size=14, color=TEXT_INV if active else TEXT_SEC),
                ft.Container(width=6),
                ft.Text(label_text,
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

    def _switch_tab(self, tid: str) -> None:
        self._active_tab = tid
        _write_instance_setting(self.profile.game_dir, "active_tab", tid)  # S3

        # U3: fade out first
        self._tab_area.opacity = 0
        try: self._tab_area.update()
        except Exception: pass

        tabs_data = [
            ("content", "Content", ft.icons.EXTENSION_ROUNDED),
            ("files",   "Files",   ft.icons.FOLDER_ROUNDED),
            ("worlds",  "Worlds",  ft.icons.PUBLIC_ROUNDED),
            ("logs",    "Logs",    ft.icons.TERMINAL_ROUNDED),
        ]
        for (t, label, icon), btn in zip(tabs_data, self._tab_btns.values()):
            active    = t == tid
            btn.bgcolor = GREEN if active else "transparent"
            row: ft.Row = btn.content
            row.controls[0].color = TEXT_INV if active else TEXT_SEC
            row.controls[2].color = TEXT_INV if active else TEXT_SEC
            try: btn.update()
            except Exception: pass

        self._render_tab()

        # U3: fade in
        self._tab_area.opacity = 1
        try: self._tab_area.update()
        except Exception: pass

    def on_show(self) -> None:
        self._render_tab()

    def _render_tab(self) -> None:
        if self._active_tab == "content":
            if not hasattr(self, "_content_tab_obj"):
                self._content_tab_obj = _ContentTab(self.page, self.app, self.profile)
            self._tab_area.content = self._content_tab_obj.root

        elif self._active_tab == "files":
            if not hasattr(self, "_files_tab_obj"):
                self._files_tab_obj = _FilesTab(self.page, self.app, self.profile)
            self._tab_area.content = self._files_tab_obj.root

        elif self._active_tab == "worlds":
            # Always rebuild worlds tab to pick up newly created worlds
            self._worlds_tab_obj = _WorldsTab(self.page, self.app, self.profile)
            self._tab_area.content = self._worlds_tab_obj.root

        elif self._active_tab == "logs":
            if not hasattr(self, "_logs_tab_obj"):
                self._logs_tab_obj = _LogsTab(self.page, self.app, self.profile)
            else:
                self._logs_tab_obj.on_show()
            self._tab_area.content = self._logs_tab_obj.root

        try: self._tab_area.update()
        except Exception: pass

    # ── B2: _rebuild_header must NOT call update() on the stale old root ───────
    def _rebuild_header(self) -> None:
        """
        Rebuild the whole view after an OptiFine state change.
        The parent must re-attach self.root; calling update() on the stale
        reference is incorrect, so we intentionally omit it here.
        """
        self._build()

    # ── U4: Play with live stage feedback ─────────────────────────────────────
    def _set_play_status(self, text: str, *, disabled: bool = True) -> None:
        self._play_btn.text     = text
        self._play_btn.disabled = disabled
        try: self._play_btn.update()
        except Exception: pass

    def _on_play(self, e: ft.ControlEvent) -> None:
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
        self._set_play_status("Preparando…")

        try:
            session      = self.app.auth_service.create_offline_session(username)
            version_data = self.app.version_manager.get_version_data(
                self.profile.version_id
            )
        except Exception as ex:
            msg = str(ex)
            log.error(f"Launch error: {msg}")
            self._set_play_status("Play", disabled=False)
            self.app.snack(msg, error=True)
            return

        def run() -> None:
            try:
                self.page.run_thread(
                    lambda: self._set_play_status("Lanzando…")
                )
                process = self.app.launcher_engine.launch(
                    self.profile, session, version_data,
                    on_output=lambda line: log.info(f"[MC] {line}"),
                )
                self._persist_last_played()
                self.app.settings.last_profile = self.profile.name
                self.app.profile_manager.mark_as_used(self.profile.id)

                self.page.run_thread(
                    lambda: self._set_play_status("Jugando…")
                )
                process.wait()
                rc = process.returncode

                def done() -> None:
                    self._set_play_status("Play", disabled=False)
                    if rc != 0:
                        self.app.snack(
                            f"Minecraft cerró con error (código {rc}).",
                            error=True,
                        )
                self.page.run_thread(done)

            except Exception as ex:
                msg = str(ex)
                log.error(f"Launch error: {msg}")
                def err(_m: str = msg) -> None:
                    self._set_play_status("Play", disabled=False)
                    self.app.snack(_m, error=True)
                self.page.run_thread(err)

        threading.Thread(target=run, daemon=True).start()
        self.app.snack(
            f"Iniciando Minecraft {self.profile.version_id} como {username}…"
        )

    def _persist_last_played(self) -> None:
        """Write current timestamp as last_played into instance_settings.json (U7)."""
        try:
            _write_instance_setting(
                self.profile.game_dir, "last_played", time.time()
            )
        except Exception:
            pass

    # ── Edit / OptiFine dialogs ────────────────────────────────────────────────
    def _open_edit(self) -> None:
        def done(updated_profile=None) -> None:
            if updated_profile:
                self.profile = updated_profile
            else:
                updated = self.app.profile_manager.get_profile(self.profile.id)
                if updated:
                    self.profile = updated
            self._build()
            try: self.root.update()
            except Exception: pass

        _InstanceSettingsDialog(self.page, self.app, self.profile, on_done=done)

    def _open_optifine_dialog(self) -> None:
        _OptiFineDialog(
            self.page, self.app, self.profile,
            on_done=lambda: self._rebuild_header(),
        )


# =============================================================================
# OptiFine Dialog
# =============================================================================
class _OptiFineDialog:
    """
    Two installation modes:
      • Installer – runs the official .jar to create a standalone version
      • Mod       – copies the .jar into /mods (requires Forge/NeoForge)

    B3: FilePicker is removed from page.overlay when the dialog closes.
    U8: Confirms before overwriting an existing OptiFine installation.
    """

    def __init__(self, page: ft.Page, app, profile, on_done=None) -> None:
        self.page    = page
        self.app     = app
        self.profile = profile
        self.on_done = on_done
        self._mode   = "installer"
        self._versions: list[dict] = []
        self._selected_version: Optional[dict] = None
        self._build()

    # ── Build ──────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        loader = _read_loader(self.profile.game_dir)

        title_row = ft.Row([
            ft.Container(
                width=40, height=40, border_radius=10,
                bgcolor="#1a2d1a",
                border=ft.border.all(1, "#2a5a2a"),
                alignment=ft.alignment.center,
                content=ft.Icon(ft.icons.SPEED_ROUNDED, size=20, color=GREEN),
            ),
            ft.Container(width=14),
            ft.Column([
                ft.Text("OptiFine", color=TEXT_PRI, size=16,
                        weight=ft.FontWeight.BOLD),
                ft.Text(
                    f"Minecraft {self.profile.version_id}  ·  {loader.capitalize()}",
                    color=TEXT_DIM, size=10,
                ),
            ], spacing=2),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

        self._mode_installer_btn = self._mode_pill("Installer", "installer")
        self._mode_mod_btn       = self._mode_pill("Mod (Forge)", "mod")
        mode_row = ft.Row(
            [self._mode_installer_btn, ft.Container(width=8), self._mode_mod_btn],
            spacing=0,
        )

        self._mode_info = ft.Text(
            self._mode_description(), color=TEXT_DIM, size=10
        )

        self._ver_dd = ft.Dropdown(
            hint_text="Cargando versiones…",
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, height=44,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=8),
            text_style=ft.TextStyle(size=12),
            options=[],
            on_change=self._on_version_change,
        )

        # B3: track the picker so we can remove it from overlay on close
        self._file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self.page.overlay.append(self._file_picker)
        self.page.update()

        self._progress = ft.ProgressBar(
            value=0, color=GREEN, bgcolor=CARD2_BG,
            border_radius=4, height=6, visible=False,
        )
        self._status_lbl = ft.Text("", color=TEXT_SEC, size=10)

        self._install_btn = ft.ElevatedButton(
            "Instalar OptiFine",
            icon=ft.icons.DOWNLOAD_ROUNDED,
            bgcolor=GREEN, color=TEXT_INV,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=20, vertical=12),
            ),
            on_click=self._on_install,
            disabled=True,
        )
        local_btn = ft.OutlinedButton(
            "Instalar desde archivo…",
            icon=ft.icons.UPLOAD_FILE_ROUNDED,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                side=ft.BorderSide(1, BORDER), color=TEXT_SEC,
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
            ),
            on_click=lambda e: self._file_picker.pick_files(
                dialog_title="Seleccionar OptiFine .jar",
                allowed_extensions=["jar"],
            ),
        )

        already = _check_optifine_installed(
            self.profile.version_id,
            self.profile.game_dir,
            self.app.settings.versions_dir,
        )
        uninstall_btn = ft.TextButton(
            "Desinstalar OptiFine",
            icon=ft.icons.DELETE_OUTLINE_ROUNDED,
            style=ft.ButtonStyle(color=ACCENT_RED),
            visible=already,
            on_click=self._on_uninstall,
        )
        self._installed_badge = ft.Container(
            visible=already,
            bgcolor="#1a3d2a",
            border=ft.border.all(1, "#2a5a2a"),
            border_radius=6,
            padding=ft.padding.symmetric(horizontal=10, vertical=4),
            content=ft.Row([
                ft.Icon(ft.icons.CHECK_CIRCLE_ROUNDED, size=12, color=GREEN),
                ft.Container(width=6),
                ft.Text("OptiFine instalado", color=GREEN, size=10,
                        weight=ft.FontWeight.W_600),
            ], spacing=0, tight=True),
        )

        loader_lower = loader.lower()
        self._forge_warning = ft.Container(
            visible=(self._mode == "mod" and
                     loader_lower not in ("forge", "neoforge")),
            bgcolor="#2d1a00",
            border=ft.border.all(1, "#5a3a00"),
            border_radius=8,
            padding=ft.padding.all(12),
            content=ft.Row([
                ft.Icon(ft.icons.WARNING_AMBER_ROUNDED, size=16, color="#ffa94d"),
                ft.Container(width=10),
                ft.Text(
                    "El modo Mod requiere Forge o NeoForge.\n"
                    f"Esta instancia usa {loader.capitalize()}.",
                    color="#ffa94d", size=10,
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.START),
        )

        content = ft.Column([
            title_row,
            ft.Container(height=20),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            ft.Text("Modo de instalación", color=TEXT_PRI, size=12,
                    weight=ft.FontWeight.BOLD),
            ft.Container(height=8),
            mode_row,
            ft.Container(height=8),
            self._mode_info,
            ft.Container(height=16),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            ft.Text("Versión de OptiFine", color=TEXT_PRI, size=12,
                    weight=ft.FontWeight.BOLD),
            ft.Container(height=8),
            self._ver_dd,
            ft.Container(height=8),
            self._forge_warning,
            ft.Container(height=16),
            self._progress,
            ft.Container(height=4),
            self._status_lbl,
            ft.Container(height=16),
            ft.Row([
                self._installed_badge,
                ft.Container(expand=True),
                uninstall_btn,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=8),
            ft.Row([
                local_btn,
                ft.Container(expand=True),
                ft.TextButton(
                    "Cancelar",
                    style=ft.ButtonStyle(color=TEXT_SEC),
                    on_click=lambda e: self._close(),
                ),
                ft.Container(width=8),
                self._install_btn,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=0, scroll=ft.ScrollMode.AUTO)

        self._dlg = ft.AlertDialog(
            modal=True, bgcolor=CARD_BG,
            content_padding=ft.padding.all(28),
            title=ft.Container(),
            content=ft.Container(width=480, content=content),
            actions=[],
        )
        self.page.open(self._dlg)
        threading.Thread(target=self._load_versions, daemon=True).start()

    # ── B3: clean up FilePicker on close ──────────────────────────────────────
    def _close(self) -> None:
        self.page.close(self._dlg)
        if self._file_picker in self.page.overlay:
            self.page.overlay.remove(self._file_picker)
        try: self.page.update()
        except Exception: pass

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _mode_description(self) -> str:
        if self._mode == "installer":
            return (
                "Ejecuta el instalador oficial de OptiFine. Crea una nueva versión "
                "standalone en el launcher. Compatible con Vanilla y Forge."
            )
        return (
            "Copia OptiFine como mod en la carpeta /mods. "
            "Solo funciona con Forge o NeoForge como loader."
        )

    def _mode_pill(self, label: str, mode: str) -> ft.Container:
        active = self._mode == mode
        pill   = ft.Container(
            bgcolor=GREEN if active else INPUT_BG,
            border=ft.border.all(1, GREEN if active else BORDER),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=16, vertical=9),
            animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
            content=ft.Text(label,
                            color=TEXT_INV if active else TEXT_SEC,
                            size=11, weight=ft.FontWeight.W_600),
        )
        def on_click(e, m=mode) -> None:
            self._mode = m
            for btn, bmode in [
                (self._mode_installer_btn, "installer"),
                (self._mode_mod_btn,       "mod"),
            ]:
                a = bmode == m
                btn.bgcolor       = GREEN if a else INPUT_BG
                btn.border        = ft.border.all(1, GREEN if a else BORDER)
                btn.content.color = TEXT_INV if a else TEXT_SEC
                try: btn.update()
                except Exception: pass
            self._mode_info.value = self._mode_description()
            try: self._mode_info.update()
            except Exception: pass
            loader = _read_loader(self.profile.game_dir).lower()
            self._forge_warning.visible = (
                m == "mod" and loader not in ("forge", "neoforge")
            )
            try: self._forge_warning.update()
            except Exception: pass

        pill.on_click = on_click
        return pill

    def _load_versions(self) -> None:
        try:
            from services.optifine_service import get_optifine_versions
            versions = get_optifine_versions(self.profile.version_id)
        except Exception as e:
            versions = []
            log.warning(f"OptiFine: {e}")

        def update_ui() -> None:
            self._versions = versions
            if versions:
                self._ver_dd.options   = [
                    ft.dropdown.Option(v["name"], v["label"]) for v in versions
                ]
                self._ver_dd.value          = versions[0]["name"]
                self._selected_version      = versions[0]
                self._install_btn.disabled  = False
                self._ver_dd.hint_text      = None
            else:
                self._ver_dd.hint_text      = (
                    f"Sin versiones para MC {self.profile.version_id}. "
                    "Usa 'Instalar desde archivo'."
                )
                self._install_btn.disabled  = True
            try:
                self._ver_dd.update()
                self._install_btn.update()
            except Exception:
                pass

        self.page.run_thread(update_ui)

    def _on_version_change(self, e: ft.ControlEvent) -> None:
        name = e.control.value
        self._selected_version = next(
            (v for v in self._versions if v["name"] == name), None
        )

    # ── U8: confirm before reinstalling ───────────────────────────────────────
    def _on_install(self, e: ft.ControlEvent) -> None:
        if not self._selected_version:
            return
        already = _check_optifine_installed(
            self.profile.version_id,
            self.profile.game_dir,
            self.app.settings.versions_dir,
        )
        if already:
            def confirm(ev: ft.ControlEvent) -> None:
                self.page.close(confirm_dlg)
                if ev.control.data == "yes":
                    self._start_install(self._selected_version)

            confirm_dlg = ft.AlertDialog(
                modal=True, bgcolor=CARD_BG,
                title=ft.Text("¿Reinstalar OptiFine?", color=TEXT_PRI,
                              weight=ft.FontWeight.BOLD),
                content=ft.Text(
                    "OptiFine ya está instalado en esta instancia. "
                    "¿Deseas reemplazarlo con la versión seleccionada?",
                    color=TEXT_SEC, size=12,
                ),
                actions=[
                    ft.TextButton("Cancelar",
                                  style=ft.ButtonStyle(color=TEXT_SEC),
                                  on_click=confirm),
                    ft.ElevatedButton(
                        "Reinstalar",
                        data="yes",
                        bgcolor=GREEN, color=TEXT_INV,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=confirm,
                    ),
                ],
            )
            self.page.open(confirm_dlg)
        else:
            self._start_install(self._selected_version)

    def _start_install(self, version_info: dict) -> None:
        self._set_busy(True, "Preparando…")
        threading.Thread(
            target=self._do_install,
            args=(version_info,),
            daemon=True,
        ).start()

    def _do_install(self, version_info: dict) -> None:
        try:
            from services.optifine_service import (
                install_optifine_standalone,
                install_optifine_as_mod,
            )
            from managers.loader_manager import save_optifine_version_id

            mods_dir = os.path.join(self.profile.game_dir, "mods")
            java     = self._get_java()

            def prog(msg: str) -> None:
                self.page.run_thread(lambda m=msg: self._set_status(m))

            if self._mode == "installer":
                version_id = install_optifine_standalone(
                    mc_version=self.profile.version_id,
                    optifine_filename=version_info["name"],
                    versions_dir=self.app.settings.versions_dir,
                    java_path=java,
                    progress_callback=prog,
                )
                save_optifine_version_id(self.profile.game_dir, version_id)
                self.page.run_thread(
                    lambda: self._on_success(f"OptiFine instalado: {version_id}")
                )
            else:
                install_optifine_as_mod(
                    optifine_filename=version_info["name"],
                    mods_dir=mods_dir,
                    versions_dir=self.app.settings.versions_dir,
                    progress_callback=prog,
                )
                self.page.run_thread(
                    lambda: self._on_success("OptiFine copiado a /mods")
                )
        except Exception as ex:
            self.page.run_thread(lambda e=ex: self._on_error(str(e)))

    def _on_file_picked(self, e: ft.FilePickerResultEvent) -> None:
        if not e.files:
            return
        jar_path = e.files[0].path
        self._set_busy(True, "Instalando desde archivo…")
        threading.Thread(
            target=self._do_install_from_file,
            args=(jar_path,), daemon=True,
        ).start()

    def _do_install_from_file(self, jar_path: str) -> None:
        try:
            from services.optifine_service import install_optifine_from_file
            from managers.loader_manager import save_optifine_version_id

            mods_dir = os.path.join(self.profile.game_dir, "mods")
            java     = self._get_java()

            def prog(msg: str) -> None:
                self.page.run_thread(lambda m=msg: self._set_status(m))

            result = install_optifine_from_file(
                jar_path=jar_path,
                mode=self._mode,
                mods_dir=mods_dir,
                versions_dir=self.app.settings.versions_dir,
                mc_version=self.profile.version_id,
                java_path=java,
                progress_callback=prog,
            )
            if self._mode == "installer":
                save_optifine_version_id(self.profile.game_dir, result)
            self.page.run_thread(lambda: self._on_success("OptiFine instalado ✓"))
        except Exception as ex:
            self.page.run_thread(lambda e=ex: self._on_error(str(e)))

    def _on_uninstall(self, e: ft.ControlEvent) -> None:
        from managers.loader_manager import clear_optifine_version_id
        mods_dir = os.path.join(self.profile.game_dir, "mods")
        if os.path.isdir(mods_dir):
            for fn in os.listdir(mods_dir):
                if "optifine" in fn.lower():
                    try: os.remove(os.path.join(mods_dir, fn))
                    except OSError: pass
        clear_optifine_version_id(self.profile.game_dir)
        self._installed_badge.visible = False
        try: self._installed_badge.update()
        except Exception: pass
        self.app.snack("OptiFine desinstalado.")
        if self.on_done:
            self.on_done()

    # ── UI helpers ─────────────────────────────────────────────────────────────
    def _get_java(self) -> Optional[str]:
        return _read_instance_setting(self.profile.game_dir, "java_path", None) or None

    def _set_busy(self, busy: bool, msg: str = "") -> None:
        self._install_btn.disabled = busy
        self._progress.visible     = busy
        self._progress.value       = None if busy else 0
        self._status_lbl.value     = msg
        try:
            self._install_btn.update()
            self._progress.update()
            self._status_lbl.update()
        except Exception:
            pass

    def _set_status(self, msg: str) -> None:
        self._status_lbl.value = msg
        try: self._status_lbl.update()
        except Exception: pass

    def _on_success(self, msg: str) -> None:
        self._set_busy(False, msg)
        self._installed_badge.visible = True
        try: self._installed_badge.update()
        except Exception: pass
        self.app.snack(msg)
        if self.on_done:
            self.on_done()

    def _on_error(self, msg: str) -> None:
        self._set_busy(False, f"Error: {msg}")
        self.app.snack(msg, error=True)


# =============================================================================
# Instance Settings Dialog
# =============================================================================
class _InstanceSettingsDialog:
    """
    Four sections: General | Installation | Java & Memory | Launch Hooks
    B1: dead methods (_do_search, _show_results, _select, _do_install,
        _set_status) have been removed — they belonged to an old dialog.
    C5: on_change uses named setter methods instead of setattr lambdas.
    S1: _write_meta sanitises values before persisting.
    """

    _SECTIONS = [
        ("general",      ft.icons.TUNE_ROUNDED,      "General"),
        ("installation", ft.icons.EXTENSION_ROUNDED, "Installation"),
        ("java",         ft.icons.MEMORY_ROUNDED,    "Java & Memory"),
        ("hooks",        ft.icons.CODE_ROUNDED,      "Launch Hooks"),
    ]
    _LOADERS = ["Vanilla", "Fabric", "NeoForge", "Forge", "Quilt"]

    def __init__(self, page: ft.Page, app, profile, on_done=None) -> None:
        self.page     = page
        self.app      = app
        self.profile  = profile
        self.on_done  = on_done
        self._section = "general"

        # Editable state
        self._name_val    = profile.name
        self._loader_val  = self._detect_loader()
        self._version_val = profile.version_id
        self._ram_val     = self._read_meta("ram_mb",     4096)
        self._java_val    = self._read_meta("java_path",  "")
        self._jvm_val     = self._read_meta("jvm_args",   "")
        self._pre_val     = self._read_meta("pre_launch", "")
        self._post_val    = self._read_meta("post_exit",  "")
        self._notes_val   = self._read_meta("notes",      "")   # U6

        self._build()

    # ── C5: named setter methods ───────────────────────────────────────────────
    def _set_name(self, e: ft.ControlEvent)    -> None: self._name_val    = e.control.value
    def _set_version(self, e: ft.ControlEvent) -> None: self._version_val = e.control.value
    def _set_ram(self, e: ft.ControlEvent)     -> None:
        try:    self._ram_val = int(e.control.value or 4096)
        except: self._ram_val = 4096
    def _set_java(self, e: ft.ControlEvent)    -> None: self._java_val    = e.control.value
    def _set_jvm(self, e: ft.ControlEvent)     -> None: self._jvm_val     = e.control.value
    def _set_pre(self, e: ft.ControlEvent)     -> None: self._pre_val     = e.control.value
    def _set_post(self, e: ft.ControlEvent)    -> None: self._post_val    = e.control.value
    def _set_notes(self, e: ft.ControlEvent)   -> None: self._notes_val   = e.control.value

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _detect_loader(self) -> str:
        ld = _read_loader(self.profile.game_dir)
        return ld.capitalize()

    def _read_meta(self, key: str, default):
        return _read_instance_setting(self.profile.game_dir, key, default)

    def _write_meta(self, updates: dict) -> None:
        """Write instance settings with S1 sanitisation."""
        path = os.path.join(self.profile.game_dir, "instance_settings.json")
        data: dict = {}
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    data = json.load(f)
            except Exception:
                pass
        data.update(updates)
        sanitised = _sanitize_settings(data)
        # Preserve keys not managed by sanitiser
        for k, v in data.items():
            if k not in sanitised:
                sanitised[k] = v
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(sanitised, f, indent=2)

    # ── Build ──────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        self._nav_items: dict[str, ft.Container] = {}
        nav_col = ft.Column(spacing=2)
        for sid, icon, label in self._SECTIONS:
            item = self._make_nav_item(sid, icon, label)
            self._nav_items[sid] = item
            nav_col.controls.append(item)

        sidebar = ft.Container(
            width=200, bgcolor=CARD2_BG,
            border=ft.border.only(right=ft.BorderSide(1, BORDER)),
            padding=ft.padding.symmetric(horizontal=10, vertical=16),
            content=nav_col,
        )

        self._content_area = ft.Container(
            expand=True, padding=ft.padding.all(28),
            content=self._render_section(self._section),
        )

        self._save_btn = ft.ElevatedButton(
            "Save changes",
            bgcolor=GREEN, color=TEXT_INV,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=24, vertical=12),
            ),
            on_click=self._on_save,
        )

        self._breadcrumb = ft.Text(
            "General", color=TEXT_PRI, size=15, weight=ft.FontWeight.BOLD,
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
            modal=True, bgcolor=CARD_BG,
            title=ft.Container(),
            content_padding=ft.padding.all(0),
            content=ft.Container(
                width=820, height=520, bgcolor=CARD_BG,
                border_radius=12,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                content=ft.Column([
                    header,
                    ft.Row([sidebar, self._content_area], spacing=0, expand=True),
                ], spacing=0, expand=True),
            ),
            actions=[],
        )
        self.page.open(self._dlg)

    def _make_nav_item(self, sid: str, icon, label: str) -> ft.Container:
        active = sid == self._section
        item   = ft.Container(
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
                        weight=(ft.FontWeight.W_600 if active
                                else ft.FontWeight.NORMAL)),
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

    def _switch_section(self, sid: str) -> None:
        self._section = sid
        label_map = {s: l for s, _, l in self._SECTIONS}
        for s, icon, label in self._SECTIONS:
            item   = self._nav_items[s]
            active = s == sid
            item.bgcolor = GREEN if active else "transparent"
            row: ft.Row  = item.content
            row.controls[0].color  = TEXT_INV if active else TEXT_DIM
            row.controls[2].color  = TEXT_INV if active else TEXT_SEC
            row.controls[2].weight = (ft.FontWeight.W_600 if active
                                      else ft.FontWeight.NORMAL)
            try: item.update()
            except Exception: pass
        self._breadcrumb.value = label_map[sid]
        try: self._breadcrumb.update()
        except Exception: pass
        self._content_area.content = self._render_section(sid)
        try: self._content_area.update()
        except Exception: pass

    # ── Section renderers ──────────────────────────────────────────────────────
    def _render_section(self, sid: str) -> ft.Control:
        if sid == "general":      return self._section_general()
        if sid == "installation": return self._section_installation()
        if sid == "java":         return self._section_java()
        if sid == "hooks":        return self._section_hooks()
        return ft.Container()

    def _heading(self, text: str) -> ft.Text:
        return ft.Text(text, color=TEXT_PRI, size=13, weight=ft.FontWeight.BOLD)

    def _subtext(self, text: str) -> ft.Text:
        return ft.Text(text, color=TEXT_DIM, size=10)

    # General ──────────────────────────────────────────────────────────────────
    def _section_general(self) -> ft.Column:
        self._name_field = ft.TextField(
            value=self._name_val,
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, height=42,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            text_size=12,
            on_change=self._set_name,          # C5
        )

        # U6: notes field in General section
        self._notes_field = ft.TextField(
            value=self._notes_val,
            hint_text="Notas sobre esta instancia (visible en el header)…",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=11),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, min_lines=2, max_lines=3,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            text_size=12,
            on_change=self._set_notes,         # C5
        )

        icon_box = ft.Container(
            width=80, height=80, border_radius=14,
            bgcolor=CARD2_BG, alignment=ft.alignment.center,
            border=ft.border.all(1, BORDER),
            content=ft.Icon(ft.icons.WIDGETS_ROUNDED, size=36, color=TEXT_DIM),
        )

        def on_duplicate(e: ft.ControlEvent) -> None:
            self.page.close(self._dlg)
            self._duplicate_instance()

        def on_delete(e: ft.ControlEvent) -> None:
            self.page.close(self._dlg)
            self._confirm_delete()

        return ft.Column([
            ft.Row([
                ft.Column([
                    self._heading("Instance name"),
                    ft.Container(height=6),
                    self._name_field,
                ], spacing=0, expand=True),
                ft.Container(width=20),
                icon_box,
            ], vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Container(height=16),
            self._heading("Notes"),
            ft.Container(height=4),
            self._subtext("Descripción corta visible en el header de la instancia."),
            ft.Container(height=10),
            self._notes_field,
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            self._heading("Duplicate instance"),
            ft.Container(height=4),
            self._subtext(
                "Creates a copy of this instance, including worlds, configs, mods, etc."
            ),
            ft.Container(height=10),
            ft.OutlinedButton(
                "Duplicate",
                icon=ft.icons.COPY_ALL_ROUNDED,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    side=ft.BorderSide(1, BORDER), color=TEXT_SEC,
                    padding=ft.padding.symmetric(horizontal=16, vertical=10),
                ),
                on_click=on_duplicate,
            ),
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            self._heading("Delete instance"),
            ft.Container(height=4),
            self._subtext(
                "Permanently deletes this instance from your device, including worlds, "
                "configs,\nand all installed content. This action cannot be undone."
            ),
            ft.Container(height=10),
            ft.ElevatedButton(
                "Delete instance",
                icon=ft.icons.DELETE_FOREVER_ROUNDED,
                bgcolor=ACCENT_RED, color="#ffffff",
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.padding.symmetric(horizontal=16, vertical=10),
                ),
                on_click=on_delete,
            ),
        ], spacing=0, scroll=ft.ScrollMode.AUTO)

    # Installation ─────────────────────────────────────────────────────────────
    def _section_installation(self) -> ft.Column:
        self._loader_btns: dict[str, ft.Container] = {}
        loader_row = ft.Row(spacing=8, wrap=True)
        for ld in self._LOADERS:
            btn = self._loader_pill(ld)
            self._loader_btns[ld] = btn
            loader_row.controls.append(btn)

        versions = [self.profile.version_id]
        try:
            all_v    = self.app.version_manager.get_available_versions()
            versions = [v.id if hasattr(v, "id") else str(v) for v in all_v] or versions
        except Exception:
            pass

        self._version_dd = ft.Dropdown(
            value=self._version_val,
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, height=42,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=8),
            text_style=ft.TextStyle(size=12),
            options=[ft.dropdown.Option(v) for v in versions],
            on_change=self._set_version,       # C5
        )

        optifine_installed = _check_optifine_installed(
            self.profile.version_id, self.profile.game_dir,
            self.app.settings.versions_dir,
        )
        optifine_status = ft.Container(
            bgcolor="#1a3d2a" if optifine_installed else CARD2_BG,
            border=ft.border.all(
                1, "#2a5a2a" if optifine_installed else BORDER
            ),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
            content=ft.Row([
                ft.Icon(ft.icons.SPEED_ROUNDED, size=16,
                        color=GREEN if optifine_installed else TEXT_DIM),
                ft.Container(width=10),
                ft.Column([
                    ft.Text("OptiFine",
                            color=GREEN if optifine_installed else TEXT_PRI,
                            size=11, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "Instalado ✓" if optifine_installed else "No instalado",
                        color=GREEN if optifine_installed else TEXT_DIM, size=9,
                    ),
                ], spacing=1, expand=True),
                ft.OutlinedButton(
                    "Gestionar",
                    icon=ft.icons.SETTINGS_ROUNDED,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=6),
                        side=ft.BorderSide(
                            1, GREEN if optifine_installed else BORDER
                        ),
                        color=GREEN if optifine_installed else TEXT_SEC,
                        padding=ft.padding.symmetric(horizontal=12, vertical=6),
                    ),
                    on_click=lambda e: (
                        self.page.close(self._dlg),
                        _OptiFineDialog(
                            self.page, self.app, self.profile,
                            on_done=self.on_done,
                        ),
                    ),
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        return ft.Column([
            self._heading("Mod loader"),
            ft.Container(height=4),
            self._subtext("Select the loader for this instance."),
            ft.Container(height=12),
            loader_row,
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            self._heading("Game version"),
            ft.Container(height=4),
            self._subtext("Minecraft version used by this instance."),
            ft.Container(height=12),
            self._version_dd,
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            self._heading("OptiFine"),
            ft.Container(height=4),
            self._subtext(
                "Optimización de gráficos y shaders. Compatible con Vanilla y Forge."
            ),
            ft.Container(height=12),
            optifine_status,
        ], spacing=0, scroll=ft.ScrollMode.AUTO)

    def _loader_pill(self, label: str) -> ft.Container:
        active = label.lower() == self._loader_val.lower()
        pill   = ft.Container(
            bgcolor=GREEN if active else INPUT_BG,
            border=ft.border.all(1, GREEN if active else BORDER),
            border_radius=20,
            padding=ft.padding.symmetric(horizontal=18, vertical=9),
            animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
            content=ft.Text(label,
                            color=TEXT_INV if active else TEXT_SEC,
                            size=11, weight=ft.FontWeight.W_600),
        )
        def on_click(e: ft.ControlEvent, lbl: str = label) -> None:
            self._loader_val = lbl
            for l2, b in self._loader_btns.items():
                a = l2.lower() == lbl.lower()
                b.bgcolor       = GREEN if a else INPUT_BG
                b.border        = ft.border.all(1, GREEN if a else BORDER)
                b.content.color = TEXT_INV if a else TEXT_SEC
                try: b.update()
                except Exception: pass

        pill.on_click = on_click
        pill.on_hover = lambda e, p=pill, lbl=label: (
            None if lbl.lower() == self._loader_val.lower() else (
                setattr(p, "bgcolor",
                        CARD2_BG if e.data == "true" else INPUT_BG)
                or p.update()
            )
        )
        return pill

    # Java & Memory ────────────────────────────────────────────────────────────
    def _section_java(self) -> ft.Column:
        ram_opts = [512, 1024, 2048, 3072, 4096, 6144, 8192, 12288, 16384]
        self._ram_dd = ft.Dropdown(
            value=str(self._ram_val),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, height=42,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=8),
            text_style=ft.TextStyle(size=12),
            options=[
                ft.dropdown.Option(
                    str(r),
                    f"{r} MB  ({r // 1024} GB)" if r >= 1024 else f"{r} MB",
                )
                for r in ram_opts
            ],
            on_change=self._set_ram,           # C5
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
            on_change=self._set_java,          # C5
        )

        def browse_java(e: ft.ControlEvent) -> None:
            fp = ft.FilePicker(on_result=self._on_java_picked)
            self.page.overlay.append(fp)
            self.page.update()
            fp.pick_files(
                dialog_title="Select Java executable",
                allowed_extensions=["exe", ""],
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
            on_change=self._set_jvm,           # C5
        )

        return ft.Column([
            self._heading("Memory (RAM)"),
            ft.Container(height=4),
            self._subtext("Amount of RAM allocated to this Minecraft instance."),
            ft.Container(height=12),
            self._ram_dd,
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            self._heading("Java executable"),
            ft.Container(height=4),
            self._subtext(
                "Path to the java binary. Leave empty to use the system default."
            ),
            ft.Container(height=12),
            ft.Row([
                self._java_field,
                ft.Container(width=8),
                ft.OutlinedButton(
                    "Browse",
                    icon=ft.icons.FOLDER_OPEN_ROUNDED,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        side=ft.BorderSide(1, BORDER), color=TEXT_SEC,
                        padding=ft.padding.symmetric(horizontal=14, vertical=10),
                    ),
                    on_click=browse_java,
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            self._heading("JVM arguments"),
            ft.Container(height=4),
            self._subtext(
                "Additional arguments passed to the JVM. Advanced users only."
            ),
            ft.Container(height=12),
            self._jvm_field,
        ], spacing=0, scroll=ft.ScrollMode.AUTO)

    def _on_java_picked(self, r: ft.FilePickerResultEvent) -> None:
        if r.files:
            self._java_val         = r.files[0].path
            self._java_field.value = self._java_val
            try: self._java_field.update()
            except Exception: pass

    # Launch Hooks ─────────────────────────────────────────────────────────────
    def _section_hooks(self) -> ft.Column:
        self._pre_field = ft.TextField(
            value=self._pre_val,
            hint_text="Command to run before launching Minecraft",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=11),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, min_lines=2, max_lines=4,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            text_size=12,
            on_change=self._set_pre,           # C5
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
            on_change=self._set_post,          # C5
        )

        return ft.Column([
            self._heading("Pre-launch command"),
            ft.Container(height=4),
            self._subtext(
                "Runs before Minecraft starts. Use $INSTANCE_DIR for the instance path.\n"
                "Example:  echo 'Starting' >> $INSTANCE_DIR/launch.log"
            ),
            ft.Container(height=12),
            self._pre_field,
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            self._heading("Post-exit command"),
            ft.Container(height=4),
            self._subtext(
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

    # ── Save ───────────────────────────────────────────────────────────────────
    def _on_save(self, e: ft.ControlEvent) -> None:
        self._save_btn.disabled = True
        self._save_btn.text     = "Saving…"
        try: self._save_btn.update()
        except Exception: pass

        try:
            if self._name_val.strip() and self._name_val != self.profile.name:
                self.app.profile_manager.rename_profile(
                    self.profile.id, self._name_val.strip()
                )
            if self._version_val != self.profile.version_id:
                self.app.profile_manager.update_profile_version(
                    self.profile.id, self._version_val
                )
            self._write_meta({
                "ram_mb":     self._ram_val,
                "java_path":  self._java_val.strip(),
                "jvm_args":   self._jvm_val.strip(),
                "pre_launch": self._pre_val.strip(),
                "post_exit":  self._post_val.strip(),
                "loader":     self._loader_val.lower(),
                "notes":      self._notes_val.strip(),   # U6
            })
            self.page.close(self._dlg)
            self.app.snack("Instance settings saved.")
            if self.on_done:
                self.on_done()
        except Exception as ex:
            self._save_btn.disabled = False
            self._save_btn.text     = "Save changes"
            try: self._save_btn.update()
            except Exception: pass
            self.app.snack(str(ex), error=True)

    # ── Duplicate ──────────────────────────────────────────────────────────────
    def _duplicate_instance(self) -> None:
        def do_dup() -> None:
            try:
                new_name = f"{self.profile.name} (copy)"
                new_dir  = f"{self.profile.game_dir}_copy_{int(time.time())}"
                shutil.copytree(self.profile.game_dir, new_dir)
                self.app.profile_manager.create_profile(
                    name=new_name,
                    version_id=self.profile.version_id,
                    game_dir=new_dir,
                )
                self.page.run_thread(
                    lambda: self.app.snack(f"'{new_name}' created.")
                )
                if self.on_done:
                    self.page.run_thread(self.on_done)
            except Exception as ex:
                self.page.run_thread(
                    lambda: self.app.snack(str(ex), error=True)
                )

        threading.Thread(target=do_dup, daemon=True).start()
        self.app.snack("Duplicating instance…")

    # ── Delete ─────────────────────────────────────────────────────────────────
    def _confirm_delete(self) -> None:
        def on_action(e: ft.ControlEvent) -> None:
            self.page.close(confirm_dlg)
            if e.control.data == "delete":
                self._do_delete()

        confirm_dlg = ft.AlertDialog(
            modal=True, bgcolor=CARD_BG,
            title=ft.Text("Delete instance?", color=TEXT_PRI,
                          weight=ft.FontWeight.BOLD),
            content=ft.Text(
                f"This will permanently delete '{self.profile.name}' and all its "
                f"worlds, configs and mods.\nThis cannot be undone.",
                color=TEXT_SEC, size=12,
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    style=ft.ButtonStyle(color=TEXT_SEC),
                    on_click=on_action,
                ),
                ft.ElevatedButton(
                    "Delete forever",
                    data="delete",
                    bgcolor=ACCENT_RED, color="#ffffff",
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8)
                    ),
                    on_click=on_action,
                ),
            ],
        )
        self.page.open(confirm_dlg)

    def _do_delete(self) -> None:
        def do() -> None:
            try:
                self.app.profile_manager.delete_profile(self.profile.id)
                shutil.rmtree(self.profile.game_dir, ignore_errors=True)
                self.page.run_thread(lambda: (
                    self.app.snack("Instance deleted."),
                    self.app._show_view("library"),
                ))
            except Exception as ex:
                self.page.run_thread(
                    lambda: self.app.snack(str(ex), error=True)
                )

        threading.Thread(target=do, daemon=True).start()


# =============================================================================
# Tab: Files
# =============================================================================
class _FilesTab:

    def __init__(self, page: ft.Page, app, profile) -> None:
        self.page    = page
        self.app     = app
        self.profile = profile
        self._build()

    def _build(self) -> None:
        game_dir = self.profile.game_dir
        folders  = [
            ("Mods",           os.path.join(game_dir, "mods")),
            ("Resource Packs", os.path.join(game_dir, "resourcepacks")),
            ("Shader Packs",   os.path.join(game_dir, "shaderpacks")),
            ("Saves / Worlds", os.path.join(game_dir, "saves")),
            ("Config",         os.path.join(game_dir, "config")),
            ("Screenshots",    os.path.join(game_dir, "screenshots")),
        ]

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
                    ft.Text(
                        f"{size:.1f} MB" if exists else "Vacía",
                        color=TEXT_SEC, size=9,
                    ),
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

        self.root = ft.Container(
            expand=True, padding=ft.padding.all(28),
            content=ft.Column([
                ft.Text("Archivos", color=TEXT_PRI, size=16,
                        weight=ft.FontWeight.BOLD),
                ft.Text("Carpetas de la instancia", color=TEXT_DIM, size=9),
                ft.Container(height=16),
                ft.Column(
                    [folder_row(n, p) for n, p in folders],
                    spacing=8, scroll=ft.ScrollMode.AUTO, expand=True,
                ),
            ], spacing=0, expand=True),
        )

    @staticmethod
    def _folder_size(path: str) -> float:
        total = 0
        for dp, _, files in os.walk(path):
            for fn in files:
                try: total += os.path.getsize(os.path.join(dp, fn))
                except OSError: pass
        return total / 1_048_576

    @staticmethod
    def _open_folder(path: str) -> None:
        import subprocess, sys
        os.makedirs(path, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])


# =============================================================================
# Tab: Worlds  (U12: date + size per world)
# =============================================================================
class _WorldsTab:

    def __init__(self, page: ft.Page, app, profile) -> None:
        self.page    = page
        self.app     = app
        self.profile = profile
        self._build()

    def _build(self) -> None:
        saves_dir = os.path.join(self.profile.game_dir, "saves")
        worlds: list[str] = []
        if os.path.isdir(saves_dir):
            worlds = sorted(
                d for d in os.listdir(saves_dir)
                if os.path.isdir(os.path.join(saves_dir, d))
            )

        if worlds:
            rows = [self._world_row(saves_dir, w) for w in worlds]
            content: ft.Control = ft.Column(
                rows, spacing=8, scroll=ft.ScrollMode.AUTO, expand=True
            )
        else:
            content = ft.Container(
                expand=True, alignment=ft.alignment.center,
                content=ft.Column([
                    ft.Text("Sin mundos guardados", color=TEXT_SEC, size=14,
                            text_align=ft.TextAlign.CENTER,
                            weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "Los mundos aparecerán aquí después de jugar.",
                        color=TEXT_DIM, size=10,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            )

        self.root = ft.Container(
            expand=True, padding=ft.padding.all(28),
            content=ft.Column([
                ft.Text("Mundos", color=TEXT_PRI, size=16,
                        weight=ft.FontWeight.BOLD),
                ft.Text(
                    f"{len(worlds)} mundo{'s' if len(worlds) != 1 else ''} "
                    f"guardado{'s' if len(worlds) != 1 else ''}",
                    color=TEXT_DIM, size=9,
                ),
                ft.Container(height=16),
                content,
            ], spacing=0, expand=True),
        )

    def _world_row(self, saves_dir: str, world_name: str) -> ft.Container:
        """World row with size and last-modified date (U12)."""
        world_path = os.path.join(saves_dir, world_name)
        size_str   = self._folder_size_str(world_path)
        date_str   = self._folder_mdate(world_path)

        return ft.Container(
            bgcolor=INPUT_BG, border_radius=8,
            padding=ft.padding.symmetric(horizontal=16, vertical=14),
            content=ft.Row([
                ft.Container(
                    width=44, height=44, border_radius=10,
                    bgcolor=CARD2_BG, alignment=ft.alignment.center,
                    content=ft.Text("W", color=TEXT_DIM, size=20,
                                    weight=ft.FontWeight.BOLD),
                ),
                ft.Container(width=14),
                ft.Column([
                    ft.Text(world_name, color=TEXT_PRI, size=11,
                            weight=ft.FontWeight.BOLD,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row([
                        ft.Icon(ft.icons.STORAGE_ROUNDED,
                                size=11, color=TEXT_DIM),
                        ft.Container(width=4),
                        ft.Text(size_str, color=TEXT_DIM, size=10),
                        ft.Container(width=12),
                        ft.Icon(ft.icons.SCHEDULE_ROUNDED,
                                size=11, color=TEXT_DIM),
                        ft.Container(width=4),
                        ft.Text(date_str, color=TEXT_DIM, size=10),
                    ], spacing=0),
                ], spacing=4, expand=True),
                ft.IconButton(
                    icon=ft.icons.FOLDER_OPEN_ROUNDED,
                    icon_color=TEXT_DIM, icon_size=18,
                    tooltip="Open world folder",
                    on_click=lambda e, p=world_path: self._open_folder(p),
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    @staticmethod
    def _folder_size_str(path: str) -> str:
        total = 0
        for dp, _, files in os.walk(path):
            for fn in files:
                try: total += os.path.getsize(os.path.join(dp, fn))
                except OSError: pass
        if total < 1024:            return f"{total} B"
        if total < 1_048_576:       return f"{total / 1024:.0f} KB"
        if total < 1_073_741_824:   return f"{total / 1_048_576:.1f} MB"
        return f"{total / 1_073_741_824:.2f} GB"

    @staticmethod
    def _folder_mdate(path: str) -> str:
        try:
            ts = os.path.getmtime(path)
            return datetime.datetime.fromtimestamp(ts).strftime("%d %b %Y")
        except Exception:
            return "—"

    @staticmethod
    def _open_folder(path: str) -> None:
        import subprocess, sys
        os.makedirs(path, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])


# =============================================================================
# Tab: Logs  (U13: real tail of logs/latest.log)
# =============================================================================
class _LogsTab:
    """
    Polls logs/latest.log every second and appends new content.
    Keeps the last LOG_LINES lines in the view.
    Call on_show() when the tab becomes visible, destroy() when unmounted.
    """

    LOG_LINES = 300
    POLL_SEC  = 1.0

    def __init__(self, page: ft.Page, app, profile) -> None:
        self.page    = page
        self.app     = app
        self.profile = profile
        self._alive  = True
        self._last_mtime = 0.0
        self._build()
        threading.Thread(target=self._tail_loop, daemon=True).start()

    def _build(self) -> None:
        log_path = os.path.join(self.profile.game_dir, "logs", "latest.log")

        self._log_text = ft.Text(
            "Los logs aparecerán aquí durante la ejecución del juego.",
            color=TEXT_DIM, size=10, selectable=True,
            font_family="Courier New",
        )
        self._log_col = ft.Column(
            [self._log_text],
            scroll=ft.ScrollMode.ALWAYS,
            expand=True,
        )
        self._path_lbl = ft.Text(
            log_path, color=TEXT_DIM, size=8,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self._status_dot = ft.Container(
            width=8, height=8, border_radius=4, bgcolor=TEXT_DIM,
        )

        self.root = ft.Container(
            expand=True, padding=ft.padding.all(28),
            content=ft.Column([
                ft.Row([
                    ft.Column([
                        ft.Text("Logs", color=TEXT_PRI, size=16,
                                weight=ft.FontWeight.BOLD),
                        self._path_lbl,
                    ], spacing=2, expand=True),
                    self._status_dot,
                    ft.Container(width=6),
                    ft.TextButton(
                        "Clear",
                        icon=ft.icons.DELETE_OUTLINE_ROUNDED,
                        style=ft.ButtonStyle(color=TEXT_DIM),
                        on_click=self._clear_log,
                    ),
                    ft.TextButton(
                        "Open",
                        icon=ft.icons.OPEN_IN_NEW_ROUNDED,
                        style=ft.ButtonStyle(color=TEXT_DIM),
                        on_click=self._open_log,
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=12),
                ft.Container(
                    expand=True, bgcolor=INPUT_BG, border_radius=8,
                    padding=ft.padding.all(14),
                    content=self._log_col,
                ),
            ], spacing=0, expand=True),
        )

    def _tail_loop(self) -> None:
        log_path = os.path.join(self.profile.game_dir, "logs", "latest.log")
        while self._alive:
            try:
                if os.path.isfile(log_path):
                    mtime = os.path.getmtime(log_path)
                    if mtime != self._last_mtime:
                        self._last_mtime = mtime
                        with open(log_path, "r", errors="replace") as f:
                            lines = f.readlines()[-self.LOG_LINES:]
                        content = "".join(lines)

                        def _update(c: str = content) -> None:
                            self._log_text.value = c
                            self._status_dot.bgcolor = GREEN
                            try:
                                self._log_text.update()
                                self._status_dot.update()
                            except Exception:
                                pass

                        self.page.run_thread(_update)
            except Exception:
                pass
            time.sleep(self.POLL_SEC)

    def on_show(self) -> None:
        """Called when the tab becomes visible again."""
        self._alive = True

    def destroy(self) -> None:
        """Stop the tail thread when the tab is unmounted."""
        self._alive = False

    def _clear_log(self, e: ft.ControlEvent) -> None:
        self._log_text.value = ""
        self._last_mtime     = 0.0
        try: self._log_text.update()
        except Exception: pass

    def _open_log(self, e: ft.ControlEvent) -> None:
        import subprocess, sys
        log_path = os.path.join(self.profile.game_dir, "logs", "latest.log")
        if not os.path.isfile(log_path):
            self.app.snack("No log file found.", error=True)
            return
        if sys.platform == "win32":
            os.startfile(log_path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", log_path])
        else:
            subprocess.Popen(["xdg-open", log_path])