"""
gui/views/library_view.py — Biblioteca de versiones instaladas
"""
import threading
import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV, ACCENT_RED,
)
from utils.logger import get_logger

log = get_logger()


class LibraryView:
    def __init__(self, page: ft.Page, app):
        self.page = page
        self.app  = app
        self._build()

    def _build(self):
        # Instalación rápida
        self._version_dd = ft.Dropdown(
            label="Versión disponible",
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, width=240, options=[],
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
        )
        self._install_btn = ft.ElevatedButton(
            "Instalar",
            bgcolor=GREEN, color=TEXT_INV,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                  padding=ft.padding.symmetric(horizontal=20, vertical=12)),
            on_click=self._on_install,
        )
        self._progress_lbl = ft.Text("", color=TEXT_DIM, size=9)
        self._progress_bar = ft.ProgressBar(value=0, bgcolor=INPUT_BG,
                                              color=GREEN, height=4)
        self._progress_row = ft.Container(
            visible=False,
            content=ft.Column([self._progress_lbl, self._progress_bar], spacing=6),
        )

        install_card = ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.all(22),
            content=ft.Column([
                ft.Text("Instalar nueva versión", color=TEXT_PRI, size=14,
                        weight=ft.FontWeight.BOLD),
                ft.Container(height=14),
                ft.Row([self._version_dd, ft.Container(width=12), self._install_btn],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=8),
                self._progress_row,
            ], spacing=0),
        )

        # Lista instaladas
        self._installed_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)

        installed_card = ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.all(22), expand=True,
            content=ft.Column([
                ft.Text("Versiones instaladas", color=TEXT_PRI, size=14,
                        weight=ft.FontWeight.BOLD),
                ft.Container(height=14),
                self._installed_col,
            ], spacing=0, expand=True),
        )

        self.root = ft.Container(
            expand=True, bgcolor=BG,
            padding=ft.padding.all(32),
            content=ft.Column([
                ft.Text("Biblioteca", color=TEXT_PRI, size=26,
                        weight=ft.FontWeight.BOLD),
                ft.Text("Versiones de Minecraft instaladas localmente",
                        color=TEXT_SEC, size=11),
                ft.Container(height=20),
                install_card,
                ft.Container(height=16),
                installed_card,
            ], spacing=8, expand=True),
        )

    def on_show(self):
        self._refresh_installed()
        threading.Thread(target=self._fetch_available, daemon=True).start()

    def _refresh_installed(self):
        self._installed_col.controls.clear()
        installed = self.app.version_manager.get_installed_version_ids()
        if not installed:
            self._installed_col.controls.append(
                ft.Text("Sin versiones instaladas.", color=TEXT_DIM, size=11))
        else:
            for v in installed:
                self._installed_col.controls.append(
                    ft.Container(
                        bgcolor=INPUT_BG, border_radius=10,
                        padding=ft.padding.symmetric(horizontal=20, vertical=14),
                        content=ft.Row([
                            ft.Container(
                                width=10, height=10, border_radius=5, bgcolor=GREEN),
                            ft.Container(width=14),
                            ft.Text(v, color=TEXT_PRI, size=12,
                                    weight=ft.FontWeight.BOLD, expand=True),
                            ft.Text("Minecraft Java Edition",
                                     color=TEXT_DIM, size=9),
                            ft.Container(width=14),
                            ft.IconButton(
                                icon=ft.icons.DELETE_OUTLINE,
                                icon_color=ACCENT_RED, icon_size=16,
                                tooltip="Desinstalar",
                                on_click=lambda e, vid=v: self._on_uninstall(vid),
                            ),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    )
                )
        try: self._installed_col.update()
        except Exception: pass

    def _fetch_available(self):
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
            log.warning(f"No se pudo cargar versiones disponibles: {e}")

    def _on_install(self, e):
        version_id = self._version_dd.value
        if not version_id:
            self.app.snack("Selecciona una versión.", error=True)
            return

        self._progress_row.visible = True
        self._progress_lbl.value   = f"Instalando {version_id}…"
        self._progress_bar.value   = 0
        self._install_btn.disabled = True
        try:
            self._progress_row.update()
            self._install_btn.update()
        except Exception: pass

        def install():
            try:
                def on_progress(step, current, total):
                    pct = (current / total) if total > 0 else 0
                    def upd():
                        self._progress_bar.value   = pct
                        self._progress_lbl.value   = step
                        try:
                            self._progress_bar.update()
                            self._progress_lbl.update()
                        except Exception: pass
                    self.page.run_thread(upd)
                self.app.version_manager.install_version(version_id, on_progress)
                self.page.run_thread(self._on_install_done)
            except Exception as err:
                self.page.run_thread(lambda: self._on_install_error(str(err)))

        threading.Thread(target=install, daemon=True).start()

    def _on_install_done(self):
        self._progress_bar.value   = 1
        self._progress_lbl.value   = "Instalación completada ✓"
        self._install_btn.disabled = False
        try:
            self._progress_bar.update()
            self._progress_lbl.update()
            self._install_btn.update()
        except Exception: pass
        self._refresh_installed()
        self.app.snack("Versión instalada correctamente.")

    def _on_install_error(self, err: str):
        self._progress_row.visible = False
        self._install_btn.disabled = False
        try:
            self._progress_row.update()
            self._install_btn.update()
        except Exception: pass
        self.app.snack(f"Error: {err}", error=True)

    def _on_uninstall(self, version_id: str):
        def confirm(e2):
            self.page.close(dlg)
            try:
                self.app.version_manager.uninstall_version(version_id)
                self._refresh_installed()
                self.app.snack(f"Versión {version_id} desinstalada.")
            except Exception as err:
                self.app.snack(str(err), error=True)

        dlg = ft.AlertDialog(
            title=ft.Text("Desinstalar versión", color=TEXT_PRI),
            content=ft.Text(f"¿Eliminar Minecraft {version_id}?", color=TEXT_SEC),
            bgcolor=CARD_BG,
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e2: self.page.close(dlg)),
                ft.ElevatedButton("Desinstalar", bgcolor="#2d1515", color=ACCENT_RED,
                                   on_click=confirm),
            ],
        )
        self.page.open(dlg)