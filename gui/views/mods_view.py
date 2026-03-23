"""
gui/views/mods_view.py
Redesigned mods view with Modrinth-style rows:
  - Mod icon (downloaded/cached or placeholder)
  - Mod name + author/filename
  - Version / filename info
  - Toggle button (enable/disable)
  - Delete button
  - Options button (⋮)
"""

import os
import io
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from urllib.request import urlopen

try:
    from PIL import Image, ImageTk, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from utils.logger import get_logger

log = get_logger()

# ── colours ───────────────────────────────────────────────────────────────────
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

ICON_SIZE   = 44          # px – square icon inside each row
ROW_H       = 64          # row height in pixels
ICON_CACHE  = {}          # url → PhotoImage


# ── helpers ───────────────────────────────────────────────────────────────────

def _placeholder_icon(size=ICON_SIZE) -> "ImageTk.PhotoImage | None":
    if not PIL_AVAILABLE:
        return None
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r = size // 5
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill="#3a3c42", outline=None)
    cx, cy = size // 2, size // 2
    hs = size // 3
    draw.rounded_rectangle([cx - hs, cy - hs, cx + hs, cy + hs],
                            radius=5, fill="#1bd96a", outline=None)
    draw.rounded_rectangle([cx - hs//2, cy - hs//2, cx + hs//2, cy + hs//2],
                            radius=3, fill="#25262b", outline=None)
    return ImageTk.PhotoImage(img)


def _fetch_icon(url: str, callback):
    """Download icon in background thread, call callback(PhotoImage) on main thread."""
    if not PIL_AVAILABLE or not url:
        callback(None)
        return
    if url in ICON_CACHE:
        callback(ICON_CACHE[url])
        return

    def _dl():
        try:
            with urlopen(url, timeout=6) as resp:
                data = resp.read()
            img = Image.open(io.BytesIO(data)).convert("RGBA")
            img = img.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
            # round corners
            mask = Image.new("L", img.size, 0)
            from PIL import ImageDraw as _D
            _D.Draw(mask).rounded_rectangle(
                [0, 0, ICON_SIZE - 1, ICON_SIZE - 1], radius=8, fill=255)
            img.putalpha(mask)
            ph = ImageTk.PhotoImage(img)
            ICON_CACHE[url] = ph
            callback(ph)
        except Exception:
            callback(None)

    threading.Thread(target=_dl, daemon=True).start()


# ── toggle widget ─────────────────────────────────────────────────────────────

class _Toggle(tk.Canvas):
    W, H = 40, 22

    def __init__(self, parent, is_on: bool, command=None, **kw):
        if "bg" not in kw:
            kw["bg"] = parent["bg"] if "bg" in parent.keys() else BG_CARD
        super().__init__(parent, width=self.W, height=self.H,
                            bd=0, highlightthickness=0, **kw)
        self._on = is_on
        self._cmd = command
        self._draw()
        self.bind("<Button-1>", self._toggle)
        self.config(cursor="hand2")

    def _draw(self):
        self.delete("all")
        color = GREEN if self._on else "#4a4c55"
        r = self.H // 2
        self.create_oval(0, 0, self.H, self.H, fill=color, outline="")
        self.create_oval(self.W - self.H, 0, self.W, self.H, fill=color, outline="")
        self.create_rectangle(r, 0, self.W - r, self.H, fill=color, outline=color)
        pad = 2
        knob_x = self.W - r if self._on else r
        self.create_oval(knob_x - r + pad, pad,
                        knob_x + r - pad, self.H - pad,
                        fill=WHITE, outline="")

    def _toggle(self, _=None):
            self._on = not self._on
            self._draw()
            if self._cmd:
                self._cmd(self._on)

    def set(self, value: bool):
            self._on = value
            self._draw()


# ── single mod row ────────────────────────────────────────────────────────────

class _ModRow(tk.Frame):
    """
    One row in the installed-mods list.

    Layout:  [icon 44px]  [name + sub]  [version col]  [toggle]  [🗑]  [⋮]
    """

    def __init__(self, parent, mod_info, on_toggle, on_delete, on_options,
                 even: bool = True, **kw):
        bg = BG_ROW if even else BG_ROW_ALT
        super().__init__(parent, bg=bg, **kw)
        self._bg = bg
        self._mod = mod_info
        self._ph = None          # keep reference to avoid GC

        self.bind("<Enter>", lambda _: self.config(bg=BG_HOVER) or self._tint(BG_HOVER))
        self.bind("<Leave>", lambda _: self.config(bg=bg) or self._tint(bg))

        self._build(mod_info, on_toggle, on_delete, on_options)
        self._load_icon(getattr(mod_info, "icon_url", ""))

    # ── build ──────────────────────────────────────────────────────────────

    def _build(self, mod, on_toggle, on_delete, on_options):
        self.columnconfigure(2, weight=1)

        # icon canvas
        # icon frame
        BG_INPUT    = "#2c2d31"
        icon_frame = tk.Frame(self, bg=self._bg, width=ICON_SIZE, height=ICON_SIZE)
        icon_frame.grid(row=0, column=0, rowspan=2, padx=(12, 10), pady=10, sticky="w")
        icon_frame.pack_propagate(False)
        self._icon_lbl = tk.Label(icon_frame, text="📦", bg=BG_INPUT,
                                font=("Segoe UI Variable Text", 18))
        self._icon_lbl.pack(expand=True, fill="both")

        # name label
        display = getattr(mod, "title", None) or getattr(mod, "display_name", mod.filename)
        author  = getattr(mod, "author", None) or ""
        tk.Label(self, text=display, bg=self._bg, fg=WHITE,
                 font=("Segoe UI Variable Text", 10, "bold"),
                 anchor="w").grid(row=0, column=1, sticky="sw", padx=(0, 8))
        sub = author if author else mod.filename
        tk.Label(self, text=sub, bg=self._bg, fg=MUTED,
                 font=("Segoe UI Variable Text", 8),
                 anchor="w").grid(row=1, column=1, sticky="nw", padx=(0, 8))

        # version / size
        ver_text = getattr(mod, "version_number", None) or f"{mod.size_mb} MB"
        tk.Label(self, text=ver_text, bg=self._bg, fg=MUTED,
                 font=("Segoe UI Variable Text", 9),
                 anchor="e").grid(row=0, column=2, sticky="se", padx=(0, 12))
        fname = getattr(mod, "filename", "")
        tk.Label(self, text=fname, bg=self._bg, fg="#555a62",
                 font=("Segoe UI Variable Text", 7),
                 anchor="e").grid(row=1, column=2, sticky="ne", padx=(0, 12))

        # toggle
        self._toggle = _Toggle(self, is_on=mod.is_enabled,
                               command=lambda v: on_toggle(mod, v), bg=self._bg)
        self._toggle.grid(row=0, column=3, rowspan=2, padx=(0, 8))

        # delete
        del_btn = tk.Label(self, text="🗑", bg=self._bg, fg=MUTED,
                           font=("Segoe UI Variable Text", 13), cursor="hand2")
        del_btn.grid(row=0, column=4, rowspan=2, padx=(0, 4))
        del_btn.bind("<Button-1>", lambda _: on_delete(mod))
        del_btn.bind("<Enter>", lambda _: del_btn.config(fg=RED))
        del_btn.bind("<Leave>", lambda _: del_btn.config(fg=MUTED))

        # options ⋮
        opt_btn = tk.Label(self, text="⋮", bg=self._bg, fg=MUTED,
                           font=("Segoe UI Variable Text", 14), cursor="hand2")
        opt_btn.grid(row=0, column=5, rowspan=2, padx=(0, 14))
        opt_btn.bind("<Button-1>", lambda e: on_options(e, mod))
        opt_btn.bind("<Enter>", lambda _: opt_btn.config(fg=WHITE))
        opt_btn.bind("<Leave>", lambda _: opt_btn.config(fg=MUTED))

    # ── icon loading ───────────────────────────────────────────────────────

    def _load_icon(self, url: str):
        if not url or not PIL_AVAILABLE:
            return
        def _dl():
            try:
                import io
                from urllib.request import urlopen
                with urlopen(url, timeout=6) as resp:
                    data = resp.read()
                img = Image.open(io.BytesIO(data)).resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
                ph = ImageTk.PhotoImage(img)
                self._ph = ph
                if self.winfo_exists():
                    self.after(0, lambda: self._icon_lbl.config(image=ph, text=""))
            except Exception:
                pass
        threading.Thread(target=_dl, daemon=True).start()

    # ── tint children bg on hover ──────────────────────────────────────────

    def _tint(self, color: str):
        for child in self.winfo_children():
            try:
                child.config(bg=color)
            except Exception:
                pass
            if hasattr(child, "_bg"):
                child._bg = color


# ── search result row ─────────────────────────────────────────────────────────

class _SearchRow(tk.Frame):
    """
    One row in the Modrinth search results.

    Layout:  [icon]  [name + description]  [downloads + mc versions]  [Install ▼]  [⋮]
    """

    def __init__(self, parent, project, on_install, on_options, even=True, **kw):
        bg = BG_ROW if even else BG_ROW_ALT
        super().__init__(parent, bg=bg, **kw)
        self._bg = bg
        self._ph = None

        self.bind("<Enter>", lambda _: self.config(bg=BG_HOVER) or self._tint(BG_HOVER))
        self.bind("<Leave>", lambda _: self.config(bg=bg) or self._tint(bg))

        self._build(project, on_install, on_options)
        self._load_icon(project.icon_url)

    def _build(self, project, on_install, on_options):
        self.columnconfigure(2, weight=1)

        # icon
        self._icon_canvas = tk.Canvas(
            self, width=ICON_SIZE, height=ICON_SIZE,
            bg=self._bg, bd=0, highlightthickness=0)
        self._icon_canvas.grid(row=0, column=0, rowspan=2, padx=(12, 10), pady=10, sticky="w")
        self._ph_placeholder = _placeholder_icon()
        if self._ph_placeholder:
            self._icon_canvas.create_image(
                ICON_SIZE // 2, ICON_SIZE // 2, image=self._ph_placeholder, anchor="center")

        # name + description
        tk.Label(self, text=project.title, bg=self._bg, fg=WHITE,
                 font=("Segoe UI Variable Text", 10, "bold"), anchor="w").grid(
            row=0, column=1, sticky="sw", padx=(0, 8))
        desc = (project.description[:72] + "…") if len(project.description) > 72 else project.description
        tk.Label(self, text=desc, bg=self._bg, fg=MUTED,
                 font=("Segoe UI Variable Text", 8), anchor="w").grid(
            row=1, column=1, sticky="nw", padx=(0, 8))

        # downloads + versions
        mc_v = ", ".join(project.game_versions[-3:]) if project.game_versions else "—"
        tk.Label(self, text=f"⬇ {project.downloads:,}", bg=self._bg, fg=MUTED,
                 font=("Segoe UI Variable Text", 9), anchor="e").grid(
            row=0, column=2, sticky="se", padx=(0, 12))
        tk.Label(self, text=mc_v, bg=self._bg, fg="#555a62",
                 font=("Segoe UI Variable Text", 7), anchor="e").grid(
            row=1, column=2, sticky="ne", padx=(0, 12))

        # install button
        inst_btn = tk.Label(self, text="⬇ Instalar", bg=GREEN_DIM, fg=WHITE,
                            font=("Segoe UI Variable Text", 8, "bold"), cursor="hand2",
                            padx=10, pady=4)
        inst_btn.grid(row=0, column=3, rowspan=2, padx=(0, 6))
        inst_btn.bind("<Button-1>", lambda _: on_install(project))
        inst_btn.bind("<Enter>", lambda _: inst_btn.config(bg=GREEN))
        inst_btn.bind("<Leave>", lambda _: inst_btn.config(bg=GREEN_DIM))

        # options
        opt_btn = tk.Label(self, text="⋮", bg=self._bg, fg=MUTED,
                           font=("Segoe UI Variable Text", 14), cursor="hand2")
        opt_btn.grid(row=0, column=4, rowspan=2, padx=(0, 14))
        opt_btn.bind("<Button-1>", lambda e: on_options(e, project))
        opt_btn.bind("<Enter>", lambda _: opt_btn.config(fg=WHITE))
        opt_btn.bind("<Leave>", lambda _: opt_btn.config(fg=MUTED))

    def _load_icon(self, url: str):
        if not url:
            return

        def _set(ph):
            if ph and self.winfo_exists():
                self._ph = ph
                self._icon_canvas.delete("all")
                self._icon_canvas.create_image(
                    ICON_SIZE // 2, ICON_SIZE // 2, image=ph, anchor="center")

        _fetch_icon(url, lambda ph: self.after(0, lambda: _set(ph)))

    def _tint(self, color: str):
        for child in self.winfo_children():
            try:
                child.config(bg=color)
            except Exception:
                pass


# ── scrollable frame ──────────────────────────────────────────────────────────

class _ScrollFrame(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.canvas = tk.Canvas(self, bg=BG, bd=0, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=BG)

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self._scroll_bound = False
        self.bind("<Enter>", self._bind_scroll)
        self.bind("<Leave>", self._unbind_scroll)
        self.canvas.bind("<Enter>", self._bind_scroll)
        self.canvas.bind("<Leave>", self._unbind_scroll)
        self.inner.bind("<Enter>", self._bind_scroll)
        self.inner.bind("<Leave>", self._unbind_scroll)

    def _bind_scroll(self, _=None):
        if not self._scroll_bound:
            self._scroll_bound = True
            self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_scroll(self, _=None):
        # Only unbind if mouse truly left — check pointer position
        self.after(50, self._check_unbind)

    def _check_unbind(self):
        try:
            x, y = self.winfo_pointerxy()
            wx, wy = self.winfo_rootx(), self.winfo_rooty()
            ww, wh = self.winfo_width(), self.winfo_height()
            if not (wx <= x <= wx + ww and wy <= y <= wy + wh):
                self._scroll_bound = False
                self.canvas.unbind_all("<MouseWheel>")
        except Exception:
            pass

    def _on_inner_configure(self, _):
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self._win, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


# ── main ModsView ──────────────────────────────────────────────────────────────

class ModsView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._current_profile = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build()

    # ── layout ────────────────────────────────────────────────────────────

    def _build(self):
        main = tk.Frame(self, bg=BG, padx=28, pady=20)
        main.grid(row=0, column=0, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(4, weight=1)

        # title
        tk.Label(main, text="Mods", bg=BG, fg=WHITE,
                 font=("Segoe UI Variable Display", 18, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(main, text="Administra los mods de cada perfil",
                 bg=BG, fg=MUTED, font=("Segoe UI Variable Text", 10)).grid(
            row=1, column=0, sticky="w", pady=(2, 16))

        # toolbar
        toolbar = tk.Frame(main, bg=BG_CARD, padx=14, pady=10)
        toolbar.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        toolbar.grid_columnconfigure(1, weight=1)

        tk.Label(toolbar, text="Perfil:", bg=BG_CARD, fg=MUTED,
                 font=("Segoe UI Variable Text", 9)).grid(row=0, column=0, padx=(0, 8))
        self._profile_var = tk.StringVar()
        self._profile_combo = ttk.Combobox(
            toolbar, textvariable=self._profile_var, state="readonly",
            font=("Segoe UI Variable Text", 10), width=22)
        self._profile_combo.grid(row=0, column=1, sticky="w", padx=(0, 16))
        self._profile_combo.bind("<<ComboboxSelected>>", self._on_profile_change)

        btn_frame = tk.Frame(toolbar, bg=BG_CARD)
        btn_frame.grid(row=0, column=2, sticky="e")
        self._mk_btn(btn_frame, "📂 Instalar .jar", self._on_install_local).pack(side="left", padx=(0, 8))
        self._mk_btn(btn_frame, "🔍 Buscar en Modrinth", self._open_modrinth_search).pack(side="left")

        # tab bar: Instalados / Buscar
        tab_bar = tk.Frame(main, bg=BG)
        tab_bar.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self._tab_var = tk.StringVar(value="installed")
        self._tab_installed = self._mk_tab(tab_bar, "Instalados", "installed")
        self._tab_installed.pack(side="left", padx=(0, 4))
        self._tab_search = self._mk_tab(tab_bar, "Resultados de búsqueda", "search")
        self._tab_search.pack(side="left")

        # content area
        self._content_frame = tk.Frame(main, bg=BG)
        self._content_frame.grid(row=4, column=0, sticky="nsew")
        self._content_frame.grid_columnconfigure(0, weight=1)
        self._content_frame.grid_rowconfigure(0, weight=1)

        # installed scroll area
        self._installed_scroll = _ScrollFrame(self._content_frame, bg=BG)
        self._installed_scroll.grid(row=0, column=0, sticky="nsew")

        # search scroll area (hidden initially)
        self._search_scroll = _ScrollFrame(self._content_frame, bg=BG)

        self._search_results = []
        self._show_tab("installed")

    # ── tab helpers ────────────────────────────────────────────────────────

    def _mk_tab(self, parent, text, value):
        lbl = tk.Label(parent, text=text, bg=BG, fg=MUTED,
                       font=("Segoe UI Variable Text", 10), cursor="hand2",
                       padx=12, pady=6)
        lbl.bind("<Button-1>", lambda _: self._show_tab(value))
        return lbl

    def _show_tab(self, which: str):
        self._tab_var.set(which)
        active_fg, inactive_fg = WHITE, MUTED
        active_border, inactive_border = GREEN, BG
        for lbl, val in [(self._tab_installed, "installed"),
                         (self._tab_search, "search")]:
            if val == which:
                lbl.config(fg=active_fg, relief="flat",
                           highlightbackground=active_border, highlightthickness=2)
            else:
                lbl.config(fg=inactive_fg, relief="flat",
                           highlightbackground=inactive_border, highlightthickness=0)

        if which == "installed":
            self._search_scroll.grid_remove()
            self._installed_scroll.grid(row=0, column=0, sticky="nsew")
        else:
            self._installed_scroll.grid_remove()
            self._search_scroll.grid(row=0, column=0, sticky="nsew")

    # ── button helper ──────────────────────────────────────────────────────

    def _mk_btn(self, parent, text, cmd):
        btn = tk.Label(parent, text=text, bg="#2f3136", fg=WHITE,
                       font=("Segoe UI Variable Text", 9), cursor="hand2",
                       padx=10, pady=5, relief="flat")
        btn.bind("<Button-1>", lambda _: cmd())
        btn.bind("<Enter>", lambda _: btn.config(bg="#3a3d44"))
        btn.bind("<Leave>", lambda _: btn.config(bg="#2f3136"))
        return btn

    # ── lifecycle ──────────────────────────────────────────────────────────

    def on_show(self):
        self._refresh_profiles()

    # ── profile handling ───────────────────────────────────────────────────

    def _refresh_profiles(self):
        print("REFRESH PROFILES called")
        profiles = self.app.profile_manager.get_all_profiles()
        names = [p.name for p in profiles]
        self._profile_combo["values"] = names
        if names and not self._profile_var.get():
            self._profile_var.set(names[0])
            self._load_mods_for_profile(names[0])
        elif names:
            self._load_mods_for_profile(self._profile_var.get())

    def _on_profile_change(self, _=None):
        name = self._profile_var.get()
        if name:
            self._load_mods_for_profile(name)

    def _load_mods_for_profile(self, profile_name: str):
        profile = self.app.profile_manager.get_profile_by_name(profile_name)
        if not profile:
            return
        self._current_profile = profile
        self._refresh_mods()

    # ── installed mods list ────────────────────────────────────────────────

    def _refresh_mods(self):
        print("REFRESH MODS called, profile:", self._current_profile)
        for w in self._installed_scroll.inner.winfo_children():
            w.destroy()

        if not self._current_profile:
            return

        from managers.mod_manager import ModManager
        mods = ModManager(self._current_profile).list_mods()

        if not mods:
            tk.Label(self._installed_scroll.inner,
                     text="No hay mods instalados en este perfil.",
                     bg=BG, fg=MUTED, font=("Segoe UI Variable Text", 10)).pack(pady=40)
            return

        for i, mod in enumerate(mods):
            row = _ModRow(
                self._installed_scroll.inner, mod,
                on_toggle=self._on_toggle_mod,
                on_delete=self._on_delete_mod,
                on_options=self._on_options_mod,
                even=(i % 2 == 0),
            )
            row.pack(fill="x", pady=(0, 1))

    # ── mod actions ────────────────────────────────────────────────────────

    def _on_toggle_mod(self, mod, new_state: bool):
        from managers.mod_manager import ModManager, ModError
        try:
            mm = ModManager(self._current_profile)
            if new_state:
                mm.enable_mod(mod.filename)
            else:
                mm.disable_mod(mod.filename)
            self._refresh_mods()
        except ModError as e:
            messagebox.showerror("Error", str(e))

    def _on_delete_mod(self, mod):
        if not messagebox.askyesno("Confirmar", f"¿Eliminar '{mod.display_name}'?"):
            return
        from managers.mod_manager import ModManager, ModError
        try:
            ModManager(self._current_profile).delete_mod(mod.filename)
            self._refresh_mods()
        except ModError as e:
            messagebox.showerror("Error", str(e))

    def _on_options_mod(self, event, mod):
        menu = tk.Menu(self, tearoff=0, bg=BG_CARD, fg=WHITE,
                       activebackground=BG_HOVER, activeforeground=WHITE,
                       font=("Segoe UI Variable Text", 9))
        enabled = mod.is_enabled
        menu.add_command(
            label="Deshabilitar mod" if enabled else "Habilitar mod",
            command=lambda: self._on_toggle_mod(mod, not enabled))
        menu.add_separator()
        menu.add_command(label="Abrir carpeta de mods",
                         command=lambda: self._open_mods_folder())
        menu.add_separator()
        menu.add_command(label="Eliminar mod",
                         command=lambda: self._on_delete_mod(mod))
        menu.tk_popup(event.x_root, event.y_root)

    def _open_mods_folder(self):
        if self._current_profile:
            import subprocess
            subprocess.Popen(f'explorer "{self._current_profile.mods_dir}"')

    # ── local install ──────────────────────────────────────────────────────

    def _on_install_local(self):
        if not self._current_profile:
            messagebox.showwarning("Aviso", "Selecciona un perfil primero.")
            return
        path = filedialog.askopenfilename(
            title="Seleccionar mod",
            filetypes=[("Archivos JAR", "*.jar"), ("Todos los archivos", "*.*")])
        if not path:
            return
        from managers.mod_manager import ModManager, ModError
        try:
            ModManager(self._current_profile).install_mod_from_file(path)
            self._refresh_mods()
            messagebox.showinfo("Listo", "Mod instalado correctamente.")
        except ModError as e:
            messagebox.showerror("Error", str(e))

    # ── modrinth search window ─────────────────────────────────────────────

    def _open_modrinth_search(self):
        if not self._current_profile:
            messagebox.showwarning("Aviso", "Selecciona un perfil primero.")
            return
        ModrinthSearchWindow(self, self.app, self._current_profile,
                             self._on_modrinth_results, self._refresh_mods)

    def _on_modrinth_results(self, results):
        """Called after a Modrinth search — populate search tab."""
        self._search_results = results
        for w in self._search_scroll.inner.winfo_children():
            w.destroy()
        for i, project in enumerate(results):
            row = _SearchRow(
                self._search_scroll.inner, project,
                on_install=self._on_install_from_search,
                on_options=self._on_options_search,
                even=(i % 2 == 0),
            )
            row.pack(fill="x", pady=(0, 1))
        self._show_tab("search")

    def _on_install_from_search(self, project):
        if not self._current_profile:
            messagebox.showwarning("Aviso", "Selecciona un perfil primero.")
            return
        self._status_msg(f"Descargando {project.title}…")

        def dl():
            try:
                from managers.mod_manager import ModManager
                version = self.app.modrinth_service.get_latest_version(
                    project.project_id, mc_version=self._current_profile.version_id)
                if not version:
                    self.after(0, lambda: messagebox.showerror(
                        "Error", "No hay versión compatible con este perfil."))
                    return
                self.app.modrinth_service.download_mod_version(
                    version, self._current_profile.mods_dir)
                self.after(0, lambda: (
                    self._refresh_mods(),
                    messagebox.showinfo("Listo", f"{project.title} instalado correctamente.")
                ))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error de descarga", str(e)))

        threading.Thread(target=dl, daemon=True).start()

    def _on_options_search(self, event, project):
        menu = tk.Menu(self, tearoff=0, bg=BG_CARD, fg=WHITE,
                       activebackground=BG_HOVER, activeforeground=WHITE,
                       font=("Segoe UI Variable Text", 9))
        menu.add_command(label=f"Instalar {project.title}",
                         command=lambda: self._on_install_from_search(project))
        menu.add_separator()
        menu.add_command(label="Ver en Modrinth",
                         command=lambda: self._open_url(
                             f"https://modrinth.com/mod/{project.slug}"))
        menu.tk_popup(event.x_root, event.y_root)

    def _open_url(self, url: str):
        import webbrowser
        webbrowser.open(url)

    def _status_msg(self, msg: str):
        # simple ephemeral status — could be replaced with a status bar
        log.info(msg)


# ── Modrinth search window ─────────────────────────────────────────────────────

class ModrinthSearchWindow(tk.Toplevel):

    DEBOUNCE_MS = 500   # ms to wait after last keystroke before searching
    LOADERS     = ["Todos", "fabric", "forge", "neoforge", "quilt"]
    SORT_OPTIONS = {
        "Relevancia": "relevance",
        "Más descargados": "downloads",
        "Más recientes": "newest",
        "Actualizados": "updated",
    }

    def __init__(self, parent, app, profile, on_results_callback, on_install_callback):
        super().__init__(parent)
        self.app = app
        self.profile = profile
        self._on_results = on_results_callback
        self._on_install = on_install_callback
        self.title(f"Buscar en Modrinth — {profile.name}")
        self.geometry("820x600")
        self.configure(bg=BG)
        self.resizable(True, True)
        self._debounce_id = None   # after() id for debounce
        self._last_query  = None   # avoid duplicate searches
        self._build()

    # ── layout ────────────────────────────────────────────────────────────

    def _build(self):
        main = tk.Frame(self, bg=BG, padx=24, pady=20)
        main.pack(fill="both", expand=True)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        tk.Label(main, text="Buscar mods en Modrinth", bg=BG, fg=WHITE,
                 font=("Segoe UI Variable Display", 14, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 12))

        # ── search bar + filters ──────────────────────────────────────────
        top = tk.Frame(main, bg=BG)
        top.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        top.grid_columnconfigure(0, weight=1)

        # row 0: search entry
        search_row = tk.Frame(top, bg=BG)
        search_row.grid(row=0, column=0, sticky="ew")
        search_row.grid_columnconfigure(0, weight=1)

        self._search_var = tk.StringVar()

        entry = tk.Entry(search_row, textvariable=self._search_var,
                         bg=BG_CARD, fg=WHITE, insertbackground=WHITE,
                         relief="flat", font=("Segoe UI Variable Text", 11))
        entry.grid(row=0, column=0, sticky="ew", ipady=9, padx=(0, 10))
        entry.bind("<KeyRelease>", self._on_text_change)
        entry.bind("<Return>", lambda _: self._trigger_search())

        # loading spinner label (dots animation)
        self._spinner_var = tk.StringVar(value="")
        tk.Label(search_row, textvariable=self._spinner_var,
                 bg=BG, fg=GREEN, font=("Segoe UI Variable Text", 11, "bold"),
                 width=2).grid(row=0, column=1)

        # row 1: filter chips
        filter_row = tk.Frame(top, bg=BG)
        filter_row.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        # Loader filter
        tk.Label(filter_row, text="Loader:", bg=BG, fg=MUTED,
                 font=("Segoe UI Variable Text", 9)).pack(side="left", padx=(0, 6))
        self._loader_var = tk.StringVar(value="Todos")
        loader_combo = ttk.Combobox(filter_row, textvariable=self._loader_var,
                                    values=self.LOADERS, state="readonly",
                                    width=10, font=("Segoe UI Variable Text", 9))
        loader_combo.pack(side="left", padx=(0, 16))
        loader_combo.bind("<<ComboboxSelected>>", self._on_filter_change)

        # MC version filter
        tk.Label(filter_row, text="Versión MC:", bg=BG, fg=MUTED,
                 font=("Segoe UI Variable Text", 9)).pack(side="left", padx=(0, 6))
        installed = self.app.version_manager.get_installed_version_ids() \
            if hasattr(self.app, "version_manager") else []
        mc_options = ["Todas"] + installed
        self._mc_var = tk.StringVar(value=self.profile.version_id
                                    if self.profile.version_id in mc_options
                                    else "Todas")
        mc_combo = ttk.Combobox(filter_row, textvariable=self._mc_var,
                                values=mc_options, state="readonly",
                                width=10, font=("Segoe UI Variable Text", 9))
        mc_combo.pack(side="left", padx=(0, 16))
        mc_combo.bind("<<ComboboxSelected>>", self._on_filter_change)

        # Sort filter
        tk.Label(filter_row, text="Ordenar:", bg=BG, fg=MUTED,
                 font=("Segoe UI Variable Text", 9)).pack(side="left", padx=(0, 6))
        self._sort_var = tk.StringVar(value="Relevancia")
        sort_combo = ttk.Combobox(filter_row, textvariable=self._sort_var,
                                  values=list(self.SORT_OPTIONS.keys()),
                                  state="readonly", width=14,
                                  font=("Segoe UI Variable Text", 9))
        sort_combo.pack(side="left")
        sort_combo.bind("<<ComboboxSelected>>", self._on_filter_change)

        # ── results list ──────────────────────────────────────────────────
        self._results_scroll = _ScrollFrame(main, bg=BG)
        self._results_scroll.grid(row=2, column=0, sticky="nsew")

        # ── status bar ────────────────────────────────────────────────────
        status_bar = tk.Frame(main, bg=BG)
        status_bar.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        status_bar.grid_columnconfigure(0, weight=1)

        self._status_var = tk.StringVar(value="Escribe algo para buscar mods…")
        tk.Label(status_bar, textvariable=self._status_var, bg=BG, fg=MUTED,
                 font=("Segoe UI Variable Text", 9)).grid(row=0, column=0, sticky="w")

        self._results = []
        entry.focus()

    # ── auto-search triggers ───────────────────────────────────────────────

    def _on_text_change(self, *_):
        print("TEXT CHANGED:", self._search_var.get())
        if self._debounce_id:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(self.DEBOUNCE_MS, self._trigger_search)

    def _on_filter_change(self, *_):
        """Called when any filter combobox changes — search immediately."""
        if self._debounce_id:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(50, self._trigger_search)

    def _trigger_search(self):
        print("TRIGGER SEARCH called, query:", self._search_var.get())
        self._debounce_id = None
        query   = self._search_var.get().strip()
        loader  = self._loader_var.get()
        mc_ver  = self._mc_var.get()
        sort    = self.SORT_OPTIONS.get(self._sort_var.get(), "relevance")

        # build a signature to avoid duplicate identical searches
        sig = (query, loader, mc_ver, sort)
        if sig == self._last_query:
            return
        self._last_query = sig

        if not query:
            for w in self._results_scroll.inner.winfo_children():
                w.destroy()
            self._status_var.set("Escribe algo para buscar mods…")
            self._spinner_var.set("")
            return

        self._status_var.set("Buscando…")
        self._spinner_var.set("⟳")
        for w in self._results_scroll.inner.winfo_children():
            w.destroy()

        loader_filter = None if loader == "Todos" else loader
        mc_filter     = None if mc_ver == "Todas" else mc_ver

        def search():
            try:
                results = self.app.modrinth_service.search_mods(
                    query,
                    mc_version=mc_filter,
                    loader=loader_filter,
                )
                self.after(0, lambda: self._show_results(results))
            except Exception as e:
                self.after(0, lambda: (
                    self._status_var.set(f"Error: {e}"),
                    self._spinner_var.set("")
                ))

        threading.Thread(target=search, daemon=True).start()

    # ── display results ────────────────────────────────────────────────────

    def _show_results(self, results):
        self._spinner_var.set("")
        self._results = results
        for w in self._results_scroll.inner.winfo_children():
            w.destroy()

        if not results:
            tk.Label(self._results_scroll.inner,
                     text="No se encontraron mods con esos filtros.",
                     bg=BG, fg=MUTED, font=("Segoe UI Variable Text", 10)).pack(pady=40)
            self._status_var.set("Sin resultados.")
            return

        for i, project in enumerate(results):
            row = _SearchRow(
                self._results_scroll.inner, project,
                on_install=self._install_and_notify,
                on_options=self._on_options,
                even=(i % 2 == 0),
            )
            row.pack(fill="x", pady=(0, 1))

        self._status_var.set(f"{len(results)} resultados encontrados")
        self._on_results(results)

    # ── install ────────────────────────────────────────────────────────────

    def _install_and_notify(self, project):
        self._status_var.set(f"Descargando {project.title}…")
        self._spinner_var.set("⟳")

        mc_filter = None if self._mc_var.get() == "Todas" else self._mc_var.get()
        loader_filter = None if self._loader_var.get() == "Todos" else self._loader_var.get()

        def dl():
            try:
                version = self.app.modrinth_service.get_latest_version(
                    project.project_id,
                    mc_version=mc_filter or self.profile.version_id,
                    loader=loader_filter,
                )
                if not version:
                    self.after(0, lambda: messagebox.showerror(
                        "Error", "No hay versión compatible con este perfil."))
                    return
                self.app.modrinth_service.download_mod_version(
                    version, self.profile.mods_dir)
                self.after(0, lambda: (
                    self._status_var.set(f"{project.title} instalado ✓"),
                    self._spinner_var.set(""),
                    self._on_install(),
                    messagebox.showinfo("Listo", f"{project.title} instalado correctamente.")
                ))
            except Exception as e:
                self.after(0, lambda: (
                    messagebox.showerror("Error de descarga", str(e)),
                    self._spinner_var.set("")
                ))

        threading.Thread(target=dl, daemon=True).start()

    # ── options menu ───────────────────────────────────────────────────────

    def _on_options(self, event, project):
        menu = tk.Menu(self, tearoff=0, bg=BG_CARD, fg=WHITE,
                       activebackground=BG_HOVER, activeforeground=WHITE,
                       font=("Segoe UI Variable Text", 9))
        menu.add_command(label=f"Instalar {project.title}",
                         command=lambda: self._install_and_notify(project))
        menu.add_separator()
        menu.add_command(label="Ver en Modrinth",
                         command=lambda: self._open_url(
                             f"https://modrinth.com/mod/{project.slug}"))
        menu.tk_popup(event.x_root, event.y_root)

    def _open_url(self, url: str):
        import webbrowser
        webbrowser.open(url)