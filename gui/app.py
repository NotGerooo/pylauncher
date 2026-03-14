"""
app.py — Gero's Launcher
Diseño inspirado en Modrinth App: sidebar de iconos, layout espacioso.
"""
import tkinter as tk
from tkinter import ttk
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


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gero's Launcher")
        self.geometry("1200x740")
        self.minsize(960, 600)
        self.configure(bg=SIDEBAR_BG)
        self.resizable(True, True)
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

    # ── Titlebar ────────────────────────────────────────────────────────────
    def _build_titlebar(self):
        BAR_BG = "#101113"

        bar = tk.Frame(self, bg=BAR_BG, height=44)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)

        # Icono + título
        tk.Label(bar, text="⛏", bg=BAR_BG, fg=GREEN,
                 font=("Segoe UI", 14)).grid(row=0, column=0, padx=(16, 8), pady=10)
        tk.Label(bar, text="Gero's Launcher", bg=BAR_BG, fg=TEXT_PRI,
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=1, sticky="w")

        # Badge "Online"
        badge = tk.Frame(bar, bg="#1a2e20", padx=8, pady=2)
        badge.grid(row=0, column=2, padx=(0, 12))
        tk.Label(badge, text="● Online", bg="#1a2e20", fg=GREEN,
                 font=("Segoe UI", 8)).pack()

        # Separador vertical
        tk.Frame(bar, bg=BORDER, width=1).grid(row=0, column=3, sticky="ns",
                                                pady=10, padx=(0, 12))

        # Botones círculo estilo macOS
        btn_container = tk.Frame(bar, bg=BAR_BG)
        btn_container.grid(row=0, column=4, padx=(0, 16))

        def _circle_btn(parent, color, hover_color, symbol, cmd):
            SIZE = 14
            c = tk.Canvas(parent, width=SIZE, height=SIZE,
                          bg=BAR_BG, highlightthickness=0, cursor="hand2")
            c.pack(side="left", padx=4)
            dot  = c.create_oval(1, 1, SIZE - 1, SIZE - 1,
                                 fill=color, outline="")
            sym  = c.create_text(SIZE // 2, SIZE // 2, text=symbol,
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

        # Drag para mover la ventana
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
            # Forzar que Windows re-evalue la ventana para la taskbar
            SWP_NOMOVE   = 0x0002
            SWP_NOSIZE   = 0x0001
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020
            # Ocultar y mostrar para forzar que Windows registre en taskbar
            ctypes.windll.user32.ShowWindow(self._hwnd, 0)   # SW_HIDE
            ctypes.windll.user32.ShowWindow(self._hwnd, 5)   # SW_SHOW
            ctypes.windll.user32.SetWindowPos(
                self._hwnd, 0, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
            )
        
    def _minimize(self):
        import ctypes
        if not getattr(self, "_hwnd", None):
            self._fix_taskbar()
        if self._hwnd:
            ctypes.windll.user32.ShowWindow(self._hwnd, 6)

    def _toggle_maximize(self):
        if self.state() == "zoomed":
            self.state("normal")
        else:
            self.state("zoomed")

    def _on_drag_start(self, event):
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _on_drag_move(self, event):
        self.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    # ── Estilos ─────────────────────────────────────────────────────────────
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
        s.configure("TLabel", background=BG, foreground=TEXT_PRI, font=("Segoe UI", 10))
        s.configure("H1.TLabel", background=BG, foreground=TEXT_PRI, font=("Segoe UI", 24, "bold"))
        s.configure("Sub.TLabel", background=BG, foreground=TEXT_SEC, font=("Segoe UI", 10))
        s.configure("Card.TFrame", background=CARD_BG)
        s.configure("TEntry", fieldbackground=INPUT_BG, foreground=TEXT_PRI,
                    insertcolor=TEXT_PRI, borderwidth=0, font=("Segoe UI", 10))
        s.configure("TCombobox", fieldbackground=INPUT_BG, foreground=TEXT_PRI,
                    background=INPUT_BG, selectbackground=INPUT_BG, font=("Segoe UI", 10))
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

    # ── Layout ──────────────────────────────────────────────────────────────
    def _build_layout(self):
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

        tk.Frame(sb, bg=BORDER, height=1).grid(row=1, column=0, sticky="ew", padx=10)

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
        tk.Frame(sb, bg=BORDER, height=1).grid(row=8, column=0, sticky="ew", padx=10)

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
                tip.destroy(); tip = None
        w.bind("<Enter>", show)
        w.bind("<Leave>", hide)

    def _show_view(self, vid: str):
        if self._active_nav and self._active_nav in self._nav_buttons:
            self._nav_buttons[self._active_nav].configure(bg=SIDEBAR_BG, fg=TEXT_SEC)
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