"""settings_view.py — Panel de ajustes con sub-navegación lateral"""
import tkinter as tk
from tkinter import ttk, filedialog
import os

BG        = "#1a1b1e"
CARD_BG   = "#25262b"
CARD2_BG  = "#2c2d32"
INPUT_BG  = "#1e1f24"
BORDER    = "#373a40"
GREEN     = "#1bd96a"
GREEN_DIM = "#0d7a3a"
TEXT_PRI  = "#e8e9ea"
TEXT_SEC  = "#909296"
TEXT_DIM  = "#5c5f66"
SEL_BG    = "#1f3329"


def _btn(parent, text, cmd, primary=True, small=False):
    bg  = GREEN if primary else CARD2_BG
    fg  = "#0a0a0a" if primary else TEXT_PRI
    abg = GREEN_DIM if primary else BORDER
    f   = ("Segoe UI", 9 if small else 10, "bold" if primary else "normal")
    return tk.Button(parent, text=text, bg=bg, fg=fg,
                     activebackground=abg, activeforeground=fg,
                     relief="flat", font=f, padx=10 if small else 16,
                     pady=5 if small else 8, cursor="hand2", command=cmd)


SECTIONS = [
    ("general",   "⚙️  General"),
    ("minecraft", "🎮  Minecraft"),
    ("java",      "☕  Java"),
    ("carpetas",  "📁  Carpetas"),
    ("apariencia","🎨  Apariencia"),
]


