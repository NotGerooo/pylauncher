"""
home_view.py — Vista de Inicio
Rediseño premium: hero banner, launch card elegante, stats visuales.
Selector de cuenta via account_manager. Sin noticias.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from utils.logger import get_logger
log = get_logger()

BG        = "#16171a"
BG_EL     = "#1c1d21"
CARD_BG   = "#222327"
CARD2_BG  = "#28292e"
INPUT_BG  = "#1a1b1f"
BORDER    = "#2e2f35"
GREEN     = "#1bd96a"
GREEN_DIM = "#13a050"
GREEN_SUB = "#0f2318"
TEXT_PRI  = "#f0f1f3"
TEXT_SEC  = "#8b8e96"
TEXT_DIM  = "#4a4d55"
TEXT_INV  = "#0a0b0d"
RED       = "#ff4757"


def _btn_primary(parent, text, command, width=None):
    kw = {"width": width} if width else {}
    return tk.Button(
        parent, text=text, command=command,
        bg=GREEN, fg=TEXT_INV,
        activebackground=GREEN_DIM, activeforeground=TEXT_INV,
        relief="flat", cursor="hand2",
        font=("Segoe UI Variable Text", 10, "bold"),
        padx=22, pady=10, **kw)


def _btn_ghost(parent, text, command, small=False):
    return tk.Button(
        parent, text=text, command=command,
        bg=CARD2_BG, fg=TEXT_PRI,
        activebackground=BORDER, activeforeground=TEXT_PRI,
        relief="flat", cursor="hand2",
        font=("Segoe UI Variable Text", 9 if small else 10),
        padx=14 if small else 18, pady=6 if small else 9)


class HomeView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build()

    def _build(self):
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

        def _bind_scroll(widget):
            widget.bind("<MouseWheel>",
                lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
            for child in widget.winfo_children():
                _bind_scroll(child)

        self._sf.bind("<Configure>", lambda e: (
            canvas.configure(scrollregion=canvas.bbox("all")),
            _bind_scroll(self._sf)
        ))
        m = self._sf
        m.grid_columnconfigure(0, weight=3)
        m.grid_columnconfigure(1, weight=1, minsize=280)

        self._build_hero(m)
        self._build_launch_card(m)
        self._build_user_profile_row(m)
        self._build_progress_area(m)
        self._build_versions_card(m)
        self._build_right_panel(m)

    # ── Hero ─────────────────────────────────────────────────────────────────
    def _build_hero(self, m):
        hero = tk.Frame(m, bg=BG_EL)
        hero.grid(row=0, column=0, columnspan=2, sticky="ew")

        inner = tk.Frame(hero, bg=BG_EL, padx=44, pady=36)
        inner.pack(fill="x")
        inner.grid_columnconfigure(0, weight=1)

        badge_f = tk.Frame(inner, bg="#0f2318", padx=10, pady=4)
        badge_f.grid(row=0, column=0, sticky="w", pady=(0, 12))
        tk.Label(badge_f, text="⚡  Gero's Launcher", bg="#0f2318", fg=GREEN,
                 font=("Segoe UI Variable Text", 9, "bold")).pack()

        tk.Label(inner, text="¡Bienvenido de vuelta!",
                 bg=BG_EL, fg=TEXT_PRI,
                 font=("Segoe UI Variable Display", 28, "bold")).grid(
                     row=1, column=0, sticky="w")
        tk.Label(inner,
                 text="Lanza Minecraft, gestiona mods y descubre contenido nuevo desde Modrinth.",
                 bg=BG_EL, fg=TEXT_SEC,
                 font=("Segoe UI Variable Text", 12)).grid(
                     row=2, column=0, sticky="w", pady=(6, 0))

        tk.Frame(hero, bg=BORDER, height=1).pack(fill="x")

    # ── Launch card ──────────────────────────────────────────────────────────
    def _build_launch_card(self, m):
        wrapper = tk.Frame(m, bg=BG, padx=40)
        wrapper.grid(row=1, column=0, sticky="ew", pady=(28, 0))
        wrapper.grid_columnconfigure(0, weight=1)

        card = tk.Frame(wrapper, bg=CARD_BG, padx=28, pady=24)
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        ico_bg = tk.Frame(card, bg="#1a2e1e", width=68, height=68)
        ico_bg.grid(row=0, column=0, rowspan=3, sticky="nw", padx=(0, 20))
        ico_bg.grid_propagate(False)
        tk.Label(ico_bg, text="🎮", bg="#1a2e1e",
                 font=("Segoe UI", 30)).place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(card, text="Lanzamiento rápido",
                 bg=CARD_BG, fg=TEXT_PRI,
                 font=("Segoe UI Variable Display", 15, "bold")).grid(
                     row=0, column=1, sticky="w")

        self._profile_label = tk.Label(card, text="Selecciona un perfil abajo",
                                        bg=CARD_BG, fg=TEXT_SEC,
                                        font=("Segoe UI Variable Text", 10))
        self._profile_label.grid(row=1, column=1, sticky="w", pady=(3, 14))

        self._launch_btn = _btn_primary(card, "▶   JUGAR", self._on_launch)
        self._launch_btn.grid(row=2, column=1, sticky="w")

    # ── Fila cuenta + perfil ─────────────────────────────────────────────────
    def _build_user_profile_row(self, m):
        wrapper = tk.Frame(m, bg=BG, padx=40)
        wrapper.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        wrapper.grid_columnconfigure(0, weight=1)
        wrapper.grid_columnconfigure(1, weight=1)

        # ── Selector de cuenta ────────────────────────────────────────────
        uf = tk.Frame(wrapper, bg=CARD_BG, padx=20, pady=18)
        uf.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        uf.grid_columnconfigure(0, weight=1)

        tk.Label(uf, text="Cuenta", bg=CARD_BG, fg=TEXT_SEC,
                 font=("Segoe UI Variable Text", 9)).pack(anchor="w", pady=(0, 7))

        self._account_var = tk.StringVar()
        self._account_combo = ttk.Combobox(uf, textvariable=self._account_var,
                                           state="readonly",
                                           font=("Segoe UI Variable Text", 11))
        self._account_combo.pack(fill="x", ipady=6)
        self._account_combo.bind("<<ComboboxSelected>>",
                                 lambda e: self._on_account_select())

        self._no_account_lbl = tk.Label(
            uf, text="⚠ Sin cuentas — crea una en 'Cuentas'",
            bg=CARD_BG, fg="#e67e22",
            font=("Segoe UI Variable Text", 9), cursor="hand2")
        self._no_account_lbl.bind("<Button-1>",
                                  lambda e: self.app._show_view("accounts"))

        # ── Selector de perfil ────────────────────────────────────────────
        pf = tk.Frame(wrapper, bg=CARD_BG, padx=20, pady=18)
        pf.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        pf.grid_columnconfigure(0, weight=1)

        tk.Label(pf, text="Perfil / Instancia", bg=CARD_BG, fg=TEXT_SEC,
                 font=("Segoe UI Variable Text", 9)).pack(anchor="w", pady=(0, 7))

        self._profile_var = tk.StringVar()
        self._profile_combo = ttk.Combobox(pf, textvariable=self._profile_var,
                                           state="readonly",
                                           font=("Segoe UI Variable Text", 11))
        self._profile_combo.pack(fill="x", ipady=7)
        self._profile_combo.bind("<<ComboboxSelected>>", self._on_profile_select)

    # ── Barra de progreso ────────────────────────────────────────────────────
    def _build_progress_area(self, m):
        self._pbar_frame = tk.Frame(m, bg=CARD_BG, padx=28, pady=18)

        hf = tk.Frame(self._pbar_frame, bg=CARD_BG)
        hf.pack(fill="x", pady=(0, 10))

        self._pbar_lbl = tk.Label(hf, text="", bg=CARD_BG, fg=TEXT_PRI,
                                   font=("Segoe UI Variable Text", 10, "bold"))
        self._pbar_lbl.pack(side="left")

        self._pbar_pct = tk.Label(hf, text="", bg=CARD_BG, fg=GREEN,
                                   font=("Segoe UI Variable Text", 10, "bold"))
        self._pbar_pct.pack(side="right")

        self._pbar = ttk.Progressbar(self._pbar_frame,
                                      style="Green.Horizontal.TProgressbar",
                                      mode="determinate")
        self._pbar.pack(fill="x")

    # ── Versiones ────────────────────────────────────────────────────────────
    def _build_versions_card(self, m):
        wrapper = tk.Frame(m, bg=BG, padx=40)
        wrapper.grid(row=4, column=0, sticky="ew", pady=(16, 40))
        wrapper.grid_columnconfigure(0, weight=1)

        card = tk.Frame(wrapper, bg=CARD_BG, padx=28, pady=24)
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        tk.Label(card, text="Versiones de Minecraft",
                 bg=CARD_BG, fg=TEXT_PRI,
                 font=("Segoe UI Variable Display", 14, "bold")).grid(
                     row=0, column=0, sticky="w", pady=(0, 18))

        ir = tk.Frame(card, bg=CARD_BG)
        ir.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        self._version_var = tk.StringVar()
        self._version_combo = ttk.Combobox(ir, textvariable=self._version_var,
                                           state="readonly",
                                           font=("Segoe UI Variable Text", 10),
                                           width=22)
        self._version_combo.pack(side="left", ipady=7)
        _btn_primary(ir, "  Instalar versión",
                     self._on_install_version).pack(side="left", padx=(12, 0))

        cols = ("Versión", "Estado")
        self._ver_tree = ttk.Treeview(card, columns=cols, show="headings", height=5)
        self._ver_tree.heading("Versión", text="Versión instalada")
        self._ver_tree.heading("Estado",  text="Estado")
        self._ver_tree.column("Versión", width=300)
        self._ver_tree.column("Estado",  width=150)
        self._ver_tree.grid(row=2, column=0, sticky="ew")

        vsb2 = ttk.Scrollbar(card, orient="vertical", command=self._ver_tree.yview)
        vsb2.grid(row=2, column=1, sticky="ns")
        self._ver_tree.configure(yscrollcommand=vsb2.set)

    # ── Panel derecho ────────────────────────────────────────────────────────
    def _build_right_panel(self, m):
        right = tk.Frame(m, bg=BG)
        right.grid(row=1, column=1, rowspan=4, sticky="nsew",
                   padx=(0, 40), pady=(28, 40))
        right.grid_columnconfigure(0, weight=1)

        self._stat_cards = []
        stats = [
            ("📦", "Versiones\ninstaladas", "0", GREEN),
            ("👤", "Perfiles\ncreados",     "0", "#3d8ff5"),
            ("🧩", "Mods totales",          "0", "#ffa502"),
        ]
        for i, (icon, label, val, color) in enumerate(stats):
            sc = tk.Frame(right, bg=CARD_BG, padx=20, pady=18)
            sc.grid(row=i, column=0, sticky="ew", pady=(0, 12))
            sc.grid_columnconfigure(1, weight=1)
            tk.Label(sc, text=icon, bg=CARD_BG,
                     font=("Segoe UI", 22)).grid(row=0, column=0, rowspan=2,
                                                  padx=(0, 14), sticky="w")
            val_lbl = tk.Label(sc, text=val, bg=CARD_BG, fg=color,
                               font=("Segoe UI Variable Display", 24, "bold"))
            val_lbl.grid(row=0, column=1, sticky="w")
            tk.Label(sc, text=label, bg=CARD_BG, fg=TEXT_SEC,
                     font=("Segoe UI Variable Text", 9)).grid(
                         row=1, column=1, sticky="w")
            self._stat_cards.append(val_lbl)

        disc = tk.Frame(right, bg=CARD_BG, padx=20, pady=20)
        disc.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        disc.grid_columnconfigure(0, weight=1)
        tk.Label(disc, text="Descubrir mods", bg=CARD_BG, fg=TEXT_PRI,
                 font=("Segoe UI Variable Display", 13, "bold")).grid(
                     row=0, column=0, sticky="w")
        tk.Label(disc, text="Busca mods y modpacks en Modrinth",
                 bg=CARD_BG, fg=TEXT_SEC,
                 font=("Segoe UI Variable Text", 9)).grid(
                     row=1, column=0, sticky="w", pady=(4, 14))
        _btn_ghost(disc, "Explorar  →",
                   lambda: self.app._show_view("discover"), small=True).grid(
                       row=2, column=0, sticky="w")

        prof = tk.Frame(right, bg=CARD_BG, padx=20, pady=20)
        prof.grid(row=4, column=0, sticky="ew")
        prof.grid_columnconfigure(0, weight=1)
        tk.Label(prof, text="Gestionar perfiles", bg=CARD_BG, fg=TEXT_PRI,
                 font=("Segoe UI Variable Display", 13, "bold")).grid(
                     row=0, column=0, sticky="w")
        tk.Label(prof, text="Crea y configura instancias",
                 bg=CARD_BG, fg=TEXT_SEC,
                 font=("Segoe UI Variable Text", 9)).grid(
                     row=1, column=0, sticky="w", pady=(4, 14))
        _btn_ghost(prof, "Ir a perfiles  →",
                   lambda: self.app._show_view("library"), small=True).grid(
                       row=2, column=0, sticky="w")

    # ── on_show ──────────────────────────────────────────────────────────────
    def on_show(self):
        self._refresh_accounts()
        self._refresh_profiles()
        self._refresh_versions()
        self._refresh_installed()
        self._refresh_stats()

    def _refresh_accounts(self):
        accounts = self.app.account_manager.get_all_accounts()
        if not accounts:
            self._account_combo.pack_forget()
            self._no_account_lbl.pack(fill="x", pady=(0, 4))
            self._account_var.set("")
            return
        self._no_account_lbl.pack_forget()
        self._account_combo.pack(fill="x", ipady=6)
        names = [a.username for a in accounts]
        self._account_combo["values"] = names
        active = self.app.account_manager.get_active_account()
        if active and active.username in names:
            self._account_var.set(active.username)
        elif names:
            self._account_var.set(names[0])

    def _on_account_select(self):
        username = self._account_var.get()
        accounts = self.app.account_manager.get_all_accounts()
        account = next((a for a in accounts if a.username == username), None)
        if account:
            try:
                self.app.account_manager.set_active_account(account.id)
            except Exception:
                pass

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
            self._ver_tree.insert("", "end", values=(v, "✓  Instalada"),
                                  tags=("ok",))
        self._ver_tree.tag_configure("ok", foreground=GREEN)
        if not installed:
            self._ver_tree.insert("", "end",
                                  values=("Sin versiones instaladas", "—"))

    def _refresh_stats(self):
        try:
            installed = len(self.app.version_manager.get_installed_version_ids())
            profiles  = len(self.app.profile_manager.get_all_profiles())
            self._stat_cards[0].configure(text=str(installed))
            self._stat_cards[1].configure(text=str(profiles))
        except Exception:
            pass

    # ── Progreso ─────────────────────────────────────────────────────────────
    def _show_progress(self, visible):
        if visible:
            self._pbar_frame.grid(row=3, column=0, sticky="ew",
                                   padx=40, pady=(0, 0))
        else:
            self._pbar_frame.grid_remove()

    # ── Instalación ──────────────────────────────────────────────────────────
    def _on_install_version(self):
        vid = self._version_var.get()
        if not vid:
            messagebox.showwarning("Aviso", "Selecciona una versión.")
            return
        self._show_progress(True)
        self._pbar_lbl.configure(text=f"Instalando {vid}...")
        self._pbar_pct.configure(text="0%")
        self._pbar["value"] = 0
        self._launch_btn.configure(state="disabled")

        def run():
            try:
                def cb(step, cur, total):
                    if total > 0:
                        pct = cur / total * 100
                        self.after(0, lambda: (
                            self._pbar.__setitem__("value", pct),
                            self._pbar_lbl.configure(text=step),
                            self._pbar_pct.configure(text=f"{pct:.0f}%")))
                self.app.version_manager.install_version(vid, cb)
                self.after(0, self._install_done)
            except Exception as ex:
                self.after(0, lambda: self._install_error(str(ex)))
        threading.Thread(target=run, daemon=True).start()

    def _install_done(self):
        self._pbar["value"] = 100
        self._pbar_pct.configure(text="100%")
        self._pbar_lbl.configure(text="✓  Instalación completada")
        self._launch_btn.configure(state="normal")
        self._refresh_installed()
        self._refresh_stats()
        self.after(2500, lambda: self._show_progress(False))

    def _install_error(self, err):
        self._show_progress(False)
        self._launch_btn.configure(state="normal")
        messagebox.showerror("Error de instalación", err)

    # ── Lanzamiento ──────────────────────────────────────────────────────────
    def _on_launch(self):
        accounts = self.app.account_manager.get_all_accounts()
        if not accounts:
            if messagebox.askyesno("Sin cuenta",
                                   "No tienes ninguna cuenta creada.\n"
                                   "¿Ir a 'Cuentas' para crear una?"):
                self.app._show_view("accounts")
            return

        username = self._account_var.get()
        if not username:
            messagebox.showwarning("Aviso", "Selecciona una cuenta.")
            return

        profile_name = self._profile_var.get()
        if not profile_name:
            messagebox.showwarning("Aviso", "Selecciona un perfil.")
            return

        account = next((a for a in accounts if a.username == username), None)
        if not account:
            messagebox.showerror("Error", "Cuenta no encontrada.")
            return

        profile = self.app.profile_manager.get_profile_by_name(profile_name)
        if not profile:
            messagebox.showerror("Error", f"Perfil '{profile_name}' no encontrado.")
            return

        try:
            session = self.app.auth_service.create_offline_session(account.username)
            version_data = self.app.version_manager.get_version_data(
                profile.version_id)
        except Exception as ex:
            messagebox.showerror("Error", str(ex))
            return

        self.app.account_manager.set_active_account(account.id)

        try:
            process = self.app.launcher_engine.launch(
                profile, session, version_data,
                on_output=lambda l: log.info(f"[MC] {l}"))
            self.app.settings.last_profile = profile_name
            self._launch_btn.configure(state="disabled", text="▶   JUGANDO...")

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
                    state="normal", text="▶   JUGAR"))
            threading.Thread(target=wait, daemon=True).start()
        except Exception as ex:
            messagebox.showerror("Error al lanzar", str(ex))