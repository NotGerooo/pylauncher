"""
home_view.py — Vista de Inicio
Cards espaciosas, layout de dos columnas, estilo Modrinth.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from utils.logger import get_logger
log = get_logger()

BG         = "#1a1b1e"
CARD_BG    = "#25262b"
CARD2_BG   = "#2c2d32"
INPUT_BG   = "#1e1f24"
BORDER     = "#373a40"
GREEN      = "#1bd96a"
GREEN_DIM  = "#0d7a3a"
TEXT_PRI   = "#e8e9ea"
TEXT_SEC   = "#909296"
TEXT_DIM   = "#5c5f66"
NAV_ACTIVE = "#1f3329"


def _btn(parent, text, command, primary=True, small=False):
    font_size = 9 if small else 10
    weight = "bold" if primary else "normal"
    bg = GREEN if primary else CARD2_BG
    fg = "#0a0a0a" if primary else TEXT_PRI
    abg = GREEN_DIM if primary else BORDER
    px = 12 if small else 20
    py = 5 if small else 9
    return tk.Button(parent, text=text, bg=bg, fg=fg,
                     activebackground=abg, activeforeground=fg,
                     relief="flat", font=("Segoe UI", font_size, weight),
                     padx=px, pady=py, cursor="hand2", command=command)


class HomeView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build()

    def _build(self):
        # Canvas scrollable
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self._sf = tk.Frame(canvas, bg=BG)
        self._sf.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self._win = canvas.create_window((0, 0), window=self._sf, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(self._win, width=e.width))
        canvas.bind("<MouseWheel>",
            lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        self._canvas = canvas

        m = self._sf
        m.grid_columnconfigure(0, weight=3)
        m.grid_columnconfigure(1, weight=1)

        # ── Cabecera bienvenida ────────────────────────────────────────────
        hero = tk.Frame(m, bg=BG, padx=40, pady=36)
        hero.grid(row=0, column=0, columnspan=2, sticky="ew")
        hero.grid_columnconfigure(0, weight=1)
        tk.Label(hero, text="¡Bienvenido a Gero's Launcher!",
                 bg=BG, fg=TEXT_PRI, font=("Segoe UI", 26, "bold")).grid(
                     row=0, column=0, sticky="w")
        tk.Label(hero, text="Lanza Minecraft, gestiona mods y descubre contenido nuevo",
                 bg=BG, fg=TEXT_SEC, font=("Segoe UI", 11)).grid(
                     row=1, column=0, sticky="w", pady=(4, 0))
        # ── Card de lanzamiento rápido ────────────────────────────────────
        lcard = tk.Frame(m, bg=CARD_BG, padx=32, pady=28)
        lcard.grid(row=1, column=0, sticky="ew", padx=(40, 16), pady=(0, 20))
        lcard.grid_columnconfigure(1, weight=1)

        # Icono instancia
        ico = tk.Frame(lcard, bg=INPUT_BG, width=64, height=64)
        ico.grid(row=0, column=0, rowspan=3, sticky="nw", padx=(0, 24))
        ico.grid_propagate(False)
        tk.Label(ico, text="🎮", bg=INPUT_BG,
                 font=("Segoe UI", 28)).place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(lcard, text="Juego rápido", bg=CARD_BG, fg=TEXT_PRI,
                 font=("Segoe UI", 14, "bold")).grid(row=0, column=1, sticky="w")
        self._profile_label = tk.Label(lcard, text="Selecciona un perfil abajo",
                                        bg=CARD_BG, fg=TEXT_SEC,
                                        font=("Segoe UI", 10))
        self._profile_label.grid(row=1, column=1, sticky="w", pady=(2, 12))

        self._launch_btn = _btn(lcard, "▶  JUGAR", self._on_launch)
        self._launch_btn.grid(row=2, column=1, sticky="w")

        # ── Selección de usuario y perfil ─────────────────────────────────
        sel = tk.Frame(m, bg=CARD_BG, padx=32, pady=24)
        sel.grid(row=2, column=0, sticky="ew", padx=(40, 16), pady=(0, 20))
        sel.grid_columnconfigure(0, weight=1)
        sel.grid_columnconfigure(1, weight=1)

        # Usuario
        uf = tk.Frame(sel, bg=CARD_BG)
        uf.grid(row=0, column=0, sticky="ew", padx=(0, 20))
        tk.Label(uf, text="Usuario", bg=CARD_BG, fg=TEXT_SEC,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))
        self._username_var = tk.StringVar(value="Player")
        ue = tk.Entry(uf, textvariable=self._username_var,
                      bg=INPUT_BG, fg=TEXT_PRI, insertbackground=TEXT_PRI,
                      relief="flat", font=("Segoe UI", 11), bd=0)
        ue.pack(fill="x", ipady=10)
        ue.bind("<KeyRelease>", self._on_username_change)

        # Perfil
        pf = tk.Frame(sel, bg=CARD_BG)
        pf.grid(row=0, column=1, sticky="ew")
        tk.Label(pf, text="Perfil / Instancia", bg=CARD_BG, fg=TEXT_SEC,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))
        self._profile_var = tk.StringVar()
        self._profile_combo = ttk.Combobox(pf, textvariable=self._profile_var,
                                           state="readonly", font=("Segoe UI", 11))
        self._profile_combo.pack(fill="x", ipady=6)
        self._profile_combo.bind("<<ComboboxSelected>>", self._on_profile_select)

        # ── Barra de progreso ─────────────────────────────────────────────
        self._pbar_frame = tk.Frame(m, bg=CARD_BG, padx=32, pady=16)
        self._pbar_lbl = tk.Label(self._pbar_frame, text="", bg=CARD_BG,
                                   fg=TEXT_SEC, font=("Segoe UI", 9))
        self._pbar_lbl.pack(anchor="w", pady=(0, 6))
        self._pbar = ttk.Progressbar(self._pbar_frame,
                                      style="Green.Horizontal.TProgressbar",
                                      mode="determinate")
        self._pbar.pack(fill="x")

        # ── Versiones de Minecraft ────────────────────────────────────────
        vcard = tk.Frame(m, bg=CARD_BG, padx=32, pady=28)
        vcard.grid(row=4, column=0, sticky="ew", padx=(40, 16), pady=(0, 40))
        vcard.grid_columnconfigure(0, weight=1)

        vh = tk.Frame(vcard, bg=CARD_BG)
        vh.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        vh.grid_columnconfigure(0, weight=1)
        tk.Label(vh, text="Versiones de Minecraft", bg=CARD_BG, fg=TEXT_PRI,
                 font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")

        ir = tk.Frame(vcard, bg=CARD_BG)
        ir.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        self._version_var = tk.StringVar()
        self._version_combo = ttk.Combobox(ir, textvariable=self._version_var,
                                           state="readonly", font=("Segoe UI", 10),
                                           width=20)
        self._version_combo.pack(side="left", ipady=7)
        _btn(ir, "Instalar versión", self._on_install_version).pack(
            side="left", padx=(14, 0))

        cols = ("Versión", "Estado")
        self._ver_tree = ttk.Treeview(vcard, columns=cols, show="headings", height=5)
        self._ver_tree.heading("Versión", text="Versión instalada")
        self._ver_tree.heading("Estado",  text="Estado")
        self._ver_tree.column("Versión", width=280)
        self._ver_tree.column("Estado",  width=140)
        self._ver_tree.grid(row=2, column=0, sticky="ew")
        vsb2 = ttk.Scrollbar(vcard, orient="vertical", command=self._ver_tree.yview)
        vsb2.grid(row=2, column=1, sticky="ns")
        self._ver_tree.configure(yscrollcommand=vsb2.set)

        # ── Panel derecho: resumen ────────────────────────────────────────
        right = tk.Frame(m, bg=BG, padx=(0), pady=0)
        right.grid(row=1, column=1, rowspan=4, sticky="nsew", padx=(0, 40), pady=(0, 40))
        right.grid_columnconfigure(0, weight=1)

        self._stat_cards = []
        stats = [
            ("📦", "Versiones\nInstaladas", "0"),
            ("👤", "Perfiles",              "0"),
            ("🧩", "Mods totales",          "0"),
        ]
        for i, (icon, label, val) in enumerate(stats):
            sc = tk.Frame(right, bg=CARD_BG, padx=20, pady=20)
            sc.grid(row=i, column=0, sticky="ew", pady=(0, 12))
            sc.grid_columnconfigure(1, weight=1)
            tk.Label(sc, text=icon, bg=CARD_BG,
                     font=("Segoe UI", 20)).grid(row=0, column=0, rowspan=2,
                                                  sticky="w", padx=(0, 16))
            val_lbl = tk.Label(sc, text=val, bg=CARD_BG, fg=GREEN,
                               font=("Segoe UI", 22, "bold"))
            val_lbl.grid(row=0, column=1, sticky="w")
            tk.Label(sc, text=label, bg=CARD_BG, fg=TEXT_SEC,
                     font=("Segoe UI", 9)).grid(row=1, column=1, sticky="w")
            self._stat_cards.append(val_lbl)

        # Atajo a descubrir
        disc_card = tk.Frame(right, bg=CARD_BG, padx=20, pady=20)
        disc_card.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        tk.Label(disc_card, text="🔍  Descubrir mods", bg=CARD_BG, fg=TEXT_PRI,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(disc_card, text="Busca mods y modpacks\nen Modrinth",
                 bg=CARD_BG, fg=TEXT_SEC,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 12))
        _btn(disc_card, "Explorar →",
             lambda: self.app._show_view("discover"), small=True).pack(anchor="w")

    def on_show(self):
        self._refresh_profiles()
        self._refresh_versions()
        self._refresh_installed()
        self._refresh_stats()

    def _refresh_profiles(self):
        profiles = self.app.profile_manager.get_all_profiles()
        names = [p.name for p in profiles]
        self._profile_combo["values"] = names
        if names:
            last = self.app.settings.last_profile
            val = last if last in names else names[0]
            self._profile_var.set(val)
            self._profile_label.configure(text=val)

    def _on_profile_select(self, e=None):
        self._profile_label.configure(text=self._profile_var.get())

    def _on_username_change(self, e=None):
        pass

    def _refresh_versions(self):
        def fetch():
            try:
                versions = self.app.version_manager.get_available_versions("release")
                ids = [v.id for v in versions]
                self.after(0, lambda: self._version_combo.configure(values=ids))
                if ids:
                    self.after(0, lambda: self._version_var.set(ids[0]))
            except Exception as ex:
                log.warning(f"No se pudieron cargar versiones: {ex}")
        threading.Thread(target=fetch, daemon=True).start()

    def _refresh_installed(self):
        self._ver_tree.delete(*self._ver_tree.get_children())
        installed = self.app.version_manager.get_installed_version_ids()
        for v in installed:
            self._ver_tree.insert("", "end", values=(v, "✓  Instalada"), tags=("ok",))
        self._ver_tree.tag_configure("ok", foreground=GREEN)
        if not installed:
            self._ver_tree.insert("", "end", values=("Sin versiones instaladas", "—"))

    def _refresh_stats(self):
        try:
            installed = len(self.app.version_manager.get_installed_version_ids())
            profiles  = len(self.app.profile_manager.get_all_profiles())
            self._stat_cards[0].configure(text=str(installed))
            self._stat_cards[1].configure(text=str(profiles))
        except Exception:
            pass

    # ── Instalación ───────────────────────────────────────────────────────────
    def _show_progress(self, visible):
        if visible:
            self._pbar_frame.grid(row=3, column=0, sticky="ew",
                                   padx=(40, 16), pady=(0, 12))
        else:
            self._pbar_frame.grid_remove()

    def _on_install_version(self):
        vid = self._version_var.get()
        if not vid:
            messagebox.showwarning("Aviso", "Selecciona una versión.")
            return
        self._show_progress(True)
        self._pbar_lbl.configure(text=f"Instalando {vid}...")
        self._pbar["value"] = 0
        self._launch_btn.configure(state="disabled")

        def run():
            try:
                def cb(step, cur, total):
                    if total > 0:
                        pct = cur / total * 100
                        self.after(0, lambda: (
                            self._pbar.__setitem__("value", pct),
                            self._pbar_lbl.configure(text=step)
                        ))
                self.app.version_manager.install_version(vid, cb)
                self.after(0, self._install_done)
            except Exception as ex:
                self.after(0, lambda: self._install_error(str(ex)))
        threading.Thread(target=run, daemon=True).start()

    def _install_done(self):
        self._pbar["value"] = 100
        self._pbar_lbl.configure(text="✓  Instalación completada")
        self._launch_btn.configure(state="normal")
        self._refresh_installed()
        self._refresh_stats()
        self.after(2500, lambda: self._show_progress(False))

    def _install_error(self, err):
        self._show_progress(False)
        self._launch_btn.configure(state="normal")
        messagebox.showerror("Error de instalación", err)

    # ── Lanzamiento ───────────────────────────────────────────────────────────
    def _on_launch(self):
        username = self._username_var.get().strip()
        profile_name = self._profile_var.get()
        if not username:
            messagebox.showwarning("Aviso", "Ingresa tu nombre de usuario.")
            return
        if not profile_name:
            messagebox.showwarning("Aviso", "Selecciona un perfil.")
            return
        profile = self.app.profile_manager.get_profile_by_name(profile_name)
        if not profile:
            messagebox.showerror("Error", f"Perfil '{profile_name}' no encontrado.")
            return
        try:
            session = self.app.auth_service.create_offline_session(username)
            version_data = self.app.version_manager.get_version_data(profile.version_id)
        except Exception as ex:
            messagebox.showerror("Error", str(ex))
            return
        try:
            process = self.app.launcher_engine.launch(
                profile, session, version_data,
                on_output=lambda l: log.info(f"[MC] {l}"))
            self.app.settings.last_profile = profile_name
            self._launch_btn.configure(state="disabled", text="▶  JUGANDO...")

            def wait():
                process.wait()
                rc = process.returncode
                log.info(f"Minecraft cerrado con código: {rc}")
                if rc != 0:
                    self.after(0, lambda: messagebox.showerror(
                        "Minecraft cerrado",
                        f"El juego cerró con error (código {rc}).\n"
                        f"Revisa /logs para más detalles."))
                self.after(0, lambda: self._launch_btn.configure(
                    state="normal", text="▶  JUGAR"))
            threading.Thread(target=wait, daemon=True).start()
        except Exception as ex:
            messagebox.showerror("Error al lanzar", str(ex))
