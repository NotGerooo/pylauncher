# -*- coding: utf-8 -*-
"""
gui/sidebar_right.py
Dos modos:
  • Normal  — cuenta activa + feed de noticias (rediseñado premium)
  • Discover — panel de filtros elegante con iconos por categoría
"""
import threading
import urllib.request
import json
import hashlib
import os
import flet as ft

from gui.theme import (
    SIDEBAR_BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER, BORDER_BRIGHT,
    GREEN, GREEN_DIM, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV,
    AVATAR_PALETTE,
)
from utils.logger import get_logger

log = get_logger()

# ── Caché de imágenes ──────────────────────────────────────────────────────────
_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache", "images")
os.makedirs(_CACHE_DIR, exist_ok=True)

_HEADERS = {"User-Agent": "PyLauncher/1.0"}

def _cached_src(url: str) -> str:
    if not url:
        return ""
    ext  = os.path.splitext(url.split("?")[0])[-1][:5] or ".png"
    name = hashlib.md5(url.encode()).hexdigest() + ext
    path = os.path.join(_CACHE_DIR, name)
    if os.path.exists(path):
        return path
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
        return path
    except Exception:
        return url


# ── Categorías ────────────────────────────────────────────────────────────────
_CAT_ICONS = {
    "Adventure":      ft.icons.EXPLORE_ROUNDED,
    "Atmosphere":     ft.icons.CLOUD_ROUNDED,
    "Cartoon":        ft.icons.BRUSH_ROUNDED,
    "Challenging":    ft.icons.FITNESS_CENTER_ROUNDED,
    "Combat":         ft.icons.SPORTS_MARTIAL_ARTS_ROUNDED,
    "Cursed":         ft.icons.AUTO_AWESOME_ROUNDED,
    "Decoration":     ft.icons.PALETTE_ROUNDED,
    "Economy":        ft.icons.ATTACH_MONEY_ROUNDED,
    "Equipment":      ft.icons.SHIELD_ROUNDED,
    "Foliage":        ft.icons.FOREST_ROUNDED,
    "Fonts":          ft.icons.TEXT_FIELDS_ROUNDED,
    "Food":           ft.icons.RESTAURANT_ROUNDED,
    "Game Mechanics": ft.icons.GAMEPAD_ROUNDED,
    "Icons":          ft.icons.EMOJI_EMOTIONS_ROUNDED,
    "Library":        ft.icons.BOOK_ROUNDED,
    "Lightweight":    ft.icons.BOLT_ROUNDED,
    "Locale":         ft.icons.LANGUAGE_ROUNDED,
    "Magic":          ft.icons.STAR_ROUNDED,
    "Management":     ft.icons.MANAGE_ACCOUNTS_ROUNDED,
    "Modded":         ft.icons.EXTENSION_ROUNDED,
    "Mobs":           ft.icons.PETS_ROUNDED,
    "Multiplayer":    ft.icons.PEOPLE_ROUNDED,
    "Optimization":   ft.icons.SPEED_ROUNDED,
    "Path Tracing":   ft.icons.LENS_ROUNDED,
    "PBR":            ft.icons.GRAIN_ROUNDED,
    "Quests":         ft.icons.CHECKLIST_ROUNDED,
    "Realistic":      ft.icons.LANDSCAPE_ROUNDED,
    "Sci-Fi":         ft.icons.ROCKET_LAUNCH_ROUNDED,
    "Semi-realistic": ft.icons.NATURE_ROUNDED,
    "Skyblock":       ft.icons.CLOUD_CIRCLE_ROUNDED,
    "Social":         ft.icons.FORUM_ROUNDED,
    "Storage":        ft.icons.INVENTORY_ROUNDED,
    "Technology":     ft.icons.SETTINGS_ROUNDED,
    "Transportation": ft.icons.TRAIN_ROUNDED,
    "Unbound":        ft.icons.ALL_INCLUSIVE_ROUNDED,
    "Utility":        ft.icons.BUILD_ROUNDED,
    "Vanilla-like":   ft.icons.GRASS_ROUNDED,
    "Worldgen":       ft.icons.TERRAIN_ROUNDED,
}

CATEGORIES_BY_TYPE: dict[str, list[str]] = {
    "mod": [
        "Adventure", "Cursed", "Decoration", "Economy", "Equipment",
        "Food", "Game Mechanics", "Library", "Magic", "Management",
        "Mobs", "Optimization", "Social", "Storage", "Technology",
        "Transportation", "Utility", "Worldgen",
    ],
    "resourcepack": [
        "Decoration", "Fonts", "Icons", "Locale",
        "Modded", "Realistic", "Utility", "Vanilla-like",
    ],
    "shader": [
        "Atmosphere", "Cartoon", "Cursed", "Foliage",
        "Path Tracing", "PBR", "Realistic", "Semi-realistic",
        "Unbound", "Vanilla-like",
    ],
    "datapack": [
        "Adventure", "Cursed", "Decoration", "Economy", "Equipment",
        "Food", "Game Mechanics", "Library", "Magic", "Mobs",
        "Optimization", "Storage", "Technology", "Utility", "Worldgen",
    ],
    "modpack": [
        "Adventure", "Challenging", "Combat", "Decoration", "Equipment",
        "Food", "Lightweight", "Magic", "Multiplayer", "Optimization",
        "Quests", "Sci-Fi", "Skyblock", "Technology", "Vanilla-like",
    ],
}

LOADERS = ["fabric", "forge", "neoforge", "quilt"]

