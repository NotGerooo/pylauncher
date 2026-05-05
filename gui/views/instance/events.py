# -*- coding: utf-8 -*-
"""
gui/views/instance/events.py
Handlers de eventos y lógica de negocio de InstanceView.
Todas reciben `self` como primer argumento para poder ser inyectadas
como métodos de la clase vía asignación directa en __init__.py.
"""
import time
import threading
from typing import Optional

import flet as ft

from gui.theme import GREEN
from gui.views.instance.helpers import (
    log,
    _read_instance_setting, _write_instance_setting,
    _VALID_TABS,
)


# ---------------------------------------------------------------------------
# on_show
# ---------------------------------------------------------------------------
def on_show(self) -> None:
    self._render_tab()


# ---------------------------------------------------------------------------
# _set_play_status — actualiza el botón Play en vivo
# ---------------------------------------------------------------------------
def _set_play_status(self, text: str, *, disabled: bool = True) -> None:
    self._play_btn.text     = text
    self._play_btn.disabled = disabled
    try:
        self._play_btn.update()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# _on_play — lógica de lanzamiento de Minecraft
# ---------------------------------------------------------------------------
def _on_play(self, e: ft.ControlEvent) -> None:
    try:
        acc = self.app.account_manager.get_active_account()
        if not acc:
            all_acc = self.app.account_manager.get_all_accounts()
            acc = all_acc[0] if all_acc else None
    except Exception:
        acc = None

    if not acc:
        self.app.snack("No hay cuenta seleccionada.", error=True)
        return

    username = acc.username
    self._set_play_status("Preparando…")

    try:
        session      = self.app.auth_service.create_offline_session(username)
        version_data = self.app.version_manager.get_version_data(self.profile.version_id)
    except Exception as ex:
        msg = str(ex)
        log.error(f"Launch error: {msg}")
        self._set_play_status("Play", disabled=False)
        self.app.snack(msg, error=True)
        return

    def run() -> None:
        try:
            self.page.run_thread(lambda: self._set_play_status("Lanzando…"))
            process = self.app.launcher_engine.launch(
                self.profile, session, version_data,
                on_output=lambda line: log.info(f"[MC] {line}"),
            )
            self._persist_last_played()
            self.app.settings.last_profile = self.profile.name
            self.app.profile_manager.mark_as_used(self.profile.id)

            self.page.run_thread(lambda: self._set_play_status("Jugando…"))
            process.wait()
            rc = process.returncode

            def done() -> None:
                self._set_play_status("Play", disabled=False)
                if rc != 0:
                    self.app.snack(f"Minecraft cerró con error (código {rc}).", error=True)

            self.page.run_thread(done)

        except Exception as ex:
            msg = str(ex)
            log.error(f"Launch error: {msg}")

            def err(_m: str = msg) -> None:
                self._set_play_status("Play", disabled=False)
                self.app.snack(_m, error=True)

            self.page.run_thread(err)

    threading.Thread(target=run, daemon=True).start()
    self.app.snack(f"Iniciando Minecraft {self.profile.version_id} como {username}…")


# ---------------------------------------------------------------------------
# _persist_last_played — guarda el timestamp actual en instance_settings.json
# ---------------------------------------------------------------------------
def _persist_last_played(self) -> None:
    try:
        _write_instance_setting(self.profile.game_dir, "last_played", time.time())
    except Exception:
        pass


# ---------------------------------------------------------------------------
# _switch_tab — cambia entre pestañas con fade de opacidad
# ---------------------------------------------------------------------------
def _switch_tab(self, tid: str) -> None:
    self._active_tab = tid
    _write_instance_setting(self.profile.game_dir, "active_tab", tid)  # S3

    # U3: fade out
    self._tab_area.opacity = 0
    try:
        self._tab_area.update()
    except Exception:
        pass

    tabs_data = [
        ("content", "Content", ft.icons.EXTENSION_ROUNDED),
        ("files",   "Files",   ft.icons.FOLDER_ROUNDED),
        ("worlds",  "Worlds",  ft.icons.PUBLIC_ROUNDED),
        ("logs",    "Logs",    ft.icons.TERMINAL_ROUNDED),
    ]
    for (t, label, icon), btn in zip(tabs_data, self._tab_btns.values()):
        active      = t == tid
        btn.bgcolor = GREEN if active else "transparent"
        row: ft.Row = btn.content
        row.controls[0].color = "white" if active else "#9ca3af"
        row.controls[2].color = "white" if active else "#9ca3af"
        try:
            btn.update()
        except Exception:
            pass

    self._render_tab()

    # U3: fade in
    self._tab_area.opacity = 1
    try:
        self._tab_area.update()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# _render_tab — monta el contenido de la pestaña activa
# ---------------------------------------------------------------------------
def _render_tab(self) -> None:
    from gui.views.content_tab import _ContentTab
    from gui.views.instance.components import _FilesTab, _WorldsTab, _LogsTab

    if self._active_tab == "content":
        if not hasattr(self, "_content_tab_obj"):
            self._content_tab_obj = _ContentTab(self.page, self.app, self.profile)
        self._tab_area.content = self._content_tab_obj.root

    elif self._active_tab == "files":
        if not hasattr(self, "_files_tab_obj"):
            self._files_tab_obj = _FilesTab(self.page, self.app, self.profile)
        self._tab_area.content = self._files_tab_obj.root

    elif self._active_tab == "worlds":
        # Siempre reconstruir para mostrar mundos recién creados
        self._worlds_tab_obj   = _WorldsTab(self.page, self.app, self.profile)
        self._tab_area.content = self._worlds_tab_obj.root

    elif self._active_tab == "logs":
        if not hasattr(self, "_logs_tab_obj"):
            self._logs_tab_obj = _LogsTab(self.page, self.app, self.profile)
        else:
            self._logs_tab_obj.on_show()
        self._tab_area.content = self._logs_tab_obj.root

    try:
        self._tab_area.update()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# _rebuild_header — reconstruye la vista después de cambio de OptiFine
# ---------------------------------------------------------------------------
def _rebuild_header(self) -> None:
    """
    B2: Reconstruye la vista completa tras un cambio de estado de OptiFine.
    El padre debe volver a conectar self.root; no llamamos update() sobre
    la referencia antigua.
    """
    self._build()


# ---------------------------------------------------------------------------
# _open_edit — abre el diálogo de edición de instancia
# ---------------------------------------------------------------------------
def _open_edit(self) -> None:
    from gui.views.instance.components import _InstanceSettingsDialog

    def done(updated_profile=None) -> None:
        if updated_profile:
            self.profile = updated_profile
        else:
            updated = self.app.profile_manager.get_profile(self.profile.id)
            if updated:
                self.profile = updated
        self._build()
        try:
            self.root.update()
        except Exception:
            pass

    _InstanceSettingsDialog(self.page, self.app, self.profile, on_done=done)


# ---------------------------------------------------------------------------
# _open_optifine_dialog — abre el diálogo de OptiFine
# ---------------------------------------------------------------------------
def _open_optifine_dialog(self) -> None:
    from gui.views.instance.components import _OptiFineDialog
    _OptiFineDialog(
        self.page, self.app, self.profile,
        on_done=lambda: self._rebuild_header(),
    )
