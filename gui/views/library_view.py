"""
gui/views/library_view.py — Gero's Launcher
Vista Biblioteca: instancias con diálogo crear/editar estilo Modrinth.
"""
import threading
import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER, BORDER_BRIGHT,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV, ACCENT_RED,
)
from utils.logger import get_logger

log = get_logger()

LOADER_LIST = [
    ("vanilla",  "Vanilla"),
    ("fabric",   "Fabric"),
    ("neoforge", "NeoForge"),
    ("forge",    "Forge"),
    ("quilt",    "Quilt"),
    ("optifine", "OptiFine"),
]

LOADER_ICONS = {
    "vanilla":  "🎮",
    "fabric":   "🪡",
    "neoforge": "🔷",
    "forge":    "🔨",
    "quilt":    "🪢",
    "optifine": "✨",
}


# ═══════════════════════════════════════════════════════════════════════════════
class LibraryView:
    def __init__(self, page: ft.Page, app):
        self.page = page
        self.app  = app

        self._list_col = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

        self.root = ft.Container(
            expand=True,
            bgcolor=BG,
            padding=ft.padding.symmetric(horizontal=36, vertical=28),
            content=ft.Column(
                spacing=0, expand=True,
                controls=[
                    self._build_header(),
                    ft.Container(height=20),
                    self._list_col,
                ],
            ),
        )

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self) -> ft.Control:
        return ft.Row(
            controls=[
                ft.Column(spacing=2, expand=True, controls=[
                    ft.Text("Biblioteca", color=TEXT_PRI, size=22,
                            weight=ft.FontWeight.BOLD),
                    ft.Text("Tus instancias de Minecraft", color=TEXT_DIM, size=11),
                ]),
                ft.ElevatedButton(
                    "+ Nueva Instancia", bgcolor=GREEN, color=TEXT_INV,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=lambda e: self._open_create_dialog(),
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    def on_show(self):
        self._refresh()

    def _refresh(self):
        self._list_col.controls.clear()
        profiles = self.app.profile_manager.get_all_profiles()
        if not profiles:
            self._list_col.controls.append(self._empty_state())
        else:
            for p in profiles:
                self._list_col.controls.append(self._build_card(p))
        try: self._list_col.update()
        except Exception: pass

    # ── Estado vacío ──────────────────────────────────────────────────────────
    def _empty_state(self) -> ft.Control:
        return ft.Container(expand=True, content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            expand=True,
            controls=[
                ft.Text("📦", size=52, text_align=ft.TextAlign.CENTER),
                ft.Text("No tienes instancias creadas", color=TEXT_SEC, size=14,
                        text_align=ft.TextAlign.CENTER),
                ft.Text("Crea tu primera instancia con '+ Nueva Instancia'",
                        color=TEXT_DIM, size=10, text_align=ft.TextAlign.CENTER),
                ft.Container(height=12),
                ft.Row([ft.ElevatedButton(
                    "+ Nueva Instancia", bgcolor=GREEN, color=TEXT_INV,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=lambda e: self._open_create_dialog(),
                )], alignment=ft.MainAxisAlignment.CENTER),
            ],
        ))

    # ── Tarjeta ───────────────────────────────────────────────────────────────
    def _build_card(self, profile) -> ft.Control:
        from managers.loader_manager import load_loader_meta
        meta   = load_loader_meta(profile.game_dir)
        loader = meta.get("loader", "vanilla") if isinstance(meta, dict) else "vanilla"
        icon   = LOADER_ICONS.get(loader, "🎮")
        last   = profile.last_used[:10] if profile.last_used else "—"

        badge = ft.Container(
            bgcolor=CARD2_BG, border_radius=4,
            padding=ft.padding.symmetric(horizontal=6, vertical=2),
            content=ft.Text(loader.capitalize(),
                            color=GREEN if loader != "vanilla" else TEXT_SEC,
                            size=8, weight=ft.FontWeight.BOLD),
        )

        return ft.Container(
            bgcolor=CARD_BG, border_radius=12,
            padding=ft.padding.symmetric(horizontal=20, vertical=14),
            border=ft.border.all(1, BORDER),
            content=ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(width=48, height=48, border_radius=10,
                                 bgcolor=CARD2_BG, alignment=ft.alignment.center,
                                 content=ft.Text(icon, size=22)),
                    ft.Container(width=16),
                    ft.Column(spacing=3, expand=True, controls=[
                        ft.Row([
                            ft.Text(profile.name, color=TEXT_PRI, size=13,
                                    weight=ft.FontWeight.BOLD),
                            badge,
                        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Text(f"Minecraft {profile.version_id}  •  RAM: {profile.ram_mb} MB",
                                color=TEXT_SEC, size=9),
                        ft.Text(f"Última vez: {last}", color=TEXT_DIM, size=8),
                    ]),
                    ft.Row(spacing=8, controls=[
                        ft.ElevatedButton(
                            "▶ Jugar", bgcolor=GREEN, color=TEXT_INV, height=34,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
                            on_click=lambda e, p=profile: self._open_launch_dialog(p),
                        ),
                        ft.OutlinedButton(
                            "✏ Editar", height=34,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=6),
                                side=ft.BorderSide(1, BORDER_BRIGHT), color=TEXT_SEC),
                            on_click=lambda e, p=profile: self._open_edit_dialog(p),
                        ),
                        ft.OutlinedButton(
                            "🗑", height=34,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=6),
                                side=ft.BorderSide(1, ACCENT_RED), color=ACCENT_RED),
                            on_click=lambda e, p=profile: self._on_delete(p),
                        ),
                    ]),
                ],
            ),
        )

    # ── Acciones ──────────────────────────────────────────────────────────────
    def _on_delete(self, profile):
        def confirm(e):
            if e.control.text == "Eliminar":
                try:
                    self.app.profile_manager.delete_profile(profile.id)
                    self._refresh()
                    self.app.snack(f"'{profile.name}' eliminada.")
                except Exception as ex:
                    self.app.snack(str(ex), error=True)
            self.page.close(dlg)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Eliminar instancia", color=TEXT_PRI),
            content=ft.Text(f"¿Eliminar '{profile.name}'?\n"
                            "Esto no borra los archivos del juego.", color=TEXT_SEC),
            actions=[
                ft.TextButton("Cancelar", on_click=confirm),
                ft.TextButton("Eliminar",
                              style=ft.ButtonStyle(color=ACCENT_RED),
                              on_click=confirm),
            ],
        )
        self.page.open(dlg)

    def _open_create_dialog(self):
        _InstanceDialog(self.page, self.app, None, self._refresh).open()

    def _open_edit_dialog(self, profile):
        _InstanceDialog(self.page, self.app, profile, self._refresh).open()

    def _open_launch_dialog(self, profile):
        _LaunchDialog(self.page, self.app, profile).open()


