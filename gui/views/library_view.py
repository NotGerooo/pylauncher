import tkinter as tk
from tkinter import ttk, messagebox
import threading
from utils.logger import get_logger

log = get_logger()


class LibraryView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg="#1a1a2e")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build()

    def _build(self):
        main = tk.Frame(self, bg="#1a1a2e", padx=32, pady=24)
        main.grid(row=0, column=0, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        # ── Header ──────────────────────────────────────────────────────────
        header = tk.Frame(main, bg="#1a1a2e")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        tk.Label(
            header,
            text="Biblioteca",
            bg="#1a1a2e",
            fg="#ffffff",
            font=("Segoe UI", 18, "bold"),
        ).grid(row=0, column=0, sticky="w")

        tk.Label(
            header,
            text="Tus instancias de Minecraft",
            bg="#1a1a2e",
            fg="#a0a0b0",
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        ttk.Button(
            header,
            text="+ Nueva Instancia",
            style="Primary.TButton",
            command=self._open_create_dialog,
        ).grid(row=0, column=1, rowspan=2, sticky="e", padx=(16, 0))

        # ── Separador ───────────────────────────────────────────────────────
        tk.Frame(main, bg="#0f3460", height=1).grid(
            row=1, column=0, sticky="ew", pady=(16, 16)
        )

        # ── Canvas con scroll para las tarjetas ─────────────────────────────
        canvas_frame = tk.Frame(main, bg="#1a1a2e")
        canvas_frame.grid(row=2, column=0, sticky="nsew")
        canvas_frame.grid_columnconfigure(0, weight=1)
        canvas_frame.grid_rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(canvas_frame, bg="#1a1a2e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            canvas_frame, orient="vertical", command=self._canvas.yview
        )
        self._canvas.configure(yscrollcommand=scrollbar.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self._cards_frame = tk.Frame(self._canvas, bg="#1a1a2e")
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._cards_frame, anchor="nw"
        )

        self._cards_frame.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._cards_frame.bind("<MouseWheel>", self._on_mousewheel)

        # ── Barra de estado ──────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="")
        tk.Label(
            main,
            textvariable=self._status_var,
            bg="#1a1a2e",
            fg="#a0a0b0",
            font=("Segoe UI", 9),
        ).grid(row=3, column=0, sticky="w", pady=(8, 0))

    # ── Scroll helpers ───────────────────────────────────────────────────────
    def _on_frame_configure(self, event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ── Lifecycle ────────────────────────────────────────────────────────────
    def on_show(self):
        self._refresh()

    def _refresh(self):
        for widget in self._cards_frame.winfo_children():
            widget.destroy()

        profiles = self.app.profile_manager.get_all_profiles()

        if not profiles:
            self._show_empty_state()
            self._status_var.set("")
            return

        self._status_var.set(f"{len(profiles)} instancia(s)")

        for i, profile in enumerate(profiles):
            self._build_profile_card(profile, i)

    def _show_empty_state(self):
        empty = tk.Frame(self._cards_frame, bg="#1a1a2e")
        empty.pack(expand=True, pady=60)

        tk.Label(
            empty,
            text="📦",
            bg="#1a1a2e",
            fg="#a0a0b0",
            font=("Segoe UI", 36),
        ).pack()

        tk.Label(
            empty,
            text="No tienes instancias creadas",
            bg="#1a1a2e",
            fg="#a0a0b0",
            font=("Segoe UI", 13),
        ).pack(pady=(8, 4))

        tk.Label(
            empty,
            text="Crea tu primera instancia con el botón '+ Nueva Instancia'",
            bg="#1a1a2e",
            fg="#555577",
            font=("Segoe UI", 10),
        ).pack()

        ttk.Button(
            empty,
            text="+ Nueva Instancia",
            style="Primary.TButton",
            command=self._open_create_dialog,
        ).pack(pady=(20, 0))

    def _build_profile_card(self, profile, index):
        card = tk.Frame(
            self._cards_frame,
            bg="#16213e",
            padx=20,
            pady=16,
            cursor="hand2",
        )
        card.pack(fill="x", pady=(0, 10))
        card.grid_columnconfigure(1, weight=1)

        # Icono
        icon_frame = tk.Frame(card, bg="#0f3460", width=52, height=52)
        icon_frame.grid(row=0, column=0, rowspan=3, sticky="w", padx=(0, 16))
        icon_frame.pack_propagate(False)
        tk.Label(
            icon_frame,
            text="⛏",
            bg="#0f3460",
            fg="#e94560",
            font=("Segoe UI", 22),
        ).place(relx=0.5, rely=0.5, anchor="center")

        # Nombre
        tk.Label(
            card,
            text=profile.name,
            bg="#16213e",
            fg="#ffffff",
            font=("Segoe UI", 13, "bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="ew")

        # Info
        info_parts = [f"Minecraft {profile.version_id}", f"RAM: {profile.ram_mb} MB"]
        tk.Label(
            card,
            text="  •  ".join(info_parts),
            bg="#16213e",
            fg="#a0a0b0",
            font=("Segoe UI", 9),
            anchor="w",
        ).grid(row=1, column=1, sticky="ew", pady=(2, 0))

        # Última vez jugado
        last = profile.last_used[:10] if profile.last_used else "—"
        tk.Label(
            card,
            text=f"Última vez: {last}",
            bg="#16213e",
            fg="#555577",
            font=("Segoe UI", 8),
            anchor="w",
        ).grid(row=2, column=1, sticky="ew")

        # Botones de acción
        btn_frame = tk.Frame(card, bg="#16213e")
        btn_frame.grid(row=0, column=2, rowspan=3, sticky="e", padx=(16, 0))

        ttk.Button(
            btn_frame,
            text="▶ Jugar",
            style="Primary.TButton",
            command=lambda p=profile: self._on_launch(p),
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            btn_frame,
            text="✏ Editar",
            command=lambda p=profile: self._open_edit_dialog(p),
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            btn_frame,
            text="🗑 Eliminar",
            command=lambda p=profile: self._on_delete(p),
        ).pack(side="left")

        # Hover effect
        def on_enter(e, c=card):
            c.configure(bg="#1e2d4a")
            for w in c.winfo_children():
                try:
                    w.configure(bg="#1e2d4a")
                except Exception:
                    pass

        def on_leave(e, c=card):
            c.configure(bg="#16213e")
            for w in c.winfo_children():
                try:
                    w.configure(bg="#16213e")
                except Exception:
                    pass

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

    # ── Acciones ─────────────────────────────────────────────────────────────
    def _on_launch(self, profile):
        # Pide usuario si no hay sesión guardada
        dialog = _UsernameDialog(self, self.app, profile)
        self.wait_window(dialog)

    def _on_delete(self, profile):
        if not messagebox.askyesno(
            "Eliminar instancia",
            f"¿Eliminar la instancia '{profile.name}'?\nEsto no borra los archivos del juego.",
        ):
            return
        try:
            self.app.profile_manager.delete_profile(profile.id)
            self._refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _open_create_dialog(self):
        dialog = _InstanceDialog(self, self.app, profile=None, on_save=self._refresh)
        self.wait_window(dialog)

    def _open_edit_dialog(self, profile):
        dialog = _InstanceDialog(self, self.app, profile=profile, on_save=self._refresh)
        self.wait_window(dialog)


# ── Diálogo crear / editar instancia ────────────────────────────────────────

class _InstanceDialog(tk.Toplevel):
    def __init__(self, parent, app, profile, on_save):
        super().__init__(parent)
        self.app = app
        self.profile = profile
        self.on_save = on_save

        title = "Editar instancia" if profile else "Nueva instancia"
        self.title(title)
        self.geometry("420x300")
        self.resizable(False, False)
        self.configure(bg="#1a1a2e")
        self.grab_set()

        self._build()
        if profile:
            self._load_profile(profile)

    def _build(self):
        main = tk.Frame(self, bg="#1a1a2e", padx=28, pady=24)
        main.pack(fill="both", expand=True)
        main.grid_columnconfigure(0, weight=1)

        tk.Label(
            main,
            text="Nueva instancia" if not self.profile else "Editar instancia",
            bg="#1a1a2e",
            fg="#ffffff",
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 20))

        # Nombre
        tk.Label(main, text="Nombre", bg="#1a1a2e", fg="#a0a0b0",
                 font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w")
        self._name_var = tk.StringVar()
        tk.Entry(
            main,
            textvariable=self._name_var,
            bg="#0f3460",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            font=("Segoe UI", 11),
        ).grid(row=2, column=0, sticky="ew", ipady=7, pady=(4, 14))

        # Versión
        tk.Label(main, text="Versión de Minecraft", bg="#1a1a2e", fg="#a0a0b0",
                 font=("Segoe UI", 9)).grid(row=3, column=0, sticky="w")
        self._version_var = tk.StringVar()
        self._version_combo = ttk.Combobox(
            main,
            textvariable=self._version_var,
            state="readonly",
            font=("Segoe UI", 10),
        )
        self._version_combo.grid(row=4, column=0, sticky="ew", ipady=5, pady=(4, 14))
        self._load_versions()

        # RAM
        tk.Label(main, text="RAM (MB)", bg="#1a1a2e", fg="#a0a0b0",
                 font=("Segoe UI", 9)).grid(row=5, column=0, sticky="w")
        self._ram_var = tk.StringVar(value="2048")
        ttk.Combobox(
            main,
            textvariable=self._ram_var,
            values=["1024", "2048", "3072", "4096", "6144", "8192"],
            state="readonly",
            font=("Segoe UI", 10),
        ).grid(row=6, column=0, sticky="ew", ipady=5, pady=(4, 20))

        # Botones
        btn_row = tk.Frame(main, bg="#1a1a2e")
        btn_row.grid(row=7, column=0, sticky="ew")
        btn_row.grid_columnconfigure(0, weight=1)

        ttk.Button(btn_row, text="Cancelar", command=self.destroy).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(
            btn_row,
            text="Guardar",
            style="Primary.TButton",
            command=self._on_save,
        ).grid(row=0, column=1, sticky="e")

    def _load_versions(self):
        installed = self.app.version_manager.get_installed_version_ids()
        self._version_combo["values"] = installed
        if installed:
            self._version_var.set(installed[0])

    def _load_profile(self, profile):
        self._name_var.set(profile.name)
        self._version_var.set(profile.version_id)
        self._ram_var.set(str(profile.ram_mb))

    def _on_save(self):
        name = self._name_var.get().strip()
        version = self._version_var.get().strip()
        ram_str = self._ram_var.get().strip()

        if not name:
            messagebox.showwarning("Aviso", "El nombre no puede estar vacío.", parent=self)
            return
        if not version:
            messagebox.showwarning("Aviso", "Selecciona una versión.", parent=self)
            return

        try:
            ram_mb = int(ram_str) if ram_str else 2048
        except ValueError:
            ram_mb = 2048

        try:
            if self.profile:
                self.app.profile_manager.update_profile(
                    self.profile.id, name=name, version_id=version, ram_mb=ram_mb
                )
            else:
                self.app.profile_manager.create_profile(name, version, ram_mb=ram_mb)
            self.on_save()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)


# ── Diálogo lanzar juego ─────────────────────────────────────────────────────

class _UsernameDialog(tk.Toplevel):
    def __init__(self, parent, app, profile):
        super().__init__(parent)
        self.app = app
        self.profile = profile

        self.title("Lanzar juego")
        self.geometry("340x180")
        self.resizable(False, False)
        self.configure(bg="#1a1a2e")
        self.grab_set()

        self._build()

    def _build(self):
        main = tk.Frame(self, bg="#1a1a2e", padx=28, pady=24)
        main.pack(fill="both", expand=True)
        main.grid_columnconfigure(0, weight=1)

        tk.Label(
            main,
            text=f"Lanzar  {self.profile.name}",
            bg="#1a1a2e",
            fg="#ffffff",
            font=("Segoe UI", 13, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 16))

        tk.Label(main, text="Nombre de usuario", bg="#1a1a2e", fg="#a0a0b0",
                 font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w")

        self._username_var = tk.StringVar(value=self.app.settings.last_profile or "Player")
        tk.Entry(
            main,
            textvariable=self._username_var,
            bg="#0f3460",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            font=("Segoe UI", 11),
        ).grid(row=2, column=0, columnspan=2, sticky="ew", ipady=7, pady=(4, 20))

        btn_row = tk.Frame(main, bg="#1a1a2e")
        btn_row.grid(row=3, column=0, columnspan=2, sticky="ew")
        btn_row.grid_columnconfigure(0, weight=1)

        ttk.Button(btn_row, text="Cancelar", command=self.destroy).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(
            btn_row,
            text="▶ Jugar",
            style="Primary.TButton",
            command=self._on_launch,
        ).grid(row=0, column=1, sticky="e")

    def _on_launch(self):
        username = self._username_var.get().strip()
        if not username:
            messagebox.showwarning("Aviso", "Ingresa tu nombre.", parent=self)
            return
        try:
            session = self.app.auth_service.create_offline_session(username)
            version_data = self.app.version_manager.get_version_data(
                self.profile.version_id
            )
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)
            return

        from utils.logger import get_logger
        log = get_logger()

        try:
            def on_output(line):
                log.info(f"[MC] {line}")

            process = self.app.launcher_engine.launch(
                self.profile, session, version_data, on_output=on_output
            )
            self.app.settings.last_profile = self.profile.name
            self.destroy()

            import threading

            def wait_process():
                process.wait()
                rc = process.returncode
                log.info(f"Minecraft cerrado con código: {rc}")
                if rc != 0:
                    self.app.after(
                        0,
                        lambda: messagebox.showerror(
                            "Minecraft cerrado",
                            f"El juego cerró con error (código {rc}).\n"
                            "Revisa los logs para más detalles.",
                        ),
                    )

            threading.Thread(target=wait_process, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error al lanzar", str(e), parent=self)