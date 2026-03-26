"""
gui/views/accounts_view.py — Gestión de cuentas
Cuentas offline y autenticación Microsoft OAuth.
"""
import threading
import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV,
    ACCENT_RED, AVATAR_PALETTE,
)
from utils.logger import get_logger

log = get_logger()


class AccountsView:
    def __init__(self, page: ft.Page, app):
        self.page = page
        self.app  = app
        self._build()

    def _build(self):
        # ── Añadir cuenta offline ─────────────────────────────────────────────
        self._offline_field = ft.TextField(
            label="Nombre de usuario (offline)",
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, width=300,
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            on_submit=self._on_add_offline,
        )

        add_offline_card = ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.all(22),
            content=ft.Column([
                ft.Text("Cuenta Offline", color=TEXT_PRI, size=14,
                        weight=ft.FontWeight.BOLD),
                ft.Text("Juega sin cuenta de Mojang en servidores offline.",
                         color=TEXT_DIM, size=9),
                ft.Container(height=14),
                ft.Row([
                    self._offline_field,
                    ft.Container(width=12),
                    ft.ElevatedButton(
                        "Añadir",
                        bgcolor=GREEN, color=TEXT_INV,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.padding.symmetric(horizontal=20, vertical=13),
                        ),
                        on_click=self._on_add_offline,
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.END),
            ], spacing=0),
        )

        # ── Microsoft ─────────────────────────────────────────────────────────
        self._ms_status = ft.Text(
            "Autenticación Microsoft vía Device Code Flow",
            color=TEXT_DIM, size=9)
        self._ms_code_lbl   = ft.Text("", color=GREEN, size=20,
                                       weight=ft.FontWeight.BOLD, selectable=True)
        self._ms_url_lbl    = ft.Text("", color=TEXT_SEC, size=9, selectable=True)
        self._ms_code_row   = ft.Container(visible=False,
                                            content=ft.Column([
                                                ft.Text("Ve a:", color=TEXT_DIM, size=9),
                                                self._ms_url_lbl,
                                                ft.Text("e ingresa el código:",
                                                         color=TEXT_DIM, size=9),
                                                self._ms_code_lbl,
                                            ], spacing=2))

        ms_card = ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.all(22),
            content=ft.Column([
                ft.Row([
                    ft.Text("Microsoft / Xbox", color=TEXT_PRI, size=14,
                            weight=ft.FontWeight.BOLD, expand=True),
                    ft.Container(
                        bgcolor="#0d2d6e", border_radius=6,
                        padding=ft.padding.symmetric(horizontal=10, vertical=4),
                        content=ft.Text("Premium", color="#4dabf7", size=8,
                                        weight=ft.FontWeight.BOLD)),
                ]),
                self._ms_status,
                ft.Container(height=14),
                ft.ElevatedButton(
                    "Iniciar sesión con Microsoft",
                    bgcolor="#0d2d6e", color="#4dabf7",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                          padding=ft.padding.symmetric(horizontal=20, vertical=12)),
                    on_click=self._on_ms_login,
                ),
                ft.Container(height=10),
                self._ms_code_row,
            ], spacing=4),
        )

        # ── Lista de cuentas ──────────────────────────────────────────────────
        self._accounts_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO)

        accounts_card = ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.all(22), expand=True,
            content=ft.Column([
                ft.Text("Cuentas guardadas", color=TEXT_PRI, size=14,
                        weight=ft.FontWeight.BOLD),
                ft.Container(height=12),
                self._accounts_col,
            ], spacing=0, expand=True),
        )

        self.root = ft.Container(
            expand=True, bgcolor=BG,
            padding=ft.padding.all(32),
            content=ft.Column([
                ft.Text("Cuentas", color=TEXT_PRI, size=26,
                        weight=ft.FontWeight.BOLD),
                ft.Text("Gestiona las cuentas del launcher",
                        color=TEXT_SEC, size=11),
                ft.Container(height=20),
                ft.Row([
                    ft.Column([add_offline_card, ft.Container(height=16), ms_card],
                               spacing=0, expand=True),
                    ft.Container(width=20),
                    accounts_card,
                ], expand=True, vertical_alignment=ft.CrossAxisAlignment.START),
            ], spacing=8),
        )

    def on_show(self):
        self._refresh_accounts()

    def _refresh_accounts(self):
        self._accounts_col.controls.clear()
        try:
            accounts = self.app.account_manager.get_all_accounts()
            active   = self.app.account_manager.get_active_account()
            active_id = getattr(active, "id", None) if active else None
        except Exception:
            accounts  = []
            active_id = None

        if not accounts:
            self._accounts_col.controls.append(
                ft.Text("Sin cuentas guardadas.", color=TEXT_DIM, size=10))
        else:
            for acc in accounts:
                is_active = (getattr(acc, "id", None) == active_id)
                is_ms     = getattr(acc, "is_microsoft", False)
                color     = AVATAR_PALETTE[abs(hash(acc.username)) % len(AVATAR_PALETTE)]
                initials  = (acc.username[:2]).upper()
                tag_text  = "Microsoft" if is_ms else "Offline"
                tag_color = "#4dabf7" if is_ms else TEXT_DIM
                tag_bg    = "#0d2d6e" if is_ms else CARD2_BG

                self._accounts_col.controls.append(
                    ft.Container(
                        bgcolor="#1a2520" if is_active else INPUT_BG,
                        border=ft.border.all(1, GREEN if is_active else "transparent"),
                        border_radius=10,
                        padding=ft.padding.symmetric(horizontal=16, vertical=12),
                        content=ft.Row([
                            ft.Container(
                                width=36, height=36, border_radius=18,
                                bgcolor=color,
                                alignment=ft.alignment.center,
                                content=ft.Text(initials, color=TEXT_INV,
                                                size=11, weight=ft.FontWeight.BOLD),
                            ),
                            ft.Container(width=12),
                            ft.Column([
                                ft.Row([
                                    ft.Text(acc.username, color=TEXT_PRI,
                                            size=11, weight=ft.FontWeight.BOLD),
                                    ft.Container(
                                        bgcolor=tag_bg, border_radius=4,
                                        padding=ft.padding.symmetric(horizontal=8, vertical=2),
                                        content=ft.Text(tag_text, color=tag_color,
                                                         size=8, weight=ft.FontWeight.BOLD)),
                                    ft.Container(
                                        bgcolor="#172616", border_radius=4,
                                        padding=ft.padding.symmetric(horizontal=8, vertical=2),
                                        content=ft.Text("Activa", color=GREEN,
                                                         size=8, weight=ft.FontWeight.BOLD),
                                    ) if is_active else ft.Container(),
                                ], spacing=8),
                            ], spacing=2, expand=True),
                            ft.Row([
                                ft.TextButton(
                                    "Activar",
                                    style=ft.ButtonStyle(color=GREEN),
                                    on_click=lambda e, a=acc: self._set_active(a),
                                ) if not is_active else ft.Container(),
                                ft.IconButton(
                                    icon=ft.icons.DELETE_OUTLINE,
                                    icon_color=ACCENT_RED, icon_size=16,
                                    tooltip="Eliminar cuenta",
                                    on_click=lambda e, a=acc: self._delete_account(a),
                                ),
                            ], spacing=0),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    )
                )
        try: self._accounts_col.update()
        except Exception: pass

    def _on_add_offline(self, e):
        username = self._offline_field.value.strip()
        if not username:
            self.app.snack("Ingresa un nombre de usuario.", error=True)
            return
        try:
            from services.auth_service import AuthError
            # Validate username
            self.app.auth_service._validate_username(username)
            from services.account_manager import Account
            acc = Account(username=username, is_microsoft=False)
            self.app.account_manager.add_account(acc)
            self._offline_field.value = ""
            try: self._offline_field.update()
            except Exception: pass
            self._refresh_accounts()
            self.app.refresh_account_panel()
            self.app.snack(f"Cuenta '{username}' añadida.")
        except Exception as err:
            self.app.snack(str(err), error=True)

    def _set_active(self, account):
        try:
            self.app.account_manager.set_active_account(account.id)
            self._refresh_accounts()
            self.app.refresh_account_panel()
            self.app.snack(f"'{account.username}' es ahora la cuenta activa.")
        except Exception as err:
            self.app.snack(str(err), error=True)

    def _delete_account(self, account):
        def confirm(e2):
            self.page.close(dlg)
            try:
                self.app.account_manager.remove_account(account.id)
                self._refresh_accounts()
                self.app.refresh_account_panel()
                self.app.snack("Cuenta eliminada.")
            except Exception as err:
                self.app.snack(str(err), error=True)

        dlg = ft.AlertDialog(
            title=ft.Text("Eliminar cuenta", color=TEXT_PRI),
            content=ft.Text(f"¿Eliminar la cuenta '{account.username}'?",
                             color=TEXT_SEC),
            bgcolor=CARD_BG,
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e2: self.page.close(dlg)),
                ft.ElevatedButton("Eliminar", bgcolor="#2d1515", color=ACCENT_RED,
                                   on_click=confirm),
            ],
        )
        self.page.open(dlg)

    def _on_ms_login(self, e):
        self._ms_status.value = "Iniciando autenticación…"
        self._ms_code_row.visible = False
        try:
            self._ms_status.update()
            self._ms_code_row.update()
        except Exception: pass

        def auth():
            try:
                device = self.app.microsoft_auth.start_device_flow()
                code   = device.get("user_code", "")
                url    = device.get("verification_uri", "https://microsoft.com/link")

                def show_code():
                    self._ms_code_lbl.value  = code
                    self._ms_url_lbl.value   = url
                    self._ms_code_row.visible = True
                    self._ms_status.value    = "Esperando inicio de sesión…"
                    try:
                        self._ms_code_lbl.update()
                        self._ms_url_lbl.update()
                        self._ms_code_row.update()
                        self._ms_status.update()
                    except Exception: pass

                self.page.run_thread(show_code)

                result = self.app.microsoft_auth.poll_device_flow(device)
                if result:
                    acc = self.app.microsoft_auth.get_minecraft_account(result)
                    self.app.account_manager.add_account(acc)

                    def done():
                        self._ms_status.value    = "✓ Cuenta Microsoft añadida"
                        self._ms_code_row.visible = False
                        try:
                            self._ms_status.update()
                            self._ms_code_row.update()
                        except Exception: pass
                        self._refresh_accounts()
                        self.app.refresh_account_panel()
                        self.app.snack(f"Cuenta Microsoft '{acc.username}' añadida.")

                    self.page.run_thread(done)
                else:
                    def failed():
                        self._ms_status.value = "Autenticación cancelada o expirada."
                        self._ms_code_row.visible = False
                        try:
                            self._ms_status.update()
                            self._ms_code_row.update()
                        except Exception: pass
                    self.page.run_thread(failed)

            except Exception as err:
                def show_err():
                    self._ms_status.value     = f"Error: {err}"
                    self._ms_code_row.visible = False
                    try:
                        self._ms_status.update()
                        self._ms_code_row.update()
                    except Exception: pass
                self.page.run_thread(show_err)

        threading.Thread(target=auth, daemon=True).start()