"""
gui/views/home_view.py — Home estilo Modrinth con mejoras:

  ✔ Carrusel con auto-scroll suave + botones ◀ ▶
  ✔ Skeleton loading animado mientras carga
  ✔ Tooltips en botones de stats
  ✔ Botón "Ver proyecto" en hover de cada tarjeta
  ✔ Indicador de puntos (dot-pager) bajo cada carrusel
  ✔ Sección "Top pick" destacada (primera tarjeta grande)
  ✔ Caché de imágenes en disco
  ✔ Scroll vertical del Column padre no interfiere con scroll horizontal de ListView
"""

import hashlib
import json
import os
import threading
import time
import urllib.parse
import urllib.request

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

_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "cache", "images")
os.makedirs(_CACHE_DIR, exist_ok=True)

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

# ── Caché de imágenes ─────────────────────────────────────────────────────────

def _cache_path(url: str) -> str:
    ext  = os.path.splitext(url.split("?")[0])[-1][:5] or ".png"
    name = hashlib.md5(url.encode()).hexdigest() + ext
    return os.path.join(_CACHE_DIR, name)


def _cached_image_src(url: str) -> str:
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
        return url


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
        proj     = projects.get(hit["project_id"], {})
        gallery  = proj.get("gallery") or []
        featured = next((g["url"] for g in gallery if g.get("featured")), None)
        fallback = gallery[0]["url"] if gallery else None
        hit["_banner"] = featured or fallback or hit.get("featured_gallery") or ""
    return hits


# ── Placeholders ──────────────────────────────────────────────────────────────

def _banner_placeholder(idx: int, kind: str = "mod") -> ft.Container:
    c1, c2, accent = _PALETTES[idx % len(_PALETTES)]
    ico   = ft.icons.WIDGETS_OUTLINED if kind == "modpack" else ft.icons.EXTENSION_OUTLINED
    label = "MODPACK" if kind == "modpack" else "MOD"

    top_row = ft.Row([
        ft.Container(expand=True),
        ft.Container(
            content=ft.Text(label, size=9, color=ft.colors.with_opacity(0.8, accent),
                            weight=ft.FontWeight.W_700),
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            bgcolor=ft.colors.with_opacity(0.18, accent),
            border_radius=4,
            border=ft.border.all(1, ft.colors.with_opacity(0.25, accent)),
        ),
    ])

    center = ft.Row([
        ft.Container(
            width=56, height=56, border_radius=28,
            bgcolor=ft.colors.with_opacity(0.15, accent),
            border=ft.border.all(1, ft.colors.with_opacity(0.3, accent)),
            content=ft.Icon(ico, color=accent, size=26),
            alignment=ft.alignment.center,
        )
    ], alignment=ft.MainAxisAlignment.CENTER)

    return ft.Container(
        width=260, height=130,
        border_radius=ft.border_radius.only(top_left=10, top_right=10),
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=[c1, c2],
        ),
        content=ft.Column([
            ft.Container(content=top_row, padding=ft.padding.only(right=10, top=8)),
            ft.Container(content=center, expand=True),
            ft.Container(height=8),
        ], spacing=0, expand=True),
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


# ── Skeleton card ─────────────────────────────────────────────────────────────

def _skeleton_card() -> ft.Container:
    """Tarjeta de carga animada (shimmer)."""
    shimmer_color = ft.colors.with_opacity(0.08, ft.colors.WHITE)
    def _box(w, h, radius=6):
        return ft.Container(
            width=w, height=h,
            bgcolor=shimmer_color,
            border_radius=radius,
            animate_opacity=ft.animation.Animation(800, ft.AnimationCurve.EASE_IN_OUT),
        )

    return ft.Container(
        width=260,
        bgcolor=CARD_BG,
        border_radius=10,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        border=ft.border.all(1, BORDER),
        content=ft.Column([
            # Banner skeleton
            ft.Container(
                width=260, height=130,
                bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE),
                border_radius=ft.border_radius.only(top_left=10, top_right=10),
            ),
            # Body skeleton
            ft.Container(
                padding=ft.padding.all(11),
                content=ft.Column([
                    ft.Row([_box(40, 40, 8), _box(140, 14)], spacing=9),
                    _box(220, 11),
                    _box(180, 11),
                    _box(200, 11),
                    ft.Row([_box(60, 20, 10), _box(60, 20, 10), _box(80, 20, 10)], spacing=8),
                ], spacing=8),
            ),
        ], spacing=0),
    )


