"""
discover_view.py
----------------
Vista de descubrimiento de contenido — estilo Modrinth App.

Características:
- Tabs: Mods | Resource Packs | Data Packs | Shaders
- Lista automática de los más descargados al abrir
- Filtros: versión de MC, loader, categoría, orden
- Búsqueda por texto
- Descarga directa a la carpeta del perfil activo
- Paginación
- Muestra badge "Instalado" si el archivo ya existe en el perfil

Integra con:
  services/modrinth_service.py  — ModrinthService
  managers/profile_manager.py   — ProfileManager (perfil activo)
"""

import os
import threading
import tkinter as tk
from tkinter import messagebox

from services.modrinth_service import ModrinthService, ModrinthError

# ── Paleta (igual que el resto del launcher) ────────────────────────────────
BG          = "#1a1b1e"
BG_CARD     = "#25262b"
BG_SIDEBAR  = "#101113"
BG_INPUT    = "#2c2d31"
BG_HOVER    = "#2f3035"
ACCENT      = "#1bd96a"
ACCENT_DIM  = "#15a050"
TEXT        = "#c1c2c5"
TEXT_BRIGHT = "#ffffff"
TEXT_DIM    = "#6c6f75"
BORDER      = "#373a40"
RED         = "#fa5252"

# ── Categorías por tipo de proyecto ─────────────────────────────────────────
CATEGORIES = {
    "mod": [
        "Todas", "Adventure", "Cursed", "Decoration", "Economy",
        "Equipment", "Food", "Game Mechanics", "Library", "Magic",
        "Optimization", "Storage", "Technology", "Transportation",
        "Utility", "World Generation",
    ],
    "resourcepack": [
        "Todas", "Decoration", "Fonts", "Game Mechanics",
        "Modded", "Realistic", "Simplistic", "Traditional",
    ],
    "datapack": [
        "Todas", "Adventure", "Decoration", "Equipment", "Game Mechanics",
        "Magic", "Technology", "Utility", "World Generation",
    ],
    "shader": [
        "Todas", "Atmosphere", "Cartoon", "Foliage",
        "Path Tracing", "PBR", "Realistic", "Semi-Realistic",
    ],
}

SORT_OPTIONS = {
    "Más descargados": "downloads",
    "Más seguidos":    "follows",
    "Más recientes":   "newest",
    "Relevancia":      "relevance",
}

LOADERS = ["Todos", "fabric", "forge", "neoforge", "quilt", "vanilla"]

PAGE_SIZE = 20


