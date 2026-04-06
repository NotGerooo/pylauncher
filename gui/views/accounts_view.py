"""
gui/views/accounts_view.py — Gestión de cuentas
Cuentas offline y autenticación Microsoft OAuth.
Skin 3D CSS · Glow sutil · Gestión de skins offline · Device Flow UI
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
    if uuid and uuid != "offline":
        return f"https://crafatar.com/avatars/{uuid}?size={size}&overlay=true"
    return f"https://minotar.net/avatar/{username}/{size}"

def _body_url(username: str, uuid: str | None = None, size: int = 256) -> str:
    if uuid and uuid != "offline":
        return f"https://crafatar.com/renders/body/{uuid}?size={size}&overlay=true"
    return f"https://minotar.net/body/{username}/{size}"


def _skin_3d_html(username: str, uuid: str | None = None,
                  width: int = 160, height: int = 220,
                  glow: str = "#4ade80") -> str:
    """HTML con skinview3d (CDN). Walk + auto-rotación + sombra de suelo."""
    skin_url = (
        f"https://crafatar.com/skins/{uuid}"
        if uuid and uuid != "offline"
        else f"https://minotar.net/skin/{username}"
    )
    cape_js = (
        f'viewer.loadCape("https://crafatar.com/capes/{uuid}");'
        if uuid and uuid != "offline"
        else ""
    )
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{
    width:{width}px; height:{height}px;
    background:transparent;
    overflow:hidden;
    display:flex; align-items:center; justify-content:center;
  }}
  canvas {{
    display:block;
    filter: drop-shadow(0 0 8px {glow}66);
    animation: floatY 3.2s ease-in-out infinite;
  }}
  @keyframes floatY {{
    0%,100% {{ transform:translateY(0px); }}
    50%      {{ transform:translateY(-7px); }}
  }}
  #shadow {{
    position:absolute;
    bottom:8px; left:50%;
    transform:translateX(-50%);
    width:50px; height:8px;
    border-radius:50%;
    background:radial-gradient(ellipse, {glow}44 0%, transparent 70%);
    animation: shadowPulse 3.2s ease-in-out infinite;
  }}
  @keyframes shadowPulse {{
    0%,100% {{ opacity:0.7; transform:translateX(-50%) scaleX(1); }}
    50%      {{ opacity:0.3; transform:translateX(-50%) scaleX(0.7); }}
  }}
</style>
</head>
<body>
<canvas id="c"></canvas>
<div id="shadow"></div>
<script src="https://cdn.jsdelivr.net/npm/skinview3d@2.2.1/bundles/skinview3d.min.js"></script>
<script>
(function() {{
  try {{
    var v = new skinview3d.SkinViewer({{
      canvas: document.getElementById("c"),
      width:  {width},
      height: {height},
      skin:   "{skin_url}",
    }});
    {cape_js}
    v.fov = 50;
    v.zoom = 0.9;
    v.autoRotate = true;
    v.autoRotateSpeed = 0.8;
    v.animation = new skinview3d.WalkingAnimation();
    v.animation.speed = 0.65;
    v.renderer.setClearColor(0x000000, 0);
  }} catch(err) {{
    document.body.style.color = "{glow}";
    document.body.style.font = "bold 12px monospace";
    document.body.style.textAlign = "center";
    document.body.style.paddingTop = "80px";
    document.body.innerText = "Skin no disponible";
  }}
}})();
</script>
</body>
</html>"""


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
        self._skin_picker: ft.FilePicker | None = None
        self._pending_skin_account_id: str | None = None
        self._build()

    # ═══════════════════════════════════════════════════════════════════════════
    #  BUILD
    # ═══════════════════════════════════════════════════════════════════════════
    def _build(self):
        # FilePicker para skins offline
        self._skin_picker = ft.FilePicker(on_result=self._on_skin_picked)
        self.page.overlay.append(self._skin_picker)
        self.page.update()

        self._hero = ft.Container(
            height=0,
            animate=ft.animation.Animation(500, ft.AnimationCurve.EASE_OUT),
        )

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

        left = ft.Column([
            self._build_offline_card(),
            ft.Container(height=14),
            self._build_ms_card(),
        ], spacing=0)

        self.root = ft.Container(
            expand=True, bgcolor=BG,
            padding=ft.padding.all(32),
            content=ft.Column([
                ft.Row([
                    ft.Column([
                        ft.Text("Cuentas", color=TEXT_PRI, size=28,
                                weight=ft.FontWeight.BOLD),
                        ft.Text("Gestiona identidades del launcher",
                                color=TEXT_DIM, size=11),
                    ], spacing=2, expand=True),
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
            animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT),
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
                self._offline_preview.border = ft.border.all(
                    2, ft.colors.with_opacity(0.55, OFFLINE_COLOR))
                self._offline_preview.shadow = [ft.BoxShadow(
                    spread_radius=0, blur_radius=12,
                    color=ft.colors.with_opacity(0.35, OFFLINE_COLOR),
                    offset=ft.Offset(0, 0),
                )]
            else:
                self._offline_preview.content = ft.Icon(
                    ft.icons.PERSON_ROUNDED, color=TEXT_DIM, size=22)
                self._offline_preview.border = ft.border.all(1, BORDER)
                self._offline_preview.shadow = []
            try:
                self._offline_preview.update()
            except Exception:
                pass

        self._offline_field.on_change = _preview_update

        add_btn = ft.ElevatedButton(
            "Añadir cuenta",
            icon=ft.icons.ADD_ROUNDED,
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
            shadow=[
                ft.BoxShadow(spread_radius=0, blur_radius=20,
                             color=ft.colors.with_opacity(0.08, OFFLINE_COLOR),
                             offset=ft.Offset(0, 4)),
            ],
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        width=36, height=36, border_radius=10,
                        bgcolor=OFFLINE_BG,
                        border=ft.border.all(1, ft.colors.with_opacity(0.35, OFFLINE_COLOR)),
                        alignment=ft.alignment.center,
                        content=ft.Icon(ft.icons.PERSON_ROUNDED,
                                        color=OFFLINE_COLOR, size=18),
                    ),
                    ft.Container(width=12),
                    ft.Column([
                        ft.Text("Cuenta Offline", color=TEXT_PRI, size=13,
                                weight=ft.FontWeight.BOLD),
                        ft.Text("Sin autenticación Mojang", color=TEXT_DIM, size=9),
                    ], spacing=2, expand=True),
                    self._small_badge("OFFLINE", OFFLINE_COLOR,
                                      ft.colors.with_opacity(0.14, OFFLINE_COLOR)),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=18, color=BORDER),
                ft.Row([
                    self._offline_preview,
                    ft.Container(width=12),
                    self._offline_field,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=12),
                ft.Row([ft.Container(expand=True), add_btn]),
            ], spacing=0),
        )

    # ═══════════════════════════════════════════════════════════════════════════
    #  MICROSOFT CARD
    # ═══════════════════════════════════════════════════════════════════════════
    def _build_ms_card(self) -> ft.Container:
        self._ms_status   = ft.Text("Autenticación vía Device Code Flow",
                                     color=TEXT_DIM, size=9)
        self._ms_code_lbl = ft.Text("", color=MS_BLUE, size=26,
                                     weight=ft.FontWeight.BOLD,
                                     selectable=True,
                                     font_family="Courier New")
        self._ms_url_lbl  = ft.Text("", color=TEXT_SEC, size=9, selectable=True)

        self._ms_code_box = ft.Container(
            visible=False,
            bgcolor=MS_BG,
            border=ft.border.all(1, MS_BORDER),
            border_radius=12,
            padding=ft.padding.all(18),
            shadow=[
                ft.BoxShadow(spread_radius=0, blur_radius=20,
                             color=ft.colors.with_opacity(0.22, MS_BLUE),
                             offset=ft.Offset(0, 4)),
            ],
            animate_opacity=ft.animation.Animation(350, ft.AnimationCurve.EASE_OUT),
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        width=8, height=8, border_radius=4,
                        bgcolor=MS_BLUE,
                        shadow=[ft.BoxShadow(spread_radius=0, blur_radius=8,
                                             color=ft.colors.with_opacity(0.8, MS_BLUE),
                                             offset=ft.Offset(0, 0))],
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
                ft.ProgressBar(
                    value=None,
                    bgcolor=ft.colors.with_opacity(0.1, MS_BLUE),
                    color=MS_BLUE,
                    height=2,
                    border_radius=1,
                ),
            ], spacing=0),
        )

        ms_btn = ft.ElevatedButton(
            content=ft.Row([
                self._ms_logo_icon(),
                ft.Container(width=10),
                ft.Text("Iniciar sesión con Microsoft",
                        color=MS_BLUE, size=11, weight=ft.FontWeight.W_600),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
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
            shadow=[
                ft.BoxShadow(spread_radius=0, blur_radius=20,
                             color=ft.colors.with_opacity(0.10, MS_BLUE),
                             offset=ft.Offset(0, 4)),
            ],
            content=ft.Column([
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
                        ft.Text("Microsoft / Xbox", color=TEXT_PRI, size=13,
                                weight=ft.FontWeight.BOLD),
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
    #  HERO — cuenta activa con skin 3D (WebView skinview3d)
    # ═══════════════════════════════════════════════════════════════════════════
    def _build_hero(self, acc) -> ft.Container:
        if not acc:
            return ft.Container(height=0)

        name     = acc.username
        uuid     = getattr(acc, "uuid", None) or getattr(acc, "id", None)
        is_ms    = getattr(acc, "is_microsoft", False)
        col      = AVATAR_PALETTE[abs(hash(name)) % len(AVATAR_PALETTE)]
        initials = (name[:2]).upper()
        glow_col = GREEN if is_ms else OFFLINE_COLOR

        # ── Skin 3D via WebView (skinview3d CDN) ────────────────────────────
        skin_html = _skin_3d_html(name, uuid, 150, 210, glow_col)
        skin_3d = ft.WebView(
            url=f"data:text/html;charset=utf-8,{skin_html}",
            width=150, height=210,
            expand=False,
        )

        # Fallback: imagen body 2D por si WebView no carga
        skin_fallback = ft.Image(
            src=_body_url(name, uuid, 256),
            width=120, height=200,
            fit=ft.ImageFit.CONTAIN,
            error_content=ft.Container(
                width=70, height=140,
                bgcolor=col, border_radius=12,
                alignment=ft.alignment.center,
                content=ft.Text(initials, color=TEXT_INV, size=22,
                                weight=ft.FontWeight.BOLD),
            ),
        )

        label_txt = "Microsoft" if is_ms else "Offline"
        label_col = MS_BLUE if is_ms else OFFLINE_COLOR
        label_bg  = ft.colors.with_opacity(0.14, label_col)

        return ft.Container(
            height=210,
            border_radius=20,
            border=ft.border.all(1, ft.colors.with_opacity(0.25, glow_col)),
            # Glow exterior muy sutil — no tapa texto
            shadow=[
                ft.BoxShadow(spread_radius=0, blur_radius=20,
                             color=ft.colors.with_opacity(0.12, glow_col),
                             offset=ft.Offset(0, 6)),
            ],
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            # Gradiente suave de fondo
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left,
                end=ft.alignment.bottom_right,
                colors=[
                    ft.colors.with_opacity(0.14, glow_col),
                    CARD_BG,
                    ft.colors.with_opacity(0.05, glow_col),
                ],
            ),
            content=ft.Row([
                # ── Skin 3D ─────────────────────────────────────────────────
                ft.Container(
                    width=160, height=210,
                    alignment=ft.alignment.center,
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    content=ft.Stack([
                        ft.Container(
                            width=160, height=210,
                            gradient=ft.RadialGradient(
                                center=ft.alignment.bottom_center,
                                radius=1.0,
                                colors=[
                                    ft.colors.with_opacity(0.20, glow_col),
                                    ft.colors.with_opacity(0.0, glow_col),
                                ],
                            ),
                        ),
                        ft.Container(
                            width=160, height=210,
                            alignment=ft.alignment.center,
                            content=skin_3d,
                        ),
                    ]),
                ),

                # ── Info ────────────────────────────────────────────────────
                ft.Column([
                    ft.Container(height=16),
                    ft.Row([
                        ft.Container(
                            width=7, height=7, border_radius=4,
                            bgcolor=glow_col,
                        ),
                        ft.Container(width=8),
                        ft.Text("JUGANDO COMO", color=TEXT_DIM, size=8,
                                weight=ft.FontWeight.BOLD),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(height=8),
                    # Nombre con fondo sólido para legibilidad total
                    ft.Container(
                        content=ft.Text(name, color=TEXT_PRI, size=22,
                                        weight=ft.FontWeight.BOLD),
                        bgcolor=ft.colors.with_opacity(0.0, CARD_BG),
                    ),
                    ft.Container(height=10),
                    ft.Row([
                        self._small_badge(label_txt.upper(), label_col, label_bg),
                        ft.Container(width=6),
                        self._small_badge("ACTIVA", GREEN,
                                          ft.colors.with_opacity(0.14, GREEN)),
                    ]),
                    ft.Container(height=12),
                    ft.Container(
                        bgcolor=ft.colors.with_opacity(0.08, CARD_BG),
                        border=ft.border.all(1, ft.colors.with_opacity(0.18, TEXT_DIM)),
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=10, vertical=5),
                        content=ft.Text(
                            f"UUID: {str(uuid)[:16]}…" if uuid else "Sin UUID — Modo Offline",
                            color=TEXT_SEC, size=8,
                            font_family="Courier New",
                        ),
                    ),
                ], spacing=0, expand=True,
                   alignment=ft.MainAxisAlignment.CENTER),

                # ── Head grande ──────────────────────────────────────────────
                ft.Container(
                    padding=ft.padding.only(right=28, top=20, bottom=20),
                    content=ft.Column([
                        ft.Container(
                            width=80, height=80, border_radius=14,
                            clip_behavior=ft.ClipBehavior.HARD_EDGE,
                            border=ft.border.all(
                                2, ft.colors.with_opacity(0.5, glow_col)),
                            shadow=[
                                ft.BoxShadow(spread_radius=0, blur_radius=14,
                                             color=ft.colors.with_opacity(0.35, glow_col),
                                             offset=ft.Offset(0, 0)),
                            ],
                            content=ft.Image(
                                src=_head_url(name, uuid, 160),
                                width=80, height=80,
                                fit=ft.ImageFit.COVER,
                                error_content=ft.Container(
                                    bgcolor=col,
                                    alignment=ft.alignment.center,
                                    content=ft.Text(initials, color=TEXT_INV,
                                                    size=18, weight=ft.FontWeight.BOLD),
                                ),
                            ),
                        ),
                        ft.Container(height=8),
                        ft.Row([
                            ft.Container(
                                width=6, height=6, border_radius=3,
                                bgcolor=GREEN,
                            ),
                            ft.Container(width=5),
                            ft.Text("En línea", color=GREEN, size=9,
                                    weight=ft.FontWeight.W_600),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER,
                           alignment=ft.MainAxisAlignment.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                       alignment=ft.MainAxisAlignment.CENTER,
                       expand=True),
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    # ═══════════════════════════════════════════════════════════════════════════
    #  ACCOUNT CARD — skin body + botón de skin para offline
    # ═══════════════════════════════════════════════════════════════════════════
    def _make_account_card(self, acc, is_active: bool) -> ft.Container:
        name     = acc.username
        uuid     = getattr(acc, "uuid", None) or getattr(acc, "id", None)
        is_ms    = getattr(acc, "is_microsoft", False)
        col      = AVATAR_PALETTE[abs(hash(name)) % len(AVATAR_PALETTE)]
        initials = (name[:2]).upper()
        skin_path = getattr(acc, "skin_path", None)

        glow_col  = GREEN if is_active else TEXT_DIM
        label_col = MS_BLUE if is_ms else OFFLINE_COLOR
        label_bg  = ft.colors.with_opacity(0.12, label_col)
        label_txt = "Microsoft" if is_ms else "Offline"

        # ── Panel izquierdo: skin body ───────────────────────────────────────
        skin_panel = ft.Container(
            width=70,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            border_radius=ft.border_radius.only(top_left=14, bottom_left=14),
            bgcolor=ft.colors.with_opacity(
                0.10 if is_active else 0.04, glow_col),
            content=ft.Stack([
                ft.Container(
                    width=70, height=110,
                    gradient=ft.RadialGradient(
                        center=ft.alignment.bottom_center,
                        radius=1.0,
                        colors=[
                            ft.colors.with_opacity(
                                0.35 if is_active else 0.12, glow_col),
                            ft.colors.with_opacity(0.0, glow_col),
                        ],
                    ),
                ),
                ft.Container(
                    width=70, height=104,
                    alignment=ft.alignment.center,
                    content=ft.Image(
                        src=_body_url(name, uuid, 128),
                        width=52, height=88,
                        fit=ft.ImageFit.CONTAIN,
                        error_content=ft.Container(
                            bgcolor=col, border_radius=8,
                            alignment=ft.alignment.center,
                            width=42, height=70,
                            content=ft.Text(initials, color=TEXT_INV,
                                            size=11, weight=ft.FontWeight.BOLD),
                        ),
                    ),
                ),
            ]),
        )

        # Head
        head = ft.Container(
            width=40, height=40, border_radius=9,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            border=ft.border.all(
                2, ft.colors.with_opacity(0.70, GREEN) if is_active else BORDER),
            shadow=[ft.BoxShadow(
                spread_radius=0, blur_radius=8,
                color=ft.colors.with_opacity(
                    0.40 if is_active else 0.10,
                    GREEN if is_active else col),
                offset=ft.Offset(0, 2),
            )],
            content=ft.Image(
                src=_head_url(name, uuid, 80),
                width=40, height=40, fit=ft.ImageFit.COVER,
                error_content=ft.Container(
                    bgcolor=col, alignment=ft.alignment.center,
                    content=ft.Text(initials, color=TEXT_INV,
                                    size=10, weight=ft.FontWeight.BOLD),
                ),
            ),
        )

        dot_col = GREEN if is_active else TEXT_DIM
        status_dot = ft.Container(
            width=7, height=7, border_radius=4, bgcolor=dot_col,
            shadow=[ft.BoxShadow(
                spread_radius=0, blur_radius=6,
                color=ft.colors.with_opacity(0.8 if is_active else 0.0, dot_col),
                offset=ft.Offset(0, 0),
            )],
        )

        # ── Acciones ─────────────────────────────────────────────────────────
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
                border=ft.border.all(1, ft.colors.with_opacity(0.30, GREEN)),
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                on_click=lambda e, a=acc: self._set_active(a),
                animate=ft.animation.Animation(150, ft.AnimationCurve.EASE_OUT),
            )
            act_btn.on_hover = lambda e, c=act_btn: (
                setattr(c, "bgcolor", ft.colors.with_opacity(
                    0.18 if e.data == "true" else 0.08, GREEN)) or c.update()
            )
            actions.append(act_btn)

        # Botón skin (solo para cuentas offline)
        if not is_ms:
            skin_icon = ft.icons.IMAGE_ROUNDED if not skin_path else ft.icons.CHECK_CIRCLE_OUTLINE_ROUNDED
            skin_color = OFFLINE_COLOR if not skin_path else GREEN
            skin_btn = ft.Container(
                width=30, height=30, border_radius=8,
                bgcolor="transparent",
                border=ft.border.all(1, BORDER),
                alignment=ft.alignment.center,
                tooltip="Cambiar skin" if not skin_path else "Cambiar/quitar skin",
                content=ft.Icon(skin_icon, size=14, color=skin_color),
                on_click=lambda e, a=acc: self._open_skin_menu(a),
                animate=ft.animation.Animation(150, ft.AnimationCurve.EASE_OUT),
            )
            skin_btn.on_hover = lambda e, c=skin_btn: (
                setattr(c, "bgcolor",
                        ft.colors.with_opacity(0.10, OFFLINE_COLOR) if e.data == "true"
                        else "transparent") or c.update()
            )
            actions.append(skin_btn)

        del_btn = ft.Container(
            width=30, height=30, border_radius=8,
            bgcolor="transparent",
            border=ft.border.all(1, BORDER),
            alignment=ft.alignment.center,
            content=ft.Icon(ft.icons.DELETE_OUTLINE_ROUNDED, size=14, color=TEXT_DIM),
            on_click=lambda e, a=acc: self._delete_account(a),
            animate=ft.animation.Animation(150, ft.AnimationCurve.EASE_OUT),
        )
        del_btn.on_hover = lambda e, c=del_btn: (
            setattr(c, "bgcolor",
                    ft.colors.with_opacity(0.14, ACCENT_RED) if e.data == "true"
                    else "transparent") or
            setattr(c.content, "color",
                    ACCENT_RED if e.data == "true" else TEXT_DIM) or
            c.update()
        )
        actions.append(del_btn)

        # ── Card completa ─────────────────────────────────────────────────────
        card = ft.Container(
            bgcolor=(ft.colors.with_opacity(0.07, GREEN) if is_active else INPUT_BG),
            border=ft.border.all(
                1, ft.colors.with_opacity(0.45, GREEN) if is_active else BORDER),
            border_radius=14,
            padding=ft.padding.only(top=0, bottom=0, left=0, right=16),
            shadow=[ft.BoxShadow(
                spread_radius=0, blur_radius=16,
                color=ft.colors.with_opacity(0.15 if is_active else 0.0, GREEN),
                offset=ft.Offset(0, 3),
            )],
            animate=ft.animation.Animation(220, ft.AnimationCurve.EASE_OUT),
            content=ft.Row([
                skin_panel,
                ft.Container(width=12),
                ft.Column([
                    ft.Container(height=10),
                    ft.Row([
                        head,
                        ft.Container(width=10),
                        ft.Column([
                            ft.Row([
                                status_dot,
                                ft.Container(width=6),
                                ft.Text(name, color=TEXT_PRI, size=12,
                                        weight=ft.FontWeight.BOLD),
                            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            ft.Container(height=4),
                            ft.Row([
                                self._small_badge(label_txt, label_col, label_bg),
                                *(
                                    [ft.Container(width=4),
                                     self._small_badge("ACTIVA", GREEN,
                                                      ft.colors.with_opacity(0.14, GREEN))]
                                    if is_active else []
                                ),
                                *(
                                    [ft.Container(width=4),
                                     self._small_badge("SKIN", OFFLINE_COLOR,
                                                      ft.colors.with_opacity(0.10, OFFLINE_COLOR))]
                                    if (not is_ms and skin_path) else []
                                ),
                            ]),
                            ft.Container(height=4),
                            ft.Text(
                                f"UUID: {str(uuid)[:12]}…" if uuid else "Modo Offline",
                                color=TEXT_DIM, size=8,
                                font_family="Courier New",
                            ),
                        ], spacing=0, expand=True),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(height=10),
                ], spacing=0, expand=True),
                ft.Row(actions, spacing=8,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        def _hover(e, c=card, active=is_active):
            if active:
                return
            c.bgcolor = (INPUT_BG if e.data != "true"
                         else ft.colors.with_opacity(0.05, TEXT_PRI))
            c.border  = ft.border.all(
                1, BORDER if e.data != "true"
                else ft.colors.with_opacity(0.35, TEXT_DIM))
            try:
                c.update()
            except Exception:
                pass

        card.on_hover = _hover
        return card

    # ═══════════════════════════════════════════════════════════════════════════
    #  SKIN MANAGEMENT (offline)
    # ═══════════════════════════════════════════════════════════════════════════
    def _open_skin_menu(self, acc):
        """Muestra un diálogo para subir o quitar skin a una cuenta offline."""
        skin_path = getattr(acc, "skin_path", None)

        def _pick(e):
            self.page.close(dlg)
            self._pending_skin_account_id = acc.id
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

        actions = [
            ft.ElevatedButton(
                content=ft.Row([
                    ft.Icon(ft.icons.UPLOAD_ROUNDED, size=14, color=TEXT_INV),
                    ft.Container(width=6),
                    ft.Text("Subir skin (.png)", color=TEXT_INV, size=11),
                ], tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=OFFLINE_COLOR,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.padding.symmetric(horizontal=16, vertical=10),
                ),
                on_click=_pick,
            ),
        ]
        if skin_path:
            actions.insert(0, ft.TextButton(
                "Quitar skin",
                style=ft.ButtonStyle(color=ACCENT_RED),
                on_click=_remove,
            ))
        actions.append(ft.TextButton(
            "Cancelar",
            style=ft.ButtonStyle(color=TEXT_SEC),
            on_click=lambda e: self.page.close(dlg),
        ))

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.IMAGE_ROUNDED, color=OFFLINE_COLOR, size=18),
                ft.Container(width=8),
                ft.Text(f"Skin de {acc.username}", color=TEXT_PRI, size=13,
                        weight=ft.FontWeight.BOLD),
            ]),
            content=ft.Column([
                ft.Container(
                    bgcolor=ft.colors.with_opacity(0.06, OFFLINE_COLOR),
                    border=ft.border.all(1, ft.colors.with_opacity(0.18, OFFLINE_COLOR)),
                    border_radius=10,
                    padding=ft.padding.all(12),
                    content=ft.Text(
                        f"Skin actual: {skin_path.split('/')[-1] if skin_path else 'Ninguna (Mojang default)'}\n"
                        "Las skins deben ser PNG de 64×64 o 64×32 píxeles.",
                        color=TEXT_SEC, size=10,
                    ),
                ),
            ], tight=True),
            bgcolor=CARD_BG,
            shape=ft.RoundedRectangleBorder(radius=14),
            actions=actions,
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg)

    def _on_skin_picked(self, e: ft.FilePickerResultEvent):
        if not e.files or not self._pending_skin_account_id:
            self._pending_skin_account_id = None
            return
        skin_path = e.files[0].path
        acc_id    = self._pending_skin_account_id
        self._pending_skin_account_id = None
        try:
            self.app.account_manager.update_skin(acc_id, skin_path)
            self._refresh_accounts()
            self.app.snack("Skin actualizada correctamente.")
        except Exception as err:
            self.app.snack(str(err), error=True)

    # ═══════════════════════════════════════════════════════════════════════════
    #  HELPERS UI
    # ═══════════════════════════════════════════════════════════════════════════
    @staticmethod
    def _small_badge(text: str, color: str, bg) -> ft.Container:
        return ft.Container(
            content=ft.Text(text, size=8, color=color,
                            weight=ft.FontWeight.W_700),
            padding=ft.padding.symmetric(horizontal=8, vertical=3),
            bgcolor=bg, border_radius=6,
            border=ft.border.all(1, ft.colors.with_opacity(0.25, color)),
        )

    @staticmethod
    def _mc_logo_badge() -> ft.Container:
        green = "#4caf50"
        black = "#000000"
        size  = 6
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
        colors_map = {1: green, 3: black, 0: "transparent"}
        rows = [
            ft.Row([ft.Container(width=size, height=size,
                                 bgcolor=colors_map.get(c, "transparent"))
                    for c in row], spacing=0)
            for row in pattern
        ]
        return ft.Container(
            bgcolor=CARD2_BG,
            border=ft.border.all(1, BORDER),
            border_radius=10,
            padding=ft.padding.all(8),
            shadow=[ft.BoxShadow(spread_radius=0, blur_radius=12,
                                 color=ft.colors.with_opacity(0.20, green),
                                 offset=ft.Offset(0, 2))],
            content=ft.Column(rows, spacing=0),
        )

    @staticmethod
    def _ms_logo_icon(size: int = 14) -> ft.Stack:
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

        self._hero.content = self._build_hero(active)
        self._hero.height  = 220 if active else 0
        try:
            self._hero.update()
        except Exception:
            pass

        self._accounts_col.controls.clear()
        if not accounts:
            self._accounts_col.controls.append(
                ft.Container(
                    padding=ft.padding.all(28),
                    content=ft.Column([
                        ft.Icon(ft.icons.PERSON_OFF_OUTLINED, color=TEXT_DIM, size=36),
                        ft.Container(height=12),
                        ft.Text("Sin cuentas guardadas", color=TEXT_DIM, size=11,
                                text_align=ft.TextAlign.CENTER),
                        ft.Text("Añade una cuenta offline o Microsoft",
                                color=TEXT_DIM, size=9,
                                text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                )
            )
        else:
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
        try:
            acc = self.app.account_manager.add_offline_account(username)
            self._offline_field.value = ""
            self._offline_preview.content = ft.Icon(
                ft.icons.PERSON_ROUNDED, color=TEXT_DIM, size=22)
            self._offline_preview.border = ft.border.all(1, BORDER)
            self._offline_preview.shadow = []
            try:
                self._offline_field.update()
                self._offline_preview.update()
            except Exception:
                pass
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
                        f"¿Eliminar la cuenta '{account.username}'?\n"
                        "Esta acción no se puede deshacer.",
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