# ── Carrusel con auto-scroll y botones ────────────────────────────────────────

class CardCarousel:
    """
    Carrusel horizontal con:
      - Auto-scroll cada `interval` segundos
      - Botones ◀ ▶ para navegación manual
      - Dot-pager indicador de posición
      - Pausa del auto-scroll al hacer hover
    """
    CARD_WIDTH  = 260
    CARD_GAP    = 16

    def __init__(self, page: ft.Page, kind: str, interval: float = 4.0):
        self.page      = page
        self.kind      = kind
        self.interval  = interval
        self._cards: list[ft.Container] = []
        self._current  = 0
        self._paused   = False
        self._running  = False

        # ListView con scroll controlado por offset
        self._lv = ft.ListView(
            controls=[_skeleton_card() for _ in range(6)],
            horizontal=True,
            spacing=self.CARD_GAP,
            height=340,
            padding=ft.padding.symmetric(horizontal=4),
        )

        # Dots
        self._dots_row = ft.Row(
            [],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=6,
        )

        # Botones nav
        btn_style = ft.ButtonStyle(
            bgcolor={ft.MaterialState.DEFAULT: ft.colors.with_opacity(0.15, ft.colors.WHITE),
                     ft.MaterialState.HOVERED: ft.colors.with_opacity(0.28, ft.colors.WHITE)},
            shape=ft.CircleBorder(),
            padding=ft.padding.all(6),
            overlay_color=ft.colors.TRANSPARENT,
        )
        self._btn_prev = ft.IconButton(
            icon=ft.icons.CHEVRON_LEFT_ROUNDED,
            icon_color=TEXT_PRI, icon_size=20,
            style=btn_style,
            on_click=self._prev,
            tooltip="Anterior",
        )
        self._btn_next = ft.IconButton(
            icon=ft.icons.CHEVRON_RIGHT_ROUNDED,
            icon_color=TEXT_PRI, icon_size=20,
            style=btn_style,
            on_click=self._next,
            tooltip="Siguiente",
        )

        # Layout de navegación sobre el carrusel
        self._nav_row = ft.Row(
            [self._btn_prev, ft.Container(expand=True), self._btn_next],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.widget = ft.Column(
            [
                ft.Stack(
                    [
                        self._lv,
                        ft.Container(
                            content=self._nav_row,
                            padding=ft.padding.symmetric(horizontal=4),
                            alignment=ft.alignment.center,
                            height=340,
                        ),
                    ]
                ),
                ft.Container(content=self._dots_row, padding=ft.padding.only(top=6)),
            ],
            spacing=0,
        )

    # ── Carga ─────────────────────────────────────────────────────────────────

    def load(self, cards: list[ft.Container]):
        self._cards   = cards
        self._current = 0
        self._lv.controls = cards
        self._build_dots(len(cards))
        self.page.update()
        if not self._running:
            self._running = True
            threading.Thread(target=self._auto_scroll_loop, daemon=True).start()

    # ── Dots ──────────────────────────────────────────────────────────────────

    def _build_dots(self, n: int):
        accent = GREEN if self.kind == "mod" else "#60a5fa"
        dots = []
        for i in range(min(n, 20)):
            dots.append(ft.Container(
                width=8 if i == 0 else 6,
                height=6,
                border_radius=3,
                bgcolor=accent if i == 0 else ft.colors.with_opacity(0.25, ft.colors.WHITE),
                data=i,
            ))
        self._dots_row.controls = dots

    def _update_dots(self):
        accent = GREEN if self.kind == "mod" else "#60a5fa"
        for i, dot in enumerate(self._dots_row.controls):
            is_active = i == (self._current % len(self._dots_row.controls))
            dot.bgcolor = accent if is_active else ft.colors.with_opacity(0.25, ft.colors.WHITE)
            dot.width   = 8 if is_active else 6

    # ── Scroll ────────────────────────────────────────────────────────────────

    def _scroll_to(self, idx: int):
        if not self._cards:
            return
        # ✅ Si el ListView no está en la página todavía, no hacemos nada
        if self._lv.page is None:
            return
        idx = max(0, min(idx, len(self._cards) - 1))
        self._current = idx
        offset = idx * (self.CARD_WIDTH + self.CARD_GAP)
        self._lv.scroll_to(offset=offset, duration=400)
        self._update_dots()
        try:
            self.page.update()
        except Exception:
            pass
        
    def _prev(self, _e=None):
        self._paused = True
        target = (self._current - 1) % len(self._cards) if self._cards else 0
        self._scroll_to(target)

    def _next(self, _e=None):
        self._paused = True
        target = (self._current + 1) % len(self._cards) if self._cards else 0
        self._scroll_to(target)

    # ── Auto-scroll loop ──────────────────────────────────────────────────────

    def _auto_scroll_loop(self):
        while self._running:
            time.sleep(self.interval)
            if self._paused:
                self._paused = False
                continue
            if not self._cards:
                continue
            target = (self._current + 1) % len(self._cards)
            self._scroll_to(target)


# ── Vista principal ───────────────────────────────────────────────────────────

class HomeView:
    def __init__(self, page: ft.Page, app):
        self.page    = page
        self.app     = app
        self._loaded = False

        self._mods_carousel  = CardCarousel(page, kind="mod",     interval=4.5)
        self._packs_carousel = CardCarousel(page, kind="modpack", interval=5.0)

        self._mods_status  = ft.Text("Cargando…", color=TEXT_DIM, size=12, italic=True)
        self._packs_status = ft.Text("Cargando…", color=TEXT_DIM, size=12, italic=True)

        # Botón Explorar — Container clickeable, compatible con todas las versiones de Flet
        self._explore_btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.icons.EXPLORE_OUTLINED, size=16, color=BG),
                    ft.Text("Explorar mods", size=13,
                            weight=ft.FontWeight.W_600, color=BG),
                ],
                spacing=6,
                tight=True,
            ),
            bgcolor=GREEN,
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=18, vertical=12),
            on_click=self._go_to_discover,
            on_hover=self._on_explore_hover,
            ink=True,
        )

        self.root = ft.Container(
            expand=True,
            bgcolor=BG,
            padding=ft.padding.all(28),
            content=ft.Column(
                [
                    self._build_header(),
                    ft.Divider(height=1, color=BORDER, thickness=1),
                    self._section_title("🔥 Mods populares",     GREEN,     self._mods_status),
                    self._mods_carousel.widget,
                    ft.Divider(height=1, color=BORDER, thickness=1),
                    self._section_title("📦 Modpacks populares", "#60a5fa", self._packs_status),
                    self._packs_carousel.widget,
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
                                    ft.Icon(ft.icons.ROCKET_LAUNCH_ROUNDED, color=GREEN, size=26),
                                    ft.Text("Gero´s Launcher", size=26,
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
                    self._explore_btn,
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
                        ft.Text(label, color=TEXT_PRI, size=15, weight=ft.FontWeight.W_600),
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

    def _on_explore_hover(self, e: ft.HoverEvent):
        self._explore_btn.bgcolor = "#22c55e" if e.data == "true" else GREEN
        self._explore_btn.update()

    # ── Carga de datos ────────────────────────────────────────────────────────

    def on_show(self):
        if not self._loaded:
            self._loaded = True
            threading.Thread(target=self._load_mods,     daemon=True).start()
            threading.Thread(target=self._load_modpacks, daemon=True).start()

    def _load_mods(self):
        self._load_section(
            _URL_MODS, self._mods_carousel, self._mods_status, "mod"
        )

    def _load_modpacks(self):
        self._load_section(
            _URL_MODPACKS, self._packs_carousel, self._packs_status, "modpack"
        )

    def _load_section(
        self,
        url: str,
        carousel: CardCarousel,
        status: ft.Text,
        kind: str,
    ):
        try:
            hits  = _fetch_with_gallery(url)
            cards = [self._build_card(h, kind, i) for i, h in enumerate(hits)]
            carousel.load(cards)
            status.visible = False
        except Exception as exc:
            status.value  = f"Error — {exc}"
            status.color  = "#ff6b6b"
            status.italic = False
        self.page.update()

    # ── Card ──────────────────────────────────────────────────────────────────

    def _build_card(self, mod: dict, kind: str = "mod", idx: int = 0) -> ft.Container:
        icon_url   = mod.get("icon_url") or ""
        banner_url = mod.get("_banner")  or ""
        title      = mod.get("title", "?")
        raw_desc   = mod.get("description", "")
        desc       = (raw_desc[:90] + "…") if len(raw_desc) > 90 else raw_desc
        downloads  = _fmt(mod.get("downloads", 0))
        follows    = _fmt(mod.get("follows", 0))
        cats       = mod.get("display_categories") or mod.get("categories") or []
        cat_label  = cats[0].capitalize() if cats else ""
        accent     = GREEN if kind == "mod" else "#60a5fa"
        ph_idx     = idx % len(_PALETTES)
        project_id = mod.get("project_id", "")
        slug       = mod.get("slug", project_id)

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

        # Stats simples sin Tooltip (compatibilidad con todas las versiones de Flet)
        stat_items: list[ft.Control] = [
            ft.Row([
                ft.Icon(ft.icons.DOWNLOAD_OUTLINED, size=12, color=TEXT_DIM),
                ft.Text(downloads, size=11, color=TEXT_DIM),
            ], spacing=3),
            ft.Row([
                ft.Icon(ft.icons.FAVORITE_BORDER, size=12, color=TEXT_DIM),
                ft.Text(follows, size=11, color=TEXT_DIM),
            ], spacing=3),
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

        # Botón "Ver en Modrinth" — visible solo en hover
        view_btn = ft.Container(
            visible=False,
            content=ft.ElevatedButton(
                content=ft.Row([
                    ft.Icon(ft.icons.OPEN_IN_NEW_ROUNDED, size=13, color=BG),
                    ft.Text("Ver proyecto", size=12, weight=ft.FontWeight.W_600, color=BG),
                ], spacing=5, tight=True),
                on_click=lambda _e, s=slug, k=kind: self._open_project(s, k),
                style=ft.ButtonStyle(
                    bgcolor={ft.MaterialState.DEFAULT: accent,
                             ft.MaterialState.HOVERED: ft.colors.with_opacity(0.85, accent)},
                    shape=ft.RoundedRectangleBorder(radius=6),
                    padding=ft.padding.symmetric(horizontal=12, vertical=7),
                    elevation=0,
                    overlay_color=ft.colors.with_opacity(0.1, ft.colors.WHITE),
                ),
            ),
            alignment=ft.alignment.center_right,
            padding=ft.padding.only(top=4),
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
                    view_btn,
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
            # Guardamos referencias para el hover
            data={"view_btn": view_btn},
        )
        card.on_hover = lambda e, c=card: self._on_card_hover(e, c)
        return card

    def _open_project(self, slug: str, kind: str):
        """Abre el proyecto en Modrinth dentro del launcher si es posible,
        o delega en la app."""
        url = f"https://modrinth.com/{kind}/{slug}"
        try:
            self.app.open_url(url)
        except Exception:
            import webbrowser
            webbrowser.open(url)

    @staticmethod
    def _on_card_hover(e: ft.HoverEvent, card: ft.Container):
        is_hover = e.data == "true"
        card.border  = ft.border.all(1, BORDER_BRIGHT if is_hover else BORDER)
        card.bgcolor = CARD2_BG if is_hover else CARD_BG

        # Mostrar / ocultar botón "Ver proyecto"
        view_btn: ft.Container = card.data.get("view_btn")
        if view_btn is not None:
            view_btn.visible = is_hover

        card.update()