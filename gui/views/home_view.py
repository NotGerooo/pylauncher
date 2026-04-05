"""
gui/views/home_view.py — Home estilo Modrinth: mods + modpacks populares
"""
import json
import threading
import urllib.request
import urllib.parse
import base64

import flet as ft
from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER, BORDER_BRIGHT,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM,
)

_HEADERS = {"User-Agent": "PyLauncher/1.0"}

_URL_MODS = (
    "https://api.modrinth.com/v2/search"
    "?limit=20&index=downloads"
    '&facets=[[%22project_type:mod%22]]'
)
_URL_MODPACKS = (
    "https://api.modrinth.com/v2/search"
    "?limit=20&index=downloads"
    '&facets=[[%22project_type:modpack%22]]'
)

# Paletas de color para placeholders (gradientes por índice)
_PLACEHOLDER_GRADIENTS = [
    ("#1a1f2e", "#2d6a4f"),  # verde bosque
    ("#1a1a2e", "#16213e"),  # azul noche
    ("#2d1b69", "#11998e"),  # morado-teal
    ("#1e3c72", "#2a5298"),  # azul océano
    ("#373b44", "#4286f4"),  # gris-azul
    ("#200122", "#6f0000"),  # rojo oscuro
    ("#0f2027", "#203a43"),  # slate
    ("#1a1a1a", "#4a4e69"),  # antracita morado
    ("#134e5e", "#71b280"),  # teal-verde
    ("#0d0d0d", "#434343"),  # negro grafito
]

# SVG inline para banner placeholder — generado con gradiente dinámico
def _make_banner_svg(color1: str, color2: str, kind: str = "mod") -> str:
    icon_path = (
        # Cubo/modpack
        "M50,15 L80,31 L80,63 L50,79 L20,63 L20,31 Z "
        "M50,15 L50,47 M80,31 L50,47 M20,31 L50,47"
        if kind == "modpack"
        # Pieza de puzzle/mod
        else "M20,30 L45,30 C45,30 42,20 50,20 C58,20 55,30 55,30 "
             "L80,30 L80,55 C80,55 90,52 90,60 C90,68 80,65 80,65 "
             "L80,75 L20,75 L20,65 C20,65 10,68 10,60 C10,52 20,55 20,55 Z"
    )
    stroke_color = "#4ade80" if kind == "mod" else "#60a5fa"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="260" height="130" viewBox="0 0 260 130">'
        f'  <defs>'
        f'    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">'
        f'      <stop offset="0%" style="stop-color:{color1};stop-opacity:1" />'
        f'      <stop offset="100%" style="stop-color:{color2};stop-opacity:1" />'
        f'    </linearGradient>'
        f'    <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">'
        f'      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(255,255,255,0.04)" stroke-width="0.5"/>'
        f'    </pattern>'
        f'  </defs>'
        f'  <rect width="260" height="130" fill="url(#bg)"/>'
        f'  <rect width="260" height="130" fill="url(#grid)"/>'
        f'  <g transform="translate(110, 18) scale(0.77)">'
        f'    <path d="{icon_path}" fill="none" stroke="{stroke_color}" stroke-width="2.5"'
        f'      stroke-linejoin="round" stroke-linecap="round" opacity="0.85"/>'
        f'  </g>'
        f'  <rect width="260" height="130" fill="url(#bg)" opacity="0.15"/>'
        f'</svg>'
    )

def _svg_to_data_uri(svg: str) -> str:
    encoded = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{encoded}"


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _get(url: str) -> dict | list:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def _fetch_with_gallery(search_url: str) -> list[dict]:
    hits = _get(search_url).get("hits", [])
    if not hits:
        return []

    ids = [h["project_id"] for h in hits]
    ids_param = urllib.parse.quote(json.dumps(ids))
    bulk_url = f"https://api.modrinth.com/v2/projects?ids={ids_param}"
    projects = {p["id"]: p for p in _get(bulk_url)}

    for hit in hits:
        proj = projects.get(hit["project_id"], {})
        gallery = proj.get("gallery") or []
        featured = next((g["url"] for g in gallery if g.get("featured")), None)
        fallback = gallery[0]["url"] if gallery else None
        hit["_banner"] = featured or fallback or hit.get("featured_gallery") or ""

    return hits


