# -*- coding: utf-8 -*-
"""
gui/sidebar_right.py
Dos modos:
  • Normal  — cuenta activa + feed de noticias
  • Discover — panel de filtros elegante con iconos por categoría
"""
import threading
import urllib.request
import json
import flet as ft

from gui.theme import (
    SIDEBAR_BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER, BORDER_BRIGHT,
    GREEN, GREEN_DIM, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV,
    AVATAR_PALETTE,
)
from utils.logger import get_logger

log = get_logger()

# ── Categorías con iconos por tipo de proyecto ────────────────────────────────
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
    "Semi-realistic":  ft.icons.NATURE_ROUNDED,
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


class SidebarRight:
    def __init__(self, app):
        self.app  = app
        self.page = app.page

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
    #  NORMAL MODE
    # ═══════════════════════════════════════════════════════════════════════
    def _build_normal_content(self):
        self._avatar_text = ft.Text("??", color=TEXT_INV, size=13,
                                    weight=ft.FontWeight.BOLD)
        self._avatar_box  = ft.Container(
            width=42, height=42, border_radius=21,
            bgcolor=GREEN, alignment=ft.alignment.center,
            content=self._avatar_text,
        )
        self._username_lbl = ft.Text("—", color=TEXT_PRI, size=11,
                                     weight=ft.FontWeight.BOLD)
        self._dot      = ft.Container(width=7, height=7, border_radius=4,
                                      bgcolor=TEXT_DIM)
        self._mode_lbl = ft.Text("Sin cuenta", color=TEXT_DIM, size=9)

        account_section = ft.Container(
            padding=ft.padding.all(18),
            content=ft.Column([
                ft.Text("JUGANDO COMO", color=TEXT_DIM, size=8,
                        weight=ft.FontWeight.BOLD,
                        letter_spacing=1.2),
                ft.Container(height=12),
                ft.Row([
                    self._avatar_box,
                    ft.Container(width=12),
                    ft.Column([
                        self._username_lbl,
                        ft.Row([
                            self._dot,
                            ft.Container(width=5),
                            self._mode_lbl,
                        ], spacing=0),
                    ], spacing=3, expand=True),
                ]),
                ft.Container(height=8),
                ft.TextButton(
                    "Gestionar cuentas →",
                    style=ft.ButtonStyle(
                        color=TEXT_SEC,
                        overlay_color=ft.colors.with_opacity(0.08, GREEN),
                    ),
                    on_click=lambda e: self.app._show_view("accounts"),
                ),
            ], spacing=0),
        )

        self._news_count_lbl = ft.Text("cargando…", color=TEXT_DIM, size=7)
        self._news_col = ft.Column(
            spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        self._news_col.controls.append(
            ft.Container(
                padding=ft.padding.all(14),
                content=ft.Text("Conectando…", color=TEXT_DIM, size=9),
            )
        )

        self._normal_col = ft.Column([
            account_section,
            ft.Divider(height=1, color=BORDER),
            ft.Column([
                ft.Container(
                    padding=ft.padding.only(left=18, right=18, top=14, bottom=8),
                    content=ft.Row([
                        ft.Text("NOTICIAS", color=TEXT_DIM, size=8,
                                weight=ft.FontWeight.BOLD, letter_spacing=1.2),
                        ft.Container(expand=True),
                        self._news_count_lbl,
                    ]),
                ),
                ft.Container(expand=True, content=self._news_col),
            ], spacing=0, expand=True),
        ], spacing=0, expand=True)

    # ═══════════════════════════════════════════════════════════════════════
    #  DISCOVER MODE
    # ═══════════════════════════════════════════════════════════════════════
    def set_discover_mode(self, active: bool, profile=None,
                          tab_type: str = "mod", on_change=None):
        self._discover_mode    = active
        self._on_filter_change = on_change
        self._discover_profile = profile
        self._selected_cats.clear()
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
        return {
            "categories":     sorted(self._selected_cats),
            "hide_installed": self._hide_installed,
            "loader":         self._discover_loader,
        }

    # ── Build discover panel ──────────────────────────────────────────────────
    def _build_discover_col(self, profile, tab_type: str) -> ft.Column:
        # Detect version and loader from profile
        mc_ver     = getattr(profile, "version_id", None) if profile else None
        auto_loader = self._detect_loader_from_profile(profile)
        self._discover_loader = auto_loader

        ver_display = mc_ver or "—"
        loader_display = auto_loader.capitalize() if auto_loader else "—"

        # ── Profile info banner ───────────────────────────────────────────
        prof_name = getattr(profile, "name", None) if profile else None
        if prof_name:
            profile_banner = ft.Container(
                padding=ft.padding.symmetric(horizontal=18, vertical=14),
                bgcolor=CARD2_BG,
                border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
                content=ft.Row([
                    ft.Container(
                        width=36, height=36, border_radius=8,
                        bgcolor=INPUT_BG,
                        alignment=ft.alignment.center,
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

        # ── Hide installed toggle ─────────────────────────────────────────
        self._hide_toggle_dot = ft.Container(
            width=16, height=16, border_radius=8,
            bgcolor=CARD2_BG,
            border=ft.border.all(1.5, BORDER_BRIGHT),
            animate=ft.animation.Animation(150, ft.AnimationCurve.EASE_OUT),
        )
        self._hide_toggle_lbl = ft.Text(
            "Hide installed", color=TEXT_SEC, size=11)

        hide_row = ft.Container(
            padding=ft.padding.symmetric(horizontal=18, vertical=12),
            border_radius=0,
            on_click=self._toggle_hide_installed,
            content=ft.Row([
                ft.Icon(ft.icons.VISIBILITY_OFF_OUTLINED,
                        size=15, color=TEXT_DIM),
                ft.Container(width=10),
                self._hide_toggle_lbl,
                ft.Container(expand=True),
                self._hide_toggle_dot,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )
        hide_row.on_hover = lambda e, c=hide_row: (
            setattr(c, "bgcolor",
                    CARD2_BG if e.data == "true" else "transparent")
            or c.update()
        )

        # ── Game version section ──────────────────────────────────────────
        self._ver_body = ft.Container(
            visible=self._ver_expanded,
            padding=ft.padding.only(left=18, right=18, bottom=14),
            content=ft.Container(
                bgcolor=INPUT_BG,
                border=ft.border.all(1, BORDER),
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                content=ft.Row([
                    ft.Icon(ft.icons.VIDEOGAME_ASSET_ROUNDED,
                            size=14, color=TEXT_DIM),
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

        # ── Loader section ────────────────────────────────────────────────
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
        self._loader_section = ft.Column([
            loader_hdr, self._loader_body_container], spacing=0)

        # ── Category section ──────────────────────────────────────────────
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
        self._cat_section = ft.Column([
            cat_hdr, self._cat_body_container], spacing=0)
        self._rebuild_cat_section()

        return ft.Column([
            profile_banner,
            hide_row,
            ft.Divider(height=1, color=BORDER),
            ft.Column([
                self._ver_section,
                ft.Divider(height=1, color=BORDER),
                self._loader_section,
                ft.Divider(height=1, color=BORDER),
                self._cat_section,
            ], spacing=0, scroll=ft.ScrollMode.AUTO, expand=True),
        ], spacing=0, expand=True)

    # ── Section header ────────────────────────────────────────────────────────
    def _section_header(self, title: str, icon, arrow_ctrl,
                        on_toggle) -> ft.Container:
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
            setattr(h, "bgcolor",
                    CARD2_BG if e.data == "true" else "transparent")
            or h.update()
        )
        return hdr

    # ── Hide installed toggle ─────────────────────────────────────────────────
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
        self._fire_filter_change()

    # ── Loader section ────────────────────────────────────────────────────────
    def _detect_loader_from_profile(self, profile) -> str | None:
        if not profile:
            return None
        import os
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
                           if auto_loader else "Auto")
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
            lbl = ft.Text(
                display,
                color=TEXT_PRI if is_sel else TEXT_SEC,
                size=11,
                weight=ft.FontWeight.W_500 if is_sel else ft.FontWeight.W_400,
            )
            row = ft.Container(
                padding=ft.padding.symmetric(horizontal=10, vertical=8),
                border_radius=7,
                content=ft.Row([
                    ft.Icon(ico, size=14, color=ico_col),
                    ft.Container(width=10),
                    lbl,
                    ft.Container(expand=True),
                    dot,
                ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )
            v = opt_value
            row.on_click = lambda e, val=v: self._on_loader_click(val)
            row.on_hover = lambda e, r=row: (
                setattr(r, "bgcolor",
                        INPUT_BG if e.data == "true" else "transparent")
                or r.update()
            )
            self._loader_body.controls.append(row)

    def _on_loader_click(self, value):
        self._discover_loader = value  # None = auto
        self._rebuild_loader_section(self._discover_profile)
        try:
            self._loader_body.update()
        except Exception:
            pass
        self._fire_filter_change()

    # ── Category section ──────────────────────────────────────────────────────
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
        ico     = _CAT_ICONS.get(cat, ft.icons.LABEL_ROUNDED)
        ico_col = GREEN if is_sel else TEXT_DIM

        dot = ft.Container(
            width=8, height=8, border_radius=4,
            bgcolor=GREEN if is_sel else "transparent",
            border=ft.border.all(1.5, GREEN if is_sel else BORDER_BRIGHT),
            animate=ft.animation.Animation(100, ft.AnimationCurve.EASE_OUT),
        )
        ico_ctrl = ft.Icon(ico, size=14, color=ico_col)
        lbl = ft.Text(
            cat, color=TEXT_PRI if is_sel else TEXT_SEC,
            size=11,
            weight=ft.FontWeight.W_500 if is_sel else ft.FontWeight.W_400,
        )
        row = ft.Container(
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            border_radius=7,
            content=ft.Row([
                ico_ctrl,
                ft.Container(width=10),
                lbl,
                ft.Container(expand=True),
                dot,
            ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        def _click(e, c=cat, d=dot, ic=ico_ctrl, l=lbl, r=row):
            if c in self._selected_cats:
                self._selected_cats.discard(c)
                d.bgcolor  = "transparent"
                d.border   = ft.border.all(1.5, BORDER_BRIGHT)
                ic.color   = TEXT_DIM
                l.color    = TEXT_SEC
                l.weight   = ft.FontWeight.W_400
            else:
                self._selected_cats.add(c)
                d.bgcolor  = GREEN
                d.border   = ft.border.all(1.5, GREEN)
                ic.color   = GREEN
                l.color    = TEXT_PRI
                l.weight   = ft.FontWeight.W_500
            try:
                d.update(); ic.update(); l.update()
            except Exception:
                pass
            self._fire_filter_change()

        row.on_click = _click
        row.on_hover = lambda e, r=row: (
            setattr(r, "bgcolor",
                    INPUT_BG if e.data == "true" else "transparent")
            or r.update()
        )
        return row

    def _fire_filter_change(self):
        if callable(self._on_filter_change):
            self._on_filter_change()

    # ── Toggle sections ───────────────────────────────────────────────────────
    def _toggle_ver(self, e):
        self._ver_expanded = not self._ver_expanded
        self._ver_body.visible = self._ver_expanded
        self._ver_arrow.name = (ft.icons.KEYBOARD_ARROW_UP_ROUNDED
                                if self._ver_expanded
                                else ft.icons.KEYBOARD_ARROW_DOWN_ROUNDED)
        try:
            self._ver_body.update()
            self._ver_arrow.update()
        except Exception:
            pass

    def _toggle_loader(self, e):
        self._loader_expanded = not self._loader_expanded
        self._loader_body_container.visible = self._loader_expanded
        self._loader_arrow.name = (ft.icons.KEYBOARD_ARROW_UP_ROUNDED
                                   if self._loader_expanded
                                   else ft.icons.KEYBOARD_ARROW_DOWN_ROUNDED)
        try:
            self._loader_body_container.update()
            self._loader_arrow.update()
        except Exception:
            pass

    def _toggle_cat(self, e):
        self._cat_expanded = not self._cat_expanded
        self._cat_body_container.visible = self._cat_expanded
        self._cat_arrow.name = (ft.icons.KEYBOARD_ARROW_UP_ROUNDED
                                if self._cat_expanded
                                else ft.icons.KEYBOARD_ARROW_DOWN_ROUNDED)
        try:
            self._cat_body_container.update()
            self._cat_arrow.update()
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    #  CUENTA
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
            mode_txt = "Microsoft" if is_ms else "Offline"
            dot_col  = GREEN if is_ms else TEXT_DIM
        else:
            name     = "Sin cuenta"
            mode_txt = "Offline"
            dot_col  = TEXT_DIM

        color    = AVATAR_PALETTE[abs(hash(name)) % len(AVATAR_PALETTE)]
        initials = (name[:2] if len(name) >= 2 else name).upper()

        self._username_lbl.value = name
        self._mode_lbl.value     = mode_txt
        self._dot.bgcolor        = dot_col
        self._avatar_text.value  = initials
        self._avatar_box.bgcolor = color
        try:
            self._username_lbl.update()
            self._mode_lbl.update()
            self._dot.update()
            self._avatar_text.update()
            self._avatar_box.update()
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    #  NOTICIAS
    # ═══════════════════════════════════════════════════════════════════════
    def _fetch_news(self):
        items = []
        try:
            req = urllib.request.Request(
                "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json",
                headers={"User-Agent": "GerosLauncher/0.2.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())
            latest_r = data["latest"]["release"]
            latest_s = data["latest"]["snapshot"]
            items.append({
                "tag": "⭐ Release", "tag_color": GREEN,
                "title": f"Latest release: {latest_r}",
                "body":  f"Snapshot: {latest_s}",
                "source": "Mojang", "url": None,
            })
            type_map = {
                "release":   ("🟢 Release",  GREEN),
                "snapshot":  ("🔵 Snapshot", "#4dabf7"),
                "old_beta":  ("🟡 Beta",     "#ffa94d"),
                "old_alpha": ("🔴 Alpha",    "#ff6b6b"),
            }
            for v in data["versions"][:4]:
                tag, tc = type_map.get(v["type"], (v["type"], TEXT_SEC))
                items.append({
                    "tag": tag, "tag_color": tc,
                    "title": f"Minecraft {v['id']}",
                    "body":  v.get("releaseTime", "")[:10],
                    "source": "Mojang", "url": None,
                })
        except Exception as ex:
            log.warning(f"News Mojang: {ex}")

        try:
            req2 = urllib.request.Request(
                "https://api.modrinth.com/v2/search"
                "?limit=3&index=updated&facets=[[%22project_type:mod%22]]",
                headers={"User-Agent": "GerosLauncher/0.2.0"})
            with urllib.request.urlopen(req2, timeout=8) as r:
                mdata = json.loads(r.read().decode())
            for hit in mdata.get("hits", []):
                desc = hit.get("description", "")
                items.append({
                    "tag": "🧩 Mod", "tag_color": "#a9e34b",
                    "title": hit.get("title", "Mod"),
                    "body":  (desc[:60] + "…") if len(desc) > 60 else desc,
                    "source": "Modrinth",
                    "url":   f"https://modrinth.com/mod/{hit.get('slug', '')}",
                })
        except Exception as ex:
            log.warning(f"News Modrinth: {ex}")

        self.app.page.run_thread(lambda: self._render_news(items))

    def _render_news(self, items: list):
        self._news_col.controls.clear()
        if not items:
            self._news_col.controls.append(
                ft.Container(
                    padding=ft.padding.all(14),
                    content=ft.Text("Sin conexión.", color=TEXT_DIM, size=9),
                )
            )
            self._news_count_lbl.value = "sin conexión"
        else:
            self._news_count_lbl.value = str(len(items))
            for i, item in enumerate(items):
                if i > 0:
                    self._news_col.controls.append(
                        ft.Divider(height=1, color=BORDER))
                self._news_col.controls.append(self._make_news_card(item))
        try:
            self._news_col.update()
            self._news_count_lbl.update()
        except Exception:
            pass

    def _make_news_card(self, item: dict) -> ft.Container:
        has_url = bool(item.get("url"))
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=18, vertical=10),
            bgcolor=SIDEBAR_BG, border_radius=4,
            on_click=(
                lambda e, u=item["url"]: __import__("webbrowser").open(u)
            ) if has_url else None,
            on_hover=lambda e: (
                setattr(e.control, "bgcolor",
                        CARD_BG if e.data == "true" else SIDEBAR_BG)
                or e.control.update()
            ),
            content=ft.Column([
                ft.Row([
                    ft.Text(item["tag"], color=item.get("tag_color", GREEN),
                            size=8, weight=ft.FontWeight.BOLD, expand=True),
                    ft.Text(item["source"], color=TEXT_DIM, size=7),
                ]),
                ft.Text(item["title"], color=TEXT_PRI, size=9,
                        weight=ft.FontWeight.BOLD,
                        overflow=ft.TextOverflow.ELLIPSIS, max_lines=2),
                ft.Text(item.get("body", ""), color=TEXT_SEC, size=8,
                        overflow=ft.TextOverflow.ELLIPSIS)
                if item.get("body") else ft.Container(height=0),
            ], spacing=2),
        )