"""
gui/views/accounts_view.py — Gestión de cuentas
Cuentas offline · Microsoft OAuth Device Flow · Skin 3D · Skin picker

LAYOUT v2 — Minimalista y limpio:
  ┌──────────────────────────────────────────────┐
  │  Header simple (título + cuenta activa)      │
  ├──────────────┬───────────────────────────────┤
  │  Agregar     │  Lista de cuentas             │
  │  cuenta      │                               │
  └──────────────┴───────────────────────────────┘
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

# ── Colores específicos de esta vista ─────────────────────────────────────────
MS_BLUE       = "#4dabf7"
MS_BG         = "#0a1929"
MS_BORDER     = "#1e3a5f"
OFFLINE_COLOR = "#ffa94d"

# UUIDs de Mojang para Steve y Alex (siempre disponibles en Crafatar)
_STEVE_UUID = "8667ba71-b85a-4004-af54-457a9734eed7"
_ALEX_UUID  = "ec561538-f3fd-461d-aff5-086b22154bce"


def _default_uuid(username: str) -> str:
    """Steve o Alex según paridad del hash del nombre (igual que Minecraft Java)."""
    return _ALEX_UUID if abs(hash(username)) % 2 == 0 else _STEVE_UUID


# ── URLs de skin ──────────────────────────────────────────────────────────────
def _head_url(username: str, uuid: str | None = None, size: int = 64) -> str:
    real_uuid = uuid if (uuid and uuid != "offline") else _default_uuid(username)
    return f"https://crafatar.com/avatars/{real_uuid}?size={size}&overlay=true"

def _body_url(username: str, uuid: str | None = None) -> str:
    real_uuid = uuid if (uuid and uuid != "offline") else _default_uuid(username)
    return f"https://crafatar.com/renders/body/{real_uuid}?scale=5&overlay=true"

def _local_skin_img(skin_path: str, width: int, height: int) -> ft.Image:
    return ft.Image(
        src=skin_path, width=width, height=height,
        fit=ft.ImageFit.CONTAIN,
        error_content=ft.Icon(ft.icons.BROKEN_IMAGE_ROUNDED, color=OFFLINE_COLOR),
    )


# ── Helpers pequeños ──────────────────────────────────────────────────────────
def _badge(text: str, color: str, bg) -> ft.Container:
    """Etiqueta de color (ej: OFFLINE, ACTIVA)."""
    return ft.Container(
        content=ft.Text(text, size=8, color=color, weight=ft.FontWeight.W_700),
        padding=ft.padding.symmetric(horizontal=7, vertical=3),
        bgcolor=bg, border_radius=5,
    )

def _icon_btn(icon, color, tooltip, on_click) -> ft.Container:
    """Botón de ícono compacto."""
    btn = ft.Container(
        width=28, height=28, border_radius=7,
        bgcolor="transparent",
        border=ft.border.all(1, BORDER),
        alignment=ft.alignment.center,
        tooltip=tooltip,
        content=ft.Icon(icon, size=13, color=color),
        on_click=on_click,
        animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
    )
    def _hover(e, c=btn):
        c.bgcolor = ft.colors.with_opacity(0.10, color) if e.data == "true" else "transparent"
        try: c.update()
        except Exception: pass
    btn.on_hover = _hover
    return btn


# ══════════════════════════════════════════════════════════════════════════════
class AccountsView:
    """Vista de gestión de cuentas del launcher."""

    def __init__(self, page: ft.Page, app):
        self.page = page
        self.app  = app
        self._pending_skin_id: str | None = None
        self._build()

    # ── BUILD PRINCIPAL ───────────────────────────────────────────────────────
    def _build(self):
        # FilePicker en overlay (requerido por Flet)
        self._skin_picker = ft.FilePicker(on_result=self._on_skin_picked)
        self.page.overlay.append(self._skin_picker)
        self.page.update()

        # ── Columna de lista de cuentas
        self._accounts_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

        # ── Layout principal: dos columnas
        self.root = ft.Container(
            expand=True, bgcolor=BG,
            padding=ft.padding.all(28),
            content=ft.Column([
                # Header
                self._build_header(),
                ft.Container(height=20),

                # Cuerpo: panel izquierdo (agregar) + lista derecha
                ft.Row([
                    # Columna izquierda — formularios fijos
                    ft.Container(
                        content=ft.Column([
                            self._build_offline_panel(),
                            ft.Container(height=12),
                            self._build_ms_panel(),
                        ], spacing=0),
                        width=290,
                    ),
                    ft.Container(width=20),

                    # Columna derecha — lista de cuentas
                    ft.Container(
                        expand=True,
                        content=ft.Column([
                            ft.Row([
                                ft.Text("Cuentas guardadas", color=TEXT_SEC, size=11,
                                        weight=ft.FontWeight.W_600),
                                ft.Container(expand=True),
                            ]),
                            ft.Container(height=10),
                            self._accounts_col,
                        ], spacing=0, expand=True),
                    ),
                ], expand=True, vertical_alignment=ft.CrossAxisAlignment.START),
            ], spacing=0),
        )

    # ── HEADER ────────────────────────────────────────────────────────────────
    def _build_header(self) -> ft.Row:
        """
        Título de la vista + pill de cuenta activa.
        El pill se actualiza en _refresh_accounts().
        """
        self._active_pill = ft.Container(visible=False)  # se rellena en _refresh_accounts

        return ft.Row([
            ft.Text("Cuentas", color=TEXT_PRI, size=22, weight=ft.FontWeight.BOLD),
            ft.Container(width=14),
            self._active_pill,
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _make_active_pill(self, acc) -> ft.Container:
        """Píldora pequeña que muestra quién está activo."""
        if not acc:
            return ft.Container(visible=False)
        name  = acc.username
        uuid  = getattr(acc, "uuid", None) or getattr(acc, "id", None)
        is_ms = getattr(acc, "is_microsoft", False)
        col   = MS_BLUE if is_ms else OFFLINE_COLOR

        return ft.Container(
            bgcolor=ft.colors.with_opacity(0.08, col),
            border=ft.border.all(1, ft.colors.with_opacity(0.25, col)),
            border_radius=20,
            padding=ft.padding.symmetric(horizontal=10, vertical=5),
            content=ft.Row([
                ft.Image(
                    src=_head_url(name, uuid, 32),
                    width=18, height=18,
                    fit=ft.ImageFit.COVER,
                    error_content=ft.Icon(ft.icons.PERSON_ROUNDED, size=14, color=col),
                ),
                ft.Container(width=6),
                ft.Text(name, color=col, size=10, weight=ft.FontWeight.W_600),
                ft.Container(width=6),
                ft.Container(width=5, height=5, border_radius=3, bgcolor=GREEN),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
        )

    # ── PANEL OFFLINE ─────────────────────────────────────────────────────────
    def _build_offline_panel(self) -> ft.Container:
        """Formulario para cuenta offline (sin internet)."""

        self._offline_preview = ft.Container(
            width=36, height=36, border_radius=8,
            bgcolor=INPUT_BG, border=ft.border.all(1, BORDER),
            alignment=ft.alignment.center,
            content=ft.Icon(ft.icons.PERSON_ROUNDED, color=TEXT_DIM, size=18),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        def _preview_update(e):
            name = self._offline_field.value.strip()
            if len(name) >= 3:
                self._offline_preview.content = ft.Image(
                    src=_head_url(name), width=36, height=36,
                    fit=ft.ImageFit.COVER,
                    error_content=ft.Icon(ft.icons.PERSON_ROUNDED, color=OFFLINE_COLOR, size=18),
                )
                self._offline_preview.border = ft.border.all(1, ft.colors.with_opacity(0.5, OFFLINE_COLOR))
            else:
                self._offline_preview.content = ft.Icon(ft.icons.PERSON_ROUNDED, color=TEXT_DIM, size=18)
                self._offline_preview.border = ft.border.all(1, BORDER)
            try: self._offline_preview.update()
            except Exception: pass

        self._offline_field = ft.TextField(
            label="Nombre de usuario", color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=OFFLINE_COLOR,
            border_radius=8,
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            on_change=_preview_update,
            on_submit=self._on_add_offline,
            expand=True,
        )

        return ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.all(18),
            border=ft.border.all(1, BORDER),
            content=ft.Column([
                # Título del panel
                ft.Row([
                    ft.Icon(ft.icons.PERSON_ROUNDED, color=OFFLINE_COLOR, size=15),
                    ft.Container(width=8),
                    ft.Text("Cuenta Offline", color=TEXT_PRI, size=12, weight=ft.FontWeight.W_600),
                    ft.Container(expand=True),
                    _badge("OFFLINE", OFFLINE_COLOR, ft.colors.with_opacity(0.10, OFFLINE_COLOR)),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=16, color=BORDER),

                # Fila: preview + campo de texto
                ft.Row([
                    self._offline_preview,
                    ft.Container(width=10),
                    self._offline_field,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=12),

                # Botón
                ft.ElevatedButton(
                    "Añadir cuenta",
                    icon=ft.icons.ADD_ROUNDED,
                    bgcolor=OFFLINE_COLOR, color="#1a0a00",
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.padding.symmetric(horizontal=16, vertical=12),
                    ),
                    on_click=self._on_add_offline,
                    expand=True,
                ),
            ], spacing=0),
        )

    # ── PANEL MICROSOFT ───────────────────────────────────────────────────────
    def _build_ms_panel(self) -> ft.Container:
        """Botón de inicio de sesión con Microsoft (Device Code Flow)."""

        self._ms_status   = ft.Text("Device Code Flow", color=TEXT_DIM, size=9)
        self._ms_code_lbl = ft.Text("", color=MS_BLUE, size=22,
                                     weight=ft.FontWeight.BOLD, selectable=True,
                                     font_family="Courier New")
        self._ms_url_lbl  = ft.Text("", color=TEXT_SEC, size=9, selectable=True)

        # Caja del código — solo visible cuando Microsoft responde
        self._ms_code_box = ft.Container(
            visible=False,
            bgcolor=MS_BG,
            border=ft.border.all(1, MS_BORDER),
            border_radius=10,
            padding=ft.padding.all(14),
            content=ft.Column([
                ft.Text("CÓDIGO DE DISPOSITIVO", color=MS_BLUE, size=8, weight=ft.FontWeight.BOLD),
                ft.Container(height=8),
                ft.Text("Visita:", color=TEXT_DIM, size=9),
                self._ms_url_lbl,
                ft.Container(height=8),
                ft.Text("Ingresa este código:", color=TEXT_DIM, size=9),
                ft.Container(height=4),
                self._ms_code_lbl,
                ft.Container(height=8),
                ft.ProgressBar(
                    value=None,
                    bgcolor=ft.colors.with_opacity(0.1, MS_BLUE),
                    color=MS_BLUE, height=2, border_radius=1,
                ),
            ], spacing=0),
        )

        return ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.all(18),
            border=ft.border.all(1, BORDER),
            content=ft.Column([
                # Título del panel
                ft.Row([
                    ft.Icon(ft.icons.WINDOW_ROUNDED, color=MS_BLUE, size=15),
                    ft.Container(width=8),
                    ft.Text("Microsoft / Xbox", color=TEXT_PRI, size=12, weight=ft.FontWeight.W_600),
                    ft.Container(expand=True),
                    _badge("PREMIUM", MS_BLUE, ft.colors.with_opacity(0.10, MS_BLUE)),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=16, color=BORDER),

                self._ms_status,
                ft.Container(height=12),

                # Botón de login
                ft.ElevatedButton(
                    "Iniciar sesión con Microsoft",
                    icon=ft.icons.LOGIN_ROUNDED,
                    bgcolor=MS_BG, color=MS_BLUE,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.padding.symmetric(horizontal=16, vertical=12),
                        side=ft.BorderSide(1, MS_BORDER),
                    ),
                    on_click=self._on_ms_login,
                    expand=True,
                ),
                ft.Container(height=10),
                self._ms_code_box,
            ], spacing=0),
        )

    # ── TARJETA DE CUENTA ─────────────────────────────────────────────────────
    def _make_account_card(self, acc, is_active: bool) -> ft.Container:
        """
        Tarjeta compacta para cada cuenta en la lista.
        [ cara ] nombre   tipo      [activar] [skin] [borrar]
        """
        name      = acc.username
        uuid      = getattr(acc, "uuid", None) or getattr(acc, "id", None)
        is_ms     = getattr(acc, "is_microsoft", False)
        skin_path = getattr(acc, "skin_path", None)
        col       = AVATAR_PALETTE[abs(hash(name)) % len(AVATAR_PALETTE)]
        initials  = name[:2].upper()
        label_col = MS_BLUE if is_ms else OFFLINE_COLOR
        label_txt = "Microsoft" if is_ms else "Offline"
        border_c  = ft.colors.with_opacity(0.40, GREEN) if is_active else BORDER

        # Cara del personaje
        if not is_ms and skin_path:
            head_content = _local_skin_img(skin_path, 36, 36)
        else:
            head_content = ft.Image(
                src=_head_url(name, uuid, 72),
                width=36, height=36, fit=ft.ImageFit.COVER,
                error_content=ft.Container(
                    bgcolor=col, alignment=ft.alignment.center,
                    content=ft.Text(initials, color=TEXT_INV, size=10, weight=ft.FontWeight.BOLD),
                ),
            )

        head = ft.Container(
            width=36, height=36, border_radius=8,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            border=ft.border.all(1, ft.colors.with_opacity(0.60, GREEN) if is_active else BORDER),
            content=head_content,
        )

        # Botones de acción
        actions: list[ft.Control] = []

        if not is_active:
            act_btn = ft.Container(
                content=ft.Text("Activar", color=GREEN, size=10, weight=ft.FontWeight.W_600),
                bgcolor=ft.colors.with_opacity(0.08, GREEN),
                border=ft.border.all(1, ft.colors.with_opacity(0.25, GREEN)),
                border_radius=7,
                padding=ft.padding.symmetric(horizontal=10, vertical=5),
                on_click=lambda e, a=acc: self._set_active(a),
                animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
            )
            act_btn.on_hover = lambda e, c=act_btn: (
                setattr(c, "bgcolor", ft.colors.with_opacity(0.18 if e.data=="true" else 0.08, GREEN))
                or c.update()
            )
            actions.append(act_btn)

        if not is_ms:
            skin_icon  = ft.icons.CHECK_CIRCLE_OUTLINE_ROUNDED if skin_path else ft.icons.IMAGE_ROUNDED
            skin_color = GREEN if skin_path else OFFLINE_COLOR
            actions.append(_icon_btn(
                skin_icon, skin_color,
                "Cambiar/quitar skin" if skin_path else "Añadir skin",
                lambda e, a=acc: self._open_skin_menu(a),
            ))

        actions.append(_icon_btn(
            ft.icons.DELETE_OUTLINE_ROUNDED, TEXT_DIM,
            "Eliminar cuenta",
            lambda e, a=acc: self._delete_account(a),
        ))

        card = ft.Container(
            bgcolor=ft.colors.with_opacity(0.05, GREEN) if is_active else INPUT_BG,
            border=ft.border.all(1, border_c),
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
            animate=ft.animation.Animation(180, ft.AnimationCurve.EASE_OUT),
            content=ft.Row([
                head,
                ft.Container(width=12),
                ft.Column([
                    ft.Row([
                        ft.Text(name, color=TEXT_PRI, size=12, weight=ft.FontWeight.W_600),
                        ft.Container(width=6),
                        _badge(label_txt, label_col, ft.colors.with_opacity(0.10, label_col)),
                        *([ ft.Container(width=4),
                            _badge("ACTIVA", GREEN, ft.colors.with_opacity(0.12, GREEN))
                          ] if is_active else []),
                        *([ ft.Container(width=4),
                            _badge("SKIN", OFFLINE_COLOR, ft.colors.with_opacity(0.10, OFFLINE_COLOR))
                          ] if (not is_ms and skin_path) else []),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(height=3),
                    ft.Text(
                        f"UUID: {str(uuid)[:14]}…" if uuid else "Modo Offline",
                        color=TEXT_DIM, size=8, font_family="Courier New",
                    ),
                ], spacing=0, expand=True),
                ft.Row(actions, spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        def _hover(e, c=card, active=is_active):
            if active: return
            c.bgcolor = ft.colors.with_opacity(0.04, TEXT_PRI) if e.data == "true" else INPUT_BG
            c.border  = ft.border.all(1, ft.colors.with_opacity(0.3, TEXT_DIM) if e.data == "true" else BORDER)
            try: c.update()
            except Exception: pass
        card.on_hover = _hover
        return card

    # ── GESTIÓN DE SKIN (solo offline) ───────────────────────────────────────
    def _open_skin_menu(self, acc):
        skin_path = getattr(acc, "skin_path", None)

        def _pick(e):
            self.page.close(dlg)
            self._pending_skin_id = acc.id
            self._skin_picker.pick_files(
                dialog_title="Selecciona una skin (.png)",
                allowed_extensions=["png"],
                allow_multiple=False,
            )

        def _remove(e):
            self.page.close(dlg)
            try:
                self.app.account_manager.update_skin(acc.id, None)
                self._refresh_accounts()
                self.app.snack("Skin eliminada.")
            except Exception as err:
                self.app.snack(str(err), error=True)

        actions = [ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(ft.icons.UPLOAD_ROUNDED, size=13, color=TEXT_INV),
                ft.Container(width=6),
                ft.Text("Subir skin (.png)", color=TEXT_INV, size=11),
            ], tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=OFFLINE_COLOR,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=14, vertical=9)),
            on_click=_pick,
        )]
        if skin_path:
            actions.insert(0, ft.TextButton(
                "Quitar skin", style=ft.ButtonStyle(color=ACCENT_RED), on_click=_remove
            ))
        actions.append(ft.TextButton(
            "Cancelar", style=ft.ButtonStyle(color=TEXT_SEC),
            on_click=lambda e: self.page.close(dlg)
        ))

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Skin — {acc.username}", color=TEXT_PRI, size=13, weight=ft.FontWeight.BOLD),
            content=ft.Text(
                f"Actual: {skin_path.split('/')[-1] if skin_path else 'Ninguna (Steve/Alex por defecto)'}\n"
                "Las skins deben ser PNG de 64×64 o 64×32 píxeles.",
                color=TEXT_SEC, size=10,
            ),
            bgcolor=CARD_BG, shape=ft.RoundedRectangleBorder(radius=12),
            actions=actions, actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg)

    def _on_skin_picked(self, e: ft.FilePickerResultEvent):
        if not e.files or not self._pending_skin_id:
            self._pending_skin_id = None
            return
        try:
            self.app.account_manager.update_skin(self._pending_skin_id, e.files[0].path)
            self._refresh_accounts()
            self.app.snack("Skin actualizada correctamente.")
        except Exception as err:
            self.app.snack(str(err), error=True)
        finally:
            self._pending_skin_id = None

    # ── LÓGICA ────────────────────────────────────────────────────────────────
    def on_show(self):
        """Se llama cada vez que el usuario navega a esta pantalla."""
        self._refresh_accounts()

    def _refresh_accounts(self):
        """Recarga la lista de cuentas y el header."""
        try:
            accounts  = self.app.account_manager.get_all_accounts()
            active    = self.app.account_manager.get_active_account()
            active_id = getattr(active, "id", None) if active else None
        except Exception:
            accounts, active_id, active = [], None, None

        # Actualiza el pill de cuenta activa en el header
        self._active_pill.content = self._make_active_pill(active).content
        self._active_pill.bgcolor = self._make_active_pill(active).bgcolor
        self._active_pill.border  = self._make_active_pill(active).border
        self._active_pill.border_radius = self._make_active_pill(active).border_radius
        self._active_pill.padding = self._make_active_pill(active).padding
        self._active_pill.visible = active is not None
        try: self._active_pill.update()
        except Exception: pass

        # Recarga la lista
        self._accounts_col.controls.clear()
        if not accounts:
            self._accounts_col.controls.append(
                ft.Container(
                    padding=ft.padding.all(24),
                    content=ft.Column([
                        ft.Icon(ft.icons.PERSON_OFF_OUTLINED, color=TEXT_DIM, size=30),
                        ft.Container(height=10),
                        ft.Text("Sin cuentas guardadas", color=TEXT_DIM, size=11,
                                text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                )
            )
        else:
            ordered = sorted(accounts, key=lambda a: 0 if getattr(a, "id", None) == active_id else 1)
            for acc in ordered:
                self._accounts_col.controls.append(
                    self._make_account_card(acc, getattr(acc, "id", None) == active_id)
                )
        try: self._accounts_col.update()
        except Exception: pass

    def _on_add_offline(self, e):
        username = self._offline_field.value.strip()
        if not username:
            self.app.snack("Ingresa un nombre de usuario.", error=True)
            return
        try:
            acc = self.app.account_manager.add_offline_account(username)
            self._offline_field.value = ""
            self._offline_preview.content = ft.Icon(ft.icons.PERSON_ROUNDED, color=TEXT_DIM, size=18)
            self._offline_preview.border = ft.border.all(1, BORDER)
            try: self._offline_field.update(); self._offline_preview.update()
            except Exception: pass
            self._refresh_accounts()
            self.app.refresh_account_panel()
            self.app.snack(f"Cuenta '{acc.username}' añadida.")
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
            modal=True,
            title=ft.Text("Eliminar cuenta", color=TEXT_PRI, size=13, weight=ft.FontWeight.BOLD),
            content=ft.Text(
                f"¿Eliminar '{account.username}'? Esta acción no se puede deshacer.",
                color=TEXT_SEC, size=11,
            ),
            bgcolor=CARD_BG, shape=ft.RoundedRectangleBorder(radius=12),
            actions=[
                ft.TextButton("Cancelar", style=ft.ButtonStyle(color=TEXT_SEC),
                    on_click=lambda e2: self.page.close(dlg)),
                ft.ElevatedButton(
                    "Eliminar", bgcolor=ACCENT_RED, color=TEXT_INV,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.padding.symmetric(horizontal=14, vertical=9)),
                    on_click=confirm,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg)

    # ── MICROSOFT DEVICE FLOW ─────────────────────────────────────────────────
    def _on_ms_login(self, e):
        """
        Inicia autenticación Microsoft.
        Device Flow: Microsoft genera un código → el usuario lo ingresa en
        microsoft.com/link → el launcher espera en segundo plano.
        """
        self._ms_status.value     = "Iniciando autenticación…"
        self._ms_code_box.visible = False
        try: self._ms_status.update(); self._ms_code_box.update()
        except Exception: pass

        def auth():
            try:
                device = self.app.microsoft_auth.start_device_flow()
                code   = device.get("user_code", "")
                url    = device.get("verification_uri", "https://microsoft.com/link")

                def show_code():
                    self._ms_code_lbl.value   = code
                    self._ms_url_lbl.value    = url
                    self._ms_code_box.visible = True
                    self._ms_status.value     = "Esperando en el navegador…"
                    try:
                        self._ms_code_lbl.update(); self._ms_url_lbl.update()
                        self._ms_code_box.update(); self._ms_status.update()
                    except Exception: pass
                self.page.run_thread(show_code)

                result = self.app.microsoft_auth.poll_device_flow(device)

                if result:
                    acc = self.app.microsoft_auth.get_minecraft_account(result)
                    self.app.account_manager.add_account(acc)
                    def done():
                        self._ms_status.value     = "✓ Cuenta Microsoft añadida"
                        self._ms_code_box.visible = False
                        try: self._ms_status.update(); self._ms_code_box.update()
                        except Exception: pass
                        self._refresh_accounts()
                        self.app.refresh_account_panel()
                        self.app.snack(f"¡Bienvenido, {acc.username}! 🎮")
                    self.page.run_thread(done)
                else:
                    def failed():
                        self._ms_status.value     = "Autenticación cancelada o expirada."
                        self._ms_code_box.visible = False
                        try: self._ms_status.update(); self._ms_code_box.update()
                        except Exception: pass
                    self.page.run_thread(failed)

            except Exception as err:
                def show_err():
                    self._ms_status.value     = f"Error: {err}"
                    self._ms_code_box.visible = False
                    try: self._ms_status.update(); self._ms_code_box.update()
                    except Exception: pass
                self.page.run_thread(show_err)

        threading.Thread(target=auth, daemon=True).start()