class SettingsView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._active = None
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=BG, padx=40, pady=32)
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew")
        tk.Label(hdr, text="Ajustes", bg=BG, fg=TEXT_PRI,
                 font=("Segoe UI", 24, "bold")).pack(anchor="w")
        tk.Label(hdr, text="Configura tu experiencia en Gero's Launcher",
                 bg=BG, fg=TEXT_SEC, font=("Segoe UI", 11)).pack(anchor="w", pady=(4, 0))

        # Sub-sidebar
        sub = tk.Frame(self, bg=CARD_BG, width=220, padx=12, pady=16)
        sub.grid(row=1, column=0, sticky="nsew", padx=(40, 0), pady=(0, 40))
        sub.grid_propagate(False)
        self._sec_btns = {}
        for key, label in SECTIONS:
            b = tk.Button(sub, text=label, bg=CARD_BG, fg=TEXT_SEC,
                          activebackground=SEL_BG, activeforeground=GREEN,
                          relief="flat", anchor="w",
                          font=("Segoe UI", 10), padx=16, pady=10,
                          cursor="hand2",
                          command=lambda k=key: self._show_section(k))
            b.pack(fill="x", pady=1)
            self._sec_btns[key] = b

        # Versión abajo del sub-sidebar
        tk.Label(sub, text="Gero's Launcher v1.0.0\nWindows",
                 bg=CARD_BG, fg=TEXT_DIM, font=("Segoe UI", 8),
                 justify="left").pack(side="bottom", anchor="w", padx=4, pady=8)

        # Contenido
        self._content = tk.Frame(self, bg=BG, padx=40, pady=8)
        self._content.grid(row=1, column=1, sticky="nsew", pady=(0, 40))
        self._content.grid_columnconfigure(0, weight=1)

        self._show_section("general")

    def _show_section(self, key):
        if self._active:
            self._sec_btns[self._active].configure(
                bg=CARD_BG, fg=TEXT_SEC, font=("Segoe UI", 10))
        self._sec_btns[key].configure(
            bg=SEL_BG, fg=GREEN, font=("Segoe UI", 10, "bold"))
        self._active = key
        for w in self._content.winfo_children():
            w.destroy()
        getattr(self, f"_section_{key}")()

    def _title(self, text):
        tk.Label(self._content, text=text, bg=BG, fg=TEXT_PRI,
                 font=("Segoe UI", 16, "bold")).pack(
                     anchor="w", pady=(8, 24))

    def _card(self):
        c = tk.Frame(self._content, bg=CARD_BG, padx=24, pady=20)
        c.pack(fill="x", pady=(0, 12))
        return c

    def _field(self, card, label, sub=None):
        tk.Label(card, text=label, bg=CARD_BG, fg=TEXT_PRI,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        if sub:
            tk.Label(card, text=sub, bg=CARD_BG, fg=TEXT_SEC,
                     font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 8))
        else:
            tk.Frame(card, bg=CARD_BG, height=8).pack()

    # ── Secciones ──────────────────────────────────────────────────────────────
    def _section_general(self):
        self._title("General")
        c = self._card()
        self._field(c, "Idioma", "Idioma de la interfaz")
        lang = tk.StringVar(value="Español")
        ttk.Combobox(c, textvariable=lang, values=["Español", "English"],
                     state="readonly", font=("Segoe UI", 10),
                     width=20).pack(anchor="w", ipady=6)

        c2 = self._card()
        self._field(c2, "Actualizaciones automáticas",
                    "Notificar cuando haya una nueva versión del launcher")
        var = tk.BooleanVar(value=True)
        tk.Checkbutton(c2, text="Activar actualizaciones automáticas",
                       variable=var, bg=CARD_BG, fg=TEXT_PRI,
                       selectcolor=INPUT_BG, activebackground=CARD_BG,
                       font=("Segoe UI", 10)).pack(anchor="w")

    def _section_minecraft(self):
        self._title("Minecraft")
        c = self._card()
        self._field(c, "RAM predeterminada",
                    "Memoria asignada a nuevas instancias")
        var = tk.StringVar(value=str(self.app.settings.default_ram_mb))
        combo = ttk.Combobox(c, textvariable=var,
                              values=["1024","2048","3072","4096","6144","8192"],
                              state="readonly", font=("Segoe UI", 10), width=16)
        combo.pack(anchor="w", ipady=6)
        def save(*_):
            try: self.app.settings.default_ram_mb = int(var.get())
            except: pass
        combo.bind("<<ComboboxSelected>>", save)
        tk.Label(c, text="MB de RAM", bg=CARD_BG, fg=TEXT_DIM,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))

        c2 = self._card()
        self._field(c2, "Cerrar launcher al jugar",
                    "Ocultar el launcher cuando Minecraft se inicia")
        var2 = tk.BooleanVar(value=self.app.settings.close_on_launch)
        def toggle():
            self.app.settings.close_on_launch = var2.get()
        tk.Checkbutton(c2, text="Cerrar al lanzar", variable=var2,
                       bg=CARD_BG, fg=TEXT_PRI, selectcolor=INPUT_BG,
                       activebackground=CARD_BG, font=("Segoe UI", 10),
                       command=toggle).pack(anchor="w")

    def _section_java(self):
        self._title("Instalaciones de Java")
        c = self._card()
        self._field(c, "Detección automática de Java",
                    "El launcher detectará las instalaciones de Java en tu sistema")
        java_path = self.app.settings.java_path or "Auto-detectado"
        tk.Label(c, text=f"Java activo: {java_path}",
                 bg=CARD_BG, fg=GREEN, font=("Segoe UI", 9)).pack(anchor="w")

        c2 = self._card()
        self._field(c2, "Java personalizado",
                    "Especifica una ruta manual a java.exe")
        pf = tk.Frame(c2, bg=CARD_BG)
        pf.pack(fill="x")
        pf.grid_columnconfigure(0, weight=1)
        var = tk.StringVar(value=self.app.settings.java_path or "")
        e = tk.Entry(pf, textvariable=var, bg=INPUT_BG, fg=TEXT_PRI,
                     insertbackground=TEXT_PRI, relief="flat", font=("Segoe UI", 10))
        e.grid(row=0, column=0, sticky="ew", ipady=8, padx=(0, 10))
        def browse():
            path = filedialog.askopenfilename(
                title="Seleccionar java.exe",
                filetypes=[("Java", "java.exe"), ("Todos", "*.*")])
            if path:
                var.set(path)
                self.app.settings.java_path = path
        _btn(pf, "Examinar", browse, primary=False, small=True).grid(row=0, column=1)

        c3 = self._card()
        self._field(c3, "Versiones de Java detectadas",
                    "Java instalado en tu sistema")
        try:
            javas = self.app.java_manager.list_available_java()
            for j in javas[:5]:
                tk.Label(c3, text=f"☕  Java {j.get('version_string','?')}  —  {j.get('path','')}",
                         bg=CARD_BG, fg=TEXT_SEC,
                         font=("Segoe UI", 9)).pack(anchor="w", pady=2)
        except Exception:
            tk.Label(c3, text="No se pudo listar Java.",
                     bg=CARD_BG, fg=TEXT_DIM, font=("Segoe UI", 9)).pack(anchor="w")

    def _section_carpetas(self):
        self._title("Carpetas")
        dirs = [
            ("Directorio principal", self.app.settings.minecraft_dir),
            ("Versiones",            self.app.settings.versions_dir),
            ("Librerías",            self.app.settings.libraries_dir),
            ("Assets",               self.app.settings.assets_dir),
            ("Perfiles",             self.app.settings.profiles_dir),
        ]
        for label, path in dirs:
            c = self._card()
            c.grid_columnconfigure(0, weight=1) if hasattr(c, "grid_columnconfigure") else None
            tk.Label(c, text=label, bg=CARD_BG, fg=TEXT_PRI,
                     font=("Segoe UI", 11, "bold")).pack(anchor="w")
            tk.Label(c, text=path, bg=CARD_BG, fg=TEXT_SEC,
                     font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))

    def _section_apariencia(self):
        self._title("Apariencia")
        c = self._card()
        self._field(c, "Tema de color", "Apariencia visual del launcher")
        temas = ["Oscuro (Modrinth)", "OLED", "Oscuro clásico"]
        var = tk.StringVar(value=temas[0])
        for t in temas:
            tk.Radiobutton(c, text=t, variable=var, value=t,
                           bg=CARD_BG, fg=TEXT_PRI,
                           selectcolor=INPUT_BG, activebackground=CARD_BG,
                           font=("Segoe UI", 10)).pack(anchor="w", pady=4)

    def on_show(self):
        pass