_LOADER_ICONS = {
    "fabric":   ft.icons.TEXTURE_ROUNDED,
    "forge":    ft.icons.HARDWARE_ROUNDED,
    "neoforge": ft.icons.CONSTRUCTION_ROUNDED,
    "quilt":    ft.icons.GRID_4X4_ROUNDED,
}

_LOADER_COLORS = {
    "fabric":   "#dbb68a",
    "forge":    "#6c8ebf",
    "neoforge": "#e8a87c",
    "quilt":    "#b39ddb",
}

# ── Paletas tipo noticia ───────────────────────────────────────────────────────
_NEWS_TYPE_STYLE: dict[str, dict] = {
    "release":  {"label": "RELEASE",  "color": GREEN,     "icon": ft.icons.NEW_RELEASES_ROUNDED,    "bg": "#0f2d1a"},
    "snapshot": {"label": "SNAPSHOT", "color": "#4dabf7", "icon": ft.icons.SCIENCE_ROUNDED,          "bg": "#0d1b3e"},
    "old_beta": {"label": "BETA",     "color": "#ffa94d", "icon": ft.icons.HISTORY_ROUNDED,          "bg": "#2d1a00"},
    "old_alpha":{"label": "ALPHA",    "color": "#ff6b6b", "icon": ft.icons.FIND_IN_PAGE_ROUNDED,     "bg": "#2d0a0a"},
    "mod":      {"label": "MOD",      "color": "#a9e34b", "icon": ft.icons.EXTENSION_ROUNDED,        "bg": "#1a2d00"},
    "modpack":  {"label": "MODPACK",  "color": "#60a5fa", "icon": ft.icons.WIDGETS_ROUNDED,          "bg": "#0a1a2d"},
    "latest":   {"label": "LATEST",   "color": GREEN,     "icon": ft.icons.STAR_ROUNDED,             "bg": "#0f2d1a"},
}


