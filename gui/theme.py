"""
theme.py — Sistema de tema centralizado para Gero's Launcher
Todas las vistas deben importar colores y fuentes desde aquí.
"""

# ── Paleta de colores ────────────────────────────────────────────────────────
BG          = "#16171a"      # fondo principal (más oscuro, más profundo)
BG_ELEVATED = "#1c1d21"     # fondo de cards elevadas
SIDEBAR_BG  = "#0e0f11"     # sidebar muy oscura
CARD_BG     = "#222327"     # cards normales
CARD2_BG    = "#28292e"     # cards secundarias / hover
INPUT_BG    = "#1a1b1f"     # campos de entrada
BORDER      = "#2e2f35"     # bordes sutiles
BORDER_BRIGHT = "#3d3e45"   # bordes visibles

GREEN       = "#1bd96a"     # acento principal
GREEN_DIM   = "#13a050"     # verde más oscuro para hover
GREEN_GLOW  = "#1bd96a22"   # verde con transparencia para backgrounds
GREEN_SUBTLE= "#0f2318"     # fondo muy sutil para elementos activos

TEXT_PRI    = "#f0f1f3"     # texto principal
TEXT_SEC    = "#8b8e96"     # texto secundario
TEXT_DIM    = "#4a4d55"     # texto muy apagado
TEXT_INV    = "#0a0b0d"     # texto sobre fondo verde

ACCENT_RED  = "#ff4757"
ACCENT_YEL  = "#ffa502"
ACCENT_BLUE = "#3d8ff5"

NAV_ACTIVE  = "#0f2318"     # fondo nav item activo
NAV_HOVER   = "#1a1c21"     # fondo nav item hover

# ── Tipografía ───────────────────────────────────────────────────────────────
# Poppins como principal, Outfit para títulos grandes, fallback a Segoe UI
# Tkinter no carga fuentes web, pero podemos usar las mejores fuentes del sistema
# En Windows: "Segoe UI Variable" (Win11) o "Segoe UI" es la mejor opción
# Para títulos usamos tamaños y pesos que den personalidad

FONT_TITLE_XL = ("Segoe UI Variable Display", 28, "bold")   # títulos hero
FONT_TITLE_LG = ("Segoe UI Variable Display", 20, "bold")   # títulos de sección
FONT_TITLE_MD = ("Segoe UI Variable Display", 15, "bold")   # subtítulos
FONT_TITLE_SM = ("Segoe UI Variable Display", 13, "bold")   # card titles

FONT_BODY_LG  = ("Segoe UI Variable Text", 12)              # cuerpo grande
FONT_BODY_MD  = ("Segoe UI Variable Text", 11)              # cuerpo normal
FONT_BODY_SM  = ("Segoe UI Variable Text", 10)              # cuerpo pequeño
FONT_BODY_XS  = ("Segoe UI Variable Text", 9)               # notas

FONT_MONO     = ("Cascadia Code", 10)                       # monoespaciado

FONT_BTN_PRI  = ("Segoe UI Variable Text", 10, "bold")      # botón primario
FONT_BTN_SEC  = ("Segoe UI Variable Text", 10)              # botón secundario
FONT_LABEL    = ("Segoe UI Variable Text", 9)               # etiquetas campos

FONT_NAV      = ("Segoe UI Variable Text", 9)               # navegación sidebar
FONT_BADGE    = ("Segoe UI Variable Text", 8, "bold")       # badges

# Fallbacks seguros (si las fuentes variables no están disponibles)
FONT_FALLBACK_TITLE = ("Segoe UI", 28, "bold")
FONT_FALLBACK_BODY  = ("Segoe UI", 10)

# ── Métricas / Spacing ───────────────────────────────────────────────────────
RADIUS        = 8    # border radius para canvas rounded
SIDEBAR_W     = 220  # ancho de sidebar expandida
SIDEBAR_W_COL = 72   # ancho sidebar colapsada
PAD_PAGE      = 40   # padding páginas
PAD_CARD      = 24   # padding interno cards
PAD_SM        = 12   # padding pequeño

# ── Helper para obtener font con fallback ────────────────────────────────────
import tkinter.font as tkfont

_font_cache: dict = {}

def get_font(preferred: tuple, fallback: tuple = None) -> tuple:
    """Devuelve la fuente preferida si existe, si no la fallback."""
    key = preferred[0]
    if key in _font_cache:
        return _font_cache[key]
    try:
        families = tkfont.families()
        if preferred[0] in families:
            _font_cache[key] = preferred
            return preferred
    except Exception:
        pass
    result = fallback or (("Segoe UI", preferred[1], preferred[2]) if len(preferred) == 3
                          else ("Segoe UI", preferred[1]))
    _font_cache[key] = result
    return result
