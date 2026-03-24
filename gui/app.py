"""
app.py — Gero's Launcher
Diseño inspirado en Modrinth App: sidebar de iconos, layout espacioso,
panel derecho fijo con cuenta activa y noticias reales.
"""
import tkinter as tk
from tkinter import ttk
import threading
import urllib.request
import json

from config.settings import Settings
from managers.version_manager import VersionManager
from managers.profile_manager import ProfileManager
from managers.java_manager import JavaManager
from services.auth_service import AuthService
from services.modrinth_service import ModrinthService
from core.launcher import LauncherEngine
from utils.logger import get_logger

log = get_logger()

BG         = "#1a1b1e"
SIDEBAR_BG = "#101113"
CARD_BG    = "#25262b"
CARD2_BG   = "#2c2d32"
INPUT_BG   = "#1e1f24"
BORDER     = "#373a40"
GREEN      = "#1bd96a"
GREEN_DIM  = "#0d7a3a"
TEXT_PRI   = "#e8e9ea"
TEXT_SEC   = "#909296"
TEXT_DIM   = "#5c5f66"
ACCENT_RED = "#fa5252"
NAV_ACTIVE = "#1f3329"
RIGHT_W    = 240   # ancho fijo del panel derecho


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gero's Launcher")
        self.geometry("1280x740")
        self.minsize(1000, 600)
        self.configure(bg=SIDEBAR_BG)
        self.resizable(True, True)
        self._apply_theme_from_settings()
        self.overrideredirect(True)
        self._drag_x = 0
        self._drag_y = 0
        self._init_services()
        self._init_styles()
        self._build_layout()
        self._show_view("home")
        log.info("Interfaz iniciada")
        self.update_idletasks()
        self.after(50, self._fix_taskbar)

    # ── Tema ────────────────────────────────────────────────────────────────
    def _apply_theme_from_settings(self):
        from config.settings import Settings
        s = Settings()
        theme = s._data.get("theme", "dark")
        palettes = {
            "dark":   {"bg": "#1a1b1e", "sidebar": "#101113", "card": "#25262b",
                       "card2": "#2c2d32", "input": "#1e1f24", "border": "#373a40",
                       "green": "#1bd96a", "green_dim": "#0d7a3a",
                       "text": "#e8e9ea", "sec": "#909296", "dim": "#5c5f66",
                       "nav": "#1f3329"},
            "darker": {"bg": "#0d0d0d", "sidebar": "#050505", "card": "#1a1a1a",
                       "card2": "#222222", "input": "#111111", "border": "#2a2a2a",
                       "green": "#1bd96a", "green_dim": "#0d7a3a",
                       "text": "#e8e9ea", "sec": "#888888", "dim": "#555555",
                       "nav": "#0d2a1a"},
            "blue":   {"bg": "#1a1a2e", "sidebar": "#16213e", "card": "#1e2a4a",
                       "card2": "#0f3460", "input": "#0a2540", "border": "#1e3a5f",
                       "green": "#e94560", "green_dim": "#c73652",
                       "text": "#e8e9ea", "sec": "#a0a0b0", "dim": "#6a6a8a",
                       "nav": "#1a2e50"},
            "light":  {"bg": "#f0f0f0", "sidebar": "#e0e0e0", "card": "#ffffff",
                       "card2": "#f5f5f5", "input": "#e8e8e8", "border": "#cccccc",
                       "green": "#1bd96a", "green_dim": "#0d7a3a",
                       "text": "#1a1a1a", "sec": "#555555", "dim": "#888888",
                       "nav": "#d0f0de"},
        }
        p = palettes.get(theme, palettes["dark"])
        import gui.app as _m
        _m.BG         = p["bg"]
        _m.SIDEBAR_BG = p["sidebar"]
        _m.CARD_BG    = p["card"]
        _m.CARD2_BG   = p["card2"]
        _m.INPUT_BG   = p["input"]
        _m.BORDER     = p["border"]
        _m.GREEN      = p["green"]
        _m.GREEN_DIM  = p["green_dim"]
        _m.TEXT_PRI   = p["text"]
        _m.TEXT_SEC   = p["sec"]
        _m.TEXT_DIM   = p["dim"]
        _m.NAV_ACTIVE = p["nav"]
        self.configure(bg=p["sidebar"])

    # ── Servicios ────────────────────────────────────────────────────────────
    def _init_services(self):
        from services.account_manager import AccountManager
        from services.microsoft_auth  import MicrosoftAuth
        from services.skin_service    import SkinService

        self.settings         = Settings()
        self.version_manager  = VersionManager(self.settings)
        self.profile_manager  = ProfileManager(self.settings)
        self.java_manager     = JavaManager(self.settings)
        self.auth_service     = AuthService()
        self.modrinth_service = ModrinthService()
        self.launcher_engine  = LauncherEngine(self.settings)
        self.account_manager  = AccountManager(data_dir="data")
        self.skin_service     = SkinService(cache_dir="data/skins")
        self.microsoft_auth   = MicrosoftAuth()

    # ── Titlebar ─────────────────────────────────────────────────────────────
    def _build_titlebar(self):
        BAR_BG = "#101113"
        bar = tk.Frame(self, bg=BAR_BG, height=44)
        bar.grid(row=0, column=0, columnspan=3, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)

        tk.Label(bar, text="⛏", bg=BAR_BG, fg=GREEN,
                 font=("Segoe UI", 14)).grid(row=0, column=0, padx=(16, 8), pady=10)
        tk.Label(bar, text="Gero's Launcher", bg=BAR_BG, fg=TEXT_PRI,
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=1, sticky="w")

        badge = tk.Frame(bar, bg="#1a2e20", padx=8, pady=2)
        badge.grid(row=0, column=2, padx=(0, 12))
        tk.Label(badge, text="● Online", bg="#1a2e20", fg=GREEN,
                 font=("Segoe UI", 8)).pack()

        tk.Frame(bar, bg=BORDER, width=1).grid(row=0, column=3, sticky="ns",
                                                pady=10, padx=(0, 12))

        btn_container = tk.Frame(bar, bg=BAR_BG)
        btn_container.grid(row=0, column=4, padx=(0, 16))

        def _circle_btn(parent, color, hover_color, symbol, cmd):
            SIZE = 14
            c = tk.Canvas(parent, width=SIZE, height=SIZE,
                          bg=BAR_BG, highlightthickness=0, cursor="hand2")
            c.pack(side="left", padx=4)
            dot = c.create_oval(1, 1, SIZE - 1, SIZE - 1, fill=color, outline="")
            sym = c.create_text(SIZE // 2, SIZE // 2, text=symbol,
                                fill=color, font=("Segoe UI", 7, "bold"),
                                state="hidden")

            def _enter(e):
                c.itemconfig(dot, fill=hover_color)
                c.itemconfig(sym, fill="#000000", state="normal")

            def _leave(e):
                c.itemconfig(dot, fill=color)
                c.itemconfig(sym, state="hidden")

            c.bind("<Enter>",    _enter)
            c.bind("<Leave>",    _leave)
            c.bind("<Button-1>", lambda e: cmd())

        _circle_btn(btn_container, "#ef4444", "#ff6b6b", "×", self.destroy)
        _circle_btn(btn_container, "#f59e0b", "#fbbf24", "−", self._minimize)
        _circle_btn(btn_container, "#10b981", "#34d399", "+", self._toggle_maximize)

        bar.bind("<ButtonPress-1>", self._on_drag_start)
        bar.bind("<B1-Motion>",     self._on_drag_move)

    def _fix_taskbar(self):
        import ctypes
        self._hwnd = ctypes.windll.user32.FindWindowW(None, "Gero's Launcher")
        if self._hwnd:
            GWL_EXSTYLE      = -20
            WS_EX_APPWINDOW  = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            style = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
            style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, style)
            SWP_NOMOVE       = 0x0002
            SWP_NOSIZE       = 0x0001
            SWP_NOZORDER     = 0x0004
            SWP_FRAMECHANGED = 0x0020
            ctypes.windll.user32.ShowWindow(self._hwnd, 0)
            ctypes.windll.user32.ShowWindow(self._hwnd, 5)
            ctypes.windll.user32.SetWindowPos(
                self._hwnd, 0, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)

    def _minimize(self):
        import ctypes
        if not getattr(self, "_hwnd", None):
            self._fix_taskbar()
        if self._hwnd:
            ctypes.windll.user32.ShowWindow(self._hwnd, 6)

    def _toggle_maximize(self):
        self.state("normal" if self.state() == "zoomed" else "zoomed")

    def _on_drag_start(self, event):
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _on_drag_move(self, event):
        self.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    # ── Estilos ──────────────────────────────────────────────────────────────
    def _init_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Primary.TButton", background=GREEN, foreground="#0a0a0a",
                    borderwidth=0, focusthickness=0,
                    font=("Segoe UI", 10, "bold"), padding=(18, 10))
        s.map("Primary.TButton",
              background=[("active", GREEN_DIM), ("disabled", CARD2_BG)],
              foreground=[("disabled", TEXT_DIM)])
        s.configure("Ghost.TButton", background=CARD2_BG, foreground=TEXT_PRI,
                    borderwidth=0, focusthickness=0,
                    font=("Segoe UI", 10), padding=(14, 8))
        s.map("Ghost.TButton", background=[("active", BORDER)])
        s.configure("Danger.TButton", background="#3d1f1f", foreground=ACCENT_RED,
                    borderwidth=0, focusthickness=0,
                    font=("Segoe UI", 10), padding=(14, 8))
        s.map("Danger.TButton", background=[("active", "#4a2424")])
        s.configure("TLabel", background=BG, foreground=TEXT_PRI,
                    font=("Segoe UI", 10))
        s.configure("H1.TLabel", background=BG, foreground=TEXT_PRI,
                    font=("Segoe UI", 24, "bold"))
        s.configure("Sub.TLabel", background=BG, foreground=TEXT_SEC,
                    font=("Segoe UI", 10))
        s.configure("Card.TFrame", background=CARD_BG)
        s.configure("TEntry", fieldbackground=INPUT_BG, foreground=TEXT_PRI,
                    insertcolor=TEXT_PRI, borderwidth=0, font=("Segoe UI", 10))
        s.configure("TCombobox", fieldbackground=INPUT_BG, foreground=TEXT_PRI,
                    background=INPUT_BG, selectbackground=INPUT_BG,
                    font=("Segoe UI", 10))
        s.map("TCombobox", fieldbackground=[("readonly", INPUT_BG)],
              foreground=[("readonly", TEXT_PRI)])
        s.configure("Treeview", background=INPUT_BG, foreground=TEXT_PRI,
                    fieldbackground=INPUT_BG, rowheight=42,
                    font=("Segoe UI", 10), borderwidth=0)
        s.configure("Treeview.Heading", background=CARD_BG, foreground=TEXT_SEC,
                    font=("Segoe UI", 9, "bold"), borderwidth=0, relief="flat")
        s.map("Treeview", background=[("selected", NAV_ACTIVE)],
              foreground=[("selected", GREEN)])
        s.configure("Vertical.TScrollbar", background=CARD_BG, troughcolor=INPUT_BG,
                    borderwidth=0, arrowsize=0, width=5)
        s.configure("Green.Horizontal.TProgressbar", background=GREEN,
                    troughcolor=INPUT_BG, borderwidth=0, thickness=6)

    # ── Layout principal ─────────────────────────────────────────────────────
    def _build_layout(self):
        # col 0 = sidebar iconos | col 1 = contenido | col 2 = panel derecho
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_titlebar()
        self._build_sidebar()

        self.content_frame = tk.Frame(self, bg=BG)
        self.content_frame.grid(row=1, column=1, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        self._current_view = None
        self._views        = {}
        self._active_nav   = None

        self._build_right_panel()

    # ── Sidebar izquierda ────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = tk.Frame(self, bg=SIDEBAR_BG, width=72)
        sb.grid(row=1, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_columnconfigure(0, weight=1)
        self._sb = sb

        logo_frame = tk.Frame(sb, bg=SIDEBAR_BG, height=76)
        logo_frame.grid(row=0, column=0, sticky="ew")
        logo_frame.grid_propagate(False)
        tk.Label(logo_frame, text="⛏", bg=SIDEBAR_BG, fg=GREEN,
                 font=("Segoe UI", 24)).place(relx=0.5, rely=0.5, anchor="center")

        tk.Frame(sb, bg=BORDER, height=1).grid(row=1, column=0,
                                                sticky="ew", padx=10)

        nav = [
            (2,  "🏠",  "Inicio",     "home"),
            (3,  "🔍",  "Descubrir",  "discover"),
            (4,  "📦",  "Biblioteca", "library"),
            (5,  "🧩",  "Mods",       "mods"),
            (6,  "⬇️",  "Descargas",  "downloads"),
        ]
        self._nav_buttons = {}
        for row, icon, label, vid in nav:
            sb.grid_rowconfigure(row, minsize=68)
            b = self._nav_btn(icon, label, vid)
            b.grid(row=row, column=0, sticky="nsew", padx=6, pady=2)
            self._nav_buttons[vid] = b

        sb.grid_rowconfigure(7, weight=1)
        tk.Frame(sb, bg=BORDER, height=1).grid(row=8, column=0,
                                                sticky="ew", padx=10)

        sb.grid_rowconfigure(9, minsize=68)
        bs = self._nav_btn("⚙️", "Ajustes", "settings")
        bs.grid(row=9, column=0, sticky="nsew", padx=6, pady=2)
        self._nav_buttons["settings"] = bs

        sb.grid_rowconfigure(10, minsize=68)
        ba = self._nav_btn("👤", "Cuentas", "accounts")
        ba.grid(row=10, column=0, sticky="nsew", padx=6, pady=(2, 10))
        self._nav_buttons["accounts"] = ba

    def _nav_btn(self, icon, tooltip, vid):
        btn = tk.Button(self._sb, text=icon,
                        bg=SIDEBAR_BG, fg=TEXT_SEC,
                        activebackground=NAV_ACTIVE, activeforeground=GREEN,
                        relief="flat", font=("Segoe UI", 20),
                        cursor="hand2",
                        command=lambda v=vid: self._show_view(v))
        self._tooltip(btn, tooltip)
        return btn

    def _tooltip(self, w, text):
        tip = None
        def show(e):
            nonlocal tip
            tip = tk.Toplevel(w)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{w.winfo_rootx()+78}+{w.winfo_rooty()+20}")
            tip.configure(bg=CARD2_BG)
            tk.Label(tip, text=text, bg=CARD2_BG, fg=TEXT_PRI,
                     font=("Segoe UI", 10), padx=12, pady=7).pack()
        def hide(e):
            nonlocal tip
            if tip:
                tip.destroy()
                tip = None
        w.bind("<Enter>", show)
        w.bind("<Leave>", hide)

    # ── Panel derecho fijo ───────────────────────────────────────────────────
    def _build_right_panel(self):
        rp = tk.Frame(self, bg=SIDEBAR_BG, width=RIGHT_W)
        rp.grid(row=1, column=2, sticky="nsew")
        rp.grid_propagate(False)
        rp.grid_columnconfigure(0, weight=1)
        rp.grid_rowconfigure(2, weight=1)
        self._right_panel = rp

        # Línea divisoria izquierda
        tk.Frame(rp, bg=BORDER, width=1).place(x=0, y=0, relheight=1)

        self._build_account_section(rp)

        tk.Frame(rp, bg=BORDER, height=1).grid(
            row=1, column=0, sticky="ew", padx=14, pady=0)

        self._build_news_section(rp)

        threading.Thread(target=self._fetch_news, daemon=True).start()

    # ── Sección cuenta ───────────────────────────────────────────────────────
    def _build_account_section(self, parent):
        frame = tk.Frame(parent, bg=SIDEBAR_BG, padx=18, pady=16)
        frame.grid(row=0, column=0, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        tk.Label(frame, text="JUGANDO COMO", bg=SIDEBAR_BG, fg=TEXT_DIM,
                 font=("Segoe UI", 8, "bold")).grid(
                 row=0, column=0, sticky="w", pady=(0, 10))

        acc_row = tk.Frame(frame, bg=SIDEBAR_BG)
        acc_row.grid(row=1, column=0, sticky="ew")
        acc_row.grid_columnconfigure(1, weight=1)

        self._avatar_canvas = tk.Canvas(acc_row, width=38, height=38,
                                         bg=SIDEBAR_BG, highlightthickness=0)
        self._avatar_canvas.grid(row=0, column=0, rowspan=2, padx=(0, 12))

        self._username_lbl = tk.Label(acc_row, text="—",
                                       bg=SIDEBAR_BG, fg=TEXT_PRI,
                                       font=("Segoe UI", 10, "bold"), anchor="w")
        self._username_lbl.grid(row=0, column=1, sticky="ew")

        dot_row = tk.Frame(acc_row, bg=SIDEBAR_BG)
        dot_row.grid(row=1, column=1, sticky="w")

        self._dot_canvas = tk.Canvas(dot_row, width=8, height=8,
                                      bg=SIDEBAR_BG, highlightthickness=0)
        self._dot_canvas.pack(side="left")
        self._dot_oval = self._dot_canvas.create_oval(
            1, 1, 7, 7, fill=TEXT_DIM, outline="")

        self._mode_lbl = tk.Label(dot_row, text="Sin cuenta",
                                   bg=SIDEBAR_BG, fg=TEXT_DIM,
                                   font=("Segoe UI", 8))
        self._mode_lbl.pack(side="left", padx=(4, 0))

        tk.Button(frame, text="Gestionar cuentas →",
                  bg=SIDEBAR_BG, fg=TEXT_SEC,
                  activebackground=CARD_BG, activeforeground=GREEN,
                  relief="flat", font=("Segoe UI", 8),
                  cursor="hand2", pady=6,
                  command=lambda: self._show_view("accounts")).grid(
                  row=2, column=0, sticky="w", pady=(12, 0))

        self.after(500, self.refresh_account_panel)

    def refresh_account_panel(self):
        """Actualiza la cuenta mostrada. Llamar desde AccountsView tras cambios."""
        try:
            account = self.account_manager.get_active_account()
            if not account:
                all_acc = self.account_manager.get_all_accounts()
                account = all_acc[0] if all_acc else None
        except Exception:
            account = None

        if account:
            name     = account.username
            is_ms    = getattr(account, "is_microsoft", False)
            mode_txt = "Microsoft" if is_ms else "Offline"
            dot_col  = GREEN if is_ms else TEXT_DIM
        else:
            name     = "Sin cuenta"
            mode_txt = "Offline"
            dot_col  = TEXT_DIM

        self._username_lbl.configure(text=name)
        self._mode_lbl.configure(text=mode_txt)
        self._dot_canvas.itemconfig(self._dot_oval, fill=dot_col)
        self._draw_avatar(name)

    def _draw_avatar(self, username: str):
        self._avatar_canvas.delete("all")
        palette = ["#1bd96a", "#4dabf7", "#f783ac", "#ffa94d",
                   "#a9e34b", "#74c0fc", "#ff8787", "#63e6be",
                   "#cc5de8", "#ff922b"]
        color    = palette[abs(hash(username)) % len(palette)]
        initials = (username[:2] if len(username) >= 2 else username).upper()
        self._avatar_canvas.create_oval(0, 0, 38, 38, fill=color, outline="")
        self._avatar_canvas.create_text(19, 19, text=initials,
                                         fill="#0a0a0a",
                                         font=("Segoe UI", 12, "bold"))

    # ── Sección noticias ─────────────────────────────────────────────────────
    def _build_news_section(self, parent):
        hdr = tk.Frame(parent, bg=SIDEBAR_BG, padx=18)
        hdr.grid(row=1, column=0, sticky="ew", pady=(14, 8))
        hdr.grid_columnconfigure(0, weight=1)

        tk.Label(hdr, text="NOTICIAS", bg=SIDEBAR_BG, fg=TEXT_DIM,
                 font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w")
        self._news_count_lbl = tk.Label(hdr, text="cargando…",
                                         bg=SIDEBAR_BG, fg=TEXT_DIM,
                                         font=("Segoe UI", 7))
        self._news_count_lbl.grid(row=0, column=1, sticky="e")

        wrapper = tk.Frame(parent, bg=SIDEBAR_BG)
        wrapper.grid(row=2, column=0, sticky="nsew", padx=(1, 0))
        wrapper.grid_columnconfigure(0, weight=1)
        wrapper.grid_rowconfigure(0, weight=1)

        self._news_canvas = tk.Canvas(wrapper, bg=SIDEBAR_BG,
                                       highlightthickness=0)
        self._news_canvas.grid(row=0, column=0, sticky="nsew")

        news_vsb = ttk.Scrollbar(wrapper, orient="vertical",
                                  command=self._news_canvas.yview)
        news_vsb.grid(row=0, column=1, sticky="ns")
        self._news_canvas.configure(yscrollcommand=news_vsb.set)

        self._news_inner = tk.Frame(self._news_canvas, bg=SIDEBAR_BG)
        self._news_win = self._news_canvas.create_window(
            (0, 0), window=self._news_inner, anchor="nw")

        self._news_inner.bind("<Configure>", lambda e:
            self._news_canvas.configure(
                scrollregion=self._news_canvas.bbox("all")))
        self._news_canvas.bind("<Configure>", lambda e:
            self._news_canvas.itemconfig(self._news_win, width=e.width))

        # Scroll solo cuando el cursor está encima del panel
        def _enter(e):
            self._news_canvas.bind_all("<MouseWheel>", _scroll)

        def _leave(e):
            self._news_canvas.unbind_all("<MouseWheel>")

        def _scroll(e):
            self._news_canvas.yview_scroll(-1 * (e.delta // 120), "units")

        self._news_canvas.bind("<Enter>", _enter)
        self._news_canvas.bind("<Leave>", _leave)
        self._news_inner.bind("<Enter>", _enter)
        self._news_inner.bind("<Leave>", _leave)

        tk.Label(self._news_inner, text="Conectando…",
                 bg=SIDEBAR_BG, fg=TEXT_DIM,
                 font=("Segoe UI", 9), pady=16).pack(fill="x", padx=14)

    def _fetch_news(self):
        items = []

        # Mojang — versiones recientes
        try:
            req = urllib.request.Request(
                "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json",
                headers={"User-Agent": "GerosLauncher/0.2.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())

            latest_r = data["latest"]["release"]
            latest_s = data["latest"]["snapshot"]
            items.append({
                "tag": "⭐ Destacado", "tag_color": GREEN,
                "title": f"Última release: {latest_r}",
                "body": f"Snapshot: {latest_s}",
                "source": "Mojang", "url": None,
            })
            type_map = {
                "release":  ("🟢 Release",  GREEN),
                "snapshot": ("🔵 Snapshot", "#4dabf7"),
                "old_beta": ("🟡 Beta",     "#ffa94d"),
                "old_alpha":("🔴 Alpha",    "#ff6b6b"),
            }
            for v in data["versions"][:5]:
                tag, tc = type_map.get(v["type"], (v["type"], TEXT_SEC))
                fecha = v.get("releaseTime", "")[:10]
                items.append({
                    "tag": tag, "tag_color": tc,
                    "title": f"Minecraft {v['id']}",
                    "body": fecha,
                    "source": "Mojang", "url": None,
                })
        except Exception as ex:
            log.warning(f"Noticias Mojang: {ex}")

        # Modrinth — mods actualizados recientemente
        try:
            req2 = urllib.request.Request(
                "https://api.modrinth.com/v2/search"
                "?limit=4&index=updated&facets=[[%22project_type:mod%22]]",
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

        self.after(0, lambda: self._render_news(items))

    def _render_news(self, items: list):
        for w in self._news_inner.winfo_children():
            w.destroy()

        if not items:
            tk.Label(self._news_inner, text="Sin conexión.",
                     bg=SIDEBAR_BG, fg=TEXT_DIM,
                     font=("Segoe UI", 9), pady=12).pack(fill="x", padx=14)
            self._news_count_lbl.configure(text="sin conexión")
            return

        self._news_count_lbl.configure(text=f"{len(items)} entradas")

        for i, item in enumerate(items):
            if i > 0:
                tk.Frame(self._news_inner, bg=BORDER, height=1).pack(
                    fill="x", padx=12)
            self._make_news_card(item)

    def _make_news_card(self, item: dict):
        has_url = bool(item.get("url"))
        card = tk.Frame(self._news_inner, bg=SIDEBAR_BG,
                        padx=14, pady=8,
                        cursor="hand2" if has_url else "")
        card.pack(fill="x")
        card.grid_columnconfigure(0, weight=1)

        hdr = tk.Frame(card, bg=SIDEBAR_BG)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        tk.Label(hdr, text=item["tag"],
                 bg=SIDEBAR_BG, fg=item.get("tag_color", GREEN),
                 font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(hdr, text=item["source"],
                 bg=SIDEBAR_BG, fg=TEXT_DIM,
                 font=("Segoe UI", 7)).grid(row=0, column=1, sticky="e")

        tk.Label(card, text=item["title"],
                 bg=SIDEBAR_BG, fg=TEXT_PRI,
                 font=("Segoe UI", 9, "bold"),
                 anchor="w", wraplength=RIGHT_W - 36,
                 justify="left").grid(row=1, column=0, sticky="ew", pady=(2, 0))

        if item.get("body"):
            tk.Label(card, text=item["body"],
                     bg=SIDEBAR_BG, fg=TEXT_SEC,
                     font=("Segoe UI", 8),
                     anchor="w", wraplength=RIGHT_W - 36,
                     justify="left").grid(row=2, column=0, sticky="ew")

        # Recoger todos los widgets para hover
        all_w = [card, hdr] + list(card.winfo_children()) + list(hdr.winfo_children())

        def on_enter(e):
            for w in all_w:
                try: w.configure(bg=CARD_BG)
                except Exception: pass

        def on_leave(e):
            for w in all_w:
                try: w.configure(bg=SIDEBAR_BG)
                except Exception: pass

        for w in all_w:
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)

        if has_url:
            def open_url(e, u=item["url"]):
                import webbrowser
                webbrowser.open(u)
            for w in all_w:
                w.bind("<Button-1>", open_url)

    # ── Navegación ───────────────────────────────────────────────────────────
    def _show_view(self, vid: str):
        if self._active_nav and self._active_nav in self._nav_buttons:
            self._nav_buttons[self._active_nav].configure(
                bg=SIDEBAR_BG, fg=TEXT_SEC)
        if vid in self._nav_buttons:
            self._nav_buttons[vid].configure(bg=NAV_ACTIVE, fg=GREEN)
        self._active_nav = vid

        if vid not in self._views:
            self._views[vid] = self._create_view(vid)
        if self._current_view:
            self._current_view.grid_remove()
        self._current_view = self._views[vid]
        self._current_view.grid(row=0, column=0, sticky="nsew")
        if hasattr(self._current_view, "on_show"):
            self._current_view.on_show()

        # Refrescar cuenta en el panel derecho
        self.after(100, self.refresh_account_panel)

    def _create_view(self, vid: str):
        from gui.views.home_view     import HomeView
        from gui.views.profiles_view import ProfilesView
        from gui.views.mods_view     import ModsView
        from gui.views.discover_view import DiscoverView
        from gui.views.library_view  import LibraryView
        from gui.views.settings_view import SettingsView
        from gui.views.accounts_view import AccountsView
        m = {
            "home":      HomeView,
            "profiles":  ProfilesView,
            "mods":      ModsView,
            "discover":  DiscoverView,
            "library":   LibraryView,
            "settings":  SettingsView,
            "accounts":  AccountsView,
        }
        cls = m.get(vid)
        return cls(self.content_frame, self) if cls else self._placeholder(vid)

    def _placeholder(self, name):
        icons = {"downloads": "⬇️", "accounts": "👤"}
        f = tk.Frame(self.content_frame, bg=BG)
        c = tk.Frame(f, bg=BG)
        c.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(c, text=icons.get(name, "🚧"), bg=BG, fg=TEXT_SEC,
                 font=("Segoe UI", 52)).pack()
        tk.Label(c, text=name.capitalize(), bg=BG, fg=TEXT_SEC,
                 font=("Segoe UI", 15)).pack(pady=(8, 0))
        tk.Label(c, text="Próximamente", bg=BG, fg=TEXT_DIM,
                 font=("Segoe UI", 10)).pack(pady=(4, 0))
        return f