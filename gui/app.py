"""
gui/app.py — Gero's Launcher
Shell principal: titlebar, sidebar, área de contenido y panel derecho.
Reescrito completamente en Flet.
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


class App:
    def __init__(self, page: ft.Page):
        self.page = page
        self._views: dict = {}          # vid -> view object
        self._nav_btns: dict = {}       # vid -> ft.Container
        self._current_vid: str | None = None

        self._setup_page()
        self._init_services()
        self._build_layout()
        self._show_view("home")
        log.info("Interfaz Flet iniciada")

    # ── Configuración de la ventana ───────────────────────────────────────────
    def _setup_page(self):
        p = self.page
        p.title = "Gero's Launcher"
        p.window.width       = 1380
        p.window.height      = 780
        p.window.min_width   = 1100
        p.window.min_height  = 640
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

    # ── Layout principal ──────────────────────────────────────────────────────
    def _build_layout(self):
        self._content_area = ft.Container(
            expand=True,
            bgcolor=BG,
        )

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

    # ── Titlebar personalizada ────────────────────────────────────────────────
    def _build_titlebar(self) -> ft.Control:
        def wbtn(color: str, hover: str, cmd):
            c = ft.Container(
                width=14, height=14,
                border_radius=7,
                bgcolor=color,
                tooltip="",
                on_click=lambda e: cmd(),
                on_hover=lambda e, nc=color, hc=hover: (
                    setattr(e.control, "bgcolor", hc if e.data == "true" else nc)
                    or e.control.update()
                ),
            )
            return c

        bar_content = ft.Row(
            controls=[
                ft.Text("⛏", color=GREEN, size=16),
                ft.Container(width=8),
                ft.Text("Gero's Launcher", color=TEXT_PRI, size=11,
                        weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.Container(
                    bgcolor="#172616",
                    border_radius=4,
                    padding=ft.padding.symmetric(horizontal=10, vertical=3),
                    content=ft.Text("v0.2.0", color=GREEN, size=8,
                                    weight=ft.FontWeight.BOLD),
                ),
                ft.Container(width=20),
                ft.Row([
                    wbtn("#ff5f57", "#ff3b30", lambda: self.page.window.close()),
                    wbtn("#febc2e", "#f0a500", self._minimize),
                    wbtn("#28c840", "#1da831", self._toggle_maximize),
                ], spacing=8),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ft.WindowDragArea(
            ft.Container(
                bgcolor=SIDEBAR_BG,
                height=48,
                padding=ft.padding.symmetric(horizontal=20),
                content=bar_content,
            ),
        )

    def _minimize(self):
        self.page.window.minimized = True
        self.page.update()

    def _toggle_maximize(self):
        self.page.window.maximized = not self.page.window.maximized
        self.page.update()

    # ── Sidebar izquierda ─────────────────────────────────────────────────────
    def _build_sidebar(self) -> ft.Control:
        menu_items    = [("home","🏠","Inicio"),("discover","🔍","Descubrir"),
                         ("library","📦","Biblioteca"),("mods","🧩","Mods")]
        account_items = [("settings","⚙️","Ajustes"),("accounts","👤","Cuentas")]

        rows = []
        rows.append(ft.Container(
            padding=ft.padding.only(left=16, top=16, bottom=4),
            content=ft.Text("MENÚ", color=TEXT_DIM, size=8,
                            weight=ft.FontWeight.BOLD),
        ))
        for vid, icon, label in menu_items:
            btn = self._make_nav_btn(vid, icon, label)
            self._nav_btns[vid] = btn
            rows.append(btn)

        rows.append(ft.Container(height=6))
        rows.append(ft.Divider(height=1, color=BORDER))
        rows.append(ft.Container(
            padding=ft.padding.only(left=16, top=12, bottom=4),
            content=ft.Text("CUENTA", color=TEXT_DIM, size=8,
                            weight=ft.FontWeight.BOLD),
        ))
        for vid, icon, label in account_items:
            btn = self._make_nav_btn(vid, icon, label)
            self._nav_btns[vid] = btn
            rows.append(btn)

        rows.append(ft.Container(expand=True))
        rows.append(ft.Container(
            padding=ft.padding.only(left=16, bottom=14),
            content=ft.Text("Gero's Launcher  •  v0.2.0",
                            color=TEXT_DIM, size=8),
        ))

        return ft.Container(
            width=220,
            bgcolor=SIDEBAR_BG,
            content=ft.Column(rows, spacing=2, expand=True),
        )

    def _make_nav_btn(self, vid: str, icon: str, label: str) -> ft.Container:
        icon_t = ft.Text(icon, color=TEXT_SEC, size=14, width=28)
        text_t = ft.Text(label, color=TEXT_SEC, size=11, expand=True)

        btn = ft.Container(
            bgcolor=SIDEBAR_BG,
            border_radius=8,
            margin=ft.margin.symmetric(horizontal=10, vertical=2),
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
            content=ft.Row([icon_t, text_t]),
            on_click=lambda e, v=vid: self._show_view(v),
            on_hover=lambda e, v=vid: self._nav_hover(e, v),
        )
        btn._icon_t  = icon_t
        btn._text_t  = text_t
        btn._active  = False
        return btn

    def _nav_hover(self, e, vid: str):
        btn = self._nav_btns.get(vid)
        if btn and not btn._active:
            btn.bgcolor = NAV_HOVER if e.data == "true" else SIDEBAR_BG
            try: btn.update()
            except Exception: pass

    def _set_nav_active(self, vid: str):
        for v, btn in self._nav_btns.items():
            active = (v == vid)
            btn._active = active
            if active:
                btn.bgcolor = NAV_ACTIVE
                btn._icon_t.color = GREEN
                btn._text_t.color = TEXT_PRI
                btn._text_t.weight = ft.FontWeight.BOLD
            else:
                btn.bgcolor = SIDEBAR_BG
                btn._icon_t.color = TEXT_SEC
                btn._text_t.color = TEXT_SEC
                btn._text_t.weight = ft.FontWeight.NORMAL
            try: btn.update()
            except Exception: pass

    # ── Panel derecho ─────────────────────────────────────────────────────────
    def _build_right_panel(self) -> ft.Control:
        # Avatar
        self._avatar_text = ft.Text("??", color=TEXT_INV, size=12,
                                     weight=ft.FontWeight.BOLD)
        self._avatar_box = ft.Container(
            width=38, height=38, border_radius=19,
            bgcolor=GREEN,
            alignment=ft.alignment.center,
            content=self._avatar_text,
        )
        self._username_lbl = ft.Text("—", color=TEXT_PRI, size=10,
                                      weight=ft.FontWeight.BOLD)
        self._dot = ft.Container(width=8, height=8, border_radius=4,
                                  bgcolor=TEXT_DIM)
        self._mode_lbl = ft.Text("Sin cuenta", color=TEXT_DIM, size=8)

        account_section = ft.Container(
            padding=ft.padding.all(18),
            content=ft.Column([
                ft.Text("JUGANDO COMO", color=TEXT_DIM, size=8,
                        weight=ft.FontWeight.BOLD),
                ft.Container(height=10),
                ft.Row([
                    self._avatar_box,
                    ft.Container(width=12),
                    ft.Column([
                        self._username_lbl,
                        ft.Row([self._dot, ft.Container(width=4), self._mode_lbl],
                               spacing=0),
                    ], spacing=2, expand=True),
                ]),
                ft.Container(height=8),
                ft.TextButton(
                    "Gestionar cuentas →",
                    style=ft.ButtonStyle(color=TEXT_SEC,
                                         overlay_color=ft.colors.with_opacity(0.08, GREEN)),
                    on_click=lambda e: self._show_view("accounts"),
                ),
            ], spacing=0),
        )

        # Noticias
        self._news_count_lbl = ft.Text("cargando…", color=TEXT_DIM, size=7)
        self._news_col = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        self._news_col.controls.append(
            ft.Container(padding=ft.padding.all(14),
                         content=ft.Text("Conectando…", color=TEXT_DIM, size=9)))

        news_section = ft.Column([
            ft.Container(
                padding=ft.padding.only(left=18, right=18, top=14, bottom=8),
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
        threading.Timer(0.6, self.refresh_account_panel).start()

        return ft.Container(
            width=250,
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
            items.append({"tag":"⭐ Destacado","tag_color":GREEN,
                          "title":f"Última release: {latest_r}",
                          "body":f"Snapshot: {latest_s}","source":"Mojang","url":None})
            type_map = {
                "release":  ("🟢 Release",  GREEN),
                "snapshot": ("🔵 Snapshot", "#4dabf7"),
                "old_beta": ("🟡 Beta",     "#ffa94d"),
                "old_alpha":("🔴 Alpha",    "#ff6b6b"),
            }
            for v in data["versions"][:5]:
                tag, tc = type_map.get(v["type"], (v["type"], TEXT_SEC))
                items.append({"tag":tag,"tag_color":tc,
                              "title":f"Minecraft {v['id']}",
                              "body":v.get("releaseTime","")[:10],
                              "source":"Mojang","url":None})
        except Exception as ex:
            log.warning(f"Noticias Mojang: {ex}")

        try:
            req2 = urllib.request.Request(
                "https://api.modrinth.com/v2/search"
                "?limit=4&index=updated&facets=[[%22project_type:mod%22]]",
                headers={"User-Agent": "GerosLauncher/0.2.0"})
            with urllib.request.urlopen(req2, timeout=8) as r:
                mdata = json.loads(r.read().decode())
            for hit in mdata.get("hits", []):
                desc = hit.get("description", "")
                items.append({"tag":"🧩 Mod","tag_color":"#a9e34b",
                              "title":hit.get("title","Mod"),
                              "body":(desc[:60]+"…") if len(desc)>60 else desc,
                              "source":"Modrinth",
                              "url":f"https://modrinth.com/mod/{hit.get('slug','')}"})
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
            self._news_count_lbl.value = f"{len(items)} entradas"
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
                setattr(e.control, "bgcolor", CARD_BG if e.data=="true" else SIDEBAR_BG)
                or e.control.update()),
            content=ft.Column([
                ft.Row([
                    ft.Text(item["tag"], color=item.get("tag_color",GREEN),
                            size=8, weight=ft.FontWeight.BOLD, expand=True),
                    ft.Text(item["source"], color=TEXT_DIM, size=7),
                ]),
                ft.Text(item["title"], color=TEXT_PRI, size=9,
                        weight=ft.FontWeight.BOLD,
                        overflow=ft.TextOverflow.ELLIPSIS, max_lines=2),
                ft.Text(item.get("body",""), color=TEXT_SEC, size=8,
                        overflow=ft.TextOverflow.ELLIPSIS)
                if item.get("body") else ft.Container(height=0),
            ], spacing=2),
        )

    # ── Navegación ────────────────────────────────────────────────────────────
    def _show_view(self, vid: str):
        self._set_nav_active(vid)
        self._current_vid = vid

        if vid not in self._views:
            self._views[vid] = self._create_view(vid)

        view_obj = self._views[vid]
        self._content_area.content = view_obj.root
        self._content_area.update()

        if hasattr(view_obj, "on_show"):
            view_obj.on_show()

        threading.Timer(0.15, self.refresh_account_panel).start()

    def _create_view(self, vid: str):
        from gui.views.home_view     import HomeView
        from gui.views.profiles_view import ProfilesView
        from gui.views.mods_view     import ModsView
        from gui.views.discover_view import DiscoverView
        from gui.views.library_view  import LibraryView
        from gui.views.settings_view import SettingsView
        from gui.views.accounts_view import AccountsView

        mapping = {
            "home":     HomeView,
            "profiles": ProfilesView,
            "mods":     ModsView,
            "discover": DiscoverView,
            "library":  LibraryView,
            "settings": SettingsView,
            "accounts": AccountsView,
        }
        cls = mapping.get(vid)
        if cls:
            return cls(self.page, self)
        return _PlaceholderView(self.page, self, vid)

    # ── Helper de snackbar ────────────────────────────────────────────────────
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
    def __init__(self, page: ft.Page, app: "App", name: str):
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