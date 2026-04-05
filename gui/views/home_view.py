"""
gui/views/home_view.py — Home estilo Modrinth: mods + modpacks populares
"""
import json
import threading
import urllib.request
import urllib.parse

import flet as ft
from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER, BORDER_BRIGHT,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM,
)

_HEADERS = {"User-Agent": "PyLauncher/1.0"}

_URL_MODS = (
    "https://api.modrinth.com/v2/search"
    "?limit=6&index=downloads"
    '&facets=[[%22project_type:mod%22]]'
)
_URL_MODPACKS = (
    "https://api.modrinth.com/v2/search"
    "?limit=6&index=downloads"
    '&facets=[[%22project_type:modpack%22]]'
)


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _get(url: str) -> dict | list:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def _fetch_with_gallery(search_url: str) -> list[dict]:
    """
    1) Busca en Modrinth (devuelve featured_gallery pero no gallery completa).
    2) Hace un bulk fetch a /v2/projects?ids=[...] para obtener la galería real.
    3) Mezcla los datos: usa la primera imagen de gallery como banner si existe.
    """
    hits = _get(search_url).get("hits", [])
    if not hits:
        return []

    # IDs de los proyectos
    ids = [h["project_id"] for h in hits]
    ids_param = urllib.parse.quote(json.dumps(ids))
    bulk_url  = f"https://api.modrinth.com/v2/projects?ids={ids_param}"
    projects  = {p["id"]: p for p in _get(bulk_url)}

    # Enriquecer hits con gallery del proyecto completo
    for hit in hits:
        proj = projects.get(hit["project_id"], {})
        gallery = proj.get("gallery") or []
        # Preferir imagen marcada como featured, si no la primera
        featured = next((g["url"] for g in gallery if g.get("featured")), None)
        fallback = gallery[0]["url"] if gallery else None
        hit["_banner"] = featured or fallback or hit.get("featured_gallery") or ""

    return hits


