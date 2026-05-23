"""
gui/splash.py — Pantalla de carga animada para Gero's Launcher.
Muestra el logo girando y un texto de estado mientras se inicializan los servicios.
"""
import math
import threading
import time
import flet as ft

from gui.theme import BG, GREEN, GREEN_DIM, SIDEBAR_BG, TEXT_PRI, TEXT_SEC, TEXT_DIM, BORDER


class SplashScreen:
    """
    Pantalla de carga que se muestra antes de que el launcher inicie.
    
    Uso:
        splash = SplashScreen(page)
        splash.show()
        # ... hacer cosas pesadas ...
        splash.set_status("Cargando perfiles...")
        # ... más cosas ...
        splash.hide()  # desaparece y muestra el launcher
    """

    def __init__(self, page: ft.Page):
        self.page = page
        self._angle = 0.0          # ángulo actual del logo (en grados)
        self._running = False      # controla el hilo de animación
        self._container = None     # el contenedor principal de la splash
        self._status_text = None   # texto de estado ("Cargando...")
        self._dots_text = None     # puntos animados "...."
        self._dot_count = 0        # contador de puntos
        self._ring_controls = []   # los segmentos del anillo giratorio
        self._build()

    # ── Construcción visual ──────────────────────────────────────────────────

    def _build(self):
        """Construye todos los widgets de la splash screen."""

        # — Texto del título —
        title = ft.Text(
            "Gero's Launcher",
            size=28,
            weight=ft.FontWeight.W_700,
            color=TEXT_PRI,
            text_align=ft.TextAlign.CENTER,
        )

        # — Ícono central (el pico/hacha de Minecraft) —
        self._icon = ft.Text(
            "⛏",
            size=52,
            text_align=ft.TextAlign.CENTER,
            color=GREEN,
        )

        # — Anillo de carga: 8 puntos en círculo —
        # Cada punto es un Container pequeño. Los animaremos cambiando su opacidad.
        self._ring_controls = []
        for i in range(8):
            dot = ft.Container(
                width=10,
                height=10,
                border_radius=5,          # círculo perfecto
                bgcolor=GREEN,
                opacity=0.15 + (i / 8) * 0.85,  # gradiente de opacidad inicial
                animate_opacity=ft.animation.Animation(100, ft.AnimationCurve.EASE_IN_OUT),
            )
            self._ring_controls.append(dot)

        # Posicionamos los 8 puntos en círculo usando una Stack + posición absoluta
        # El radio del círculo de puntos
        RADIUS = 48
        CENTER = 56  # mitad del Stack (112x112)
        DOT_SIZE = 10

        positioned_dots = []
        for i, dot in enumerate(self._ring_controls):
            angle_rad = math.radians((i / 8) * 360 - 90)  # empieza arriba
            x = CENTER + RADIUS * math.cos(angle_rad) - DOT_SIZE / 2
            y = CENTER + RADIUS * math.sin(angle_rad) - DOT_SIZE / 2
            positioned_dots.append(
                ft.Container(
                    left=x,
                    top=y,
                    content=dot,
                )
            )

        # Stack que contiene el anillo + el ícono central
        ring_stack = ft.Stack(
            width=112,
            height=112,
            controls=[
                *positioned_dots,
                # Ícono en el centro del stack
                ft.Container(
                    left=28,   # (112 - 56) / 2 ≈ 28
                    top=20,
                    content=self._icon,
                ),
            ]
        )

        # — Texto de estado —
        self._status_text = ft.Text(
            "Iniciando...",
            size=13,
            color=TEXT_SEC,
            text_align=ft.TextAlign.CENTER,
            animate_opacity=ft.animation.Animation(300, ft.AnimationCurve.EASE_IN_OUT),
        )

        # — Barra de progreso indeterminada (serpiente verde) —
        progress_bar = ft.ProgressBar(
            width=220,
            color=GREEN,
            bgcolor=BORDER,
            # Sin value= → modo indeterminado (serpiente animada)
        )

        # — Versión pequeña abajo —
        version_label = ft.Text(
            "Gero's Launcher",
            size=10,
            color=TEXT_DIM,
            text_align=ft.TextAlign.CENTER,
        )

        # — Contenedor principal (ocupa toda la pantalla) —
        self._container = ft.Container(
            expand=True,
            bgcolor=BG,
            alignment=ft.alignment.center,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=0,
                controls=[
                    ring_stack,
                    ft.Container(height=24),
                    title,
                    ft.Container(height=20),
                    progress_bar,
                    ft.Container(height=16),
                    self._status_text,
                    ft.Container(height=40),
                    version_label,
                ],
            ),
        )

    # ── API pública ──────────────────────────────────────────────────────────

    def show(self):
        """Muestra la splash screen en la página."""
        self.page.controls.clear()
        self.page.add(self._container)
        self.page.update()

        # Inicia la animación del anillo en un hilo separado
        self._running = True
        threading.Thread(target=self._animate_ring, daemon=True).start()

    def set_status(self, message: str):
        """Cambia el texto de estado (ej: 'Cargando perfiles...')."""
        if self._status_text:
            self._status_text.value = message
            try:
                self._status_text.update()
            except Exception:
                pass

    def hide(self):
        """
        Hace desaparecer la splash con una animación de fade-out
        y limpia la pantalla para que App construya el layout normal.
        """
        self._running = False

        # Fade out: reducimos la opacidad del contenedor
        self._container.opacity = 0
        self._container.animate_opacity = ft.animation.Animation(
            400, ft.AnimationCurve.EASE_OUT
        )
        try:
            self._container.update()
        except Exception:
            pass

        # Esperamos que termine el fade
        time.sleep(0.45)

        # Limpiamos la página para que App construya su layout
        try:
            self.page.controls.clear()
            self.page.update()
        except Exception:
            pass

    # ── Animación interna ────────────────────────────────────────────────────

    def _animate_ring(self):
        """
        Hilo que hace girar el anillo de puntos.
        Cada 80ms rota cuál punto está más brillante,
        creando el efecto de "spinner" girando.
        """
        step = 0
        n = len(self._ring_controls)  # 8 puntos

        while self._running:
            # Distribuimos la opacidad como una ola que gira
            for i, dot in enumerate(self._ring_controls):
                # El punto más cercano al "cabezal" tiene opacidad 1.0
                # Los demás van bajando gradualmente
                distance = (i - step) % n
                # distance=0 → cabezal (opacidad máxima)
                # distance=n-1 → cola (opacidad mínima)
                opacity = 0.1 + (1.0 - distance / n) * 0.9
                dot.opacity = round(opacity, 2)

            try:
                # Actualizamos todos los puntos de una vez
                self.page.update()
            except Exception:
                break

            step = (step + 1) % n
            time.sleep(0.08)  # 80ms por frame → ~12 fps