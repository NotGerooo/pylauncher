"""
home_view.py — Vista de Inicio
Diseño premium + account_manager + panel derecho scrolleable con cuenta y noticias.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import urllib.request
import json
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


def _btn_primary(parent, text, command):
    return tk.Button(
        parent, text=text, command=command,
        bg=GREEN, fg=TEXT_INV,
        activebackground=GREEN_DIM, activeforeground=TEXT_INV,
        relief="flat", cursor="hand2",
        font=("Segoe UI Variable Text", 10, "bold"),
        padx=22, pady=10)


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
        self._skin_photo = None
        self._build()

    # ── Layout principal scrolleable ─────────────────────────────────────────
    def _build(self):
        # Canvas principal que hace scrolleable toda la vista
        self._main_canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self._main_vsb = ttk.Scrollbar(self, orient="vertical",
                                        command=self._main_canvas.yview)
        self._sf = tk.Frame(self._main_canvas, bg=BG)
        self._sf.bind("<Configure>", lambda e:
            self._main_canvas.configure(
                scrollregion=self._main_canvas.bbox("all")))
        self._win = self._main_canvas.create_window(
            (0, 0), window=self._sf, anchor="nw")
        self._main_canvas.configure(yscrollcommand=self._main_vsb.set)
        self._main_canvas.grid(row=0, column=0, sticky="nsew")
        self._main_vsb.grid(row=0, column=1, sticky="ns")
        self._main_canvas.bind("<Configure>", lambda e:
            self._main_canvas.itemconfig(self._win, width=e.width))

        # Scroll con rueda — desactivar cuando el cursor esté en el panel de noticias
        self._main_scroll_active = True

        def _main_scroll(e):
            if self._main_scroll_active:
                self._main_canvas.yview_scroll(-1*(e.delta//120), "units")

        self._main_canvas.bind("<MouseWheel>", _main_scroll)
        self._sf.bind("<MouseWheel>", _main_scroll)

        self._main_scroll_fn = _main_scroll

        m = self._sf
        # col 0 = contenido principal | col 1 = panel derecho fijo
        m.grid_columnconfigure(0, weight=1)
        m.grid_columnconfigure(1, minsize=290, weight=0)

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

        inner = tk.Frame(hero, bg=BG_EL, padx=44, pady=32)
        inner.pack(fill="x")
        inner.grid_columnconfigure(0, weight=1)

        badge = tk.Frame(inner, bg=GREEN_SUB, padx=10, pady=4)
        badge.grid(row=0, column=0, sticky="w", pady=(0, 10))
        tk.Label(badge, text="⚡  Gero's Launcher",
                 bg=GREEN_SUB, fg=GREEN,
                 font=("Segoe UI Variable Text", 9, "bold")).pack()

        tk.Label(inner, text="¡Bienvenido de vuelta!",
                 bg=BG_EL, fg=TEXT_PRI,
                 font=("Segoe UI Variable Display", 26, "bold")).grid(
                     row=1, column=0, sticky="w")
        tk.Label(inner,
                 text="Lanza Minecraft, gestiona mods y descubre contenido nuevo.",
                 bg=BG_EL, fg=TEXT_SEC,
                 font=("Segoe UI Variable Text", 11)).grid(
                     row=2, column=0, sticky="w", pady=(5, 0))

        tk.Frame(hero, bg=BORDER, height=1).pack(fill="x")

    # ── Launch card ──────────────────────────────────────────────────────────
    def _build_launch_card(self, m):
        wrapper = tk.Frame(m, bg=BG, padx=36, pady=0)
        wrapper.grid(row=1, column=0, sticky="ew", pady=(24, 0))
        wrapper.grid_columnconfigure(0, weight=1)

        card = tk.Frame(wrapper, bg=CARD_BG, padx=28, pady=22)
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        ico = tk.Frame(card, bg="#1a2e1e", width=64, height=64)
        ico.grid(row=0, column=0, rowspan=3, sticky="nw", padx=(0, 20))
        ico.grid_propagate(False)
        tk.Label(ico, text="🎮", bg="#1a2e1e",
                 font=("Segoe UI", 28)).place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(card, text="Lanzamiento rápido",
                 bg=CARD_BG, fg=TEXT_PRI,
                 font=("Segoe UI Variable Display", 15, "bold")).grid(
                     row=0, column=1, sticky="w")

        self._profile_label = tk.Label(card, text="Selecciona un perfil abajo",
                                        bg=CARD_BG, fg=TEXT_SEC,
                                        font=("Segoe UI Variable Text", 10))
        self._profile_label.grid(row=1, column=1, sticky="w", pady=(3, 12))

        self._launch_btn = _btn_primary(card, "▶   JUGAR", self._on_launch)
        self._launch_btn.grid(row=2, column=1, sticky="w")

    # ── Fila cuenta + perfil ─────────────────────────────────────────────────
    def _build_user_profile_row(self, m):
        wrapper = tk.Frame(m, bg=BG, padx=36)
        wrapper.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        wrapper.grid_columnconfigure(0, weight=1)
        wrapper.grid_columnconfigure(1, weight=1)

        # ── Campo cuenta ──────────────────────────────────────────────────
        uf = tk.Frame(wrapper, bg=CARD_BG, padx=20, pady=18)
        uf.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        uf.grid_columnconfigure(0, weight=1)

        tk.Label(uf, text="Usuario", bg=CARD_BG, fg=TEXT_SEC,
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

        # ── Campo perfil ──────────────────────────────────────────────────
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
        self._pbar_frame = tk.Frame(m, bg=CARD_BG, padx=28, pady=16)

        hf = tk.Frame(self._pbar_frame, bg=CARD_BG)
        hf.pack(fill="x", pady=(0, 8))
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
        wrapper = tk.Frame(m, bg=BG, padx=36)
        wrapper.grid(row=4, column=0, sticky="ew", pady=(14, 36))
        wrapper.grid_columnconfigure(0, weight=1)

        card = tk.Frame(wrapper, bg=CARD_BG, padx=28, pady=24)
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        tk.Label(card, text="Versiones de Minecraft",
                 bg=CARD_BG, fg=TEXT_PRI,
                 font=("Segoe UI Variable Display", 14, "bold")).grid(
                     row=0, column=0, sticky="w", pady=(0, 16))

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

    # ── Panel derecho ─────────────────────────────────────────────────────────
    def _build_right_panel(self, m):
        # Frame exterior que ocupa toda la altura del grid
        outer = tk.Frame(m, bg=BG)
        outer.grid(row=0, column=1, rowspan=6, sticky="nsew",
                   padx=(8, 32), pady=0)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(0, weight=1)

        # Canvas scrollable para TODO el panel derecho
        rp_canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        rp_canvas.grid(row=0, column=0, sticky="nsew")
        rp_vsb = ttk.Scrollbar(outer, orient="vertical",
                                command=rp_canvas.yview)
        rp_vsb.grid(row=0, column=1, sticky="ns")
        rp_canvas.configure(yscrollcommand=rp_vsb.set)

        rp_inner = tk.Frame(rp_canvas, bg=BG)
        rp_win = rp_canvas.create_window((0, 0), window=rp_inner, anchor="nw")

        rp_inner.bind("<Configure>", lambda e:
            rp_canvas.configure(scrollregion=rp_canvas.bbox("all")))
        rp_canvas.bind("<Configure>", lambda e:
            rp_canvas.itemconfig(rp_win, width=e.width))

        # Scroll solo cuando el cursor está sobre el panel derecho
        def _rp_enter(e):
            self._main_scroll_active = False
            rp_canvas.bind_all("<MouseWheel>",
                lambda ev: rp_canvas.yview_scroll(-1*(ev.delta//120), "units"))

        def _rp_leave(e):
            self._main_scroll_active = True
            rp_canvas.unbind_all("<MouseWheel>")
            self._sf.bind("<MouseWheel>", self._main_scroll_fn)
            self._main_canvas.bind("<MouseWheel>", self._main_scroll_fn)

        rp_canvas.bind("<Enter>", _rp_enter)
        rp_canvas.bind("<Leave>", _rp_leave)
        rp_inner.bind("<Enter>", _rp_enter)
        rp_inner.bind("<Leave>", _rp_leave)

        rp = rp_inner
        rp.grid_columnconfigure(0, weight=1)

        # ── Sección cuenta ────────────────────────────────────────────────
        self._build_account_card(rp)

        # ── Stat cards ────────────────────────────────────────────────────
        self._stat_cards = []
        stats = [
            ("📦", "Versiones\ninstaladas", "0", GREEN),
            ("👤", "Perfiles\ncreados",     "0", "#3d8ff5"),
            ("🧩", "Mods totales",          "0", "#ffa502"),
        ]
        for i, (icon, label, val, color) in enumerate(stats):
            sc = tk.Frame(rp, bg=CARD_BG, padx=18, pady=16)
            sc.grid(row=i + 1, column=0, sticky="ew", pady=(0, 10))
            sc.grid_columnconfigure(1, weight=1)
            tk.Label(sc, text=icon, bg=CARD_BG,
                     font=("Segoe UI", 20)).grid(row=0, column=0, rowspan=2,
                                                  padx=(0, 14), sticky="w")
            val_lbl = tk.Label(sc, text=val, bg=CARD_BG, fg=color,
                               font=("Segoe UI Variable Display", 22, "bold"))
            val_lbl.grid(row=0, column=1, sticky="w")
            tk.Label(sc, text=label, bg=CARD_BG, fg=TEXT_SEC,
                     font=("Segoe UI Variable Text", 9)).grid(
                         row=1, column=1, sticky="w")
            self._stat_cards.append(val_lbl)

        # ── Accesos rápidos ───────────────────────────────────────────────
        disc = tk.Frame(rp, bg=CARD_BG, padx=18, pady=18)
        disc.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        disc.grid_columnconfigure(0, weight=1)
        tk.Label(disc, text="Descubrir mods", bg=CARD_BG, fg=TEXT_PRI,
                 font=("Segoe UI Variable Display", 12, "bold")).grid(
                     row=0, column=0, sticky="w")
        tk.Label(disc, text="Busca mods y modpacks en Modrinth",
                 bg=CARD_BG, fg=TEXT_SEC,
                 font=("Segoe UI Variable Text", 9)).grid(
                     row=1, column=0, sticky="w", pady=(4, 12))
        _btn_ghost(disc, "Explorar  →",
                   lambda: self.app._show_view("discover"), small=True).grid(
                       row=2, column=0, sticky="w")

        # ── Noticias ──────────────────────────────────────────────────────
        self._build_news_section(rp)

    # ── Card de cuenta ───────────────────────────────────────────────────────
    def _build_account_card(self, parent):
        card = tk.Frame(parent, bg=CARD_BG, padx=18, pady=16)
        card.grid(row=0, column=0, sticky="ew", pady=(24, 10))
        card.grid_columnconfigure(0, weight=1)

        tk.Label(card, text="JUGANDO COMO", bg=CARD_BG, fg=TEXT_DIM,
                 font=("Segoe UI Variable Text", 8, "bold")).grid(
                 row=0, column=0, sticky="w", pady=(0, 10))

        row = tk.Frame(card, bg=CARD_BG)
        row.grid(row=1, column=0, sticky="ew")
        row.grid_columnconfigure(1, weight=1)

        # Avatar
        self._avatar_canvas = tk.Canvas(row, width=38, height=38,
                                         bg=CARD_BG, highlightthickness=0)
        self._avatar_canvas.grid(row=0, column=0, rowspan=2, padx=(0, 12))

        self._acc_name_lbl = tk.Label(row, text="Sin cuenta",
                                       bg=CARD_BG, fg=TEXT_PRI,
                                       font=("Segoe UI Variable Text", 10, "bold"),
                                       anchor="w")
        self._acc_name_lbl.grid(row=0, column=1, sticky="ew")

        dot_row = tk.Frame(row, bg=CARD_BG)
        dot_row.grid(row=1, column=1, sticky="w")
        self._dot_c = tk.Canvas(dot_row, width=8, height=8,
                                 bg=CARD_BG, highlightthickness=0)
        self._dot_c.pack(side="left")
        self._dot_oval = self._dot_c.create_oval(1, 1, 7, 7,
                                                  fill=TEXT_DIM, outline="")
        self._acc_mode_lbl = tk.Label(dot_row, text="Offline",
                                       bg=CARD_BG, fg=TEXT_DIM,
                                       font=("Segoe UI Variable Text", 8))
        self._acc_mode_lbl.pack(side="left", padx=(4, 0))

        tk.Button(card, text="Gestionar cuentas →",
                  bg=CARD_BG, fg=TEXT_SEC,
                  activebackground=CARD2_BG, activeforeground=GREEN,
                  relief="flat", font=("Segoe UI Variable Text", 8),
                  cursor="hand2", pady=5,
                  command=lambda: self.app._show_view("accounts")).grid(
                  row=2, column=0, sticky="w", pady=(10, 0))

    def _draw_avatar(self, username: str):
        self._avatar_canvas.delete("all")
        palette = ["#1bd96a","#4dabf7","#f783ac","#ffa94d",
                   "#a9e34b","#74c0fc","#ff8787","#63e6be",
                   "#cc5de8","#ff922b"]
        color    = palette[abs(hash(username)) % len(palette)]
        initials = (username[:2] if len(username) >= 2 else username).upper()
        self._avatar_canvas.create_oval(0, 0, 38, 38, fill=color, outline="")
        self._avatar_canvas.create_text(19, 19, text=initials,
                                         fill="#0a0a0a",
                                         font=("Segoe UI", 12, "bold"))

    def _refresh_account_panel(self):
        try:
            account = self.app.account_manager.get_active_account()
            if not account:
                all_acc = self.app.account_manager.get_all_accounts()
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

        self._acc_name_lbl.configure(text=name)
        self._acc_mode_lbl.configure(text=mode_txt)
        self._dot_c.itemconfig(self._dot_oval, fill=dot_col)
        self._draw_avatar(name)

    def _on_account_select(self):
        username = self._account_var.get()
        self._acc_name_lbl.configure(text=username)
        self._draw_avatar(username)
        try:
            self.app.account_manager.set_active_account_by_username(username)
        except Exception:
            pass

    # ── Noticias ─────────────────────────────────────────────────────────────
    def _build_news_section(self, parent):
        card = tk.Frame(parent, bg=CARD_BG)
        card.grid(row=5, column=0, sticky="ew", pady=(0, 24))
        card.grid_columnconfigure(0, weight=1)

        # Encabezado
        hdr = tk.Frame(card, bg=CARD_BG, padx=18, pady=14)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        tk.Label(hdr, text="NOTICIAS", bg=CARD_BG, fg=TEXT_DIM,
                 font=("Segoe UI Variable Text", 8, "bold")).grid(
                 row=0, column=0, sticky="w")
        self._news_count_lbl = tk.Label(hdr, text="cargando…",
                                         bg=CARD_BG, fg=TEXT_DIM,
                                         font=("Segoe UI Variable Text", 7))
        self._news_count_lbl.grid(row=0, column=1, sticky="e")

        tk.Frame(card, bg=BORDER, height=1).grid(
            row=1, column=0, sticky="ew", padx=12)

        # Contenedor de cards de noticias (sin canvas extra — ya scrollea con el panel)
        self._news_container = tk.Frame(card, bg=CARD_BG)
        self._news_container.grid(row=2, column=0, sticky="ew")
        self._news_container.grid_columnconfigure(0, weight=1)

        tk.Label(self._news_container, text="Conectando…",
                 bg=CARD_BG, fg=TEXT_DIM,
                 font=("Segoe UI Variable Text", 9), pady=14).pack(
                 fill="x", padx=14)

        threading.Thread(target=self._fetch_news, daemon=True).start()

    def _fetch_news(self):
        items = []
        try:
            req = urllib.request.Request(
                "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json",
                headers={"User-Agent": "GerosLauncher/0.2.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())
            lr = data["latest"]["release"]
            ls = data["latest"]["snapshot"]
            items.append({"tag":"⭐ Destacado","tag_color":GREEN,
                           "title":f"Última release: {lr}",
                           "body":f"Snapshot: {ls}","source":"Mojang","url":None})
            tm = {"release":("🟢 Release",GREEN),"snapshot":("🔵 Snapshot","#4dabf7"),
                  "old_beta":("🟡 Beta","#ffa94d"),"old_alpha":("🔴 Alpha","#ff6b6b")}
            for v in data["versions"][:5]:
                tag, tc = tm.get(v["type"],(v["type"],TEXT_SEC))
                items.append({"tag":tag,"tag_color":tc,
                              "title":f"Minecraft {v['id']}",
                              "body":v.get("releaseTime","")[:10],
                              "source":"Mojang","url":None})
        except Exception as ex:
            log.warning(f"Noticias Mojang: {ex}")
        try:
            req2 = urllib.request.Request(
                "https://api.modrinth.com/v2/search"
                "?limit=4&index=updated&facets=[[%22project_type:mod%22]]",
                headers={"User-Agent": "GerosLauncher/0.2.0"})
            with urllib.request.urlopen(req2, timeout=8) as r:
                mdata = json.loads(r.read().decode())
            for hit in mdata.get("hits",[]):
                desc = hit.get("description","")
                items.append({"tag":"🧩 Mod","tag_color":"#a9e34b",
                              "title":hit.get("title","Mod"),
                              "body":(desc[:60]+"…") if len(desc)>60 else desc,
                              "source":"Modrinth",
                              "url":f"https://modrinth.com/mod/{hit.get('slug','')}"})
        except Exception as ex:
            log.warning(f"Noticias Modrinth: {ex}")
        self.after(0, lambda: self._render_news(items))

    def _render_news(self, items):
        for w in self._news_container.winfo_children():
            w.destroy()
        if not items:
            tk.Label(self._news_container, text="Sin conexión.",
                     bg=CARD_BG, fg=TEXT_DIM,
                     font=("Segoe UI Variable Text", 9), pady=10).pack(
                     fill="x", padx=14)
            self._news_count_lbl.configure(text="sin conexión")
            return
        self._news_count_lbl.configure(text=f"{len(items)} entradas")
        for i, item in enumerate(items):
            if i > 0:
                tk.Frame(self._news_container, bg=BORDER, height=1).pack(
                    fill="x", padx=12)
            self._make_news_card(item)

    def _make_news_card(self, item):
        has_url = bool(item.get("url"))
        card = tk.Frame(self._news_container, bg=CARD_BG,
                        padx=14, pady=8,
                        cursor="hand2" if has_url else "")
        card.pack(fill="x")
        card.grid_columnconfigure(0, weight=1)

        hdr = tk.Frame(card, bg=CARD_BG)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        tk.Label(hdr, text=item["tag"], bg=CARD_BG,
                 fg=item.get("tag_color", GREEN),
                 font=("Segoe UI Variable Text", 8, "bold")).grid(
                 row=0, column=0, sticky="w")
        tk.Label(hdr, text=item["source"], bg=CARD_BG, fg=TEXT_DIM,
                 font=("Segoe UI Variable Text", 7)).grid(
                 row=0, column=1, sticky="e")

        tk.Label(card, text=item["title"], bg=CARD_BG, fg=TEXT_PRI,
                 font=("Segoe UI Variable Text", 9, "bold"),
                 anchor="w", wraplength=230, justify="left").grid(
                 row=1, column=0, sticky="ew", pady=(2, 0))

        if item.get("body"):
            tk.Label(card, text=item["body"], bg=CARD_BG, fg=TEXT_SEC,
                     font=("Segoe UI Variable Text", 8),
                     anchor="w", wraplength=230, justify="left").grid(
                     row=2, column=0, sticky="ew")

        all_w = ([card, hdr] + list(card.winfo_children())
                 + list(hdr.winfo_children()))

        def on_enter(e):
            for w in all_w:
                try: w.configure(bg=CARD2_BG)
                except Exception: pass

        def on_leave(e):
            for w in all_w:
                try: w.configure(bg=CARD_BG)
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

    # ── on_show ──────────────────────────────────────────────────────────────
    def on_show(self):
        self._refresh_accounts()
        self._refresh_profiles()
        self._refresh_versions()
        self._refresh_installed()
        self._refresh_stats()
        self._refresh_account_panel()

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
                                   padx=36, pady=(0, 0))
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
                                   "No tienes ninguna cuenta.\n¿Ir a 'Cuentas'?"):
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