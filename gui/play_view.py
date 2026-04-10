"""
Zen Play View — el corazón de la UI.
Botón Play central + barra de progreso sutil en el fondo.
"""
import threading
import flet as ft
from gui.theme import BG, SURFACE, TEXT_DIM, ACCENT, ACCENT_GLOW
from config.settings import Settings
from utils.helpers import get_logger

log = get_logger("play")

# Compatibilidad con todas las versiones de Flet
_icons = getattr(ft, "Icons", None) or ft.icons


class PlayView:
    def __init__(self, app):
        self.app      = app
        self.page     = app.page
        self.settings = Settings()
        self._running = False

        self._status = ft.Text(
            "", color=TEXT_DIM, size=11,
            text_align=ft.TextAlign.CENTER,
        )
        self._bar = ft.ProgressBar(
            value=0, visible=False,
            bgcolor="transparent", color=ACCENT, height=1,
        )
        self._btn = self._make_btn()
        self.root = self._build()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self) -> ft.Control:
        return ft.Container(
            expand=True, bgcolor=BG,
            content=ft.Stack([
                # Centro: botón + estado
                ft.Column(
                    [
                        self._btn,
                        ft.Container(height=16),
                        self._status,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    expand=True,
                ),
                # Fondo: barra de progreso hairline
                ft.Container(
                    content=self._bar,
                    bottom=0, left=0, right=0,
                    alignment=ft.alignment.bottom_center,
                ),
            ]),
        )

    def _make_btn(self) -> ft.Container:
        return ft.Container(
            width=88, height=88, border_radius=44,
            bgcolor=ACCENT_GLOW,
            border=ft.border.all(1, ACCENT),
            alignment=ft.alignment.center,
            animate=ft.animation.Animation(180, ft.AnimationCurve.EASE_OUT),
            content=ft.Icon(_icons.PLAY_ARROW_ROUNDED, color=ACCENT, size=38),
            on_click=self._on_play,
            on_hover=self._on_hover,
        )

    def _on_hover(self, e):
        self._btn.bgcolor = "#1a3d28" if e.data == "true" else ACCENT_GLOW
        self._btn.scale   = 1.06    if e.data == "true" else 1.0
        self._btn.update()

    # ── Flujo de lanzamiento ──────────────────────────────────────────────────
    def _on_play(self, _):
        if self._running: return
        threading.Thread(target=self._launch, daemon=True, name="launch").start()

    def _launch(self):
        self._set(loading=True, status="Preparando…")
        try:
            from services.auth import offline_account
            from core.installer import install
            from core.launcher import launch
            from config.constants import MINECRAFT_DIR
            from managers.profile_manager import ProfileManager

            pm      = ProfileManager()
            profile = pm.ensure_default()
            version = profile.version
            account = offline_account(profile.username)

            # Instalar si no está
            versions_dir = MINECRAFT_DIR / "versions"
            installed = [v.name for v in versions_dir.glob("*/")] if versions_dir.exists() else []
            if version not in installed:
                install(
                    version, MINECRAFT_DIR,
                    on_progress=self._progress,
                    on_status=self._status_set,
                )

            self._status_set("Lanzando…")
            launch(version, account, self.settings, MINECRAFT_DIR)
            self._set(loading=False, status="")
        except Exception as exc:
            log.error("launch: %s", exc)
            self._set(loading=False, status=f"Error — {exc}")

    # ── Flujo de actualización ────────────────────────────────────────────────
    def start_update(self, info: dict):
        def _work():
            self._set(loading=True, status=f"Descargando v{info['version']}…")
            try:
                from services.updater import download, apply
                exe = download(info["url"], self._progress)
                self._status_set("Instalando…")
                apply(exe)
            except Exception as e:
                self._set(loading=False, status=f"Error: {e}")
        threading.Thread(target=_work, daemon=True).start()

    # ── Helpers UI ────────────────────────────────────────────────────────────
    def _progress(self, pct: float):
        self._bar.value = pct / 100
        self._safe_update()

    def _status_set(self, msg: str):
        self._status.value = msg
        self._safe_update()

    def _set(self, loading: bool = None, status: str = None):
        if loading is not None:
            self._running      = loading
            self._btn.disabled = loading
            self._bar.visible  = loading
            self._bar.value    = None if loading else 0
        if status is not None:
            self._status.value = status
        self._safe_update()

    def _safe_update(self):
        try: self.page.update()
        except Exception: pass
