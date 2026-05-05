# -*- coding: utf-8 -*-
"""
gui/views/discover_view.py
Diseño inspirado en Modrinth App:
 - Header de instancia (nombre, loader, versión) + Back to instance
 - Tabs pill: Mods / Resource Packs / Data Packs / Shaders / Modpacks
 - Barra de búsqueda full-width
 - Sort by + View (page size) + paginación numérica
 - Chips de versión MC + loader activo
 - Cards grandes estilo Modrinth
 - Panel de filtros en sidebar_right (categorías, loader, hide installed)
 - Diálogo de detalle con lista de versiones — estilo Modrinth App
"""

import threading
import os
import json
import math
import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER, BORDER_BRIGHT,
    GREEN, GREEN_DIM, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV, ACCENT_RED,
)
from utils.icon_cache import _fetch_author_avatar, get_author as cache_get_author
from utils.install_detector import build_installed_set, is_installed_in
from utils.logger import get_logger

log = get_logger()

# ── Constantes ─────────────────────────────────────────────────────────────────
SORT_OPTIONS = {
    "relevance": "Relevance",
    "downloads": "Downloads",
    "follows":   "Follows",
    "newest":    "Newest",
    "updated":   "Updated",
}
VIEW_SIZES   = [10, 20, 40]

TAB_PROJECT_TYPES = ["mod", "resourcepack", "datapack", "shader", "modpack"]
TAB_LABELS        = ["Mods", "Resource Packs", "Data Packs", "Shaders", "Modpacks"]
TAB_HINTS         = [
    "Search mods...",
    "Search resource packs...",
    "Search data packs...",
    "Search shaders...",
    "Search modpacks...",
]

_PALETTE = [
    "#2d6a4f", "#1e3a5f", "#5c2a2a", "#3a3a1e",
    "#2a1e5c", "#1e5c4a", "#4a3a1e", "#5c3a4a",
]


