"""library_view.py — Biblioteca de instancias instaladas"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading

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


def _btn(parent, text, command, primary=True, small=False):
    bg = GREEN if primary else CARD2_BG
    fg = "#0a0a0a" if primary else TEXT_PRI
    abg = GREEN_DIM if primary else BORDER
    f = ("Segoe UI", 9 if small else 10, "bold" if primary else "normal")
    return tk.Button(parent, text=text, bg=bg, fg=fg,
                     activebackground=abg, activeforeground=fg,
                     relief="flat", font=f,
                     padx=10 if small else 16, pady=5 if small else 8,
                     cursor="hand2", command=command)


class LibraryView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build()

    def _build(self):
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        sf = tk.Frame(canvas, bg=BG)
        sf.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=sf, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind("<MouseWheel>",
            lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        self._sf = sf
        self._sf.grid_columnconfigure(0, weight=1)

        # Header
        hdr = tk.Frame(sf, bg=BG, padx=40, pady=32)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        tk.Label(hdr, text="Biblioteca", bg=BG, fg=TEXT_PRI,
                 font=("Segoe UI", 24, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(hdr, text="Tus instancias y versiones instaladas",
                 bg=BG, fg=TEXT_SEC, font=("Segoe UI", 11)).grid(
                     row=1, column=0, sticky="w", pady=(4, 0))
        _btn(hdr, "+ Nueva instancia",
             lambda: self.app._show_view("profiles")).grid(
                 row=0, column=1, sticky="e")

        self._cards_frame = tk.Frame(sf, bg=BG, padx=40)
        self._cards_frame.grid(row=1, column=0, sticky="ew")
        self._cards_frame.grid_columnconfigure(0, weight=1)

    def on_show(self):
        for w in self._cards_frame.winfo_children():
            w.destroy()
        profiles = self.app.profile_manager.get_all_profiles()
        if not profiles:
            tk.Label(self._cards_frame,
                     text="No tienes instancias aún.\nCrea una en la sección Perfiles.",
                     bg=BG, fg=TEXT_DIM, font=("Segoe UI", 12),
                     justify="center").pack(pady=60)
            return
        for p in profiles:
            self._make_instance_card(p)

    def _make_instance_card(self, profile):
        card = tk.Frame(self._cards_frame, bg=CARD_BG, padx=28, pady=22)
        card.pack(fill="x", pady=(0, 12))
        card.grid_columnconfigure(1, weight=1)

        # Icono
        ico = tk.Frame(card, bg=INPUT_BG, width=60, height=60)
        ico.grid(row=0, column=0, rowspan=3, sticky="nw", padx=(0, 22))
        ico.grid_propagate(False)
        tk.Label(ico, text="🎮", bg=INPUT_BG,
                 font=("Segoe UI", 24)).place(relx=0.5, rely=0.5, anchor="center")

        # Info
        tk.Label(card, text=profile.name, bg=CARD_BG, fg=TEXT_PRI,
                 font=("Segoe UI", 13, "bold")).grid(row=0, column=1, sticky="w")
        tk.Label(card, text=f"Minecraft {profile.version_id}  ·  {profile.ram_mb} MB RAM",
                 bg=CARD_BG, fg=TEXT_SEC, font=("Segoe UI", 10)).grid(
                     row=1, column=1, sticky="w", pady=(2, 0))
        tk.Label(card, text=f"Carpeta: {profile.game_dir}",
                 bg=CARD_BG, fg=TEXT_DIM, font=("Segoe UI", 8)).grid(
                     row=2, column=1, sticky="w", pady=(2, 0))

        # Botones
        btns = tk.Frame(card, bg=CARD_BG)
        btns.grid(row=0, column=2, rowspan=3, sticky="e", padx=(16, 0))
        _btn(btns, "▶  Jugar",
             lambda p=profile: self._launch(p), small=True).pack(pady=(0, 6))
        _btn(btns, "Editar",
             lambda: self.app._show_view("profiles"),
             primary=False, small=True).pack()

    def _launch(self, profile):
        username = "Player"
        try:
            session = self.app.auth_service.create_offline_session(username)
            vd = self.app.version_manager.get_version_data(profile.version_id)
            self.app.launcher_engine.launch(profile, session, vd)
        except Exception as ex:
            messagebox.showerror("Error al lanzar", str(ex))