class DiscoverView(tk.Frame):
    """
    Vista principal de descubrimiento de contenido de Modrinth.

    Params
    ------
    parent      : tk widget padre
    app         : instancia de App (accede a modrinth_service y profile_manager)
    """

    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._modrinth: ModrinthService = app.modrinth_service

        # Estado de búsqueda/paginación
        self._current_type   = "mod"
        self._current_page   = 0
        self._total_hits     = 0
        self._results        = []
        self._loading        = False
        self._installed_files: set[str] = set()

        self._build_ui()
        self._refresh_installed_set()
        # Cargar trending al abrir
        self.after(100, self._load_trending)

    # ────────────────────────────────────────────────────────────────────────
    #  BUILD UI
    # ────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Encabezado ──────────────────────────────────────────────────────
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=24, pady=(20, 0))

        tk.Label(
            header, text="Discover content",
            bg=BG, fg=TEXT_BRIGHT,
            font=("Segoe UI", 18, "bold"),
        ).pack(side="left")

        # Badge perfil activo
        self._profile_badge = tk.Label(
            header, text="",
            bg=BG_CARD, fg=ACCENT,
            font=("Segoe UI", 9, "bold"),
            padx=10, pady=4,
            relief="flat",
        )
        self._profile_badge.pack(side="right", padx=(0, 4))
        self._update_profile_badge()

        # ── Tabs de tipo ────────────────────────────────────────────────────
        tabs_frame = tk.Frame(self, bg=BG)
        tabs_frame.pack(fill="x", padx=24, pady=(14, 0))

        self._tab_buttons: dict[str, tk.Label] = {}
        tab_defs = [
            ("mod",          "Mods"),
            ("resourcepack", "Resource Packs"),
            ("datapack",     "Data Packs"),
            ("shader",       "Shaders"),
        ]
        for ptype, label in tab_defs:
            btn = tk.Label(
                tabs_frame, text=label,
                bg=BG, fg=TEXT_DIM,
                font=("Segoe UI", 10, "bold"),
                cursor="hand2",
                padx=14, pady=6,
            )
            btn.pack(side="left", padx=(0, 2))
            btn.bind("<Button-1>", lambda e, t=ptype: self._on_tab_click(t))
            self._tab_buttons[ptype] = btn

        # Separador
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24, pady=(8, 0))

        # ── Barra de búsqueda + filtros ─────────────────────────────────────
        filters_frame = tk.Frame(self, bg=BG)
        filters_frame.pack(fill="x", padx=24, pady=(12, 0))

        # Búsqueda
        search_frame = tk.Frame(filters_frame, bg=BG_INPUT, padx=10, pady=0)
        search_frame.pack(side="left", fill="y")

        tk.Label(search_frame, text="🔍", bg=BG_INPUT, fg=TEXT_DIM,
                 font=("Segoe UI", 11)).pack(side="left")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_changed)
        search_entry = tk.Entry(
            search_frame,
            textvariable=self._search_var,
            bg=BG_INPUT, fg=TEXT_BRIGHT,
            insertbackground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 10),
            width=28,
        )
        search_entry.pack(side="left", ipady=6)
        search_entry.insert(0, "Search mods...")
        search_entry.bind("<FocusIn>",  self._on_search_focus_in)
        search_entry.bind("<FocusOut>", self._on_search_focus_out)
        search_entry.bind("<Return>",   lambda e: self._do_search())

        # Separador vertical
        tk.Frame(filters_frame, bg=BORDER, width=1).pack(side="left", fill="y", padx=8)

        # Sort
        self._sort_var = tk.StringVar(value="Más descargados")
        self._build_dropdown(filters_frame, "Ordenar:", self._sort_var,
                             list(SORT_OPTIONS.keys()), width=17)

        # Loader
        self._loader_var = tk.StringVar(value="Todos")
        self._loader_dropdown_widget = self._build_dropdown(
            filters_frame, "Loader:", self._loader_var, LOADERS, width=12)

        # Categoría
        self._category_var = tk.StringVar(value="Todas")
        self._cat_label_widget, self._cat_menu_widget = self._build_dropdown(
            filters_frame, "Categoría:", self._category_var,
            CATEGORIES["mod"], width=18, return_both=True)

        # Botón buscar
        search_btn = tk.Label(
            filters_frame, text="Buscar",
            bg=ACCENT, fg=BG,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
            padx=14, pady=7,
        )
        search_btn.pack(side="left", padx=(10, 0))
        search_btn.bind("<Button-1>", lambda e: self._do_search())
        search_btn.bind("<Enter>", lambda e: search_btn.config(bg=ACCENT_DIM))
        search_btn.bind("<Leave>", lambda e: search_btn.config(bg=ACCENT))

        # ── Chips de filtros activos (versión MC + loader del perfil) ────────
        chips_frame = tk.Frame(self, bg=BG)
        chips_frame.pack(fill="x", padx=24, pady=(8, 0))
        self._chips_frame = chips_frame
        self._rebuild_chips()

        # ── Área principal: lista de resultados ─────────────────────────────
        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True, padx=24, pady=(10, 0))

        # Panel izquierdo: lista
        left = tk.Frame(content, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        # Status bar
        status_frame = tk.Frame(left, bg=BG)
        status_frame.pack(fill="x", pady=(0, 6))

        self._status_var = tk.StringVar(value="Cargando contenido popular…")
        tk.Label(
            status_frame, textvariable=self._status_var,
            bg=BG, fg=TEXT_DIM,
            font=("Segoe UI", 9),
        ).pack(side="left")

        self._page_label = tk.Label(
            status_frame, text="",
            bg=BG, fg=TEXT_DIM,
            font=("Segoe UI", 9),
        )
        self._page_label.pack(side="right")

        # Scrollable canvas para la lista
        canvas_frame = tk.Frame(left, bg=BG)
        canvas_frame.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(canvas_frame, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical",
                                 command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._list_frame = tk.Frame(self._canvas, bg=BG)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._list_frame, anchor="nw"
        )
        self._list_frame.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # ── Paginación ───────────────────────────────────────────────────────
        page_frame = tk.Frame(self, bg=BG)
        page_frame.pack(fill="x", padx=24, pady=(6, 16))

        self._prev_btn = self._page_btn(page_frame, "← Anterior",
                                        self._prev_page)
        self._prev_btn.pack(side="left")

        self._page_info_var = tk.StringVar(value="")
        tk.Label(
            page_frame, textvariable=self._page_info_var,
            bg=BG, fg=TEXT_DIM,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=16)

        self._next_btn = self._page_btn(page_frame, "Siguiente →",
                                        self._next_page)
        self._next_btn.pack(side="left")

        self._update_tab_styles()

    # ── Helpers de UI ───────────────────────────────────────────────────────

    def _build_dropdown(self, parent, label_text, var, options,
                        width=14, return_both=False):
        frame = tk.Frame(parent, bg=BG)
        frame.pack(side="left", padx=(0, 8))
        lbl = tk.Label(frame, text=label_text, bg=BG, fg=TEXT_DIM,
                       font=("Segoe UI", 9))
        lbl.pack(side="left", padx=(0, 4))
        menu_btn = tk.Menubutton(
            frame, textvariable=var,
            bg=BG_INPUT, fg=TEXT_BRIGHT,
            activebackground=BG_HOVER, activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 9),
            width=width,
            indicatoron=True,
            padx=8, pady=5,
        )
        menu = tk.Menu(menu_btn, tearoff=0, bg=BG_CARD, fg=TEXT,
                       activebackground=BG_HOVER, activeforeground=TEXT_BRIGHT,
                       font=("Segoe UI", 9))
        for opt in options:
            menu.add_command(
                label=opt,
                command=lambda v=opt: var.set(v),
            )
        menu_btn.configure(menu=menu)
        menu_btn.pack(side="left")
        if return_both:
            return lbl, menu_btn
        return menu_btn

    def _page_btn(self, parent, text, cmd):
        btn = tk.Label(
            parent, text=text,
            bg=BG_CARD, fg=TEXT,
            font=("Segoe UI", 9),
            cursor="hand2",
            padx=12, pady=5,
        )
        btn.bind("<Button-1>", lambda e: cmd())
        btn.bind("<Enter>", lambda e: btn.config(bg=BG_HOVER))
        btn.bind("<Leave>", lambda e: btn.config(bg=BG_CARD))
        return btn

    # ── Scroll ───────────────────────────────────────────────────────────────

    def _on_frame_configure(self, event):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ────────────────────────────────────────────────────────────────────────
    #  ESTADO / PERFIL
    # ────────────────────────────────────────────────────────────────────────

    def _active_profile(self):
        """Devuelve el perfil activo o None."""
        try:
            return self.app.profile_manager.get_active_profile()
        except Exception:
            pass
        # Fallback: primer perfil disponible
        try:
            profiles = self.app.profile_manager.get_all_profiles()
            return profiles[0] if profiles else None
        except Exception:
            return None

    def _update_profile_badge(self):
        profile = self._active_profile()
        if profile:
            loader = getattr(profile, "loader_type", "vanilla") or "vanilla"
            self._profile_badge.config(
                text=f"  {profile.name}  ·  {profile.version_id}  ·  {loader}  "
            )
        else:
            self._profile_badge.config(text="  Sin perfil activo  ")

    def _refresh_installed_set(self):
        self._installed_files = set()
        profile = self._active_profile()
        print(f"[DEBUG] profile={profile}")
        if not profile:
            return
        try:
            from managers.mod_manager import ModManager
            mods = ModManager(profile).list_mods()
            print(f"[DEBUG] mods encontrados={[m.filename for m in mods]}")
            for mod in mods:
                self._installed_files.add(mod.display_name.lower())
                self._installed_files.add(mod.filename.lower())
        except Exception as e:
            print(f"[DEBUG] error={e}")
        print(f"[DEBUG] installed_files={self._installed_files}")
    

    def _rebuild_chips(self):
        for w in self._chips_frame.winfo_children():
            w.destroy()
        profile = self._active_profile()
        if not profile:
            return
        chips = []
        if profile.version_id:
            chips.append(profile.version_id)
        loader = getattr(profile, "loader_type", None)
        if loader and loader != "vanilla":
            chips.append(loader.capitalize())
        for chip_text in chips:
            chip = tk.Label(
                self._chips_frame, text=f"  {chip_text}  ",
                bg=BG_CARD, fg=TEXT,
                font=("Segoe UI", 8, "bold"),
                padx=2, pady=3,
                relief="flat",
            )
            chip.pack(side="left", padx=(0, 4))

    # ────────────────────────────────────────────────────────────────────────
    #  TABS
    # ────────────────────────────────────────────────────────────────────────

    def _on_tab_click(self, ptype: str):
        if ptype == self._current_type:
            return
        self._current_type = ptype
        self._current_page = 0
        self._search_var.set("")
        self._category_var.set("Todas")
        # Actualizar opciones de categoría
        cats = CATEGORIES.get(ptype, ["Todas"])
        self._rebuild_category_menu(cats)
        # Ocultar loader para shaders (no aplica)
        if ptype == "shader":
            self._loader_var.set("Todos")
        self._update_tab_styles()
        self._load_trending()

    def _rebuild_category_menu(self, cats):
        self._category_var.set("Todas")
        menu = tk.Menu(
            self._cat_menu_widget, tearoff=0,
            bg=BG_CARD, fg=TEXT,
            activebackground=BG_HOVER, activeforeground=TEXT_BRIGHT,
            font=("Segoe UI", 9),
        )
        for opt in cats:
            menu.add_command(
                label=opt,
                command=lambda v=opt: self._category_var.set(v),
            )
        self._cat_menu_widget.configure(menu=menu)

    def _update_tab_styles(self):
        for ptype, btn in self._tab_buttons.items():
            if ptype == self._current_type:
                btn.config(
                    fg=ACCENT,
                    bg=BG,
                    relief="flat",
                    font=("Segoe UI", 10, "bold"),
                )
                # Subrayado verde simulado
                btn.config(pady=6)
            else:
                btn.config(fg=TEXT_DIM, bg=BG, relief="flat",
                           font=("Segoe UI", 10, "bold"), pady=6)

    # ────────────────────────────────────────────────────────────────────────
    #  BÚSQUEDA / CARGA
    # ────────────────────────────────────────────────────────────────────────

    def _on_search_focus_in(self, event):
        if event.widget.get() == "Search mods...":
            event.widget.delete(0, "end")
            event.widget.config(fg=TEXT_BRIGHT)

    def _on_search_focus_out(self, event):
        if not event.widget.get().strip():
            event.widget.insert(0, "Search mods...")
            event.widget.config(fg=TEXT_DIM)

    def _on_search_changed(self, *_):
            # Búsqueda automática con debounce ligero
        if hasattr(self, "_search_after_id"):
                self.after_cancel(self._search_after_id)
                self._search_after_id = self.after(600, self._do_search)

    def _do_search(self):
        self._current_page = 0
        self._fetch_results()

    def _load_trending(self):
        """Carga los más descargados sin texto de búsqueda."""
        self._sort_var.set("Más descargados")
        self._fetch_results()

    def _get_facets(self) -> list:
        """Construye la lista de facets para la API de Modrinth."""
        facets = [[f"project_type:{self._current_type}"]]
        profile = self._active_profile()
        # Versión MC — del perfil activo salvo que el usuario haya buscado algo genérico
        if profile and profile.version_id:
            facets.append([f"versions:{profile.version_id}"])
        # Loader (sólo para mods)
        loader_val = self._loader_var.get()
        if loader_val not in ("Todos", "vanilla") and self._current_type == "mod":
            facets.append([f"categories:{loader_val}"])
        elif (self._current_type == "mod" and profile):
            loader = getattr(profile, "loader_type", None)
            if loader and loader not in ("vanilla", ""):
                facets.append([f"categories:{loader}"])
        # Categoría
        cat = self._category_var.get()
        if cat and cat != "Todas":
            facets.append([f"categories:{cat.lower()}"])
        return facets

    def _fetch_results(self):
        if self._loading:
            return
        self._loading = True
        self._status_var.set("Cargando…")
        self._clear_list()

        query  = self._search_var.get().strip()
        if query == "Search mods...":
            query = ""
        sort   = SORT_OPTIONS.get(self._sort_var.get(), "downloads")
        facets = self._get_facets()
        offset = self._current_page * PAGE_SIZE

        def _worker():
            try:
                import json
                import urllib.request
                import urllib.parse
                from config.constants import (
                    MODRINTH_API_BASE_URL,
                    HTTP_TIMEOUT_SECONDS,
                    USER_AGENT,
                )
                params = {
                    "query":  query,
                    "limit":  PAGE_SIZE,
                    "offset": offset,
                    "index":  sort,
                    "facets": json.dumps(facets),
                }
                url = (f"{MODRINTH_API_BASE_URL}/search?"
                    f"{urllib.parse.urlencode(params)}")
                req = urllib.request.Request(
                    url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as r:
                    data = json.loads(r.read().decode("utf-8"))

                hits  = data.get("hits", [])
                total = data.get("total_hits", len(hits))
                self.after(0, lambda: self._show_results(hits, total))
            except Exception as exc:
                self.after(0, lambda: self._on_fetch_error(str(exc)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_fetch_error(self, msg: str):
        self._loading = False  # ← desbloquea para el próximo intento
        self._status_var.set(f"Error: {msg} — haz clic en Buscar para reintentar")

    def _show_results(self, hits: list, total: int):
        self._loading  = False
        self._results  = hits
        self._total_hits = total
        total_pages    = max(1, -(-total // PAGE_SIZE))  # ceil division
        current        = self._current_page + 1

        self._status_var.set(f"{total:,} resultados encontrados")
        self._page_info_var.set(f"Página {current} de {total_pages}")
        self._prev_btn.config(state="normal" if self._current_page > 0 else "disabled")
        self._next_btn.config(
            state="normal" if self._current_page < total_pages - 1 else "disabled"
        )
        self._refresh_installed_set()
        self._render_results(hits)

    def _on_fetch_error(self, msg: str):
        self._loading = False
        self._status_var.set(f"Error: {msg}")

    # ────────────────────────────────────────────────────────────────────────
    #  RENDER
    # ────────────────────────────────────────────────────────────────────────

    def _clear_list(self):
        for w in self._list_frame.winfo_children():
            w.destroy()

    def _render_results(self, hits: list):
        self._clear_list()
        if not hits:
            tk.Label(
                self._list_frame,
                text="No se encontraron resultados.",
                bg=BG, fg=TEXT_DIM,
                font=("Segoe UI", 11),
            ).pack(pady=40)
            return

        for hit in hits:
            self._render_card(hit)

    def _render_card(self, hit: dict):
        project_id   = hit.get("project_id", hit.get("id", ""))
        title        = hit.get("title", "Sin título")
        description  = hit.get("description", "")
        downloads    = hit.get("downloads", 0)
        follows      = hit.get("follows", 0)
        categories   = hit.get("categories", [])
        date_mod     = hit.get("date_modified", "")[:10]
        icon_url     = hit.get("icon_url", "")
        client_side  = hit.get("client_side", "")
        server_side  = hit.get("server_side", "")

        # Detectar si está instalado
        mods_dir    = ""
        profile     = self._active_profile()
        # DESPUÉS — compara el título del proyecto contra display_names reales
        is_installed = False
        if profile and self._installed_files:
            title_lower = title.lower()
            for installed_name in self._installed_files:
                # Coincidencia si el título está contenido en el nombre del .jar
                # o viceversa (cubre "Sodium" vs "sodium-mc1.21.1-0.6.0-fabric.jar")
                if title_lower in installed_name or installed_name.startswith(title_lower):
                    is_installed = True
                    break

        # ── Card frame ──────────────────────────────────────────────────────
        card = tk.Frame(self._list_frame, bg=BG_CARD, pady=0)
        card.pack(fill="x", pady=(0, 2))

        inner = tk.Frame(card, bg=BG_CARD)
        inner.pack(fill="x", padx=16, pady=12)

        # Icono placeholder
        icon_frame = tk.Frame(inner, bg=BG_INPUT, width=52, height=52)
        icon_frame.pack(side="left", padx=(0, 14))
        icon_frame.pack_propagate(False)
        icon_lbl = tk.Label(icon_frame, text="📦", bg=BG_INPUT,
                            font=("Segoe UI", 22))
        icon_lbl.pack(expand=True)

        # Carga icono en hilo si hay URL
        if icon_url:
            threading.Thread(
                target=self._load_icon,
                args=(icon_url, icon_lbl),
                daemon=True,
            ).start()

        # ── Info central ────────────────────────────────────────────────────
        info = tk.Frame(inner, bg=BG_CARD)
        info.pack(side="left", fill="both", expand=True)

        # Título
        title_row = tk.Frame(info, bg=BG_CARD)
        title_row.pack(fill="x")
        tk.Label(
            title_row, text=title,
            bg=BG_CARD, fg=TEXT_BRIGHT,
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        ).pack(side="left")

        # Descripción
        desc_text = description[:120] + "…" if len(description) > 120 else description
        tk.Label(
            info, text=desc_text,
            bg=BG_CARD, fg=TEXT_DIM,
            font=("Segoe UI", 9),
            anchor="w", justify="left",
            wraplength=560,
        ).pack(fill="x", pady=(2, 4))

        # Chips de categorías + compatibilidad
        tags_row = tk.Frame(info, bg=BG_CARD)
        tags_row.pack(fill="x")

        if client_side in ("required", "optional"):
            self._chip(tags_row, "Client", BG_INPUT)
        if server_side in ("required", "optional"):
            self._chip(tags_row, "Server", BG_INPUT)
        for cat in categories[:4]:
            self._chip(tags_row, cat.capitalize(), BG_INPUT)

        # ── Estadísticas ────────────────────────────────────────────────────
        stats = tk.Frame(info, bg=BG_CARD)
        stats.pack(fill="x", pady=(4, 0))

        tk.Label(
            stats,
            text=f"⬇ {downloads:,}   ♥ {follows:,}   🕒 {date_mod}",
            bg=BG_CARD, fg=TEXT_DIM,
            font=("Segoe UI", 8),
        ).pack(side="left")

        # ── Botón instalar / instalado ───────────────────────────────────────
        right = tk.Frame(inner, bg=BG_CARD)
        right.pack(side="right", padx=(12, 0))

        if is_installed:
            tk.Label(
                right, text="✓ Instalado",
                bg=BG_CARD, fg=ACCENT,
                font=("Segoe UI", 9, "bold"),
                padx=14, pady=7,
            ).pack()
        else:
            install_btn = tk.Label(
                right, text="Instalar",
                bg=ACCENT, fg=BG,
                font=("Segoe UI", 9, "bold"),
                cursor="hand2",
                padx=14, pady=7,
            )
            install_btn.pack()
            install_btn.bind(
                "<Button-1>",
                lambda e, pid=project_id, t=title, b=install_btn: (
                    self._install_project(pid, t, b)
                ),
            )
            install_btn.bind("<Enter>",
                             lambda e, b=install_btn: b.config(bg=ACCENT_DIM))
            install_btn.bind("<Leave>",
                             lambda e, b=install_btn: b.config(bg=ACCENT))

        # Hover highlight + click para detalle
        for widget in (card, inner, info, stats, tags_row):
            widget.bind("<Enter>",
                        lambda e, c=card: c.config(bg=BG_HOVER))
            widget.bind("<Leave>",
                        lambda e, c=card: c.config(bg=BG_CARD))
            widget.bind("<Button-1>",
                        lambda e, pid=project_id, h=hit: self._open_detail(pid, h))

    def _chip(self, parent, text, bg_color):
        tk.Label(
            parent, text=f" {text} ",
            bg=bg_color, fg=TEXT_DIM,
            font=("Segoe UI", 7, "bold"),
            padx=4, pady=2,
        ).pack(side="left", padx=(0, 3))

    # ────────────────────────────────────────────────────────────────────────
    #  ICONOS
    # ────────────────────────────────────────────────────────────────────────

    def _load_icon(self, url: str, label: tk.Label):
        """Descarga y muestra el icono del mod (requiere Pillow)."""
        try:
            import urllib.request as _req
            import io
            from PIL import Image, ImageTk

            with _req.urlopen(url, timeout=5) as resp:
                data = resp.read()

            img = Image.open(io.BytesIO(data)).resize((48, 48), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            # Guardar referencia para evitar garbage collection
            label._photo = photo
            self.after(0, lambda: label.config(image=photo, text=""))
        except Exception:
            pass  # Si Pillow no está o falla la red, queda el emoji

    # ────────────────────────────────────────────────────────────────────────
    #  INSTALACIÓN
    # ────────────────────────────────────────────────────────────────────────

    def _install_project(self, project_id: str, title: str, btn: tk.Label):
        profile = self._active_profile()
        if not profile:
            messagebox.showwarning(
                "Sin perfil",
                "No hay ningún perfil activo.\n"
                "Crea o selecciona un perfil antes de instalar contenido.",
            )
            return

        # ── Carpeta destino según tipo de contenido ──────────────────────────
        dest_dir = self._get_install_dir(profile)
        if not dest_dir:
            messagebox.showerror("Error", "El perfil no tiene carpeta de mods configurada.")
            return

        btn.config(text="Descargando…", bg=BG_CARD, fg=TEXT_DIM, cursor="arrow")
        btn.unbind("<Button-1>")

        mc_version = profile.version_id
        loader = getattr(profile, "loader_type", None)
        loader = None if loader in ("vanilla", "", None) else loader

        def _worker():
            try:
                version = self._modrinth.get_latest_version(
                    project_id,
                    mc_version=mc_version,
                    loader=loader,
                )
                if not version:
                    version = self._modrinth.get_latest_version(
                        project_id, mc_version=mc_version)
                if not version:
                    self.after(0, lambda: self._on_install_error(
                        btn, f"No hay versión compatible con {mc_version}."))
                    return

                dest_path = self._modrinth.download_mod_version(version, dest_dir)
                self.after(0, lambda: self._on_install_done(btn, title, dest_path))
            except ModrinthError as exc:
                self.after(0, lambda: self._on_install_error(btn, str(exc)))
            except Exception as exc:
                self.after(0, lambda: self._on_install_error(btn, str(exc)))

        threading.Thread(target=_worker, daemon=True).start()

    def _get_install_dir(self, profile) -> str | None:
        """Devuelve la carpeta de instalación correcta según el tipo de contenido activo."""
        base = getattr(profile, "game_dir", None)
        mods_dir = getattr(profile, "mods_dir", None)

        if self._current_type == "mod":
            return mods_dir

        if not base:
            # Fallback: derivar desde mods_dir subiendo un nivel
            if mods_dir:
                base = os.path.dirname(mods_dir)
            else:
                return None

        mapping = {
            "resourcepack": os.path.join(base, "resourcepacks"),
            "datapack":     os.path.join(base, "datapacks"),
            "shader":       os.path.join(base, "shaderpacks"),
        }
        dest = mapping.get(self._current_type)
        if dest:
            os.makedirs(dest, exist_ok=True)
        return dest

    def _on_install_done(self, btn: tk.Label, title: str, dest_path: str):
        btn.config(text="✓ Instalado", bg=BG_CARD, fg=ACCENT, cursor="arrow")
        filename = os.path.basename(dest_path)
        name_no_ext = filename.lower().replace(".jar", "").replace(".disabled", "")
        self._installed_files.add(filename.lower())
        self._installed_files.add(name_no_ext)

    def _on_install_error(self, btn: tk.Label, msg: str):
        btn.config(text="Instalar", bg=ACCENT, fg=BG, cursor="hand2")
        messagebox.showerror("Error al instalar", msg)

    # ────────────────────────────────────────────────────────────────────────
    #  PAGINACIÓN
    # ────────────────────────────────────────────────────────────────────────

    def _prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._fetch_results()
            self._canvas.yview_moveto(0)

    def _next_page(self):
        total_pages = max(1, -(-self._total_hits // PAGE_SIZE))
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._fetch_results()
            self._canvas.yview_moveto(0)

    def _open_detail(self, project_id: str, hit: dict):
            profile = self._active_profile()
            if not profile:
                messagebox.showwarning("Sin perfil",
                    "Selecciona un perfil antes de ver detalles.")
                return
            ModDetailPanel(self, self.app, project_id, hit, profile,
                        on_install_done=self._refresh_installed_set)

class ModDetailPanel(tk.Toplevel):
    """
    Ventana de detalle de un proyecto de Modrinth.
    Muestra descripción completa, lista de versiones y changelog.
    Click en una versión carga su changelog.
    Botón instala la versión seleccionada con el loader del perfil.
    """

    def __init__(self, parent, app, project_id: str, hit: dict,
                 profile, on_install_done=None):
        super().__init__(parent)
        self.app             = app
        self.project_id      = project_id
        self.hit             = hit
        self.profile         = profile
        self.on_install_done = on_install_done
        self._versions       = []
        self._modrinth       = app.modrinth_service

        title = hit.get("title", "Mod")
        self.title(title)
        self.geometry("740x560")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.grab_set()

        self._build()
        self._load_versions()

    # ── Layout ───────────────────────────────────────────────────────────

    def _build(self):
        hit = self.hit

        # ── Header ──────────────────────────────────────────────────────
        header = tk.Frame(self, bg=BG_SIDEBAR, padx=20, pady=14)
        header.pack(fill="x")

        # Icono
        icon_frame = tk.Frame(header, bg=BG_INPUT, width=54, height=54)
        icon_frame.pack(side="left")
        icon_frame.pack_propagate(False)
        self._icon_lbl = tk.Label(icon_frame, text="📦", bg=BG_INPUT,
                                   font=("Segoe UI", 24))
        self._icon_lbl.pack(expand=True)
        icon_url = hit.get("icon_url", "")
        if icon_url:
            threading.Thread(target=self._load_icon,
                             args=(icon_url,), daemon=True).start()

        # Texto header
        hinfo = tk.Frame(header, bg=BG_SIDEBAR, padx=14)
        hinfo.pack(side="left", fill="x", expand=True)

        tk.Label(hinfo, text=hit.get("title", ""),
                 bg=BG_SIDEBAR, fg=TEXT_BRIGHT,
                 font=("Segoe UI", 14, "bold"), anchor="w").pack(fill="x")

        desc = hit.get("description", "")
        tk.Label(hinfo, text=desc,
                 bg=BG_SIDEBAR, fg=TEXT_DIM,
                 font=("Segoe UI", 9), anchor="w",
                 wraplength=460, justify="left").pack(fill="x")

        # Stats
        dl  = hit.get("downloads", 0)
        flw = hit.get("follows", 0)
        tk.Label(hinfo, text=f"⬇ {dl:,}   ♥ {flw:,}",
                 bg=BG_SIDEBAR, fg=ACCENT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(4, 0))

        # Perfil activo badge
        loader = getattr(self.profile, "loader_type", "vanilla") or "vanilla"
        tk.Label(header,
                 text=f"  {self.profile.name} · {self.profile.version_id} · {loader}  ",
                 bg=BG_CARD, fg=ACCENT,
                 font=("Segoe UI", 8, "bold"),
                 padx=6, pady=4).pack(side="right", anchor="ne")

        # ── Tabs ─────────────────────────────────────────────────────────
        tab_bar = tk.Frame(self, bg=BG_SIDEBAR)
        tab_bar.pack(fill="x")

        self._tab_btns = {}
        self._active_tab = "versions"
        for key, label in [("versions", "Versiones"), ("changelog", "Changelog")]:
            b = tk.Label(tab_bar, text=f"  {label}  ",
                         bg=BG_SIDEBAR, fg=TEXT_DIM,
                         font=("Segoe UI", 10, "bold"),
                         cursor="hand2", pady=8)
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, k=key: self._switch_tab(k))
            self._tab_btns[key] = b

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # ── Área de contenido ────────────────────────────────────────────
        # Bottom bar ANTES del content area para que no quede tapado
        bottom = tk.Frame(self, bg=BG_SIDEBAR, padx=16, pady=10)
        bottom.pack(fill="x", side="bottom")

        self._status_var = tk.StringVar(value="Cargando versiones…")
        tk.Label(bottom, textvariable=self._status_var,
                 bg=BG_SIDEBAR, fg=TEXT_DIM,
                 font=("Segoe UI", 9)).pack(side="left")

        self._install_btn = tk.Label(
            bottom, text="⬇  Instalar versión seleccionada",
            bg=ACCENT, fg=BG,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2", padx=14, pady=7,
        )
        self._install_btn.pack(side="right")
        self._install_btn.bind("<Button-1>", lambda e: self._on_install())
        self._install_btn.bind("<Enter>",
            lambda e: self._install_btn.config(bg=ACCENT_DIM))
        self._install_btn.bind("<Leave>",
            lambda e: self._install_btn.config(bg=ACCENT))

        self._content_area = tk.Frame(self, bg=BG)
        self._content_area.pack(fill="both", expand=True)

        # Panel versiones
        self._versions_panel = tk.Frame(self._content_area, bg=BG)

        cols = ("Nombre", "MC", "Loaders", "Fecha")
        self._vtree_frame = tk.Frame(self._versions_panel, bg=BG)
        self._vtree_frame.pack(fill="both", expand=True, padx=12, pady=10)

        from tkinter import ttk
        self._vtree = ttk.Treeview(self._vtree_frame, columns=cols,
                                   show="headings", height=12)
        for col, w in zip(cols, [190, 80, 160, 110]):
            self._vtree.heading(col, text=col)
            self._vtree.column(col, width=w, anchor="w")
        vsb = ttk.Scrollbar(self._vtree_frame, orient="vertical",
                             command=self._vtree.yview)
        self._vtree.configure(yscrollcommand=vsb.set)
        self._vtree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")
        # Click en versión → cargar su changelog si la tab está visible
        self._vtree.bind("<<TreeviewSelect>>", self._on_version_select)

        # Panel changelog
        self._changelog_panel = tk.Frame(self._content_area, bg=BG)
        self._cl_text = tk.Text(self._changelog_panel,
                                bg=BG_SIDEBAR, fg=TEXT,
                                relief="flat", font=("Consolas", 9),
                                wrap="word", state="disabled",
                                padx=14, pady=12)
        cl_vsb = tk.Scrollbar(self._changelog_panel, orient="vertical",
                               command=self._cl_text.yview)
        self._cl_text.configure(yscrollcommand=cl_vsb.set)
        self._cl_text.pack(side="left", fill="both",
                           expand=True, padx=(12, 0), pady=10)
        cl_vsb.pack(side="left", fill="y", pady=10)

        self._switch_tab("versions")

    # ── Tabs ─────────────────────────────────────────────────────────────

    def _switch_tab(self, key: str):
        self._active_tab = key
        for k, b in self._tab_btns.items():
            if k == key:
                b.config(fg=ACCENT, font=("Segoe UI", 10, "bold"))
            else:
                b.config(fg=TEXT_DIM, font=("Segoe UI", 10))

        self._versions_panel.pack_forget()
        self._changelog_panel.pack_forget()

        if key == "versions":
            self._versions_panel.pack(fill="both", expand=True)
        else:
            self._changelog_panel.pack(fill="both", expand=True)
            # Cargar changelog de la versión seleccionada
            self._load_changelog_for_selected()

    # ── Carga de datos ───────────────────────────────────────────────────

    def _load_versions(self):
        loader = getattr(self.profile, "loader_type", None)
        loader = None if loader in ("vanilla", "", None) else loader

        def fetch():
            try:
                versions = self._modrinth.get_project_versions(
                    self.project_id,
                    mc_version=self.profile.version_id,
                    loader=loader,
                )
                # Fallback sin loader si no hay resultados
                if not versions:
                    versions = self._modrinth.get_project_versions(
                        self.project_id,
                        mc_version=self.profile.version_id,
                    )
                self.after(0, lambda: self._populate_versions(versions))
            except Exception as e:
                self.after(0, lambda: self._status_var.set(f"Error: {e}"))

        threading.Thread(target=fetch, daemon=True).start()

    def _populate_versions(self, versions):
        self._versions = versions
        self._vtree.delete(*self._vtree.get_children())

        profile_loader = getattr(self.profile, "loader_type", "vanilla") or "vanilla"

        for v in versions:
            mc      = ", ".join(v.game_versions[:3]) if v.game_versions else "—"
            loaders = ", ".join(v.loaders)           if v.loaders       else "—"
            date    = v.date_published[:10]          if v.date_published else "—"
            name    = v.name or v.version_number

            # Determinar compatibilidad con el loader del perfil
            compatible = self._is_compatible(v, profile_loader)
            tag = "compatible" if compatible else "incompatible"

            self._vtree.insert("", "end", iid=v.version_id,
                               values=(name, mc, loaders, date),
                               tags=(tag,))

        # Estilos visuales
        self._vtree.tag_configure("compatible",   foreground=TEXT_BRIGHT)
        self._vtree.tag_configure("incompatible", foreground=TEXT_DIM)

        n = len(versions)
        self._status_var.set(
            f"{n} versión{'es' if n != 1 else ''} — "
            f"loader del perfil: {profile_loader}"
        )

        # Seleccionar la primera versión compatible automáticamente
        first_compatible = next(
            (v for v in versions if self._is_compatible(v, profile_loader)), None
        )
        if first_compatible:
            self._vtree.selection_set(first_compatible.version_id)
            self._vtree.see(first_compatible.version_id)
        elif versions:
            self._vtree.selection_set(versions[0].version_id)
            self._vtree.see(versions[0].version_id)

        self._update_install_btn()

    def _is_compatible(self, version, profile_loader: str) -> bool:
        """True si la versión es compatible con el loader del perfil."""
        if profile_loader in ("vanilla", "", None):
            # Vanilla: compatible si no requiere ningún loader específico
            return not version.loaders or "minecraft" in version.loaders
        return profile_loader.lower() in [l.lower() for l in version.loaders]

    def _on_version_select(self, _event=None):
        self._update_install_btn()
        if self._active_tab == "changelog":
            self._load_changelog_for_selected()

    def _update_install_btn(self):
        """Habilita o bloquea el botón según compatibilidad de la versión seleccionada."""
        selected = self._vtree.selection()
        if not selected:
            self._install_btn.config(
                text="Selecciona una versión",
                bg=BG_CARD, fg=TEXT_DIM, cursor="arrow")
            self._install_btn.unbind("<Button-1>")
            return

        vid     = selected[0]
        version = next((v for v in self._versions if v.version_id == vid), None)
        if not version:
            return

        profile_loader = getattr(self.profile, "loader_type", "vanilla") or "vanilla"
        compatible     = self._is_compatible(version, profile_loader)

        if compatible:
            self._install_btn.config(
                text="⬇  Instalar versión seleccionada",
                bg=ACCENT, fg=BG, cursor="hand2")
            self._install_btn.bind("<Button-1>", lambda e: self._on_install())
            self._install_btn.bind("<Enter>",
                lambda e: self._install_btn.config(bg=ACCENT_DIM))
            self._install_btn.bind("<Leave>",
                lambda e: self._install_btn.config(bg=ACCENT))
        else:
            loaders_str = ", ".join(version.loaders) if version.loaders else "desconocido"
            self._install_btn.config(
                text=f"✗  Requiere {loaders_str}",
                bg=RED, fg=TEXT_BRIGHT, cursor="arrow")
            self._install_btn.unbind("<Button-1>")
            self._install_btn.unbind("<Enter>")
            self._install_btn.unbind("<Leave>")

    def _load_changelog_for_selected(self):
        selected = self._vtree.selection()
        if not selected:
            self._set_changelog("Selecciona una versión para ver el changelog.")
            return
        vid     = selected[0]
        version = next((v for v in self._versions if v.version_id == vid), None)
        if not version:
            return

        # ModrinthVersion puede no tener changelog si vino de búsqueda general
        changelog = getattr(version, "changelog", None)
        if changelog is not None:
            self._set_changelog(changelog or "Sin changelog disponible.")
            return

        # Fetch específico de la versión para obtener el changelog
        def fetch():
            try:
                import json, urllib.request
                from config.constants import MODRINTH_API_BASE_URL, HTTP_TIMEOUT_SECONDS, USER_AGENT
                url = f"{MODRINTH_API_BASE_URL}/version/{vid}"
                req = urllib.request.Request(
                    url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as r:
                    data = json.loads(r.read().decode())
                cl = data.get("changelog") or "Sin changelog disponible."
                # Cachear en el objeto
                version.changelog = cl
                self.after(0, lambda: self._set_changelog(cl))
            except Exception as ex:
                self.after(0, lambda: self._set_changelog(f"Error cargando changelog: {ex}"))

        self._set_changelog("Cargando changelog…")
        threading.Thread(target=fetch, daemon=True).start()

    def _set_changelog(self, text: str):
        self._cl_text.configure(state="normal")
        self._cl_text.delete("1.0", "end")
        self._cl_text.insert("end", text)
        self._cl_text.configure(state="disabled")

    # ── Instalación ──────────────────────────────────────────────────────

    def _on_install(self):
        selected = self._vtree.selection()
        if not selected:
            messagebox.showwarning("Aviso",
                "Selecciona una versión de la lista para instalar.")
            return
        vid     = selected[0]
        version = next((v for v in self._versions if v.version_id == vid), None)
        if not version:
            return

        self._install_btn.config(
            text="Descargando…", bg=BG_CARD, fg=TEXT_DIM, cursor="arrow")
        self._install_btn.unbind("<Button-1>")
        self._status_var.set(f"Descargando {version.name or version.version_number}…")

        dest_dir = getattr(self.profile, "mods_dir", None)
        if not dest_dir:
            messagebox.showerror("Error",
                "El perfil no tiene carpeta de mods configurada.")
            return

        def download():
            try:
                self._modrinth.download_mod_version(version, dest_dir)
                self.after(0, self._on_done)
            except Exception as ex:
                err = str(ex)
                self.after(0, lambda: self._on_error(err))

        threading.Thread(target=download, daemon=True).start()

    def _on_done(self):
        self._status_var.set("✓ Mod instalado correctamente")
        self._install_btn.config(
            text="✓ Instalado", bg=BG_CARD, fg=ACCENT, cursor="arrow")
        if self.on_install_done:
            self.on_install_done()
        messagebox.showinfo("Listo", "Mod instalado correctamente.")
        self.destroy()

    def _on_error(self, err: str):
        self._status_var.set("Error en la descarga")
        self._install_btn.config(
            text="⬇  Instalar versión seleccionada",
            bg=ACCENT, fg=BG, cursor="hand2")
        self._install_btn.bind("<Button-1>", lambda e: self._on_install())
        messagebox.showerror("Error al instalar", err)

    # ── Icono ────────────────────────────────────────────────────────────

    def _load_icon(self, url: str):
        try:
            import urllib.request as _req, io
            from PIL import Image, ImageTk
            with _req.urlopen(url, timeout=5) as resp:
                data = resp.read()
            img   = Image.open(io.BytesIO(data)).resize((52, 52), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._icon_lbl._photo = photo
            self.after(0, lambda: self._icon_lbl.config(image=photo, text=""))
        except Exception:
            pass

    # ── Llamar cuando el usuario cambia de perfil desde otro panel ──────────
    def on_profile_changed(self):
        """Notificar desde app.py cuando el perfil activo cambie."""
        self._update_profile_badge()
        self._rebuild_chips()
        self._refresh_installed_set()
        self._current_page = 0
        self._fetch_results()