class HomeView:
    def __init__(self, page: ft.Page, app):
        self.page    = page
        self.app     = app
        self._loaded = False

        self._mods_row     = ft.Row(controls=[], scroll=ft.ScrollMode.AUTO, spacing=16)
        self._packs_row    = ft.Row(controls=[], scroll=ft.ScrollMode.AUTO, spacing=16)
        self._mods_status  = ft.Text("Cargando…", color=TEXT_DIM, size=12, italic=True)
        self._packs_status = ft.Text("Cargando…", color=TEXT_DIM, size=12, italic=True)

        self.root = ft.Container(
            expand=True,
            bgcolor=BG,
            padding=ft.padding.all(28),
            content=ft.Column(
                [
                    self._build_header(),
                    ft.Divider(height=1, color=BORDER, thickness=1),

                    # ── Sección Mods ──────────────────────────────────────
                    ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Container(
                                        width=4, height=18,
                                        bgcolor=GREEN,
                                        border_radius=2,
                                    ),
                                    ft.Text(
                                        "Mods populares", color=TEXT_PRI,
                                        size=15, weight=ft.FontWeight.W_600,
                                    ),
                                ],
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            self._mods_status,
                        ],
                        spacing=14,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        content=self._mods_row,
                        height=340,
                    ),

                    ft.Divider(height=1, color=BORDER, thickness=1),

                    # ── Sección Modpacks ──────────────────────────────────
                    ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Container(
                                        width=4, height=18,
                                        bgcolor="#60a5fa",
                                        border_radius=2,
                                    ),
                                    ft.Text(
                                        "Modpacks populares", color=TEXT_PRI,
                                        size=15, weight=ft.FontWeight.W_600,
                                    ),
                                ],
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            self._packs_status,
                        ],
                        spacing=14,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        content=self._packs_row,
                        height=340,
                    ),
                ],
                spacing=14,
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
        )

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self) -> ft.Control:
        return ft.Container(
            padding=ft.padding.symmetric(vertical=8),
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(
                                        ft.icons.ROCKET_LAUNCH_ROUNDED,
                                        color=GREEN, size=28,
                                    ),
                                    ft.Text(
                                        "PyLauncher",
                                        size=28,
                                        weight=ft.FontWeight.BOLD,
                                        color=TEXT_PRI,
                                    ),
                                ],
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Text(
                                "Descubre y gestiona tus mods favoritos de Minecraft",
                                color=TEXT_SEC,
                                size=13,
                            ),
                        ],
                        spacing=4,
                        expand=True,
                    ),
                    ft.ElevatedButton(
                        content=ft.Row(
                            [
                                ft.Icon(ft.icons.EXPLORE_OUTLINED, size=16, color=BG),
                                ft.Text(
                                    "Explorar mods",
                                    size=13,
                                    weight=ft.FontWeight.W_600,
                                    color=BG,
                                ),
                            ],
                            spacing=6,
                        ),
                        on_click=self._go_to_discover,
                        style=ft.ButtonStyle(
                            bgcolor={ft.MaterialState.DEFAULT: GREEN,
                                     ft.MaterialState.HOVERED: "#22c55e"},
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.padding.symmetric(horizontal=18, vertical=12),
                            elevation=0,
                            overlay_color=ft.colors.with_opacity(0.12, ft.colors.WHITE),
                        ),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    # ── Navegación ────────────────────────────────────────────────────────────

    def _go_to_discover(self, _e):
        """Navega a la vista de descubrimiento/exploración de mods."""
        for dest in ("discover", "mods", "browse", "search"):
            try:
                self.app.navigate(dest)
                return
            except Exception:
                continue

    # ── Carga de datos ────────────────────────────────────────────────────────

    def on_show(self):
        if not self._loaded:
            self._loaded = True
            threading.Thread(target=self._load_mods,     daemon=True).start()
            threading.Thread(target=self._load_modpacks, daemon=True).start()

    def _load_mods(self):
        self._load_section(_URL_MODS, self._mods_row, self._mods_status, "mod")

    def _load_modpacks(self):
        self._load_section(_URL_MODPACKS, self._packs_row, self._packs_status, "modpack")

    def _load_section(self, url: str, row: ft.Row, status: ft.Text, kind: str):
        try:
            hits = _fetch_with_gallery(url)
            row.controls = [
                self._build_card(h, kind, idx)
                for idx, h in enumerate(hits)
            ]
            status.visible = False
        except Exception as exc:
            status.value  = f"Error — {exc}"
            status.color  = "#ff6b6b"
            status.italic = False
        self.page.update()

    # ── Card ─────────────────────────────────────────────────────────────────

    def _build_card(self, mod: dict, kind: str = "mod", idx: int = 0) -> ft.Container:
        icon_url   = mod.get("icon_url") or ""
        banner_url = mod.get("_banner") or ""
        title      = mod.get("title", "?")
        raw_desc   = mod.get("description", "")
        desc       = (raw_desc[:90] + "…") if len(raw_desc) > 90 else raw_desc
        downloads  = _fmt(mod.get("downloads", 0))
        follows    = _fmt(mod.get("follows", 0))
        cats       = mod.get("display_categories") or mod.get("categories") or []
        cat_label  = cats[0].capitalize() if cats else ""

        # Colores del placeholder según índice cíclico
        grad = _PLACEHOLDER_GRADIENTS[idx % len(_PLACEHOLDER_GRADIENTS)]

        # Banner
        if banner_url:
            banner: ft.Control = ft.Image(
                src=banner_url, width=260, height=130,
                fit=ft.ImageFit.COVER,
                border_radius=ft.border_radius.only(top_left=10, top_right=10),
                error_content=self._make_svg_banner(grad, kind),
            )
        else:
            banner = self._make_svg_banner(grad, kind)

        # Ícono
        if icon_url:
            icon: ft.Control = ft.Image(
                src=icon_url, width=40, height=40,
                border_radius=ft.border_radius.all(8),
                fit=ft.ImageFit.COVER,
                error_content=self._make_svg_icon(grad, kind),
            )
        else:
            icon = self._make_svg_icon(grad, kind)

        # Stats row
        accent = GREEN if kind == "mod" else "#60a5fa"
        stat_items: list[ft.Control] = [
            ft.Row(
                [
                    ft.Icon(ft.icons.DOWNLOAD_OUTLINED, size=12, color=TEXT_DIM),
                    ft.Text(downloads, size=11, color=TEXT_DIM),
                ],
                spacing=3,
            ),
            ft.Row(
                [
                    ft.Icon(ft.icons.FAVORITE_BORDER, size=12, color=TEXT_DIM),
                    ft.Text(follows, size=11, color=TEXT_DIM),
                ],
                spacing=3,
            ),
        ]
        if cat_label:
            stat_items.append(
                ft.Container(
                    content=ft.Text(cat_label, size=10, color=accent,
                                    weight=ft.FontWeight.W_500),
                    padding=ft.padding.symmetric(horizontal=7, vertical=3),
                    bgcolor=ft.colors.with_opacity(0.12, accent),
                    border_radius=10,
                    border=ft.border.all(1, ft.colors.with_opacity(0.25, accent)),
                )
            )

        body = ft.Container(
            padding=ft.padding.all(11),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            icon,
                            ft.Text(
                                title, size=13,
                                weight=ft.FontWeight.BOLD,
                                color=TEXT_PRI, expand=True,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                max_lines=1,
                            ),
                        ],
                        spacing=9,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        desc, size=11, color=TEXT_SEC,
                        max_lines=3,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Row(stat_items, spacing=8),
                ],
                spacing=7,
            ),
        )

        card = ft.Container(
            width=260,
            bgcolor=CARD_BG,
            border_radius=10,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            border=ft.border.all(1, BORDER),
            content=ft.Column([banner, body], spacing=0),
            animate_opacity=200,
        )
        card.on_hover = lambda e, c=card: self._on_card_hover(e, c)
        return card

    # ── Placeholders SVG ──────────────────────────────────────────────────────

    @staticmethod
    def _make_svg_banner(
        grad: tuple[str, str],
        kind: str = "mod",
    ) -> ft.Container:
        """Banner placeholder con gradiente SVG y patrón de cuadrícula."""
        svg = _make_banner_svg(grad[0], grad[1], kind)
        data_uri = _svg_to_data_uri(svg)
        return ft.Container(
            width=260, height=130,
            border_radius=ft.border_radius.only(top_left=10, top_right=10),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Image(
                src=data_uri,
                width=260, height=130,
                fit=ft.ImageFit.COVER,
            ),
        )

    @staticmethod
    def _make_svg_icon(
        grad: tuple[str, str],
        kind: str = "mod",
    ) -> ft.Container:
        """Ícono placeholder con gradiente SVG pequeño."""
        ico = ft.icons.WIDGETS_OUTLINED if kind == "modpack" else ft.icons.EXTENSION_OUTLINED
        # Ícono con fondo gradiente usando Container + stack
        accent = "#60a5fa" if kind == "modpack" else "#4ade80"
        return ft.Container(
            width=40, height=40,
            border_radius=ft.border_radius.all(8),
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left,
                end=ft.alignment.bottom_right,
                colors=[grad[0], grad[1]],
            ),
            content=ft.Icon(ico, color=accent, size=20),
            alignment=ft.alignment.center,
        )

    # ── Hover ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _on_card_hover(e: ft.HoverEvent, card: ft.Container):
        is_hover = e.data == "true"
        card.border = ft.border.all(1, BORDER_BRIGHT if is_hover else BORDER)
        card.bgcolor = CARD2_BG if is_hover else CARD_BG
        card.update()