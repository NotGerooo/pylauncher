# -*- coding: utf-8 -*-
"""
gui/views/instance/__init__.py
Punto de entrada del paquete de instancia.
Exporta InstanceView ensamblando los módulos:
  - helpers.py   → constantes y funciones puras
  - layout.py    → métodos que construyen la UI
  - events.py    → métodos que manejan eventos y lógica
  - components.py → diálogos y tabs independientes
"""
import os
import flet as ft

from gui.views.instance.helpers import (
    _read_instance_setting,
    _VALID_TABS,
)
from gui.views.instance import layout, events


class InstanceView:
    """
    Vista de detalle de una instancia de Minecraft.
    Pestañas: Content | Files | Worlds | Logs
    """

    # -----------------------------------------------------------------------
    # Inyección de métodos de layout
    # -----------------------------------------------------------------------
    _build        = layout._build
    _count_items  = layout._count_items
    _make_tab_btn = layout._make_tab_btn

    # -----------------------------------------------------------------------
    # Inyección de métodos de eventos
    # -----------------------------------------------------------------------
    on_show               = events.on_show
    _set_play_status      = events._set_play_status
    _on_play              = events._on_play
    _persist_last_played  = events._persist_last_played
    _switch_tab           = events._switch_tab
    _render_tab           = events._render_tab
    _rebuild_header       = events._rebuild_header
    _open_edit            = events._open_edit
    _open_optifine_dialog = events._open_optifine_dialog

    # -----------------------------------------------------------------------
    # Constructor
    # -----------------------------------------------------------------------
    def __init__(self, page: ft.Page, app, profile) -> None:
        self.page    = page
        self.app     = app
        self.profile = profile

        # B5: asegurar que game_dir exista para que los sub-tabs puedan escribir
        os.makedirs(profile.game_dir, exist_ok=True)

        # S3: restaurar la última pestaña activa
        self._active_tab: str = _read_instance_setting(
            profile.game_dir, "active_tab", "content"
        )
        if self._active_tab not in _VALID_TABS:
            self._active_tab = "content"

        # Construir la UI llamando al método inyectado desde layout.py
        self._build()


# Re-exportar las clases de componentes para acceso directo al paquete
from gui.views.instance.components import (  # noqa: E402, F401
    _OptiFineDialog,
    _InstanceSettingsDialog,
    _FilesTab,
    _WorldsTab,
    _LogsTab,
)