# ═══════════════════════════════════════════════════════════════════════════════
# Diálogo crear / editar  (estilo Modrinth)
# ═══════════════════════════════════════════════════════════════════════════════
class _InstanceDialog:
    def __init__(self, page: ft.Page, app, profile, on_save):
        self.page    = page
        self.app     = app
        self.profile = profile
        self.on_save = on_save

        # Estado seleccionado
        from managers.loader_manager import load_loader_meta
        if profile:
            meta = load_loader_meta(profile.game_dir)
            self._sel_loader = meta.get("loader", "vanilla") if isinstance(meta, dict) else "vanilla"
            self._sel_mc     = profile.version_id
            self._sel_lv_key = "stable"          # pill
            self._sel_lv_val = meta.get("loader_version") if isinstance(meta, dict) else ""
        else:
            self._sel_loader = "vanilla"
            self._sel_mc     = ""
            self._sel_lv_key = "stable"
            self._sel_lv_val = ""

        # Controles reutilizables
        self._loader_btns: dict[str, ft.Container] = {}
        self._lv_btns:     dict[str, ft.Container] = {}

        installed = app.version_manager.get_installed_version_ids()
        mc_val = self._sel_mc if self._sel_mc in installed else (installed[0] if installed else None)
        self._sel_mc = mc_val or ""

        self._name_field = ft.TextField(
            label="Nombre", bgcolor=INPUT_BG, color=TEXT_PRI,
            label_style=ft.TextStyle(color=TEXT_DIM),
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, value=profile.name if profile else "",
        )
        self._mc_dd = ft.Dropdown(
            label="Versión del juego", bgcolor=INPUT_BG, color=TEXT_PRI,
            label_style=ft.TextStyle(color=TEXT_DIM),
            border_color=BORDER, focused_border_color=GREEN, border_radius=8,
            options=[ft.dropdown.Option(v) for v in installed],
            value=mc_val,
            on_change=self._on_mc_change,
        )
        ram_opts = ["1024","2048","3072","4096","6144","8192"]
        cur_ram  = str(profile.ram_mb) if profile else "2048"
        self._ram_dd = ft.Dropdown(
            label="RAM (MB)", bgcolor=INPUT_BG, color=TEXT_PRI,
            label_style=ft.TextStyle(color=TEXT_DIM),
            border_color=BORDER, focused_border_color=GREEN, border_radius=8,
            options=[ft.dropdown.Option(r) for r in ram_opts],
            value=cur_ram if cur_ram in ram_opts else "2048",
        )
        self._lv_dd = ft.Dropdown(
            label="Versión específica", bgcolor=INPUT_BG, color=TEXT_PRI,
            label_style=ft.TextStyle(color=TEXT_DIM),
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, visible=False, options=[],
        )
        self._prog_bar  = ft.ProgressBar(color=GREEN, bgcolor=CARD2_BG, visible=False)
        self._prog_text = ft.Text("", color=TEXT_DIM, size=9)
        self._save_btn  = ft.ElevatedButton(
            ("Crear instancia" if not profile else "Guardar cambios"),
            bgcolor=GREEN, color=TEXT_INV,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=self._on_save,
        )

        # Filas de pills
        loader_row = ft.Row(spacing=8, wrap=True,
                            controls=[self._make_loader_pill(lid, lname)
                                      for lid, lname in LOADER_LIST])
        self._lv_pills_row = ft.Row(spacing=8, controls=[
            self._make_lv_pill("stable", "Stable"),
            self._make_lv_pill("latest", "Latest"),
            self._make_lv_pill("other",  "Other"),
        ])
        self._lv_section = ft.Column([self._lv_pills_row, self._lv_dd],
                                     spacing=8, tight=True,
                                     visible=(self._sel_loader != "vanilla"))

        content = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=0, controls=[
            self._name_field,
            ft.Container(height=18),
            ft.Text("Loader", color=TEXT_PRI, size=12, weight=ft.FontWeight.BOLD),
            ft.Container(height=8),
            loader_row,
            ft.Container(height=18),
            ft.Text("Versión del juego", color=TEXT_PRI, size=12,
                    weight=ft.FontWeight.BOLD),
            ft.Container(height=8),
            self._mc_dd,
            ft.Container(height=18),
            self._lv_section,
            ft.Container(height=18),
            ft.Text("Memoria RAM", color=TEXT_PRI, size=12,
                    weight=ft.FontWeight.BOLD),
            ft.Container(height=8),
            self._ram_dd,
            ft.Container(height=10),
            self._prog_bar,
            self._prog_text,
        ])

        self._dlg = ft.AlertDialog(
            modal=True, bgcolor=CARD_BG,
            title=ft.Text(
                "Crear instancia" if not profile else "Editar instancia",
                color=TEXT_PRI, weight=ft.FontWeight.BOLD, size=16,
            ),
            content=ft.Container(width=460, height=530, content=content),
            actions=[
                ft.TextButton("Cancelar",
                              style=ft.ButtonStyle(color=TEXT_SEC),
                              on_click=lambda e: self.page.close(self._dlg)),
                self._save_btn,
            ],
        )

    def open(self):
        self.page.open(self._dlg)

    # ── Pills: loader ─────────────────────────────────────────────────────────
    def _make_loader_pill(self, lid: str, lname: str) -> ft.Container:
        active = (lid == self._sel_loader)
        btn = _pill(lname, active, lambda e, l=lid: self._select_loader(l))
        self._loader_btns[lid] = btn
        return btn

    def _select_loader(self, lid: str):
        self._sel_loader = lid
        for l, btn in self._loader_btns.items():
            _set_pill(btn, btn._label, l == lid)
            try: btn.update()
            except Exception: pass

        # Mostrar/ocultar sección loader version
        self._lv_section.visible = lid != "vanilla"
        try: self._lv_section.update()
        except Exception: pass

        # Reset lv pill a "stable"
        self._sel_lv_key = "stable"
        for k, b in self._lv_btns.items():
            _set_pill(b, b._label, k == "stable")
            try: b.update()
            except Exception: pass
        self._lv_dd.visible = False
        try: self._lv_dd.update()
        except Exception: pass

    # ── Pills: loader version ─────────────────────────────────────────────────
    def _make_lv_pill(self, key: str, label: str) -> ft.Container:
        active = (key == self._sel_lv_key)
        btn = _pill(label, active, lambda e, k=key: self._select_lv(k))
        self._lv_btns[key] = btn
        return btn

    def _select_lv(self, key: str):
        self._sel_lv_key = key
        for k, b in self._lv_btns.items():
            _set_pill(b, b._label, k == key)
            try: b.update()
            except Exception: pass

        if key == "other":
            self._lv_dd.visible = True
            self._load_lv_dropdown()
        else:
            self._lv_dd.visible = False
        try: self._lv_dd.update()
        except Exception: pass

    def _on_mc_change(self, e):
        self._sel_mc = e.control.value or ""
        if self._lv_dd.visible:
            self._load_lv_dropdown()

    def _load_lv_dropdown(self):
        self._lv_dd.options = [ft.dropdown.Option("Cargando…")]
        self._lv_dd.value   = None
        try: self._lv_dd.update()
        except Exception: pass

        def fetch():
            from managers.loader_manager import get_loader_versions
            versions = get_loader_versions(self._sel_loader, self._sel_mc)
            opts = [ft.dropdown.Option(v) for v in versions]

            def apply():
                self._lv_dd.options = opts
                self._lv_dd.value   = versions[0] if versions else None
                try: self._lv_dd.update()
                except Exception: pass

            self.page.run_thread(apply)

        threading.Thread(target=fetch, daemon=True).start()

    # ── Guardar ───────────────────────────────────────────────────────────────
    def _resolve_lv(self) -> str:
        if self._sel_lv_key == "other" and self._lv_dd.value:
            return self._lv_dd.value
        from managers.loader_manager import get_loader_versions
        versions = get_loader_versions(self._sel_loader, self._sel_mc)
        return versions[0] if versions else "latest"

    def _on_save(self, e):
        name    = (self._name_field.value or "").strip()
        version = self._sel_mc
        ram_str = self._ram_dd.value or "2048"

        if not name:
            self._name_field.error_text = "El nombre no puede estar vacío"
            self._name_field.update(); return
        if not version:
            self.app.snack("Selecciona una versión de Minecraft.", error=True); return

        try: ram_mb = int(ram_str)
        except ValueError: ram_mb = 2048

        loader_version = self._resolve_lv() if self._sel_loader != "vanilla" else None

        self._save_btn.disabled   = True
        self._prog_bar.visible    = True
        self._prog_text.value     = "Iniciando…"
        try:
            self._save_btn.update()
            self._prog_bar.update()
            self._prog_text.update()
        except Exception: pass

        def worker():
            try:
                from managers.loader_manager import install_loader, _save_loader_meta

                def prog(msg):
                    self._prog_text.value = msg
                    try: self._prog_text.update()
                    except Exception: pass

                if self.profile:
                    self.app.profile_manager.update_profile(
                        self.profile.id, name=name, version_id=version, ram_mb=ram_mb)
                    pobj = self.app.profile_manager.get_profile(self.profile.id)
                else:
                    pobj = self.app.profile_manager.create_profile(
                        name, version, ram_mb=ram_mb)

                if self._sel_loader != "vanilla":
                    install_loader(
                        loader=self._sel_loader,
                        mc_version=version,
                        loader_version=loader_version,
                        game_dir=pobj.game_dir,
                        libraries_dir=self.app.settings.libraries_dir,
                        versions_dir=self.app.settings.versions_dir,
                        progress_callback=prog,
                    )
                else:
                    _save_loader_meta(pobj.game_dir, {
                        "loader": "vanilla", "mc_version": version,
                        "loader_version": None, "main_class": None,
                        "extra_libs": [], "args": [],
                    })

                def finish():
                    self.page.close(self._dlg)
                    self.on_save()
                    self.app.snack("Instancia guardada correctamente.")

                self.page.run_thread(finish)

            except Exception as ex:
                log.error(f"Error guardando instancia: {ex}")
                def show_err():
                    self.app.snack(str(ex), error=True)
                    self._save_btn.disabled = False
                    self._prog_bar.visible  = False
                    self._prog_text.value   = ""
                    try:
                        self._save_btn.update()
                        self._prog_bar.update()
                        self._prog_text.update()
                    except Exception: pass
                self.page.run_thread(show_err)

        threading.Thread(target=worker, daemon=True).start()