def _human(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _rel_date(iso: str) -> str:
    if not iso:
        return ""
    try:
        from datetime import datetime, timezone
        dt   = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        diff = datetime.now(timezone.utc) - dt
        d    = diff.days
        if d == 0:
            h = diff.seconds // 3600
            return "Today" if h == 0 else f"{h}h ago"
        if d == 1:
            return "Yesterday"
        if d < 30:
            return f"{d} days ago"
        if d < 365:
            return f"{d // 30} months ago"
        return f"{d // 365} years ago"
    except Exception:
        return ""


# ── Icon widget ────────────────────────────────────────────────────────────────
def _icon_widget(url: str, title: str, size: int = 80) -> ft.Control:
    color    = _PALETTE[abs(hash(title)) % len(_PALETTE)]
    initial  = (title[0] if title else "?").upper()
    fallback = ft.Container(
        width=size, height=size, border_radius=12,
        bgcolor=color, alignment=ft.alignment.center,
        content=ft.Text(initial, color="#ffffff",
                        size=int(size * 0.38), weight=ft.FontWeight.BOLD),
    )
    if not url:
        return fallback
    return ft.Image(
        src=url, width=size, height=size,
        border_radius=12, fit=ft.ImageFit.COVER,
        error_content=fallback,
    )


# ── Category chip ──────────────────────────────────────────────────────────────
def _cat_chip(label: str) -> ft.Container:
    _icons = {
        "client":         ft.icons.COMPUTER_ROUNDED,
        "server":         ft.icons.DNS_ROUNDED,
        "library":        ft.icons.BOOK_ROUNDED,
        "optimization":   ft.icons.SPEED_ROUNDED,
        "utility":        ft.icons.BUILD_ROUNDED,
        "decoration":     ft.icons.PALETTE_ROUNDED,
        "adventure":      ft.icons.EXPLORE_ROUNDED,
        "magic":          ft.icons.AUTO_AWESOME_ROUNDED,
        "technology":     ft.icons.SETTINGS_ROUNDED,
        "food":           ft.icons.RESTAURANT_ROUNDED,
        "mobs":           ft.icons.PETS_ROUNDED,
        "worldgen":       ft.icons.TERRAIN_ROUNDED,
        "storage":        ft.icons.INVENTORY_ROUNDED,
        "transportation": ft.icons.TRAIN_ROUNDED,
        "social":         ft.icons.PEOPLE_ROUNDED,
        "management":     ft.icons.MANAGE_ACCOUNTS_ROUNDED,
        "economy":        ft.icons.ATTACH_MONEY_ROUNDED,
        "equipment":      ft.icons.SHIELD_ROUNDED,
        "game mechanics": ft.icons.GAMEPAD_ROUNDED,
    }
    ico = _icons.get(label.lower())
    row_children: list = []
    if ico:
        row_children.append(ft.Icon(ico, size=10, color=TEXT_DIM))
        row_children.append(ft.Container(width=4))
    row_children.append(ft.Text(
        label.replace("-", " ").title(), color=TEXT_DIM, size=9))
    return ft.Container(
        bgcolor="#1f2937", border_radius=5,
        padding=ft.padding.symmetric(horizontal=8, vertical=4),
        content=ft.Row(row_children, spacing=0, tight=True),
    )


# ── Skeleton card ──────────────────────────────────────────────────────────────
def _skeleton_card() -> ft.Container:
    def _bar(w, h=10, op=0.13):
        return ft.Container(width=w, height=h, border_radius=4,
                            bgcolor="#ffffff", opacity=op)
    return ft.Container(
        bgcolor=CARD_BG, border=ft.border.all(1, BORDER),
        border_radius=14, padding=ft.padding.all(20),
        content=ft.Row([
            ft.Container(width=80, height=80, border_radius=12,
                         bgcolor="#ffffff", opacity=0.09),
            ft.Container(width=20),
            ft.Column([
                _bar(220, 14, 0.18), ft.Container(height=6),
                _bar(100, 9),        ft.Container(height=6),
                _bar(380, 9),        _bar(300, 9),
                ft.Container(height=10),
                ft.Row([_bar(70, 8), ft.Container(width=6),
                        _bar(80, 8), ft.Container(width=6), _bar(55, 8)]),
            ], spacing=4, expand=True),
            ft.Column([
                _bar(80, 9), ft.Container(height=6),
                _bar(70, 9), ft.Container(height=6), _bar(60, 9),
            ], horizontal_alignment=ft.CrossAxisAlignment.END),
        ], vertical_alignment=ft.CrossAxisAlignment.START),
    )


# ══════════════════════════════════════════════════════════════════════════════
#  DiscoverView
# ══════════════════════════════════════════════════════════════════════════════
class DiscoverView:
    def __init__(self, page: ft.Page, app):
        self.page = page
        self.app  = app

        self._results    : list = []
        self._page_index : int  = 0
        self._page_size  : int  = 20
        self._total_hits : int  = 0
        self._loading    : bool = False
        self._tab_index  : int  = 0
        self._debounce_timer     = None
        self._installed_set: set = set()
        self._source_profile     = None   # set by instance_view before on_show
        self._selected_account   = None   # cuenta elegida en el dropdown

        self._build()

    # ── Build ──────────────────────────────────────────────────────────────────
    def _build(self):
        # ── Instance header (visible only when source_profile is set) ─────────
        self._inst_icon   = ft.Container(
            width=40, height=40, border_radius=8,
            bgcolor=CARD2_BG, alignment=ft.alignment.center,
            content=ft.Icon(ft.icons.WIDGETS_ROUNDED, size=20, color=TEXT_DIM),
        )
        self._inst_name   = ft.Text("", color=TEXT_PRI, size=14,
                                    weight=ft.FontWeight.BOLD)
        self._inst_meta   = ft.Text("", color=TEXT_SEC, size=11)
        self._back_btn    = ft.Container(
            bgcolor=INPUT_BG,
            border=ft.border.all(1, BORDER),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=14, vertical=8),
            on_click=lambda e: self._go_back(),
            on_hover=lambda e, b=None: None,  # set below
            content=ft.Row([
                ft.Icon(ft.icons.ARROW_BACK_ROUNDED, size=14, color=TEXT_SEC),
                ft.Container(width=6),
                ft.Text("Back to instance", color=TEXT_SEC, size=11,
                        weight=ft.FontWeight.W_500),
            ], spacing=0, tight=True),
        )
        self._back_btn.on_hover = lambda e, b=self._back_btn: (
            setattr(b, "bgcolor", CARD2_BG if e.data == "true" else INPUT_BG)
            or b.update()
        )
        self._inst_header = ft.Container(
            visible=False,
            padding=ft.padding.only(bottom=20),
            content=ft.Row([
                self._inst_icon,
                ft.Container(width=14),
                ft.Column([
                    self._inst_name,
                    self._inst_meta,
                ], spacing=2, expand=True),
                self._back_btn,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        # ── Account selector ──────────────────────────────────────────────────
        self._account_dd = ft.Dropdown(
            prefix_icon=ft.icons.PERSON_ROUNDED,
            hint_text="Select account...",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=12),
            width=220, height=44, color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            text_style=ft.TextStyle(size=12),
            on_change=self._on_account_change,
        )
        self._account_selector_row = ft.Container(
            visible=False,
            padding=ft.padding.only(bottom=12),
            content=ft.Row([
                ft.Icon(ft.icons.WIDGETS_ROUNDED, size=16, color=TEXT_SEC),
                ft.Container(width=10),
                ft.Text("Install as:", color=TEXT_SEC, size=12),
                ft.Container(width=10),
                self._account_dd,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        # ── Tabs ──────────────────────────────────────────────────────────────
        self._tab_buttons: list[ft.Container] = []
        tab_controls = []
        for i, label in enumerate(TAB_LABELS):
            lbl = ft.Text(
                label, size=12, weight=ft.FontWeight.W_600,
                color=TEXT_INV if i == 0 else TEXT_SEC,
            )
            btn = ft.Container(
                bgcolor=GREEN if i == 0 else "transparent",
                border_radius=20,
                padding=ft.padding.symmetric(horizontal=16, vertical=7),
                on_click=lambda e, idx=i: self._switch_tab(idx),
                on_hover=lambda e, idx=i: self._tab_hover(e, idx),
                animate=ft.animation.Animation(150, ft.AnimationCurve.EASE_OUT),
                content=lbl,
                data=i,
            )
            self._tab_buttons.append(btn)
            tab_controls.append(btn)

        # ── Search ────────────────────────────────────────────────────────────
        self._search_field = ft.TextField(
            hint_text="Search mods...",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=13),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, expand=True, height=44,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=10),
            prefix_icon=ft.icons.SEARCH_ROUNDED,
            text_size=13,
            on_change=self._on_search_change,
        )

        # ── Sort + View dropdowns ─────────────────────────────────────────────
        self._sort_dd = ft.Dropdown(
            prefix_text="Sort by: ",
            prefix_style=ft.TextStyle(color=TEXT_SEC, size=12),
            width=225, height=44, color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            options=[ft.dropdown.Option(key=k, text=v)
                     for k, v in SORT_OPTIONS.items()],
            value="relevance",
            text_style=ft.TextStyle(size=12),
            on_change=self._on_filter_change,
        )
        self._view_dd = ft.Dropdown(
            prefix_text="View: ",
            prefix_style=ft.TextStyle(color=TEXT_SEC, size=12),
            width=130, height=44, color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            options=[ft.dropdown.Option(str(s)) for s in VIEW_SIZES],
            value="20",
            text_style=ft.TextStyle(size=12),
            on_change=self._on_view_change,
        )

        # ── Pagination ────────────────────────────────────────────────────────
        self._pagination_row       = ft.Row([], spacing=4)
        self._pagination_container = ft.Container(
            content=self._pagination_row, visible=False)

        # ── Version/loader filter chips ───────────────────────────────────────
        self._filter_chips_row = ft.Row([], spacing=8, visible=False)

        # ── Results list ──────────────────────────────────────────────────────
        self._list_col = ft.Column(
            [], spacing=8, expand=True)

        self._empty_state = ft.Container(
            visible=False, alignment=ft.alignment.center, expand=True,
            content=ft.Column([
                ft.Icon(ft.icons.SEARCH_OFF_ROUNDED, size=56, color=TEXT_DIM),
                ft.Container(height=12),
                ft.Text("No results found", color=TEXT_SEC, size=16,
                        weight=ft.FontWeight.BOLD),
                ft.Text("Try a different search or adjust your filters.",
                        color=TEXT_DIM, size=11),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
        )

        self._count_lbl = ft.Text("", color=TEXT_DIM, size=11)

        self.root = ft.Container(
            expand=True, bgcolor=BG,
            content=ft.Column([
                ft.Container(
                    expand=True,
                    content=ft.ListView(
                        key="main_scroll",
                        on_scroll_interval=10,
                        controls=[
                            ft.Container(
                                padding=ft.padding.only(
                                    left=36, right=36, top=28, bottom=16),
                                content=ft.Column([
                                    self._inst_header,
                                    ft.Text("Install content to instance",
                                            color=TEXT_PRI, size=22,
                                            weight=ft.FontWeight.BOLD),
                                    ft.Container(height=12),
                                    self._account_selector_row,
                                    ft.Container(height=6),
                                    ft.Row(tab_controls, spacing=4),
                                    ft.Container(height=16),
                                    ft.Row([self._search_field]),
                                    ft.Container(height=12),
                                    ft.Row([
                                        self._sort_dd,
                                        ft.Container(width=8),
                                        self._view_dd,
                                        ft.Container(expand=True),
                                        self._pagination_container,
                                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                    ft.Container(height=10),
                                    self._filter_chips_row,
                                    ft.Container(height=4),
                                    ft.Stack([
                                        self._list_col,
                                        self._empty_state,
                                    ]),
                                    ft.Container(height=6),
                                    ft.Row([self._count_lbl]),
                                    ft.Container(height=16),
                                ], spacing=0),
                            ),
                        ],
                        padding=0,
                    ),
                ),
            ], spacing=0, expand=True),
        )
        self._main_lv = self.root.content.controls[0].content

    def _smooth_scroll(self, delta: float):
        """Scroll suave simulado con pasos pequeños."""
        steps   = 8
        step_px = delta / steps

        def _do_step(i):
            if i >= steps:
                return
            try:
                self._main_lv.scroll_to(
                    delta=step_px,
                    duration=18,
                    curve=ft.AnimationCurve.EASE_OUT,
                )
            except Exception:
                pass
            threading.Timer(0.018 * (i + 1), lambda: _do_step(i + 1)).start()

        _do_step(0)

    # ── Lifecycle ──────────────────────────────────────────────────────────────
    def on_show(self):
        if not self._source_profile:
            try:
                last = self.app.settings.last_profile
                if last:
                    p = self.app.profile_manager.get_profile_by_name(last)
                    if p:
                        self._source_profile = p
                if not self._source_profile:
                    profiles = self.app.profile_manager.get_all_profiles()
                    if profiles:
                        self._source_profile = profiles[0]
            except Exception:
                pass
        self._loading = False
        self._update_instance_header()
        self._load_account_dropdown()
        self._refresh_chips()
        if hasattr(self.app, "sidebar_right"):
            self.app.sidebar_right.set_discover_mode(
                True,
                profile=self._source_profile,
                tab_type=TAB_PROJECT_TYPES[self._tab_index],
                on_change=self._on_sidebar_filter_change,
            )
        self._do_search(reset=True)

    def on_hide(self):
        if hasattr(self.app, "sidebar_right"):
            self.app.sidebar_right.set_discover_mode(False)

    def set_source_profile(self, profile):
        self._source_profile = profile

    def _update_instance_header(self):
        profile = self._source_profile
        if not profile:
            self._inst_header.visible = False
            try: self._inst_header.update()
            except Exception: pass
            return

        self._inst_name.value = getattr(profile, "name", "Instance")
        loader = self._detect_loader(profile)
        mc_ver = getattr(profile, "version_id", "")
        meta_parts = []
        if loader:
            meta_parts.append(loader.capitalize())
        if mc_ver:
            meta_parts.append(mc_ver)
        self._inst_meta.value = "  ".join(meta_parts)
        self._inst_header.visible = True
        try: self._inst_header.update()
        except Exception: pass

    def _refresh_chips(self):
        profile = self._source_profile
        if not profile:
            self._filter_chips_row.visible = False
            try: self._filter_chips_row.update()
            except Exception: pass
            return

        mc_ver = getattr(profile, "version_id", None)
        loader = self._detect_loader(profile)
        chips  = []
        if mc_ver:
            chips.append(self._filter_chip(ft.icons.LOCK_OUTLINE_ROUNDED, mc_ver))
        if loader:
            chips.append(self._filter_chip(ft.icons.LOCK_OUTLINE_ROUNDED,
                                           loader.capitalize()))
        self._filter_chips_row.controls.clear()
        self._filter_chips_row.controls.extend(chips)
        self._filter_chips_row.visible = bool(chips)
        try: self._filter_chips_row.update()
        except Exception: pass

    def _filter_chip(self, icon, label: str) -> ft.Container:
        return ft.Container(
            bgcolor=INPUT_BG,
            border=ft.border.all(1, BORDER),
            border_radius=6,
            padding=ft.padding.symmetric(horizontal=10, vertical=5),
            content=ft.Row([
                ft.Icon(icon, size=11, color=TEXT_SEC),
                ft.Container(width=5),
                ft.Text(label, color=TEXT_PRI, size=11),
            ], spacing=0, tight=True),
        )

    def _go_back(self):
        self.on_hide()
        self.app._show_view("instance")

    # ── Tabs ───────────────────────────────────────────────────────────────────
    def _switch_tab(self, idx: int):
        if self._loading:
            return
        self._tab_index = idx
        self._highlight_tab(idx)
        self._search_field.hint_text = TAB_HINTS[idx]
        try: self._search_field.update()
        except Exception: pass
        if hasattr(self.app, "sidebar_right"):
            self.app.sidebar_right.update_tab_filters(TAB_PROJECT_TYPES[idx])
        self._do_search(reset=True)

    def _highlight_tab(self, active: int):
        for i, btn in enumerate(self._tab_buttons):
            is_active = (i == active)
            btn.bgcolor = GREEN if is_active else "transparent"
            lbl: ft.Text = btn.content
            lbl.color  = TEXT_INV if is_active else TEXT_SEC
            lbl.weight = (ft.FontWeight.W_700 if is_active
                          else ft.FontWeight.W_600)
            try: btn.update()
            except Exception: pass

    def _tab_hover(self, e, idx: int):
        if idx == self._tab_index:
            return
        btn = self._tab_buttons[idx]
        btn.bgcolor = CARD2_BG if e.data == "true" else "transparent"
        lbl: ft.Text = btn.content
        lbl.color = TEXT_PRI if e.data == "true" else TEXT_SEC
        try: btn.update()
        except Exception: pass

    # ── Events ─────────────────────────────────────────────────────────────────
    def _on_account_change(self, e):
        profile_id = self._account_dd.value
        if profile_id and hasattr(self.app, "profile_manager"):
            p = self.app.profile_manager.get_profile(profile_id)
            if p:
                self._source_profile = p
                target = self._target_dir(p)
                self._installed_set = build_installed_set(target)
                self._refresh_chips()
                self._do_search(reset=True)

    def _load_account_dropdown(self):
        try:
            if not hasattr(self.app, "profile_manager"):
                return
            profiles = self.app.profile_manager.get_all_profiles()
            if not profiles:
                self._account_selector_row.visible = False
                try: self._account_selector_row.update()
                except Exception: pass
                return

            self._account_dd.options = [
                ft.dropdown.Option(key=p.id, text=f"{p.name}  ({getattr(p, 'version_id', '?')})")
                for p in profiles
            ]

            if self._source_profile and self._source_profile.id in [p.id for p in profiles]:
                self._account_dd.value = self._source_profile.id
            elif profiles:
                self._account_dd.value = profiles[0].id

            self._account_selector_row.visible = True
            try:
                self._account_dd.update()
                self._account_selector_row.update()
            except Exception: pass
        except Exception as e:
            log.warning(f"Error loading profiles into dropdown: {e}")

    def _on_search_change(self, e):
        if self._debounce_timer:
            self._debounce_timer.cancel()
        self._debounce_timer = threading.Timer(
            0.4, lambda: self._do_search(reset=True))
        self._debounce_timer.start()

    def _on_filter_change(self, e):
        self._do_search(reset=True)

    def _on_view_change(self, e):
        try:
            self._page_size = int(self._view_dd.value or "20")
        except ValueError:
            self._page_size = 20
        self._do_search(reset=True)

    def _on_sidebar_filter_change(self):
        self._do_search(reset=True)

    # ── Search ─────────────────────────────────────────────────────────────────
    def _do_search(self, reset: bool = True):
        if self._loading:
            return
        if reset:
            self._page_index = 0
            self._results    = []
        self._loading = True
        threading.Thread(target=self._fetch, daemon=True).start()

    def _go_to_page(self, page_idx: int):
        if self._loading or page_idx < 0:
            return
        total_pages = max(1, math.ceil(self._total_hits / self._page_size))
        if page_idx >= total_pages:
            return
        self._page_index = page_idx
        self._loading = True
        threading.Thread(target=self._fetch, daemon=True).start()

    # ── Fetch (background thread) ──────────────────────────────────────────────
    def _fetch(self):
        self.page.run_thread(self._show_skeleton)

        query        = (self._search_field.value or "").strip()
        profile      = self._source_profile
        mc_ver       = getattr(profile, "version_id", None) if profile else None
        project_type = TAB_PROJECT_TYPES[self._tab_index]
        sort_by      = self._sort_dd.value or "relevance"
        offset       = self._page_index * self._page_size

        sidebar_filters: dict = {}
        if hasattr(self.app, "sidebar_right") and self.app.sidebar_right._discover_mode:
            sidebar_filters = self.app.sidebar_right.get_discover_filters()

        categories     = sidebar_filters.get("categories", [])
        excluded_cats  = sidebar_filters.get("excluded_cats", [])
        hide_installed = sidebar_filters.get("hide_installed", False)
        loader_override= sidebar_filters.get("loader")

        loader = loader_override if loader_override else (
            self._detect_loader(profile)
            if project_type in ("mod", "modpack") else None
        )

        target_dir          = self._target_dir(profile) if profile else None
        self._installed_set = build_installed_set(target_dir)

        try:
            service = self.app.modrinth_service
            kwargs = dict(
                query        = query,
                mc_version   = mc_ver,
                loader       = loader,
                limit        = self._page_size,
                offset       = offset,
                sort_by      = sort_by,
                project_type = project_type,
            )
            results = service.search_mods(**kwargs, categories=categories)

            if excluded_cats:
                excl_lower = {c.lower() for c in excluded_cats}
                results = [
                    r for r in results
                    if not any(c.lower() in excl_lower
                            for c in (r.categories or []))
                ]

            total = getattr(service, "_last_total_hits", None)
            if total is None:
                if len(results) < self._page_size:
                    total = offset + len(results)
                else:
                    total = max(self._total_hits, offset + len(results) + 1)

            if hide_installed:
                results = [r for r in results
                           if not is_installed_in(r.slug, r.title,
                                                  self._installed_set)]

            self._results    = results
            self._total_hits = total

            def _render():
                self._hide_skeleton()
                if not results:
                    self._show_empty()
                else:
                    self._render_results(results)
            self.page.run_thread(_render)

        except Exception as err:
            log.warning(f"DiscoverView fetch error: {err}")
            def _err():
                self._hide_skeleton()
                self._count_lbl.value = f"Network error: {err}"
                try: self._count_lbl.update()
                except Exception: pass
            self.page.run_thread(_err)
        finally:
            self._loading = False

    # ── Render ─────────────────────────────────────────────────────────────────
    def _render_results(self, results: list):
        self._list_col.controls.clear()
        self._empty_state.visible = False

        for proj in results:
            installed = is_installed_in(
                proj.slug, proj.title, self._installed_set)
            self._list_col.controls.append(self._make_card(proj, installed))

        start = self._page_index * self._page_size + 1
        end   = start + len(results) - 1
        self._count_lbl.value = (
            f"Showing {start}\u2013{end} of {self._total_hits:,} results"
            if self._total_hits > 0 else f"{len(results)} results"
        )

        self._rebuild_pagination()
        self._pagination_container.visible = (
            self._total_hits > self._page_size)

        try:
            self._list_col.update()
            self._empty_state.update()
            self._count_lbl.update()
            self._pagination_container.update()
        except Exception:
            pass

    def _rebuild_pagination(self):
        total_pages = max(1, math.ceil(self._total_hits / self._page_size))
        cur         = self._page_index
        row         = self._pagination_row
        row.controls.clear()

        def _page_btn(label, page_idx, active=False, disabled=False):
            if active:
                bg, fg, brd = GREEN, TEXT_INV, None
            elif disabled:
                bg, fg, brd = "transparent", TEXT_DIM, None
            else:
                bg  = INPUT_BG
                fg  = TEXT_PRI
                brd = ft.border.all(1, BORDER)
            btn = ft.Container(
                width=36, height=36,
                bgcolor=bg, border=brd, border_radius=8,
                alignment=ft.alignment.center,
                animate=ft.animation.Animation(100, ft.AnimationCurve.EASE_OUT),
                content=ft.Text(str(label), color=fg, size=12,
                                weight=ft.FontWeight.BOLD if active
                                else ft.FontWeight.W_500,
                                text_align=ft.TextAlign.CENTER),
            )
            if not active and not disabled:
                t = page_idx
                btn.on_click = lambda e, p=t: self._go_to_page(p)
                btn.on_hover = lambda e, b=btn: (
                    setattr(b, "bgcolor",
                            CARD2_BG if e.data == "true" else INPUT_BG)
                    or b.update()
                )
            return btn

        def _ellipsis():
            return ft.Container(
                width=36, height=36, alignment=ft.alignment.center,
                content=ft.Text("\u2026", color=TEXT_DIM, size=12))

        def _arrow(icon, target, enabled):
            btn = ft.Container(
                width=36, height=36, border_radius=8,
                bgcolor=INPUT_BG if enabled else "transparent",
                border=ft.border.all(1, BORDER) if enabled else None,
                alignment=ft.alignment.center,
                content=ft.Icon(icon, size=18,
                                color=TEXT_PRI if enabled else TEXT_DIM),
            )
            if enabled:
                btn.on_click = lambda e, t=target: self._go_to_page(t)
                btn.on_hover = lambda e, b=btn: (
                    setattr(b, "bgcolor",
                            CARD2_BG if e.data == "true" else INPUT_BG)
                    or b.update()
                )
            return btn

        row.controls.append(
            _arrow(ft.icons.CHEVRON_LEFT_ROUNDED, cur - 1, cur > 0))

        pages_to_show: list = []
        if total_pages <= 7:
            pages_to_show = list(range(total_pages))
        else:
            core = set(range(max(0, cur - 1), min(total_pages, cur + 2)))
            pages_to_show = sorted({0, total_pages - 1} | core)

        prev_p = None
        for p in pages_to_show:
            if prev_p is not None and p - prev_p > 1:
                row.controls.append(_ellipsis())
            row.controls.append(_page_btn(p + 1, p, active=(p == cur)))
            prev_p = p

        row.controls.append(
            _arrow(ft.icons.CHEVRON_RIGHT_ROUNDED, cur + 1,
                   cur < total_pages - 1))

    # ── Skeleton / Empty ───────────────────────────────────────────────────────
    def _show_skeleton(self):
        self._list_col.controls.clear()
        self._empty_state.visible          = False
        self._pagination_container.visible = False
        for _ in range(5):
            self._list_col.controls.append(_skeleton_card())
        try:
            self._list_col.update()
            self._empty_state.update()
            self._pagination_container.update()
        except Exception:
            pass

    def _hide_skeleton(self):
        pass

    def _show_empty(self):
        self._list_col.controls.clear()
        self._empty_state.visible          = True
        self._count_lbl.value              = "0 results"
        self._pagination_container.visible = False
        try:
            self._list_col.update()
            self._empty_state.update()
            self._count_lbl.update()
            self._pagination_container.update()
        except Exception:
            pass

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _detect_loader(self, profile) -> str | None:
        if not profile:
            return None
        meta_path = os.path.join(
            getattr(profile, "game_dir", ""), "loader_meta.json")
        if os.path.isfile(meta_path):
            try:
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                entries = meta if isinstance(meta, list) else [meta]
                if entries:
                    return entries[0].get("loader_type")
            except Exception:
                pass
        return None

    def _target_dir(self, profile) -> str | None:
        if not profile:
            return None
        pt = TAB_PROJECT_TYPES[self._tab_index]
        if pt == "resourcepack":
            return getattr(profile, "resourcepacks_dir", None)
        if pt == "shader":
            return getattr(profile, "shaderpacks_dir", None)
        return getattr(profile, "mods_dir", None)

    # ── CARD ───────────────────────────────────────────────────────────────────
    def _make_card(self, proj, is_installed: bool) -> ft.Container:
        author   = getattr(proj, "author", "")
        follows  = getattr(proj, "follows", 0)
        updated  = (getattr(proj, "date_modified", "") or getattr(proj, "date_updated", ""))
        date_str = _rel_date(updated)
        slug_url = f"https://modrinth.com/mod/{proj.slug}"
        auth_url = f"https://modrinth.com/user/{author}" if author else ""

        if is_installed:
            install_btn = ft.Container(
                bgcolor="transparent",
                border=ft.border.all(1.5, GREEN),
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=14, vertical=7),
                content=ft.Row([
                    ft.Icon(ft.icons.CHECK_ROUNDED, size=14, color=GREEN),
                    ft.Container(width=6),
                    ft.Text("Installed", color=GREEN, size=11, weight=ft.FontWeight.W_600),
                ], spacing=0, tight=True),
            )
        else:
            install_btn = ft.Container(
                bgcolor=GREEN, border_radius=8,
                padding=ft.padding.symmetric(horizontal=14, vertical=7),
                animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
                on_click=lambda e, p=proj: self._quick_install(p),
                content=ft.Row([
                    ft.Icon(ft.icons.DOWNLOAD_ROUNDED, size=14, color=TEXT_INV),
                    ft.Container(width=6),
                    ft.Text("Install", color=TEXT_INV, size=11, weight=ft.FontWeight.W_600),
                ], spacing=0, tight=True),
            )
            install_btn.on_hover = lambda e, b=install_btn: (
                setattr(b, "bgcolor", GREEN_DIM if e.data == "true" else GREEN) or b.update()
            )

        meta_controls: list = []
        if author:
            author_txt = ft.Text(author, color=GREEN, size=11, weight=ft.FontWeight.W_500)
            cached = cache_get_author(author) or {}
            av_url = cached.get("avatar_url")
            if not av_url:
                av_placeholder = ft.Container(
                    width=15, height=15, border_radius=8,
                    bgcolor=CARD2_BG, alignment=ft.alignment.center,
                    content=ft.Text(author[0].upper(), size=7, color=TEXT_DIM),
                )
                def _load_avatar(a=author, placeholder=av_placeholder):
                    url = _fetch_author_avatar(a)
                    if url:
                        def update():
                            placeholder.content = ft.Image(
                                src=url, width=15, height=15,
                                border_radius=8, fit=ft.ImageFit.COVER)
                            try: placeholder.update()
                            except Exception: pass
                        self.page.run_thread(update)
                threading.Thread(target=_load_avatar, daemon=True).start()
                av = av_placeholder
            else:
                av = ft.Image(src=av_url, width=15, height=15,
                              border_radius=8, fit=ft.ImageFit.COVER)
            author_gd = ft.GestureDetector(
                mouse_cursor=ft.MouseCursor.CLICK,
                on_tap=lambda e, u=auth_url: self.page.launch_url(u),
                on_enter=lambda e, t=author_txt: (
                    setattr(t, "decoration", ft.TextDecoration.UNDERLINE) or t.update()
                ),
                on_exit=lambda e, t=author_txt: (
                    setattr(t, "decoration", ft.TextDecoration.NONE) or t.update()
                ),
                content=ft.Row([av, ft.Container(width=5), author_txt], spacing=0, tight=True),
            )
            ext_icon = ft.GestureDetector(
                mouse_cursor=ft.MouseCursor.CLICK,
                on_tap=lambda e, u=slug_url: self.page.launch_url(u),
                content=ft.Icon(ft.icons.OPEN_IN_NEW_ROUNDED, size=12, color=TEXT_DIM),
            )
            meta_controls = [
                ft.Text("by ", color=TEXT_DIM, size=11),
                author_gd,
                ft.Container(width=6),
                ext_icon,
            ]

        cats       = getattr(proj, "categories", []) or []
        shown      = cats[:3]
        extra      = len(cats) - 3
        chip_row: list = [_cat_chip(c) for c in shown]
        if extra > 0:
            chip_row.append(ft.Container(
                bgcolor="#1f2937", border_radius=5,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                content=ft.Text(f"+{extra}", color=TEXT_DIM, size=9),
            ))

        stats_col = ft.Column([
            ft.Row([
                ft.Icon(ft.icons.DOWNLOAD_ROUNDED, size=13, color=TEXT_DIM),
                ft.Container(width=5),
                ft.Text(_human(proj.downloads), color=TEXT_SEC, size=11, weight=ft.FontWeight.W_500),
            ], spacing=0, tight=True),
            ft.Row([
                ft.Icon(ft.icons.FAVORITE_BORDER_ROUNDED, size=13, color=TEXT_DIM),
                ft.Container(width=5),
                ft.Text(_human(follows) if follows else "\u2014", color=TEXT_SEC, size=11, weight=ft.FontWeight.W_500),
            ], spacing=0, tight=True),
            ft.Row([
                ft.Icon(ft.icons.HISTORY_ROUNDED, size=13, color=TEXT_DIM),
                ft.Container(width=5),
                ft.Text(date_str or "\u2014", color=TEXT_SEC, size=11),
            ], spacing=0, tight=True),
        ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.END)

        title_txt = ft.Text(
            proj.title, color=TEXT_PRI, size=15,
            weight=ft.FontWeight.BOLD,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        author_row_controls: list = [ft.Container(width=0)]
        if meta_controls:
            author_row_controls = meta_controls

        card = ft.Container(
            bgcolor=CARD_BG,
            border=ft.border.all(1, BORDER),
            border_radius=14, padding=ft.padding.all(20),
            animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
            on_click=lambda e, p=proj: self._open_detail(p),
            content=ft.Row([
                _icon_widget(proj.icon_url, proj.title, size=80),
                ft.Container(width=20),
                ft.Column([
                    ft.Row([
                        ft.Column([
                            title_txt,
                            ft.Container(height=3),
                            ft.Row(author_row_controls, spacing=0, wrap=False,
                                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ], expand=True, spacing=0),
                        install_btn,
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                       vertical_alignment=ft.CrossAxisAlignment.START),
                    ft.Container(height=8),
                    ft.Text(
                        (proj.description[:180] + "\u2026" if len(proj.description) > 180
                         else proj.description),
                        color=TEXT_SEC, size=11,
                        overflow=ft.TextOverflow.ELLIPSIS, max_lines=2,
                    ),
                    ft.Container(height=10),
                    ft.Row(chip_row, spacing=6, wrap=True),
                ], spacing=0, expand=True),
                ft.Container(width=24),
                stats_col,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        def _hover(e, c=card, t=title_txt):
            c.bgcolor = CARD2_BG if e.data == "true" else CARD_BG
            c.border  = ft.border.all(1, BORDER_BRIGHT if e.data == "true" else BORDER)
            t.decoration = (ft.TextDecoration.UNDERLINE if e.data == "true"
                            else ft.TextDecoration.NONE)
            try:
                c.update()
                t.update()
            except Exception:
                pass

        card.on_hover = _hover
        return card

    # ── Quick install ──────────────────────────────────────────────────────────
    def _quick_install(self, project):
        profile = self._source_profile
        if not profile:
            self.app.snack("Select a profile first.", error=True)
            return
        loader = self._detect_loader(profile)

        def do():
            try:
                version = self.app.modrinth_service.get_latest_version(
                    project.project_id,
                    mc_version=getattr(profile, "version_id", None),
                    loader=loader,
                )
                if not version:
                    self.page.run_thread(lambda: self.app.snack(
                        "No compatible version found.", error=True))
                    return
                target = self._target_dir(profile)
                os.makedirs(target, exist_ok=True)
                self.app.modrinth_service.download_mod_version(version, target)
                self._installed_set = build_installed_set(target)
                self.page.run_thread(lambda: self.app.snack(
                    f"{project.title} installed. \u2713"))
                self.page.run_thread(self._refresh_badges)
            except Exception as err:
                self.page.run_thread(
                    lambda e=err: self.app.snack(f"Error: {e}", error=True))

        threading.Thread(target=do, daemon=True).start()

    def _refresh_badges(self):
        new_controls = []
        for proj in self._results:
            installed = is_installed_in(
                proj.slug, proj.title, self._installed_set)
            new_controls.append(self._make_card(proj, installed))
        self._list_col.controls.clear()
        self._list_col.controls.extend(new_controls)
        try: self._list_col.update()
        except Exception: pass

    # ── Detail dialog ──────────────────────────────────────────────────────────
    def _open_detail(self, project):
        profile = self._source_profile
        ModDetailDialog(
            self.page, self.app, project,
            active_profile=profile,
            active_loader=self._detect_loader(profile),
            target_dir=self._target_dir(profile) if profile else None,
            on_installed=lambda: self._on_installed(project),
        )

    def _on_installed(self, project):
        profile = self._source_profile
        self._installed_set = build_installed_set(self._target_dir(profile))
        self._refresh_badges()



# ══════════════════════════════════════════════════════════════════════════════
#  Stat pill helper  (keep outside class so _build can call it)
# ══════════════════════════════════════════════════════════════════════════════
def _stat_pill(icon, value: str, tooltip: str) -> ft.Container:
    return ft.Container(
        bgcolor=INPUT_BG, border=ft.border.all(1, BORDER),
        border_radius=8,
        padding=ft.padding.symmetric(horizontal=12, vertical=6),
        tooltip=tooltip,
        content=ft.Row([
            ft.Icon(icon, size=13, color=TEXT_DIM),
            ft.Container(width=6),
            ft.Text(value, color=TEXT_SEC, size=11,
                    weight=ft.FontWeight.W_500),
        ], spacing=0, tight=True),
    )


# ══════════════════════════════════════════════════════════════════════════════
#  ModDetailDialog  —  Modrinth-style detail view
# ══════════════════════════════════════════════════════════════════════════════
class ModDetailDialog:
    """
    Full-screen-style dialog that mirrors the Modrinth App detail page:
      • Header  : icon, title, description, stats, Install button
      • Tabs    : Versions | Description | Gallery (Description & Gallery are stubs)
      • Versions: Platform / Game Version / Channel filter pills + sortable table
      • Sidebar : Compatibility chips, Platforms, Supported environments, Links
    """

    # ── filter state ──────────────────────────────────────────────────────────
    _CHANNEL_COLORS = {
        "release": "#27ae60",
        "beta":    "#e67e22",
        "alpha":   "#e74c3c",
    }

    def __init__(self, page, app, project, active_profile,
                 active_loader, target_dir=None, on_installed=None):
        self.page           = page
        self.app            = app
        self.project        = project
        self.active_profile = active_profile
        self.active_loader  = active_loader
        self.target_dir     = target_dir
        self.on_installed   = on_installed

        self._versions      : list = []
        self._selected_ver          = None
        self._active_tab    : int  = 0          # 0=Versions 1=Description 2=Gallery

        # filter state
        self._filter_platform : str | None = None   # None = all
        self._filter_mcver    : str | None = None
        self._filter_channel  : str | None = None   # None = all

        self._build()
        threading.Thread(target=self._fetch_versions, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    #  BUILD
    # ══════════════════════════════════════════════════════════════════════════
    def _build(self):
        author    = getattr(self.project, "author",  "")
        follows   = getattr(self.project, "follows", 0)
        cats      = getattr(self.project, "categories", []) or []
        prof_name = self.active_profile.name if self.active_profile else "No profile"
        mc_ver    = (getattr(self.active_profile, "version_id", None)
                     if self.active_profile else None)

        # ── TOP HEADER ────────────────────────────────────────────────────────
        header = ft.Container(
            padding=ft.padding.only(bottom=16),
            content=ft.Row([
                # Icon
                _icon_widget(self.project.icon_url, self.project.title, size=72),
                ft.Container(width=18),
                # Title + meta column
                ft.Column([
                    ft.Text(self.project.title, color=TEXT_PRI, size=20,
                            weight=ft.FontWeight.BOLD),
                    ft.Container(height=2),
                    ft.Text(
                        (self.project.description[:180] + "…"
                         if len(self.project.description) > 180
                         else self.project.description),
                        color=TEXT_SEC, size=11, max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Container(height=8),
                    # Stats row
                    ft.Row([
                        ft.Icon(ft.icons.DOWNLOAD_ROUNDED, size=14, color=TEXT_DIM),
                        ft.Container(width=4),
                        ft.Text(_human(self.project.downloads),
                                color=TEXT_SEC, size=11, weight=ft.FontWeight.W_600),
                        ft.Container(width=14),
                        ft.Icon(ft.icons.FAVORITE_BORDER_ROUNDED, size=14, color=TEXT_DIM),
                        ft.Container(width=4),
                        ft.Text(_human(follows) if follows else "—",
                                color=TEXT_SEC, size=11, weight=ft.FontWeight.W_600),
                        ft.Container(width=14),
                        *[_cat_chip(c) for c in cats[:3]],
                    ], spacing=0, tight=True, wrap=False),
                ], spacing=0, expand=True),
                # Install button
                self._make_install_btn(),
            ], vertical_alignment=ft.CrossAxisAlignment.START),
        )

        # ── TABS ──────────────────────────────────────────────────────────────
        self._tab_labels = ["Versions", "Description", "Gallery"]
        self._tab_btns   = []
        tab_row_controls = []
        for i, lbl in enumerate(self._tab_labels):
            t = ft.Text(lbl, size=12, weight=ft.FontWeight.W_600,
                        color=TEXT_PRI if i == 0 else TEXT_SEC)
            underline = ft.Container(
                height=2, border_radius=2,
                bgcolor=GREEN if i == 0 else "transparent",
                animate=ft.animation.Animation(150, ft.AnimationCurve.EASE_OUT),
            )
            btn = ft.Container(
                padding=ft.padding.symmetric(horizontal=14, vertical=6),
                on_click=lambda e, idx=i: self._switch_tab(idx),
                content=ft.Column([t, ft.Container(height=4), underline],
                                  spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                data={"label": t, "underline": underline},
            )
            self._tab_btns.append(btn)
            tab_row_controls.append(btn)

        tabs_row = ft.Row(tab_row_controls, spacing=0)

        # ── FILTER PILLS row (for Versions tab) ───────────────────────────────
        self._platform_dd = ft.Dropdown(
            prefix_text="Platform  ",
            prefix_style=ft.TextStyle(color=TEXT_SEC, size=11),
            hint_text="All",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=11),
            width=180, height=36, color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=6,
            content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
            text_style=ft.TextStyle(size=11),
            on_change=self._on_platform_change,
        )
        self._mcver_dd = ft.Dropdown(
            prefix_text="Game version  ",
            prefix_style=ft.TextStyle(color=TEXT_SEC, size=11),
            hint_text="All",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=11),
            width=210, height=36, color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=6,
            content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
            text_style=ft.TextStyle(size=11),
            on_change=self._on_mcver_change,
        )
        self._channel_dd = ft.Dropdown(
            prefix_text="Channel  ",
            prefix_style=ft.TextStyle(color=TEXT_SEC, size=11),
            hint_text="All",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=11),
            width=160, height=36, color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=6,
            content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
            text_style=ft.TextStyle(size=11),
            on_change=self._on_channel_change,
        )

        self._filter_row = ft.Container(
            visible=False,
            padding=ft.padding.only(top=10, bottom=4),
            content=ft.Row([
                ft.Icon(ft.icons.FILTER_LIST_ROUNDED, size=14, color=TEXT_DIM),
                ft.Container(width=8),
                self._platform_dd,
                ft.Container(width=8),
                self._mcver_dd,
                ft.Container(width=8),
                self._channel_dd,
            ], spacing=0, tight=True),
        )

        # ── VERSION TABLE ─────────────────────────────────────────────────────
        # Header row
        _col_name    = ft.Container(expand=True)
        _col_gv      = ft.Container(width=110)
        _col_plat    = ft.Container(width=120)
        _col_pub     = ft.Container(width=110)
        _col_dl      = ft.Container(width=80)
        _col_actions = ft.Container(width=60)

        def _th(label, width=None, expand=False):
            return ft.Container(
                width=width, expand=expand,
                content=ft.Text(label, color=TEXT_DIM, size=9,
                                weight=ft.FontWeight.BOLD),
            )

        table_header = ft.Container(
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
            border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
            content=ft.Row([
                ft.Container(width=28),   # channel dot
                _th("Name",          expand=True),
                _th("Game version",  width=110),
                _th("Platforms",     width=120),
                _th("Published",     width=110),
                _th("Downloads",     width=80),
                ft.Container(width=60),   # actions
            ], spacing=0),
        )

        self._spinner_row = ft.Row([
            ft.ProgressRing(width=16, height=16, color=GREEN, stroke_width=2),
            ft.Container(width=10),
            ft.Text("Loading versions…", color=TEXT_DIM, size=10),
        ], visible=True)

        self._status_lbl = ft.Text("", color=TEXT_DIM, size=10, visible=False)

        self._versions_col = ft.Column([], spacing=1)
        self._versions_lv  = ft.ListView(
            height=340,
            padding=ft.padding.only(right=4),
            controls=[
                table_header,
                self._spinner_row,
                self._status_lbl,
                self._versions_col,
            ],
        )

        # ── DESCRIPTION / GALLERY stubs ───────────────────────────────────────
        self._desc_panel = ft.Container(
            visible=False, height=340,
            alignment=ft.alignment.center,
            content=ft.Column([
                ft.Icon(ft.icons.DESCRIPTION_ROUNDED, size=40, color=TEXT_DIM),
                ft.Container(height=8),
                ft.Text("Description", color=TEXT_SEC, size=13,
                        weight=ft.FontWeight.BOLD),
                ft.Text(self.project.description, color=TEXT_DIM, size=11),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
        )
        self._gallery_panel = ft.Container(
            visible=False, height=340,
            alignment=ft.alignment.center,
            content=ft.Column([
                ft.Icon(ft.icons.PHOTO_LIBRARY_ROUNDED, size=40, color=TEXT_DIM),
                ft.Container(height=8),
                ft.Text("No gallery images available.",
                        color=TEXT_DIM, size=11),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
        )

        # ── LEFT CONTENT COLUMN ───────────────────────────────────────────────
        left_col = ft.Column([
            header,
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=4),
            tabs_row,
            ft.Divider(height=1, color=BORDER),
            self._filter_row,
            self._versions_lv,
            self._desc_panel,
            self._gallery_panel,
        ], spacing=0, expand=True)

        # ── RIGHT SIDEBAR ─────────────────────────────────────────────────────
        # Compatibility MC versions — will be filled after fetch
        self._compat_versions_row = ft.Row([], wrap=True, spacing=6, run_spacing=6)
        self._compat_loaders_row  = ft.Row([], wrap=True, spacing=6, run_spacing=6)
        self._compat_env_row      = ft.Row([], wrap=True, spacing=6, run_spacing=6)

        def _sidebar_section(title: str, body: ft.Control) -> ft.Container:
            return ft.Container(
                padding=ft.padding.only(bottom=16),
                content=ft.Column([
                    ft.Text(title, color=TEXT_PRI, size=11,
                            weight=ft.FontWeight.BOLD),
                    ft.Container(height=8),
                    body,
                ], spacing=0),
            )

        def _link_row(icon, label: str, url: str) -> ft.Container:
            txt = ft.Text(label, color=TEXT_SEC, size=11)
            return ft.Container(
                padding=ft.padding.symmetric(vertical=3),
                on_click=lambda e, u=url: self.page.launch_url(u),
                on_hover=lambda e, t=txt: (
                    setattr(t, "color", GREEN if e.data == "true" else TEXT_SEC)
                    or t.update()
                ),
                content=ft.Row([
                    ft.Icon(icon, size=13, color=TEXT_DIM),
                    ft.Container(width=8),
                    txt,
                    ft.Container(expand=True),
                    ft.Icon(ft.icons.OPEN_IN_NEW_ROUNDED, size=10, color=TEXT_DIM),
                ], spacing=0, tight=False),
            )

        slug = getattr(self.project, "slug", "")
        proj_url = f"https://modrinth.com/mod/{slug}"

        sidebar = ft.Container(
            width=200,
            padding=ft.padding.only(left=20),
            border=ft.border.only(left=ft.BorderSide(1, BORDER)),
            content=ft.Column([
                _sidebar_section("Compatibility", ft.Column([
                    ft.Text("Minecraft: Java Edition",
                            color=TEXT_DIM, size=9, weight=ft.FontWeight.W_500),
                    ft.Container(height=6),
                    self._compat_versions_row,
                ], spacing=0)),
                _sidebar_section("Platforms", self._compat_loaders_row),
                _sidebar_section("Supported environments", self._compat_env_row),
                _sidebar_section("Links", ft.Column([
                    _link_row(ft.icons.BUG_REPORT_ROUNDED,
                              "Report issues", f"{proj_url}/issues"),
                    _link_row(ft.icons.CODE_ROUNDED,
                              "View source", proj_url),
                    _link_row(ft.icons.MENU_BOOK_ROUNDED,
                              "Visit wiki", proj_url),
                ], spacing=0)),
            ], spacing=0, scroll=ft.ScrollMode.AUTO),
        )

        # ── INSTALL SELECTED BUTTON ───────────────────────────────────────────
        self._install_sel_btn = ft.ElevatedButton(
            "Install selected version",
            bgcolor=GREEN, color=TEXT_INV, disabled=True,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=20, vertical=12),
            ),
            icon=ft.icons.DOWNLOAD_ROUNDED,
            on_click=self._do_install,
        )

        # ── DIALOG ────────────────────────────────────────────────────────────
        self._dlg = ft.AlertDialog(
            bgcolor=CARD_BG,
            title=ft.Container(),           # empty title — header is in content
            content=ft.Container(
                width=920,
                content=ft.Row([
                    ft.Container(content=left_col, expand=True),
                    sidebar,
                ], vertical_alignment=ft.CrossAxisAlignment.START, spacing=0),
            ),
            actions=[
                ft.TextButton(
                    "Close",
                    style=ft.ButtonStyle(color=TEXT_SEC),
                    on_click=lambda e: self.page.close(self._dlg),
                ),
                self._install_sel_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        self.page.open(self._dlg)

    # ── Quick-install button in header ────────────────────────────────────────
    def _make_install_btn(self) -> ft.Container:
        btn = ft.Container(
            bgcolor=GREEN, border_radius=8,
            padding=ft.padding.symmetric(horizontal=20, vertical=10),
            animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
            on_click=lambda e: self._quick_install_latest(),
            content=ft.Row([
                ft.Icon(ft.icons.DOWNLOAD_ROUNDED, size=16, color=TEXT_INV),
                ft.Container(width=8),
                ft.Text("Install", color=TEXT_INV, size=13,
                        weight=ft.FontWeight.W_600),
            ], spacing=0, tight=True),
        )
        btn.on_hover = lambda e, b=btn: (
            setattr(b, "bgcolor", GREEN_DIM if e.data == "true" else GREEN)
            or b.update()
        )
        return btn

    # ══════════════════════════════════════════════════════════════════════════
    #  TABS
    # ══════════════════════════════════════════════════════════════════════════
    def _switch_tab(self, idx: int):
        self._active_tab = idx
        for i, btn in enumerate(self._tab_btns):
            d = btn.data
            d["label"].color     = TEXT_PRI if i == idx else TEXT_SEC
            d["underline"].bgcolor = GREEN if i == idx else "transparent"
            try:
                d["label"].update()
                d["underline"].update()
            except Exception:
                pass

        self._versions_lv.visible   = (idx == 0)
        self._filter_row.visible    = (idx == 0) and bool(self._versions)
        self._desc_panel.visible    = (idx == 1)
        self._gallery_panel.visible = (idx == 2)
        try:
            self._versions_lv.update()
            self._filter_row.update()
            self._desc_panel.update()
            self._gallery_panel.update()
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    #  FETCH versions
    # ══════════════════════════════════════════════════════════════════════════
    def _fetch_versions(self):
        try:
            mc_ver   = (getattr(self.active_profile, "version_id", None)
                        if self.active_profile else None)
            versions = self.app.modrinth_service.get_project_versions(
                self.project.project_id,
                mc_version=None,
                loader=self.active_loader,
            )
            self.page.run_thread(lambda: self._on_versions_loaded(versions, mc_ver))
        except Exception as err:
            def _e():
                self._spinner_row.visible = False
                self._status_lbl.value    = f"Error loading versions: {err}"
                self._status_lbl.visible  = True
                try:
                    self._spinner_row.update()
                    self._status_lbl.update()
                except Exception:
                    pass
            self.page.run_thread(_e)

    # ══════════════════════════════════════════════════════════════════════════
    #  VERSIONS LOADED
    # ══════════════════════════════════════════════════════════════════════════
    def _on_versions_loaded(self, versions, mc_ver: str | None):
        self._versions            = versions
        self._spinner_row.visible = False

        if not versions:
            self._status_lbl.value   = "No versions available."
            self._status_lbl.visible = True
            try:
                self._spinner_row.update()
                self._status_lbl.update()
            except Exception:
                pass
            return

        # ── Populate sidebar compat chips ─────────────────────────────────────
        all_mc_vers  = sorted({gv for v in versions for gv in v.game_versions},
                               reverse=True)
        all_loaders  = sorted({ld for v in versions for ld in v.loaders})
        all_channels = sorted({getattr(v, "version_type", "release") for v in versions})

        def _compat_chip(label: str, active: bool = False) -> ft.Container:
            return ft.Container(
                bgcolor=INPUT_BG if not active else GREEN,
                border=ft.border.all(1, GREEN if active else BORDER),
                border_radius=5,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                content=ft.Text(label,
                                color=TEXT_INV if active else TEXT_SEC,
                                size=10, weight=ft.FontWeight.W_500),
            )

        def _loader_chip(label: str) -> ft.Container:
            ico_map = {
                "fabric":   ft.icons.DIAMOND_OUTLINED,
                "forge":    ft.icons.LOCAL_FIRE_DEPARTMENT_ROUNDED,
                "neoforge": ft.icons.WHATSHOT_ROUNDED,
                "quilt":    ft.icons.GRID_ON_ROUNDED,
            }
            ico = ico_map.get(label.lower(), ft.icons.EXTENSION_ROUNDED)
            return ft.Container(
                bgcolor=INPUT_BG, border=ft.border.all(1, BORDER),
                border_radius=5,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                content=ft.Row([
                    ft.Icon(ico, size=11, color=TEXT_DIM),
                    ft.Container(width=5),
                    ft.Text(label.capitalize(), color=TEXT_SEC,
                            size=10, weight=ft.FontWeight.W_500),
                ], spacing=0, tight=True),
            )

        self._compat_versions_row.controls = [
            _compat_chip(v, active=(v == mc_ver)) for v in all_mc_vers[:8]
        ]
        self._compat_loaders_row.controls = [
            _loader_chip(ld) for ld in all_loaders
        ]
        self._compat_env_row.controls = [
            _compat_chip("Client-side"),
        ]

        try:
            self._compat_versions_row.update()
            self._compat_loaders_row.update()
            self._compat_env_row.update()
        except Exception:
            pass

        # ── Populate filter dropdowns ─────────────────────────────────────────
        self._platform_dd.options = (
            [ft.dropdown.Option("", "All")] +
            [ft.dropdown.Option(ld, ld.capitalize()) for ld in all_loaders]
        )
        self._mcver_dd.options = (
            [ft.dropdown.Option("", "All")] +
            [ft.dropdown.Option(v, v) for v in all_mc_vers]
        )
        self._channel_dd.options = (
            [ft.dropdown.Option("", "All")] +
            [ft.dropdown.Option(c, c.capitalize()) for c in all_channels]
        )
        # Pre-select profile's mc_ver if available
        if mc_ver and mc_ver in all_mc_vers:
            self._mcver_dd.value    = mc_ver
            self._filter_mcver      = mc_ver
        if self.active_loader and self.active_loader in all_loaders:
            self._platform_dd.value  = self.active_loader
            self._filter_platform    = self.active_loader

        self._filter_row.visible = True

        try:
            self._platform_dd.update()
            self._mcver_dd.update()
            self._channel_dd.update()
            self._filter_row.update()
        except Exception:
            pass

        # ── Status label ──────────────────────────────────────────────────────
        count_compat = sum(
            1 for v in versions
            if not mc_ver or mc_ver in v.game_versions
        )
        self._status_lbl.value = (
            f"{len(versions)} versions  ·  "
            f"{count_compat} compatible with {mc_ver or 'any version'}"
        )
        self._status_lbl.visible = True

        try:
            self._spinner_row.update()
            self._status_lbl.update()
        except Exception:
            pass

        self._render_version_rows()

    # ══════════════════════════════════════════════════════════════════════════
    #  RENDER rows
    # ══════════════════════════════════════════════════════════════════════════
    def _render_version_rows(self):
        mc_ver = (getattr(self.active_profile, "version_id", None)
                  if self.active_profile else None)

        def _passes(v) -> bool:
            if self._filter_platform:
                if self._filter_platform not in v.loaders:
                    return False
            if self._filter_mcver:
                if self._filter_mcver not in v.game_versions:
                    return False
            if self._filter_channel:
                if getattr(v, "version_type", "release") != self._filter_channel:
                    return False
            return True

        filtered = [v for v in self._versions if _passes(v)]

        self._versions_col.controls.clear()

        if not filtered:
            self._versions_col.controls.append(
                ft.Container(
                    padding=ft.padding.symmetric(vertical=24),
                    alignment=ft.alignment.center,
                    content=ft.Text("No versions match the selected filters.",
                                    color=TEXT_DIM, size=11),
                )
            )
        else:
            for v in filtered:
                self._versions_col.controls.append(
                    self._make_version_row(v, mc_ver))

        try:
            self._versions_col.update()
        except Exception:
            pass

    def _make_version_row(self, v, mc_ver: str | None) -> ft.Container:
        compatible  = not mc_ver or mc_ver in v.game_versions
        primary     = v.get_primary_file()
        filename    = primary.get("filename", "—") if primary else "—"
        ver_type    = getattr(v, "version_type", "release")
        chan_color  = self._CHANNEL_COLORS.get(ver_type, TEXT_DIM)
        date_str    = _rel_date(getattr(v, "date_published", ""))
        downloads   = getattr(v, "downloads", 0)

        # Loader pills
        loader_pills = ft.Row(
            [self._mini_loader_chip(ld) for ld in (v.loaders or [])[:2]],
            spacing=4, tight=True,
        )

        row = ft.Container(
            bgcolor="transparent",
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            animate=ft.animation.Animation(100, ft.AnimationCurve.EASE_OUT),
            data=v.version_id,
            on_click=(lambda e, ver=v: self._select_version(ver)) if compatible else None,
            content=ft.Row([
                # Channel dot
                ft.Container(
                    width=8, height=8, border_radius=4,
                    bgcolor=chan_color,
                    tooltip=ver_type.capitalize(),
                ),
                ft.Container(width=10),
                # Name + filename
                ft.Column([
                    ft.Text(v.name,
                            color=TEXT_PRI if compatible else TEXT_DIM,
                            size=12, weight=ft.FontWeight.W_600),
                    ft.Text(filename, color=TEXT_DIM, size=9,
                            overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=1, expand=True),
                # Game version
                ft.Container(
                    width=110,
                    content=ft.Text(
                        ", ".join(v.game_versions[:2]),
                        color=TEXT_DIM, size=10,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ),
                # Platforms
                ft.Container(width=120, content=loader_pills),
                # Published
                ft.Container(
                    width=110,
                    content=ft.Text(date_str or "—", color=TEXT_DIM, size=10),
                ),
                # Downloads
                ft.Container(
                    width=80,
                    content=ft.Text(_human(downloads), color=TEXT_DIM, size=10),
                ),
                # Actions
                ft.Container(
                    width=60,
                    content=ft.Row([
                        ft.IconButton(
                            icon=ft.icons.DOWNLOAD_ROUNDED,
                            icon_color=TEXT_DIM,
                            icon_size=16,
                            tooltip="Download",
                            on_click=(lambda e, ver=v: self._select_and_install(ver))
                                     if compatible else None,
                        ),
                        ft.IconButton(
                            icon=ft.icons.OPEN_IN_NEW_ROUNDED,
                            icon_color=TEXT_DIM,
                            icon_size=14,
                            tooltip="Open on Modrinth",
                            on_click=lambda e, s=getattr(self.project, "slug", ""):
                                self.page.launch_url(f"https://modrinth.com/mod/{s}"),
                        ),
                    ], spacing=0, tight=True),
                ),
            ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        def _hover(e, r=row):
            r.bgcolor = "#1a2030" if e.data == "true" else "transparent"
            try: r.update()
            except Exception: pass

        if compatible:
            row.on_hover = _hover

        return row

    def _mini_loader_chip(self, label: str) -> ft.Container:
        return ft.Container(
            bgcolor="#1f2937", border_radius=4,
            padding=ft.padding.symmetric(horizontal=6, vertical=3),
            content=ft.Text(label.capitalize(), color=TEXT_SEC,
                            size=9, weight=ft.FontWeight.W_500),
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  FILTERS
    # ══════════════════════════════════════════════════════════════════════════
    def _on_platform_change(self, e):
        self._filter_platform = self._platform_dd.value or None
        self._render_version_rows()

    def _on_mcver_change(self, e):
        self._filter_mcver = self._mcver_dd.value or None
        self._render_version_rows()

    def _on_channel_change(self, e):
        self._filter_channel = self._channel_dd.value or None
        self._render_version_rows()

    # ══════════════════════════════════════════════════════════════════════════
    #  SELECTION + INSTALL
    # ══════════════════════════════════════════════════════════════════════════
    def _select_version(self, version):
        self._selected_ver             = version
        self._install_sel_btn.disabled = False
        for c in self._versions_col.controls:
            if hasattr(c, "data") and c.data:
                is_sel = c.data == version.version_id
                c.bgcolor = "#162820" if is_sel else "transparent"
                try: c.update()
                except Exception: pass
        try: self._install_sel_btn.update()
        except Exception: pass

    def _select_and_install(self, version):
        self._select_version(version)
        self._do_install(None)

    def _quick_install_latest(self):
        """Install the first compatible version directly."""
        if not self._versions:
            self.app.snack("Versions still loading, try again.", error=True)
            return
        mc_ver = (getattr(self.active_profile, "version_id", None)
                  if self.active_profile else None)
        best = next(
            (v for v in self._versions
             if not mc_ver or mc_ver in v.game_versions),
            self._versions[0]
        )
        self._select_and_install(best)

    def _do_install(self, e):
        if not self._selected_ver or not self.active_profile:
            self.app.snack("Select an active profile first.", error=True)
            return
        self._install_sel_btn.disabled = True
        self._status_lbl.value         = f"Downloading {self._selected_ver.name}…"
        self._status_lbl.visible       = True
        try:
            self._install_sel_btn.update()
            self._status_lbl.update()
        except Exception:
            pass

        ver  = self._selected_ver
        prof = self.active_profile

        def do():
            try:
                target = self.target_dir or getattr(prof, "mods_dir", None)
                os.makedirs(target, exist_ok=True)
                self.app.modrinth_service.download_mod_version(ver, target)

                def done():
                    self._status_lbl.value         = "✓ Installed successfully"
                    self._install_sel_btn.disabled = False
                    try:
                        self._status_lbl.update()
                        self._install_sel_btn.update()
                    except Exception:
                        pass
                    self.app.snack(
                        f"{self.project.title} installed in {prof.name}. ✓")
                    if self.on_installed:
                        self.on_installed()

                self.page.run_thread(done)
            except Exception as err:
                def _e(err=err):
                    self._status_lbl.value         = f"Error: {err}"
                    self._install_sel_btn.disabled = False
                    try:
                        self._status_lbl.update()
                        self._install_sel_btn.update()
                    except Exception:
                        pass
                self.page.run_thread(_e)

        threading.Thread(target=do, daemon=True).start()