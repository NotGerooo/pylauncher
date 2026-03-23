"""profiles_view.py — Gestión de perfiles/instancias"""
import tkinter as tk
from tkinter import ttk, messagebox
from utils.logger import get_logger
log = get_logger()

BG        = "#16171a"
BG_EL     = "#1c1d21"
CARD_BG   = "#222327"
CARD2_BG  = "#28292e"
INPUT_BG  = "#1a1b1f"
BORDER    = "#2e2f35"
BORDER_BRIGHT = "#3d3e45"
GREEN     = "#1bd96a"
GREEN_DIM = "#13a050"
GREEN_SUB = "#0f2318"
TEXT_PRI  = "#f0f1f3"
TEXT_SEC  = "#8b8e96"
TEXT_DIM  = "#4a4d55"
TEXT_INV  = "#0a0b0d"
NAV_ACT   = "#0f2318"
RED       = "#ff4757"
ACCENT    = "#1bd96a"
ACCENT_DIM= "#13a050"
TEXT      = "#f0f1f3"
TEXT_BRIGHT="#ffffff"
BG_CARD   = "#222327"
BG_SIDEBAR= "#0e0f11"
BG_INPUT  = "#1a1b1f"
BG_HOVER  = "#28292e"
SEL_BG    = "#0f2318"
DIALOG_BG = "#1c1d21"

LOADERS = ["Vanilla", "Fabric", "Forge", "NeoForge", "Quilt", "OptiFine"]


def _btn(parent, text, cmd, primary=True, small=False):
    bg  = GREEN if primary else CARD2_BG
    fg  = "#0a0a0a" if primary else TEXT_PRI
    abg = GREEN_DIM if primary else BORDER
    f   = ("Segoe UI", 9 if small else 10, "bold" if primary else "normal")
    return tk.Button(parent, text=text, bg=bg, fg=fg,
                     activebackground=abg, activeforeground=fg,
                     relief="flat", font=f,
                     padx=10 if small else 16, pady=5 if small else 8,
                     cursor="hand2", command=cmd)


