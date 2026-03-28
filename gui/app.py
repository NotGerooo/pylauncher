"""
gui/app.py — Gero's Launcher
Shell principal: titlebar, sidebar icon-only, área de contenido y panel derecho.
"""
import threading
import urllib.request
import json
import flet as ft

from config.settings import Settings
from managers.version_manager import VersionManager
from managers.profile_manager import ProfileManager
from managers.java_manager import JavaManager
from services.auth_service import AuthService
from services.modrinth_service import ModrinthService
from core.launcher import LauncherEngine
from utils.logger import get_logger

from gui.theme import (
    BG, SIDEBAR_BG, CARD_BG, CARD2_BG, INPUT_BG,
    BORDER, BORDER_BRIGHT, GREEN, GREEN_DIM, GREEN_SUBTLE,
    TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV,
    NAV_ACTIVE, NAV_HOVER, ACCENT_RED, AVATAR_PALETTE,
)

log = get_logger()

_SIDEBAR_W = 68   # ancho del sidebar icon-only


class App:
    def __init__(self, page: ft.Page):
        self.page = page
        self._views: dict = {}
        self._current_vid: str | None = None
        self._active_instance = None   # profile object cuando estamos dentro de una instancia

        self._setup_page()
        self._init_services()
        self._build_layout()
        self._show_view("library")
        log.info("Interfaz Flet iniciada")

    # ── Página ────────────────────────────────────────────────────────────────
    def _setup_page(self):
        p = self.page
        p.title = "Gero's Launcher"
        p.window.width       = 1380
        p.window.height      = 780
        p.window.min_width   = 1000
        p.window.min_height  = 620
        p.window.title_bar_hidden = True
        p.bgcolor  = SIDEBAR_BG
        p.padding  = 0
        p.spacing  = 0

    # ── Servicios ─────────────────────────────────────────────────────────────
    def _init_services(self):
        from services.account_manager import AccountManager
        from services.microsoft_auth  import MicrosoftAuth
        self.settings         = Settings()
        self.version_manager  = VersionManager(self.settings)
        self.profile_manager  = ProfileManager(self.settings)
        self.java_manager     = JavaManager(self.settings)
        self.auth_service     = AuthService()
        self.modrinth_service = ModrinthService()
        self.launcher_engine  = LauncherEngine(self.settings)
        self.account_manager  = AccountManager(data_dir="data")
        self.microsoft_auth   = MicrosoftAuth()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build_layout(self):
        self._content_area = ft.Container(expand=True, bgcolor=BG)

        body = ft.Row(
            controls=[
                self._build_sidebar(),
                ft.VerticalDivider(width=1, color=BORDER),
                self._content_area,
                ft.VerticalDivider(width=1, color=BORDER),
                self._build_right_panel(),
            ],
            spacing=0,
            expand=True,
        )

        self.page.add(
            ft.Column(
                spacing=0,
                expand=True,
                controls=[
                    self._build_titlebar(),
                    ft.Divider(height=1, color=BORDER),
                    body,
                ],
            )
        )

    # ── Titlebar ──────────────────────────────────────────────────────────────
    def _build_titlebar(self) -> ft.Control:
        def wbtn(color, hover, cmd):
            return ft.Container(
                width=14, height=14, border_radius=7, bgcolor=color,
                on_click=lambda e: cmd(),
                on_hover=lambda e, nc=color, hc=hover: (
                    setattr(e.control, "bgcolor", hc if e.data == "true" else nc)
                    or e.control.update()),
            )

        return ft.WindowDragArea(
            ft.Container(
                bgcolor=SIDEBAR_BG, height=48,
                padding=ft.padding.symmetric(horizontal=20),
                content=ft.Row([
                    ft.Text("⛏", color=GREEN, size=15),
                    ft.Container(width=8),
                    ft.Text("Gero's Launcher", color=TEXT_PRI, size=11,
                            weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.Container(
                        bgcolor="#172616", border_radius=4,
                        padding=ft.padding.symmetric(horizontal=10, vertical=3),
                        content=ft.Text("v0.2.0", color=GREEN, size=8,
                                        weight=ft.FontWeight.BOLD),
                    ),
                    ft.Container(width=16),
                    ft.Row([
                        wbtn("#ff5f57", "#ff3b30", lambda: self.page.window.close()),
                        wbtn("#febc2e", "#f0a500", self._minimize),
                        wbtn("#28c840", "#1da831", self._toggle_maximize),
                    ], spacing=8),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )
        )

    def _minimize(self):
        self.page.window.minimized = True
        self.page.update()

    def _toggle_maximize(self):
        self.page.window.maximized = not self.page.window.maximized
        self.page.update()

    # ── Sidebar icon-only ─────────────────────────────────────────────────────
    def _build_sidebar(self) -> ft.Control:
        # Nav principal (top)
        self._nav_btns: dict[str, ft.Container] = {}
        top_items = [
            ("home",     "🏠",  "Inicio"),
            ("discover", "🔍",  "Descubrir"),
            ("library",  "📚",  "Biblioteca"),
        ]
        top_rows = []
        for vid, icon, tip in top_items:
            btn = self._make_icon_btn(vid, icon, tip)
            self._nav_btns[vid] = btn
            top_rows.append(btn)

        # Instancias (medio, scrollable)
        self._instances_col = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO)
        self._add_instance_btn = ft.Container(
            width=40, height=40, border_radius=20,
            bgcolor=CARD2_BG,
            border=ft.border.all(1, BORDER),
            alignment=ft.alignment.center,
            tooltip="Nueva instancia",
            content=ft.Text("+", color=TEXT_SEC, size=18, weight=ft.FontWeight.BOLD),
            on_click=lambda e: self._open_create_instance(),
            on_hover=lambda e: (
                setattr(e.control, "bgcolor", NAV_HOVER if e.data=="true" else CARD2_BG)
                or e.control.update()),
        )
        self._refresh_instance_icons()

        # Bottom items
        self._bottom_btns: dict[str, ft.Container] = {}
        bottom_items = [
            ("settings", "⚙️", "Ajustes"),
            ("accounts", "👤", "Cuentas"),
        ]
        bottom_rows = []
        for vid, icon, tip in bottom_items:
            btn = self._make_icon_btn(vid, icon, tip)
            self._nav_btns[vid] = btn
            self._bottom_btns[vid] = btn
            bottom_rows.append(btn)

        return ft.Container(
            width=_SIDEBAR_W,
            bgcolor=SIDEBAR_BG,
            content=ft.Column([
                ft.Container(height=8),
                *top_rows,
                ft.Container(height=4),
                ft.Divider(height=1, color=BORDER),
                ft.Container(height=4),
                ft.Container(
                    expand=True,
                    content=ft.Column([
                        self._instances_col,
                        ft.Container(height=6),
                        self._add_instance_btn,
                    ], spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                ),
                ft.Divider(height=1, color=BORDER),
                ft.Container(height=4),
                *bottom_rows,
                ft.Container(height=8),
            ], spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )

    def _make_icon_btn(self, vid: str, icon: str, tooltip: str) -> ft.Container:
        btn = ft.Container(
            width=44, height=44,
            border_radius=10,
            bgcolor=SIDEBAR_BG,
            alignment=ft.alignment.center,
            tooltip=tooltip,
            content=ft.Text(icon, size=20, text_align=ft.TextAlign.CENTER),
            on_click=lambda e, v=vid: self._show_view(v),
            on_hover=lambda e, v=vid: self._icon_hover(e, v),
        )
        btn._active = False
        btn._vid    = vid
        return btn

    def _icon_hover(self, e, vid: str):
        btn = self._nav_btns.get(vid)
        if btn and not btn._active:
            btn.bgcolor = NAV_HOVER if e.data == "true" else SIDEBAR_BG
            try: btn.update()
            except Exception: pass

    def _set_nav_active(self, vid: str):
        for v, btn in self._nav_btns.items():
            active = (v == vid)
            btn._active = active
            btn.bgcolor = NAV_ACTIVE if active else SIDEBAR_BG
            try: btn.update()
            except Exception: pass

    def _refresh_instance_icons(self):
        """Regenera los iconos de instancias en el sidebar."""
        self._instances_col.controls.clear()
        profiles = self.profile_manager.get_all_profiles()
        for p in profiles:
            color = AVATAR_PALETTE[abs(hash(p.name)) % len(AVATAR_PALETTE)]
            initial = (p.name[0]).upper() if p.name else "?"
            ic = ft.Container(
                width=40, height=40, border_radius=8,
                bgcolor=color,
                alignment=ft.alignment.center,
                tooltip=p.name,
                content=ft.Text(initial, color=TEXT_INV, size=14,
                                weight=ft.FontWeight.BOLD),
                on_click=lambda e, prof=p: self._show_instance(prof),
                on_hover=lambda e, c=color: (
                    setattr(e.control, "border",
                            ft.border.all(2, GREEN) if e.data=="true"
                            else ft.border.all(0, "transparent"))
                    or e.control.update()),
            )
            self._instances_col.controls.append(ic)
        try:
            self._instances_col.update()
            self._add_instance_btn.update()
        except Exception:
            pass

    # ── Panel derecho ─────────────────────────────────────────────────────────
    def _build_right_panel(self) -> ft.Control:
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
                        ft.Row([self._dot, ft.Container(width=4), self._mode_lbl],
                               spacing=0),
                    ], spacing=2, expand=True),
                ]),
                ft.Container(height=6),
                ft.TextButton(
                    "Gestionar cuentas →",
                    style=ft.ButtonStyle(color=TEXT_SEC,
                                         overlay_color=ft.colors.with_opacity(0.08, GREEN)),
                    on_click=lambda e: self._show_view("accounts"),
                ),
            ], spacing=0),
        )

        self._news_count_lbl = ft.Text("cargando…", color=TEXT_DIM, size=7)
        self._news_col = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        self._news_col.controls.append(
            ft.Container(padding=ft.padding.all(14),
                         content=ft.Text("Conectando…", color=TEXT_DIM, size=9)))

        news_section = ft.Column([
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
        ], spacing=0, expand=True)

        threading.Thread(target=self._fetch_news, daemon=True).start()
        threading.Timer(0.5, self.refresh_account_panel).start()

        return ft.Container(
            width=240,
            bgcolor=SIDEBAR_BG,
            content=ft.Column([
                account_section,
                ft.Divider(height=1, color=BORDER),
                news_section,
            ], spacing=0, expand=True),
        )

    def refresh_account_panel(self):
        try:
            acc = self.account_manager.get_active_account()
            if not acc:
                all_acc = self.account_manager.get_all_accounts()
                acc = all_acc[0] if all_acc else None
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

    # ── Noticias ──────────────────────────────────────────────────────────────
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
            items.append({"tag": "⭐ Release", "tag_color": GREEN,
                          "title": f"Última release: {latest_r}",
                          "body": f"Snapshot: {latest_s}", "source": "Mojang", "url": None})
            type_map = {
                "release":  ("🟢 Release",  GREEN),
                "snapshot": ("🔵 Snapshot", "#4dabf7"),
                "old_beta": ("🟡 Beta",     "#ffa94d"),
                "old_alpha": ("🔴 Alpha",   "#ff6b6b"),
            }
            for v in data["versions"][:4]:
                tag, tc = type_map.get(v["type"], (v["type"], TEXT_SEC))
                items.append({"tag": tag, "tag_color": tc,
                              "title": f"Minecraft {v['id']}",
                              "body": v.get("releaseTime", "")[:10],
                              "source": "Mojang", "url": None})
        except Exception as ex:
            log.warning(f"Noticias Mojang: {ex}")

        try:
            req2 = urllib.request.Request(
                "https://api.modrinth.com/v2/search"
                "?limit=3&index=updated&facets=[[%22project_type:mod%22]]",
                headers={"User-Agent": "GerosLauncher/0.2.0"})
            with urllib.request.urlopen(req2, timeout=8) as r:
                mdata = json.loads(r.read().decode())
            for hit in mdata.get("hits", []):
                desc = hit.get("description", "")
                items.append({"tag": "🧩 Mod", "tag_color": "#a9e34b",
                              "title": hit.get("title", "Mod"),
                              "body": (desc[:60] + "…") if len(desc) > 60 else desc,
                              "source": "Modrinth",
                              "url": f"https://modrinth.com/mod/{hit.get('slug', '')}"})
        except Exception as ex:
            log.warning(f"Noticias Modrinth: {ex}")

        self.page.run_thread(lambda: self._render_news(items))

    def _render_news(self, items: list):
        self._news_col.controls.clear()
        if not items:
            self._news_col.controls.append(
                ft.Container(padding=ft.padding.all(14),
                             content=ft.Text("Sin conexión.", color=TEXT_DIM, size=9)))
            self._news_count_lbl.value = "sin conexión"
        else:
            self._news_count_lbl.value = f"{len(items)}"
            for i, item in enumerate(items):
                if i > 0:
                    self._news_col.controls.append(ft.Divider(height=1, color=BORDER))
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
            bgcolor=SIDEBAR_BG,
            border_radius=4,
            on_click=(lambda e, u=item["url"]: __import__("webbrowser").open(u))
                     if has_url else None,
            on_hover=lambda e: (
                setattr(e.control, "bgcolor", CARD_BG if e.data == "true" else SIDEBAR_BG)
                or e.control.update()),
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

    # ── Navegación ────────────────────────────────────────────────────────────
    def _show_view(self, vid: str):
        self._active_instance = None
        self._set_nav_active(vid)
        self._current_vid = vid

        if vid not in self._views:
            self._views[vid] = self._create_view(vid)

        view_obj = self._views[vid]
        self._content_area.content = view_obj.root
        try: self._content_area.update()
        except Exception: pass

        if hasattr(view_obj, "on_show"):
            view_obj.on_show()

        threading.Timer(0.15, self.refresh_account_panel).start()

    def _show_instance(self, profile):
        """Navega a la vista de instancia para un perfil dado."""
        from gui.views.instance_view import InstanceView
        self._active_instance = profile
        self._set_nav_active("")  # desactivar nav principal

        key = f"instance_{profile.id}"
        if key not in self._views:
            self._views[key] = InstanceView(self.page, self, profile)

        view_obj = self._views[key]
        self._content_area.content = view_obj.root
        try: self._content_area.update()
        except Exception: pass

        if hasattr(view_obj, "on_show"):
            view_obj.on_show()

    def _create_view(self, vid: str):
        from gui.views.home_view     import HomeView
        from gui.views.library_view  import LibraryView
        from gui.views.discover_view import DiscoverView
        from gui.views.settings_view import SettingsView
        from gui.views.accounts_view import AccountsView

        mapping = {
            "home":     HomeView,
            "discover": DiscoverView,
            "library":  LibraryView,
            "settings": SettingsView,
            "accounts": AccountsView,
        }
        cls = mapping.get(vid)
        if cls:
            return cls(self.page, self)
        return _PlaceholderView(self.page, self, vid)

    # ── Abrir diálogo crear instancia desde sidebar ───────────────────────────
    def _open_create_instance(self):
        """Abre el diálogo de crear instancia y luego va a Library."""
        self._show_view("library")
        # Pequeño delay para que el view cargue antes de abrir el diálogo
        def open_dlg():
            lib = self._views.get("library")
            if lib and hasattr(lib, "open_create_dialog"):
                lib.open_create_dialog()
        threading.Timer(0.2, open_dlg).start()

    # ── Invalidar caché de una instancia (llámalo después de editar) ──────────
    def invalidate_instance(self, profile_id: str):
        key = f"instance_{profile_id}"
        if key in self._views:
            del self._views[key]
        self._refresh_instance_icons()

    # ── Snack ─────────────────────────────────────────────────────────────────
    def snack(self, msg: str, error: bool = False):
        bar = ft.SnackBar(
            content=ft.Text(msg, color=TEXT_PRI),
            bgcolor=CARD2_BG if not error else "#2d1515",
            duration=3000,
        )
        self.page.overlay.append(bar)
        bar.open = True
        self.page.update()


class _PlaceholderView:
    def __init__(self, page, app, name):
        self.root = ft.Container(
            expand=True, bgcolor=BG,
            content=ft.Column([
                ft.Text("🚧", size=52, text_align=ft.TextAlign.CENTER),
                ft.Text(name.capitalize(), color=TEXT_SEC, size=18,
                        weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Text("Próximamente", color=TEXT_DIM, size=11,
                        text_align=ft.TextAlign.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               alignment=ft.MainAxisAlignment.CENTER, expand=True),
        )