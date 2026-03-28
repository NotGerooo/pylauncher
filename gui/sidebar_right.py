"""
gui/sidebar_right.py — Panel derecho.
Cuenta activa + feed de noticias (Mojang / Modrinth).
"""
import threading
import urllib.request
import json
import flet as ft

from gui.theme import (
    SIDEBAR_BG, CARD_BG, BORDER,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV,
    AVATAR_PALETTE,
)
from utils.logger import get_logger

log = get_logger()


class SidebarRight:
    def __init__(self, app):
        self.app = app
        self._build()
        threading.Thread(target=self._fetch_news, daemon=True).start()
        threading.Timer(0.5, self.refresh_account).start()

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self):
        # ── Sección de cuenta ─────────────────────────────────────────────
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

        # ── Sección de noticias ───────────────────────────────────────────
        self._news_count_lbl = ft.Text("cargando…", color=TEXT_DIM, size=7)
        self._news_col = ft.Column(
            spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        self._news_col.controls.append(
            ft.Container(
                padding=ft.padding.all(14),
                content=ft.Text("Conectando…", color=TEXT_DIM, size=9),
            )
        )

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

        self.root = ft.Container(
            width=240,
            bgcolor=SIDEBAR_BG,
            content=ft.Column([
                account_section,
                ft.Divider(height=1, color=BORDER),
                news_section,
            ], spacing=0, expand=True),
        )

    # ── Cuenta ────────────────────────────────────────────────────────────────
    def refresh_account(self):
        try:
            acc = self.app.account_manager.get_active_account()
            if not acc:
                all_acc = self.app.account_manager.get_all_accounts()
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
            items.append({
                "tag": "⭐ Release", "tag_color": GREEN,
                "title": f"Última release: {latest_r}",
                "body": f"Snapshot: {latest_s}",
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
                    "body": v.get("releaseTime", "")[:10],
                    "source": "Mojang", "url": None,
                })
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
                items.append({
                    "tag": "🧩 Mod", "tag_color": "#a9e34b",
                    "title": hit.get("title", "Mod"),
                    "body": (desc[:60] + "…") if len(desc) > 60 else desc,
                    "source": "Modrinth",
                    "url": f"https://modrinth.com/mod/{hit.get('slug', '')}",
                })
        except Exception as ex:
            log.warning(f"Noticias Modrinth: {ex}")

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
            bgcolor=SIDEBAR_BG,
            border_radius=4,
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