class _OptiFineDialog:
    """
    Diálogo que guía al usuario para instalar OptiFine manualmente.
    Monitorea la carpeta mods/ y notifica cuando detecta el jar.
    """
    def __init__(self, page: ft.Page, app, profile, on_done):
        self.page    = page
        self.app     = app
        self.profile = profile
        self.on_done = on_done
        self._monitoring = False
 
        from managers.loader_manager import load_loader_meta
        meta     = load_loader_meta(profile.game_dir)
        mods_dir = meta.get("mods_dir") or os.path.join(profile.game_dir, "mods")
        mc_ver   = meta.get("mc_version", profile.version_id)
        lv       = meta.get("loader_version", "")
 
        self._mods_dir   = mods_dir
        self._status_txt = ft.Text("Esperando que descargues el jar…",
                                   color=TEXT_DIM, size=10)
 
        self._dlg = ft.AlertDialog(
            modal=True, bgcolor=CARD_BG,
            title=ft.Text("Instalar OptiFine", color=TEXT_PRI,
                          weight=ft.FontWeight.BOLD),
            content=ft.Container(width=440, content=ft.Column(
                spacing=0, tight=True,
                controls=[
                    ft.Text(f"OptiFine {lv}  •  Minecraft {mc_ver}",
                            color=TEXT_DIM, size=10),
                    ft.Container(height=16),
                    ft.Container(
                        bgcolor=CARD2_BG, border_radius=8,
                        padding=ft.padding.all(14),
                        content=ft.Column(spacing=6, controls=[
                            ft.Text("Pasos para instalar OptiFine:",
                                    color=TEXT_PRI, size=11,
                                    weight=ft.FontWeight.BOLD),
                            ft.Text("1. Haz clic en 'Abrir optifine.net'",
                                    color=TEXT_SEC, size=10),
                            ft.Text("2. Descarga la versión para Minecraft " + mc_ver,
                                    color=TEXT_SEC, size=10),
                            ft.Text("3. Copia el archivo .jar a esta carpeta:",
                                    color=TEXT_SEC, size=10),
                            ft.Container(
                                bgcolor=INPUT_BG, border_radius=6,
                                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                                content=ft.Text(mods_dir, color=GREEN,
                                                size=9, selectable=True),
                            ),
                            ft.Text("4. El launcher lo detectará automáticamente ✓",
                                    color=TEXT_SEC, size=10),
                        ]),
                    ),
                    ft.Container(height=14),
                    self._status_txt,
                ],
            )),
            actions=[
                ft.TextButton("Cerrar", style=ft.ButtonStyle(color=TEXT_SEC),
                              on_click=self._on_close),
                ft.ElevatedButton(
                    "📂 Abrir carpeta mods",
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        bgcolor=CARD2_BG, color=TEXT_PRI),
                    on_click=self._open_folder,
                ),
                ft.ElevatedButton(
                    "🌐 Abrir optifine.net",
                    bgcolor=GREEN, color=TEXT_INV,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=self._open_web,
                ),
            ],
        )
 
    def open(self):
        self.page.open(self._dlg)
        self._start_monitor()
 
    def _open_web(self, e):
        import webbrowser
        webbrowser.open("https://optifine.net/downloads")
 
    def _open_folder(self, e):
        import subprocess
        os.makedirs(self._mods_dir, exist_ok=True)
        subprocess.Popen(["explorer", self._mods_dir])
 
    def _on_close(self, e):
        self._monitoring = False
        self.page.close(self._dlg)
 
    def _start_monitor(self):
        import threading
        self._monitoring = True
 
        def watch():
            import time
            seen = set(os.listdir(self._mods_dir)) if os.path.isdir(self._mods_dir) else set()
            while self._monitoring:
                time.sleep(2)
                if not os.path.isdir(self._mods_dir):
                    continue
                current = set(os.listdir(self._mods_dir))
                new = current - seen
                for f in new:
                    if "optifine" in f.lower() and f.endswith(".jar"):
                        self._monitoring = False
                        def notify():
                            self._status_txt.value = f"✓ OptiFine detectado: {f}"
                            self._status_txt.color = GREEN
                            try: self._status_txt.update()
                            except Exception: pass
                            self.app.snack(f"✓ OptiFine instalado: {f}")
                            self.on_done()
                        self.page.run_thread(notify)
                        return
                seen = current
 
        threading.Thread(target=watch, daemon=True).start()
