"""
app.py — Gero's Launcher
Diseño premium con sidebar expandida, tipografía mejorada y titlebar elegante.
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
from gui.theme import (
    BG, SIDEBAR_BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER, BORDER_BRIGHT,
    GREEN, GREEN_DIM, GREEN_SUBTLE,
    TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV,
    NAV_ACTIVE, NAV_HOVER, ACCENT_RED,
)

log = get_logger()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gero's Launcher")
        self.geometry("1280x780")
        self.minsize(1000, 640)
        self.configure(bg=SIDEBAR_BG)
        self.resizable(True, True)
        self.overrideredirect(True)
        self._drag_x = 0
        self._drag_y = 0
        self._maximized = False

        self._init_services()
        self._apply_theme_from_settings()
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

    def _apply_theme_from_settings(self):
        pass

    # ── Titlebar ─────────────────────────────────────────────────────────────
    def _build_titlebar(self):
        bar = tk.Frame(self, bg=SIDEBAR_BG, height=48)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(2, weight=1)

        # Logo area alineada con sidebar
        logo_area = tk.Frame(bar, bg=SIDEBAR_BG, width=220)
        logo_area.grid(row=0, column=0, sticky="ns")
        logo_area.grid_propagate(False)
        logo_inner = tk.Frame(logo_area, bg=SIDEBAR_BG)
        logo_inner.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(logo_inner, text="⛏", bg=SIDEBAR_BG, fg=GREEN,
                 font=("Segoe UI", 16)).pack(side="left", padx=(0, 8))
        tk.Label(logo_inner, text="Gero's Launcher", bg=SIDEBAR_BG, fg=TEXT_PRI,
                 font=("Segoe UI Variable Display", 11, "bold")).pack(side="left")

        # Separador
        tk.Frame(bar, bg=BORDER, width=1).grid(row=0, column=1, sticky="ns", pady=10)

        # Área de arrastre central
        drag_area = tk.Frame(bar, bg=SIDEBAR_BG)
        drag_area.grid(row=0, column=2, sticky="nsew")
        drag_area.bind("<ButtonPress-1>", self._on_drag_start)
        drag_area.bind("<B1-Motion>",     self._on_drag_move)
        drag_area.bind("<Double-Button-1>", lambda e: self._toggle_maximize())

        # Badge versión
        ver_badge = tk.Frame(drag_area, bg="#172616", padx=10, pady=3)
        ver_badge.place(relx=0.02, rely=0.5, anchor="w")
        tk.Label(ver_badge, text="v0.2.0", bg="#172616", fg=GREEN,
                 font=("Segoe UI Variable Text", 8, "bold")).pack()

        # Botones ventana
        btn_area = tk.Frame(bar, bg=SIDEBAR_BG)
        btn_area.grid(row=0, column=3, sticky="ns", padx=(0, 18))

        def _wbtn(parent, color, hover_c, symbol, cmd):
            SIZE = 15
            c = tk.Canvas(parent, width=SIZE, height=SIZE,
                          bg=SIDEBAR_BG, highlightthickness=0, cursor="hand2")
            c.pack(side="left", padx=5)
            oval = c.create_oval(1, 1, SIZE - 1, SIZE - 1, fill=color, outline="")
            sym  = c.create_text(SIZE // 2, SIZE // 2, text=symbol,
                                  fill="#333333", font=("Segoe UI", 7, "bold"),
                                  state="hidden")
            def _enter(e):
                c.itemconfig(oval, fill=hover_c)
                c.itemconfig(sym, state="normal")
            def _leave(e):
                c.itemconfig(oval, fill=color)
                c.itemconfig(sym, state="hidden")
            c.bind("<Enter>",    _enter)
            c.bind("<Leave>",    _leave)
            c.bind("<Button-1>", lambda e: cmd())

        _wbtn(btn_area, "#ff5f57", "#ff3b30", "×", self.destroy)
        _wbtn(btn_area, "#febc2e", "#f0a500", "−", self._minimize)
        _wbtn(btn_area, "#28c840", "#1da831", "+", self._toggle_maximize)

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
            SWP_FLAGS = 0x0002 | 0x0001 | 0x0004 | 0x0020
            ctypes.windll.user32.ShowWindow(self._hwnd, 0)
            ctypes.windll.user32.ShowWindow(self._hwnd, 5)
            ctypes.windll.user32.SetWindowPos(self._hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)

    def _minimize(self):
        import ctypes
        if not getattr(self, "_hwnd", None):
            self._fix_taskbar()
        if self._hwnd:
            ctypes.windll.user32.ShowWindow(self._hwnd, 6)

    def _toggle_maximize(self):
        if self._maximized:
            self.state("normal")
            self._maximized = False
        else:
            self.state("zoomed")
            self._maximized = True

    def _on_drag_start(self, event):
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _on_drag_move(self, event):
        if not self._maximized:
            self.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    # ── Estilos ttk ──────────────────────────────────────────────────────────
    def _init_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")

        s.configure("Primary.TButton",
                    background=GREEN, foreground=TEXT_INV,
                    borderwidth=0, focusthickness=0,
                    font=("Segoe UI Variable Text", 10, "bold"),
                    padding=(20, 10))
        s.map("Primary.TButton",
              background=[("active", GREEN_DIM), ("disabled", CARD2_BG)],
              foreground=[("disabled", TEXT_DIM)])

        s.configure("Ghost.TButton",
                    background=CARD2_BG, foreground=TEXT_PRI,
                    borderwidth=0, focusthickness=0,
                    font=("Segoe UI Variable Text", 10),
                    padding=(16, 9))
        s.map("Ghost.TButton", background=[("active", BORDER_BRIGHT)])

        s.configure("Danger.TButton",
                    background="#2d1515", foreground=ACCENT_RED,
                    borderwidth=0, focusthickness=0,
                    font=("Segoe UI Variable Text", 10),
                    padding=(16, 9))
        s.map("Danger.TButton", background=[("active", "#3d1f1f")])

        s.configure("Subtle.TButton",
                    background=INPUT_BG, foreground=TEXT_SEC,
                    borderwidth=0, focusthickness=0,
                    font=("Segoe UI Variable Text", 9),
                    padding=(12, 7))
        s.map("Subtle.TButton",
              background=[("active", CARD2_BG)],
              foreground=[("active", TEXT_PRI)])

        s.configure("TLabel",
                    background=BG, foreground=TEXT_PRI,
                    font=("Segoe UI Variable Text", 10))
        s.configure("H1.TLabel",
                    background=BG, foreground=TEXT_PRI,
                    font=("Segoe UI Variable Display", 26, "bold"))
        s.configure("H2.TLabel",
                    background=BG, foreground=TEXT_PRI,
                    font=("Segoe UI Variable Display", 18, "bold"))
        s.configure("Sub.TLabel",
                    background=BG, foreground=TEXT_SEC,
                    font=("Segoe UI Variable Text", 11))

        s.configure("Card.TFrame", background=CARD_BG)
        s.configure("Card2.TFrame", background=CARD2_BG)

        s.configure("TEntry",
                    fieldbackground=INPUT_BG, foreground=TEXT_PRI,
                    insertcolor=TEXT_PRI, borderwidth=0,
                    font=("Segoe UI Variable Text", 10),
                    padding=(10, 8))

        s.configure("TCombobox",
                    fieldbackground=INPUT_BG, foreground=TEXT_PRI,
                    background=INPUT_BG, selectbackground=INPUT_BG,
                    font=("Segoe UI Variable Text", 10))
        s.map("TCombobox",
              fieldbackground=[("readonly", INPUT_BG)],
              foreground=[("readonly", TEXT_PRI)],
              selectbackground=[("readonly", INPUT_BG)])

        s.configure("Treeview",
                    background=INPUT_BG, foreground=TEXT_PRI,
                    fieldbackground=INPUT_BG, rowheight=46,
                    font=("Segoe UI Variable Text", 10), borderwidth=0)
        s.configure("Treeview.Heading",
                    background=CARD_BG, foreground=TEXT_SEC,
                    font=("Segoe UI Variable Text", 9, "bold"),
                    borderwidth=0, relief="flat")
        s.map("Treeview",
              background=[("selected", NAV_ACTIVE)],
              foreground=[("selected", GREEN)])

        s.configure("Vertical.TScrollbar",
                    background=CARD_BG, troughcolor=INPUT_BG,
                    borderwidth=0, arrowsize=0, width=4)
        s.map("Vertical.TScrollbar",
              background=[("active", BORDER_BRIGHT)])

        s.configure("Green.Horizontal.TProgressbar",
                    background=GREEN, troughcolor=INPUT_BG,
                    borderwidth=0, thickness=4)

        s.configure("TNotebook", background=CARD_BG, borderwidth=0, tabmargins=0)
        s.configure("TNotebook.Tab",
                    background=CARD_BG, foreground=TEXT_SEC,
                    font=("Segoe UI Variable Text", 10),
                    padding=(18, 9), borderwidth=0)
        s.map("TNotebook.Tab",
              background=[("selected", BG)],
              foreground=[("selected", TEXT_PRI)])

    # ── Layout ───────────────────────────────────────────────────────────────
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
        sb = tk.Frame(self, bg=SIDEBAR_BG, width=220)
        sb.grid(row=1, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_columnconfigure(0, weight=1)
        self._sb = sb

        # Borde superior
        tk.Frame(sb, bg=BORDER, height=1).grid(row=0, column=0, sticky="ew")

        # Sección MENÚ
        s1 = tk.Frame(sb, bg=SIDEBAR_BG, padx=16)
        s1.grid(row=1, column=0, sticky="ew", pady=(16, 4))
        tk.Label(s1, text="MENÚ", bg=SIDEBAR_BG, fg=TEXT_DIM,
                 font=("Segoe UI Variable Text", 8, "bold")).pack(anchor="w")

        self._nav_buttons = {}
        nav_items = [
            ("home",    "🏠", "Inicio"),
            ("discover","🔍", "Descubrir"),
            ("library", "📦", "Biblioteca"),
            ("mods",    "🧩", "Mods"),
        ]
        for i, (vid, icon, label) in enumerate(nav_items, start=2):
            btn = self._make_nav_btn(vid, icon, label)
            btn.grid(row=i, column=0, sticky="ew", padx=10, pady=2)
            self._nav_buttons[vid] = btn

        sb.grid_rowconfigure(7, weight=1)

        tk.Frame(sb, bg=BORDER, height=1).grid(row=8, column=0, sticky="ew", padx=16)

        s2 = tk.Frame(sb, bg=SIDEBAR_BG, padx=16)
        s2.grid(row=9, column=0, sticky="ew", pady=(12, 4))
        tk.Label(s2, text="CUENTA", bg=SIDEBAR_BG, fg=TEXT_DIM,
                 font=("Segoe UI Variable Text", 8, "bold")).pack(anchor="w")

        for i, (vid, icon, label) in enumerate([
            ("settings", "⚙️", "Ajustes"),
            ("accounts", "👤", "Cuentas"),
        ], start=10):
            btn = self._make_nav_btn(vid, icon, label)
            btn.grid(row=i, column=0, sticky="ew", padx=10, pady=2)
            self._nav_buttons[vid] = btn

        footer = tk.Frame(sb, bg=SIDEBAR_BG, padx=16, pady=14)
        footer.grid(row=12, column=0, sticky="ew")
        tk.Label(footer, text="Gero's Launcher  •  v0.2.0",
                 bg=SIDEBAR_BG, fg=TEXT_DIM,
                 font=("Segoe UI Variable Text", 8)).pack(anchor="w")

    def _make_nav_btn(self, vid: str, icon: str, label: str) -> tk.Frame:
        container = tk.Frame(self._sb, bg=SIDEBAR_BG, cursor="hand2")
        container.grid_columnconfigure(1, weight=1)

        pill = tk.Frame(container, bg=SIDEBAR_BG, padx=14, pady=10)
        pill.grid(row=0, column=0, columnspan=3, sticky="ew")
        pill.grid_columnconfigure(1, weight=1)

        icon_lbl = tk.Label(pill, text=icon, bg=SIDEBAR_BG, fg=TEXT_SEC,
                            font=("Segoe UI", 14), width=2)
        icon_lbl.grid(row=0, column=0, padx=(0, 10))

        text_lbl = tk.Label(pill, text=label, bg=SIDEBAR_BG, fg=TEXT_SEC,
                            font=("Segoe UI Variable Text", 11), anchor="w")
        text_lbl.grid(row=0, column=1, sticky="ew")

        container._pill   = pill
        container._icon   = icon_lbl
        container._text   = text_lbl
        container._vid    = vid
        container._active = False

        def _enter(e):
            if not container._active:
                for w in (pill, icon_lbl, text_lbl):
                    w.configure(bg=NAV_HOVER)

        def _leave(e):
            if not container._active:
                for w in (pill, icon_lbl, text_lbl):
                    w.configure(bg=SIDEBAR_BG)

        def _click(e):
            self._show_view(vid)

        for w in (container, pill, icon_lbl, text_lbl):
            w.bind("<Enter>",    _enter)
            w.bind("<Leave>",    _leave)
            w.bind("<Button-1>", _click)

        return container

    def _set_nav_active(self, vid: str):
        for v, btn in self._nav_buttons.items():
            active = (v == vid)
            btn._active = active
            if active:
                btn._pill.configure(bg=NAV_ACTIVE)
                btn._icon.configure(bg=NAV_ACTIVE, fg=GREEN)
                btn._text.configure(bg=NAV_ACTIVE, fg=TEXT_PRI,
                                    font=("Segoe UI Variable Text", 11, "bold"))
            else:
                btn._pill.configure(bg=SIDEBAR_BG)
                btn._icon.configure(bg=SIDEBAR_BG, fg=TEXT_SEC)
                btn._text.configure(bg=SIDEBAR_BG, fg=TEXT_SEC,
                                    font=("Segoe UI Variable Text", 11))

    # ── Navegación ───────────────────────────────────────────────────────────
    def _show_view(self, vid: str):
        self._set_nav_active(vid)
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
            "home":     HomeView,
            "profiles": ProfilesView,
            "mods":     ModsView,
            "discover": DiscoverView,
            "library":  LibraryView,
            "settings": SettingsView,
            "accounts": AccountsView,
        }
        cls = m.get(vid)
        return cls(self.content_frame, self) if cls else self._placeholder(vid)

    def _placeholder(self, name):
        icons = {"downloads": "⬇️", "accounts": "👤"}
        f = tk.Frame(self.content_frame, bg=BG)
        c = tk.Frame(f, bg=BG)
        c.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(c, text=icons.get(name, "🚧"), bg=BG, fg=TEXT_SEC,
                 font=("Segoe UI", 48)).pack()
        tk.Label(c, text=name.capitalize(), bg=BG, fg=TEXT_SEC,
                 font=("Segoe UI Variable Display", 16, "bold")).pack(pady=(10, 0))
        tk.Label(c, text="Próximamente", bg=BG, fg=TEXT_DIM,
                 font=("Segoe UI Variable Text", 10)).pack(pady=(4, 0))
        return f