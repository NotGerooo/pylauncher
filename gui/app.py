"""
gui/app.py — Gero's Launcher
Shell principal: titlebar, sidebar izquierdo, área de contenido, sidebar derecho.
"""
import json
import threading
from pathlib import Path

import flet as ft

from config.settings          import Settings
from core.launcher            import LauncherEngine
from managers.java_manager    import JavaManager
from managers.profile_manager import ProfileManager
from managers.version_manager import VersionManager
from services.auth_service    import AuthService
from services.modrinth_service import ModrinthService
from services.updater         import run_update_check_async, download_update, apply_update
from utils.logger             import get_logger

from gui.theme import (
    BG, SIDEBAR_BG, CARD_BG, CARD2_BG,
    BORDER, GREEN,
    TEXT_PRI, TEXT_SEC, TEXT_DIM,
    NAV_ACTIVE, NAV_HOVER,
)
from gui.sidebar_left  import SidebarLeft
from gui.sidebar_right import SidebarRight

log = get_logger()

_ICO_PATH     = r"Gero´s Launcher.ico"
_VERSION_FILE = Path("version.json")

# Vistas disponibles — mapeo id → clase (importación lazy para arranque más rápido)
_VIEW_MAP: dict[str, str] = {
    "home":     "gui.views.home_view:HomeView",
    "discover": "gui.views.discover_view:DiscoverView",
    "library":  "gui.views.library_view:LibraryView",
    "accounts": "gui.views.accounts_view:AccountsView",
    # "settings" se maneja como overlay, NO como vista normal
}


def _load_version() -> str:
    try:
        return json.loads(_VERSION_FILE.read_text(encoding="utf-8")).get("version", "?")
    except Exception:
        return "?"


def _import_view(module_path: str):
    module, cls_name = module_path.split(":")
    import importlib
    return getattr(importlib.import_module(module), cls_name)


