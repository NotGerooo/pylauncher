"""
gui/views/accounts_view.py — Gestión de cuentas ✦ Premium Edition
Cuentas offline y autenticación Microsoft OAuth.
Skin renders · Glows · Animaciones · Hero section · Device Flow UI
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

# ── Skin API helpers ──────────────────────────────────────────────────────────
def _head_url(username: str, uuid: str | None = None, size: int = 64) -> str:
    """Avatar de cabeza desde Crafatar (UUID) o Minotar (username)."""
    if uuid and uuid != "offline":
        return f"https://crafatar.com/avatars/{uuid}?size={size}&overlay=true"
    return f"https://minotar.net/avatar/{username}/{size}"

def _body_url(username: str, uuid: str | None = None, size: int = 256) -> str:
    """Render de cuerpo completo desde Crafatar o Minotar."""
    if uuid and uuid != "offline":
        return f"https://crafatar.com/renders/body/{uuid}?size={size}&overlay=true"
    return f"https://minotar.net/body/{username}/{size}"

# ── Paleta Microsoft ──────────────────────────────────────────────────────────
MS_BLUE   = "#4dabf7"
MS_BG     = "#0a1929"
MS_BORDER = "#1e3a5f"

OFFLINE_COLOR = "#ffa94d"
OFFLINE_BG    = "#1f1200"

# ─────────────────────────────────────────────────────────────────────────────
class AccountsView:
    def __init__(self, page: ft.Page, app):
        self.page = page
        self.app  = app
        self._ms_device_thread = None
        self._build()

    # ═══════════════════════════════════════════════════════════════════════════
    #  BUILD
    # ═══════════════════════════════════════════════════════════════════════════
    def _build(self):
        # ── Hero: cuenta activa ───────────────────────────────────────────────
        self._hero = ft.Container(
            height=0,       # se expande al llamar on_show
            animate=ft.animation.Animation(400, ft.AnimationCurve.EASE_OUT),
        )

        # ── Columna de cuentas ────────────────────────────────────────────────
        self._accounts_col = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)

        accounts_panel = ft.Container(
            bgcolor=CARD_BG, border_radius=16,
            padding=ft.padding.all(24), expand=True,
            border=ft.border.all(1, BORDER),
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.icons.PEOPLE_ROUNDED, color=TEXT_SEC, size=18),
                    ft.Container(width=8),
                    ft.Text("Cuentas guardadas", color=TEXT_PRI, size=14,
                            weight=ft.FontWeight.BOLD, expand=True),
                    self._small_badge("Panel", TEXT_DIM, CARD2_BG),
                ]),
                ft.Divider(height=18, color=BORDER),
                self._accounts_col,
            ], spacing=0, expand=True),
        )

        # ── Panel izquierdo (add forms) ───────────────────────────────────────
        left = ft.Column([
            self._build_offline_card(),
            ft.Container(height=14),
            self._build_ms_card(),
        ], spacing=0)

        self.root = ft.Container(
            expand=True, bgcolor=BG,
            padding=ft.padding.all(32),
            content=ft.Column([
                # Cabecera
                ft.Row([
                    ft.Column([
                        ft.Text("Cuentas", color=TEXT_PRI, size=28,
                                weight=ft.FontWeight.BOLD),
                        ft.Text("Gestiona identidades del launcher",
                                color=TEXT_DIM, size=11),
                    ], spacing=2, expand=True),
                    # Decoración: logo pixelart Minecraft (creeper face)
                    self._mc_logo_badge(),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),

                ft.Container(height=18),
                self._hero,
                ft.Container(height=14),

                ft.Row([
                    ft.Container(content=left, width=310),
                    ft.Container(width=20),
                    accounts_panel,
                ], expand=True, vertical_alignment=ft.CrossAxisAlignment.START),
            ], spacing=0),
        )

    # ═══════════════════════════════════════════════════════════════════════════
    #  OFFLINE CARD
    # ═══════════════════════════════════════════════════════════════════════════
    def _build_offline_card(self) -> ft.Container:
        self._offline_field = ft.TextField(
            label="Nombre de usuario",
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=OFFLINE_COLOR,
            border_radius=10,
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            content_padding=ft.padding.symmetric(horizontal=14, vertical=12),
            on_submit=self._on_add_offline,
            expand=True,
            prefix_icon=ft.icons.PERSON_OUTLINE_ROUNDED,
        )
        self._offline_preview = ft.Container(
            width=48, height=48, border_radius=10,
            bgcolor=CARD2_BG,
            border=ft.border.all(1, BORDER),
            alignment=ft.alignment.center,
            content=ft.Icon(ft.icons.PERSON_ROUNDED, color=TEXT_DIM, size=22),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        def _preview_update(e):
            name = self._offline_field.value.strip()
            if len(name) >= 3:
                self._offline_preview.content = ft.Image(
                    src=_head_url(name),
                    width=48, height=48, fit=ft.ImageFit.COVER,
                    error_content=ft.Icon(ft.icons.PERSON_ROUNDED,
                                          color=OFFLINE_COLOR, size=22),
                )
            else:
                self._offline_preview.content = ft.Icon(
                    ft.icons.PERSON_ROUNDED, color=TEXT_DIM, size=22)
            try:
                self._offline_preview.update()
            except Exception:
                pass

        self._offline_field.on_change = _preview_update

        add_btn = ft.ElevatedButton(
            "Añadir",
            bgcolor=OFFLINE_COLOR, color="#1a0a00",
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.padding.symmetric(horizontal=20, vertical=14),
                overlay_color=ft.colors.with_opacity(0.15, "#ffffff"),
            ),
            on_click=self._on_add_offline,
        )

        return ft.Container(
            bgcolor=CARD_BG, border_radius=16,
            padding=ft.padding.all(22),
            border=ft.border.all(1, BORDER),
            shadow=[ft.BoxShadow(
                spread_radius=0, blur_radius=20,
                color=ft.colors.with_opacity(0.08, OFFLINE_COLOR),
                offset=ft.Offset(0, 4),
            )],
            content=ft.Column([
                # Header
                ft.Row([
                    ft.Container(
                        width=36, height=36, border_radius=10,
                        bgcolor=OFFLINE_BG,
                        border=ft.border.all(1, ft.colors.with_opacity(0.3, OFFLINE_COLOR)),
                        alignment=ft.alignment.center,
                        content=ft.Icon(ft.icons.PERSON_ROUNDED,
                                        color=OFFLINE_COLOR, size=18),
                    ),
                    ft.Container(width=12),
                    ft.Column([
                        ft.Text("Cuenta Offline", color=TEXT_PRI, size=13,
                                weight=ft.FontWeight.BOLD),
                        ft.Text("Sin autenticación Mojang",
                                color=TEXT_DIM, size=9),
                    ], spacing=2, expand=True),
                    self._small_badge("OFFLINE", OFFLINE_COLOR,
                                      ft.colors.with_opacity(0.12, OFFLINE_COLOR)),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),

                ft.Divider(height=18, color=BORDER),

                # Skin preview + campo
                ft.Row([
                    self._offline_preview,
                    ft.Container(width=12),
                    self._offline_field,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),

                ft.Container(height=12),
                ft.Row([
                    ft.Container(expand=True),
                    add_btn,
                ]),
            ], spacing=0),
        )

    # ═══════════════════════════════════════════════════════════════════════════
    #  MICROSOFT CARD
    # ═══════════════════════════════════════════════════════════════════════════
    def _build_ms_card(self) -> ft.Container:
        self._ms_status     = ft.Text("Autenticación vía Device Code Flow",
                                       color=TEXT_DIM, size=9)
        self._ms_code_lbl   = ft.Text("", color=MS_BLUE, size=26,
                                       weight=ft.FontWeight.BOLD,
                                       selectable=True,
                                       font_family="Courier New")
        self._ms_url_lbl    = ft.Text("", color=TEXT_SEC, size=9, selectable=True)

        # Caja de código estilizada
        self._ms_code_box = ft.Container(
            visible=False,
            bgcolor=MS_BG,
            border=ft.border.all(1, MS_BORDER),
            border_radius=12,
            padding=ft.padding.all(18),
            shadow=[ft.BoxShadow(
                spread_radius=0, blur_radius=24,
                color=ft.colors.with_opacity(0.25, MS_BLUE),
                offset=ft.Offset(0, 4),
            )],
            animate_opacity=ft.animation.Animation(300, ft.AnimationCurve.EASE_OUT),
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        width=8, height=8, border_radius=4,
                        bgcolor=MS_BLUE,
                        shadow=[ft.BoxShadow(
                            spread_radius=0, blur_radius=8,
                            color=ft.colors.with_opacity(0.8, MS_BLUE),
                            offset=ft.Offset(0, 0),
                        )],
                        animate=ft.animation.Animation(
                            600, ft.AnimationCurve.EASE_IN_OUT),
                    ),
                    ft.Container(width=8),
                    ft.Text("CÓDIGO DE DISPOSITIVO", color=MS_BLUE,
                            size=8, weight=ft.FontWeight.BOLD),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=12),
                ft.Text("Visita:", color=TEXT_DIM, size=9),
                ft.Container(height=2),
                self._ms_url_lbl,
                ft.Container(height=10),
                ft.Text("Ingresa este código:", color=TEXT_DIM, size=9),
                ft.Container(height=4),
                ft.Container(
                    bgcolor=ft.colors.with_opacity(0.08, MS_BLUE),
                    border=ft.border.all(1, ft.colors.with_opacity(0.3, MS_BLUE)),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=16, vertical=10),
                    content=ft.Row([
                        ft.Container(expand=True),
                        self._ms_code_lbl,
                        ft.Container(expand=True),
                    ]),
                ),
                ft.Container(height=10),
                # Barra de progreso
                ft.ProgressBar(
                    value=None,
                    bgcolor=ft.colors.with_opacity(0.1, MS_BLUE),
                    color=MS_BLUE,
                    height=2,
                    border_radius=1,
                ),
            ], spacing=0),
        )

        # Botón con logo MS SVG integrado
        ms_btn = ft.ElevatedButton(
            content=ft.Row([
                self._ms_logo_icon(),
                ft.Container(width=10),
                ft.Text("Iniciar sesión con Microsoft",
                        color=MS_BLUE, size=11, weight=ft.FontWeight.W_600),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER,
               tight=True),
            bgcolor=MS_BG,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.padding.symmetric(horizontal=20, vertical=14),
                overlay_color=ft.colors.with_opacity(0.1, MS_BLUE),
                side=ft.BorderSide(1, MS_BORDER),
            ),
            on_click=self._on_ms_login,
        )

        return ft.Container(
            bgcolor=CARD_BG, border_radius=16,
            padding=ft.padding.all(22),
            border=ft.border.all(1, BORDER),
            shadow=[ft.BoxShadow(
                spread_radius=0, blur_radius=20,
                color=ft.colors.with_opacity(0.1, MS_BLUE),
                offset=ft.Offset(0, 4),
            )],
            content=ft.Column([
                # Header
                ft.Row([
                    ft.Container(
                        width=36, height=36, border_radius=10,
                        bgcolor=MS_BG,
                        border=ft.border.all(1, MS_BORDER),
                        alignment=ft.alignment.center,
                        content=self._ms_logo_icon(size=18),
                    ),
                    ft.Container(width=12),
                    ft.Column([
                        ft.Row([
                            ft.Text("Microsoft / Xbox", color=TEXT_PRI, size=13,
                                    weight=ft.FontWeight.BOLD),
                        ]),
                        ft.Text("Autenticación oficial de Mojang",
                                color=TEXT_DIM, size=9),
                    ], spacing=2, expand=True),
                    self._small_badge("PREMIUM", MS_BLUE,
                                      ft.colors.with_opacity(0.12, MS_BLUE)),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),

                ft.Divider(height=18, color=BORDER),

                self._ms_status,
                ft.Container(height=14),
                ms_btn,
                ft.Container(height=12),
                self._ms_code_box,
            ], spacing=0),
        )

    # ═══════════════════════════════════════════════════════════════════════════
    #  HERO — cuenta activa
    # ═══════════════════════════════════════════════════════════════════════════
    def _build_hero(self, acc) -> ft.Container:
        if not acc:
            return ft.Container(height=0)

        name     = acc.username
        uuid     = getattr(acc, "id", None)
        is_ms    = getattr(acc, "is_microsoft", False)
        col      = AVATAR_PALETTE[abs(hash(name)) % len(AVATAR_PALETTE)]
        initials = (name[:2]).upper()
        glow_col = GREEN if is_ms else OFFLINE_COLOR

        # Body render del skin
        skin_body = ft.Container(
            width=80, height=120,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Image(
                src=_body_url(name, uuid, 256),
                width=80, height=120,
                fit=ft.ImageFit.CONTAIN,
                error_content=ft.Container(
                    width=80, height=120,
                    alignment=ft.alignment.center,
                    content=ft.Text(initials, color=TEXT_INV, size=22,
                                    weight=ft.FontWeight.BOLD),
                    bgcolor=col,
                    border_radius=10,
                ),
            ),
        )
        # Glow bajo el skin
        skin_glow = ft.Container(
            width=80, height=20,
            gradient=ft.RadialGradient(
                center=ft.alignment.center,
                radius=1.0,
                colors=[
                    ft.colors.with_opacity(0.5, glow_col),
                    ft.colors.with_opacity(0.0, glow_col),
                ],
            ),
        )

        label_txt = "Microsoft" if is_ms else "Offline"
        label_col = MS_BLUE if is_ms else OFFLINE_COLOR
        label_bg  = ft.colors.with_opacity(0.12, label_col)

        return ft.Container(
            border_radius=18,
            border=ft.border.all(1, ft.colors.with_opacity(0.4, glow_col)),
            shadow=[ft.BoxShadow(
                spread_radius=0, blur_radius=32,
                color=ft.colors.with_opacity(0.22, glow_col),
                offset=ft.Offset(0, 4),
            )],
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            gradient=ft.LinearGradient(
                begin=ft.alignment.center_left,
                end=ft.alignment.center_right,
                colors=[
                    ft.colors.with_opacity(0.18, glow_col),
                    CARD_BG,
                    CARD_BG,
                ],
            ),
            content=ft.Row([
                # Izquierda: skin
                ft.Container(
                    width=140, height=160,
                    padding=ft.padding.only(left=24, top=10, bottom=0),
                    content=ft.Column([
                        skin_body,
                        skin_glow,
                    ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    alignment=ft.alignment.bottom_center,
                ),

                # Centro: info
                ft.Column([
                    ft.Container(height=8),
                    ft.Row([
                        ft.Container(
                            width=8, height=8, border_radius=4,
                            bgcolor=glow_col,
                            shadow=[ft.BoxShadow(
                                spread_radius=0, blur_radius=10,
                                color=ft.colors.with_opacity(0.8, glow_col),
                                offset=ft.Offset(0, 0),
                            )],
                        ),
                        ft.Container(width=8),
                        ft.Text("JUGANDO COMO", color=TEXT_DIM, size=8,
                                weight=ft.FontWeight.BOLD),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(height=10),
                    ft.Text(name, color=TEXT_PRI, size=22,
                            weight=ft.FontWeight.BOLD),
                    ft.Container(height=8),
                    ft.Row([
                        self._small_badge(label_txt.upper(), label_col, label_bg),
                        ft.Container(width=6),
                        self._small_badge("ACTIVA", GREEN,
                                          ft.colors.with_opacity(0.12, GREEN)),
                    ]),
                    ft.Container(height=10),
                    ft.Text(f"UUID: {str(uuid)[:8]}…" if uuid else "Sin UUID",
                            color=TEXT_DIM, size=8,
                            font_family="Courier New"),
                ], spacing=0, expand=True,
                   alignment=ft.MainAxisAlignment.CENTER),

                # Derecha: head grande + botón
                ft.Container(
                    padding=ft.padding.only(right=24, top=20, bottom=20),
                    content=ft.Column([
                        ft.Container(
                            width=72, height=72, border_radius=14,
                            clip_behavior=ft.ClipBehavior.HARD_EDGE,
                            border=ft.border.all(2, ft.colors.with_opacity(0.5, glow_col)),
                            shadow=[ft.BoxShadow(
                                spread_radius=0, blur_radius=18,
                                color=ft.colors.with_opacity(0.4, glow_col),
                                offset=ft.Offset(0, 0),
                            )],
                            content=ft.Image(
                                src=_head_url(name, uuid, 128),
                                width=72, height=72,
                                fit=ft.ImageFit.COVER,
                                error_content=ft.Container(
                                    bgcolor=col,
                                    alignment=ft.alignment.center,
                                    content=ft.Text(initials, color=TEXT_INV,
                                                    size=18, weight=ft.FontWeight.BOLD),
                                ),
                            ),
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                       alignment=ft.MainAxisAlignment.CENTER,
                       expand=True),
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            height=160,
        )

    # ═══════════════════════════════════════════════════════════════════════════
    #  ACCOUNT CARD
    # ═══════════════════════════════════════════════════════════════════════════
    def _make_account_card(self, acc, is_active: bool) -> ft.Container:
        name     = acc.username
        uuid     = getattr(acc, "id", None)
        is_ms    = getattr(acc, "is_microsoft", False)
        col      = AVATAR_PALETTE[abs(hash(name)) % len(AVATAR_PALETTE)]
        initials = (name[:2]).upper()

        glow_col  = GREEN if is_active else ("transparent")
        label_col = MS_BLUE if is_ms else OFFLINE_COLOR
        label_bg  = ft.colors.with_opacity(0.12, label_col)
        label_txt = "Microsoft" if is_ms else "Offline"

        # Cabeza del skin
        head = ft.Container(
            width=44, height=44, border_radius=10,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            border=ft.border.all(
                2,
                ft.colors.with_opacity(0.6, GREEN) if is_active else BORDER,
            ),
            shadow=[ft.BoxShadow(
                spread_radius=0, blur_radius=10,
                color=ft.colors.with_opacity(0.35, GREEN if is_active else col),
                offset=ft.Offset(0, 2),
            )],
            content=ft.Image(
                src=_head_url(name, uuid, 88),
                width=44, height=44,
                fit=ft.ImageFit.COVER,
                error_content=ft.Container(
                    bgcolor=col, alignment=ft.alignment.center,
                    content=ft.Text(initials, color=TEXT_INV,
                                    size=12, weight=ft.FontWeight.BOLD),
                ),
            ),
        )

        # Status dot
        dot_col = GREEN if is_active else TEXT_DIM
        status_dot = ft.Container(
            width=7, height=7, border_radius=4,
            bgcolor=dot_col,
            shadow=[ft.BoxShadow(
                spread_radius=0, blur_radius=8,
                color=ft.colors.with_opacity(0.8 if is_active else 0, dot_col),
                offset=ft.Offset(0, 0),
            )],
        )

        # Botones
        actions: list[ft.Control] = []
        if not is_active:
            act_btn = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.PLAY_ARROW_ROUNDED, size=12, color=GREEN),
                    ft.Container(width=4),
                    ft.Text("Activar", color=GREEN, size=10,
                            weight=ft.FontWeight.W_600),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
                bgcolor=ft.colors.with_opacity(0.08, GREEN),
                border=ft.border.all(1, ft.colors.with_opacity(0.3, GREEN)),
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                on_click=lambda e, a=acc: self._set_active(a),
                animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
            )
            act_btn.on_hover = lambda e, c=act_btn: (
                setattr(c, "bgcolor", ft.colors.with_opacity(
                    0.15 if e.data == "true" else 0.08, GREEN))
                or c.update()
            )
            actions.append(act_btn)

        del_btn = ft.Container(
            width=30, height=30, border_radius=8,
            bgcolor="transparent",
            border=ft.border.all(1, BORDER),
            alignment=ft.alignment.center,
            content=ft.Icon(ft.icons.DELETE_OUTLINE_ROUNDED,
                            size=14, color=TEXT_DIM),
            on_click=lambda e, a=acc: self._delete_account(a),
            animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
        )
        del_btn.on_hover = lambda e, c=del_btn: (
            setattr(c, "bgcolor",
                    ft.colors.with_opacity(0.12, ACCENT_RED) if e.data == "true"
                    else "transparent") or
            setattr(c.content, "color",
                    ACCENT_RED if e.data == "true" else TEXT_DIM) or
            c.update()
        )
        actions.append(del_btn)

        card = ft.Container(
            bgcolor=(ft.colors.with_opacity(0.06, GREEN) if is_active
                     else INPUT_BG),
            border=ft.border.all(
                1,
                ft.colors.with_opacity(0.4, GREEN) if is_active else BORDER,
            ),
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            shadow=[ft.BoxShadow(
                spread_radius=0, blur_radius=18,
                color=ft.colors.with_opacity(0.15 if is_active else 0, GREEN),
                offset=ft.Offset(0, 2),
            )],
            animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT),
            content=ft.Row([
                head,
                ft.Container(width=14),
                ft.Column([
                    ft.Row([
                        status_dot,
                        ft.Container(width=6),
                        ft.Text(name, color=TEXT_PRI, size=12,
                                weight=ft.FontWeight.BOLD),
                        ft.Container(width=8),
                        self._small_badge(label_txt, label_col, label_bg),
                        *(
                            [ft.Container(width=4),
                             self._small_badge("ACTIVA", GREEN,
                                              ft.colors.with_opacity(0.12, GREEN))]
                            if is_active else []
                        ),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(height=4),
                    ft.Text(
                        f"UUID: {str(uuid)[:12]}…" if uuid else "Modo Offline",
                        color=TEXT_DIM, size=8,
                        font_family="Courier New",
                    ),
                ], spacing=0, expand=True),
                ft.Row(actions, spacing=8,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        def _hover(e, c=card, active=is_active):
            if active:
                return
            c.bgcolor = (INPUT_BG if e.data != "true"
                         else ft.colors.with_opacity(0.04, TEXT_PRI))
            c.border  = ft.border.all(
                1, BORDER if e.data != "true"
                else ft.colors.with_opacity(0.4, TEXT_DIM),
            )
            try:
                c.update()
            except Exception:
                pass

        card.on_hover = _hover
        return card

    # ═══════════════════════════════════════════════════════════════════════════
    #  HELPERS UI
    # ═══════════════════════════════════════════════════════════════════════════
    @staticmethod
    def _small_badge(text: str, color: str, bg) -> ft.Container:
        return ft.Container(
            content=ft.Text(text, size=8, color=color,
                            weight=ft.FontWeight.W_700),
            padding=ft.padding.symmetric(horizontal=8, vertical=3),
            bgcolor=bg,
            border_radius=6,
            border=ft.border.all(1, ft.colors.with_opacity(0.25, color)),
        )

    @staticmethod
    def _mc_logo_badge() -> ft.Container:
        """Creeper face mini pixelart via Container grid."""
        green  = "#4caf50"
        dark   = "#1b5e20"
        black  = "#000000"
        size   = 6

        # 8×8 creeper face pattern (0=transparent, 1=green, 2=dark, 3=black)
        pattern = [
            [1,1,1,1,1,1,1,1],
            [1,1,1,1,1,1,1,1],
            [1,3,3,1,1,3,3,1],
            [1,3,3,1,1,3,3,1],
            [1,1,1,3,3,1,1,1],
            [1,1,3,3,3,3,1,1],
            [1,1,3,1,1,3,1,1],
            [1,1,1,1,1,1,1,1],
        ]
        colors_map = {1: green, 2: dark, 3: black, 0: "transparent"}
        rows = []
        for row in pattern:
            cells = []
            for cell in row:
                cells.append(ft.Container(
                    width=size, height=size,
                    bgcolor=colors_map[cell],
                ))
            rows.append(ft.Row(cells, spacing=0))
        return ft.Container(
            bgcolor=CARD2_BG,
            border=ft.border.all(1, BORDER),
            border_radius=10,
            padding=ft.padding.all(8),
            content=ft.Column(rows, spacing=0),
        )

    @staticmethod
    def _ms_logo_icon(size: int = 14) -> ft.Stack:
        """Logo Microsoft 4 cuadrados de colores."""
        half  = size // 2
        gap   = max(1, size // 8)
        total = half * 2 + gap
        return ft.Stack([
            ft.Container(width=half, height=half, bgcolor="#f25022",
                         left=0, top=0, border_radius=1),
            ft.Container(width=half, height=half, bgcolor="#7fba00",
                         left=half + gap, top=0, border_radius=1),
            ft.Container(width=half, height=half, bgcolor="#00a4ef",
                         left=0, top=half + gap, border_radius=1),
            ft.Container(width=half, height=half, bgcolor="#ffb900",
                         left=half + gap, top=half + gap, border_radius=1),
        ], width=total, height=total)

    # ═══════════════════════════════════════════════════════════════════════════
    #  LOGIC
    # ═══════════════════════════════════════════════════════════════════════════
    def on_show(self):
        self._refresh_accounts()

    def _refresh_accounts(self):
        try:
            accounts  = self.app.account_manager.get_all_accounts()
            active    = self.app.account_manager.get_active_account()
            active_id = getattr(active, "id", None) if active else None
        except Exception:
            accounts  = []
            active_id = None
            active    = None

        # Hero
        self._hero.content = self._build_hero(active)
        self._hero.height  = 160 if active else 0
        try:
            self._hero.update()
        except Exception:
            pass

        # Lista
        self._accounts_col.controls.clear()
        if not accounts:
            self._accounts_col.controls.append(
                ft.Container(
                    padding=ft.padding.all(24),
                    content=ft.Column([
                        ft.Icon(ft.icons.PERSON_OFF_OUTLINED,
                                color=TEXT_DIM, size=32),
                        ft.Container(height=10),
                        ft.Text("Sin cuentas guardadas",
                                color=TEXT_DIM, size=11,
                                text_align=ft.TextAlign.CENTER),
                        ft.Text("Añade una cuenta offline o Microsoft",
                                color=TEXT_DIM, size=9,
                                text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                )
            )
        else:
            # Activa primero
            ordered = sorted(accounts,
                             key=lambda a: 0 if getattr(a, "id", None) == active_id else 1)
            for acc in ordered:
                is_active = (getattr(acc, "id", None) == active_id)
                self._accounts_col.controls.append(
                    self._make_account_card(acc, is_active))

        try:
            self._accounts_col.update()
        except Exception:
            pass

    def _on_add_offline(self, e):
        username = self._offline_field.value.strip()
        if not username:
            self.app.snack("Ingresa un nombre de usuario.", error=True)
            return
        if len(username) < 3:
            self.app.snack("El nombre debe tener al menos 3 caracteres.", error=True)
            return
        try:
            from services.auth_service import AuthError
            self.app.auth_service._validate_username(username)
            from services.account_manager import Account
            acc = Account(username=username, is_microsoft=False)
            self.app.account_manager.add_account(acc)
            self._offline_field.value = ""
            # Reset preview
            self._offline_preview.content = ft.Icon(
                ft.icons.PERSON_ROUNDED, color=TEXT_DIM, size=22)
            try:
                self._offline_field.update()
                self._offline_preview.update()
            except Exception:
                pass
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
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.WARNING_AMBER_ROUNDED, color=ACCENT_RED, size=20),
                ft.Container(width=8),
                ft.Text("Eliminar cuenta", color=TEXT_PRI, size=14,
                        weight=ft.FontWeight.BOLD),
            ]),
            content=ft.Column([
                ft.Container(
                    bgcolor=ft.colors.with_opacity(0.08, ACCENT_RED),
                    border=ft.border.all(1, ft.colors.with_opacity(0.2, ACCENT_RED)),
                    border_radius=10,
                    padding=ft.padding.all(14),
                    content=ft.Text(
                        f"¿Eliminar la cuenta '{account.username}'?\nEsta acción no se puede deshacer.",
                        color=TEXT_SEC, size=11),
                ),
            ], tight=True),
            bgcolor=CARD_BG,
            shape=ft.RoundedRectangleBorder(radius=14),
            actions=[
                ft.TextButton(
                    "Cancelar",
                    style=ft.ButtonStyle(color=TEXT_SEC),
                    on_click=lambda e2: self.page.close(dlg),
                ),
                ft.ElevatedButton(
                    content=ft.Row([
                        ft.Icon(ft.icons.DELETE_ROUNDED, size=14, color=TEXT_INV),
                        ft.Container(width=6),
                        ft.Text("Eliminar", color=TEXT_INV, size=11),
                    ], tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=ACCENT_RED,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.padding.symmetric(horizontal=16, vertical=10),
                    ),
                    on_click=confirm,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg)

    # ═══════════════════════════════════════════════════════════════════════════
    #  MICROSOFT DEVICE FLOW
    # ═══════════════════════════════════════════════════════════════════════════
    def _on_ms_login(self, e):
        self._ms_status.value     = "Iniciando autenticación…"
        self._ms_code_box.visible = False
        try:
            self._ms_status.update()
            self._ms_code_box.update()
        except Exception:
            pass

        def auth():
            try:
                device = self.app.microsoft_auth.start_device_flow()
                code   = device.get("user_code", "")
                url    = device.get("verification_uri", "https://microsoft.com/link")

                def show_code():
                    self._ms_code_lbl.value   = code
                    self._ms_url_lbl.value    = url
                    self._ms_code_box.visible = True
                    self._ms_status.value     = "Esperando inicio de sesión en el navegador…"
                    try:
                        self._ms_code_lbl.update()
                        self._ms_url_lbl.update()
                        self._ms_code_box.update()
                        self._ms_status.update()
                    except Exception:
                        pass

                self.page.run_thread(show_code)
                result = self.app.microsoft_auth.poll_device_flow(device)

                if result:
                    acc = self.app.microsoft_auth.get_minecraft_account(result)
                    self.app.account_manager.add_account(acc)

                    def done():
                        self._ms_status.value     = "✓ Cuenta Microsoft añadida correctamente"
                        self._ms_code_box.visible = False
                        try:
                            self._ms_status.update()
                            self._ms_code_box.update()
                        except Exception:
                            pass
                        self._refresh_accounts()
                        self.app.refresh_account_panel()
                        self.app.snack(f"¡Bienvenido, {acc.username}! 🎮")

                    self.page.run_thread(done)
                else:
                    def failed():
                        self._ms_status.value     = "Autenticación cancelada o expirada."
                        self._ms_code_box.visible = False
                        try:
                            self._ms_status.update()
                            self._ms_code_box.update()
                        except Exception:
                            pass
                    self.page.run_thread(failed)

            except Exception as err:
                def show_err():
                    self._ms_status.value     = f"Error: {err}"
                    self._ms_code_box.visible = False
                    try:
                        self._ms_status.update()
                        self._ms_code_box.update()
                    except Exception:
                        pass
                self.page.run_thread(show_err)

        threading.Thread(target=auth, daemon=True).start()