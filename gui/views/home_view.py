"""
gui/views/home_view.py — Home estilo Modrinth con mods populares en tiempo real
"""
import json
import threading
import urllib.request

import flet as ft

# ── Colores del tema (ajusta si ya los tienes en gui/theme.py) ──────────────
try:
    from gui.theme import BG, TEXT_SEC, TEXT_DIM
    CARD  = getattr(__import__("gui.theme", fromlist=["CARD"]),  "CARD",  "#16213e")
    HOVER = getattr(__import__("gui.theme", fromlist=["HOVER"]), "HOVER", "#0f3460")
    PRIMARY = getattr(__import__("gui.theme", fromlist=["PRIMARY"]), "PRIMARY", "#e94560")
except ImportError:
    BG      = "#1a1a2e"
    CARD    = "#16213e"
    HOVER   = "#0f3460"
    PRIMARY = "#e94560"
    TEXT_SEC = "#c9d1d9"
    TEXT_DIM = "#6e7681"

# ── Modrinth API ─────────────────────────────────────────────────────────────
_SEARCH_URL = (
    "https://api.modrinth.com/v2/search"
    "?limit=6&index=downloads"
    '&facets=[["project_type:mod"]]'
)
_HEADERS = {"User-Agent": "PyLauncher/1.0 (contact@pylauncher.dev)"}


def _fmt_num(n: int) -> str:
    """139400000 → '139.4M', 34700 → '34.7K'"""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


