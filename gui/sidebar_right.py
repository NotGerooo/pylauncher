# -*- coding: utf-8 -*-
"""
gui/sidebar_right.py
Dos modos:
  • Normal  — cuenta activa + feed de noticias
  • Discover — panel de filtros (Game version, Loader, Category)
               se activa cuando DiscoverView llama set_discover_mode(True)
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

# ── Categorías por tipo de proyecto ──────────────────────────────────────────
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


class SidebarRight:
    def __init__(self, app):
        self.app = app
        self.page = app.page

        # ── Discover filter state ─────────────────────────────────────────
        self._discover_mode      = False
        self._on_filter_change   = None
        self._selected_cats: set = set()
        self._hide_installed     = False
        self._discover_profile   = None
        self._discover_tab_type  = "mod"
        self._discover_loader    = None   # None = auto-detect from profile

        # section expanded state
        self._ver_expanded     = True
        self._loader_expanded  = True
        self._cat_expanded     = True

        self._build()
        threading.Thread(target=self._fetch_news, daemon=True).start()
        threading.Timer(0.5, self.refresh_account).start()

    # ═══════════════════════════════════════════════════════════════════════
    #  Shell
    # ═══════════════════════════════════════════════════════════════════════
    def _build(self):
        self._swap = ft.Container(expand=True)
        self.root  = ft.Container(
            width=252, bgcolor=SIDEBAR_BG,
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
    #  NORMAL MODE  (cuenta + noticias)
    # ═══════════════════════════════════════════════════════════════════════
    def _build_normal_content(self):
        self._avatar_text  = ft.Text("??", color=TEXT_INV, size=12,
                                     weight=ft.FontWeight.BOLD)
        self._avatar_box   = ft.Container(
            width=38, height=38, border_radius=19,
            bgcolor=GREEN, alignment=ft.alignment.center,
            content=self._avatar_text,
        )
        self._username_lbl = ft.Text("—", color=TEXT_PRI, size=10,
                                     weight=ft.FontWeight.BOLD)
        self._dot          = ft.Container(width=8, height=8, border_radius=4,
                                          bgcolor=TEXT_DIM)
        self._mode_lbl     = ft.Text("Sin cuenta", color=TEXT_DIM, size=8)

        account_section = ft.Container(
            padding=ft.padding.all(16),
            content=ft.Column([
                ft.Text("JUGANDO COMO", color=TEXT_DIM, size=8,
                        weight=ft.FontWeight.BOLD),
                ft.Container(height=10),
                ft.Row([
                    self._avatar_box,
                    ft.Container(width=10),
                    ft.Column([
                        self._username_lbl,
                        ft.Row([
                            self._dot,
                            ft.Container(width=4),
                            self._mode_lbl,
                        ], spacing=0),
                    ], spacing=2, expand=True),
                ]),
                ft.Container(height=6),
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
                    padding=ft.padding.only(left=16, right=16, top=14, bottom=8),
                    content=ft.Row([
                        ft.Text("NOTICIAS", color=TEXT_DIM, size=8,
                                weight=ft.FontWeight.BOLD),
                        ft.Container(expand=True),
                        self._news_count_lbl,
                    ]),
                ),
                ft.Container(expand=True, content=self._news_col),
            ], spacing=0, expand=True),
        ], spacing=0, expand=True)

    # ═══════════════════════════════════════════════════════════════════════
    #  DISCOVER MODE  (filtros)
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
        """Llamado desde DiscoverView al cambiar de tab."""
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

    # ── Build discover panel ─────────────────────────────────────────────────
    def _build_discover_col(self, profile, tab_type: str) -> ft.Column:
        mc_ver = getattr(profile, "version_id", "—") if profile else "—"

        # ── Hide installed ────────────────────────────────────────────────
        self._hide_cb = ft.Checkbox(
            label="Hide installed content",
            label_style=ft.TextStyle(color=TEXT_SEC, size=11),
            value=False,
            fill_color=GREEN,
            check_color=TEXT_INV,
            on_change=self._on_hide_installed_change,
        )

        hide_row = ft.Container(
            padding=ft.padding.symmetric(horizontal=16, vertical=14),
            content=self._hide_cb,
        )

        # ── Game version section ──────────────────────────────────────────
        self._ver_body = ft.Container(
            visible=self._ver_expanded,
            padding=ft.padding.only(left=16, right=16, bottom=14),
            content=ft.Container(
                bgcolor=INPUT_BG,
                border=ft.border.all(1, BORDER),
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                content=ft.Text(mc_ver, color=TEXT_PRI, size=12,
                                weight=ft.FontWeight.W_500),
            ),
        )
        self._ver_section = ft.Column([
            self._section_header("Game version", self._ver_expanded,
                                 self._toggle_ver),
            self._ver_body,
        ], spacing=0)

        # ── Loader section ────────────────────────────────────────────────
        self._loader_controls: list[ft.Container] = []
        self._loader_body = ft.Column(
            spacing=4,
            visible=self._loader_expanded,
        )
        self._rebuild_loader_section(profile)
        self._loader_section = ft.Column([
            self._section_header("Loader", self._loader_expanded,
                                 self._toggle_loader),
            ft.Container(
                padding=ft.padding.only(left=16, right=16, bottom=14),
                content=self._loader_body,
                visible=self._loader_expanded,
            ),
        ], spacing=0)
        # Keep ref to loader container for toggle
        self._loader_body_container = self._loader_section.controls[1]

        # ── Category section ──────────────────────────────────────────────
        self._cat_col  = ft.Column(spacing=2)
        self._cat_body_container = ft.Container(
            padding=ft.padding.only(left=16, right=16, bottom=14),
            content=ft.Column([
                self._cat_col,
                ft.Container(height=4),
            ], spacing=0),
            visible=self._cat_expanded,
        )
        self._cat_header_arrow = ft.Icon(
            ft.icons.KEYBOARD_ARROW_UP_ROUNDED if self._cat_expanded
            else ft.icons.KEYBOARD_ARROW_DOWN_ROUNDED,
            size=18, color=TEXT_DIM,
        )
        self._cat_section = ft.Column([
            self._section_header("Category", self._cat_expanded,
                                 self._toggle_cat,
                                 arrow_ref=self._cat_header_arrow),
            self._cat_body_container,
        ], spacing=0)
        self._rebuild_cat_section()

        discover_col = ft.Column([
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

        return discover_col

    # ── Section header ────────────────────────────────────────────────────────
    def _section_header(self, title: str, expanded: bool,
                        on_toggle, arrow_ref=None) -> ft.Container:
        arrow = arrow_ref or ft.Icon(
            ft.icons.KEYBOARD_ARROW_UP_ROUNDED if expanded
            else ft.icons.KEYBOARD_ARROW_DOWN_ROUNDED,
            size=18, color=TEXT_DIM,
        )
        hdr = ft.Container(
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            on_click=on_toggle,
            on_hover=lambda e, c=None: None,  # set below
            content=ft.Row([
                ft.Text(title, color=TEXT_PRI, size=12,
                        weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                arrow,
            ]),
        )
        hdr.on_hover = lambda e, h=hdr: (
            setattr(h, "bgcolor",
                    CARD2_BG if e.data == "true" else "transparent")
            or h.update()
        )
        return hdr

    # ── Loader section rebuild ────────────────────────────────────────────────
    def _rebuild_loader_section(self, profile):
        # Auto-detect loader from profile
        auto_loader = None
        if profile:
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
                        auto_loader = entries[0].get("loader_type")
                except Exception:
                    pass

        self._discover_loader = auto_loader
        self._loader_body.controls.clear()

        options = ["(auto)"] + LOADERS
        for opt in options:
            display = opt.capitalize() if opt != "(auto)" else (
                f"Auto ({auto_loader.capitalize()})" if auto_loader else "Auto"
            )
            is_sel  = (opt == "(auto)" and self._discover_loader == auto_loader) \
                      or (opt == self._discover_loader)
            row = self._loader_option_row(display, opt, is_sel)
            self._loader_body.controls.append(row)

    def _loader_option_row(self, display: str, value: str,
                           selected: bool) -> ft.Container:
        dot = ft.Container(
            width=10, height=10, border_radius=5,
            bgcolor=GREEN if selected else "transparent",
            border=ft.border.all(1.5, GREEN if selected else BORDER_BRIGHT),
            animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
        )
        lbl = ft.Text(display, color=TEXT_PRI if selected else TEXT_SEC,
                      size=11)
        row = ft.Container(
            padding=ft.padding.symmetric(horizontal=4, vertical=6),
            border_radius=6,
            content=ft.Row([dot, ft.Container(width=10), lbl],
                           spacing=0, tight=True),
        )
        row.on_click  = lambda e, v=value: self._on_loader_click(v)
        row.on_hover  = lambda e, r=row: (
            setattr(r, "bgcolor",
                    INPUT_BG if e.data == "true" else "transparent")
            or r.update()
        )
        return row

    def _on_loader_click(self, value: str):
        self._discover_loader = None if value == "(auto)" else value
        # Rebuild loader rows
        self._rebuild_loader_section(self._discover_profile)
        try: self._loader_body.update()
        except Exception: pass
        self._fire_filter_change()

    # ── Category section rebuild ──────────────────────────────────────────────
    def _rebuild_cat_section(self):
        cats = CATEGORIES_BY_TYPE.get(self._discover_tab_type, [])
        self._cat_col.controls.clear()
        for cat in cats:
            cb = ft.Checkbox(
                label=cat,
                label_style=ft.TextStyle(color=TEXT_SEC, size=11),
                value=(cat in self._selected_cats),
                fill_color=GREEN,
                check_color=TEXT_INV,
                data=cat,
                on_change=self._on_cat_change,
            )
            self._cat_col.controls.append(
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=4, vertical=2),
                    border_radius=6,
                    content=cb,
                )
            )
        try: self._cat_col.update()
        except Exception: pass

    def _on_cat_change(self, e):
        cat = e.control.data
        if e.control.value:
            self._selected_cats.add(cat)
        else:
            self._selected_cats.discard(cat)
        self._fire_filter_change()

    def _on_hide_installed_change(self, e):
        self._hide_installed = e.control.value
        self._fire_filter_change()

    def _fire_filter_change(self):
        if callable(self._on_filter_change):
            self._on_filter_change()

    # ── Toggle sections ───────────────────────────────────────────────────────
    def _toggle_ver(self, e):
        self._ver_expanded = not self._ver_expanded
        self._ver_body.visible = self._ver_expanded
        try: self._ver_body.update()
        except Exception: pass

    def _toggle_loader(self, e):
        self._loader_expanded = not self._loader_expanded
        self._loader_body_container.visible = self._loader_expanded
        try: self._loader_body_container.update()
        except Exception: pass

    def _toggle_cat(self, e):
        self._cat_expanded = not self._cat_expanded
        self._cat_body_container.visible = self._cat_expanded
        try: self._cat_body_container.update()
        except Exception: pass

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
            padding=ft.padding.symmetric(horizontal=14, vertical=8),
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