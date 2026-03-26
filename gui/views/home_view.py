"""
gui/views/home_view.py — Vista Inicio
Selector de perfil, lanzamiento del juego e instalación de versiones.
"""
import threading
import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER, BORDER_BRIGHT,
    GREEN, GREEN_DIM, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV,
)
from utils.logger import get_logger

log = get_logger()


class HomeView:
    def __init__(self, page: ft.Page, app):
        self.page = page
        self.app  = app
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self):
        # ── Launch card ──────────────────────────────────────────────────────
        self._username_field = ft.TextField(
            value="Player",
            label="Usuario",
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            color=TEXT_PRI,
            bgcolor=INPUT_BG,
            border_color=BORDER,
            focused_border_color=GREEN,
            border_radius=8,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            width=200,
        )

        self._profile_dd = ft.Dropdown(
            label="Perfil",
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            color=TEXT_PRI,
            bgcolor=INPUT_BG,
            border_color=BORDER,
            focused_border_color=GREEN,
            border_radius=8,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            expand=True,
            options=[],
        )

        self._launch_btn = ft.ElevatedButton(
            "▶  JUGAR",
            bgcolor=GREEN,
            color=TEXT_INV,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=28, vertical=14),
                overlay_color=ft.colors.with_opacity(0.15, "#000000"),
            ),
            on_click=self._on_launch,
        )

        launch_card = ft.Container(
            bgcolor=CARD_BG,
            border_radius=12,
            padding=ft.padding.all(24),
            content=ft.Row([
                self._username_field,
                ft.Container(width=16),
                self._profile_dd,
                ft.Container(width=16),
                self._launch_btn,
            ], vertical_alignment=ft.CrossAxisAlignment.END),
        )

        # ── Progress bar (oculta inicialmente) ────────────────────────────────
        self._progress_label = ft.Text("", color=TEXT_DIM, size=9)
        self._progress_bar   = ft.ProgressBar(
            value=0, bgcolor=INPUT_BG, color=GREEN, height=4,
        )
        self._progress_row = ft.Container(
            visible=False,
            content=ft.Column([
                self._progress_label,
                self._progress_bar,
            ], spacing=6),
        )

        # ── Versiones instaladas ──────────────────────────────────────────────
        self._version_dd = ft.Dropdown(
            label="Versión disponible",
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            width=220, options=[],
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
        )

        self._install_btn = ft.ElevatedButton(
            "Instalar versión",
            bgcolor=CARD2_BG, color=TEXT_PRI,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=18, vertical=12),
                overlay_color=ft.colors.with_opacity(0.12, GREEN),
            ),
            on_click=self._on_install,
        )

        self._installed_col = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO)

        versions_card = ft.Container(
            bgcolor=CARD_BG,
            border_radius=12,
            padding=ft.padding.all(24),
            content=ft.Column([
                ft.Text("Versiones instaladas", color=TEXT_PRI, size=14,
                        weight=ft.FontWeight.BOLD),
                ft.Container(height=12),
                ft.Row([self._version_dd, ft.Container(width=12), self._install_btn],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=12),
                self._installed_col,
            ], spacing=0),
        )

        self.root = ft.Container(
            expand=True,
            bgcolor=BG,
            padding=ft.padding.all(32),
            content=ft.Column([
                ft.Text("Inicio", color=TEXT_PRI, size=26,
                        weight=ft.FontWeight.BOLD),
                ft.Text("Selecciona un perfil y lanza el juego",
                        color=TEXT_SEC, size=11),
                ft.Container(height=20),
                launch_card,
                self._progress_row,
                ft.Container(height=20),
                versions_card,
            ], spacing=8, scroll=ft.ScrollMode.AUTO),
        )

    # ── on_show ───────────────────────────────────────────────────────────────
    def on_show(self):
        self._refresh_profiles()
        self._refresh_installed()
        threading.Thread(target=self._fetch_available_versions, daemon=True).start()

    def _refresh_profiles(self):
        profiles = self.app.profile_manager.get_all_profiles()
        last     = self.app.settings.last_profile
        self._profile_dd.options = [
            ft.dropdown.Option(p.name) for p in profiles
        ]
        if profiles:
            names = [p.name for p in profiles]
            self._profile_dd.value = last if last in names else names[0]
        try: self._profile_dd.update()
        except Exception: pass

    def _refresh_installed(self):
        self._installed_col.controls.clear()
        installed = self.app.version_manager.get_installed_version_ids()
        if not installed:
            self._installed_col.controls.append(
                ft.Text("Sin versiones instaladas", color=TEXT_DIM, size=10))
        else:
            for v in installed:
                self._installed_col.controls.append(
                    ft.Container(
                        bgcolor=INPUT_BG, border_radius=6,
                        padding=ft.padding.symmetric(horizontal=14, vertical=8),
                        content=ft.Row([
                            ft.Text("✓", color=GREEN, size=12, width=20),
                            ft.Text(v, color=TEXT_PRI, size=10, expand=True),
                        ]),
                    )
                )
        try: self._installed_col.update()
        except Exception: pass

    def _fetch_available_versions(self):
        try:
            versions = self.app.version_manager.get_available_versions("release")
            ids = [v.id for v in versions]
            def update():
                self._version_dd.options = [ft.dropdown.Option(i) for i in ids]
                if ids: self._version_dd.value = ids[0]
                try: self._version_dd.update()
                except Exception: pass
            self.page.run_thread(update)
        except Exception as e:
            log.warning(f"No se pudo cargar versiones: {e}")

    # ── Instalar versión ──────────────────────────────────────────────────────
    def _on_install(self, e):
        version_id = self._version_dd.value
        if not version_id:
            self.app.snack("Selecciona una versión para instalar.", error=True)
            return

        self._progress_row.visible = True
        self._progress_label.value = f"Preparando instalación de {version_id}…"
        self._progress_bar.value   = 0
        self._install_btn.disabled = True
        self._launch_btn.disabled  = True
        try:
            self._progress_row.update()
            self._install_btn.update()
            self._launch_btn.update()
        except Exception: pass

        def install():
            try:
                def on_progress(step, current, total):
                    pct = (current / total) if total > 0 else 0
                    def upd():
                        self._progress_bar.value   = pct
                        self._progress_label.value = step
                        try:
                            self._progress_bar.update()
                            self._progress_label.update()
                        except Exception: pass
                    self.page.run_thread(upd)

                self.app.version_manager.install_version(version_id, on_progress)
                self.page.run_thread(self._on_install_done)
            except Exception as err:
                self.page.run_thread(lambda: self._on_install_error(str(err)))

        threading.Thread(target=install, daemon=True).start()

    def _on_install_done(self):
        self._progress_bar.value   = 1
        self._progress_label.value = "Instalación completada ✓"
        self._install_btn.disabled = False
        self._launch_btn.disabled  = False
        try:
            self._progress_bar.update()
            self._progress_label.update()
            self._install_btn.update()
            self._launch_btn.update()
        except Exception: pass
        self._refresh_installed()
        self.app.snack("Versión instalada correctamente.")

    def _on_install_error(self, err: str):
        self._progress_row.visible = False
        self._install_btn.disabled = False
        self._launch_btn.disabled  = False
        try:
            self._progress_row.update()
            self._install_btn.update()
            self._launch_btn.update()
        except Exception: pass
        self.app.snack(f"Error de instalación: {err}", error=True)

    # ── Lanzar juego ──────────────────────────────────────────────────────────
    def _on_launch(self, e):
        username     = self._username_field.value.strip()
        profile_name = self._profile_dd.value

        if not username:
            self.app.snack("Ingresa tu nombre de usuario.", error=True)
            return
        if not profile_name:
            self.app.snack("Selecciona un perfil.", error=True)
            return

        profile = self.app.profile_manager.get_profile_by_name(profile_name)
        if not profile:
            self.app.snack(f"Perfil '{profile_name}' no encontrado.", error=True)
            return

        try:
            session      = self.app.auth_service.create_offline_session(username)
            version_data = self.app.version_manager.get_version_data(profile.version_id)
        except Exception as err:
            self.app.snack(str(err), error=True)
            return

        def on_output(line: str):
            log.info(f"[MC] {line}")

        try:
            process = self.app.launcher_engine.launch(
                profile, session, version_data, on_output=on_output)
            self.app.settings.last_profile = profile_name
            self._launch_btn.disabled = True
            try: self._launch_btn.update()
            except Exception: pass

            def monitor():
                process.wait()
                rc = process.returncode
                log.info(f"Minecraft cerrado con código: {rc}")
                def done():
                    self._launch_btn.disabled = False
                    try: self._launch_btn.update()
                    except Exception: pass
                    if rc != 0:
                        self.app.snack(
                            f"Minecraft cerró con error (código {rc}). "
                            f"Revisa los logs.", error=True)
                self.page.run_thread(done)

            threading.Thread(target=monitor, daemon=True).start()
            self.app.snack(f"Minecraft {profile.version_id} iniciado.")
        except Exception as err:
            self.app.snack(f"Error al lanzar: {err}", error=True)