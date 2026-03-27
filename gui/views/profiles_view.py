"""
gui/views/profiles_view.py
Gestión de perfiles con diálogo multi-paso estilo Modrinth.
  Paso 0 – Tipo de instalación (Custom / Modpack / Import)
  Paso 1 – Configuración: nombre, loader, versión MC
"""
import os
import json
import threading

import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV, ACCENT_RED,
)
from utils.logger import get_logger

log = get_logger()

# ── Paleta del diálogo (más oscura que el resto de la app) ────────────────────
_DLG_BG   = "#0f1117"
_DLG_CARD = "#161b22"
_DLG_SEL  = "#1a2820"   # fondo de loader/versión seleccionado

# ── Loaders disponibles ───────────────────────────────────────────────────────
LOADERS = [
    {"id": "vanilla",  "label": "Vanilla",  "icon": ft.icons.GRASS},
    {"id": "fabric",   "label": "Fabric",   "icon": ft.icons.TEXTURE},
    {"id": "forge",    "label": "Forge",    "icon": ft.icons.HARDWARE},
    {"id": "neoforge", "label": "NeoForge", "icon": ft.icons.AUTO_FIX_HIGH},
    {"id": "quilt",    "label": "Quilt",    "icon": ft.icons.GRID_ON},
]


# ══════════════════════════════════════════════════════════════════════════════
#  Diálogo multi-paso de creación
# ══════════════════════════════════════════════════════════════════════════════
class CreateProfileDialog:
    """
    Diálogo Modrinth-style de 2 pasos para crear un perfil.
    Llama a on_created(profile) cuando el perfil se crea con éxito.
    """

    def __init__(self, page: ft.Page, app, on_created=None):
        self.page       = page
        self.app        = app
        self.on_created = on_created

        # Estado del wizard
        self._step         : int = 0
        self._setup_type   : str = "custom"   # "custom" | "modpack" | "import"
        self._loader       : str = "vanilla"
        self._mc_version   : str | None = None
        self._name         : str = ""

        # Controles que se actualizan entre pasos
        self._content_area = ft.Container(expand=True)
        self._back_btn     = ft.TextButton(
            "← Atrás",
            style=ft.ButtonStyle(color=TEXT_DIM),
            visible=False,
            on_click=self._go_back,
        )
        self._create_btn = ft.ElevatedButton(
            "Continuar",
            bgcolor=GREEN, color="#000000",
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=24, vertical=12),
            ),
            on_click=self._on_primary,
        )

        self._dlg = ft.AlertDialog(
            bgcolor=_DLG_BG,
            title=ft.Row(
                [
                    ft.Text("Nueva instancia", color=TEXT_PRI,
                             size=16, weight=ft.FontWeight.BOLD, expand=True),
                    ft.IconButton(
                        icon=ft.icons.CLOSE, icon_color=TEXT_DIM, icon_size=18,
                        on_click=lambda e: self.page.close(self._dlg),
                        style=ft.ButtonStyle(
                            shape=ft.CircleBorder(),
                            overlay_color={"hovered": "#1f2937"},
                        ),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            content=ft.Container(
                width=620,
                content=ft.Column([
                    self._content_area,
                    ft.Container(height=8),
                ], spacing=0),
            ),
            actions=[
                self._back_btn,
                ft.Container(expand=True),
                ft.TextButton(
                    "Cancelar",
                    style=ft.ButtonStyle(color=TEXT_DIM),
                    on_click=lambda e: self.page.close(self._dlg),
                ),
                ft.Container(width=8),
                self._create_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.START,
        )

        self._render_step0()
        self.page.open(self._dlg)

        # Cargar versiones en background
        threading.Thread(target=self._load_versions, daemon=True).start()

    # ── Pasos ─────────────────────────────────────────────────────────────────
    def _render_step0(self):
        """Paso 0 — Selección del tipo de instalación."""
        self._step = 0
        self._back_btn.visible    = False
        self._create_btn.text     = "Continuar"

        cards = [
            self._type_card(
                "custom", ft.icons.BUILD_CIRCLE_ROUNDED,
                "Custom Setup",
                "Elige tu versión, loader y mods libremente.",
            ),
            self._type_card(
                "modpack", ft.icons.INVENTORY_2_ROUNDED,
                "Modpack Base",
                "Importa un modpack desde Modrinth o CurseForge.",
                disabled=True,
            ),
            self._type_card(
                "import", ft.icons.UPLOAD_FILE_ROUNDED,
                "Import Instance",
                "Importa una instancia existente desde disco.",
                disabled=True,
            ),
        ]

        self._content_area.content = ft.Column(
            cards, spacing=10,
        )
        self._refresh_content()

    def _render_step1(self):
        """Paso 1 — Formulario de configuración."""
        self._step = 1
        self._back_btn.visible = True
        self._create_btn.text  = "+ Crear instancia"

        # ── Campo nombre ──────────────────────────────────────────────────────
        self._name_field = ft.TextField(
            label="Nombre de la instancia",
            value=self._name,
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8,
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            content_padding=ft.padding.symmetric(horizontal=14, vertical=12),
            on_change=self._on_name_change,
        )

        # ── Selector de loader ────────────────────────────────────────────────
        self._loader_btns: dict[str, ft.Container] = {}
        loader_row = ft.Row(spacing=8, wrap=True)
        for l in LOADERS:
            btn = self._loader_btn(l["id"], l["label"], l["icon"])
            self._loader_btns[l["id"]] = btn
            loader_row.controls.append(btn)

        # ── Selector de versión MC ────────────────────────────────────────────
        self._version_dd = ft.Dropdown(
            label="Versión de Minecraft",
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8,
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            options=[],
            hint_text="Cargando versiones…",
            on_change=self._on_version_change,
        )
        # Si ya tenemos versiones del background thread, rellenar ahora
        if hasattr(self, "_available_versions") and self._available_versions:
            self._populate_version_dd()

        # ── RAM ───────────────────────────────────────────────────────────────
        self._ram_dd = ft.Dropdown(
            label="RAM (MB)",
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8,
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            value="2048",
            options=[ft.dropdown.Option(str(x))
                     for x in [1024, 2048, 3072, 4096, 6144, 8192]],
        )

        self._content_area.content = ft.Column([
            # Fila icono + nombre
            ft.Row([
                # Placeholder de icono
                ft.Container(
                    width=72, height=72, border_radius=12,
                    bgcolor=_DLG_CARD,
                    border=ft.border.all(1, BORDER),
                    alignment=ft.alignment.center,
                    content=ft.Icon(ft.icons.IMAGE_ROUNDED,
                                     color=TEXT_DIM, size=28),
                    tooltip="Imagen del perfil (próximamente)",
                ),
                ft.Container(width=16),
                ft.Column([
                    self._name_field,
                ], expand=True, spacing=0),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),

            ft.Container(height=20),

            # Loader
            ft.Text("Loader", color=TEXT_DIM, size=10,
                     weight=ft.FontWeight.BOLD),
            ft.Container(height=8),
            loader_row,

            ft.Container(height=20),

            # Versión + RAM lado a lado
            ft.Row([
                ft.Container(content=self._version_dd, expand=True),
                ft.Container(width=12),
                ft.Container(content=self._ram_dd, width=150),
            ]),
        ], spacing=0)

        self._update_create_btn_state()
        self._refresh_content()

    # ── Widgets helper ─────────────────────────────────────────────────────────
    def _type_card(self, type_id: str, icon, title: str,
                   desc: str, disabled=False) -> ft.Container:
        alpha = 0.35 if disabled else 1.0
        bg    = _DLG_CARD

        def hover(e):
            if disabled: return
            e.control.bgcolor = "#1e2530" if e.data == "true" else _DLG_CARD
            e.control.border  = ft.border.all(
                1, GREEN if e.data == "true" else BORDER)
            e.control.update()

        def click(e):
            if disabled: return
            self._setup_type = type_id
            self._render_step1()

        return ft.Container(
            bgcolor=bg, border_radius=10,
            border=ft.border.all(1, BORDER),
            padding=ft.padding.symmetric(horizontal=20, vertical=18),
            on_hover=hover, on_click=click,
            opacity=alpha,
            content=ft.Row([
                ft.Container(
                    width=44, height=44, border_radius=10,
                    bgcolor="#1f2937",
                    alignment=ft.alignment.center,
                    content=ft.Icon(icon, color=GREEN if not disabled else TEXT_DIM,
                                     size=22),
                ),
                ft.Container(width=16),
                ft.Column([
                    ft.Row([
                        ft.Text(title, color=TEXT_PRI if not disabled else TEXT_DIM,
                                size=13, weight=ft.FontWeight.BOLD),
                        ft.Container(
                            visible=disabled,
                            bgcolor="#1f2937", border_radius=4,
                            padding=ft.padding.symmetric(horizontal=6, vertical=2),
                            content=ft.Text("Próximamente", color=TEXT_DIM, size=8),
                        ),
                    ], spacing=8),
                    ft.Text(desc, color=TEXT_SEC, size=9),
                ], spacing=3, expand=True),
                ft.Icon(ft.icons.CHEVRON_RIGHT_ROUNDED,
                         color=TEXT_DIM if not disabled else "transparent",
                         size=20),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    def _loader_btn(self, loader_id: str, label: str, icon) -> ft.Container:
        is_sel = loader_id == self._loader
        bg     = _DLG_SEL if is_sel else _DLG_CARD
        border = ft.border.all(1.5, GREEN) if is_sel else ft.border.all(1, BORDER)

        def hover(e):
            if loader_id != self._loader:
                e.control.bgcolor = "#1e2530" if e.data == "true" else _DLG_CARD
                e.control.update()

        def click(e):
            self._loader = loader_id
            self._rebuild_loader_btns()

        return ft.Container(
            data=loader_id,
            bgcolor=bg, border_radius=8,
            border=border,
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
            on_hover=hover, on_click=click,
            content=ft.Row([
                ft.Icon(icon, color=GREEN if is_sel else TEXT_DIM, size=14),
                ft.Container(width=6),
                ft.Text(label,
                         color=TEXT_PRI if is_sel else TEXT_SEC,
                         size=10,
                         weight=ft.FontWeight.BOLD if is_sel
                         else ft.FontWeight.NORMAL),
            ], spacing=0, tight=True),
        )

    def _rebuild_loader_btns(self):
        """Regenera los botones de loader para reflejar la selección."""
        for l in LOADERS:
            btn = self._loader_btns.get(l["id"])
            if not btn: continue
            is_sel      = l["id"] == self._loader
            btn.bgcolor = _DLG_SEL if is_sel else _DLG_CARD
            btn.border  = ft.border.all(1.5, GREEN) if is_sel \
                          else ft.border.all(1, BORDER)
            for ctrl in btn.content.controls:
                if isinstance(ctrl, ft.Icon):
                    ctrl.color = GREEN if is_sel else TEXT_DIM
                if isinstance(ctrl, ft.Text):
                    ctrl.color  = TEXT_PRI if is_sel else TEXT_SEC
                    ctrl.weight = (ft.FontWeight.BOLD if is_sel
                                   else ft.FontWeight.NORMAL)
            try: btn.update()
            except Exception: pass

    # ── Cargar versiones MC en background ─────────────────────────────────────
    def _load_versions(self):
        try:
            versions = self.app.version_manager.get_available_versions("release")
            self._available_versions = [v.id for v in versions]
        except Exception:
            self._available_versions = \
                self.app.version_manager.get_installed_version_ids()
        # Si el step1 ya está abierto, poblar el dd ahora
        if self._step == 1:
            self.page.run_thread(self._populate_version_dd)

    def _populate_version_dd(self):
        versions = getattr(self, "_available_versions", [])
        if not versions:
            versions = self.app.version_manager.get_installed_version_ids()
        self._version_dd.options = [ft.dropdown.Option(v) for v in versions]
        self._version_dd.hint_text = None
        if versions:
            self._version_dd.value = (
                self._mc_version if self._mc_version in versions else versions[0]
            )
            self._mc_version = self._version_dd.value
        try: self._version_dd.update()
        except Exception: pass
        self._update_create_btn_state()

    # ── Callbacks ─────────────────────────────────────────────────────────────
    def _on_name_change(self, e):
        self._name = e.control.value
        self._update_create_btn_state()

    def _on_version_change(self, e):
        self._mc_version = e.control.value
        self._update_create_btn_state()

    def _update_create_btn_state(self):
        version_ok = bool(self._mc_version)
        name_ok    = bool(self._name.strip())
        enabled    = (name_ok and version_ok) if self._step == 1 else True
        self._create_btn.disabled = not enabled
        try: self._create_btn.update()
        except Exception: pass

    def _on_primary(self, e):
        if self._step == 0:
            self._render_step1()
        elif self._step == 1:
            self._do_create()

    def _go_back(self, e):
        self._render_step0()

    def _do_create(self):
        name    = getattr(self, "_name_field", None)
        name    = name.value.strip() if name else self._name.strip()
        version = self._mc_version
        ram_val = getattr(self, "_ram_dd", None)
        ram     = int(ram_val.value) if ram_val and ram_val.value else 2048

        if not name or not version:
            self.app.snack("Nombre y versión son obligatorios.", error=True)
            return

        self._create_btn.disabled = True
        self._create_btn.text     = "Creando…"
        try: self._create_btn.update()
        except Exception: pass

        try:
            profile = self.app.profile_manager.create_profile(
                name, version, ram_mb=ram)

            # Guardar loader_meta.json si no es vanilla
            if self._loader != "vanilla":
                meta = [{
                    "loader_type": self._loader,
                    "mc_version":  version,
                    "loader_ver":  "stable",
                    "install_id":  None,
                }]
                meta_path = os.path.join(profile.game_dir, "loader_meta.json")
                os.makedirs(profile.game_dir, exist_ok=True)
                with open(meta_path, "w") as f:
                    json.dump(meta, f, indent=2)

            self.page.close(self._dlg)
            self.app.snack(f"Perfil '{name}' creado.")
            if self.on_created:
                self.on_created(profile)

        except Exception as err:
            self.app.snack(str(err), error=True)
            self._create_btn.disabled = False
            self._create_btn.text     = "+ Crear instancia"
            try: self._create_btn.update()
            except Exception: pass

    # ── Helpers de UI ─────────────────────────────────────────────────────────
    def _refresh_content(self):
        try:
            self._content_area.update()
            self._back_btn.update()
            self._create_btn.update()
        except Exception: pass


# ══════════════════════════════════════════════════════════════════════════════
#  Vista principal de perfiles
# ══════════════════════════════════════════════════════════════════════════════
class ProfilesView:
    def __init__(self, page: ft.Page, app):
        self.page = page
        self.app  = app
        self._selected_id: str | None = None
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build(self):
        # ── Lista ─────────────────────────────────────────────────────────────
        self._profiles_col = ft.Column(
            spacing=4, scroll=ft.ScrollMode.AUTO, expand=True)

        self._empty_hint = ft.Container(
            visible=False, alignment=ft.alignment.center,
            padding=ft.padding.only(top=40),
            content=ft.Column([
                ft.Icon(ft.icons.GRID_VIEW_ROUNDED, size=40, color=TEXT_DIM),
                ft.Container(height=8),
                ft.Text("Sin perfiles", color=TEXT_SEC, size=13,
                         weight=ft.FontWeight.BOLD),
                ft.Text("Crea tu primera instancia con el botón + Nueva instancia.",
                         color=TEXT_DIM, size=10),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )

        list_card = ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.all(20), expand=True,
            content=ft.Column([
                ft.Row([
                    ft.Text("Mis instancias", color=TEXT_PRI, size=14,
                             weight=ft.FontWeight.BOLD, expand=True),
                    ft.ElevatedButton(
                        "+ Nueva instancia",
                        icon=ft.icons.ADD,
                        bgcolor=GREEN, color="#000000",
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.padding.symmetric(horizontal=16, vertical=10),
                        ),
                        on_click=self._open_create_dialog,
                    ),
                ]),
                ft.Container(height=12),
                ft.Stack([
                    self._profiles_col,
                    self._empty_hint,
                ], expand=True),
            ], spacing=0, expand=True),
        )

        # ── Panel de detalle / edición ────────────────────────────────────────
        self._form_title   = ft.Text("Selecciona un perfil",
                                      color=TEXT_PRI, size=14,
                                      weight=ft.FontWeight.BOLD)
        self._name_field   = ft.TextField(
            label="Nombre", color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN, border_radius=8,
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            disabled=True,
        )
        self._version_lbl  = ft.Text("—", color=TEXT_SEC, size=10)
        self._ram_dd       = ft.Dropdown(
            label="RAM (MB)", color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN, border_radius=8,
            label_style=ft.TextStyle(color=TEXT_DIM, size=10),
            value="2048",
            options=[ft.dropdown.Option(str(x))
                     for x in [1024, 2048, 3072, 4096, 6144, 8192]],
            disabled=True,
        )
        self._loader_lbl   = ft.Text("—", color=TEXT_SEC, size=10)
        self._save_btn     = ft.ElevatedButton(
            "Guardar cambios",
            bgcolor=GREEN, color="#000000",
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=18, vertical=12),
            ),
            on_click=self._on_save,
            visible=False,
        )
        self._delete_btn   = ft.ElevatedButton(
            "Eliminar instancia",
            bgcolor="#2d1515", color=ACCENT_RED,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=18, vertical=12),
            ),
            on_click=self._on_delete,
            visible=False,
        )

        self._detail_placeholder = ft.Container(
            expand=True,
            alignment=ft.alignment.center,
            content=ft.Column([
                ft.Icon(ft.icons.INFO_OUTLINE_ROUNDED, size=36, color=TEXT_DIM),
                ft.Container(height=8),
                ft.Text("Selecciona una instancia para ver sus detalles.",
                         color=TEXT_DIM, size=10),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )
        self._detail_form = ft.Container(
            visible=False,
            content=ft.Column([
                self._name_field,
                ft.Container(height=12),
                ft.Row([
                    ft.Column([
                        ft.Text("Versión", color=TEXT_DIM, size=9),
                        self._version_lbl,
                    ], spacing=3),
                    ft.Container(width=24),
                    ft.Column([
                        ft.Text("Loader", color=TEXT_DIM, size=9),
                        self._loader_lbl,
                    ], spacing=3),
                ]),
                ft.Container(height=12),
                self._ram_dd,
                ft.Container(height=20),
                self._save_btn,
                ft.Container(height=8),
                self._delete_btn,
            ], spacing=0),
        )

        detail_card = ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.all(24), width=300,
            content=ft.Column([
                self._form_title,
                ft.Container(height=16),
                ft.Stack([
                    self._detail_placeholder,
                    self._detail_form,
                ]),
            ], spacing=0),
        )

        self.root = ft.Container(
            expand=True, bgcolor=BG,
            padding=ft.padding.all(32),
            content=ft.Column([
                ft.Text("Instancias", color=TEXT_PRI, size=26,
                        weight=ft.FontWeight.BOLD),
                ft.Text("Gestiona tus instancias de Minecraft",
                         color=TEXT_SEC, size=11),
                ft.Container(height=20),
                ft.Row(
                    [list_card, ft.Container(width=20), detail_card],
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
            ], spacing=8),
        )

    # ── Ciclo de vida ─────────────────────────────────────────────────────────
    def on_show(self):
        self._refresh_list()

    # ── Lista ─────────────────────────────────────────────────────────────────
    def _refresh_list(self):
        profiles = self.app.profile_manager.get_all_profiles()
        self._profiles_col.controls.clear()
        self._empty_hint.visible = len(profiles) == 0

        for p in profiles:
            is_sel   = p.id == self._selected_id
            loader   = self._read_loader(p)
            bg       = "#1a2520" if is_sel else INPUT_BG
            border   = ft.border.all(1, GREEN) if is_sel \
                       else ft.border.all(1, "transparent")

            self._profiles_col.controls.append(
                ft.Container(
                    bgcolor=bg, border_radius=8, border=border,
                    padding=ft.padding.symmetric(horizontal=16, vertical=12),
                    on_click=lambda e, pid=p.id: self._on_select(pid),
                    on_hover=lambda e: (
                        setattr(e.control, "bgcolor",
                                CARD2_BG if e.data == "true"
                                else ("#1a2520" if e.control.data == self._selected_id
                                      else INPUT_BG))
                        or e.control.update()
                    ),
                    data=p.id,
                    content=ft.Row([
                        # Icono loader
                        ft.Container(
                            width=38, height=38, border_radius=8,
                            bgcolor=_DLG_CARD,
                            alignment=ft.alignment.center,
                            content=ft.Icon(
                                self._loader_icon(loader),
                                color=GREEN if is_sel else TEXT_DIM,
                                size=18,
                            ),
                        ),
                        ft.Container(width=12),
                        ft.Column([
                            ft.Text(p.name, color=TEXT_PRI, size=11,
                                     weight=ft.FontWeight.BOLD,
                                     overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(
                                f"{p.version_id}  ·  {loader.capitalize()}  ·  {p.ram_mb} MB",
                                color=TEXT_SEC, size=9),
                        ], spacing=2, expand=True),
                        ft.Icon(
                            ft.icons.CHEVRON_RIGHT_ROUNDED,
                            color=GREEN if is_sel else TEXT_DIM,
                            size=16,
                        ),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                )
            )

        try:
            self._profiles_col.update()
            self._empty_hint.update()
        except Exception: pass

    # ── Detalle ───────────────────────────────────────────────────────────────
    def _on_select(self, profile_id: str):
        self._selected_id = profile_id
        profile = self.app.profile_manager.get_profile(profile_id)
        if not profile:
            return

        loader = self._read_loader(profile)

        self._form_title.value         = profile.name
        self._name_field.value         = profile.name
        self._name_field.disabled      = False
        self._version_lbl.value        = profile.version_id
        self._loader_lbl.value         = loader.capitalize()
        self._ram_dd.value             = str(profile.ram_mb)
        self._ram_dd.disabled          = False
        self._save_btn.visible         = True
        self._delete_btn.visible       = True
        self._detail_placeholder.visible = False
        self._detail_form.visible      = True

        try:
            self._form_title.update()
            self._name_field.update()
            self._version_lbl.update()
            self._loader_lbl.update()
            self._ram_dd.update()
            self._save_btn.update()
            self._delete_btn.update()
            self._detail_placeholder.update()
            self._detail_form.update()
        except Exception: pass

        self._refresh_list()

    # ── Guardar / Eliminar ────────────────────────────────────────────────────
    def _on_save(self, e):
        if not self._selected_id:
            return
        name = self._name_field.value.strip()
        ram  = int(self._ram_dd.value) if self._ram_dd.value else 2048
        if not name:
            self.app.snack("El nombre no puede estar vacío.", error=True)
            return
        try:
            self.app.profile_manager.update_profile(
                self._selected_id, name=name, ram_mb=ram)
            self.app.snack("Cambios guardados.")
            self._refresh_list()
        except Exception as err:
            self.app.snack(str(err), error=True)

    def _on_delete(self, e):
        if not self._selected_id:
            return
        profile = self.app.profile_manager.get_profile(self._selected_id)
        if not profile:
            return

        def confirm(e2):
            self.page.close(dlg)
            try:
                self.app.profile_manager.delete_profile(self._selected_id)
                self.app.snack("Instancia eliminada.")
                self._selected_id               = None
                self._detail_form.visible       = False
                self._detail_placeholder.visible= True
                try:
                    self._detail_form.update()
                    self._detail_placeholder.update()
                except Exception: pass
                self._refresh_list()
            except Exception as err:
                self.app.snack(str(err), error=True)

        dlg = ft.AlertDialog(
            title=ft.Text("Eliminar instancia", color=TEXT_PRI),
            content=ft.Text(
                f"¿Seguro que quieres eliminar '{profile.name}'? "
                "Esta acción no se puede deshacer.",
                color=TEXT_SEC,
            ),
            bgcolor=CARD_BG,
            actions=[
                ft.TextButton("Cancelar",
                               on_click=lambda e2: self.page.close(dlg)),
                ft.ElevatedButton(
                    "Eliminar", bgcolor="#2d1515", color=ACCENT_RED,
                    on_click=confirm,
                ),
            ],
        )
        self.page.open(dlg)

    # ── Diálogo de creación ───────────────────────────────────────────────────
    def _open_create_dialog(self, e):
        CreateProfileDialog(
            self.page, self.app,
            on_created=lambda p: self._refresh_list(),
        )

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _read_loader(profile) -> str:
        """Lee el loader desde loader_meta.json del perfil."""
        meta_path = os.path.join(profile.game_dir, "loader_meta.json")
        if os.path.isfile(meta_path):
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                entries = meta if isinstance(meta, list) else [meta]
                if entries:
                    return entries[0].get("loader_type", "vanilla")
            except Exception:
                pass
        return "vanilla"

    @staticmethod
    def _loader_icon(loader: str):
        return {
            "fabric":   ft.icons.TEXTURE,
            "forge":    ft.icons.HARDWARE,
            "neoforge": ft.icons.AUTO_FIX_HIGH,
            "quilt":    ft.icons.GRID_ON,
        }.get(loader, ft.icons.GRASS)