# ─────────────────────────────────────────────────────────────────────────────
class HomeView:
    def __init__(self, page: ft.Page, app):
        self.page = page
        self.app  = app
        self._loaded = False

        # ── Skeleton / estado de carga ────────────────────────────────────
        self._status_text = ft.Text(
            "Cargando mods populares…",
            color=TEXT_DIM,
            size=12,
            italic=True,
        )

        # ── Fila de tarjetas (scroll horizontal) ─────────────────────────
        self._cards_row = ft.Row(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            spacing=16,
        )

        # ── Layout principal ──────────────────────────────────────────────
        self.root = ft.Container(
            expand=True,
            bgcolor=BG,
            padding=ft.padding.all(28),
            content=ft.Column(
                controls=[
                    self._build_header(),
                    ft.Divider(height=1, color="#2a2a4a", thickness=1),
                    ft.Row(
                        [
                            ft.Text(
                                "Mods populares",
                                color=TEXT_SEC,
                                size=16,
                                weight=ft.FontWeight.W_600,
                            ),
                            self._status_text,
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    # Contenedor con altura fija para la fila de tarjetas
                    ft.Container(
                        content=self._cards_row,
                        height=340,
                    ),
                ],
                spacing=14,
                expand=True,
            ),
        )

    # ── Header ───────────────────────────────────────────────────────────────
    def _build_header(self) -> ft.Control:
        return ft.Column(
            [
                ft.Text(
                    "¡Bienvenido a PyLauncher!",
                    size=30,
                    weight=ft.FontWeight.BOLD,
                    color=TEXT_SEC,
                ),
                ft.Row(
                    [
                        ft.TextButton(
                            content=ft.Row(
                                [
                                    ft.Text(
                                        "Descubrir mods",
                                        color=PRIMARY,
                                        size=13,
                                        weight=ft.FontWeight.W_600,
                                    ),
                                    ft.Icon(
                                        ft.icons.CHEVRON_RIGHT,
                                        color=PRIMARY,
                                        size=18,
                                    ),
                                ],
                                spacing=2,
                            ),
                            on_click=self._go_to_mods,
                            style=ft.ButtonStyle(
                                padding=ft.padding.all(0),
                                overlay_color=ft.colors.TRANSPARENT,
                            ),
                        )
                    ]
                ),
            ],
            spacing=0,
        )

    # ── Navegación ───────────────────────────────────────────────────────────
    def _go_to_mods(self, _e):
        """Navega a la vista de mods. Ajusta el nombre si tu app usa otro."""
        try:
            self.app.navigate("mods")
        except Exception:
            pass  # Si el método se llama diferente, no rompe la UI

    # ── Ciclo de vida ─────────────────────────────────────────────────────────
    def on_show(self):
        if not self._loaded:
            self._loaded = True
            threading.Thread(target=self._fetch_mods, daemon=True).start()

    # ── Fetch Modrinth ────────────────────────────────────────────────────────
    def _fetch_mods(self):
        try:
            req = urllib.request.Request(_SEARCH_URL, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            hits = data.get("hits", [])
            cards = [self._build_card(h) for h in hits[:6]]
            self._cards_row.controls = cards
            self._status_text.visible = False
        except Exception as exc:
            self._status_text.value = f"Sin conexión — {exc}"
            self._status_text.color = "#e94560"
        finally:
            self.page.update()

    # ── Tarjeta de mod ────────────────────────────────────────────────────────
    def _build_card(self, mod: dict) -> ft.Container:
        icon_url   = mod.get("icon_url") or ""
        gallery    = mod.get("gallery") or []
        banner_url = gallery[0] if gallery else ""
        title      = mod.get("title", "Mod")
        raw_desc   = mod.get("description", "")
        desc       = (raw_desc[:92] + "…") if len(raw_desc) > 92 else raw_desc
        downloads  = _fmt_num(mod.get("downloads", 0))
        follows    = _fmt_num(mod.get("follows", 0))
        cats       = mod.get("display_categories") or mod.get("categories") or []
        cat_label  = cats[0].capitalize() if cats else ""

        # ── Banner (imagen o placeholder) ────────────────────────────────
        if banner_url:
            banner: ft.Control = ft.Image(
                src=banner_url,
                width=260,
                height=130,
                fit=ft.ImageFit.COVER,
                border_radius=ft.border_radius.only(
                    top_left=10, top_right=10
                ),
                error_content=self._banner_placeholder(),
            )
        else:
            banner = self._banner_placeholder()

        # ── Ícono del mod ────────────────────────────────────────────────
        if icon_url:
            icon: ft.Control = ft.Image(
                src=icon_url,
                width=40,
                height=40,
                border_radius=ft.border_radius.all(8),
                fit=ft.ImageFit.COVER,
                error_content=self._icon_placeholder(),
            )
        else:
            icon = self._icon_placeholder()

        # ── Fila de estadísticas ─────────────────────────────────────────
        stats_controls = [
            ft.Icon(ft.icons.DOWNLOAD_OUTLINED, size=13, color=TEXT_DIM),
            ft.Text(downloads, size=11, color=TEXT_DIM),
            ft.Icon(ft.icons.FAVORITE_BORDER, size=13, color=TEXT_DIM),
            ft.Text(follows, size=11, color=TEXT_DIM),
        ]
        if cat_label:
            stats_controls += [
                ft.Icon(ft.icons.LABEL_OUTLINE, size=13, color=TEXT_DIM),
                ft.Container(
                    content=ft.Text(cat_label, size=10, color=TEXT_DIM),
                    padding=ft.padding.symmetric(horizontal=7, vertical=3),
                    bgcolor="#252545",
                    border_radius=10,
                ),
            ]
        stats_row = ft.Row(stats_controls, spacing=5, wrap=False)

        # ── Cuerpo de la tarjeta ─────────────────────────────────────────
        body = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            icon,
                            ft.Text(
                                title,
                                size=14,
                                weight=ft.FontWeight.BOLD,
                                color=TEXT_SEC,
                                expand=True,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                max_lines=1,
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        desc,
                        size=11,
                        color=TEXT_DIM,
                        max_lines=3,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    stats_row,
                ],
                spacing=7,
                expand=True,
            ),
            padding=ft.padding.all(11),
            expand=True,
        )

        # ── Tarjeta completa ─────────────────────────────────────────────
        return ft.Container(
            width=260,
            bgcolor=CARD,
            border_radius=10,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            border=ft.border.all(1, "#2a2a4a"),
            content=ft.Column(
                [banner, body],
                spacing=0,
                expand=True,
            ),
            on_hover=self._card_hover,
        )

    # ── Helpers visuales ──────────────────────────────────────────────────────
    @staticmethod
    def _banner_placeholder() -> ft.Container:
        return ft.Container(
            width=260,
            height=130,
            bgcolor=HOVER,
            border_radius=ft.border_radius.only(top_left=10, top_right=10),
            content=ft.Icon(ft.icons.EXTENSION, color=TEXT_DIM, size=38),
            alignment=ft.alignment.center,
        )

    @staticmethod
    def _icon_placeholder() -> ft.Container:
        return ft.Container(
            width=40,
            height=40,
            bgcolor=HOVER,
            border_radius=ft.border_radius.all(8),
            content=ft.Icon(ft.icons.EXTENSION, color=TEXT_DIM, size=20),
            alignment=ft.alignment.center,
        )

    @staticmethod
    def _card_hover(e: ft.HoverEvent):
        e.control.border = ft.border.all(
            1, PRIMARY if e.data == "true" else "#2a2a4a"
        )
        e.control.update()