class SidebarRight:
    def __init__(self, app):
        self.app  = app
        self.page = app.page

        self._excluded_cats: set = set()
        self._discover_mode      = False
        self._on_filter_change   = None
        self._selected_cats: set = set()
        self._hide_installed     = False
        self._discover_profile   = None
        self._discover_tab_type  = "mod"
        self._discover_loader    = None

        self._ver_expanded    = True
        self._loader_expanded = True
        self._cat_expanded    = True

        self._build()
        threading.Thread(target=self._fetch_news, daemon=True).start()
        threading.Timer(0.5, self.refresh_account).start()

    # ═══════════════════════════════════════════════════════════════════════
    #  Shell
    # ═══════════════════════════════════════════════════════════════════════
    def _build(self):
        self._swap = ft.Container(expand=True)
        self.root  = ft.Container(
            width=290,
            bgcolor=SIDEBAR_BG,
            content=ft.Column([self._swap], spacing=0, expand=True),
        )
        self._build_normal_content()
        self._swap.content = self._normal_col

    def _set_swap(self, content):
        self._swap.content = content
        try:
            self._swap.update()
        except Exception:
            pass
        try:
            self.page.update()
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    #  NORMAL MODE — Account + News (rediseñado)
    # ═══════════════════════════════════════════════════════════════════════
    def _build_normal_content(self):
        # ── Avatar con glow ───────────────────────────────────────────────
        self._avatar_initials = ft.Text(
            "??", color=TEXT_INV, size=14, weight=ft.FontWeight.BOLD,
        )
        self._avatar_inner = ft.Container(
            width=46, height=46, border_radius=23,
            bgcolor=GREEN,
            alignment=ft.alignment.center,
            content=self._avatar_initials,
            animate=ft.animation.Animation(300, ft.AnimationCurve.EASE_OUT),
        )
        # Anillo de glow exterior
        self._avatar_glow = ft.Container(
            width=54, height=54, border_radius=27,
            bgcolor="transparent",
            border=ft.border.all(2, ft.colors.with_opacity(0.5, GREEN)),
            shadow=[ft.BoxShadow(
                spread_radius=0, blur_radius=14,
                color=ft.colors.with_opacity(0.4, GREEN),
                offset=ft.Offset(0, 0),
            )],
            content=ft.Container(
                width=50, height=50, border_radius=25,
                bgcolor="transparent",
                alignment=ft.alignment.center,
                content=self._avatar_inner,
            ),
            alignment=ft.alignment.center,
            animate=ft.animation.Animation(400, ft.AnimationCurve.EASE_OUT),
        )
        self._avatar_glow_ref = self._avatar_glow   # para actualizar el shadow

        # ── Status dot animado ────────────────────────────────────────────
        self._status_dot = ft.Container(
            width=9, height=9, border_radius=5,
            bgcolor=TEXT_DIM,
            shadow=[ft.BoxShadow(
                spread_radius=0, blur_radius=6,
                color=ft.colors.with_opacity(0.0, GREEN),
                offset=ft.Offset(0, 0),
            )],
            animate=ft.animation.Animation(400, ft.AnimationCurve.EASE_OUT),
        )
        self._username_lbl = ft.Text(
            "—", color=TEXT_PRI, size=13,
            weight=ft.FontWeight.BOLD,
        )
        self._mode_lbl = ft.Text(
            "Sin cuenta", color=TEXT_DIM, size=10,
        )

        # ── Badge tipo cuenta ─────────────────────────────────────────────
        self._account_badge = ft.Container(
            content=ft.Text("OFFLINE", size=8, color=TEXT_DIM,
                            weight=ft.FontWeight.W_700),
            padding=ft.padding.symmetric(horizontal=7, vertical=3),
            bgcolor=INPUT_BG,
            border_radius=4,
            border=ft.border.all(1, BORDER),
            animate=ft.animation.Animation(300, ft.AnimationCurve.EASE_OUT),
        )

        # ── Botón cambiar cuenta con hover ────────────────────────────────
        manage_btn = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.MANAGE_ACCOUNTS_ROUNDED, size=13, color=TEXT_DIM),
                ft.Container(width=6),
                ft.Text("Gestionar cuentas", color=TEXT_SEC, size=10),
                ft.Container(expand=True),
                ft.Icon(ft.icons.CHEVRON_RIGHT_ROUNDED, size=14, color=TEXT_DIM),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.symmetric(horizontal=18, vertical=10),
            border_radius=0,
            animate=ft.animation.Animation(150, ft.AnimationCurve.EASE_OUT),
            on_click=lambda e: self.app._show_view("accounts"),
        )
        manage_btn.on_hover = lambda e, c=manage_btn: (
            setattr(c, "bgcolor", CARD2_BG if e.data == "true" else "transparent")
            or c.update()
        )

        # ── Card de cuenta con gradiente sutil ────────────────────────────
        account_card = ft.Container(
            padding=ft.padding.all(18),
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left,
                end=ft.alignment.bottom_right,
                colors=[SIDEBAR_BG, CARD2_BG],
            ),
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        width=3, height=14,
                        bgcolor=GREEN, border_radius=2,
                        shadow=[ft.BoxShadow(
                            spread_radius=0, blur_radius=8,
                            color=ft.colors.with_opacity(0.6, GREEN),
                            offset=ft.Offset(0, 0),
                        )],
                    ),
                    ft.Container(width=8),
                    ft.Text("JUGANDO COMO", color=TEXT_DIM, size=8,
                            weight=ft.FontWeight.BOLD),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=14),
                ft.Row([
                    self._avatar_glow,
                    ft.Container(width=14),
                    ft.Column([
                        self._username_lbl,
                        ft.Container(height=4),
                        ft.Row([
                            self._status_dot,
                            ft.Container(width=6),
                            self._mode_lbl,
                            ft.Container(width=8),
                            self._account_badge,
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ], spacing=0, expand=True),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=0),
        )

        # ── News header ───────────────────────────────────────────────────
        self._news_count_badge = ft.Container(
            content=ft.Text("…", size=8, color=TEXT_DIM,
                            weight=ft.FontWeight.W_600),
            padding=ft.padding.symmetric(horizontal=7, vertical=3),
            bgcolor=INPUT_BG,
            border_radius=10,
            border=ft.border.all(1, BORDER),
        )
        news_header = ft.Container(
            padding=ft.padding.only(left=18, right=18, top=14, bottom=10),
            content=ft.Row([
                ft.Container(
                    width=3, height=14,
                    bgcolor="#4dabf7", border_radius=2,
                    shadow=[ft.BoxShadow(
                        spread_radius=0, blur_radius=8,
                        color=ft.colors.with_opacity(0.5, "#4dabf7"),
                        offset=ft.Offset(0, 0),
                    )],
                ),
                ft.Container(width=8),
                ft.Text("NOTICIAS", color=TEXT_DIM, size=8,
                        weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                self._news_count_badge,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        # ── Loading skeleton ──────────────────────────────────────────────
        self._news_col = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        self._news_col.controls.append(self._build_skeleton())

        self._normal_col = ft.Column([
            account_card,
            manage_btn,
            ft.Divider(height=1, color=BORDER, thickness=1),
            news_header,
            ft.Container(content=self._news_col, expand=True),
        ], spacing=0, expand=True)

    # ── Skeleton loader ───────────────────────────────────────────────────────
    def _build_skeleton(self) -> ft.Column:
        def _skel(w: int, h: int, radius: int = 4) -> ft.Container:
            return ft.Container(
                width=w, height=h, border_radius=radius,
                bgcolor=CARD2_BG,
                animate_opacity=ft.animation.Animation(800, ft.AnimationCurve.EASE_IN_OUT),
            )

        items = []
        for _ in range(5):
            items.append(ft.Container(
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                content=ft.Row([
                    _skel(36, 36, 8),
                    ft.Container(width=10),
                    ft.Column([
                        _skel(120, 8),
                        ft.Container(height=6),
                        _skel(80, 8),
                        ft.Container(height=5),
                        _skel(160, 7),
                    ], spacing=0),
                ], vertical_alignment=ft.CrossAxisAlignment.START),
            ))
            items.append(ft.Divider(height=1, color=BORDER))
        return ft.Column(items, spacing=0)

    # ═══════════════════════════════════════════════════════════════════════
    #  DISCOVER MODE (sin cambios)
    # ═══════════════════════════════════════════════════════════════════════
    def set_discover_mode(self, active: bool, profile=None,
                          tab_type: str = "mod", on_change=None):
        self._discover_mode    = active
        self._on_filter_change = on_change
        self._discover_profile = profile
        self._selected_cats.clear()
        self._excluded_cats.clear()
        self._hide_installed  = False
        self._discover_loader = None

        if active:
            self._discover_tab_type = tab_type
            col = self._build_discover_col(profile, tab_type)
            self._set_swap(col)
        else:
            self._set_swap(self._normal_col)

    def update_tab_filters(self, tab_type: str):
        if not self._discover_mode:
            return
        self._discover_tab_type = tab_type
        self._selected_cats.clear()
        if not hasattr(self, "_cat_col"):
            return
        self._rebuild_cat_section()

    def get_discover_filters(self) -> dict:
        loader = self._discover_loader
        if loader is None:
            loader = self._detect_loader_from_profile(self._discover_profile)
        return {
            "categories":     sorted(self._selected_cats),
            "excluded_cats":  sorted(self._excluded_cats),
            "hide_installed": self._hide_installed,
            "loader":         loader,
        }

    def _build_discover_col(self, profile, tab_type: str) -> ft.Column:
        mc_ver      = getattr(profile, "version_id", None) if profile else None
        auto_loader = self._detect_loader_from_profile(profile)
        self._discover_loader = auto_loader
        ver_display    = mc_ver or "—"
        loader_display = auto_loader.capitalize() if auto_loader else "—"

        prof_name = getattr(profile, "name", None) if profile else None
        if prof_name:
            profile_banner = ft.Container(
                padding=ft.padding.symmetric(horizontal=18, vertical=14),
                bgcolor=CARD2_BG,
                border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
                content=ft.Row([
                    ft.Container(
                        width=36, height=36, border_radius=8,
                        bgcolor=INPUT_BG, alignment=ft.alignment.center,
                        content=ft.Icon(ft.icons.WIDGETS_ROUNDED,
                                        size=18, color=TEXT_SEC),
                    ),
                    ft.Container(width=12),
                    ft.Column([
                        ft.Text(prof_name, color=TEXT_PRI, size=12,
                                weight=ft.FontWeight.BOLD),
                        ft.Row([
                            ft.Container(
                                bgcolor=INPUT_BG, border_radius=4,
                                padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                content=ft.Text(ver_display, color=TEXT_SEC,
                                                size=9, weight=ft.FontWeight.W_500),
                            ),
                            ft.Container(width=4),
                            ft.Container(
                                bgcolor=INPUT_BG, border_radius=4,
                                padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                content=ft.Text(loader_display, color=TEXT_SEC,
                                                size=9, weight=ft.FontWeight.W_500),
                            ),
                        ], spacing=0),
                    ], spacing=4, expand=True),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )
        else:
            profile_banner = ft.Container(height=0)

        self._hide_toggle_dot = ft.Container(
            width=16, height=16, border_radius=8,
            bgcolor=CARD2_BG,
            border=ft.border.all(1.5, BORDER_BRIGHT),
            animate=ft.animation.Animation(150, ft.AnimationCurve.EASE_OUT),
        )
        self._hide_toggle_lbl = ft.Text("Hide installed", color=TEXT_SEC, size=11)
        hide_row = ft.Container(
            padding=ft.padding.symmetric(horizontal=18, vertical=12),
            on_click=self._toggle_hide_installed,
            content=ft.Row([
                ft.Icon(ft.icons.VISIBILITY_OFF_OUTLINED, size=15, color=TEXT_DIM),
                ft.Container(width=10),
                self._hide_toggle_lbl,
                ft.Container(expand=True),
                self._hide_toggle_dot,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )
        hide_row.on_hover = lambda e, c=hide_row: (
            setattr(c, "bgcolor", CARD2_BG if e.data == "true" else "transparent")
            or c.update()
        )

        self._ver_body = ft.Container(
            visible=self._ver_expanded,
            padding=ft.padding.only(left=18, right=18, bottom=14),
            content=ft.Container(
                bgcolor=INPUT_BG, border=ft.border.all(1, BORDER),
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                content=ft.Row([
                    ft.Icon(ft.icons.VIDEOGAME_ASSET_ROUNDED, size=14, color=TEXT_DIM),
                    ft.Container(width=10),
                    ft.Text(ver_display, color=TEXT_PRI, size=12,
                            weight=ft.FontWeight.W_500),
                    ft.Container(expand=True),
                    ft.Container(
                        bgcolor=CARD2_BG, border_radius=4,
                        padding=ft.padding.symmetric(horizontal=6, vertical=2),
                        content=ft.Text("locked", color=TEXT_DIM, size=8),
                    ),
                ], spacing=0),
            ),
        )
        self._ver_arrow = ft.Icon(
            ft.icons.KEYBOARD_ARROW_UP_ROUNDED if self._ver_expanded
            else ft.icons.KEYBOARD_ARROW_DOWN_ROUNDED,
            size=16, color=TEXT_DIM,
        )
        ver_hdr = self._section_header(
            "Game Version", ft.icons.SPORTS_ESPORTS_ROUNDED,
            self._ver_arrow, self._toggle_ver)
        self._ver_section = ft.Column([ver_hdr, self._ver_body], spacing=0)

        self._loader_body = ft.Column(spacing=1, visible=self._loader_expanded)
        self._rebuild_loader_section(profile)
        self._loader_body_container = ft.Container(
            padding=ft.padding.only(left=18, right=18, bottom=12),
            content=self._loader_body,
            visible=self._loader_expanded,
        )
        self._loader_arrow = ft.Icon(
            ft.icons.KEYBOARD_ARROW_UP_ROUNDED if self._loader_expanded
            else ft.icons.KEYBOARD_ARROW_DOWN_ROUNDED,
            size=16, color=TEXT_DIM,
        )
        loader_hdr = self._section_header(
            "Loader", ft.icons.EXTENSION_ROUNDED,
            self._loader_arrow, self._toggle_loader)
        self._loader_section = ft.Column([loader_hdr, self._loader_body_container], spacing=0)

        self._cat_col = ft.Column(spacing=1)
        self._cat_body_container = ft.Container(
            padding=ft.padding.only(left=18, right=18, bottom=14),
            content=self._cat_col,
            visible=self._cat_expanded,
        )
        self._cat_arrow = ft.Icon(
            ft.icons.KEYBOARD_ARROW_UP_ROUNDED if self._cat_expanded
            else ft.icons.KEYBOARD_ARROW_DOWN_ROUNDED,
            size=16, color=TEXT_DIM,
        )
        cat_hdr = self._section_header(
            "Category", ft.icons.CATEGORY_ROUNDED,
            self._cat_arrow, self._toggle_cat)
        self._cat_section = ft.Column([cat_hdr, self._cat_body_container], spacing=0)
        self._rebuild_cat_section()

        return ft.Column([
            profile_banner, hide_row,
            ft.Divider(height=1, color=BORDER),
            ft.Column([
                self._ver_section,
                ft.Divider(height=1, color=BORDER),
                self._loader_section,
                ft.Divider(height=1, color=BORDER),
                self._cat_section,
            ], spacing=0, scroll=ft.ScrollMode.AUTO, expand=True),
        ], spacing=0, expand=True)

    def _section_header(self, title, icon, arrow_ctrl, on_toggle) -> ft.Container:
        hdr = ft.Container(
            padding=ft.padding.symmetric(horizontal=18, vertical=12),
            on_click=on_toggle,
            content=ft.Row([
                ft.Icon(icon, size=15, color=TEXT_SEC),
                ft.Container(width=10),
                ft.Text(title, color=TEXT_PRI, size=12,
                        weight=ft.FontWeight.BOLD, expand=True),
                arrow_ctrl,
            ]),
        )
        hdr.on_hover = lambda e, h=hdr: (
            setattr(h, "bgcolor", CARD2_BG if e.data == "true" else "transparent")
            or h.update()
        )
        return hdr

    def _toggle_hide_installed(self, e):
        self._hide_installed = not self._hide_installed
        if self._hide_installed:
            self._hide_toggle_dot.bgcolor = GREEN
            self._hide_toggle_dot.border  = ft.border.all(1.5, GREEN)
            self._hide_toggle_lbl.color   = TEXT_PRI
        else:
            self._hide_toggle_dot.bgcolor = CARD2_BG
            self._hide_toggle_dot.border  = ft.border.all(1.5, BORDER_BRIGHT)
            self._hide_toggle_lbl.color   = TEXT_SEC
        try:
            self._hide_toggle_dot.update()
            self._hide_toggle_lbl.update()
        except Exception:
            pass
        if callable(self._on_filter_change):
            self._on_filter_change()

    def _detect_loader_from_profile(self, profile) -> str | None:
        if not profile:
            return None
        meta_path = os.path.join(
            getattr(profile, "game_dir", ""), "loader_meta.json")
        if os.path.isfile(meta_path):
            try:
                import json as _json
                with open(meta_path) as f:
                    meta = _json.load(f)
                entries = meta if isinstance(meta, list) else [meta]
                if entries:
                    return entries[0].get("loader_type")
            except Exception:
                pass
        return None

    def _rebuild_loader_section(self, profile):
        auto_loader = self._detect_loader_from_profile(profile)
        self._loader_body.controls.clear()
        options = [("(auto)", None)] + [(l, l) for l in LOADERS]
        for opt_label, opt_value in options:
            if opt_value is None:
                display = (f"Auto  ·  {auto_loader.capitalize()}"
                           if auto_loader and auto_loader != "vanilla" else "Auto")
                is_sel  = self._discover_loader is None
                ico     = ft.icons.TUNE_ROUNDED
                ico_col = GREEN if is_sel else TEXT_DIM
            else:
                display = opt_value.capitalize()
                is_sel  = self._discover_loader == opt_value
                ico     = _LOADER_ICONS.get(opt_value, ft.icons.EXTENSION_ROUNDED)
                ico_col = (_LOADER_COLORS.get(opt_value, TEXT_SEC)
                           if is_sel else TEXT_DIM)
            dot = ft.Container(
                width=8, height=8, border_radius=4,
                bgcolor=GREEN if is_sel else "transparent",
                border=ft.border.all(1.5, GREEN if is_sel else BORDER_BRIGHT),
                animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
            )
            lbl = ft.Text(display, color=TEXT_PRI if is_sel else TEXT_SEC, size=11,
                          weight=ft.FontWeight.W_500 if is_sel else ft.FontWeight.W_400)
            row = ft.Container(
                padding=ft.padding.symmetric(horizontal=10, vertical=8),
                border_radius=7,
                content=ft.Row([
                    ft.Icon(ico, size=14, color=ico_col),
                    ft.Container(width=10), lbl,
                    ft.Container(expand=True), dot,
                ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )
            v = opt_value
            row.on_click = lambda e, val=v: self._on_loader_click(val)
            row.on_hover = lambda e, r=row: (
                setattr(r, "bgcolor", INPUT_BG if e.data == "true" else "transparent")
                or r.update()
            )
            self._loader_body.controls.append(row)

    def _on_loader_click(self, value):
        self._discover_loader = value
        self._rebuild_loader_section(self._discover_profile)
        try:
            self._loader_body.update()
        except Exception:
            pass
        if callable(self._on_filter_change):
            self._on_filter_change()

    def _rebuild_cat_section(self):
        if not hasattr(self, "_cat_col"):
            return
        cats = CATEGORIES_BY_TYPE.get(self._discover_tab_type, [])
        self._cat_col.controls.clear()
        for cat in cats:
            self._cat_col.controls.append(self._make_cat_row(cat))
        try:
            self._cat_col.update()
        except Exception:
            pass

    def _make_cat_row(self, cat: str) -> ft.Container:
        is_sel  = cat in self._selected_cats
        is_excl = cat in self._excluded_cats
        ico     = _CAT_ICONS.get(cat, ft.icons.LABEL_ROUNDED)
        check     = ft.Icon(ft.icons.CHECK_ROUNDED, size=14, color=GREEN, visible=is_sel)
        block_icon = ft.Icon(ft.icons.BLOCK_ROUNDED, size=14, color="#e05555")
        block_btn = ft.Container(
            width=22, height=22, border_radius=11,
            bgcolor=ft.colors.with_opacity(0.15, "#e05555") if is_excl else "transparent",
            alignment=ft.alignment.center, visible=is_excl, content=block_icon,
        )
        ico_ctrl = ft.Icon(ico, size=14,
                           color=GREEN if is_sel else (TEXT_DIM if not is_excl else "#e05555"))
        lbl = ft.Text(cat,
                      color=TEXT_PRI if is_sel else (TEXT_SEC if not is_excl else "#e05555"),
                      size=11,
                      weight=ft.FontWeight.W_600 if is_sel else ft.FontWeight.W_400)
        row = ft.Container(
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            border_radius=7,
            bgcolor=(ft.colors.with_opacity(0.06, GREEN) if is_sel else
                     ft.colors.with_opacity(0.06, "#e05555") if is_excl else "transparent"),
            animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
            content=ft.Row([
                ico_ctrl, ft.Container(width=10), lbl,
                ft.Container(expand=True),
                check, ft.Container(width=4), block_btn,
            ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        def _refresh_ui(sel, excl):
            check.visible     = sel
            block_btn.visible = excl
            block_btn.bgcolor = (ft.colors.with_opacity(0.15, "#e05555") if excl else "transparent")
            ico_ctrl.color    = GREEN if sel else ("#e05555" if excl else TEXT_DIM)
            lbl.color         = TEXT_PRI if sel else ("#e05555" if excl else TEXT_SEC)
            lbl.weight        = ft.FontWeight.W_600 if sel else ft.FontWeight.W_400
            row.bgcolor       = (ft.colors.with_opacity(0.06, GREEN) if sel else
                                 ft.colors.with_opacity(0.06, "#e05555") if excl else "transparent")
            try:
                check.update(); block_btn.update(); ico_ctrl.update(); lbl.update(); row.update()
            except Exception:
                pass

        def _click(e, c=cat):
            excl = c in self._excluded_cats
            sel  = c in self._selected_cats
            if excl:
                self._excluded_cats.discard(c); _refresh_ui(False, False)
            elif sel:
                self._selected_cats.discard(c); _refresh_ui(False, False)
            else:
                self._selected_cats.add(c); _refresh_ui(True, False)
            if callable(self._on_filter_change):
                self._on_filter_change()

        def _block_click(e, c=cat):
            excl = c in self._excluded_cats
            if excl:
                self._excluded_cats.discard(c); _refresh_ui(False, False)
            else:
                self._selected_cats.discard(c)
                self._excluded_cats.add(c); _refresh_ui(False, True)
            if callable(self._on_filter_change):
                self._on_filter_change()

        def _hover(e, c=cat):
            sel  = c in self._selected_cats
            excl = c in self._excluded_cats
            if e.data == "true":
                block_btn.visible = True
                row.bgcolor = (ft.colors.with_opacity(0.10, GREEN) if sel else
                               ft.colors.with_opacity(0.10, "#e05555") if excl else INPUT_BG)
            else:
                block_btn.visible = excl
                row.bgcolor = (ft.colors.with_opacity(0.06, GREEN) if sel else
                               ft.colors.with_opacity(0.06, "#e05555") if excl else "transparent")
            try:
                block_btn.update(); row.update()
            except Exception:
                pass

        block_btn.on_click = _block_click
        row.on_click = _click
        row.on_hover = _hover
        return row

    def _toggle_ver(self, e):
        self._ver_expanded = not self._ver_expanded
        self._ver_body.visible = self._ver_expanded
        self._ver_arrow.name = (ft.icons.KEYBOARD_ARROW_UP_ROUNDED
                                if self._ver_expanded
                                else ft.icons.KEYBOARD_ARROW_DOWN_ROUNDED)
        try:
            self._ver_body.update(); self._ver_arrow.update()
        except Exception:
            pass

    def _toggle_loader(self, e):
        self._loader_expanded = not self._loader_expanded
        self._loader_body_container.visible = self._loader_expanded
        self._loader_arrow.name = (ft.icons.KEYBOARD_ARROW_UP_ROUNDED
                                   if self._loader_expanded
                                   else ft.icons.KEYBOARD_ARROW_DOWN_ROUNDED)
        try:
            self._loader_body_container.update(); self._loader_arrow.update()
        except Exception:
            pass

    def _toggle_cat(self, e):
        self._cat_expanded = not self._cat_expanded
        self._cat_body_container.visible = self._cat_expanded
        self._cat_arrow.name = (ft.icons.KEYBOARD_ARROW_UP_ROUNDED
                                if self._cat_expanded
                                else ft.icons.KEYBOARD_ARROW_DOWN_ROUNDED)
        try:
            self._cat_body_container.update(); self._cat_arrow.update()
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    #  CUENTA — refresh
    # ═══════════════════════════════════════════════════════════════════════
    def refresh_account(self):
        try:
            acc = self.app.account_manager.get_active_account()
            if not acc:
                all_acc = self.app.account_manager.get_all_accounts()
                acc     = all_acc[0] if all_acc else None
        except Exception:
            acc = None

        if acc:
            name     = acc.username
            is_ms    = getattr(acc, "is_microsoft", False)
            mode_txt = "Microsoft"  if is_ms else "Offline"
            dot_col  = GREEN        if is_ms else "#ffa94d"
            badge_lbl = "MICROSOFT" if is_ms else "OFFLINE"
            badge_col = GREEN       if is_ms else "#ffa94d"
            glow_col  = GREEN       if is_ms else "#ffa94d"
        else:
            name      = "Sin cuenta"
            mode_txt  = "Offline"
            dot_col   = TEXT_DIM
            badge_lbl = "OFFLINE"
            badge_col = TEXT_DIM
            glow_col  = TEXT_DIM

        color    = AVATAR_PALETTE[abs(hash(name)) % len(AVATAR_PALETTE)]
        initials = (name[:2] if len(name) >= 2 else name).upper()

        self._username_lbl.value     = name
        self._mode_lbl.value         = mode_txt
        self._avatar_initials.value  = initials
        self._avatar_inner.bgcolor   = color

        # Actualizar dot + glow
        self._status_dot.bgcolor = dot_col
        self._status_dot.shadow  = [ft.BoxShadow(
            spread_radius=0, blur_radius=8,
            color=ft.colors.with_opacity(0.7, dot_col),
            offset=ft.Offset(0, 0),
        )]

        # Actualizar glow del avatar
        self._avatar_glow.border = ft.border.all(
            2, ft.colors.with_opacity(0.5, glow_col))
        self._avatar_glow.shadow = [ft.BoxShadow(
            spread_radius=0, blur_radius=16,
            color=ft.colors.with_opacity(0.35, glow_col),
            offset=ft.Offset(0, 0),
        )]

        # Badge
        self._account_badge.content = ft.Text(
            badge_lbl, size=8, color=badge_col, weight=ft.FontWeight.W_700)
        self._account_badge.border = ft.border.all(
            1, ft.colors.with_opacity(0.3, badge_col))
        self._account_badge.bgcolor = ft.colors.with_opacity(0.1, badge_col)

        try:
            self._username_lbl.update()
            self._mode_lbl.update()
            self._avatar_initials.update()
            self._avatar_inner.update()
            self._status_dot.update()
            self._avatar_glow.update()
            self._account_badge.update()
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    #  NOTICIAS — fetch + render
    # ═══════════════════════════════════════════════════════════════════════
    def _fetch_news(self):
        items = []

        # ── Mojang version manifest ───────────────────────────────────────
        try:
            req = urllib.request.Request(
                "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json",
                headers={"User-Agent": "PyLauncher/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode())

            latest_r = data["latest"]["release"]
            latest_s = data["latest"]["snapshot"]
            items.append({
                "kind":   "latest",
                "title":  f"Minecraft {latest_r}",
                "body":   f"Último snapshot: {latest_s}",
                "date":   "",
                "source": "Mojang",
                "image":  None,
                "url":    None,
                "mc_ver": latest_r,
            })

            type_map = {
                "release":   "release",
                "snapshot":  "snapshot",
                "old_beta":  "old_beta",
                "old_alpha": "old_alpha",
            }
            for v in data["versions"][:6]:
                kind = type_map.get(v["type"], "snapshot")
                items.append({
                    "kind":   kind,
                    "title":  f"Minecraft {v['id']}",
                    "body":   None,
                    "date":   v.get("releaseTime", "")[:10],
                    "source": "Mojang",
                    "image":  None,
                    "url":    None,
                    "mc_ver": v["id"],
                })
        except Exception as ex:
            log.warning(f"News Mojang: {ex}")

        # ── Modrinth mods recientes ───────────────────────────────────────
        try:
            for project_type, kind in [("mod", "mod"), ("modpack", "modpack")]:
                url = (
                    f"https://api.modrinth.com/v2/search"
                    f"?limit=5&index=updated"
                    f'&facets=[[%22project_type:{project_type}%22]]'
                )
                req2 = urllib.request.Request(url, headers={"User-Agent": "PyLauncher/1.0"})
                with urllib.request.urlopen(req2, timeout=10) as r:
                    mdata = json.loads(r.read().decode())
                for hit in mdata.get("hits", []):
                    desc = hit.get("description", "")
                    # Descarga imagen en background
                    icon_url = hit.get("icon_url") or ""
                    cached   = _cached_src(icon_url) if icon_url else None
                    items.append({
                        "kind":   kind,
                        "title":  hit.get("title", "?"),
                        "body":   (desc[:70] + "…") if len(desc) > 70 else desc,
                        "date":   (hit.get("date_modified") or "")[:10],
                        "source": "Modrinth",
                        "image":  cached,
                        "url":    f"https://modrinth.com/{project_type}/{hit.get('slug', '')}",
                        "mc_ver": None,
                        "downloads": hit.get("downloads", 0),
                    })
        except Exception as ex:
            log.warning(f"News Modrinth: {ex}")

        self.app.page.run_thread(lambda: self._render_news(items))

    def _render_news(self, items: list):
        self._news_col.controls.clear()
        if not items:
            self._news_col.controls.append(
                ft.Container(
                    padding=ft.padding.all(18),
                    content=ft.Column([
                        ft.Icon(ft.icons.WIFI_OFF_ROUNDED, color=TEXT_DIM, size=28),
                        ft.Container(height=8),
                        ft.Text("Sin conexión", color=TEXT_DIM, size=11,
                                text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                )
            )
            self._update_news_count(0)
            return

        self._update_news_count(len(items))
        for i, item in enumerate(items):
            if i > 0:
                self._news_col.controls.append(
                    ft.Divider(height=1, color=BORDER, thickness=1))
            self._news_col.controls.append(self._make_news_card(item))

        try:
            self._news_col.update()
        except Exception:
            pass

    def _update_news_count(self, count: int):
        self._news_count_badge.content = ft.Text(
            str(count), size=8, color=TEXT_SEC, weight=ft.FontWeight.W_600)
        try:
            self._news_count_badge.update()
        except Exception:
            pass

    # ── News card ─────────────────────────────────────────────────────────────
    def _make_news_card(self, item: dict) -> ft.Container:
        kind    = item.get("kind", "release")
        style   = _NEWS_TYPE_STYLE.get(kind, _NEWS_TYPE_STYLE["release"])
        color   = style["color"]
        icon    = style["icon"]
        bg_tint = style["bg"]
        label   = style["label"]
        has_url = bool(item.get("url"))

        # ── Thumbnail / icon ──────────────────────────────────────────────
        img_src = item.get("image")
        if img_src:
            thumb: ft.Control = ft.Container(
                width=38, height=38, border_radius=9,
                clip_behavior=ft.ClipBehavior.HARD_EDGE,
                shadow=[ft.BoxShadow(
                    spread_radius=0, blur_radius=8,
                    color=ft.colors.with_opacity(0.3, color),
                    offset=ft.Offset(0, 2),
                )],
                content=ft.Image(
                    src=img_src, width=38, height=38,
                    fit=ft.ImageFit.COVER,
                    error_content=self._icon_fallback(icon, color, bg_tint),
                ),
            )
        else:
            thumb = self._icon_fallback(icon, color, bg_tint, size=38)

        # ── Badge tipo ────────────────────────────────────────────────────
        badge = ft.Container(
            content=ft.Text(label, size=8, color=color, weight=ft.FontWeight.W_700),
            padding=ft.padding.symmetric(horizontal=6, vertical=2),
            bgcolor=ft.colors.with_opacity(0.15, color),
            border_radius=4,
            border=ft.border.all(1, ft.colors.with_opacity(0.3, color)),
        )

        # ── Date / source ─────────────────────────────────────────────────
        meta_parts: list[ft.Control] = []
        if item.get("source"):
            meta_parts.append(ft.Text(item["source"], color=TEXT_DIM, size=8))
        if item.get("date"):
            if meta_parts:
                meta_parts.append(ft.Text("·", color=TEXT_DIM, size=8))
            meta_parts.append(ft.Text(item["date"], color=TEXT_DIM, size=8))
        if item.get("downloads"):
            def _fmt(n):
                if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
                if n >= 1_000: return f"{n/1_000:.1f}K"
                return str(n)
            if meta_parts:
                meta_parts.append(ft.Text("·", color=TEXT_DIM, size=8))
            meta_parts.append(ft.Icon(ft.icons.DOWNLOAD_OUTLINED,
                                      size=10, color=TEXT_DIM))
            meta_parts.append(ft.Text(_fmt(item["downloads"]), color=TEXT_DIM, size=8))

        meta_row = ft.Row(meta_parts, spacing=4,
                          vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # ── Card body ─────────────────────────────────────────────────────
        card = ft.Container(
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            border_radius=0,
            animate=ft.animation.Animation(180, ft.AnimationCurve.EASE_OUT),
            on_click=(
                lambda e, u=item["url"]: __import__("webbrowser").open(u)
            ) if has_url else None,
            content=ft.Row([
                thumb,
                ft.Container(width=10),
                ft.Column([
                    ft.Row([
                        badge,
                        ft.Container(expand=True),
                        meta_row,
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(height=4),
                    ft.Text(
                        item.get("title", ""),
                        color=TEXT_PRI, size=11,
                        weight=ft.FontWeight.BOLD,
                        overflow=ft.TextOverflow.ELLIPSIS, max_lines=2,
                    ),
                    *(
                        [ft.Text(
                            item["body"], color=TEXT_SEC, size=9,
                            overflow=ft.TextOverflow.ELLIPSIS, max_lines=2,
                        )]
                        if item.get("body") else []
                    ),
                ], spacing=0, expand=True),
            ], vertical_alignment=ft.CrossAxisAlignment.START),
        )

        # Hover: fondo tintado + glow borde izquierdo
        def _hover(e, c=card, col=color, bg=bg_tint):
            if e.data == "true":
                c.bgcolor = ft.colors.with_opacity(0.06, col)
                c.border  = ft.border.only(
                    left=ft.BorderSide(2, ft.colors.with_opacity(0.7, col)))
            else:
                c.bgcolor = "transparent"
                c.border  = None
            try:
                c.update()
            except Exception:
                pass

        card.on_hover = _hover
        return card

    @staticmethod
    def _icon_fallback(icon, color: str, bg: str,
                       size: int = 38) -> ft.Container:
        """Fallback cuadrado con gradiente + ícono centrado."""
        return ft.Container(
            width=size, height=size, border_radius=9,
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left,
                end=ft.alignment.bottom_right,
                colors=[bg, ft.colors.with_opacity(0.6, bg)],
            ),
            border=ft.border.all(1, ft.colors.with_opacity(0.2, color)),
            shadow=[ft.BoxShadow(
                spread_radius=0, blur_radius=6,
                color=ft.colors.with_opacity(0.2, color),
                offset=ft.Offset(0, 2),
            )],
            content=ft.Icon(icon, color=ft.colors.with_opacity(0.8, color),
                            size=size // 2 - 1),
            alignment=ft.alignment.center,
        )