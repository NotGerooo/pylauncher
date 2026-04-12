"""
gui/app.py — Gero's Launcher
Shell principal: titlebar, sidebar izquierdo, área de contenido, sidebar derecho.
"""
import threading
import flet as ft
from services.updater import run_update_check_async, download_update, apply_update
from config.settings import Settings
from managers.version_manager import VersionManager
from managers.profile_manager import ProfileManager
from managers.java_manager import JavaManager
from services.auth_service import AuthService
from services.modrinth_service import ModrinthService
from core.launcher import LauncherEngine
from utils.logger import get_logger
from PIL import Image
img = Image.open("Gero´s Launcher.ico")
img.save("Gero´s Launcher.ico", format="ICO", sizes=[(16,16),(32,32),(48,48),(256,256)])

from gui.theme import (
    BG, SIDEBAR_BG, CARD_BG, CARD2_BG, INPUT_BG,
    BORDER, BORDER_BRIGHT, GREEN, GREEN_DIM, GREEN_SUBTLE,
    TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV,
    NAV_ACTIVE, NAV_HOVER, ACCENT_RED, AVATAR_PALETTE,
)
from gui.sidebar_left  import SidebarLeft
from gui.sidebar_right import SidebarRight

log = get_logger()


class App:
    def __init__(self, page: ft.Page):
        self.page = page
        self._views: dict        = {}
        self._current_vid: str | None = None
        self._active_instance    = None

        self._setup_page()
        self._init_services()
        self._build_layout()
        self._check_updates()
        self._show_view("library")
        log.info("Interfaz Flet iniciada")

    # ── Página ────────────────────────────────────────────────────────────────
    def _setup_page(self):
        p = self.page
        p.title                   = "Gero's Launcher"
        p.window.width            = 1380
        p.window.height           = 780
        p.window.min_width        = 1000
        p.window.min_height       = 620
        p.window.title_bar_hidden = True
        p.bgcolor = SIDEBAR_BG
        p.padding = 0
        p.spacing = 0
        p.scroll_animation_duration = 300
        p.window.icon = "Gero´s Launcher.ico"   # o .ico — Flet acepta ambos

    # ── Servicios ─────────────────────────────────────────────────────────────
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

    @property
    def sidebar_right(self):
        return self._sidebar_right

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build_layout(self):
        self._sidebar_left  = SidebarLeft(self)
        self._sidebar_right = SidebarRight(self)
        self._content_area  = ft.Container(expand=True, bgcolor=BG)

        body = ft.Row(
            controls=[
                self._sidebar_left.root,
                ft.VerticalDivider(width=1, color=BORDER),
                self._content_area,
                ft.VerticalDivider(width=1, color=BORDER),
                self._sidebar_right.root,
            ],
            spacing=0,
            expand=True,
        )

        self.page.add(
            ft.Column(
                spacing=0,
                expand=True,
                controls=[
                    self._build_titlebar(),
                    ft.Divider(height=1, color=BORDER),
                    body,
                ],
            )
        )

    # ── Titlebar ──────────────────────────────────────────────────────────────
    # ── Titlebar ──────────────────────────────────────────────────────────────
    def _build_titlebar(self) -> ft.Control:
        def wbtn(icon_path: str, on_click, close: bool = False) -> ft.Container:
            icon = ft.canvas.Canvas(
                shapes=[
                    ft.canvas.Path(
                        [ft.canvas.Path.MoveTo(*icon_path[0]),
                        *[ft.canvas.Path.LineTo(*p) for p in icon_path[1:]]],
                        paint=ft.Paint(
                            color=TEXT_DIM,
                            stroke_width=1.2,
                            style=ft.PaintingStyle.STROKE,
                        ),
                    )
                ],
                width=10, height=10,
            )
            c = ft.Container(
                width=46, height=42,
                alignment=ft.alignment.center,
                content=icon,
                on_click=lambda e: on_click(),
            )
            normal_bg   = ft.colors.with_opacity(0.0,  "#ffffff")
            hover_bg    = "#c0392b" if close else ft.colors.with_opacity(0.07, "#ffffff")

            def on_hover(e):
                c.bgcolor = hover_bg if e.data == "true" else normal_bg
                # cambiar color del ícono en hover
                icon.shapes[0].paint.color = (
                    "#ffffff" if e.data == "true" else TEXT_DIM
                )
                c.update()

            c.on_hover = on_hover
            return c

        # Ícono SVG en canvas es verboso — más simple con Text + unicode thin:
        def win_btn(symbol: str, cmd, close: bool = False) -> ft.Container:
            lbl = ft.Text(symbol, size=13, color=TEXT_DIM,
                        text_align=ft.TextAlign.CENTER)
            c = ft.Container(
                width=46, height=42,
                alignment=ft.alignment.center,
                content=lbl,
                on_click=lambda e: cmd(),
                tooltip=("Cerrar" if close else None),
            )
            def on_hover(e):
                is_hov = e.data == "true"
                c.bgcolor = ("#c0392b" if (close and is_hov)
                            else (ft.colors.with_opacity(0.07, "#ffffff") if is_hov
                                else ft.colors.TRANSPARENT))
                lbl.color  = "#ffffff" if is_hov else TEXT_DIM
                c.update()
            c.on_hover = on_hover
            return c

        return ft.WindowDragArea(
            ft.Container(
                bgcolor=SIDEBAR_BG, height=42,
                padding=ft.padding.only(left=16, right=0),
                content=ft.Row(
                    [
                        # Logo + nombre
                        ft.Text("⛏", color=GREEN, size=14),
                        ft.Container(width=8),
                        ft.Text(
                            "Gero's Launcher",
                            color=TEXT_PRI, size=12,
                            weight=ft.FontWeight.W_600,
                        ),
                        ft.Container(
                            bgcolor=ft.colors.with_opacity(0.12, GREEN),
                            border=ft.border.all(1, ft.colors.with_opacity(0.25, GREEN)),
                            border_radius=3,
                            padding=ft.padding.symmetric(horizontal=6, vertical=2),
                            content=ft.Text(
                                "v0.2.0", color=GREEN, size=9,
                                weight=ft.FontWeight.W_600,
                            ),
                            margin=ft.margin.only(left=6),
                        ),
                        ft.Container(expand=True),   # spacer — área de drag
                        # Botones de ventana (sin margen derecho, pegados al borde)
                        win_btn("−", self._minimize),
                        win_btn("⬜", self._toggle_maximize),
                        win_btn("✕", lambda: self.page.window.destroy(), close=True),
                    ],
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
            expand=True,
        )

    def _minimize(self):
        self.page.window.minimized = True
        self.page.update()

    def _toggle_maximize(self):
        self.page.window.maximized = not self.page.window.maximized
        self.page.update()

    # ── Navegación ────────────────────────────────────────────────────────────
    def _show_view(self, vid: str):
        # Notificar a la vista actual que se oculta
        if self._current_vid and self._current_vid in self._views:
            prev = self._views[self._current_vid]
            if hasattr(prev, "on_hide"):
                try:
                    prev.on_hide()
                except Exception:
                    pass

        self._active_instance = None
        self._sidebar_left.set_active(vid)
        self._current_vid = vid

        if vid not in self._views:
            self._views[vid] = self._create_view(vid)

        view_obj = self._views[vid]
        self._content_area.content = view_obj.root
        try:
            self._content_area.update()
        except Exception:
            pass

        if hasattr(view_obj, "on_show"):
            view_obj.on_show()

        threading.Timer(0.15, self._sidebar_right.refresh_account).start()

    def _show_instance(self, profile):
        from gui.views.instance_view import InstanceView
        self._active_instance = profile
        self._sidebar_left.set_active("")

        key = f"instance_{profile.id}"
        if key not in self._views:
            self._views[key] = InstanceView(self.page, self, profile)

        view_obj = self._views[key]
        self._content_area.content = view_obj.root
        try: self._content_area.update()
        except Exception: pass

        if hasattr(view_obj, "on_show"):
            view_obj.on_show()

    def _create_view(self, vid: str):
        from gui.views.home_view     import HomeView
        from gui.views.library_view  import LibraryView
        from gui.views.discover_view import DiscoverView
        from gui.views.settings_view import SettingsView
        from gui.views.accounts_view import AccountsView

        mapping = {
            "home":     HomeView,
            "discover": DiscoverView,
            "library":  LibraryView,
            "settings": SettingsView,
            "accounts": AccountsView,
        }
        cls = mapping.get(vid)
        if cls:
            return cls(self.page, self)
        return _PlaceholderView(self.page, self, vid)

    # ── Crear instancia desde sidebar ─────────────────────────────────────────
    def _open_create_instance(self):
        self._show_view("library")
        def open_dlg():
            lib = self._views.get("library")
            if lib and hasattr(lib, "open_create_dialog"):
                lib.open_create_dialog()
        threading.Timer(0.2, open_dlg).start()

    # ── Invalidar caché de instancia ──────────────────────────────────────────
    def invalidate_instance(self, profile_id: str):
        key = f"instance_{profile_id}"
        if key in self._views:
            del self._views[key]
        self._sidebar_left.refresh_instances()

    # ── Compatibilidad: refresh_account_panel (llamado desde otras vistas) ────
    def refresh_account_panel(self):
        self._sidebar_right.refresh_account()

    # ── Snack ─────────────────────────────────────────────────────────────────
    def snack(self, msg: str, error: bool = False):
        bar = ft.SnackBar(
            content=ft.Text(msg, color=TEXT_PRI),
            bgcolor=CARD2_BG if not error else "#2d1515",
            duration=3000,
        )
        self.page.overlay.append(bar)
        bar.open = True
        self.page.update()

    def _check_updates(self):
        """Lanza la verificación de actualizaciones en background."""
        def on_update_available(info):
            # Flet necesita que los cambios de UI vengan del hilo correcto
            self.page.run_thread(self._show_update_dialog, info)
    
        run_update_check_async(on_update_available)
    
    
    def _show_update_dialog(self, info: dict):
        """Muestra el diálogo de actualización en la UI de Flet."""
        new_version = info.get("version", "?")
        url = info.get("url", "")
    
        progress_bar = ft.ProgressBar(width=400, value=0, visible=False)
        status_text = ft.Text("", size=12, color=ft.Colors.GREY_400)
    
        def on_update_click(e):
            btn_update.disabled = True
            btn_skip.disabled = True
            progress_bar.visible = True
            status_text.value = "Descargando actualización..."
            dlg.update()
    
            def do_download():
                try:
                    def on_progress(pct):
                        progress_bar.value = pct / 100
                        status_text.value = f"Descargando... {pct:.0f}%"
                        dlg.update()
    
                    new_exe = download_update(url, on_progress)
                    status_text.value = "Instalando y reiniciando..."
                    dlg.update()
                    apply_update(new_exe)
                except Exception as ex:
                    status_text.value = f"Error: {ex}"
                    btn_skip.disabled = False
                    dlg.update()
    
            self.page.run_thread(do_download)
    
        def on_skip_click(e):
            self.page.close(dlg)
    
        btn_update = ft.ElevatedButton(
            "Actualizar ahora",
            on_click=on_update_click,
            bgcolor=ft.Colors.GREEN_700,
            color=ft.Colors.WHITE,
        )
        btn_skip = ft.TextButton("Más tarde", on_click=on_skip_click)
    
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Actualización disponible — v{new_version}"),
            content=ft.Column(
                [
                    ft.Text(
                        f"Hay una nueva versión de Gero's Launcher disponible.\n"
                        f"¿Deseas actualizar ahora?",
                        size=13,
                    ),
                    progress_bar,
                    status_text,
                ],
                tight=True,
                spacing=10,
            ),
            actions=[btn_update, btn_skip],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    
        self.page.open(dlg)

class _PlaceholderView:
    def __init__(self, page, app, name):
        self.root = ft.Container(
            expand=True, bgcolor=BG,
            content=ft.Column([
                ft.Text("🚧", size=52, text_align=ft.TextAlign.CENTER),
                ft.Text(name.capitalize(), color=TEXT_SEC, size=18,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER),
                ft.Text("Próximamente", color=TEXT_DIM, size=11,
                        text_align=ft.TextAlign.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               alignment=ft.MainAxisAlignment.CENTER, expand=True),
        )