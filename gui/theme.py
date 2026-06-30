# gui/theme.py — Color palette shared across all Flet views
#
# Antes este archivo solo tenía colores fijos. Ahora define 3 paletas
# (dark, light, oled) y elige cuál usar leyendo data/launcher_settings.json
# apenas se importa el módulo (es decir, al arrancar el launcher).
#
# IMPORTANTE: cambiar el tema desde Settings guarda la elección, pero
# para que se vea hay que reiniciar el launcher (SettingsView ya lo pide).
# Esto es porque el resto de los archivos hacen
# "from gui.theme import BG, ..." y Python copia el valor en ese momento;
# no hay forma de "avisarles" que cambió sin reiniciar el proceso.

import json
import os
import sys

_SETTINGS_FILE = os.path.join("data", "launcher_settings.json")

_PALETTES = {
    "dark": dict(
        BG="#1a1b1e", SIDEBAR_BG="#101113", CARD_BG="#1e2023", CARD2_BG="#25272b",
        INPUT_BG="#2c2e33", BORDER="#2e3035", BORDER_BRIGHT="#3d4049",
        GREEN="#1bd96a", GREEN_DIM="#17b85a", GREEN_SUBTLE="#0d2018",
        TEXT_PRI="#e8e8e8", TEXT_SEC="#9da3ae", TEXT_DIM="#5c6370", TEXT_INV="#0a0a0a",
        NAV_ACTIVE="#1a2520", NAV_HOVER="#16191c",
        ACCENT_RED="#ff6b6b",
        ROW_SELECTED="#162820", ROW_HOVER_INCOMPATIBLE="#141920",
    ),
    "oled": dict(
        BG="#000000", SIDEBAR_BG="#000000", CARD_BG="#0a0a0a", CARD2_BG="#121212",
        INPUT_BG="#161616", BORDER="#1f1f1f", BORDER_BRIGHT="#2a2a2a",
        GREEN="#1bd96a", GREEN_DIM="#17b85a", GREEN_SUBTLE="#08140f",
        TEXT_PRI="#f0f0f0", TEXT_SEC="#9da3ae", TEXT_DIM="#55585c", TEXT_INV="#0a0a0a",
        NAV_ACTIVE="#0d1310", NAV_HOVER="#0a0a0a",
        ACCENT_RED="#ff6b6b",
        ROW_SELECTED="#0d1310", ROW_HOVER_INCOMPATIBLE="#0a0a0a",
    ),
    "light": dict(
        BG="#f5f5f6", SIDEBAR_BG="#ffffff", CARD_BG="#ffffff", CARD2_BG="#eef0f2",
        INPUT_BG="#eceef0", BORDER="#dcdfe3", BORDER_BRIGHT="#c8ccd1",
        GREEN="#0fa958", GREEN_DIM="#0c8a47", GREEN_SUBTLE="#e3f9ee",
        TEXT_PRI="#1a1b1e", TEXT_SEC="#52565c", TEXT_DIM="#8a8f96", TEXT_INV="#ffffff",
        NAV_ACTIVE="#e3f9ee", NAV_HOVER="#eef0f2",
        ACCENT_RED="#e03131",
        ROW_SELECTED="#e3f9ee", ROW_HOVER_INCOMPATIBLE="#f4f4f5",
    ),
}


def _read_saved_theme() -> str:
    """
    Lee el tema guardado en data/launcher_settings.json.
    No usa config.settings.Settings a propósito, para no crear un
    import circular (theme.py se importa muy temprano, antes que
    el resto de la app).
    """
    try:
        with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("theme", "dark")
    except Exception:
        return "dark"


def _detect_system_theme() -> str:
    """
    Detecta si Windows está en modo claro u oscuro mirando el registro.
    En cualquier otro caso (no es Windows, o falla la lectura) usa 'dark'.
    """
    if sys.platform != "win32":
        return "dark"
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        # AppsUseLightTheme: 1 = modo claro, 0 = modo oscuro
        return "light" if value == 1 else "dark"
    except Exception:
        return "dark"


def _resolve_active_palette() -> dict:
    choice = _read_saved_theme()
    if choice == "system":
        choice = _detect_system_theme()
    return _PALETTES.get(choice, _PALETTES["dark"])


_active = _resolve_active_palette()

BG            = _active["BG"]
SIDEBAR_BG    = _active["SIDEBAR_BG"]
CARD_BG       = _active["CARD_BG"]
CARD2_BG      = _active["CARD2_BG"]
INPUT_BG      = _active["INPUT_BG"]
BORDER        = _active["BORDER"]
BORDER_BRIGHT = _active["BORDER_BRIGHT"]

GREEN        = _active["GREEN"]
GREEN_DIM    = _active["GREEN_DIM"]
GREEN_SUBTLE = _active["GREEN_SUBTLE"]

TEXT_PRI = _active["TEXT_PRI"]
TEXT_SEC = _active["TEXT_SEC"]
TEXT_DIM = _active["TEXT_DIM"]
TEXT_INV = _active["TEXT_INV"]

NAV_ACTIVE = _active["NAV_ACTIVE"]
NAV_HOVER  = _active["NAV_HOVER"]

ACCENT_RED = _active["ACCENT_RED"]

AVATAR_PALETTE = [
    "#1bd96a", "#4dabf7", "#f783ac", "#ffa94d",
    "#a9e34b", "#74c0fc", "#ff8787", "#63e6be",
    "#cc5de8", "#ff922b",
]
ROW_SELECTED = _active["ROW_SELECTED"]
ROW_HOVER_INCOMPATIBLE = _active["ROW_HOVER_INCOMPATIBLE"]