class HomeView:
    def __init__(self, page: ft.Page, app):
        self.page    = page
        self.app     = app
        self._loaded = False

        self._mods_row     = ft.Row(controls=[], scroll=ft.ScrollMode.AUTO, spacing=16)
        self._packs_row    = ft.Row(controls=[], scroll=ft.ScrollMode.AUTO, spacing=16)
        self._mods_status  = ft.Text("Cargando…", color=TEXT_DIM, size=12, italic=True)
        self._packs_status = ft.Text("Cargando…", color=TEXT_DIM, size=12, italic=True)

        self.root = ft.Container(
            expand=True,
            bgcolor=BG,
            padding=ft.padding.all(28),
            content=ft.Column(
                [
                    self._build_header(),
                    ft.Divider(height=1, color=BORDER, thickness=1),
                    ft.Row(
                        [
                            ft.Text("Mods populares", color=TEXT_PRI, size=15,
                                    weight=ft.FontWeight.W_600),
                            self._mods_status,
                        ],
                        spacing=14,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(content=self._mods_row, height=340),
                    ft.Divider(height=1, color=BORDER, thickness=1),
                    ft.Row(
                        [
                            ft.Text("Modpacks populares", color=TEXT_PRI, size=15,
                                    weight=ft.FontWeight.W_600),
                            self._packs_status,
                        ],
                        spacing=14,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(content=self._packs_row, height=340),
                ],
                spacing=14,
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
        )

    def _build_header(self) -> ft.Control:
        return ft.Column(
            [
                ft.Text("¡Bienvenido a PyLauncher!", size=30,
                        weight=ft.FontWeight.BOLD, color=TEXT_PRI),
                ft.TextButton(
                    content=ft.Row(
                        [
                            ft.Text("Descubrir mods", color=GREEN, size=13,
                                    weight=ft.FontWeight.W_600),
                            ft.Icon(ft.icons.CHEVRON_RIGHT, color=GREEN, size=18),
                        ],
                        spacing=2,
                    ),
                    on_click=self._go_to_mods,
                    style=ft.ButtonStyle(
                        padding=ft.padding.all(0),
                        overlay_color=ft.colors.TRANSPARENT,
                    ),
                ),
            ],
            spacing=2,
        )

    def _go_to_mods(self, _e):
        try:
            self.app.navigate("mods")
        except Exception:
            pass

    def on_show(self):
        if not self._loaded:
            self._loaded = True
            threading.Thread(target=self._load_mods,     daemon=True).start()
            threading.Thread(target=self._load_modpacks, daemon=True).start()

    def _load_mods(self):
        self._load_section(_URL_MODS, self._mods_row, self._mods_status, "mod")

    def _load_modpacks(self):
        self._load_section(_URL_MODPACKS, self._packs_row, self._packs_status, "modpack")

    def _load_section(self, url: str, row: ft.Row, status: ft.Text, kind: str):
        try:
            hits = _fetch_with_gallery(url)
            row.controls = [self._build_card(h, kind) for h in hits]
            status.visible = False
        except Exception as exc:
            status.value  = f"Error — {exc}"
            status.color  = "#ff6b6b"
            status.italic = False
        self.page.update()

    def _build_card(self, mod: dict, kind: str = "mod") -> ft.Container:
        icon_url  = mod.get("icon_url") or ""
        banner_url = mod.get("_banner") or ""
        title     = mod.get("title", "?")
        raw_desc  = mod.get("description", "")
        desc      = (raw_desc[:90] + "…") if len(raw_desc) > 90 else raw_desc
        downloads = _fmt(mod.get("downloads", 0))
        follows   = _fmt(mod.get("follows", 0))
        cats      = mod.get("display_categories") or mod.get("categories") or []
        cat_label = cats[0].capitalize() if cats else ""

        banner: ft.Control = (
            ft.Image(
                src=banner_url, width=260, height=130,
                fit=ft.ImageFit.COVER,
                border_radius=ft.border_radius.only(top_left=10, top_right=10),
                error_content=self._banner_ph(kind),
            )
            if banner_url else self._banner_ph(kind)
        )

        icon: ft.Control = (
            ft.Image(
                src=icon_url, width=40, height=40,
                border_radius=ft.border_radius.all(8),
                fit=ft.ImageFit.COVER,
                error_content=self._icon_ph(kind),
            )
            if icon_url else self._icon_ph(kind)
        )

        stat_items = [
            ft.Icon(ft.icons.DOWNLOAD_OUTLINED, size=13, color=TEXT_DIM),
            ft.Text(downloads, size=11, color=TEXT_DIM),
            ft.Icon(ft.icons.FAVORITE_BORDER,   size=13, color=TEXT_DIM),
            ft.Text(follows,   size=11, color=TEXT_DIM),
        ]
        if cat_label:
            stat_items += [
                ft.Icon(ft.icons.LABEL_OUTLINE, size=13, color=TEXT_DIM),
                ft.Container(
                    content=ft.Text(cat_label, size=10, color=TEXT_DIM),
                    padding=ft.padding.symmetric(horizontal=7, vertical=3),
                    bgcolor=CARD2_BG, border_radius=10,
                ),
            ]

        body = ft.Container(
            padding=ft.padding.all(11),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            icon,
                            ft.Text(title, size=14, weight=ft.FontWeight.BOLD,
                                    color=TEXT_PRI, expand=True,
                                    overflow=ft.TextOverflow.ELLIPSIS, max_lines=1),
                        ],
                        spacing=9,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(desc, size=11, color=TEXT_SEC,
                            max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row(stat_items, spacing=5),
                ],
                spacing=7,
            ),
        )

        return ft.Container(
            width=260,
            bgcolor=CARD_BG,
            border_radius=10,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            border=ft.border.all(1, BORDER),
            content=ft.Column([banner, body], spacing=0),
            on_hover=self._on_card_hover,
        )

    @staticmethod
    def _banner_ph(kind: str = "mod") -> ft.Container:
        ico = ft.icons.WIDGETS_OUTLINED if kind == "modpack" else ft.icons.EXTENSION_OUTLINED
        return ft.Container(
            width=260, height=130, bgcolor=INPUT_BG,
            border_radius=ft.border_radius.only(top_left=10, top_right=10),
            content=ft.Icon(ico, color=TEXT_DIM, size=36),
            alignment=ft.alignment.center,
        )

    @staticmethod
    def _icon_ph(kind: str = "mod") -> ft.Container:
        ico = ft.icons.WIDGETS_OUTLINED if kind == "modpack" else ft.icons.EXTENSION_OUTLINED
        return ft.Container(
            width=40, height=40, bgcolor=INPUT_BG,
            border_radius=ft.border_radius.all(8),
            content=ft.Icon(ico, color=TEXT_DIM, size=20),
            alignment=ft.alignment.center,
        )

    @staticmethod
    def _on_card_hover(e: ft.HoverEvent):
        e.control.border = ft.border.all(1, BORDER_BRIGHT if e.data == "true" else BORDER)
        e.control.update()