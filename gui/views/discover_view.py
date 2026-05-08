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
from gui.views.mod_detail_dialog import ModDetailDialog

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
# -*- coding: utf-8 -*-
"""
mod_detail_dialog.py
Dialog de detalle de mod estilo Modrinth App — versión premium.

Mejoras respecto al original:
  • Descripción real (body del proyecto) con scroll y renderizado de Markdown básico
  • Galería real con imágenes del proyecto (grid responsivo)
  • version_type y downloads correctamente leídos desde la API
  • Header con banner de color, stats con iconos y animaciones
  • Versiones: canal, plataforma, fecha y descargas reales
  • Sidebar con chips animados y links funcionales
  • Animaciones de hover y selección en toda la UI
"""

import os
import threading
import hashlib
import urllib.request
from datetime import datetime, timezone

import flet as ft

from gui.theme import (
    CARD_BG, CARD2_BG, INPUT_BG, BORDER, BORDER_BRIGHT,
    GREEN, GREEN_DIM, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_IMG_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache", "images")
os.makedirs(_IMG_CACHE_DIR, exist_ok=True)


def _cached_src(url: str) -> str:
    """Descarga la imagen si no está en caché y devuelve el path local."""
    if not url:
        return ""
    ext  = os.path.splitext(url.split("?")[0])[-1][:5] or ".png"
    name = hashlib.md5(url.encode()).hexdigest() + ext
    path = os.path.join(_IMG_CACHE_DIR, name)
    if os.path.exists(path):
        return path
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PyLauncher/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
        return path
    except Exception:
        return url


def _human(n: int) -> str:
    """Convierte un número grande en formato legible: 1.2M, 34.5K, etc."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _rel_date(iso: str) -> str:
    """Convierte una fecha ISO a 'hace X días/meses'."""
    if not iso:
        return ""
    try:
        dt   = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        diff = (datetime.now(timezone.utc) - dt).days
        if diff == 0:
            return "hoy"
        if diff == 1:
            return "ayer"
        if diff < 30:
            return f"hace {diff}d"
        if diff < 365:
            return f"hace {diff // 30}m"
        return f"hace {diff // 365}a"
    except Exception:
        return iso[:10]


def _icon_widget(url: str, title: str, size: int = 48) -> ft.Control:
    """Ícono del mod con fallback de letras si no hay imagen."""
    fallback = ft.Container(
        width=size, height=size, border_radius=size // 5,
        bgcolor=INPUT_BG,
        border=ft.border.all(1, BORDER),
        alignment=ft.alignment.center,
        content=ft.Text(
            (title[:2] if title else "??").upper(),
            color=TEXT_SEC, size=size // 3,
            weight=ft.FontWeight.BOLD,
        ),
    )
    if not url:
        return fallback
    return ft.Container(
        width=size, height=size, border_radius=size // 5,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        shadow=[ft.BoxShadow(
            spread_radius=0, blur_radius=12,
            color=ft.colors.with_opacity(0.25, GREEN),
            offset=ft.Offset(0, 4),
        )],
        content=ft.Image(
            src=url, width=size, height=size,
            fit=ft.ImageFit.COVER,
            error_content=fallback,
        ),
    )


def _cat_chip(label: str) -> ft.Container:
    return ft.Container(
        bgcolor=ft.colors.with_opacity(0.08, GREEN),
        border=ft.border.all(1, ft.colors.with_opacity(0.25, GREEN)),
        border_radius=5,
        padding=ft.padding.symmetric(horizontal=7, vertical=3),
        content=ft.Text(label.capitalize(), color=GREEN, size=9,
                        weight=ft.FontWeight.W_600),
    )


# ── Colores de canal ──────────────────────────────────────────────────────────
_CHANNEL_COLORS = {
    "release": "#27ae60",
    "beta":    "#e67e22",
    "alpha":   "#e74c3c",
}

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


# ══════════════════════════════════════════════════════════════════════════════
#  ModDetailDialog
# ══════════════════════════════════════════════════════════════════════════════
class ModDetailDialog:
    """
    Dialog de detalle de mod al estilo Modrinth — diseño premium.

    Pestañas:
      • Versiones  — tabla con filtros de plataforma, versión MC y canal
      • Descripción — body completo del proyecto con scroll
      • Galería    — grid de imágenes del proyecto

    Sidebar:
      • Compatibilidad (chips de versiones MC)
      • Plataformas (loaders)
      • Entornos soportados
      • Links (Modrinth, issues, source)
    """

    def __init__(self, page, app, project, active_profile,
                 active_loader, target_dir=None, on_installed=None):
        self.page           = page
        self.app            = app
        self.project        = project
        self.active_profile = active_profile
        self.active_loader  = active_loader
        self.target_dir     = target_dir
        self.on_installed   = on_installed

        self._versions: list  = []
        self._selected_ver    = None
        self._active_tab: int = 0   # 0=Versions 1=Description 2=Gallery

        # Estado de filtros
        self._filter_platform: str | None = None
        self._filter_mcver:    str | None = None
        self._filter_channel:  str | None = None

        self._build()
        threading.Thread(target=self._fetch_versions,       daemon=True).start()
        threading.Thread(target=self._fetch_project_details, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    #  BUILD
    # ══════════════════════════════════════════════════════════════════════════
    def _build(self):
        cats      = getattr(self.project, "categories", []) or []
        follows   = getattr(self.project, "follows", 0)

        # ── HEADER ────────────────────────────────────────────────────────────
        #   Banda de color superior + icono + metadatos + botón instalar
        accent_bar = ft.Container(
            height=3,
            border_radius=ft.border_radius.only(top_left=12, top_right=12),
            gradient=ft.LinearGradient(
                begin=ft.alignment.center_left,
                end=ft.alignment.center_right,
                colors=[GREEN, ft.colors.with_opacity(0.3, GREEN)],
            ),
        )

        header_content = ft.Container(
            padding=ft.padding.only(left=24, right=24, top=20, bottom=16),
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left,
                end=ft.alignment.bottom_right,
                colors=[ft.colors.with_opacity(0.08, GREEN), "transparent"],
            ),
            content=ft.Row([
                _icon_widget(self.project.icon_url, self.project.title, size=72),
                ft.Container(width=20),
                ft.Column([
                    # Título
                    ft.Text(self.project.title,
                            color=TEXT_PRI, size=22,
                            weight=ft.FontWeight.BOLD),
                    ft.Container(height=3),
                    # Descripción corta
                    ft.Text(
                        (self.project.description[:160] + "…"
                         if len(self.project.description) > 160
                         else self.project.description),
                        color=TEXT_SEC, size=11, max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Container(height=10),
                    # Stats row
                    ft.Row([
                        # Descargas
                        ft.Container(
                            bgcolor=ft.colors.with_opacity(0.07, GREEN),
                            border=ft.border.all(1, ft.colors.with_opacity(0.2, GREEN)),
                            border_radius=6,
                            padding=ft.padding.symmetric(horizontal=9, vertical=4),
                            content=ft.Row([
                                ft.Icon(ft.icons.DOWNLOAD_ROUNDED,
                                        size=12, color=GREEN),
                                ft.Container(width=5),
                                ft.Text(_human(self.project.downloads),
                                        color=GREEN, size=11,
                                        weight=ft.FontWeight.W_600),
                            ], spacing=0, tight=True),
                        ),
                        ft.Container(width=8),
                        # Followers
                        ft.Container(
                            bgcolor=INPUT_BG,
                            border=ft.border.all(1, BORDER),
                            border_radius=6,
                            padding=ft.padding.symmetric(horizontal=9, vertical=4),
                            content=ft.Row([
                                ft.Icon(ft.icons.FAVORITE_BORDER_ROUNDED,
                                        size=12, color=TEXT_DIM),
                                ft.Container(width=5),
                                ft.Text(_human(follows) if follows else "—",
                                        color=TEXT_SEC, size=11,
                                        weight=ft.FontWeight.W_600),
                            ], spacing=0, tight=True),
                        ),
                        ft.Container(width=12),
                        # Categorías
                        *[_cat_chip(c) for c in cats[:3]],
                    ], spacing=0, tight=True, wrap=False),
                ], spacing=0, expand=True),
                ft.Container(width=16),
                # Botón instalar rápido
                self._make_install_btn(),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        header = ft.Column([accent_bar, header_content], spacing=0)

        # ── TABS ──────────────────────────────────────────────────────────────
        self._tab_labels = ["Versiones", "Descripción", "Galería"]
        self._tab_btns   = []
        tab_controls     = []

        for i, lbl in enumerate(self._tab_labels):
            txt = ft.Text(lbl, size=12, weight=ft.FontWeight.W_600,
                          color=TEXT_PRI if i == 0 else TEXT_SEC)
            bar = ft.Container(
                height=2, border_radius=2,
                bgcolor=GREEN if i == 0 else "transparent",
                animate=ft.animation.Animation(160, ft.AnimationCurve.EASE_OUT),
            )
            btn = ft.Container(
                padding=ft.padding.symmetric(horizontal=18, vertical=8),
                on_click=lambda e, idx=i: self._switch_tab(idx),
                animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
                content=ft.Column(
                    [txt, ft.Container(height=5), bar],
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                data={"txt": txt, "bar": bar},
            )
            btn.on_hover = lambda e, b=btn: (
                setattr(b, "bgcolor",
                        ft.colors.with_opacity(0.04, GREEN)
                        if e.data == "true" else "transparent")
                or b.update()
            )
            self._tab_btns.append(btn)
            tab_controls.append(btn)

        tabs_row = ft.Row(tab_controls, spacing=0)

        # ── FILTROS ───────────────────────────────────────────────────────────
        def _dd(prefix, width):
            return ft.Dropdown(
                prefix_text=f"{prefix}  ",
                prefix_style=ft.TextStyle(color=TEXT_SEC, size=11),
                hint_text="Todos",
                hint_style=ft.TextStyle(color=TEXT_DIM, size=11),
                width=width, height=36, color=TEXT_PRI,
                bgcolor=INPUT_BG,
                border_color=BORDER,
                focused_border_color=GREEN,
                border_radius=7,
                content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
                text_style=ft.TextStyle(size=11),
            )

        self._platform_dd = _dd("Plataforma", 185)
        self._mcver_dd    = _dd("MC Versión", 215)
        self._channel_dd  = _dd("Canal", 155)
        self._platform_dd.on_change = self._on_platform_change
        self._mcver_dd.on_change    = self._on_mcver_change
        self._channel_dd.on_change  = self._on_channel_change

        self._filter_row = ft.Container(
            visible=False,
            padding=ft.padding.only(top=12, bottom=6),
            content=ft.Row([
                ft.Container(
                    bgcolor=INPUT_BG, border=ft.border.all(1, BORDER),
                    border_radius=7,
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    content=ft.Icon(ft.icons.FILTER_LIST_ROUNDED,
                                    size=14, color=TEXT_DIM),
                ),
                ft.Container(width=10),
                self._platform_dd,
                ft.Container(width=8),
                self._mcver_dd,
                ft.Container(width=8),
                self._channel_dd,
            ], spacing=0, tight=True),
        )

        # ── TABLA DE VERSIONES ────────────────────────────────────────────────
        def _th(label, width=None, expand=False):
            return ft.Container(
                width=width, expand=expand,
                content=ft.Text(label, color=TEXT_DIM, size=9,
                                weight=ft.FontWeight.BOLD),
            )

        table_header = ft.Container(
            padding=ft.padding.symmetric(horizontal=16, vertical=9),
            bgcolor=ft.colors.with_opacity(0.03, GREEN),
            border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
            content=ft.Row([
                ft.Container(width=20),   # dot canal
                ft.Container(width=10),
                _th("NOMBRE",        expand=True),
                _th("MC VERSIÓN",    width=110),
                _th("PLATAFORMAS",   width=120),
                _th("PUBLICADO",     width=110),
                _th("DESCARGAS",     width=80),
                ft.Container(width=60),
            ], spacing=0),
        )

        self._spinner_row = ft.Row([
            ft.ProgressRing(width=16, height=16, color=GREEN, stroke_width=2),
            ft.Container(width=10),
            ft.Text("Cargando versiones…", color=TEXT_DIM, size=11),
        ], visible=True)

        self._status_lbl = ft.Text("", color=TEXT_DIM, size=10, visible=False)
        self._versions_col = ft.Column([], spacing=0)

        self._versions_lv = ft.ListView(
            height=330,
            padding=ft.padding.only(right=4),
            controls=[
                table_header,
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=20, vertical=14),
                    content=self._spinner_row,
                ),
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=20, vertical=4),
                    content=self._status_lbl,
                ),
                self._versions_col,
            ],
        )

        # ── PANEL DESCRIPCIÓN ─────────────────────────────────────────────────
        # Spinner inicial; se rellena cuando llegue _fetch_project_details
        self._desc_spinner = ft.Container(
            padding=ft.padding.all(24),
            alignment=ft.alignment.center,
            content=ft.Row([
                ft.ProgressRing(width=14, height=14, color=GREEN, stroke_width=2),
                ft.Container(width=10),
                ft.Text("Cargando descripción…", color=TEXT_DIM, size=11),
            ], tight=True),
        )
        self._desc_body = ft.Column(
            [self._desc_spinner],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
        )
        self._desc_panel = ft.Container(
            visible=False,
            height=330,
            padding=ft.padding.only(right=4),
            content=self._desc_body,
        )

        # ── PANEL GALERÍA ─────────────────────────────────────────────────────
        self._gallery_spinner = ft.Container(
            padding=ft.padding.all(24),
            alignment=ft.alignment.center,
            content=ft.Row([
                ft.ProgressRing(width=14, height=14, color=GREEN, stroke_width=2),
                ft.Container(width=10),
                ft.Text("Cargando galería…", color=TEXT_DIM, size=11),
            ], tight=True),
        )
        self._gallery_body = ft.Column(
            [self._gallery_spinner],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
        )
        self._gallery_panel = ft.Container(
            visible=False,
            height=330,
            padding=ft.padding.only(right=4),
            content=self._gallery_body,
        )

        # ── COLUMNA IZQUIERDA ─────────────────────────────────────────────────
        left_col = ft.Column([
            header,
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=2),
            tabs_row,
            ft.Divider(height=1, color=BORDER),
            self._filter_row,
            self._versions_lv,
            self._desc_panel,
            self._gallery_panel,
        ], spacing=0, expand=True)

        # ── SIDEBAR ───────────────────────────────────────────────────────────
        self._compat_versions_row = ft.Row([], wrap=True, spacing=6, run_spacing=6)
        self._compat_loaders_row  = ft.Row([], wrap=True, spacing=6, run_spacing=6)
        self._compat_env_row      = ft.Row([], wrap=True, spacing=6, run_spacing=6)

        def _sidebar_section(title: str, body: ft.Control) -> ft.Column:
            return ft.Column([
                ft.Row([
                    ft.Container(
                        width=3, height=12, border_radius=2,
                        bgcolor=GREEN,
                        shadow=[ft.BoxShadow(
                            spread_radius=0, blur_radius=6,
                            color=ft.colors.with_opacity(0.5, GREEN),
                            offset=ft.Offset(0, 0),
                        )],
                    ),
                    ft.Container(width=8),
                    ft.Text(title.upper(), color=TEXT_DIM, size=8,
                            weight=ft.FontWeight.BOLD),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=10),
                body,
                ft.Container(height=18),
            ], spacing=0)

        def _link_btn(icon, label: str, url: str) -> ft.Container:
            txt = ft.Text(label, color=TEXT_SEC, size=11)
            c = ft.Container(
                border_radius=7,
                padding=ft.padding.symmetric(horizontal=8, vertical=6),
                on_click=lambda e, u=url: self.page.launch_url(u),
                animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
                content=ft.Row([
                    ft.Container(
                        width=26, height=26, border_radius=6,
                        bgcolor=INPUT_BG,
                        border=ft.border.all(1, BORDER),
                        alignment=ft.alignment.center,
                        content=ft.Icon(icon, size=12, color=TEXT_DIM),
                    ),
                    ft.Container(width=9),
                    txt,
                    ft.Container(expand=True),
                    ft.Icon(ft.icons.OPEN_IN_NEW_ROUNDED,
                            size=10, color=TEXT_DIM),
                ], spacing=0, tight=False),
            )

            def _hov(e, cc=c, t=txt):
                if e.data == "true":
                    cc.bgcolor = ft.colors.with_opacity(0.06, GREEN)
                    t.color    = GREEN
                else:
                    cc.bgcolor = "transparent"
                    t.color    = TEXT_SEC
                try:
                    cc.update(); t.update()
                except Exception:
                    pass

            c.on_hover = _hov
            return c

        slug     = getattr(self.project, "slug", "")
        proj_url = f"https://modrinth.com/mod/{slug}"

        sidebar = ft.Container(
            width=210,
            padding=ft.padding.only(left=22),
            border=ft.border.only(left=ft.BorderSide(1, BORDER)),
            content=ft.Column([
                _sidebar_section("Compatibilidad", ft.Column([
                    ft.Text("Minecraft: Java Edition",
                            color=TEXT_DIM, size=9,
                            weight=ft.FontWeight.W_500),
                    ft.Container(height=8),
                    self._compat_versions_row,
                ], spacing=0)),
                _sidebar_section("Plataformas", self._compat_loaders_row),
                _sidebar_section("Entornos", self._compat_env_row),
                _sidebar_section("Links", ft.Column([
                    _link_btn(ft.icons.BUG_REPORT_ROUNDED,
                              "Reportar bugs", f"{proj_url}"),
                    _link_btn(ft.icons.CODE_ROUNDED,
                              "Ver código", proj_url),
                    _link_btn(ft.icons.OPEN_IN_BROWSER_ROUNDED,
                              "Ver en Modrinth", proj_url),
                ], spacing=2)),
            ], spacing=0, scroll=ft.ScrollMode.AUTO),
        )

        # ── BOTÓN INSTALAR SELECCIONADO ───────────────────────────────────────
        self._install_sel_btn = ft.ElevatedButton(
            "Instalar versión seleccionada",
            bgcolor=GREEN, color=TEXT_INV,
            disabled=True,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=22, vertical=13),
                elevation=0,
                overlay_color=ft.colors.with_opacity(0.15, "#ffffff"),
            ),
            icon=ft.icons.DOWNLOAD_ROUNDED,
            on_click=self._do_install,
        )

        # ── DIALOG ────────────────────────────────────────────────────────────
        self._dlg = ft.AlertDialog(
            bgcolor=CARD_BG,
            shape=ft.RoundedRectangleBorder(radius=14),
            title=ft.Container(),
            content=ft.Container(
                width=940,
                content=ft.Row([
                    ft.Container(content=left_col, expand=True),
                    sidebar,
                ], vertical_alignment=ft.CrossAxisAlignment.START, spacing=0),
            ),
            actions=[
                ft.TextButton(
                    "Cerrar",
                    style=ft.ButtonStyle(color=TEXT_SEC),
                    on_click=lambda e: self.page.close(self._dlg),
                ),
                self._install_sel_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        self.page.open(self._dlg)

    # ── Botón instalar rápido (header) ────────────────────────────────────────
    def _make_install_btn(self) -> ft.Container:
        btn = ft.Container(
            bgcolor=GREEN, border_radius=9,
            padding=ft.padding.symmetric(horizontal=22, vertical=11),
            animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
            shadow=[ft.BoxShadow(
                spread_radius=0, blur_radius=12,
                color=ft.colors.with_opacity(0.35, GREEN),
                offset=ft.Offset(0, 4),
            )],
            on_click=lambda e: self._quick_install_latest(),
            content=ft.Row([
                ft.Icon(ft.icons.DOWNLOAD_ROUNDED, size=16, color=TEXT_INV),
                ft.Container(width=8),
                ft.Text("Instalar", color=TEXT_INV, size=13,
                        weight=ft.FontWeight.W_700),
            ], spacing=0, tight=True),
        )
        btn.on_hover = lambda e, b=btn: (
            setattr(b, "bgcolor", GREEN_DIM if e.data == "true" else GREEN)
            or setattr(b, "shadow", [ft.BoxShadow(
                spread_radius=0,
                blur_radius=18 if e.data == "true" else 12,
                color=ft.colors.with_opacity(0.5 if e.data == "true" else 0.35, GREEN),
                offset=ft.Offset(0, 4),
            )])
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
            active = (i == idx)
            d["txt"].color  = TEXT_PRI if active else TEXT_SEC
            d["bar"].bgcolor = GREEN if active else "transparent"
            try:
                d["txt"].update()
                d["bar"].update()
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
    #  FETCH — versiones
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
                self._status_lbl.value    = f"Error al cargar versiones: {err}"
                self._status_lbl.visible  = True
                try:
                    self._spinner_row.update()
                    self._status_lbl.update()
                except Exception:
                    pass
            self.page.run_thread(_e)

    # ══════════════════════════════════════════════════════════════════════════
    #  FETCH — detalles del proyecto (body + gallery)
    # ══════════════════════════════════════════════════════════════════════════
    def _fetch_project_details(self):
        try:
            full = self.app.modrinth_service.get_project(self.project.project_id)
            self.page.run_thread(lambda: self._on_project_details_loaded(full))
        except Exception as err:
            def _e():
                self._desc_body.controls = [
                    ft.Container(
                        padding=ft.padding.all(24),
                        alignment=ft.alignment.center,
                        content=ft.Column([
                            ft.Icon(ft.icons.ERROR_OUTLINE_ROUNDED,
                                    size=32, color=TEXT_DIM),
                            ft.Container(height=8),
                            ft.Text(f"Error: {err}", color=TEXT_DIM, size=11),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    )
                ]
                self._gallery_body.controls = self._desc_body.controls.copy()
                try:
                    self._desc_body.update()
                    self._gallery_body.update()
                except Exception:
                    pass
            self.page.run_thread(_e)

    # ══════════════════════════════════════════════════════════════════════════
    #  CALLBACK — versiones cargadas
    # ══════════════════════════════════════════════════════════════════════════
    def _on_versions_loaded(self, versions, mc_ver: str | None):
        self._versions            = versions
        self._spinner_row.visible = False

        if not versions:
            self._status_lbl.value   = "No hay versiones disponibles."
            self._status_lbl.visible = True
            try:
                self._spinner_row.update()
                self._status_lbl.update()
            except Exception:
                pass
            return

        # Chips del sidebar
        all_mc_vers  = sorted({gv for v in versions for gv in v.game_versions},
                               reverse=True)
        all_loaders  = sorted({ld for v in versions for ld in v.loaders})
        all_channels = sorted({getattr(v, "version_type", "release") for v in versions})

        def _compat_chip(label: str, active: bool = False) -> ft.Container:
            return ft.Container(
                bgcolor=ft.colors.with_opacity(0.12, GREEN) if active else INPUT_BG,
                border=ft.border.all(1, GREEN if active else BORDER),
                border_radius=5,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                content=ft.Text(label,
                                color=TEXT_INV if active else TEXT_SEC,
                                size=10, weight=ft.FontWeight.W_500),
            )

        def _loader_chip(label: str) -> ft.Container:
            ico   = _LOADER_ICONS.get(label.lower(), ft.icons.EXTENSION_ROUNDED)
            color = _LOADER_COLORS.get(label.lower(), TEXT_SEC)
            return ft.Container(
                bgcolor=ft.colors.with_opacity(0.08, color),
                border=ft.border.all(1, ft.colors.with_opacity(0.3, color)),
                border_radius=5,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                content=ft.Row([
                    ft.Icon(ico, size=11, color=color),
                    ft.Container(width=5),
                    ft.Text(label.capitalize(), color=color,
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
            _compat_chip("Cliente"),
            _compat_chip("Servidor"),
        ]

        try:
            self._compat_versions_row.update()
            self._compat_loaders_row.update()
            self._compat_env_row.update()
        except Exception:
            pass

        # Filtros
        self._platform_dd.options = (
            [ft.dropdown.Option("", "Todos")] +
            [ft.dropdown.Option(ld, ld.capitalize()) for ld in all_loaders]
        )
        self._mcver_dd.options = (
            [ft.dropdown.Option("", "Todos")] +
            [ft.dropdown.Option(v, v) for v in all_mc_vers]
        )
        self._channel_dd.options = (
            [ft.dropdown.Option("", "Todos")] +
            [ft.dropdown.Option(c, c.capitalize()) for c in all_channels]
        )

        if mc_ver and mc_ver in all_mc_vers:
            self._mcver_dd.value  = mc_ver
            self._filter_mcver    = mc_ver
        if self.active_loader and self.active_loader in all_loaders:
            self._platform_dd.value = self.active_loader
            self._filter_platform   = self.active_loader

        self._filter_row.visible = True

        try:
            self._platform_dd.update()
            self._mcver_dd.update()
            self._channel_dd.update()
            self._filter_row.update()
        except Exception:
            pass

        # Etiqueta de estado
        compat = sum(1 for v in versions
                     if not mc_ver or mc_ver in v.game_versions)
        self._status_lbl.value = (
            f"{len(versions)} versiones  ·  "
            f"{compat} compatibles con {mc_ver or 'cualquier versión'}"
        )
        self._status_lbl.visible = True

        try:
            self._spinner_row.update()
            self._status_lbl.update()
        except Exception:
            pass

        self._render_version_rows()

    # ══════════════════════════════════════════════════════════════════════════
    #  CALLBACK — detalles del proyecto cargados
    # ══════════════════════════════════════════════════════════════════════════
    def _on_project_details_loaded(self, full):
        # ── Descripción ───────────────────────────────────────────────────────
        body = getattr(full, "body", "") or self.project.description or ""
        desc_controls = self._render_markdown(body)
        self._desc_body.controls = desc_controls
        try:
            self._desc_body.update()
        except Exception:
            pass

        # ── Galería ───────────────────────────────────────────────────────────
        gallery = getattr(full, "gallery", []) or []
        if not gallery:
            self._gallery_body.controls = [
                ft.Container(
                    padding=ft.padding.all(40),
                    alignment=ft.alignment.center,
                    content=ft.Column([
                        ft.Container(
                            width=64, height=64, border_radius=32,
                            bgcolor=INPUT_BG,
                            border=ft.border.all(1, BORDER),
                            alignment=ft.alignment.center,
                            content=ft.Icon(ft.icons.PHOTO_LIBRARY_ROUNDED,
                                            size=28, color=TEXT_DIM),
                        ),
                        ft.Container(height=12),
                        ft.Text("Sin imágenes en la galería",
                                color=TEXT_DIM, size=12),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0),
                )
            ]
        else:
            items = []
            for entry in gallery:
                url   = entry.get("url", "")
                title = entry.get("title", "") or entry.get("description", "")
                if not url:
                    continue

                img_card = ft.Container(
                    border_radius=10,
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    border=ft.border.all(1, BORDER),
                    animate=ft.animation.Animation(150, ft.AnimationCurve.EASE_OUT),
                    on_click=lambda e, u=url: self.page.launch_url(u),
                    shadow=[ft.BoxShadow(
                        spread_radius=0, blur_radius=10,
                        color=ft.colors.with_opacity(0.2, "#000000"),
                        offset=ft.Offset(0, 4),
                    )],
                    content=ft.Image(
                        src=url,
                        width=870, height=220,
                        fit=ft.ImageFit.COVER,
                        error_content=ft.Container(
                            height=120, bgcolor=INPUT_BG,
                            alignment=ft.alignment.center,
                            content=ft.Column([
                                ft.Icon(ft.icons.BROKEN_IMAGE_ROUNDED,
                                        color=TEXT_DIM, size=28),
                                ft.Container(height=6),
                                ft.Text("Imagen no disponible",
                                        color=TEXT_DIM, size=10),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=0),
                        ),
                    ),
                )

                def _img_hover(e, c=img_card):
                    c.border = ft.border.all(
                        1, ft.colors.with_opacity(0.6, GREEN)
                        if e.data == "true" else BORDER)
                    try:
                        c.update()
                    except Exception:
                        pass

                img_card.on_hover = _img_hover
                items.append(img_card)

                if title:
                    items.append(ft.Container(
                        padding=ft.padding.only(top=6, bottom=2),
                        content=ft.Text(title, color=TEXT_SEC, size=10,
                                        text_align=ft.TextAlign.CENTER),
                    ))
                items.append(ft.Container(height=14))

            self._gallery_body.controls = items

        try:
            self._gallery_body.update()
        except Exception:
            pass

    # ── Renderizado de Markdown básico ────────────────────────────────────────
    def _render_markdown(self, text: str) -> list:
        """Convierte Markdown básico en controles de Flet."""
        if not text.strip():
            return [ft.Container(
                padding=ft.padding.all(24),
                alignment=ft.alignment.center,
                content=ft.Text("Sin descripción disponible.",
                                color=TEXT_DIM, size=11),
            )]

        controls = []
        paragraphs = text.split("\n\n")

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Encabezado H1
            if para.startswith("# "):
                controls.append(ft.Container(
                    padding=ft.padding.only(top=12, bottom=4),
                    content=ft.Text(
                        para[2:].strip(),
                        color=TEXT_PRI, size=16,
                        weight=ft.FontWeight.BOLD,
                    ),
                ))
                controls.append(ft.Divider(height=1, color=BORDER))
                controls.append(ft.Container(height=4))

            # Encabezado H2
            elif para.startswith("## "):
                controls.append(ft.Container(
                    padding=ft.padding.only(top=10, bottom=2),
                    content=ft.Text(
                        para[3:].strip(),
                        color=TEXT_PRI, size=13,
                        weight=ft.FontWeight.BOLD,
                    ),
                ))

            # Encabezado H3
            elif para.startswith("### "):
                controls.append(ft.Container(
                    padding=ft.padding.only(top=8, bottom=2),
                    content=ft.Text(
                        para[4:].strip(),
                        color=TEXT_SEC, size=12,
                        weight=ft.FontWeight.W_600,
                    ),
                ))

            # Lista
            elif any(line.startswith(("- ", "* ", "+ "))
                     for line in para.splitlines()):
                for line in para.splitlines():
                    clean = line.lstrip("-*+ ").strip()
                    if not clean:
                        continue
                    clean = clean.replace("**", "").replace("__", "")
                    controls.append(ft.Container(
                        padding=ft.padding.only(left=14, bottom=3),
                        content=ft.Row([
                            ft.Container(
                                width=5, height=5, border_radius=3,
                                bgcolor=GREEN,
                                margin=ft.margin.only(top=4, right=8),
                            ),
                            ft.Text(clean, color=TEXT_SEC, size=11, expand=True),
                        ], vertical_alignment=ft.CrossAxisAlignment.START,
                        spacing=0, tight=True),
                    ))

            # Bloque de código
            elif para.startswith("```"):
                code = para.strip("`").strip()
                first_line = code.split("\n")[0]
                if first_line in ("python", "java", "json", "bash", "sh", "xml"):
                    code = "\n".join(code.split("\n")[1:])
                controls.append(ft.Container(
                    bgcolor=CARD2_BG,
                    border=ft.border.all(1, BORDER),
                    border_radius=8,
                    padding=ft.padding.all(12),
                    content=ft.Text(
                        code.strip(), color=TEXT_SEC,
                        size=10, font_family="monospace",
                    ),
                ))
                controls.append(ft.Container(height=6))

            # Párrafo normal
            else:
                clean = para.replace("**", "").replace("__", "").replace("`", "")
                controls.append(ft.Container(
                    padding=ft.padding.only(bottom=8),
                    content=ft.Text(clean, color=TEXT_SEC, size=11,
                                    selectable=True),
                ))

        return controls if controls else [
            ft.Text("Sin descripción disponible.", color=TEXT_DIM, size=11)
        ]

    # ══════════════════════════════════════════════════════════════════════════
    #  RENDER filas de versión
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
                    padding=ft.padding.symmetric(vertical=30),
                    alignment=ft.alignment.center,
                    content=ft.Column([
                        ft.Icon(ft.icons.SEARCH_OFF_ROUNDED,
                                size=32, color=TEXT_DIM),
                        ft.Container(height=8),
                        ft.Text("Ninguna versión coincide con los filtros.",
                                color=TEXT_DIM, size=11),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0),
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
        compatible = not mc_ver or mc_ver in v.game_versions
        primary    = v.get_primary_file()
        filename   = primary.get("filename", "—") if primary else "—"
        ver_type   = getattr(v, "version_type", "release")
        chan_color  = _CHANNEL_COLORS.get(ver_type, TEXT_DIM)
        date_str   = _rel_date(getattr(v, "date_published", ""))
        downloads  = getattr(v, "downloads", 0)

        loader_pills = ft.Row(
            [self._mini_loader_chip(ld) for ld in (v.loaders or [])[:2]],
            spacing=4, tight=True,
        )

        # Indicador de compatibilidad
        compat_indicator = ft.Container(
            width=3, height=28, border_radius=2,
            bgcolor=ft.colors.with_opacity(0.6, GREEN)
                    if compatible else "transparent",
        ) if compatible else ft.Container(width=3)

        row = ft.Container(
            bgcolor="transparent",
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            animate=ft.animation.Animation(100, ft.AnimationCurve.EASE_OUT),
            data=v.version_id,
            on_click=(lambda e, ver=v: self._select_version(ver))
                     if compatible else None,
            content=ft.Row([
                compat_indicator,
                ft.Container(width=6),
                # Dot de canal
                ft.Container(
                    width=8, height=8, border_radius=4,
                    bgcolor=chan_color,
                    tooltip=ver_type.capitalize(),
                    shadow=[ft.BoxShadow(
                        spread_radius=0, blur_radius=5,
                        color=ft.colors.with_opacity(0.5, chan_color),
                        offset=ft.Offset(0, 0),
                    )],
                ),
                ft.Container(width=12),
                # Nombre + archivo
                ft.Column([
                    ft.Text(v.name,
                            color=TEXT_PRI if compatible else TEXT_DIM,
                            size=12, weight=ft.FontWeight.W_600),
                    ft.Text(filename, color=TEXT_DIM, size=9,
                            overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=1, expand=True),
                # MC Versión
                ft.Container(
                    width=110,
                    content=ft.Text(
                        ", ".join(v.game_versions[:2]),
                        color=TEXT_DIM, size=10,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ),
                # Plataformas
                ft.Container(width=120, content=loader_pills),
                # Publicado
                ft.Container(
                    width=110,
                    content=ft.Text(date_str or "—",
                                    color=TEXT_DIM, size=10),
                ),
                # Descargas
                ft.Container(
                    width=80,
                    content=ft.Row([
                        ft.Icon(ft.icons.DOWNLOAD_ROUNDED,
                                size=10, color=TEXT_DIM),
                        ft.Container(width=3),
                        ft.Text(_human(downloads), color=TEXT_DIM, size=10),
                    ], spacing=0, tight=True),
                ),
                # Acciones
                ft.Container(
                    width=60,
                    content=ft.Row([
                        ft.IconButton(
                            icon=ft.icons.DOWNLOAD_ROUNDED,
                            icon_color=TEXT_DIM,
                            icon_size=16,
                            tooltip="Descargar",
                            on_click=(lambda e, ver=v: self._select_and_install(ver))
                                     if compatible else None,
                        ),
                        ft.IconButton(
                            icon=ft.icons.OPEN_IN_NEW_ROUNDED,
                            icon_color=TEXT_DIM,
                            icon_size=14,
                            tooltip="Abrir en Modrinth",
                            on_click=lambda e, s=getattr(self.project, "slug", ""):
                                self.page.launch_url(
                                    f"https://modrinth.com/mod/{s}"),
                        ),
                    ], spacing=0, tight=True),
                ),
            ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        def _hover(e, r=row):
            if e.data == "true":
                r.bgcolor = ft.colors.with_opacity(0.06, GREEN) if compatible \
                            else "#141920"
            else:
                # Mantener fondo si está seleccionado
                is_sel = (self._selected_ver is not None and
                          self._selected_ver.version_id == r.data)
                r.bgcolor = "#162820" if is_sel else "transparent"
            try:
                r.update()
            except Exception:
                pass

        if compatible:
            row.on_hover = _hover

        return row

    def _mini_loader_chip(self, label: str) -> ft.Container:
        color = _LOADER_COLORS.get(label.lower(), TEXT_DIM)
        return ft.Container(
            bgcolor=ft.colors.with_opacity(0.1, color),
            border=ft.border.all(1, ft.colors.with_opacity(0.25, color)),
            border_radius=4,
            padding=ft.padding.symmetric(horizontal=6, vertical=2),
            content=ft.Text(label.capitalize(), color=color,
                            size=9, weight=ft.FontWeight.W_500),
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  FILTROS
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
    #  SELECCIÓN + INSTALACIÓN
    # ══════════════════════════════════════════════════════════════════════════
    def _select_version(self, version):
        self._selected_ver             = version
        self._install_sel_btn.disabled = False
        for c in self._versions_col.controls:
            if hasattr(c, "data") and c.data:
                is_sel = c.data == version.version_id
                c.bgcolor = "#162820" if is_sel else "transparent"
                try:
                    c.update()
                except Exception:
                    pass
        try:
            self._install_sel_btn.update()
        except Exception:
            pass

    def _select_and_install(self, version):
        self._select_version(version)
        self._do_install(None)

    def _quick_install_latest(self):
        """Instala la primera versión compatible directamente."""
        if not self._versions:
            self.app.snack("Las versiones aún se están cargando.", error=True)
            return
        mc_ver = (getattr(self.active_profile, "version_id", None)
                  if self.active_profile else None)
        best = next(
            (v for v in self._versions
             if not mc_ver or mc_ver in v.game_versions),
            self._versions[0],
        )
        self._select_and_install(best)

    def _do_install(self, e):
        if not self._selected_ver or not self.active_profile:
            self.app.snack("Selecciona un perfil activo primero.", error=True)
            return

        self._install_sel_btn.disabled = True
        self._status_lbl.value         = f"⬇  Descargando {self._selected_ver.name}…"
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
                    self._status_lbl.value         = "✓  Instalado correctamente"
                    self._install_sel_btn.disabled = False
                    try:
                        self._status_lbl.update()
                        self._install_sel_btn.update()
                    except Exception:
                        pass
                    self.app.snack(
                        f"{self.project.title} instalado en {prof.name}. ✓")
                    if self.on_installed:
                        self.on_installed()

                self.page.run_thread(done)

            except Exception as err:
                def _e(err=err):
                    self._status_lbl.value         = f"✗  Error: {err}"
                    self._install_sel_btn.disabled = False
                    try:
                        self._status_lbl.update()
                        self._install_sel_btn.update()
                    except Exception:
                        pass
                self.page.run_thread(_e)

        threading.Thread(target=do, daemon=True).start()