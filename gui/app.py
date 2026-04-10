"""Zen Launcher — shell de página y secuencia de arranque."""
import flet as ft
from config.constants import APP_NAME, APP_VERSION, DATA_DIR
from gui.theme import BG, SURFACE, TEXT_DIM, DANGER, WARNING
from services.sync import auto_sync
from services.updater import check_async
from utils.helpers import get_logger

log = get_logger("app")


class App:
    def __init__(self, page: ft.Page):
        self.page = page
        self._configure()
        self._build()
        self._boot()

    # ── Configuración de página ───────────────────────────────────────────────
    def _configure(self):
        p = self.page
        p.title, p.bgcolor, p.padding, p.spacing = APP_NAME, BG, 0, 0
        p.window.width            = 780
        p.window.height           = 520
        p.window.min_width        = 580
        p.window.min_height       = 380
        p.window.title_bar_hidden = True

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self):
        from gui.play_view import PlayView
        self.play_view = PlayView(self)
        self.page.add(ft.Column(
            spacing=0, expand=True,
            controls=[self._titlebar(), self.play_view.root],
        ))

    def _titlebar(self) -> ft.Control:
        def dot(color, action):
            return ft.Container(
                width=11, height=11, border_radius=6, bgcolor=color,
                on_click=action,
            )
        return ft.WindowDragArea(ft.Container(
            height=34, bgcolor=SURFACE,
            padding=ft.padding.symmetric(horizontal=14),
            content=ft.Row([
                ft.Text(APP_NAME, color=TEXT_DIM, size=10,
                        weight=ft.FontWeight.W_500),
                ft.Container(expand=True),
                ft.Text(f"v{APP_VERSION}", color=TEXT_DIM, size=9),
                ft.Container(width=10),
                ft.Row([
                    dot(DANGER,    lambda e: self.page.window.destroy()),
                    dot(WARNING,   lambda e: (
                        setattr(self.page.window, "minimized", True),
                        self.page.update())),
                    dot("#1fa832", lambda e: (
                        setattr(self.page.window, "maximized",
                                not self.page.window.maximized),
                        self.page.update())),
                ], spacing=5),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ))

    # ── Boot ──────────────────────────────────────────────────────────────────
    def _boot(self):
        auto_sync(DATA_DIR)
        check_async(lambda info: self.page.run_thread(self._update_banner, info))
        log.info("Zen Launcher listo")

    def _update_banner(self, info: dict):
        bar = ft.SnackBar(
            content=ft.Text(f"v{info['version']} disponible", color=TEXT_DIM),
            action="↑ Actualizar",
            on_action=lambda e: self.play_view.start_update(info),
            bgcolor=SURFACE,
            duration=8000,
        )
        self.page.overlay.append(bar)
        bar.open = True
        self.page.update()

    def snack(self, msg: str, error: bool = False):
        bar = ft.SnackBar(
            content=ft.Text(msg),
            bgcolor="#2d1515" if error else SURFACE,
            duration=3000,
        )
        self.page.overlay.append(bar)
        bar.open = True
        self.page.update()
