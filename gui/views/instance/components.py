# -*- coding: utf-8 -*-
"""
gui/views/instance/components.py
Widgets reutilizables e independientes de InstanceView:
  - _OptiFineDialog
  - _InstanceSettingsDialog
  - _FilesTab
  - _WorldsTab
  - _LogsTab
"""
import os
import json
import time
import shutil
import threading
import datetime
from typing import Optional

import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV, ACCENT_RED,
)
from gui.views.instance.helpers import (
    log,
    _read_loader, _check_optifine_installed, _sanitize_settings,
    _read_instance_setting, _write_instance_setting,
    _VALID_LOADERS, _VALID_TABS, _SHELL_META,
    _MIN_RAM_MB, _MAX_RAM_MB,
)


# =============================================================================
# OptiFine Dialog
# =============================================================================
class _OptiFineDialog:
    """
    Dos modos de instalación:
      - Installer: ejecuta el .jar oficial creando una versión standalone.
      - Mod:       copia el .jar en /mods (requiere Forge/NeoForge).

    B3: FilePicker se elimina de page.overlay al cerrar el diálogo.
    U8: Confirma antes de sobreescribir una instalación de OptiFine existente.
    """

    def __init__(self, page: ft.Page, app, profile, on_done=None) -> None:
        self.page    = page
        self.app     = app
        self.profile = profile
        self.on_done = on_done
        self._mode   = "installer"
        self._versions: list[dict] = []
        self._selected_version: Optional[dict] = None
        self._build()

    def _build(self) -> None:
        loader = _read_loader(self.profile.game_dir)

        title_row = ft.Row([
            ft.Container(
                width=40, height=40, border_radius=10,
                bgcolor="#1a2d1a",
                border=ft.border.all(1, "#2a5a2a"),
                alignment=ft.alignment.center,
                content=ft.Icon(ft.icons.SPEED_ROUNDED, size=20, color=GREEN),
            ),
            ft.Container(width=14),
            ft.Column([
                ft.Text("OptiFine", color=TEXT_PRI, size=16, weight=ft.FontWeight.BOLD),
                ft.Text(
                    f"Minecraft {self.profile.version_id}  ·  {loader.capitalize()}",
                    color=TEXT_DIM, size=10,
                ),
            ], spacing=2),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

        self._mode_installer_btn = self._mode_pill("Installer", "installer")
        self._mode_mod_btn       = self._mode_pill("Mod (Forge)", "mod")
        mode_row = ft.Row(
            [self._mode_installer_btn, ft.Container(width=8), self._mode_mod_btn],
            spacing=0,
        )

        self._mode_info = ft.Text(self._mode_description(), color=TEXT_DIM, size=10)

        self._ver_dd = ft.Dropdown(
            hint_text="Cargando versiones…",
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, height=44,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=8),
            text_style=ft.TextStyle(size=12),
            options=[],
            on_change=self._on_version_change,
        )

        self._file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self.page.overlay.append(self._file_picker)
        self.page.update()

        self._progress = ft.ProgressBar(
            value=0, color=GREEN, bgcolor=CARD2_BG,
            border_radius=4, height=6, visible=False,
        )
        self._status_lbl = ft.Text("", color=TEXT_SEC, size=10)

        self._install_btn = ft.ElevatedButton(
            "Instalar OptiFine",
            icon=ft.icons.DOWNLOAD_ROUNDED,
            bgcolor=GREEN, color=TEXT_INV,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=20, vertical=12),
            ),
            on_click=self._on_install,
            disabled=True,
        )
        local_btn = ft.OutlinedButton(
            "Instalar desde archivo…",
            icon=ft.icons.UPLOAD_FILE_ROUNDED,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                side=ft.BorderSide(1, BORDER), color=TEXT_SEC,
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
            ),
            on_click=lambda e: self._file_picker.pick_files(
                dialog_title="Seleccionar OptiFine .jar",
                allowed_extensions=["jar"],
            ),
        )

        already = _check_optifine_installed(
            self.profile.version_id,
            self.profile.game_dir,
            self.app.settings.versions_dir,
        )
        uninstall_btn = ft.TextButton(
            "Desinstalar OptiFine",
            icon=ft.icons.DELETE_OUTLINE_ROUNDED,
            style=ft.ButtonStyle(color=ACCENT_RED),
            visible=already,
            on_click=self._on_uninstall,
        )
        self._installed_badge = ft.Container(
            visible=already,
            bgcolor="#1a3d2a",
            border=ft.border.all(1, "#2a5a2a"),
            border_radius=6,
            padding=ft.padding.symmetric(horizontal=10, vertical=4),
            content=ft.Row([
                ft.Icon(ft.icons.CHECK_CIRCLE_ROUNDED, size=12, color=GREEN),
                ft.Container(width=6),
                ft.Text("OptiFine instalado", color=GREEN, size=10, weight=ft.FontWeight.W_600),
            ], spacing=0, tight=True),
        )

        loader_lower = loader.lower()
        self._forge_warning = ft.Container(
            visible=(self._mode == "mod" and loader_lower not in ("forge", "neoforge")),
            bgcolor="#2d1a00",
            border=ft.border.all(1, "#5a3a00"),
            border_radius=8,
            padding=ft.padding.all(12),
            content=ft.Row([
                ft.Icon(ft.icons.WARNING_AMBER_ROUNDED, size=16, color="#ffa94d"),
                ft.Container(width=10),
                ft.Text(
                    "El modo Mod requiere Forge o NeoForge.\n"
                    f"Esta instancia usa {loader.capitalize()}.",
                    color="#ffa94d", size=10,
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.START),
        )

        content = ft.Column([
            title_row,
            ft.Container(height=20),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            ft.Text("Modo de instalación", color=TEXT_PRI, size=12, weight=ft.FontWeight.BOLD),
            ft.Container(height=8),
            mode_row,
            ft.Container(height=8),
            self._mode_info,
            ft.Container(height=16),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            ft.Text("Versión de OptiFine", color=TEXT_PRI, size=12, weight=ft.FontWeight.BOLD),
            ft.Container(height=8),
            self._ver_dd,
            ft.Container(height=8),
            self._forge_warning,
            ft.Container(height=16),
            self._progress,
            ft.Container(height=4),
            self._status_lbl,
            ft.Container(height=16),
            ft.Row([
                self._installed_badge,
                ft.Container(expand=True),
                uninstall_btn,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=8),
            ft.Row([
                local_btn,
                ft.Container(expand=True),
                ft.TextButton(
                    "Cancelar",
                    style=ft.ButtonStyle(color=TEXT_SEC),
                    on_click=lambda e: self._close(),
                ),
                ft.Container(width=8),
                self._install_btn,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=0, scroll=ft.ScrollMode.AUTO)

        self._dlg = ft.AlertDialog(
            modal=True, bgcolor=CARD_BG,
            content_padding=ft.padding.all(28),
            title=ft.Container(),
            content=ft.Container(width=480, content=content),
            actions=[],
        )
        self.page.open(self._dlg)
        threading.Thread(target=self._load_versions, daemon=True).start()

    def _close(self) -> None:
        self.page.close(self._dlg)
        if self._file_picker in self.page.overlay:
            self.page.overlay.remove(self._file_picker)
        try:
            self.page.update()
        except Exception:
            pass

    def _mode_description(self) -> str:
        if self._mode == "installer":
            return (
                "Ejecuta el instalador oficial de OptiFine. Crea una nueva versión "
                "standalone en el launcher. Compatible con Vanilla y Forge."
            )
        return (
            "Copia OptiFine como mod en la carpeta /mods. "
            "Solo funciona con Forge o NeoForge como loader."
        )

    def _mode_pill(self, label: str, mode: str) -> ft.Container:
        active = self._mode == mode
        pill   = ft.Container(
            bgcolor=GREEN if active else INPUT_BG,
            border=ft.border.all(1, GREEN if active else BORDER),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=16, vertical=9),
            animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
            content=ft.Text(label, color=TEXT_INV if active else TEXT_SEC,
                            size=11, weight=ft.FontWeight.W_600),
        )

        def on_click(e, m=mode) -> None:
            self._mode = m
            for btn, bmode in [
                (self._mode_installer_btn, "installer"),
                (self._mode_mod_btn,       "mod"),
            ]:
                a = bmode == m
                btn.bgcolor       = GREEN if a else INPUT_BG
                btn.border        = ft.border.all(1, GREEN if a else BORDER)
                btn.content.color = TEXT_INV if a else TEXT_SEC
                try:
                    btn.update()
                except Exception:
                    pass
            self._mode_info.value = self._mode_description()
            try:
                self._mode_info.update()
            except Exception:
                pass
            loader = _read_loader(self.profile.game_dir).lower()
            self._forge_warning.visible = (
                m == "mod" and loader not in ("forge", "neoforge")
            )
            try:
                self._forge_warning.update()
            except Exception:
                pass

        pill.on_click = on_click
        return pill

    def _load_versions(self) -> None:
        try:
            from services.optifine_service import get_optifine_versions
            versions = get_optifine_versions(self.profile.version_id)
        except Exception as e:
            versions = []
            log.warning(f"OptiFine: {e}")

        def update_ui() -> None:
            self._versions = versions
            if versions:
                self._ver_dd.options  = [ft.dropdown.Option(v["name"], v["label"]) for v in versions]
                self._ver_dd.value         = versions[0]["name"]
                self._selected_version     = versions[0]
                self._install_btn.disabled = False
                self._ver_dd.hint_text     = None
            else:
                self._ver_dd.hint_text    = (
                    f"Sin versiones para MC {self.profile.version_id}. "
                    "Usa 'Instalar desde archivo'."
                )
                self._install_btn.disabled = True
            try:
                self._ver_dd.update()
                self._install_btn.update()
            except Exception:
                pass

        self.page.run_thread(update_ui)

    def _on_version_change(self, e: ft.ControlEvent) -> None:
        name = e.control.value
        self._selected_version = next(
            (v for v in self._versions if v["name"] == name), None
        )

    def _on_install(self, e: ft.ControlEvent) -> None:
        if not self._selected_version:
            return
        already = _check_optifine_installed(
            self.profile.version_id,
            self.profile.game_dir,
            self.app.settings.versions_dir,
        )
        if already:
            def confirm(ev: ft.ControlEvent) -> None:
                self.page.close(confirm_dlg)
                if ev.control.data == "yes":
                    self._start_install(self._selected_version)

            confirm_dlg = ft.AlertDialog(
                modal=True, bgcolor=CARD_BG,
                title=ft.Text("¿Reinstalar OptiFine?", color=TEXT_PRI, weight=ft.FontWeight.BOLD),
                content=ft.Text(
                    "OptiFine ya está instalado en esta instancia. "
                    "¿Deseas reemplazarlo con la versión seleccionada?",
                    color=TEXT_SEC, size=12,
                ),
                actions=[
                    ft.TextButton("Cancelar", style=ft.ButtonStyle(color=TEXT_SEC), on_click=confirm),
                    ft.ElevatedButton(
                        "Reinstalar", data="yes",
                        bgcolor=GREEN, color=TEXT_INV,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=confirm,
                    ),
                ],
            )
            self.page.open(confirm_dlg)
        else:
            self._start_install(self._selected_version)

    def _start_install(self, version_info: dict) -> None:
        self._set_busy(True, "Preparando…")
        threading.Thread(
            target=self._do_install,
            args=(version_info,),
            daemon=True,
        ).start()

    def _do_install(self, version_info: dict) -> None:
        try:
            from services.optifine_service import (
                install_optifine_standalone,
                install_optifine_as_mod,
            )
            from managers.loader_manager import save_optifine_version_id

            mods_dir = os.path.join(self.profile.game_dir, "mods")
            java     = self._get_java()

            def prog(msg: str) -> None:
                self.page.run_thread(lambda m=msg: self._set_status(m))

            if self._mode == "installer":
                version_id = install_optifine_standalone(
                    mc_version=self.profile.version_id,
                    optifine_filename=version_info["name"],
                    versions_dir=self.app.settings.versions_dir,
                    java_path=java,
                    progress_callback=prog,
                )
                save_optifine_version_id(self.profile.game_dir, version_id)
                self.page.run_thread(
                    lambda: self._on_success(f"OptiFine instalado: {version_id}")
                )
            else:
                install_optifine_as_mod(
                    optifine_filename=version_info["name"],
                    mods_dir=mods_dir,
                    versions_dir=self.app.settings.versions_dir,
                    progress_callback=prog,
                )
                self.page.run_thread(lambda: self._on_success("OptiFine copiado a /mods"))
        except Exception as ex:
            self.page.run_thread(lambda e=ex: self._on_error(str(e)))

    def _on_file_picked(self, e: ft.FilePickerResultEvent) -> None:
        if not e.files:
            return
        jar_path = e.files[0].path
        self._set_busy(True, "Instalando desde archivo…")
        threading.Thread(
            target=self._do_install_from_file, args=(jar_path,), daemon=True,
        ).start()

    def _do_install_from_file(self, jar_path: str) -> None:
        try:
            from services.optifine_service import install_optifine_from_file
            from managers.loader_manager import save_optifine_version_id

            mods_dir = os.path.join(self.profile.game_dir, "mods")
            java     = self._get_java()

            def prog(msg: str) -> None:
                self.page.run_thread(lambda m=msg: self._set_status(m))

            result = install_optifine_from_file(
                jar_path=jar_path,
                mode=self._mode,
                mods_dir=mods_dir,
                versions_dir=self.app.settings.versions_dir,
                mc_version=self.profile.version_id,
                java_path=java,
                progress_callback=prog,
            )
            if self._mode == "installer":
                save_optifine_version_id(self.profile.game_dir, result)
            self.page.run_thread(lambda: self._on_success("OptiFine instalado ✓"))
        except Exception as ex:
            self.page.run_thread(lambda e=ex: self._on_error(str(e)))

    def _on_uninstall(self, e: ft.ControlEvent) -> None:
        from managers.loader_manager import clear_optifine_version_id
        mods_dir = os.path.join(self.profile.game_dir, "mods")
        if os.path.isdir(mods_dir):
            for fn in os.listdir(mods_dir):
                if "optifine" in fn.lower():
                    try:
                        os.remove(os.path.join(mods_dir, fn))
                    except OSError:
                        pass
        clear_optifine_version_id(self.profile.game_dir)
        self._installed_badge.visible = False
        try:
            self._installed_badge.update()
        except Exception:
            pass
        self.app.snack("OptiFine desinstalado.")
        if self.on_done:
            self.on_done()

    def _get_java(self) -> Optional[str]:
        return _read_instance_setting(self.profile.game_dir, "java_path", None) or None

    def _set_busy(self, busy: bool, msg: str = "") -> None:
        self._install_btn.disabled = busy
        self._progress.visible     = busy
        self._progress.value       = None if busy else 0
        self._status_lbl.value     = msg
        try:
            self._install_btn.update()
            self._progress.update()
            self._status_lbl.update()
        except Exception:
            pass

    def _set_status(self, msg: str) -> None:
        self._status_lbl.value = msg
        try:
            self._status_lbl.update()
        except Exception:
            pass

    def _on_success(self, msg: str) -> None:
        self._set_busy(False, msg)
        self._installed_badge.visible = True
        try:
            self._installed_badge.update()
        except Exception:
            pass
        self.app.snack(msg)
        if self.on_done:
            self.on_done()

    def _on_error(self, msg: str) -> None:
        self._set_busy(False, f"Error: {msg}")
        self.app.snack(msg, error=True)


# =============================================================================
# Instance Settings Dialog
# =============================================================================
class _InstanceSettingsDialog:
    """
    Cuatro secciones: General | Installation | Java & Memory | Launch Hooks
    B1: métodos muertos eliminados.
    C5: on_change usa setters con nombre.
    S1: _write_meta sanea los valores antes de persistirlos.
    """

    _SECTIONS = [
        ("general",      ft.icons.TUNE_ROUNDED,      "General"),
        ("installation", ft.icons.EXTENSION_ROUNDED, "Installation"),
        ("java",         ft.icons.MEMORY_ROUNDED,    "Java & Memory"),
        ("hooks",        ft.icons.CODE_ROUNDED,      "Launch Hooks"),
    ]
    _LOADERS = ["Vanilla", "Fabric", "NeoForge", "Forge", "Quilt"]

    def __init__(self, page: ft.Page, app, profile, on_done=None) -> None:
        self.page    = page
        self.app     = app
        self.profile = profile
        self.on_done = on_done
        self._section = "general"

        self._name_val    = profile.name
        self._loader_val  = self._detect_loader()
        self._version_val = profile.version_id
        self._ram_val     = self._read_meta("ram_mb",     4096)
        self._java_val    = self._read_meta("java_path",  "")
        self._jvm_val     = self._read_meta("jvm_args",   "")
        self._pre_val     = self._read_meta("pre_launch", "")
        self._post_val    = self._read_meta("post_exit",  "")
        self._notes_val   = self._read_meta("notes",      "")

        self._build()

    # C5: setters con nombre
    def _set_name(self, e: ft.ControlEvent)    -> None: self._name_val    = e.control.value
    def _set_version(self, e: ft.ControlEvent) -> None: self._version_val = e.control.value
    def _set_ram(self, e: ft.ControlEvent)     -> None:
        try:    self._ram_val = int(e.control.value or 4096)
        except: self._ram_val = 4096
    def _set_java(self, e: ft.ControlEvent)    -> None: self._java_val    = e.control.value
    def _set_jvm(self, e: ft.ControlEvent)     -> None: self._jvm_val     = e.control.value
    def _set_pre(self, e: ft.ControlEvent)     -> None: self._pre_val     = e.control.value
    def _set_post(self, e: ft.ControlEvent)    -> None: self._post_val    = e.control.value
    def _set_notes(self, e: ft.ControlEvent)   -> None: self._notes_val   = e.control.value

    def _detect_loader(self) -> str:
        return _read_loader(self.profile.game_dir).capitalize()

    def _read_meta(self, key: str, default):
        return _read_instance_setting(self.profile.game_dir, key, default)

    def _write_meta(self, updates: dict) -> None:
        """Escribe configuración de instancia con saneado S1."""
        path = os.path.join(self.profile.game_dir, "instance_settings.json")
        data: dict = {}
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    data = json.load(f)
            except Exception:
                pass
        data.update(updates)
        sanitised = _sanitize_settings(data)
        for k, v in data.items():
            if k not in sanitised:
                sanitised[k] = v
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(sanitised, f, indent=2)

    def _build(self) -> None:
        self._nav_items: dict[str, ft.Container] = {}
        nav_col = ft.Column(spacing=2)
        for sid, icon, label in self._SECTIONS:
            item = self._make_nav_item(sid, icon, label)
            self._nav_items[sid] = item
            nav_col.controls.append(item)

        sidebar = ft.Container(
            width=200, bgcolor=CARD2_BG,
            border=ft.border.only(right=ft.BorderSide(1, BORDER)),
            padding=ft.padding.symmetric(horizontal=10, vertical=16),
            content=nav_col,
        )

        self._content_area = ft.Container(
            expand=True, padding=ft.padding.all(28),
            content=self._render_section(self._section),
        )

        self._save_btn = ft.ElevatedButton(
            "Save changes",
            bgcolor=GREEN, color=TEXT_INV,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.padding.symmetric(horizontal=24, vertical=12),
            ),
            on_click=self._on_save,
        )

        self._breadcrumb = ft.Text(
            "General", color=TEXT_PRI, size=15, weight=ft.FontWeight.BOLD,
        )

        header = ft.Container(
            bgcolor=CARD_BG,
            padding=ft.padding.symmetric(horizontal=24, vertical=16),
            border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
            content=ft.Row([
                ft.Text(self.profile.name, color=TEXT_DIM, size=13),
                ft.Icon(ft.icons.CHEVRON_RIGHT_ROUNDED, size=14, color=TEXT_DIM),
                self._breadcrumb,
                ft.Container(expand=True),
                ft.TextButton(
                    "Cancel",
                    style=ft.ButtonStyle(color=TEXT_SEC),
                    on_click=lambda e: self.page.close(self._dlg),
                ),
                ft.Container(width=8),
                self._save_btn,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        self._dlg = ft.AlertDialog(
            modal=True, bgcolor=CARD_BG,
            title=ft.Container(),
            content_padding=ft.padding.all(0),
            content=ft.Container(
                width=820, height=520, bgcolor=CARD_BG,
                border_radius=12,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                content=ft.Column([
                    header,
                    ft.Row([sidebar, self._content_area], spacing=0, expand=True),
                ], spacing=0, expand=True),
            ),
            actions=[],
        )
        self.page.open(self._dlg)

    def _make_nav_item(self, sid: str, icon, label: str) -> ft.Container:
        active = sid == self._section
        item   = ft.Container(
            bgcolor=GREEN if active else "transparent",
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
            on_click=lambda e, s=sid: self._switch_section(s),
            content=ft.Row([
                ft.Icon(icon, size=16, color=TEXT_INV if active else TEXT_DIM),
                ft.Container(width=10),
                ft.Text(label, size=12,
                        color=TEXT_INV if active else TEXT_SEC,
                        weight=(ft.FontWeight.W_600 if active else ft.FontWeight.NORMAL)),
            ], spacing=0, tight=True),
        )
        item.on_hover = lambda e, b=item, s=sid: (
            None if s == self._section else (
                setattr(b, "bgcolor", INPUT_BG if e.data == "true" else "transparent")
                or b.update()
            )
        )
        return item

    def _switch_section(self, sid: str) -> None:
        self._section = sid
        label_map = {s: l for s, _, l in self._SECTIONS}
        for s, icon, label in self._SECTIONS:
            item   = self._nav_items[s]
            active = s == sid
            item.bgcolor = GREEN if active else "transparent"
            row: ft.Row  = item.content
            row.controls[0].color  = TEXT_INV if active else TEXT_DIM
            row.controls[2].color  = TEXT_INV if active else TEXT_SEC
            row.controls[2].weight = (ft.FontWeight.W_600 if active else ft.FontWeight.NORMAL)
            try:
                item.update()
            except Exception:
                pass
        self._breadcrumb.value = label_map[sid]
        try:
            self._breadcrumb.update()
        except Exception:
            pass
        self._content_area.content = self._render_section(sid)
        try:
            self._content_area.update()
        except Exception:
            pass

    def _render_section(self, sid: str) -> ft.Control:
        if sid == "general":      return self._section_general()
        if sid == "installation": return self._section_installation()
        if sid == "java":         return self._section_java()
        if sid == "hooks":        return self._section_hooks()
        return ft.Container()

    def _heading(self, text: str) -> ft.Text:
        return ft.Text(text, color=TEXT_PRI, size=13, weight=ft.FontWeight.BOLD)

    def _subtext(self, text: str) -> ft.Text:
        return ft.Text(text, color=TEXT_DIM, size=10)

    def _section_general(self) -> ft.Column:
        self._name_field = ft.TextField(
            value=self._name_val,
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, height=42,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            text_size=12,
            on_change=self._set_name,
        )
        self._notes_field = ft.TextField(
            value=self._notes_val,
            hint_text="Notas sobre esta instancia (visible en el header)…",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=11),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, min_lines=2, max_lines=3,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            text_size=12,
            on_change=self._set_notes,
        )
        icon_box = ft.Container(
            width=80, height=80, border_radius=14,
            bgcolor=CARD2_BG, alignment=ft.alignment.center,
            border=ft.border.all(1, BORDER),
            content=ft.Icon(ft.icons.WIDGETS_ROUNDED, size=36, color=TEXT_DIM),
        )

        def on_duplicate(e):
            self.page.close(self._dlg)
            self._duplicate_instance()

        def on_delete(e):
            self.page.close(self._dlg)
            self._confirm_delete()

        return ft.Column([
            ft.Row([
                ft.Column([
                    self._heading("Instance name"),
                    ft.Container(height=6),
                    self._name_field,
                ], spacing=0, expand=True),
                ft.Container(width=20),
                icon_box,
            ], vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Container(height=16),
            self._heading("Notes"),
            ft.Container(height=4),
            self._subtext("Descripción corta visible en el header de la instancia."),
            ft.Container(height=10),
            self._notes_field,
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            self._heading("Duplicate instance"),
            ft.Container(height=4),
            self._subtext("Creates a copy of this instance, including worlds, configs, mods, etc."),
            ft.Container(height=10),
            ft.OutlinedButton(
                "Duplicate",
                icon=ft.icons.COPY_ALL_ROUNDED,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    side=ft.BorderSide(1, BORDER), color=TEXT_SEC,
                    padding=ft.padding.symmetric(horizontal=16, vertical=10),
                ),
                on_click=on_duplicate,
            ),
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            self._heading("Delete instance"),
            ft.Container(height=4),
            self._subtext(
                "Permanently deletes this instance from your device, including worlds, "
                "configs,\nand all installed content. This action cannot be undone."
            ),
            ft.Container(height=10),
            ft.ElevatedButton(
                "Delete instance",
                icon=ft.icons.DELETE_FOREVER_ROUNDED,
                bgcolor=ACCENT_RED, color="#ffffff",
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.padding.symmetric(horizontal=16, vertical=10),
                ),
                on_click=on_delete,
            ),
        ], spacing=0, scroll=ft.ScrollMode.AUTO)

    def _section_installation(self) -> ft.Column:
        self._loader_btns: dict[str, ft.Container] = {}
        loader_row = ft.Row(spacing=8, wrap=True)
        for ld in self._LOADERS:
            btn = self._loader_pill(ld)
            self._loader_btns[ld] = btn
            loader_row.controls.append(btn)

        versions = [self.profile.version_id]
        try:
            all_v    = self.app.version_manager.get_available_versions()
            versions = [v.id if hasattr(v, "id") else str(v) for v in all_v] or versions
        except Exception:
            pass

        self._version_dd = ft.Dropdown(
            value=self._version_val,
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, height=42,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=8),
            text_style=ft.TextStyle(size=12),
            options=[ft.dropdown.Option(v) for v in versions],
            on_change=self._set_version,
        )

        optifine_installed = _check_optifine_installed(
            self.profile.version_id, self.profile.game_dir, self.app.settings.versions_dir,
        )
        optifine_status = ft.Container(
            bgcolor="#1a3d2a" if optifine_installed else CARD2_BG,
            border=ft.border.all(1, "#2a5a2a" if optifine_installed else BORDER),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
            content=ft.Row([
                ft.Icon(ft.icons.SPEED_ROUNDED, size=16,
                        color=GREEN if optifine_installed else TEXT_DIM),
                ft.Container(width=10),
                ft.Column([
                    ft.Text("OptiFine",
                            color=GREEN if optifine_installed else TEXT_PRI,
                            size=11, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "Instalado ✓" if optifine_installed else "No instalado",
                        color=GREEN if optifine_installed else TEXT_DIM, size=9,
                    ),
                ], spacing=1, expand=True),
                ft.OutlinedButton(
                    "Gestionar",
                    icon=ft.icons.SETTINGS_ROUNDED,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=6),
                        side=ft.BorderSide(1, GREEN if optifine_installed else BORDER),
                        color=GREEN if optifine_installed else TEXT_SEC,
                        padding=ft.padding.symmetric(horizontal=12, vertical=6),
                    ),
                    on_click=lambda e: (
                        self.page.close(self._dlg),
                        _OptiFineDialog(self.page, self.app, self.profile, on_done=self.on_done),
                    ),
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        return ft.Column([
            self._heading("Mod loader"),
            ft.Container(height=4),
            self._subtext("Select the loader for this instance."),
            ft.Container(height=12),
            loader_row,
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            self._heading("Game version"),
            ft.Container(height=4),
            self._subtext("Minecraft version used by this instance."),
            ft.Container(height=12),
            self._version_dd,
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            self._heading("OptiFine"),
            ft.Container(height=4),
            self._subtext("Optimización de gráficos y shaders. Compatible con Vanilla y Forge."),
            ft.Container(height=12),
            optifine_status,
        ], spacing=0, scroll=ft.ScrollMode.AUTO)

    def _loader_pill(self, label: str) -> ft.Container:
        active = label.lower() == self._loader_val.lower()
        pill   = ft.Container(
            bgcolor=GREEN if active else INPUT_BG,
            border=ft.border.all(1, GREEN if active else BORDER),
            border_radius=20,
            padding=ft.padding.symmetric(horizontal=18, vertical=9),
            animate=ft.animation.Animation(120, ft.AnimationCurve.EASE_OUT),
            content=ft.Text(label, color=TEXT_INV if active else TEXT_SEC,
                            size=11, weight=ft.FontWeight.W_600),
        )

        def on_click(e: ft.ControlEvent, lbl: str = label) -> None:
            self._loader_val = lbl
            for l2, b in self._loader_btns.items():
                a = l2.lower() == lbl.lower()
                b.bgcolor       = GREEN if a else INPUT_BG
                b.border        = ft.border.all(1, GREEN if a else BORDER)
                b.content.color = TEXT_INV if a else TEXT_SEC
                try:
                    b.update()
                except Exception:
                    pass

        pill.on_click = on_click
        pill.on_hover = lambda e, p=pill, lbl=label: (
            None if lbl.lower() == self._loader_val.lower() else (
                setattr(p, "bgcolor", CARD2_BG if e.data == "true" else INPUT_BG)
                or p.update()
            )
        )
        return pill

    def _section_java(self) -> ft.Column:
        ram_opts = [512, 1024, 2048, 3072, 4096, 6144, 8192, 12288, 16384]
        self._ram_dd = ft.Dropdown(
            value=str(self._ram_val),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, height=42,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=8),
            text_style=ft.TextStyle(size=12),
            options=[
                ft.dropdown.Option(
                    str(r),
                    f"{r} MB  ({r // 1024} GB)" if r >= 1024 else f"{r} MB",
                )
                for r in ram_opts
            ],
            on_change=self._set_ram,
        )

        self._java_field = ft.TextField(
            value=self._java_val,
            hint_text="Leave empty to use system default",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=11),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, height=42, expand=True,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            text_size=12,
            on_change=self._set_java,
        )

        def browse_java(e: ft.ControlEvent) -> None:
            fp = ft.FilePicker(on_result=self._on_java_picked)
            self.page.overlay.append(fp)
            self.page.update()
            fp.pick_files(dialog_title="Select Java executable", allowed_extensions=["exe", ""])

        self._jvm_field = ft.TextField(
            value=self._jvm_val,
            hint_text="e.g.  -XX:+UseG1GC -XX:MaxGCPauseMillis=50",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=11),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, min_lines=2, max_lines=4,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            text_size=12,
            on_change=self._set_jvm,
        )

        return ft.Column([
            self._heading("Memory (RAM)"),
            ft.Container(height=4),
            self._subtext("Amount of RAM allocated to this Minecraft instance."),
            ft.Container(height=12),
            self._ram_dd,
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            self._heading("Java executable"),
            ft.Container(height=4),
            self._subtext("Path to the java binary. Leave empty to use the system default."),
            ft.Container(height=12),
            ft.Row([
                self._java_field,
                ft.Container(width=8),
                ft.OutlinedButton(
                    "Browse",
                    icon=ft.icons.FOLDER_OPEN_ROUNDED,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        side=ft.BorderSide(1, BORDER), color=TEXT_SEC,
                        padding=ft.padding.symmetric(horizontal=14, vertical=10),
                    ),
                    on_click=browse_java,
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            self._heading("JVM arguments"),
            ft.Container(height=4),
            self._subtext("Additional arguments passed to the JVM. Advanced users only."),
            ft.Container(height=12),
            self._jvm_field,
        ], spacing=0, scroll=ft.ScrollMode.AUTO)

    def _on_java_picked(self, r: ft.FilePickerResultEvent) -> None:
        if r.files:
            self._java_val         = r.files[0].path
            self._java_field.value = self._java_val
            try:
                self._java_field.update()
            except Exception:
                pass

    def _section_hooks(self) -> ft.Column:
        self._pre_field = ft.TextField(
            value=self._pre_val,
            hint_text="Command to run before launching Minecraft",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=11),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, min_lines=2, max_lines=4,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            text_size=12,
            on_change=self._set_pre,
        )
        self._post_field = ft.TextField(
            value=self._post_val,
            hint_text="Command to run after Minecraft exits",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=11),
            color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8, min_lines=2, max_lines=4,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
            text_size=12,
            on_change=self._set_post,
        )
        return ft.Column([
            self._heading("Pre-launch command"),
            ft.Container(height=4),
            self._subtext(
                "Runs before Minecraft starts. Use $INSTANCE_DIR for the instance path.\n"
                "Example:  echo 'Starting' >> $INSTANCE_DIR/launch.log"
            ),
            ft.Container(height=12),
            self._pre_field,
            ft.Container(height=24),
            ft.Divider(height=1, color=BORDER),
            ft.Container(height=16),
            self._heading("Post-exit command"),
            ft.Container(height=4),
            self._subtext(
                "Runs after Minecraft exits. $EXIT_CODE contains the process exit code.\n"
                "Example:  notify-send 'Minecraft closed with code $EXIT_CODE'"
            ),
            ft.Container(height=12),
            self._post_field,
            ft.Container(height=24),
            ft.Container(
                bgcolor="#1a2a1a",
                border=ft.border.all(1, "#2a4a2a"),
                border_radius=8,
                padding=ft.padding.all(14),
                content=ft.Row([
                    ft.Icon(ft.icons.INFO_OUTLINE_ROUNDED, size=16, color=GREEN),
                    ft.Container(width=10),
                    ft.Text(
                        "Commands run in a shell (bash on Linux/macOS, cmd on Windows).\n"
                        "The instance directory is passed as $INSTANCE_DIR.",
                        color=TEXT_SEC, size=10,
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.START),
            ),
        ], spacing=0, scroll=ft.ScrollMode.AUTO)

    def _on_save(self, e: ft.ControlEvent) -> None:
        self._save_btn.disabled = True
        self._save_btn.text     = "Saving…"
        try:
            self._save_btn.update()
        except Exception:
            pass
        try:
            if self._name_val.strip() and self._name_val != self.profile.name:
                self.app.profile_manager.rename_profile(self.profile.id, self._name_val.strip())
            if self._version_val != self.profile.version_id:
                self.app.profile_manager.update_profile_version(self.profile.id, self._version_val)
            self._write_meta({
                "ram_mb":     self._ram_val,
                "java_path":  self._java_val.strip(),
                "jvm_args":   self._jvm_val.strip(),
                "pre_launch": self._pre_val.strip(),
                "post_exit":  self._post_val.strip(),
                "loader":     self._loader_val.lower(),
                "notes":      self._notes_val.strip(),
            })
            self.page.close(self._dlg)
            self.app.snack("Instance settings saved.")
            if self.on_done:
                self.on_done()
        except Exception as ex:
            self._save_btn.disabled = False
            self._save_btn.text     = "Save changes"
            try:
                self._save_btn.update()
            except Exception:
                pass
            self.app.snack(str(ex), error=True)

    def _duplicate_instance(self) -> None:
        def do_dup() -> None:
            try:
                new_name = f"{self.profile.name} (copy)"
                new_dir  = f"{self.profile.game_dir}_copy_{int(time.time())}"
                shutil.copytree(self.profile.game_dir, new_dir)
                self.app.profile_manager.create_profile(
                    name=new_name,
                    version_id=self.profile.version_id,
                    game_dir=new_dir,
                )
                self.page.run_thread(lambda: self.app.snack(f"'{new_name}' created."))
                if self.on_done:
                    self.page.run_thread(self.on_done)
            except Exception as ex:
                self.page.run_thread(lambda: self.app.snack(str(ex), error=True))

        threading.Thread(target=do_dup, daemon=True).start()
        self.app.snack("Duplicating instance…")

    def _confirm_delete(self) -> None:
        def on_action(e: ft.ControlEvent) -> None:
            self.page.close(confirm_dlg)
            if e.control.data == "delete":
                self._do_delete()

        confirm_dlg = ft.AlertDialog(
            modal=True, bgcolor=CARD_BG,
            title=ft.Text("Delete instance?", color=TEXT_PRI, weight=ft.FontWeight.BOLD),
            content=ft.Text(
                f"This will permanently delete '{self.profile.name}' and all its "
                f"worlds, configs and mods.\nThis cannot be undone.",
                color=TEXT_SEC, size=12,
            ),
            actions=[
                ft.TextButton("Cancel", style=ft.ButtonStyle(color=TEXT_SEC), on_click=on_action),
                ft.ElevatedButton(
                    "Delete forever", data="delete",
                    bgcolor=ACCENT_RED, color="#ffffff",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=on_action,
                ),
            ],
        )
        self.page.open(confirm_dlg)

    def _do_delete(self) -> None:
        def do() -> None:
            try:
                self.app.profile_manager.delete_profile(self.profile.id)
                shutil.rmtree(self.profile.game_dir, ignore_errors=True)
                self.page.run_thread(lambda: (
                    self.app.snack("Instance deleted."),
                    self.app._show_view("library"),
                ))
            except Exception as ex:
                self.page.run_thread(lambda: self.app.snack(str(ex), error=True))

        threading.Thread(target=do, daemon=True).start()


# =============================================================================
# Tab: Files
# =============================================================================
class _FilesTab:
    def __init__(self, page: ft.Page, app, profile) -> None:
        self.page    = page
        self.app     = app
        self.profile = profile
        self._build()

    def _build(self) -> None:
        game_dir = self.profile.game_dir
        folders  = [
            ("Mods",           os.path.join(game_dir, "mods")),
            ("Resource Packs", os.path.join(game_dir, "resourcepacks")),
            ("Shader Packs",   os.path.join(game_dir, "shaderpacks")),
            ("Saves / Worlds", os.path.join(game_dir, "saves")),
            ("Config",         os.path.join(game_dir, "config")),
            ("Screenshots",    os.path.join(game_dir, "screenshots")),
        ]

        def folder_row(name: str, path: str) -> ft.Container:
            exists = os.path.isdir(path)
            size   = self._folder_size(path) if exists else 0
            return ft.Container(
                bgcolor=INPUT_BG, border_radius=8,
                padding=ft.padding.symmetric(horizontal=16, vertical=12),
                content=ft.Row([
                    ft.Icon(ft.icons.FOLDER_ROUNDED, color=GREEN if exists else TEXT_DIM, size=20),
                    ft.Container(width=14),
                    ft.Column([
                        ft.Text(name, color=TEXT_PRI, size=10, weight=ft.FontWeight.BOLD),
                        ft.Text(path, color=TEXT_DIM, size=8, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=2, expand=True),
                    ft.Text(f"{size:.1f} MB" if exists else "Vacía", color=TEXT_SEC, size=9),
                    ft.Container(width=12),
                    ft.OutlinedButton(
                        "Abrir",
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=6),
                            side=ft.BorderSide(1, BORDER), color=TEXT_SEC,
                            padding=ft.padding.symmetric(horizontal=12, vertical=6),
                        ),
                        on_click=lambda e, p=path: self._open_folder(p),
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            )

        self.root = ft.Container(
            expand=True, padding=ft.padding.all(28),
            content=ft.Column([
                ft.Text("Archivos", color=TEXT_PRI, size=16, weight=ft.FontWeight.BOLD),
                ft.Text("Carpetas de la instancia", color=TEXT_DIM, size=9),
                ft.Container(height=16),
                ft.Column([folder_row(n, p) for n, p in folders],
                          spacing=8, scroll=ft.ScrollMode.AUTO, expand=True),
            ], spacing=0, expand=True),
        )

    @staticmethod
    def _folder_size(path: str) -> float:
        total = 0
        for dp, _, files in os.walk(path):
            for fn in files:
                try:
                    total += os.path.getsize(os.path.join(dp, fn))
                except OSError:
                    pass
        return total / 1_048_576

    @staticmethod
    def _open_folder(path: str) -> None:
        import subprocess, sys
        os.makedirs(path, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])


# =============================================================================
# Tab: Worlds  (U12: fecha + tamaño por mundo)
# =============================================================================
class _WorldsTab:
    def __init__(self, page: ft.Page, app, profile) -> None:
        self.page    = page
        self.app     = app
        self.profile = profile
        self._build()

    def _build(self) -> None:
        saves_dir = os.path.join(self.profile.game_dir, "saves")
        worlds: list[str] = []
        if os.path.isdir(saves_dir):
            worlds = sorted(
                d for d in os.listdir(saves_dir)
                if os.path.isdir(os.path.join(saves_dir, d))
            )

        if worlds:
            rows    = [self._world_row(saves_dir, w) for w in worlds]
            content: ft.Control = ft.Column(rows, spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
        else:
            content = ft.Container(
                expand=True, alignment=ft.alignment.center,
                content=ft.Column([
                    ft.Text("Sin mundos guardados", color=TEXT_SEC, size=14,
                            text_align=ft.TextAlign.CENTER, weight=ft.FontWeight.BOLD),
                    ft.Text("Los mundos aparecerán aquí después de jugar.",
                            color=TEXT_DIM, size=10, text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            )

        self.root = ft.Container(
            expand=True, padding=ft.padding.all(28),
            content=ft.Column([
                ft.Text("Mundos", color=TEXT_PRI, size=16, weight=ft.FontWeight.BOLD),
                ft.Text(
                    f"{len(worlds)} mundo{'s' if len(worlds) != 1 else ''} "
                    f"guardado{'s' if len(worlds) != 1 else ''}",
                    color=TEXT_DIM, size=9,
                ),
                ft.Container(height=16),
                content,
            ], spacing=0, expand=True),
        )

    def _world_row(self, saves_dir: str, world_name: str) -> ft.Container:
        world_path = os.path.join(saves_dir, world_name)
        size_str   = self._folder_size_str(world_path)
        date_str   = self._folder_mdate(world_path)

        return ft.Container(
            bgcolor=INPUT_BG, border_radius=8,
            padding=ft.padding.symmetric(horizontal=16, vertical=14),
            content=ft.Row([
                ft.Container(
                    width=44, height=44, border_radius=10,
                    bgcolor=CARD2_BG, alignment=ft.alignment.center,
                    content=ft.Text("W", color=TEXT_DIM, size=20, weight=ft.FontWeight.BOLD),
                ),
                ft.Container(width=14),
                ft.Column([
                    ft.Text(world_name, color=TEXT_PRI, size=11,
                            weight=ft.FontWeight.BOLD, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row([
                        ft.Icon(ft.icons.STORAGE_ROUNDED, size=11, color=TEXT_DIM),
                        ft.Container(width=4),
                        ft.Text(size_str, color=TEXT_DIM, size=10),
                        ft.Container(width=12),
                        ft.Icon(ft.icons.SCHEDULE_ROUNDED, size=11, color=TEXT_DIM),
                        ft.Container(width=4),
                        ft.Text(date_str, color=TEXT_DIM, size=10),
                    ], spacing=0),
                ], spacing=4, expand=True),
                ft.IconButton(
                    icon=ft.icons.FOLDER_OPEN_ROUNDED,
                    icon_color=TEXT_DIM, icon_size=18,
                    tooltip="Open world folder",
                    on_click=lambda e, p=world_path: self._open_folder(p),
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    @staticmethod
    def _folder_size_str(path: str) -> str:
        total = 0
        for dp, _, files in os.walk(path):
            for fn in files:
                try:
                    total += os.path.getsize(os.path.join(dp, fn))
                except OSError:
                    pass
        if total < 1024:          return f"{total} B"
        if total < 1_048_576:     return f"{total / 1024:.0f} KB"
        if total < 1_073_741_824: return f"{total / 1_048_576:.1f} MB"
        return f"{total / 1_073_741_824:.2f} GB"

    @staticmethod
    def _folder_mdate(path: str) -> str:
        try:
            ts = os.path.getmtime(path)
            return datetime.datetime.fromtimestamp(ts).strftime("%d %b %Y")
        except Exception:
            return "—"

    @staticmethod
    def _open_folder(path: str) -> None:
        import subprocess, sys
        os.makedirs(path, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])


# =============================================================================
# Tab: Logs  (U13: tail en tiempo real de logs/latest.log)
# =============================================================================
class _LogsTab:
    """
    Hace poll de logs/latest.log cada segundo y anexa el nuevo contenido.
    Mantiene las últimas LOG_LINES líneas en la vista.
    """

    LOG_LINES = 300
    POLL_SEC  = 1.0

    def __init__(self, page: ft.Page, app, profile) -> None:
        self.page         = page
        self.app          = app
        self.profile      = profile
        self._alive       = True
        self._last_mtime  = 0.0
        self._build()
        threading.Thread(target=self._tail_loop, daemon=True).start()

    def _build(self) -> None:
        log_path = os.path.join(self.profile.game_dir, "logs", "latest.log")

        self._log_text = ft.Text(
            "Los logs aparecerán aquí durante la ejecución del juego.",
            color=TEXT_DIM, size=10, selectable=True, font_family="Courier New",
        )
        self._log_col = ft.Column([self._log_text], scroll=ft.ScrollMode.ALWAYS, expand=True)
        self._path_lbl = ft.Text(log_path, color=TEXT_DIM, size=8, overflow=ft.TextOverflow.ELLIPSIS)
        self._status_dot = ft.Container(width=8, height=8, border_radius=4, bgcolor=TEXT_DIM)

        self.root = ft.Container(
            expand=True, padding=ft.padding.all(28),
            content=ft.Column([
                ft.Row([
                    ft.Column([
                        ft.Text("Logs", color=TEXT_PRI, size=16, weight=ft.FontWeight.BOLD),
                        self._path_lbl,
                    ], spacing=2, expand=True),
                    self._status_dot,
                    ft.Container(width=6),
                    ft.TextButton(
                        "Clear",
                        icon=ft.icons.DELETE_OUTLINE_ROUNDED,
                        style=ft.ButtonStyle(color=TEXT_DIM),
                        on_click=self._clear_log,
                    ),
                    ft.TextButton(
                        "Open",
                        icon=ft.icons.OPEN_IN_NEW_ROUNDED,
                        style=ft.ButtonStyle(color=TEXT_DIM),
                        on_click=self._open_log,
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=12),
                ft.Container(
                    expand=True, bgcolor=INPUT_BG, border_radius=8,
                    padding=ft.padding.all(14),
                    content=self._log_col,
                ),
            ], spacing=0, expand=True),
        )

    def _tail_loop(self) -> None:
        import time as _time
        log_path = os.path.join(self.profile.game_dir, "logs", "latest.log")
        while self._alive:
            try:
                if os.path.isfile(log_path):
                    mtime = os.path.getmtime(log_path)
                    if mtime != self._last_mtime:
                        self._last_mtime = mtime
                        with open(log_path, "r", errors="replace") as f:
                            lines = f.readlines()[-self.LOG_LINES:]
                        content = "".join(lines)

                        def _update(c: str = content) -> None:
                            self._log_text.value     = c
                            self._status_dot.bgcolor = GREEN
                            try:
                                self._log_text.update()
                                self._status_dot.update()
                            except Exception:
                                pass

                        self.page.run_thread(_update)
            except Exception:
                pass
            _time.sleep(self.POLL_SEC)

    def on_show(self) -> None:
        self._alive = True

    def destroy(self) -> None:
        self._alive = False

    def _clear_log(self, e: ft.ControlEvent) -> None:
        self._log_text.value = ""
        self._last_mtime     = 0.0
        try:
            self._log_text.update()
        except Exception:
            pass

    def _open_log(self, e: ft.ControlEvent) -> None:
        import subprocess, sys
        log_path = os.path.join(self.profile.game_dir, "logs", "latest.log")
        if not os.path.isfile(log_path):
            self.app.snack("No log file found.", error=True)
            return
        if sys.platform == "win32":
            os.startfile(log_path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", log_path])
        else:
            subprocess.Popen(["xdg-open", log_path])
