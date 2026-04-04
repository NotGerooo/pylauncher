# -*- coding: utf-8 -*-
"""
gui/views/discover_view.py
Diseño inspirado en Modrinth App:
 - Header con nombre de instancia (si viene de una) + Back
 - Tabs pill: Mods / Resource Packs / Data Packs / Shaders / Modpacks
 - Barra de búsqueda full-width
 - Sort by + View (page size) + paginación numérica a la derecha
 - Chips de versión MC + loader activo
 - Cards grandes estilo Modrinth: icon izq, stats der, chips abajo
 - Diálogo de detalle con lista de versiones
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
from utils.icon_cache import get_author as cache_get_author
from utils.install_detector import build_installed_set, is_installed_in
from utils.logger import get_logger

log = get_logger()

# ── Constantes ─────────────────────────────────────────────────────────────────
LOADERS      = ["fabric", "forge", "neoforge", "quilt"]
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

_PALETTE = [
    "#2d6a4f", "#1e3a5f", "#5c2a2a", "#3a3a1e",
    "#2a1e5c", "#1e5c4a", "#4a3a1e", "#5c3a4a",
]

_HUMAN_NUM_CACHE: dict = {}


def _human(n: int) -> str:
    """152790000 → '152.79M'"""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _rel_date(iso: str) -> str:
    """'2024-01-15T...' → '2 days ago'"""
    if not iso:
        return ""
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        diff = datetime.now(timezone.utc) - dt
        d = diff.days
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


# ── Widget de ícono ─────────────────────────────────────────────────────────────
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


# ── Chip de categoría ───────────────────────────────────────────────────────────
def _cat_chip(label: str) -> ft.Container:
    icons = {
        "client":        ft.icons.COMPUTER_ROUNDED,
        "server":        ft.icons.DNS_ROUNDED,
        "library":       ft.icons.BOOK_ROUNDED,
        "optimization":  ft.icons.SPEED_ROUNDED,
        "utility":       ft.icons.BUILD_ROUNDED,
        "decoration":    ft.icons.PALETTE_ROUNDED,
        "adventure":     ft.icons.EXPLORE_ROUNDED,
        "magic":         ft.icons.AUTO_AWESOME_ROUNDED,
        "technology":    ft.icons.SETTINGS_ROUNDED,
        "food":          ft.icons.RESTAURANT_ROUNDED,
        "mobs":          ft.icons.PETS_ROUNDED,
        "worldgen":      ft.icons.TERRAIN_ROUNDED,
        "storage":       ft.icons.INVENTORY_ROUNDED,
        "transportation":ft.icons.TRAIN_ROUNDED,
    }
    ico = icons.get(label.lower())
    children: list = []
    if ico:
        children.append(ft.Icon(ico, size=10, color=TEXT_DIM))
        children.append(ft.Container(width=4))
    children.append(ft.Text(
        label.replace("-", " ").title(),
        color=TEXT_DIM, size=9,
    ))
    return ft.Container(
        bgcolor="#1f2937", border_radius=5,
        padding=ft.padding.symmetric(horizontal=8, vertical=4),
        content=ft.Row(children, spacing=0, tight=True),
    )


# ── Skeleton ────────────────────────────────────────────────────────────────────
def _skeleton_card() -> ft.Container:
    def _bar(w, h=10, opacity=0.14):
        return ft.Container(width=w, height=h, border_radius=4,
                            bgcolor="#ffffff", opacity=opacity)
    return ft.Container(
        bgcolor=CARD_BG, border_radius=14,
        padding=ft.padding.all(20),
        content=ft.Row([
            ft.Container(width=80, height=80, border_radius=12,
                         bgcolor="#ffffff", opacity=0.10),
            ft.Container(width=20),
            ft.Column([
                _bar(220, 14, 0.20),
                ft.Container(height=6),
                _bar(100, 9),
                ft.Container(height=6),
                _bar(380, 9),
                _bar(300, 9),
                ft.Container(height=10),
                ft.Row([_bar(70, 8), ft.Container(width=6),
                        _bar(80, 8), ft.Container(width=6), _bar(55, 8)]),
            ], spacing=4, expand=True),
            ft.Column([
                _bar(80, 9),
                ft.Container(height=6),
                _bar(70, 9),
                ft.Container(height=6),
                _bar(60, 9),
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
        self._page_index : int  = 0   # 0-based
        self._page_size  : int  = 20
        self._total_hits : int  = 0
        self._loading    : bool = False
        self._tab_index  : int  = 0
        self._debounce_timer     = None
        self._installed_set: set = set()

        # Optional: si viene desde una instancia, se puede pasar profile
        self._source_profile = None

        self._build()

    # ── LAYOUT ──────────────────────────────────────────────────────────────
    def _build(self):
        # ── TABS ─────────────────────────────────────────────────────────────
        self._tab_buttons: list[ft.Container] = []
        tab_row_controls = []
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
            tab_row_controls.append(btn)

        self._tabs_row = ft.Row(
            tab_row_controls,
            spacing=4,
        )

        # ── SEARCH ───────────────────────────────────────────────────────────
        self._search_field = ft.TextField(
            hint_text="Search mods...",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=13),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, expand=True,
            height=44,
            content_padding=ft.padding.symmetric(horizontal=16, vertical=10),
            prefix_icon=ft.icons.SEARCH_ROUNDED,
            text_size=13,
            on_change=self._on_search_change,
        )

        # ── SORT + VIEW ───────────────────────────────────────────────────────
        self._sort_dd = ft.Dropdown(
            prefix_text="Sort by: ",
            prefix_style=ft.TextStyle(color=TEXT_SEC, size=12),
            width=220,
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, height=44,
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
            width=130,
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, height=44,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            options=[ft.dropdown.Option(str(s)) for s in VIEW_SIZES],
            value="20",
            text_style=ft.TextStyle(size=12),
            on_change=self._on_view_change,
        )

        # ── PAGINACIÓN ────────────────────────────────────────────────────────
        self._pagination_row = ft.Row([], spacing=4)
        self._pagination_container = ft.Container(
            content=self._pagination_row,
            visible=False,
        )

        # ── CHIPS de versión/loader ───────────────────────────────────────────
        self._filter_chips_row = ft.Row([], spacing=8, visible=False)

        # ── LISTA ─────────────────────────────────────────────────────────────
        self._list_col = ft.Column(
            [], spacing=8,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        self._empty_state = ft.Container(
            visible=False,
            alignment=ft.alignment.center,
            expand=True,
            content=ft.Column([
                ft.Icon(ft.icons.SEARCH_OFF_ROUNDED, size=56, color=TEXT_DIM),
                ft.Container(height=12),
                ft.Text("No results found", color=TEXT_SEC, size=16,
                        weight=ft.FontWeight.BOLD),
                ft.Text("Try a different search term or adjust your filters.",
                        color=TEXT_DIM, size=11),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=4),
        )

        self._count_lbl = ft.Text("", color=TEXT_DIM, size=11)

        # ── HEADER (título de sección) ────────────────────────────────────────
        self._header_title = ft.Text(
            "Install content to instance",
            color=TEXT_PRI, size=22,
            weight=ft.FontWeight.BOLD,
        )

        self.root = ft.Container(
            expand=True, bgcolor=BG,
            padding=ft.padding.only(left=36, right=36, top=28, bottom=0),
            content=ft.Column([
                # Title
                self._header_title,
                ft.Container(height=18),
                # Tabs
                ft.Row([self._tabs_row]),
                ft.Container(height=16),
                # Search
                ft.Row([self._search_field]),
                ft.Container(height=12),
                # Filters row: sort + view | pagination
                ft.Row([
                    self._sort_dd,
                    ft.Container(width=8),
                    self._view_dd,
                    ft.Container(expand=True),
                    self._pagination_container,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=10),
                # Chips de versión/loader
                self._filter_chips_row,
                ft.Container(height=4, visible=False, ref=ft.Ref()),
                # Content area
                ft.Stack([
                    self._list_col,
                    self._empty_state,
                ], expand=True),
                ft.Container(height=8),
                # Bottom pagination
                ft.Row([
                    self._count_lbl,
                    ft.Container(expand=True),
                ]),
                ft.Container(height=16),
            ], spacing=0, expand=True),
        )

        self._highlight_tab(0)

    # ── Ciclo de vida ──────────────────────────────────────────────────────────
    def on_show(self):
        self._refresh_chips()
        self._do_search(reset=True)

    def set_source_profile(self, profile):
        """Llamar desde instance_view antes de on_show para dar contexto."""
        self._source_profile = profile

    def _refresh_chips(self):
        profile = self._active_profile()
        if not profile:
            self._filter_chips_row.visible = False
            try: self._filter_chips_row.update()
            except Exception: pass
            return

        mc_ver = getattr(profile, "version_id", None)
        loader = self._detect_loader(profile)

        chips = []
        if mc_ver:
            chips.append(self._make_filter_chip(
                ft.icons.LOCK_OUTLINE_ROUNDED, mc_ver))
        if loader:
            chips.append(self._make_filter_chip(
                ft.icons.LOCK_OUTLINE_ROUNDED, loader.capitalize()))

        self._filter_chips_row.controls.clear()
        self._filter_chips_row.controls.extend(chips)
        self._filter_chips_row.visible = bool(chips)
        try: self._filter_chips_row.update()
        except Exception: pass

    def _make_filter_chip(self, icon, label: str) -> ft.Container:
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

    # ── Tabs ───────────────────────────────────────────────────────────────────
    def _switch_tab(self, idx: int):
        if self._loading:
            return
        self._tab_index = idx
        self._highlight_tab(idx)
        # Actualizar hint text
        hints = {
            0: "Search mods...",
            1: "Search resource packs...",
            2: "Search data packs...",
            3: "Search shaders...",
            4: "Search modpacks...",
        }
        self._search_field.hint_text = hints.get(idx, "Search...")
        try: self._search_field.update()
        except Exception: pass
        self._do_search(reset=True)

    def _highlight_tab(self, active: int):
        for i, btn in enumerate(self._tab_buttons):
            is_active = (i == active)
            btn.bgcolor = GREEN if is_active else "transparent"
            lbl: ft.Text = btn.content
            lbl.color = TEXT_INV if is_active else TEXT_SEC
            lbl.weight = ft.FontWeight.W_700 if is_active else ft.FontWeight.W_600
            try:
                btn.update()
            except Exception:
                pass

    def _tab_hover(self, e, idx: int):
        btn = self._tab_buttons[idx]
        is_active = (idx == self._tab_index)
        if is_active:
            return
        btn.bgcolor = CARD2_BG if e.data == "true" else "transparent"
        lbl: ft.Text = btn.content
        lbl.color = TEXT_PRI if e.data == "true" else TEXT_SEC
        try: btn.update()
        except Exception: pass

    # ── Eventos ────────────────────────────────────────────────────────────────
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

    # ── Búsqueda ───────────────────────────────────────────────────────────────
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

    # ── Fetch (hilo secundario) ────────────────────────────────────────────────
    def _fetch(self):
        self.page.run_thread(self._show_skeleton)

        query        = (self._search_field.value or "").strip()
        profile      = self._active_profile()
        mc_ver       = getattr(profile, "version_id", None) if profile else None
        project_type = TAB_PROJECT_TYPES[self._tab_index]
        loader       = (self._detect_loader(profile)
                        if project_type in ("mod", "modpack") else None)
        sort_by      = self._sort_dd.value or "relevance"
        offset       = self._page_index * self._page_size

        # Instalar detector
        target_dir = self._target_dir(profile) if profile else None
        self._installed_set = build_installed_set(target_dir)

        try:
            # Intentar obtener total_hits si el servicio lo expone
            service = self.app.modrinth_service
            results = service.search_mods(
                query        = query,
                mc_version   = mc_ver,
                loader       = loader,
                limit        = self._page_size,
                offset       = offset,
                sort_by      = sort_by,
                project_type = project_type,
            )
            # Intentar leer total_hits del servicio si lo cachea
            total = getattr(service, "_last_total_hits", None)
            if total is None:
                # Estimación: si tuvimos hits previos o calcular por resultados
                if len(results) < self._page_size:
                    total = offset + len(results)
                else:
                    total = max(self._total_hits, offset + len(results) + 1)

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

        # Count label
        start = self._page_index * self._page_size + 1
        end   = start + len(results) - 1
        self._count_lbl.value = (
            f"Showing {start}–{end} of {self._total_hits:,} results"
            if self._total_hits > 0 else f"{len(results)} results"
        )

        # Paginación
        self._rebuild_pagination()
        self._pagination_container.visible = self._total_hits > self._page_size

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
                bg  = GREEN
                fg  = TEXT_INV
                brd = None
            elif disabled:
                bg  = "transparent"
                fg  = TEXT_DIM
                brd = None
            else:
                bg  = INPUT_BG
                fg  = TEXT_PRI
                brd = ft.border.all(1, BORDER)

            btn = ft.Container(
                width=36, height=36,
                bgcolor=bg,
                border=brd,
                border_radius=8,
                alignment=ft.alignment.center,
                animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
                content=ft.Text(
                    str(label), color=fg, size=12,
                    weight=ft.FontWeight.BOLD if active else ft.FontWeight.W_500,
                    text_align=ft.TextAlign.CENTER,
                ),
            )
            if not active and not disabled:
                target = page_idx
                btn.on_click = lambda e, p=target: self._go_to_page(p)
                btn.on_hover = lambda e, b=btn: (
                    setattr(b, "bgcolor",
                            CARD2_BG if e.data == "true" else INPUT_BG)
                    or b.update()
                )
            return btn

        def _ellipsis():
            return ft.Container(
                width=36, height=36,
                alignment=ft.alignment.center,
                content=ft.Text("…", color=TEXT_DIM, size=12),
            )

        # Prev arrow
        prev_arrow = ft.Container(
            width=36, height=36,
            bgcolor=INPUT_BG if cur > 0 else "transparent",
            border=ft.border.all(1, BORDER) if cur > 0 else None,
            border_radius=8,
            alignment=ft.alignment.center,
            content=ft.Icon(
                ft.icons.CHEVRON_LEFT_ROUNDED,
                size=18,
                color=TEXT_PRI if cur > 0 else TEXT_DIM,
            ),
        )
        if cur > 0:
            prev_arrow.on_click = lambda e: self._go_to_page(cur - 1)
            prev_arrow.on_hover = lambda e, b=prev_arrow: (
                setattr(b, "bgcolor",
                        CARD2_BG if e.data == "true" else INPUT_BG)
                or b.update()
            )
        row.controls.append(prev_arrow)

        # Page numbers
        # Logic: always show first, last, current ±1, with ellipsis
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

        # Next arrow
        has_next = cur < total_pages - 1
        next_arrow = ft.Container(
            width=36, height=36,
            bgcolor=INPUT_BG if has_next else "transparent",
            border=ft.border.all(1, BORDER) if has_next else None,
            border_radius=8,
            alignment=ft.alignment.center,
            content=ft.Icon(
                ft.icons.CHEVRON_RIGHT_ROUNDED,
                size=18,
                color=TEXT_PRI if has_next else TEXT_DIM,
            ),
        )
        if has_next:
            next_arrow.on_click = lambda e: self._go_to_page(cur + 1)
            next_arrow.on_hover = lambda e, b=next_arrow: (
                setattr(b, "bgcolor",
                        CARD2_BG if e.data == "true" else INPUT_BG)
                or b.update()
            )
        row.controls.append(next_arrow)

    # ── Skeleton / Empty state ─────────────────────────────────────────────────
    def _show_skeleton(self):
        self._list_col.controls.clear()
        self._empty_state.visible = False
        self._pagination_container.visible = False
        for _ in range(6):
            self._list_col.controls.append(_skeleton_card())
        try:
            self._list_col.update()
            self._empty_state.update()
            self._pagination_container.update()
        except Exception:
            pass

    def _hide_skeleton(self):
        pass  # _render_results / _show_empty lo limpia

    def _show_empty(self):
        self._list_col.controls.clear()
        self._empty_state.visible = True
        self._count_lbl.value     = "0 results"
        self._pagination_container.visible = False
        try:
            self._list_col.update()
            self._empty_state.update()
            self._count_lbl.update()
            self._pagination_container.update()
        except Exception:
            pass

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _active_profile(self):
        if self._source_profile:
            return self._source_profile
        return None

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
        if pt in ("shader",):
            return getattr(profile, "shaderpacks_dir", None)
        return getattr(profile, "mods_dir", None)

    # ── CARD ───────────────────────────────────────────────────────────────────
    def _make_card(self, proj, is_installed: bool) -> ft.Container:
        author     = getattr(proj, "author", "")
        slug_url   = f"https://modrinth.com/mod/{proj.slug}"
        author_url = f"https://modrinth.com/user/{author}" if author else ""
        follows    = getattr(proj, "follows", 0)
        updated    = getattr(proj, "date_modified", "") or getattr(proj, "date_updated", "")
        date_str   = _rel_date(updated)

        # ── Install button ────────────────────────────────────────────────────
        if is_installed:
            install_btn = ft.Container(
                bgcolor="transparent",
                border=ft.border.all(1.5, GREEN),
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=14, vertical=7),
                tooltip="Already installed in this profile",
                content=ft.Row([
                    ft.Icon(ft.icons.CHECK_ROUNDED, size=14, color=GREEN),
                    ft.Container(width=6),
                    ft.Text("Installed", color=GREEN, size=11,
                            weight=ft.FontWeight.W_600),
                ], spacing=0, tight=True),
            )
        else:
            install_btn = ft.Container(
                bgcolor=GREEN, border_radius=8,
                padding=ft.padding.symmetric(horizontal=14, vertical=7),
                animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
                on_click=lambda e, p=proj: self._quick_install(p),
                on_hover=lambda e, b=None: None,  # set below
                content=ft.Row([
                    ft.Icon(ft.icons.DOWNLOAD_ROUNDED, size=14, color=TEXT_INV),
                    ft.Container(width=6),
                    ft.Text("Install", color=TEXT_INV, size=11,
                            weight=ft.FontWeight.W_600),
                ], spacing=0, tight=True),
            )
            install_btn.on_hover = lambda e, b=install_btn: (
                setattr(b, "bgcolor", GREEN_DIM if e.data == "true" else GREEN)
                or b.update()
            )

        # ── Author row ────────────────────────────────────────────────────────
        author_row_controls = []
        if author:
            cached = cache_get_author(author) or {}
            av_url = cached.get("avatar_url")
            if av_url:
                av = ft.Image(src=av_url, width=15, height=15,
                              border_radius=8, fit=ft.ImageFit.COVER)
            else:
                av = ft.Container(
                    width=15, height=15, border_radius=8,
                    bgcolor=CARD2_BG, alignment=ft.alignment.center,
                    content=ft.Text(author[0].upper(), size=7,
                                    color=TEXT_DIM),
                )
            author_txt = ft.Text(
                author, color=GREEN, size=11,
                weight=ft.FontWeight.W_500,
            )
            author_gd = ft.GestureDetector(
                mouse_cursor=ft.MouseCursor.CLICK,
                on_tap=lambda e, u=author_url: self.page.launch_url(u),
                on_enter=lambda e, t=author_txt: (
                    setattr(t, "decoration", ft.TextDecoration.UNDERLINE)
                    or t.update()
                ),
                on_exit=lambda e, t=author_txt: (
                    setattr(t, "decoration", ft.TextDecoration.NONE)
                    or t.update()
                ),
                content=ft.Row(
                    [av, ft.Container(width=5), author_txt],
                    spacing=0, tight=True,
                ),
            )
            author_row_controls = [
                ft.Text("by ", color=TEXT_DIM, size=11),
                author_gd,
                ft.Container(width=6),
                ft.GestureDetector(
                    mouse_cursor=ft.MouseCursor.CLICK,
                    on_tap=lambda e, u=slug_url: self.page.launch_url(u),
                    content=ft.Icon(
                        ft.icons.OPEN_IN_NEW_ROUNDED,
                        size=12, color=TEXT_DIM,
                    ),
                    tooltip="Open on Modrinth",
                ),
            ]

        # ── Categories ────────────────────────────────────────────────────────
        cats = getattr(proj, "categories", []) or []
        shown_cats = cats[:3]
        extra      = len(cats) - 3

        chip_row_controls = [_cat_chip(c) for c in shown_cats]
        if extra > 0:
            chip_row_controls.append(
                ft.Container(
                    bgcolor="#1f2937", border_radius=5,
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                    content=ft.Text(f"+{extra}", color=TEXT_DIM, size=9),
                )
            )
        chips_row = ft.Row(chip_row_controls, spacing=6, wrap=True)

        # ── Stats (right side) ────────────────────────────────────────────────
        stats_col = ft.Column([
            ft.Row([
                ft.Icon(ft.icons.DOWNLOAD_ROUNDED, size=13, color=TEXT_DIM),
                ft.Container(width=5),
                ft.Text(_human(proj.downloads), color=TEXT_SEC, size=11,
                        weight=ft.FontWeight.W_500),
            ], spacing=0, tight=True),
            ft.Row([
                ft.Icon(ft.icons.FAVORITE_BORDER_ROUNDED, size=13, color=TEXT_DIM),
                ft.Container(width=5),
                ft.Text(_human(follows) if follows else "—",
                        color=TEXT_SEC, size=11,
                        weight=ft.FontWeight.W_500),
            ], spacing=0, tight=True),
            ft.Row([
                ft.Icon(ft.icons.HISTORY_ROUNDED, size=13, color=TEXT_DIM),
                ft.Container(width=5),
                ft.Text(date_str or "—", color=TEXT_SEC, size=11),
            ], spacing=0, tight=True),
        ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.END)

        # ── Title text (for hover underline) ─────────────────────────────────
        title_txt = ft.Text(
            proj.title, color=TEXT_PRI, size=15,
            weight=ft.FontWeight.BOLD,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        desc_txt = ft.Text(
            (proj.description[:180] + "…"
             if len(proj.description) > 180 else proj.description),
            color=TEXT_SEC, size=11,
            overflow=ft.TextOverflow.ELLIPSIS,
            max_lines=2,
        )

        # ── Main card ─────────────────────────────────────────────────────────
        card = ft.Container(
            bgcolor=CARD_BG,
            border=ft.border.all(1, BORDER),
            border_radius=14,
            padding=ft.padding.all(20),
            animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
            on_click=lambda e, p=proj: self._open_detail(p),
            on_hover=lambda e, c=None, t=title_txt: None,  # set below
            content=ft.Row([
                # Left: icon
                _icon_widget(proj.icon_url, proj.title, size=80),
                ft.Container(width=20),
                # Center: info
                ft.Column([
                    ft.Row([
                        ft.Column([
                            ft.Row([title_txt] + author_row_controls,
                                   spacing=0, wrap=False,
                                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ], expand=True, spacing=0),
                        install_btn,
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                       vertical_alignment=ft.CrossAxisAlignment.START),
                    ft.Container(height=6),
                    desc_txt,
                    ft.Container(height=10),
                    chips_row,
                ], spacing=0, expand=True),
                ft.Container(width=24),
                # Right: stats
                ft.Column([
                    stats_col,
                ], alignment=ft.MainAxisAlignment.END,
                   horizontal_alignment=ft.CrossAxisAlignment.END),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        def _card_hover(e, c=card, t=title_txt):
            c.bgcolor = CARD2_BG if e.data == "true" else CARD_BG
            c.border  = ft.border.all(1, BORDER_BRIGHT if e.data == "true" else BORDER)
            t.decoration = (ft.TextDecoration.UNDERLINE
                            if e.data == "true" else ft.TextDecoration.NONE)
            try:
                c.update()
                t.update()
            except Exception:
                pass

        card.on_hover = _card_hover
        return card

    # ── Quick install ──────────────────────────────────────────────────────────
    def _quick_install(self, project):
        profile = self._active_profile()
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
                        "No compatible version found for this profile.", error=True))
                    return
                target = self._target_dir(profile)
                os.makedirs(target, exist_ok=True)
                self.app.modrinth_service.download_mod_version(version, target)
                self._installed_set = build_installed_set(target)
                self.page.run_thread(lambda: self.app.snack(
                    f"{project.title} installed in {profile.name}. ✓"))
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
        profile = self._active_profile()
        ModDetailDialog(
            self.page, self.app, project,
            active_profile=profile,
            active_loader=self._detect_loader(profile),
            target_dir=self._target_dir(profile) if profile else None,
            on_installed=lambda: self._on_installed(project),
        )

    def _on_installed(self, project):
        profile = self._active_profile()
        self._installed_set = build_installed_set(self._target_dir(profile))
        self._refresh_badges()


# ══════════════════════════════════════════════════════════════════════════════
#  Diálogo de detalle
# ══════════════════════════════════════════════════════════════════════════════
class ModDetailDialog:
    def __init__(self, page, app, project, active_profile,
                 active_loader, target_dir=None, on_installed=None):
        self.page           = page
        self.app            = app
        self.project        = project
        self.active_profile = active_profile
        self.active_loader  = active_loader
        self.target_dir     = target_dir
        self.on_installed   = on_installed
        self._versions      = []
        self._selected_ver  = None
        self._build()
        threading.Thread(target=self._fetch_versions, daemon=True).start()

    def _build(self):
        author    = getattr(self.project, "author", "")
        follows   = getattr(self.project, "follows", 0)
        prof_name = self.active_profile.name if self.active_profile else "No profile"

        header = ft.Row([
            _icon_widget(self.project.icon_url, self.project.title, size=68),
            ft.Container(width=20),
            ft.Column([
                ft.Text(self.project.title, color=TEXT_PRI, size=18,
                        weight=ft.FontWeight.BOLD),
                ft.Text(f"by {author}" if author else "",
                        color=GREEN, size=11),
                ft.Container(height=4),
                ft.Text(
                    (self.project.description[:200] + "…"
                     if len(self.project.description) > 200
                     else self.project.description),
                    color=TEXT_SEC, size=11, max_lines=3,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Container(height=8),
                ft.Row([
                    _stat_pill(ft.icons.DOWNLOAD_ROUNDED,
                               _human(self.project.downloads), "Downloads"),
                    ft.Container(width=8),
                    _stat_pill(ft.icons.FAVORITE_BORDER_ROUNDED,
                               _human(follows) if follows else "—", "Follows"),
                    ft.Container(width=8),
                    _stat_pill(ft.icons.COMPUTER_ROUNDED, prof_name, "Profile"),
                ]),
            ], spacing=2, expand=True),
        ], vertical_alignment=ft.CrossAxisAlignment.START)

        self._spinner_row = ft.Row([
            ft.ProgressRing(width=16, height=16, color=GREEN, stroke_width=2),
            ft.Container(width=10),
            ft.Text("Loading versions…", color=TEXT_DIM, size=10),
        ], visible=True)

        self._status_lbl  = ft.Text("", color=TEXT_DIM, size=10, visible=False)
        self._versions_lv = ft.ListView(spacing=6, height=300,
                                        padding=ft.padding.only(right=4))

        self._install_btn = ft.ElevatedButton(
            "Install selected version",
            bgcolor=GREEN, color=TEXT_INV, disabled=True,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=20, vertical=12),
            ),
            icon=ft.icons.DOWNLOAD_ROUNDED,
            on_click=self._do_install,
        )

        self._dlg = ft.AlertDialog(
            bgcolor=CARD_BG,
            title=ft.Container(),
            content=ft.Container(
                width=740,
                content=ft.Column([
                    header,
                    ft.Divider(height=1, color=BORDER),
                    ft.Container(height=4),
                    self._spinner_row,
                    self._status_lbl,
                    ft.Container(height=4),
                    self._versions_lv,
                ], spacing=8),
            ),
            actions=[
                ft.TextButton(
                    "Close",
                    style=ft.ButtonStyle(color=TEXT_SEC),
                    on_click=lambda e: self.page.close(self._dlg),
                ),
                self._install_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        self.page.open(self._dlg)

    def _fetch_versions(self):
        try:
            mc_ver   = (getattr(self.active_profile, "version_id", None)
                        if self.active_profile else None)
            versions = self.app.modrinth_service.get_project_versions(
                self.project.project_id,
                mc_version=None,
                loader=self.active_loader,
            )
            self.page.run_thread(lambda: self._render_versions(versions, mc_ver))
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

    def _render_versions(self, versions, mc_ver):
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

        count_compat = sum(
            1 for v in versions
            if not mc_ver or mc_ver in v.game_versions
        )

        # Header row
        self._versions_lv.controls.clear()
        self._versions_lv.controls.append(
            ft.Container(
                padding=ft.padding.symmetric(horizontal=14, vertical=6),
                content=ft.Row([
                    ft.Container(width=22),
                    ft.Text("Version", color=TEXT_DIM, size=9,
                            weight=ft.FontWeight.BOLD, expand=True),
                    ft.Text("MC versions", color=TEXT_DIM, size=9, width=130),
                    ft.Text("Loaders",    color=TEXT_DIM, size=9, width=100),
                    ft.Text("File",       color=TEXT_DIM, size=9, width=170),
                ]),
            )
        )
        self._versions_lv.controls.append(ft.Divider(height=1, color=BORDER))

        for v in versions:
            compatible = not mc_ver or mc_ver in v.game_versions
            primary    = v.get_primary_file()
            filename   = primary.get("filename", "—") if primary else "—"

            dot   = ft.Container(width=8, height=8, border_radius=4,
                                 bgcolor=GREEN if compatible else TEXT_DIM)
            row   = ft.Container(
                bgcolor=INPUT_BG if compatible else CARD2_BG,
                border_radius=8, data=v.version_id,
                padding=ft.padding.symmetric(horizontal=14, vertical=11),
                animate=ft.animation.Animation(100, ft.AnimationCurve.EASE_OUT),
                on_click=(lambda e, ver=v: self._select_version(ver))
                         if compatible else None,
                on_hover=(lambda e, r=None: None) if compatible else None,
                content=ft.Row([
                    dot,
                    ft.Container(width=14),
                    ft.Text(v.name,
                            color=TEXT_PRI if compatible else TEXT_DIM,
                            size=11, weight=ft.FontWeight.W_600,
                            expand=True),
                    ft.Text(", ".join(v.game_versions[:3]),
                            color=TEXT_DIM, size=9, width=130),
                    ft.Text(", ".join(v.loaders[:2]),
                            color=TEXT_DIM, size=9, width=100),
                    ft.Text(filename, color=TEXT_DIM, size=9,
                            width=170, overflow=ft.TextOverflow.ELLIPSIS),
                ]),
            )
            if compatible:
                r = row
                row.on_hover = lambda e, b=r: (
                    setattr(b, "bgcolor",
                            "#1e2533" if e.data == "true" else INPUT_BG)
                    or b.update()
                )
            self._versions_lv.controls.append(row)

        self._status_lbl.value = (
            f"{len(versions)} versions  ·  "
            f"{count_compat} compatible with {mc_ver or 'this profile'}"
        )
        self._status_lbl.visible = True
        try:
            self._spinner_row.update()
            self._status_lbl.update()
            self._versions_lv.update()
        except Exception:
            pass

    def _select_version(self, version):
        self._selected_ver         = version
        self._install_btn.disabled = False
        for c in self._versions_lv.controls:
            if hasattr(c, "data"):
                c.bgcolor = "#162820" if c.data == version.version_id else INPUT_BG
                try: c.update()
                except Exception: pass
        try: self._install_btn.update()
        except Exception: pass

    def _do_install(self, e):
        if not self._selected_ver or not self.active_profile:
            self.app.snack("Select an active profile first.", error=True)
            return
        self._install_btn.disabled = True
        self._status_lbl.value     = f"Downloading {self._selected_ver.name}…"
        try:
            self._install_btn.update()
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
                    self._status_lbl.value     = "✓ Installed successfully"
                    self._install_btn.disabled = False
                    try:
                        self._status_lbl.update()
                        self._install_btn.update()
                    except Exception:
                        pass
                    self.app.snack(
                        f"{self.project.title} installed in {prof.name}. ✓")
                    if self.on_installed:
                        self.on_installed()
                self.page.run_thread(done)
            except Exception as err:
                def _e(e=err):
                    self._status_lbl.value     = f"Error: {e}"
                    self._install_btn.disabled = False
                    try:
                        self._status_lbl.update()
                        self._install_btn.update()
                    except Exception:
                        pass
                self.page.run_thread(_e)

        threading.Thread(target=do, daemon=True).start()


# ── Util: stat pill para el diálogo ──────────────────────────────────────────
def _stat_pill(icon, value: str, label: str) -> ft.Container:
    return ft.Container(
        bgcolor=INPUT_BG,
        border=ft.border.all(1, BORDER),
        border_radius=8,
        padding=ft.padding.symmetric(horizontal=12, vertical=6),
        tooltip=label,
        content=ft.Row([
            ft.Icon(icon, size=13, color=TEXT_DIM),
            ft.Container(width=6),
            ft.Text(value, color=TEXT_SEC, size=11,
                    weight=ft.FontWeight.W_500),
        ], spacing=0, tight=True),
    )