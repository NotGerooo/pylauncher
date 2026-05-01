"""
gui/views/settings_view.py — Settings estilo Modrinth
Ventana flotante con blur, sidebar de pestañas y contenido dinámico.
"""
import platform
import flet as ft

from gui.theme import (
    BG, CARD_BG, CARD2_BG, INPUT_BG, BORDER,
    GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV,
)
from utils.logger import get_logger

log = get_logger()

# ── Colores internos del modal ──────────────────────────────────────────────
_MODAL_BG   = "#18181b"
_SIDEBAR_BG = "#111113"
_HOVER_BG   = "#27272a"
_ACTIVE_BG  = "#1a2520"
_CODE_BG    = "#0d0d0f"


class SettingsView:
    """
    Vista de ajustes estilo Modrinth.
    Se muestra como modal flotante con fondo desenfocado sobre la vista actual.
    """

    def __init__(self, page: ft.Page, app):
        self.page        = page
        self.app         = app
        self._active_tab = "appearance"

        self._init_controls()
        self._build()

    # ══════════════════════════════════════════════════════════════════════
    # INICIALIZACIÓN DE CONTROLES CON ESTADO
    # ══════════════════════════════════════════════════════════════════════

    def _init_controls(self):
        s = self.app.settings

        # ── RAM ──
        self._ram_lbl = ft.Text(
            f"{int(s.default_ram_mb)} MB",
            color=GREEN, size=12, weight="bold",
        )
        self._ram_slider = ft.Slider(
            value=s.default_ram_mb,
            min=512, max=16384, divisions=31,
            label="{value} MB",
            active_color=GREEN, inactive_color=INPUT_BG, thumb_color=GREEN,
            on_change=self._on_ram_change,
            expand=True,
        )

        # ── Java ──
        self._java_field = ft.TextField(
            value=s.java_path,
            hint_text="Dejar vacío para detección automática",
            hint_style=ft.TextStyle(color=TEXT_DIM, size=11),
            text_size=11, color=TEXT_PRI, bgcolor=INPUT_BG,
            border_color=BORDER, focused_border_color=GREEN,
            border_radius=8,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            expand=True,
        )
        self._java_status = ft.Text("", color=TEXT_DIM, size=10)

        # ── Switches ──
        self._sw_close    = ft.Switch(value=s.close_on_launch,  active_color=GREEN, on_change=self._on_close_toggle)
        self._sw_advanced = ft.Switch(value=True,               active_color=GREEN)

        # ── Diagnóstico ──
        self._diag_output = ft.Text(
            "Presiona el botón para ejecutar el diagnóstico del sistema.",
            color=TEXT_SEC, size=10, selectable=True,
            font_family="Consolas",
        )

    # ══════════════════════════════════════════════════════════════════════
    # BUILD PRINCIPAL
    # ══════════════════════════════════════════════════════════════════════

    def _build(self):
        # Área de contenido dinámica (lado derecho del modal)
        self._content_col = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
        )
        self._load_tab(self._active_tab)

        # Sidebar izquierdo
        self._sidebar_tabs: dict[str, ft.Container] = {}
        sidebar = self._build_sidebar()

        modal = ft.Container(
            width=900, height=580,
            bgcolor=_MODAL_BG,
            border_radius=14,
            border=ft.border.all(1, ft.colors.with_opacity(0.08, "white")),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            shadow=ft.BoxShadow(
                spread_radius=0, blur_radius=40,
                color=ft.colors.with_opacity(0.6, "black"),
            ),
            content=ft.Column(
                spacing=0,
                controls=[
                    # ── Header ──
                    ft.Container(
                        padding=ft.padding.only(left=20, right=12, top=14, bottom=14),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Row([
                                    ft.Icon(ft.icons.SETTINGS_OUTLINED, color=TEXT_PRI, size=18),
                                    ft.Text("Settings", color=TEXT_PRI, size=15, weight="bold"),
                                ], spacing=10),
                                ft.IconButton(
                                    icon=ft.icons.CLOSE,
                                    icon_size=16, icon_color=TEXT_SEC,
                                    hover_color=ft.colors.with_opacity(0.1, "white"),
                                    on_click=lambda _: self._close(),
                                ),
                            ],
                        ),
                    ),
                    ft.Divider(height=1, color=BORDER),
                    # ── Body (sidebar + contenido) ──
                    ft.Row(
                        expand=True,
                        spacing=0,
                        controls=[
                            sidebar,
                            ft.VerticalDivider(width=1, color=BORDER),
                            ft.Container(
                                expand=True,
                                padding=ft.padding.only(left=28, right=28, top=20, bottom=20),
                                content=self._content_col,
                            ),
                        ],
                    ),
                ],
            ),
        )

        # Root: fondo semitransparente con blur (efecto glassmorphism)
        self.root = ft.Container(
            expand=True,
            bgcolor=ft.colors.with_opacity(0.55, "#000000"),
            alignment=ft.alignment.center,
            content=modal,
        )

    # ══════════════════════════════════════════════════════════════════════
    # SIDEBAR
    # ══════════════════════════════════════════════════════════════════════

    def _build_sidebar(self) -> ft.Container:
        tabs = [
            ("appearance", ft.icons.BRUSH_OUTLINED,         "Appearance"),
            ("language",   ft.icons.TRANSLATE,              "Language",    True),
            ("privacy",    ft.icons.SHIELD_OUTLINED,        "Privacy"),
            ("java",       ft.icons.COFFEE_OUTLINED,        "Java installations"),
            ("options",    ft.icons.TUNE,                   "Default instance options"),
            ("diag",       ft.icons.SPEED_OUTLINED,         "Resource management"),
        ]

        controls = []
        for tab_def in tabs:
            tid   = tab_def[0]
            icon  = tab_def[1]
            title = tab_def[2]
            beta  = tab_def[3] if len(tab_def) > 3 else False
            btn   = self._tab_btn(tid, icon, title, beta)
            self._sidebar_tabs[tid] = btn
            controls.append(btn)

        version_info = ft.Container(
            padding=ft.padding.only(left=4, bottom=4),
            content=ft.Row([
                ft.Icon(ft.icons.INFO_OUTLINE, size=14, color=TEXT_DIM),
                ft.Column([
                    ft.Text(f"Launcher v{self.app.version}", size=10, color=TEXT_DIM),
                    ft.Text(f"{platform.system()} {platform.release()}", size=10, color=TEXT_DIM),
                ], spacing=1, tight=True),
            ], spacing=8),
        )

        return ft.Container(
            width=230,
            bgcolor=_SIDEBAR_BG,
            padding=ft.padding.all(10),
            content=ft.Column(
                expand=True,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(controls=controls, spacing=2),
                    version_info,
                ],
            ),
        )

    def _tab_btn(self, tid: str, icon, title: str, beta: bool = False) -> ft.Container:
        is_active = tid == self._active_tab

        badge = ft.Container(
            visible=beta,
            bgcolor=ft.colors.with_opacity(0.2, GREEN),
            padding=ft.padding.symmetric(horizontal=6, vertical=2),
            border_radius=10,
            content=ft.Text("Beta", size=8, color=GREEN, weight="bold"),
        )

        btn = ft.Container(
            bgcolor=_ACTIVE_BG if is_active else ft.colors.TRANSPARENT,
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            on_click=lambda e, t=tid: self._switch_tab(t),
            on_hover=lambda e, t=tid: self._on_hover(e, t),
            content=ft.Row([
                ft.Icon(icon, size=16, color=GREEN if is_active else TEXT_SEC),
                ft.Text(title, size=12, color=GREEN if is_active else TEXT_PRI, weight="w500", expand=True),
                badge,
            ], spacing=10),
        )
        return btn

    def _on_hover(self, e, tid: str):
        if tid != self._active_tab:
            e.control.bgcolor = _HOVER_BG if e.data == "true" else ft.colors.TRANSPARENT
            e.control.update()

    def _switch_tab(self, tid: str):
        # Tabs sin implementar
        if tid in ("language", "privacy"):
            return

        # Desactivar tab anterior
        prev = self._sidebar_tabs.get(self._active_tab)
        if prev:
            prev.bgcolor = ft.colors.TRANSPARENT
            prev.content.controls[0].color = TEXT_SEC   # icono
            prev.content.controls[1].color = TEXT_PRI   # texto
            prev.update()

        # Activar tab nuevo
        self._active_tab = tid
        curr = self._sidebar_tabs.get(tid)
        if curr:
            curr.bgcolor = _ACTIVE_BG
            curr.content.controls[0].color = GREEN
            curr.content.controls[1].color = GREEN
            curr.update()

        self._load_tab(tid)

    def _load_tab(self, tid: str):
        builders = {
            "appearance": self._tab_appearance,
            "java":       self._tab_java,
            "options":    self._tab_options,
            "diag":       self._tab_diag,
        }
        builder = builders.get(tid)
        if builder:
            self._content_col.controls = [builder()]
            try: self._content_col.update()
            except Exception: pass

    # ══════════════════════════════════════════════════════════════════════
    # PESTAÑAS
    # ══════════════════════════════════════════════════════════════════════

    def _tab_appearance(self) -> ft.Control:
        def theme_card(tid, label, preview_bg, accent_bg, is_light=False):
            is_sel = self.app.settings._data.get("theme", "dark") == tid
            txt_c  = "#27272a" if is_light else "#e4e4e7"
            bar1   = ft.Container(width=50, height=6, bgcolor=txt_c, border_radius=3)
            bar2   = ft.Container(width=35, height=6, bgcolor=txt_c, border_radius=3,
                                  opacity=0.5)
            toggle = ft.Container(
                width=26, height=14, border_radius=7,
                bgcolor=GREEN if is_sel else ("#9ca3af" if is_light else "#52525b"),
                content=ft.Container(
                    width=10, height=10, border_radius=5,
                    bgcolor="white",
                    margin=ft.margin.only(left=2 if not is_sel else 14),
                ),
            )
            preview = ft.Container(
                width=140, height=90,
                bgcolor=preview_bg,
                border_radius=10,
                border=ft.border.all(2, GREEN if is_sel else ft.colors.TRANSPARENT),
                padding=ft.padding.all(12),
                on_click=lambda e, t=tid: self._set_theme(t),
                content=ft.Column([
                    ft.Container(
                        width=float("inf"), height=18,
                        bgcolor=accent_bg, border_radius=4,
                    ),
                    ft.Container(height=6),
                    bar1, ft.Container(height=4), bar2,
                    ft.Container(height=8),
                    toggle,
                ], spacing=0),
            )
            dot_color = GREEN if is_sel else TEXT_DIM
            return ft.Column([
                preview,
                ft.Row([
                    ft.Icon(
                        ft.icons.RADIO_BUTTON_CHECKED if is_sel else ft.icons.RADIO_BUTTON_UNCHECKED,
                        size=14, color=dot_color,
                    ),
                    ft.Text(label, size=11, color=TEXT_PRI),
                ], spacing=6),
            ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        themes_row = ft.Row([
            theme_card("dark",   "Dark",          "#27272a", "#18181b"),
            theme_card("light",  "Light",         "#f4f4f5", "#e4e4e7", is_light=True),
            theme_card("oled",   "OLED",          "#000000", "#0a0a0a"),
            theme_card("system", "Sync with system", "#1c1c1f", "#111113"),
        ], spacing=14, wrap=True)

        adv_row = self._setting_row(
            ft.icons.AUTO_AWESOME_OUTLINED,
            "Advanced rendering",
            "Activa blur y efectos avanzados. Puede reducir rendimiento sin GPU.",
            self._sw_advanced,
        )

        return ft.Column([
            self._section_header("Color theme", "Elige el tema de color del launcher."),
            themes_row,
            ft.Container(height=24),
            self._section_header("Display", "Opciones de renderizado."),
            adv_row,
        ], spacing=12)

    def _tab_java(self) -> ft.Control:
        detect_btn = ft.ElevatedButton(
            "Detectar",
            bgcolor=CARD2_BG, color=TEXT_PRI,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=self._detect_java,
        )
        save_btn = ft.ElevatedButton(
            "Guardar",
            bgcolor=GREEN, color=TEXT_INV,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=self._save_java,
        )

        card = self._card([
            ft.Text("Ruta a java.exe", size=12, color=TEXT_PRI, weight="bold"),
            ft.Container(height=6),
            ft.Row([self._java_field, detect_btn, save_btn], spacing=8),
            ft.Container(height=6),
            self._java_status,
        ])

        return ft.Column([
            self._section_header("Java installations", "Gestiona la ruta de Java manualmente o déjala en auto."),
            card,
        ], spacing=12)

    def _tab_options(self) -> ft.Control:
        ram_card = self._card([
            ft.Row([
                ft.Column([
                    ft.Text("Memoria RAM", size=12, color=TEXT_PRI, weight="bold"),
                    ft.Text("RAM máxima asignada a Minecraft por defecto.", size=10, color=TEXT_DIM),
                ], expand=True, spacing=2),
                ft.Container(
                    bgcolor=ft.colors.with_opacity(0.15, GREEN),
                    border_radius=6,
                    padding=ft.padding.symmetric(horizontal=10, vertical=4),
                    content=self._ram_lbl,
                ),
            ]),
            ft.Container(height=8),
            self._ram_slider,
            ft.Row([
                ft.Text("512 MB", size=9, color=TEXT_DIM),
                ft.Container(expand=True),
                ft.Text("16 GB", size=9, color=TEXT_DIM),
            ]),
        ])

        close_row = self._setting_row(
            ft.icons.CLOSE_FULLSCREEN_OUTLINED,
            "Close on launch",
            "Cierra el launcher automáticamente al iniciar Minecraft.",
            self._sw_close,
        )

        return ft.Column([
            self._section_header("Default instance options", "Ajustes por defecto para todas las instancias."),
            ram_card,
            ft.Container(height=12),
            self._card([close_row]),
        ], spacing=12)

    def _tab_diag(self) -> ft.Control:
        run_btn = ft.ElevatedButton(
            "Ejecutar diagnóstico",
            icon=ft.icons.PLAY_ARROW_OUTLINED,
            bgcolor=CARD2_BG, color=TEXT_PRI,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=self._run_diag,
        )

        output_box = ft.Container(
            bgcolor=_CODE_BG,
            border_radius=8,
            border=ft.border.all(1, BORDER),
            padding=ft.padding.all(14),
            content=self._diag_output,
            width=float("inf"),
        )

        return ft.Column([
            self._section_header("Resource management", "Diagnóstico del sistema y Java."),
            run_btn,
            ft.Container(height=10),
            output_box,
        ], spacing=12)

    # ══════════════════════════════════════════════════════════════════════
    # HELPERS VISUALES
    # ══════════════════════════════════════════════════════════════════════

    def _section_header(self, title: str, subtitle: str) -> ft.Control:
        return ft.Column([
            ft.Text(title, size=16, weight="bold", color=TEXT_PRI),
            ft.Text(subtitle, size=11, color=TEXT_SEC),
            ft.Container(height=4),
        ], spacing=3)

    def _card(self, controls: list) -> ft.Container:
        return ft.Container(
            bgcolor=ft.colors.with_opacity(0.4, CARD_BG),
            border_radius=10,
            border=ft.border.all(1, BORDER),
            padding=ft.padding.all(18),
            content=ft.Column(controls=controls, spacing=6),
        )

    def _setting_row(self, icon, title: str, subtitle: str, control) -> ft.Control:
        return ft.Row([
            ft.Icon(icon, size=20, color=TEXT_SEC),
            ft.Column([
                ft.Text(title,    size=12, color=TEXT_PRI, weight="bold"),
                ft.Text(subtitle, size=10, color=TEXT_DIM),
            ], expand=True, spacing=2),
            control,
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=14)

    # ══════════════════════════════════════════════════════════════════════
    # LÓGICA
    # ══════════════════════════════════════════════════════════════════════

    def _close(self):
        try:
            self.app.overlay_area.visible = False
            self.app.overlay_area.update()
        except Exception:
            pass

    def _set_theme(self, tid: str):
        self.app.settings._data["theme"] = tid
        self.app.settings._save()
        # Refrescar pestaña appearance para actualizar las tarjetas
        self._load_tab("appearance")

    def on_show(self):
        s = self.app.settings
        self._ram_slider.value     = s.default_ram_mb
        self._ram_lbl.value        = f"{int(s.default_ram_mb)} MB"
        self._java_field.value     = s.java_path
        self._sw_close.value       = s.close_on_launch
        try: self.root.update()
        except Exception: pass

    # ── RAM ──
    def _on_ram_change(self, e):
        val = int(self._ram_slider.value)
        self._ram_lbl.value = f"{val} MB"
        self.app.settings.default_ram_mb = val
        try: self._ram_lbl.update()
        except Exception: pass

    # ── Java ──
    def _detect_java(self, e):
        try:
            info = self.app.java_manager.get_java_info()
            if info.get("error"):
                self._java_status.value = f"⚠  {info['error']}"
                self._java_status.color = "#ff6b6b"
            else:
                self._java_status.value = f"✓  {info['path']}  (Java {info['version']}, fuente: {info['source']})"
                self._java_status.color = GREEN
                self._java_field.value  = info["path"]
                try: self._java_field.update()
                except Exception: pass
        except Exception as err:
            self._java_status.value = f"Error: {err}"
            self._java_status.color = "#ff6b6b"
        try: self._java_status.update()
        except Exception: pass

    def _save_java(self, e):
        path = self._java_field.value.strip()
        if not path:
            self.app.settings.java_path = ""
            self.app.snack("Ruta borrada — se usará detección automática.")
            return
        if self.app.java_manager.set_manual_java_path(path):
            self.app.snack("Ruta de Java guardada.")
        else:
            self.app.snack("Ruta inválida o Java demasiado viejo.", error=True)

    # ── Switches ──
    def _on_close_toggle(self, e):
        self.app.settings.close_on_launch = e.control.value

    # ── Diagnóstico ──
    def _run_diag(self, e):
        self._diag_output.value = "Ejecutando…"
        try: self._diag_output.update()
        except Exception: pass
        try:
            from utils.system_utils import get_system_info
            info      = get_system_info()
            java_info = self.app.java_manager.get_java_info()
            installed = self.app.version_manager.get_installed_version_ids()
            lines = [
                f"OS        : {info.get('os')} ({info.get('architecture')})",
                f"RAM total : {info.get('ram_mb')} MB",
                f"Python    : {info.get('python_version')}",
                f"Java      : {java_info.get('path')}",
                f"Java ver  : {java_info.get('version')}  [{java_info.get('source')}]",
                f"Versiones : {len(installed)} instaladas — {', '.join(installed) or 'ninguna'}",
                f"Dir       : {self.app.settings.minecraft_dir}",
            ]
            self._diag_output.value = "\n".join(lines)
        except Exception as err:
            self._diag_output.value = f"Error al ejecutar diagnóstico:\n{err}"
        try: self._diag_output.update()
        except Exception: pass