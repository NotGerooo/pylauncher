"""
gui/views/settings_view.py — Ajustes del launcher
"""
import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV,
)
from utils.logger import get_logger

log = get_logger()


class SettingsView:
    def __init__(self, page: ft.Page, app):
        self.page = page
        self.app  = app
        self._build()

    def _build(self):
        # ── RAM ──────────────────────────────────────────────────────────────
        self._ram_lbl = ft.Text(
            f"RAM: {self.app.settings.default_ram_mb} MB",
            color=TEXT_PRI, size=11, weight=ft.FontWeight.BOLD)
        self._ram_slider = ft.Slider(
            value=self.app.settings.default_ram_mb,
            min=512, max=16384, divisions=31,
            label="{value} MB",
            active_color=GREEN, inactive_color=INPUT_BG, thumb_color=GREEN,
            on_change=self._on_ram_change,
        )

        ram_card = self._card("Memoria RAM", [
            self._ram_lbl,
            ft.Container(height=8),
            self._ram_slider,
            ft.Text("RAM máxima asignada a Minecraft por defecto.",
                     color=TEXT_DIM, size=9),
        ])

        # ── Java ──────────────────────────────────────────────────────────────
        self._java_field = ft.TextField(
            value=self.app.settings.java_path,
            hint_text="Dejar vacío para detección automática",
            hint_style=ft.TextStyle(color=TEXT_DIM),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            expand=True,
            label="Ruta a java.exe",
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
        )
        self._java_info = ft.Text("", color=TEXT_DIM, size=9)

        java_card = self._card("Java", [
            ft.Row([
                self._java_field,
                ft.Container(width=10),
                ft.ElevatedButton(
                    "Detectar",
                    bgcolor=CARD2_BG, color=TEXT_PRI,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.padding.symmetric(horizontal=16, vertical=12),
                    ),
                    on_click=self._detect_java,
                ),
                ft.Container(width=8),
                ft.ElevatedButton(
                    "Guardar",
                    bgcolor=GREEN, color=TEXT_INV,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.padding.symmetric(horizontal=16, vertical=12),
                    ),
                    on_click=self._save_java,
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=6),
            self._java_info,
        ])

        # ── Launcher ──────────────────────────────────────────────────────────
        self._close_on_launch = ft.Switch(
            label="Cerrar launcher al iniciar el juego",
            label_style=ft.TextStyle(color=TEXT_PRI, size=10),
            value=self.app.settings.close_on_launch,
            active_color=GREEN,
            on_change=self._on_close_toggle,
        )

        launcher_card = self._card("Comportamiento", [
            self._close_on_launch,
        ])

        # ── Diagnóstico ───────────────────────────────────────────────────────
        self._diag_text = ft.Text("", color=TEXT_SEC, size=9,
                                   selectable=True, no_wrap=False)

        diag_card = self._card("Diagnóstico del sistema", [
            ft.ElevatedButton(
                "Ejecutar diagnóstico",
                bgcolor=CARD2_BG, color=TEXT_PRI,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                on_click=self._run_diag,
            ),
            ft.Container(height=10),
            self._diag_text,
        ])

        self.root = ft.Container(
            expand=True, bgcolor=BG,
            padding=ft.padding.all(32),
            content=ft.Column([
                ft.Text("Ajustes", color=TEXT_PRI, size=26,
                        weight=ft.FontWeight.BOLD),
                ft.Text("Configura el comportamiento del launcher",
                        color=TEXT_SEC, size=11),
                ft.Container(height=20),
                ram_card,
                ft.Container(height=16),
                java_card,
                ft.Container(height=16),
                launcher_card,
                ft.Container(height=16),
                diag_card,
            ], spacing=0, scroll=ft.ScrollMode.AUTO),
        )

    def on_show(self):
        self._ram_slider.value = self.app.settings.default_ram_mb
        self._ram_lbl.value    = f"RAM: {int(self.app.settings.default_ram_mb)} MB"
        self._java_field.value = self.app.settings.java_path
        try:
            self._ram_slider.update()
            self._ram_lbl.update()
            self._java_field.update()
        except Exception: pass

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _card(self, title: str, controls: list) -> ft.Container:
        return ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.all(24),
            content=ft.Column([
                ft.Text(title, color=TEXT_PRI, size=13,
                        weight=ft.FontWeight.BOLD),
                ft.Divider(height=1, color=BORDER),
                ft.Container(height=4),
                *controls,
            ], spacing=0),
        )

    # ── Handlers ─────────────────────────────────────────────────────────────
    def _on_ram_change(self, e):
        val = int(self._ram_slider.value)
        self._ram_lbl.value = f"RAM: {val} MB"
        self.app.settings.default_ram_mb = val
        try: self._ram_lbl.update()
        except Exception: pass

    def _detect_java(self, e):
        try:
            info = self.app.java_manager.get_java_info()
            if info["error"]:
                self._java_info.value = f"⚠ {info['error']}"
                self._java_info.color = "#ff6b6b"
            else:
                self._java_info.value = (
                    f"✓  {info['path']}  (Java {info['version']}, "
                    f"fuente: {info['source']})")
                self._java_info.color = GREEN
                self._java_field.value = info["path"]
                try: self._java_field.update()
                except Exception: pass
        except Exception as err:
            self._java_info.value = f"Error: {err}"
            self._java_info.color = "#ff6b6b"
        try: self._java_info.update()
        except Exception: pass

    def _save_java(self, e):
        path = self._java_field.value.strip()
        if not path:
            self.app.settings.java_path = ""
            self.app.snack("Ruta de Java borrada. Se usará detección automática.")
            return
        ok = self.app.java_manager.set_manual_java_path(path)
        if ok:
            self.app.snack("Ruta de Java guardada.")
        else:
            self.app.snack("Ruta inválida o Java demasiado viejo.", error=True)

    def _on_close_toggle(self, e):
        self.app.settings.close_on_launch = e.control.value

    def _run_diag(self, e):
        try:
            from utils.system_utils import get_system_info
            info = get_system_info()
            java_info = self.app.java_manager.get_java_info()
            installed = self.app.version_manager.get_installed_version_ids()
            lines = [
                f"OS: {info.get('os')}  arch: {info.get('architecture')}",
                f"RAM total: {info.get('ram_mb')} MB",
                f"Python: {info.get('python_version')}",
                f"Java: {java_info.get('path')} (v{java_info.get('version')})",
                f"Java fuente: {java_info.get('source')}",
                f"Versiones instaladas: {', '.join(installed) or 'ninguna'}",
                f"Carpeta .pylauncher: {self.app.settings.minecraft_dir}",
            ]
            self._diag_text.value = "\n".join(lines)
        except Exception as err:
            self._diag_text.value = f"Error: {err}"
        try: self._diag_text.update()
        except Exception: pass