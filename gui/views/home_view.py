"""
gui/views/home_view.py — Home estilo Modrinth con caché de imágenes en disco.
"""
import hashlib
import json
import os
import threading
import urllib.request
import urllib.parse

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

# Directorio de caché (junto al script o en AppData)
_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "cache", "images")
os.makedirs(_CACHE_DIR, exist_ok=True)

# Paletas (start, end, accent) por índice cíclico
_PALETTES = [
    ("#0f2d1a", "#1a5c32", "#4ade80"),
    ("#0d1b3e", "#1a2f6b", "#60a5fa"),
    ("#1e0a3c", "#3b1278", "#a78bfa"),
    ("#0a1f3d", "#0e4a7a", "#38bdf8"),
    ("#1a0d00", "#5c2800", "#fb923c"),
    ("#0d2626", "#0e5555", "#2dd4bf"),
    ("#1f0a0a", "#6b1212", "#f87171"),
    ("#1a1208", "#5c3d08", "#fbbf24"),
    ("#0a1a0a", "#1a4a1a", "#86efac"),
    ("#1a0a1f", "#4a1060", "#e879f9"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Caché de imágenes
# ─────────────────────────────────────────────────────────────────────────────

def _cache_path(url: str) -> str:
    """Devuelve la ruta local para una URL, usando su hash como nombre."""
    ext = os.path.splitext(url.split("?")[0])[-1][:5] or ".png"
    name = hashlib.md5(url.encode()).hexdigest() + ext
    return os.path.join(_CACHE_DIR, name)


def _cached_image_src(url: str) -> str:
    """
    Devuelve la ruta local si la imagen ya está cacheada,
    o descarga y cachea antes de devolver la ruta.
    Ante cualquier error devuelve la URL original.
    """
    if not url:
        return ""
    path = _cache_path(url)
    if os.path.exists(path):
        return path
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
        return path
    except Exception:
        return url          # fallback: URL directa


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _get(url: str) -> dict | list:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def _fetch_with_gallery(search_url: str) -> list[dict]:
    hits = _get(search_url).get("hits", [])
    if not hits:
        return []
    ids       = [h["project_id"] for h in hits]
    ids_param = urllib.parse.quote(json.dumps(ids))
    bulk_url  = f"https://api.modrinth.com/v2/projects?ids={ids_param}"
    projects  = {p["id"]: p for p in _get(bulk_url)}
    for hit in hits:
        proj    = projects.get(hit["project_id"], {})
        gallery = proj.get("gallery") or []
        featured = next((g["url"] for g in gallery if g.get("featured")), None)
        fallback = gallery[0]["url"] if gallery else None
        hit["_banner"] = featured or fallback or hit.get("featured_gallery") or ""
    return hits


# ─────────────────────────────────────────────────────────────────────────────
# Placeholders Flet (sin letter_spacing, sin Stack posicional)
# ─────────────────────────────────────────────────────────────────────────────

def _banner_placeholder(idx: int, kind: str = "mod") -> ft.Container:
    c1, c2, accent = _PALETTES[idx % len(_PALETTES)]
    ico   = ft.icons.WIDGETS_OUTLINED if kind == "modpack" else ft.icons.EXTENSION_OUTLINED
    label = "MODPACK" if kind == "modpack" else "MOD"

    top_row = ft.Row(
        [
            ft.Container(expand=True),
            ft.Container(
                content=ft.Text(label, size=9, color=ft.colors.with_opacity(0.8, accent),
                                weight=ft.FontWeight.W_700),
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                bgcolor=ft.colors.with_opacity(0.18, accent),
                border_radius=4,
                border=ft.border.all(1, ft.colors.with_opacity(0.25, accent)),
            ),
        ],
    )

    center = ft.Row(
        [
            ft.Container(
                width=56, height=56, border_radius=28,
                bgcolor=ft.colors.with_opacity(0.15, accent),
                border=ft.border.all(1, ft.colors.with_opacity(0.3, accent)),
                content=ft.Icon(ico, color=accent, size=26),
                alignment=ft.alignment.center,
            )
        ],
        alignment=ft.MainAxisAlignment.CENTER,
    )

    return ft.Container(
        width=260, height=130,
        border_radius=ft.border_radius.only(top_left=10, top_right=10),
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=[c1, c2],
        ),
        content=ft.Column(
            [
                ft.Container(content=top_row, padding=ft.padding.only(right=10, top=8)),
                ft.Container(content=center, expand=True),
                ft.Container(height=8),
            ],
            spacing=0,
            expand=True,
        ),
    )


def _icon_placeholder(idx: int, kind: str = "mod") -> ft.Container:
    c1, c2, accent = _PALETTES[idx % len(_PALETTES)]
    ico = ft.icons.WIDGETS_OUTLINED if kind == "modpack" else ft.icons.EXTENSION_OUTLINED
    return ft.Container(
        width=40, height=40,
        border_radius=ft.border_radius.all(8),
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=[c1, c2],
        ),
        content=ft.Icon(ico, color=accent, size=20),
        alignment=ft.alignment.center,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Vista principal
# ─────────────────────────────────────────────────────────────────────────────

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
                    self._section_title("Mods populares",     GREEN,     self._mods_status),
                    ft.Container(content=self._mods_row,  height=340),
                    ft.Divider(height=1, color=BORDER, thickness=1),
                    self._section_title("Modpacks populares", "#60a5fa", self._packs_status),
                    ft.Container(content=self._packs_row, height=340),
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
                                    ft.Icon(ft.icons.ROCKET_LAUNCH_ROUNDED,
                                            color=GREEN, size=26),
                                    ft.Text("PyLauncher", size=26,
                                            weight=ft.FontWeight.BOLD, color=TEXT_PRI),
                                ],
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Text(
                                "Descubre y gestiona tus mods favoritos de Minecraft",
                                color=TEXT_SEC, size=13,
                            ),
                        ],
                        spacing=4,
                        expand=True,
                    ),
                    ft.ElevatedButton(
                        content=ft.Row(
                            [
                                ft.Icon(ft.icons.EXPLORE_OUTLINED, size=16, color=BG),
                                ft.Text("Explorar mods", size=13,
                                        weight=ft.FontWeight.W_600, color=BG),
                            ],
                            spacing=6,
                        ),
                        on_click=self._go_to_discover,
                        style=ft.ButtonStyle(
                            bgcolor={
                                ft.MaterialState.DEFAULT: GREEN,
                                ft.MaterialState.HOVERED: "#22c55e",
                            },
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

    @staticmethod
    def _section_title(label: str, accent: str, status: ft.Text) -> ft.Row:
        return ft.Row(
            [
                ft.Row(
                    [
                        ft.Container(width=4, height=18, bgcolor=accent, border_radius=2),
                        ft.Text(label, color=TEXT_PRI, size=15,
                                weight=ft.FontWeight.W_600),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                status,
            ],
            spacing=14,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    # ── Navegación ────────────────────────────────────────────────────────────

    def _go_to_discover(self, _e):
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
        accent     = GREEN if kind == "mod" else "#60a5fa"
        ph_idx     = idx % len(_PALETTES)

        # Resuelve src con caché (descarga en background ya terminó en _load_section)
        banner_src = _cached_image_src(banner_url) if banner_url else ""
        icon_src   = _cached_image_src(icon_url)   if icon_url   else ""

        # Banner
        ph_banner = _banner_placeholder(ph_idx, kind)
        if banner_src:
            banner: ft.Control = ft.Image(
                src=banner_src, width=260, height=130,
                fit=ft.ImageFit.COVER,
                border_radius=ft.border_radius.only(top_left=10, top_right=10),
                error_content=ph_banner,
            )
        else:
            banner = ph_banner

        # Ícono
        ph_icon = _icon_placeholder(ph_idx, kind)
        if icon_src:
            icon_ctrl: ft.Control = ft.Image(
                src=icon_src, width=40, height=40,
                border_radius=ft.border_radius.all(8),
                fit=ft.ImageFit.COVER,
                error_content=ph_icon,
            )
        else:
            icon_ctrl = ph_icon

        # Stats
        stat_items: list[ft.Control] = [
            ft.Row([ft.Icon(ft.icons.DOWNLOAD_OUTLINED, size=12, color=TEXT_DIM),
                    ft.Text(downloads, size=11, color=TEXT_DIM)], spacing=3),
            ft.Row([ft.Icon(ft.icons.FAVORITE_BORDER,   size=12, color=TEXT_DIM),
                    ft.Text(follows,   size=11, color=TEXT_DIM)], spacing=3),
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
                        [icon_ctrl,
                         ft.Text(title, size=13, weight=ft.FontWeight.BOLD,
                                 color=TEXT_PRI, expand=True,
                                 overflow=ft.TextOverflow.ELLIPSIS, max_lines=1)],
                        spacing=9,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(desc, size=11, color=TEXT_SEC,
                            max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row(stat_items, spacing=8),
                ],
                spacing=7,
            ),
        )

        card = ft.Container(
            width=260, bgcolor=CARD_BG,
            border_radius=10,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            border=ft.border.all(1, BORDER),
            content=ft.Column([banner, body], spacing=0),
        )
        card.on_hover = lambda e, c=card: self._on_card_hover(e, c)
        return card

    @staticmethod
    def _on_card_hover(e: ft.HoverEvent, card: ft.Container):
        is_hover = e.data == "true"
        card.border = ft.border.all(1, BORDER_BRIGHT if is_hover else BORDER)
        card.bgcolor = CARD2_BG if is_hover else CARD_BG
        card.update()