class ProfileDialog(tk.Toplevel):
    """
    Ventana modal flotante para crear o editar un perfil.
    Diseño inspirado en launchers modernos:
    - Loader como botones pill seleccionables
    - Versión del loader aparece solo si no es Vanilla
    - Versión de MC como dropdown
    - Botones Cancelar / Crear al fondo
    """

    def __init__(self, parent, app, profile=None, on_save=None):
        super().__init__(parent)
        self.app         = app
        self.profile     = profile
        self.on_save     = on_save
        self._loader_var = tk.StringVar(value="Vanilla")

        # ── Ventana ───────────────────────────────────────────────────────────
        self.title("Crear perfil" if not profile else "Editar perfil")
        self.configure(bg=DIALOG_BG)
        self.resizable(False, False)
        self.grab_set()
        self.focus_set()

        self._build()

        # Forzar tamaño y centrar DESPUÉS de construir
        self.update_idletasks()
        self.geometry("480x620")
        self._center(parent)

        if profile:
            self._fill(profile)

    # ── Construcción ──────────────────────────────────────────────────────────

    def _build(self):
        # Canvas + scrollbar para que nunca se corte nada
        canvas = tk.Canvas(self, bg=DIALOG_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._inner = tk.Frame(canvas, bg=DIALOG_BG)
        canvas_window = canvas.create_window((0, 0), window=self._inner,
                                             anchor="nw")

        def _on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(e):
            canvas.itemconfig(canvas_window, width=e.width)

        self._inner.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Scroll con rueda del mouse
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        self._build_content(self._inner)

    def _build_content(self, root):
        root.grid_columnconfigure(0, weight=1)
        p = {"padx": 32}

        # ── Título ────────────────────────────────────────────────────────────
        title_frame = tk.Frame(root, bg=DIALOG_BG)
        title_frame.grid(row=0, column=0, sticky="ew", padx=32,
                         pady=(28, 24))
        title_frame.grid_columnconfigure(0, weight=1)
        tk.Label(title_frame,
                 text="Crear perfil" if not self.profile else "Editar perfil",
                 bg=DIALOG_BG, fg=TEXT_PRI,
                 font=("Segoe UI Variable Display", 15, "bold")).grid(row=0, column=0, sticky="w")

        # ── Separador ─────────────────────────────────────────────────────────
        tk.Frame(root, bg=BORDER, height=1).grid(
            row=1, column=0, sticky="ew", padx=0, pady=(0, 24))

        # ── Nombre ────────────────────────────────────────────────────────────
        self._section_label(root, 2, "Nombre")
        self._name_var = tk.StringVar()
        entry = tk.Entry(root, textvariable=self._name_var,
                         bg=INPUT_BG, fg=TEXT_PRI,
                         insertbackground=TEXT_PRI, relief="flat",
                         font=("Segoe UI Variable Text", 10),
                         highlightthickness=1,
                         highlightbackground=BORDER,
                         highlightcolor=GREEN)
        entry.grid(row=3, column=0, sticky="ew", ipady=10,
                   padx=32, pady=(6, 20))
        # Placeholder
        self._add_placeholder(entry, self._name_var,
                              "Escribe un nombre para tu perfil...")

        # ── Loader ────────────────────────────────────────────────────────────
        self._section_label(root, 4, "Loader")
        loader_frame = tk.Frame(root, bg=DIALOG_BG)
        loader_frame.grid(row=5, column=0, sticky="ew", padx=32, pady=(8, 0))

        self._loader_btns = {}
        for i, loader in enumerate(LOADERS):
            btn = tk.Button(
                loader_frame, text=loader,
                bg=CARD2_BG, fg=TEXT_SEC,
                activebackground=BORDER, activeforeground=TEXT_PRI,
                relief="flat", font=("Segoe UI Variable Text", 9),
                padx=12, pady=7, cursor="hand2",
                command=lambda l=loader: self._select_loader(l)
            )
            btn.grid(row=0, column=i, padx=(0, 6), pady=4)
            self._loader_btns[loader] = btn

        # ── Versión del loader (oculta por defecto) ───────────────────────────
        self._lver_frame = tk.Frame(root, bg=DIALOG_BG)
        self._lver_frame.grid(row=6, column=0, sticky="ew",
                              padx=32, pady=(16, 0))
        self._lver_frame.grid_columnconfigure(0, weight=1)
        tk.Label(self._lver_frame, text="Versión del loader",
                 bg=DIALOG_BG, fg=TEXT_SEC,
                 font=("Segoe UI Variable Text", 9)).grid(row=0, column=0, sticky="w")
        self._lver_var = tk.StringVar()
        self._lver_combo = ttk.Combobox(self._lver_frame,
                                        textvariable=self._lver_var,
                                        state="readonly",
                                        font=("Segoe UI Variable Text", 10))
        self._lver_combo.grid(row=1, column=0, sticky="ew",
                              ipady=6, pady=(6, 0))
        self._lver_frame.grid_remove()  # Oculto hasta elegir loader

        # ── Versión de Minecraft ──────────────────────────────────────────────
        self._section_label(root, 7, "Versión de Minecraft")
        self._version_var = tk.StringVar()
        self._vcombo = ttk.Combobox(root, textvariable=self._version_var,
                                    state="readonly", font=("Segoe UI Variable Text", 10))
        self._vcombo.grid(row=8, column=0, sticky="ew",
                          ipady=6, padx=32, pady=(6, 20))
        self._vcombo.bind("<<ComboboxSelected>>", self._on_version_change)

        installed = self.app.version_manager.get_installed_version_ids()
        self._vcombo["values"] = installed
        if installed:
            self._version_var.set(installed[0])

        # ── RAM ───────────────────────────────────────────────────────────────
        self._section_label(root, 9, "RAM (MB)")
        self._ram_var = tk.StringVar(value="2048")
        ttk.Combobox(root, textvariable=self._ram_var,
                     values=["1024", "2048", "3072", "4096", "6144", "8192"],
                     state="readonly", font=("Segoe UI Variable Text", 10)).grid(
                         row=10, column=0, sticky="ew",
                         ipady=6, padx=32, pady=(6, 24))

        # ── Separador ─────────────────────────────────────────────────────────
        tk.Frame(root, bg=BORDER, height=1).grid(
            row=11, column=0, sticky="ew", pady=(0, 20))

        # ── Botones ───────────────────────────────────────────────────────────
        btn_frame = tk.Frame(root, bg=DIALOG_BG)
        btn_frame.grid(row=12, column=0, sticky="ew", padx=32, pady=(0, 28))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        tk.Button(btn_frame, text="✕  Cancelar",
                  bg=CARD2_BG, fg=TEXT_PRI,
                  activebackground=BORDER, activeforeground=TEXT_PRI,
                  relief="flat", font=("Segoe UI Variable Text", 10),
                  padx=16, pady=10, cursor="hand2",
                  command=self.destroy).grid(
                      row=0, column=0, sticky="ew", padx=(0, 8))

        tk.Button(btn_frame,
                  text="+ Crear" if not self.profile else "✓  Guardar",
                  bg=GREEN, fg="#0a0a0a",
                  activebackground=GREEN_DIM, activeforeground="#0a0a0a",
                  relief="flat", font=("Segoe UI Variable Text", 10, "bold"),
                  padx=16, pady=10, cursor="hand2",
                  command=self._on_save).grid(
                      row=0, column=1, sticky="ew")

        # Seleccionar Vanilla por defecto
        self._select_loader("Vanilla")

    # ── Helpers de construcción ───────────────────────────────────────────────

    def _section_label(self, parent, row, text):
        tk.Label(parent, text=text, bg=DIALOG_BG, fg=TEXT_PRI,
                 font=("Segoe UI Variable Text", 10, "bold")).grid(
                     row=row, column=0, sticky="w", padx=32, pady=(0, 0))

    def _add_placeholder(self, entry, var, placeholder):
        def on_focus_in(e):
            if var.get() == placeholder:
                var.set("")
                entry.configure(fg=TEXT_PRI)

        def on_focus_out(e):
            if not var.get():
                var.set(placeholder)
                entry.configure(fg=TEXT_DIM)

        var.set(placeholder)
        entry.configure(fg=TEXT_DIM)
        entry.bind("<FocusIn>",  on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

    # ── Lógica de loader ──────────────────────────────────────────────────────

    def _select_loader(self, loader: str):
        self._loader_var.set(loader)
        for name, btn in self._loader_btns.items():
            if name == loader:
                btn.configure(bg=GREEN, fg="#0a0a0a",
                               font=("Segoe UI Variable Text", 9, "bold"))
            else:
                btn.configure(bg=CARD2_BG, fg=TEXT_SEC,
                               font=("Segoe UI Variable Text", 9))

        if loader == "Vanilla":
            self._lver_frame.grid_remove()
        else:
            self._lver_frame.grid()
            self._load_loader_versions(loader)

    def _on_version_change(self, e=None):
        loader = self._loader_var.get()
        if loader != "Vanilla":
            self._load_loader_versions(loader)

    def _load_loader_versions(self, loader: str):
        mc_ver = self._version_var.get()
        if not mc_ver:
            return
        self._lver_combo["values"] = ["Cargando..."]
        self._lver_var.set("Cargando...")
        self.update_idletasks()
        try:
            from managers.loader_manager import LoaderManager
            lm       = LoaderManager(self.app.settings)
            versions = lm.get_available_versions(
                loader.lower(), mc_ver, stable_only=True)
            ver_list = [v.loader_ver for v in versions]
            if ver_list:
                self._lver_combo["values"] = ver_list
                self._lver_var.set(ver_list[0])
            else:
                self._lver_combo["values"] = []
                self._lver_var.set("")
                messagebox.showwarning(
                    "Sin versiones",
                    f"{loader} no tiene versiones para MC {mc_ver}.\n"
                    "Verifica tu conexión a internet.")
        except Exception as ex:
            self._lver_combo["values"] = []
            self._lver_var.set("")
            log.error(f"Error cargando versiones de {loader}: {ex}")

    # ── Guardar ───────────────────────────────────────────────────────────────

    def _on_save(self):
        name    = self._name_var.get().strip()
        version = self._version_var.get().strip()
        ram     = self._ram_var.get().strip()
        loader  = self._loader_var.get().lower()
        lver    = self._lver_var.get().strip()

        # Ignorar placeholder
        placeholders = ["escribe un nombre para tu perfil..."]
        if name.lower() in placeholders or not name:
            messagebox.showwarning("Aviso", "Escribe un nombre para el perfil.")
            return
        if not version:
            messagebox.showwarning("Aviso", "Selecciona una versión de Minecraft.")
            return

        try:
            ram_mb = int(ram) if ram else 2048
        except ValueError:
            ram_mb = 2048

        if loader != "vanilla" and lver in ("", "Cargando..."):
            lver = ""

        try:
            if self.profile:
                self.app.profile_manager.update_profile(
                    self.profile.id,
                    name=name, version_id=version, ram_mb=ram_mb)
                if loader != "vanilla":
                    self.app.profile_manager.update_loader(
                        self.profile.id, loader, lver)
            else:
                self.app.profile_manager.create_profile(
                    name, version,
                    ram_mb=ram_mb,
                    loader_type=loader,
                    loader_ver=lver)
            if self.on_save:
                self.on_save()
            self.destroy()
            messagebox.showinfo("✓ Listo", "Perfil guardado correctamente.")
        except Exception as ex:
            messagebox.showerror("Error", str(ex))

    # ── Rellenar al editar ────────────────────────────────────────────────────

    def _fill(self, profile):
        self._name_var.set(profile.name)
        self._version_var.set(profile.version_id)
        self._ram_var.set(str(profile.ram_mb))
        try:
            from managers.loader_manager import LoaderManager
            lm      = LoaderManager(self.app.settings)
            loaders = lm.get_installed_loaders(profile.game_dir)
            active  = next(
                (e for e in loaders
                 if e.get("mc_version") == profile.version_id
                 and e.get("loader_type") != "vanilla"), None)
            if active:
                name = active["loader_type"].capitalize()
                if name == "Neoforge":
                    name = "NeoForge"
                self._select_loader(name)
                self._lver_var.set(active.get("loader_ver", ""))
        except Exception:
            pass

    # ── Centrar ───────────────────────────────────────────────────────────────

    def _center(self, parent):
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width()  // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        w  = self.winfo_width()
        h  = self.winfo_height()
        self.geometry(f"480x620+{pw - w//2}+{ph - h//2}")


# ── Vista principal ───────────────────────────────────────────────────────────

class ProfilesView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build()

    def _build(self):
        main = tk.Frame(self, bg=BG, padx=40, pady=32)
        main.grid(row=0, column=0, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        # Header
        hdr = tk.Frame(main, bg=BG)
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 24))
        hdr.grid_columnconfigure(0, weight=1)
        tk.Label(hdr, text="Perfiles", bg=BG, fg=TEXT_PRI,
                 font=("Segoe UI Variable Display", 24, "bold")).grid(
                     row=0, column=0, sticky="w")
        tk.Label(hdr, text="Crea y administra tus instancias de Minecraft",
                 bg=BG, fg=TEXT_SEC,
                 font=("Segoe UI Variable Text", 11)).grid(
                     row=1, column=0, sticky="w", pady=(4, 0))
        _btn(hdr, "+ Nuevo perfil", self._open_create,
             small=True).grid(row=0, column=1, rowspan=2, sticky="e")

        # Tabla
        card = tk.Frame(main, bg=CARD_BG, padx=24, pady=24)
        card.grid(row=1, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        tk.Label(card, text="Mis perfiles", bg=CARD_BG, fg=TEXT_PRI,
                 font=("Segoe UI Variable Display", 13, "bold")).grid(
                     row=0, column=0, sticky="w", pady=(0, 16))

        cols = ("Nombre", "Versión", "Loader", "RAM")
        self._tree = ttk.Treeview(card, columns=cols,
                                  show="headings", height=16)
        for col in cols:
            self._tree.heading(col, text=col)
        self._tree.column("Nombre",  width=220)
        self._tree.column("Versión", width=120)
        self._tree.column("Loader",  width=110)
        self._tree.column("RAM",     width=90)
        self._tree.grid(row=1, column=0, sticky="nsew")
        self._tree.bind("<Double-1>", lambda e: self._open_edit())

        vsb = ttk.Scrollbar(card, orient="vertical",
                            command=self._tree.yview)
        vsb.grid(row=1, column=1, sticky="ns")
        self._tree.configure(yscrollcommand=vsb.set)

        bf = tk.Frame(card, bg=CARD_BG)
        bf.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        _btn(bf, "✎  Editar", self._open_edit,
             primary=False, small=True).pack(side="left", padx=(0, 8))
        tk.Button(bf, text="✕  Eliminar",
                  bg="#3d1f1f", fg="#fa5252",
                  activebackground="#4a2424", relief="flat",
                  font=("Segoe UI Variable Text", 9), padx=12, pady=5,
                  cursor="hand2",
                  command=self._on_delete).pack(side="left")

    def on_show(self):
        self._refresh_list()

    def _refresh_list(self):
        self._tree.delete(*self._tree.get_children())
        for p in self.app.profile_manager.get_all_profiles():
            loader_label = "Vanilla"
            try:
                from managers.loader_manager import LoaderManager
                lm = LoaderManager(self.app.settings)
                loaders = lm.get_installed_loaders(p.game_dir)
                active = next(
                    (e for e in loaders
                     if e.get("mc_version") == p.version_id
                     and e.get("loader_type") != "vanilla"), None)
                if active:
                    loader_label = active["loader_type"].capitalize()
            except Exception:
                pass
            self._tree.insert("", "end", iid=p.id,
                values=(p.name, p.version_id, loader_label,
                        f"{p.ram_mb} MB"))

    def _open_create(self):
        ProfileDialog(self, self.app, on_save=self._refresh_list)

    def _open_edit(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecciona un perfil para editar.")
            return
        profile = self.app.profile_manager.get_profile(sel[0])
        if profile:
            ProfileDialog(self, self.app, profile=profile,
                          on_save=self._refresh_list)

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecciona un perfil.")
            return
        p = self.app.profile_manager.get_profile(sel[0])
        if not messagebox.askyesno("Confirmar", f"¿Eliminar '{p.name}'?"):
            return
        try:
            self.app.profile_manager.delete_profile(sel[0])
            self._refresh_list()
        except Exception as ex:
            messagebox.showerror("Error", str(ex))