# ══════════════════════════════════════════════════════════════════════════════
class App:
    """Clase principal. Orquesta layout, navegación y servicios."""

    def __init__(self, page: ft.Page):
        self.page    = page
        self.version = _load_version()

        # Estado interno
        self._views:           dict[str, object] = {}
        self._current_vid:     str | None = None
        self._active_instance: object | None = None

        self._setup_page()
        self._init_services()
        self._build_layout()
        self._show_view("home")
        self._check_updates()

        log.info("Interfaz iniciada — v%s", self.version)

    # ── Configuración de la ventana ───────────────────────────────────────
    def _setup_page(self):
        p = self.page
        p.title                           = "Gero's Launcher"
        p.window.width                    = 1380
        p.window.height                   = 780
        p.window.min_width                = 1000
        p.window.min_height               = 620
        p.window.title_bar_hidden         = True
        p.window.title_bar_buttons_hidden = True
        p.window.icon                     = _ICO_PATH
        p.bgcolor                         = SIDEBAR_BG
        p.padding                         = 0
        p.spacing                         = 0
        p.scroll_animation_duration       = 300
        p.window.frameless                = True

    # ── Inicialización de servicios ───────────────────────────────────────
    def _init_services(self):
        from services.account_manager import AccountManager
        from services.microsoft_auth  import MicrosoftAuth

        self.settings         = Settings()
        self.version_manager  = VersionManager(self.settings)
        self.profile_manager  = ProfileManager(self.settings)
        self.java_manager     = JavaManager(self.settings)
        self.auth_service     = AuthService()
        self.modrinth_service = ModrinthService()
        self.launcher_engine  = LauncherEngine(self.settings)
        self.account_manager  = AccountManager(data_dir="data")
        self.microsoft_auth   = MicrosoftAuth()

    # ── Propiedad de compatibilidad ───────────────────────────────────────
    @property
    def sidebar_right(self) -> "SidebarRight":
        return self._sidebar_right

    # ── Construcción del layout ───────────────────────────────────────────
    def _build_layout(self):
        self._sidebar_left  = SidebarLeft(self)
        self._sidebar_right = SidebarRight(self)
        self._content_area  = ft.Container(expand=True, bgcolor=BG)

        # overlay_area: capa flotante para Settings (invisible por defecto)
        self.overlay_area = ft.Container(
            expand=True,
            visible=False,
        )

        # Stack: apila el contenido normal debajo y el overlay encima
        self._main_stack = ft.Stack(
            expand=True,
            controls=[self._content_area, self.overlay_area],
        )

        self.page.add(
            ft.Column(
                spacing=0,
                expand=True,
                controls=[
                    self._build_titlebar(),
                    ft.Divider(height=1, color=BORDER),
                    ft.Row(
                        spacing=0,
                        expand=True,
                        controls=[
                            self._sidebar_left.root,
                            ft.VerticalDivider(width=1, color=BORDER),
                            self._main_stack,   # ← Stack con overlay
                            ft.VerticalDivider(width=1, color=BORDER),
                            self._sidebar_right.root,
                        ],
                    ),
                ],
            )
        )

    # ── Titlebar personalizada ────────────────────────────────────────────
    def _build_titlebar(self) -> ft.Control:
        def _win_btn(symbol: str, cmd, is_close: bool = False) -> ft.Stack:
            BG_HOVER      = "#c0392b" if is_close else "#3a3d42"
            COLOR_HOVER   = "#ffffff"
            COLOR_DEFAULT = "#6b7280"

            bg_layer = ft.Container(
                width=46, height=38,
                bgcolor=ft.colors.TRANSPARENT,
                border_radius=0,
                animate=ft.animation.Animation(80, ft.AnimationCurve.LINEAR),
            )
            txt = ft.Text(
                symbol, size=12,
                color=COLOR_DEFAULT,
                text_align=ft.TextAlign.CENTER,
                font_family="Consolas",
            )
            label_box = ft.Container(
                width=46, height=38,
                alignment=ft.alignment.center,
                content=txt,
            )

            def _enter(e):
                bg_layer.bgcolor = BG_HOVER
                txt.color        = COLOR_HOVER
                try: bg_layer.update(); txt.update()
                except Exception: pass

            def _leave(e):
                bg_layer.bgcolor = ft.colors.TRANSPARENT
                txt.color        = COLOR_DEFAULT
                try: bg_layer.update(); txt.update()
                except Exception: pass

            detector = ft.GestureDetector(
                width=46, height=38,
                on_tap=lambda _: cmd(),
                on_enter=_enter,
                on_exit=_leave,
                mouse_cursor=ft.MouseCursor.BASIC,
            )
            return ft.Stack(width=46, height=38, controls=[bg_layer, label_box, detector])

        btn_min = _win_btn("−", self._minimize)
        btn_max = _win_btn("▢", self._toggle_maximize)
        btn_cls = _win_btn("×", self.page.window.close, is_close=True)

        version_badge = ft.Container(
            bgcolor=ft.colors.with_opacity(0.12, GREEN),
            border=ft.border.all(1, ft.colors.with_opacity(0.25, GREEN)),
            border_radius=4,
            padding=ft.padding.symmetric(horizontal=6, vertical=2),
            margin=ft.margin.only(left=8),
            content=ft.Text(f"v{self.version}", color=GREEN, size=9, weight=ft.FontWeight.W_600),
        )

        drag_area = ft.WindowDragArea(
            ft.Container(
                expand=True, height=38,
                content=ft.Row(
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(width=14),
                        ft.Text("⛏", color=GREEN, size=13),
                        ft.Container(width=8),
                        ft.Text("Gero's Launcher", color=TEXT_PRI, size=12, weight=ft.FontWeight.W_600),
                        version_badge,
                    ],
                ),
            ),
            expand=True,
        )

        return ft.Container(
            bgcolor=SIDEBAR_BG,
            height=38,
            content=ft.Row(
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[drag_area, btn_min, btn_max, btn_cls],
            ),
        )

    def _minimize(self):
        self.page.window.minimized = True
        self.page.update()

    def _toggle_maximize(self):
        self.page.window.maximized = not self.page.window.maximized
        self.page.update()

    # ── Navegación ────────────────────────────────────────────────────────
    def navigate_to(self, vid: str):
        """Alias público — lo usa sidebar_left."""
        if vid == "settings":
            self._open_settings()
        else:
            self._show_view(vid)

    def _show_view(self, vid: str):
        """Muestra una vista por su id."""
        # Ocultar settings si estaba abierto
        if self.overlay_area.visible:
            self.overlay_area.visible = False

        if self._current_vid and self._current_vid in self._views:
            prev = self._views[self._current_vid]
            if hasattr(prev, "on_hide"):
                try: prev.on_hide()
                except Exception: pass

        self._active_instance = None
        self._sidebar_left.set_active(vid)
        self._current_vid = vid

        if vid not in self._views:
            self._views[vid] = self._create_view(vid)

        view = self._views[vid]
        self._content_area.content = view.root
        try: self._content_area.update()
        except Exception: pass

        if hasattr(view, "on_show"):
            view.on_show()

        threading.Timer(0.15, self._sidebar_right.refresh_account).start()

    def _open_settings(self):
        """Abre el modal de settings como overlay flotante."""
        from gui.views.settings_view import SettingsView
        sv = SettingsView(self.page, self)
        self.overlay_area.content = sv.root
        self.overlay_area.visible = True
        try: self.overlay_area.update()
        except Exception: pass

    def _show_instance(self, profile):
        """Muestra la vista de una instancia específica."""
        from gui.views.instance_view import InstanceView

        self._active_instance = profile
        self._sidebar_left.set_active("")

        key = f"instance_{profile.id}"
        if key not in self._views:
            self._views[key] = InstanceView(self.page, self, profile)

        view = self._views[key]
        self._content_area.content = view.root
        try: self._content_area.update()
        except Exception: pass

        if hasattr(view, "on_show"):
            view.on_show()

    def _create_view(self, vid: str):
        module_path = _VIEW_MAP.get(vid)
        if module_path:
            cls = _import_view(module_path)
            return cls(self.page, self)
        return _PlaceholderView(vid)

    # ── Acciones del sidebar izquierdo ────────────────────────────────────
    def _open_create_instance(self):
        self._show_view("library")

        def _open():
            lib = self._views.get("library")
            if lib and hasattr(lib, "open_create_dialog"):
                lib.open_create_dialog()

        threading.Timer(0.2, _open).start()

    # ── Invalidar caché de instancia ──────────────────────────────────────
    def invalidate_instance(self, profile_id: str):
        key = f"instance_{profile_id}"
        self._views.pop(key, None)
        self._sidebar_left.refresh_instances()

    # ── API pública para las vistas ───────────────────────────────────────
    def refresh_account_panel(self):
        self._sidebar_right.refresh_account()

    def snack(self, msg: str, error: bool = False):
        bar = ft.SnackBar(
            content=ft.Text(msg, color=TEXT_PRI),
            bgcolor="#2d1515" if error else CARD2_BG,
            duration=3000,
        )
        self.page.overlay.append(bar)
        bar.open = True
        self.page.update()

    # ── Actualizaciones ───────────────────────────────────────────────────
    def _check_updates(self):
        run_update_check_async(lambda info: self.page.run_thread(self._show_update_dialog, info))

    def _show_update_dialog(self, info: dict):
        new_version = info.get("version", "?")
        url         = info.get("url", "")

        progress = ft.ProgressBar(width=400, value=0, visible=False, color=GREEN)
        status   = ft.Text("", size=11, color=TEXT_SEC)

        def _do_update(e):
            btn_update.disabled = True
            btn_skip.disabled   = True
            progress.visible    = True
            status.value        = "Descargando…"
            dlg.update()

            def _download():
                try:
                    def _on_progress(pct):
                        progress.value = pct / 100
                        status.value   = f"Descargando… {pct:.0f}%"
                        dlg.update()

                    new_exe      = download_update(url, _on_progress)
                    status.value = "Instalando y reiniciando…"
                    dlg.update()
                    apply_update(new_exe)
                except Exception as ex:
                    status.value      = f"Error: {ex}"
                    btn_skip.disabled = False
                    dlg.update()

            self.page.run_thread(_download)

        btn_update = ft.ElevatedButton(
            "Actualizar ahora",
            bgcolor=GREEN, color=TEXT_PRI,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=_do_update,
        )
        btn_skip = ft.TextButton(
            "Más tarde",
            style=ft.ButtonStyle(color=TEXT_SEC),
            on_click=lambda _: self.page.close(dlg),
        )

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Nueva versión disponible — v{new_version}", color=TEXT_PRI, size=13,
                          weight=ft.FontWeight.W_600),
            content=ft.Column([
                ft.Text(
                    "Hay una actualización de Gero's Launcher disponible.\n¿Deseas instalarla ahora?",
                    color=TEXT_SEC, size=12,
                ),
                progress,
                status,
            ], tight=True, spacing=10),
            bgcolor=CARD_BG,
            shape=ft.RoundedRectangleBorder(radius=14),
            actions=[btn_update, btn_skip],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg)


# ── Vista placeholder ─────────────────────────────────────────────────────────
class _PlaceholderView:
    def __init__(self, name: str):
        self.root = ft.Container(
            expand=True,
            bgcolor=BG,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                expand=True,
                controls=[
                    ft.Text("🚧", size=48, text_align=ft.TextAlign.CENTER),
                    ft.Container(height=12),
                    ft.Text(
                        name.capitalize(),
                        color=TEXT_SEC, size=16,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "Próximamente",
                        color=TEXT_DIM, size=10,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
            ),
        )