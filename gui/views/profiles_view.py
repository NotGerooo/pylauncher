"""
gui/views/profiles_view.py — Gestión de perfiles
"""
import flet as ft
from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV, ACCENT_RED,
)
from utils.logger import get_logger

log = get_logger()


class ProfilesView:
    def __init__(self, page: ft.Page, app):
        self.page = page
        self.app  = app
        self._selected_id: str | None = None
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self):
        # ── Lista de perfiles ─────────────────────────────────────────────────
        self._profiles_col = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO,
                                        expand=True)

        list_card = ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.all(20), expand=True,
            content=ft.Column([
                ft.Row([
                    ft.Text("Mis perfiles", color=TEXT_PRI, size=14,
                            weight=ft.FontWeight.BOLD, expand=True),
                    ft.ElevatedButton(
                        "+ Nuevo",
                        bgcolor=GREEN, color=TEXT_INV,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                             padding=ft.padding.symmetric(horizontal=16, vertical=10)),
                        on_click=self._clear_form,
                    ),
                ]),
                ft.Container(height=12),
                self._profiles_col,
            ], spacing=0, expand=True),
        )

        # ── Formulario ────────────────────────────────────────────────────────
        self._name_field = ft.TextField(
            label="Nombre del perfil", color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN, border_radius=8,
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
        )
        self._version_dd = ft.Dropdown(
            label="Versión de Minecraft", color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN, border_radius=8,
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            options=[],
        )
        self._ram_dd = ft.Dropdown(
            label="RAM (MB)", color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN, border_radius=8,
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            value="2048",
            options=[ft.dropdown.Option(str(x)) for x in [1024,2048,3072,4096,6144,8192]],
        )
        self._form_title = ft.Text("Nuevo perfil", color=TEXT_PRI, size=14,
                                    weight=ft.FontWeight.BOLD)
        self._save_btn = ft.ElevatedButton(
            "Guardar perfil",
            bgcolor=GREEN, color=TEXT_INV,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                  padding=ft.padding.symmetric(horizontal=18, vertical=12)),
            on_click=self._on_save,
        )
        self._delete_btn = ft.ElevatedButton(
            "Eliminar perfil",
            bgcolor="#2d1515", color=ACCENT_RED,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                  padding=ft.padding.symmetric(horizontal=18, vertical=12)),
            on_click=self._on_delete,
            visible=False,
        )

        form_card = ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.all(24), width=300,
            content=ft.Column([
                self._form_title,
                ft.Container(height=16),
                self._name_field,
                ft.Container(height=12),
                self._version_dd,
                ft.Container(height=12),
                self._ram_dd,
                ft.Container(height=20),
                self._save_btn,
                ft.Container(height=8),
                self._delete_btn,
            ], spacing=0),
        )

        self.root = ft.Container(
            expand=True, bgcolor=BG,
            padding=ft.padding.all(32),
            content=ft.Column([
                ft.Text("Perfiles", color=TEXT_PRI, size=26,
                        weight=ft.FontWeight.BOLD),
                ft.Text("Crea y administra tus perfiles de juego",
                        color=TEXT_SEC, size=11),
                ft.Container(height=20),
                ft.Row([list_card, ft.Container(width=20), form_card],
                        expand=True, vertical_alignment=ft.CrossAxisAlignment.START),
            ], spacing=8),
        )

    # ── on_show ───────────────────────────────────────────────────────────────
    def on_show(self):
        self._refresh_list()
        self._refresh_versions()

    def _refresh_list(self):
        self._profiles_col.controls.clear()
        for p in self.app.profile_manager.get_all_profiles():
            is_sel = p.id == self._selected_id
            self._profiles_col.controls.append(
                ft.Container(
                    bgcolor=INPUT_BG if not is_sel else "#1a2520",
                    border=ft.border.all(1, GREEN if is_sel else "transparent"),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=16, vertical=12),
                    on_click=lambda e, pid=p.id: self._on_select(pid),
                    on_hover=lambda e: (
                        setattr(e.control, "bgcolor",
                                CARD2_BG if e.data=="true" else
                                (INPUT_BG if e.control.border==ft.border.all(1,"transparent") else "#1a2520"))
                        or e.control.update()),
                    content=ft.Row([
                        ft.Column([
                            ft.Text(p.name, color=TEXT_PRI, size=11,
                                    weight=ft.FontWeight.BOLD),
                            ft.Text(f"{p.version_id}  •  {p.ram_mb} MB",
                                    color=TEXT_SEC, size=9),
                        ], spacing=2, expand=True),
                        ft.Text("✓", color=GREEN, size=14) if is_sel
                        else ft.Container(),
                    ]),
                    data=p.id,
                )
            )
        try: self._profiles_col.update()
        except Exception: pass

    def _refresh_versions(self):
        installed = self.app.version_manager.get_installed_version_ids()
        self._version_dd.options = [ft.dropdown.Option(v) for v in installed]
        if installed and not self._version_dd.value:
            self._version_dd.value = installed[0]
        try: self._version_dd.update()
        except Exception: pass

    def _on_select(self, profile_id: str):
        self._selected_id = profile_id
        profile = self.app.profile_manager.get_profile(profile_id)
        if not profile:
            return
        self._form_title.value    = "Editar perfil"
        self._name_field.value    = profile.name
        self._version_dd.value    = profile.version_id
        self._ram_dd.value        = str(profile.ram_mb)
        self._delete_btn.visible  = True
        try:
            self._form_title.update()
            self._name_field.update()
            self._version_dd.update()
            self._ram_dd.update()
            self._delete_btn.update()
        except Exception: pass
        self._refresh_list()

    def _clear_form(self, e=None):
        self._selected_id        = None
        self._form_title.value   = "Nuevo perfil"
        self._name_field.value   = ""
        self._ram_dd.value       = "2048"
        self._delete_btn.visible = False
        try:
            self._form_title.update()
            self._name_field.update()
            self._version_dd.update()
            self._ram_dd.update()
            self._delete_btn.update()
        except Exception: pass
        self._refresh_list()

    def _on_save(self, e):
        name    = self._name_field.value.strip()
        version = self._version_dd.value
        ram     = self._ram_dd.value

        if not name or not version:
            self.app.snack("Nombre y versión son obligatorios.", error=True)
            return
        try:
            ram_mb = int(ram) if ram else 2048
            if self._selected_id:
                self.app.profile_manager.update_profile(
                    self._selected_id, name=name, version_id=version, ram_mb=ram_mb)
                self.app.snack("Perfil actualizado.")
            else:
                self.app.profile_manager.create_profile(name, version, ram_mb=ram_mb)
                self.app.snack("Perfil creado.")
            self._clear_form()
        except Exception as err:
            self.app.snack(str(err), error=True)

    def _on_delete(self, e):
        if not self._selected_id:
            return
        profile = self.app.profile_manager.get_profile(self._selected_id)
        if not profile:
            return

        def confirm(e2):
            self.page.close(dlg)
            try:
                self.app.profile_manager.delete_profile(self._selected_id)
                self.app.snack("Perfil eliminado.")
                self._clear_form()
            except Exception as err:
                self.app.snack(str(err), error=True)

        dlg = ft.AlertDialog(
            title=ft.Text("Confirmar eliminación", color=TEXT_PRI),
            content=ft.Text(f"¿Eliminar el perfil '{profile.name}'?", color=TEXT_SEC),
            bgcolor=CARD_BG,
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e2: self.page.close(dlg)),
                ft.ElevatedButton("Eliminar", bgcolor="#2d1515", color=ACCENT_RED,
                                   on_click=confirm),
            ],
        )
        self.page.open(dlg)