"""
gui/views/library_view.py — Gero's Launcher
Vista Biblioteca: lista de instancias con botón crear/editar/lanzar.
"""
import threading
import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER, BORDER_BRIGHT,
    GREEN, GREEN_DIM, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV,
    ACCENT_RED, AVATAR_PALETTE,
)
from utils.logger import get_logger

log = get_logger()


class LibraryView:
    def __init__(self, page: ft.Page, app):
        self.page = page
        self.app  = app

        self._list_col = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

        self.root = ft.Container(
            expand=True,
            bgcolor=BG,
            padding=ft.padding.symmetric(horizontal=36, vertical=28),
            content=ft.Column(
                spacing=0,
                expand=True,
                controls=[
                    self._build_header(),
                    ft.Container(height=20),
                    self._list_col,
                ],
            ),
        )

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self) -> ft.Control:
        return ft.Row(
            controls=[
                ft.Column(
                    spacing=2,
                    expand=True,
                    controls=[
                        ft.Text("Biblioteca", color=TEXT_PRI, size=22,
                                weight=ft.FontWeight.BOLD),
                        ft.Text("Tus instancias de Minecraft",
                                color=TEXT_DIM, size=11),
                    ],
                ),
                ft.ElevatedButton(
                    "+ Nueva Instancia",
                    bgcolor=GREEN,
                    color=TEXT_INV,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=lambda e: self._open_create_dialog(),
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    def on_show(self):
        self._refresh()

    def _refresh(self):
        self._list_col.controls.clear()
        profiles = self.app.profile_manager.get_all_profiles()

        if not profiles:
            self._list_col.controls.append(self._empty_state())
        else:
            for profile in profiles:
                self._list_col.controls.append(self._build_card(profile))

        try:
            self._list_col.update()
        except Exception:
            pass

    # ── Estado vacío ──────────────────────────────────────────────────────────
    def _empty_state(self) -> ft.Control:
        return ft.Container(
            expand=True,
            content=ft.Column(
                controls=[
                    ft.Text("📦", size=52, text_align=ft.TextAlign.CENTER),
                    ft.Text("No tienes instancias creadas",
                            color=TEXT_SEC, size=14,
                            text_align=ft.TextAlign.CENTER),
                    ft.Text(
                        "Crea tu primera instancia con el botón '+ Nueva Instancia'",
                        color=TEXT_DIM, size=10,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=12),
                    ft.Row(
                        [ft.ElevatedButton(
                            "+ Nueva Instancia",
                            bgcolor=GREEN,
                            color=TEXT_INV,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=8)),
                            on_click=lambda e: self._open_create_dialog(),
                        )],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                expand=True,
            ),
        )

    # ── Tarjeta de instancia ──────────────────────────────────────────────────
    def _build_card(self, profile) -> ft.Control:
        last = profile.last_used[:10] if profile.last_used else "—"

        icon_box = ft.Container(
            width=48, height=48, border_radius=10,
            bgcolor=CARD2_BG,
            alignment=ft.alignment.center,
            content=ft.Text("⛏", size=22),
        )

        info_col = ft.Column(
            spacing=2,
            expand=True,
            controls=[
                ft.Text(profile.name, color=TEXT_PRI, size=13,
                        weight=ft.FontWeight.BOLD),
                ft.Text(
                    f"Minecraft {profile.version_id}  •  RAM: {profile.ram_mb} MB",
                    color=TEXT_SEC, size=9,
                ),
                ft.Text(f"Última vez: {last}", color=TEXT_DIM, size=8),
            ],
        )

        btn_play = ft.ElevatedButton(
            "▶ Jugar",
            bgcolor=GREEN,
            color=TEXT_INV,
            height=34,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
            on_click=lambda e, p=profile: self._open_launch_dialog(p),
        )
        btn_edit = ft.OutlinedButton(
            "✏ Editar",
            height=34,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                side=ft.BorderSide(1, BORDER_BRIGHT),
                color=TEXT_SEC,
            ),
            on_click=lambda e, p=profile: self._open_edit_dialog(p),
        )
        btn_del = ft.OutlinedButton(
            "🗑",
            height=34,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                side=ft.BorderSide(1, ACCENT_RED),
                color=ACCENT_RED,
            ),
            on_click=lambda e, p=profile: self._on_delete(p),
        )

        return ft.Container(
            bgcolor=CARD_BG,
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=20, vertical=14),
            border=ft.border.all(1, BORDER),
            content=ft.Row(
                controls=[
                    icon_box,
                    ft.Container(width=16),
                    info_col,
                    ft.Row([btn_play, btn_edit, btn_del], spacing=8),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    # ── Acciones ──────────────────────────────────────────────────────────────
    def _on_delete(self, profile):
        def confirm(e):
            if e.control.text == "Eliminar":
                try:
                    self.app.profile_manager.delete_profile(profile.id)
                    self._refresh()
                    self.app.snack(f"Instancia '{profile.name}' eliminada.")
                except Exception as ex:
                    self.app.snack(str(ex), error=True)
            self.page.close(dlg)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Eliminar instancia", color=TEXT_PRI),
            content=ft.Text(
                f"¿Eliminar '{profile.name}'?\nEsto no borra los archivos del juego.",
                color=TEXT_SEC,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=confirm),
                ft.TextButton(
                    "Eliminar",
                    style=ft.ButtonStyle(color=ACCENT_RED),
                    on_click=confirm,
                ),
            ],
        )
        self.page.open(dlg)

    def _open_create_dialog(self):
        _InstanceDialog(self.page, self.app, profile=None,
                        on_save=self._refresh).open()

    def _open_edit_dialog(self, profile):
        _InstanceDialog(self.page, self.app, profile=profile,
                        on_save=self._refresh).open()

    def _open_launch_dialog(self, profile):
        _LaunchDialog(self.page, self.app, profile).open()


# ── Diálogo crear / editar instancia ─────────────────────────────────────────

class _InstanceDialog:
    def __init__(self, page: ft.Page, app, profile, on_save):
        self.page    = page
        self.app     = app
        self.profile = profile
        self.on_save = on_save

        title_text = "Editar instancia" if profile else "Nueva instancia"

        self._name_field = ft.TextField(
            label="Nombre",
            bgcolor=INPUT_BG,
            color=TEXT_PRI,
            label_style=ft.TextStyle(color=TEXT_DIM),
            border_color=BORDER,
            focused_border_color=GREEN,
            border_radius=8,
            value=profile.name if profile else "",
        )

        installed = app.version_manager.get_installed_version_ids()
        self._version_dd = ft.Dropdown(
            label="Versión de Minecraft",
            bgcolor=INPUT_BG,
            color=TEXT_PRI,
            label_style=ft.TextStyle(color=TEXT_DIM),
            border_color=BORDER,
            focused_border_color=GREEN,
            border_radius=8,
            options=[ft.dropdown.Option(v) for v in installed],
            value=(profile.version_id if profile and profile.version_id in installed
                   else (installed[0] if installed else None)),
        )

        ram_opts = ["1024", "2048", "3072", "4096", "6144", "8192"]
        cur_ram  = str(profile.ram_mb) if profile else "2048"
        self._ram_dd = ft.Dropdown(
            label="RAM (MB)",
            bgcolor=INPUT_BG,
            color=TEXT_PRI,
            label_style=ft.TextStyle(color=TEXT_DIM),
            border_color=BORDER,
            focused_border_color=GREEN,
            border_radius=8,
            options=[ft.dropdown.Option(r) for r in ram_opts],
            value=cur_ram if cur_ram in ram_opts else "2048",
        )

        self._dlg = ft.AlertDialog(
            modal=True,
            bgcolor=CARD_BG,
            title=ft.Text(title_text, color=TEXT_PRI, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=360,
                content=ft.Column([
                    self._name_field,
                    ft.Container(height=8),
                    self._version_dd,
                    ft.Container(height=8),
                    self._ram_dd,
                ], spacing=0, tight=True),
            ),
            actions=[
                ft.TextButton("Cancelar",
                              style=ft.ButtonStyle(color=TEXT_SEC),
                              on_click=lambda e: self.page.close(self._dlg)),
                ft.ElevatedButton(
                    "Guardar",
                    bgcolor=GREEN,
                    color=TEXT_INV,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=self._on_save,
                ),
            ],
        )

    def open(self):
        self.page.open(self._dlg)

    def _on_save(self, e):
        name    = (self._name_field.value or "").strip()
        version = self._version_dd.value or ""
        ram_str = self._ram_dd.value or "2048"

        if not name:
            self._name_field.error_text = "El nombre no puede estar vacío"
            self._name_field.update()
            return
        if not version:
            self._version_dd.error_text = "Selecciona una versión"
            self._version_dd.update()
            return

        try:
            ram_mb = int(ram_str)
        except ValueError:
            ram_mb = 2048

        try:
            if self.profile:
                self.app.profile_manager.update_profile(
                    self.profile.id,
                    name=name, version_id=version, ram_mb=ram_mb,
                )
            else:
                self.app.profile_manager.create_profile(name, version, ram_mb=ram_mb)
            self.page.close(self._dlg)
            self.on_save()
            self.app.snack("Instancia guardada correctamente.")
        except Exception as ex:
            self.app.snack(str(ex), error=True)


# ── Diálogo lanzar juego ──────────────────────────────────────────────────────

class _LaunchDialog:
    def __init__(self, page: ft.Page, app, profile):
        self.page    = page
        self.app     = app
        self.profile = profile

        self._username_field = ft.TextField(
            label="Nombre de usuario",
            bgcolor=INPUT_BG,
            color=TEXT_PRI,
            label_style=ft.TextStyle(color=TEXT_DIM),
            border_color=BORDER,
            focused_border_color=GREEN,
            border_radius=8,
            value=app.settings.last_profile or "Player",
        )

        self._dlg = ft.AlertDialog(
            modal=True,
            bgcolor=CARD_BG,
            title=ft.Text(f"Lanzar  {profile.name}",
                          color=TEXT_PRI, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=320,
                content=ft.Column([
                    ft.Text(
                        f"Minecraft {profile.version_id}  •  {profile.ram_mb} MB RAM",
                        color=TEXT_DIM, size=10,
                    ),
                    ft.Container(height=12),
                    self._username_field,
                ], spacing=0, tight=True),
            ),
            actions=[
                ft.TextButton("Cancelar",
                              style=ft.ButtonStyle(color=TEXT_SEC),
                              on_click=lambda e: self.page.close(self._dlg)),
                ft.ElevatedButton(
                    "▶ Jugar",
                    bgcolor=GREEN,
                    color=TEXT_INV,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=self._on_launch,
                ),
            ],
        )

    def open(self):
        self.page.open(self._dlg)

    def _on_launch(self, e):
        username = (self._username_field.value or "").strip()
        if not username:
            self._username_field.error_text = "Ingresa tu nombre"
            self._username_field.update()
            return

        try:
            session      = self.app.auth_service.create_offline_session(username)
            version_data = self.app.version_manager.get_version_data(
                self.profile.version_id)
        except Exception as ex:
            self.app.snack(str(ex), error=True)
            return

        self.page.close(self._dlg)

        def launch_thread():
            try:
                def on_output(line):
                    log.info(f"[MC] {line}")

                process = self.app.launcher_engine.launch(
                    self.profile, session, version_data, on_output=on_output)
                self.app.settings.last_profile = self.profile.name
                log.info(f"Minecraft lanzado PID={process.pid}")

                process.wait()
                rc = process.returncode
                log.info(f"Minecraft cerrado con código: {rc}")
                if rc != 0:
                    self.app.snack(
                        f"Minecraft cerró con error (código {rc}). Revisa los logs.",
                        error=True)
            except Exception as ex:
                log.error(f"Error al lanzar: {ex}")
                self.app.snack(str(ex), error=True)

        threading.Thread(target=launch_thread, daemon=True).start()