# ═══════════════════════════════════════════════════════════════════════════════
# Diálogo lanzar
# ═══════════════════════════════════════════════════════════════════════════════
class _LaunchDialog:
    def __init__(self, page: ft.Page, app, profile):
        self.page    = page
        self.app     = app
        self.profile = profile

        from managers.loader_manager import load_loader_meta
        meta   = load_loader_meta(profile.game_dir)
        loader = meta.get("loader", "vanilla") if isinstance(meta, dict) else "vanilla"
        icon   = LOADER_ICONS.get(loader, "🎮")

        self._user_field = ft.TextField(
            label="Nombre de usuario", bgcolor=INPUT_BG, color=TEXT_PRI,
            label_style=ft.TextStyle(color=TEXT_DIM),
            border_color=BORDER, focused_border_color=GREEN, border_radius=8,
            value=app.settings.last_profile or "Player",
        )
        self._dlg = ft.AlertDialog(
            modal=True, bgcolor=CARD_BG,
            title=ft.Text(f"Lanzar  {profile.name}",
                          color=TEXT_PRI, weight=ft.FontWeight.BOLD),
            content=ft.Container(width=320, content=ft.Column(spacing=0, tight=True, controls=[
                ft.Text(f"{icon} {loader.capitalize()}  •  Minecraft {profile.version_id}"
                        f"  •  {profile.ram_mb} MB RAM", color=TEXT_DIM, size=10),
                ft.Container(height=12),
                self._user_field,
            ])),
            actions=[
                ft.TextButton("Cancelar", style=ft.ButtonStyle(color=TEXT_SEC),
                              on_click=lambda e: self.page.close(self._dlg)),
                ft.ElevatedButton("▶ Jugar", bgcolor=GREEN, color=TEXT_INV,
                                  style=ft.ButtonStyle(
                                      shape=ft.RoundedRectangleBorder(radius=8)),
                                  on_click=self._on_launch),
            ],
        )

    def open(self):
        self.page.open(self._dlg)

    def _on_launch(self, e):
        username = (self._user_field.value or "").strip()
        if not username:
            self._user_field.error_text = "Ingresa tu nombre"
            self._user_field.update(); return

        try:
            session      = self.app.auth_service.create_offline_session(username)
            version_data = self.app.version_manager.get_version_data(
                self.profile.version_id)
        except Exception as ex:
            self.app.snack(str(ex), error=True); return

        self.page.close(self._dlg)

        def run():
            try:
                process = self.app.launcher_engine.launch(
                    self.profile, session, version_data,
                    on_output=lambda line: log.info(f"[MC] {line}"))
                self.app.settings.last_profile = self.profile.name
                log.info(f"Minecraft PID={process.pid}")
                process.wait()
                rc = process.returncode
                log.info(f"Minecraft cerrado código={rc}")
                if rc != 0:
                    self.app.snack(
                        f"Minecraft cerró con error (código {rc}). Revisa logs.",
                        error=True)
            except Exception as ex:
                log.error(f"Launch error: {ex}")
                self.app.snack(str(ex), error=True)

        threading.Thread(target=run, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers de pills (fuera de clase para no duplicar código)
# ═══════════════════════════════════════════════════════════════════════════════
def _pill(label: str, active: bool, on_click) -> ft.Container:
    text_ctrl = ft.Text(
        ("✓ " if active else "") + label,
        color=GREEN if active else TEXT_SEC,
        size=10, weight=ft.FontWeight.W_500,
    )
    btn = ft.Container(
        bgcolor="#1a2e1a" if active else CARD2_BG,
        border=ft.border.all(1, GREEN if active else BORDER),
        border_radius=20,
        padding=ft.padding.symmetric(horizontal=14, vertical=7),
        content=text_ctrl,
        on_click=on_click,
    )
    btn._label     = label
    btn._text_ctrl = text_ctrl
    return btn


def _set_pill(btn: ft.Container, label: str, active: bool):
    btn.bgcolor               = "#1a2e1a" if active else CARD2_BG
    btn.border                = ft.border.all(1, GREEN if active else BORDER)
    btn._text_ctrl.value      = ("✓ " if active else "") + label
    btn._text_ctrl.color      = GREEN if active else TEXT_SEC