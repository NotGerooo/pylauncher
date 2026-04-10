"""App constants & Zen design tokens — single source of truth."""
from pathlib import Path

# ── Identity ──────────────────────────────────────────────
APP_NAME    = "Zen Launcher"
APP_VERSION = "1.0.0"
APP_ID      = "zen.launcher.1.0"

# ── Paths ─────────────────────────────────────────────────
DATA_DIR      = Path.home() / ".zen_launcher"
MINECRAFT_DIR = DATA_DIR / "minecraft"
LOGS_DIR      = DATA_DIR / "logs"

# ── Zen palette (Zen Browser inspired) ────────────────────
BG          = "#0e0e0e"
SURFACE     = "#161616"
SURFACE_2   = "#1e1e1e"
BORDER      = "#262626"

TEXT_PRI    = "#e2e2e2"
TEXT_SEC    = "#888888"
TEXT_DIM    = "#3d3d3d"

ACCENT      = "#3ecf6e"
ACCENT_DIM  = "#1a3d28"
ACCENT_GLOW = "#0f2018"

DANGER      = "#cc4a44"
WARNING     = "#c9941a"
