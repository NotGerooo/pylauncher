"""
progress_bar.py — Widget de barra de progreso premium para Gero's Launcher
"""
import tkinter as tk
from tkinter import ttk

BG      = "#16171a"
CARD_BG = "#222327"
GREEN   = "#1bd96a"
TEXT_PRI= "#f0f1f3"
TEXT_SEC= "#8b8e96"
INPUT_BG= "#1a1b1f"


class ProgressBar(tk.Frame):
    """
    Barra de progreso con label de estado y porcentaje.
    """

    def __init__(self, parent, bg_color=None, **kwargs):
        bg_color = bg_color or CARD_BG
        super().__init__(parent, bg=bg_color, **kwargs)

        self._label_text = tk.StringVar(value="")
        self._pct_text   = tk.StringVar(value="")

        header = tk.Frame(self, bg=bg_color)
        header.pack(fill="x", pady=(0, 8))

        self._label = tk.Label(
            header,
            textvariable=self._label_text,
            bg=bg_color, fg=TEXT_PRI,
            font=("Segoe UI Variable Text", 9, "bold"),
            anchor="w"
        )
        self._label.pack(side="left")

        self._pct_label = tk.Label(
            header,
            textvariable=self._pct_text,
            bg=bg_color, fg=GREEN,
            font=("Segoe UI Variable Text", 9, "bold"),
            anchor="e"
        )
        self._pct_label.pack(side="right")

        # Track background
        track = tk.Frame(self, bg=INPUT_BG, height=5)
        track.pack(fill="x")
        track.pack_propagate(False)

        self._fill = tk.Frame(track, bg=GREEN, height=5)
        self._fill.place(x=0, y=0, relheight=1.0, relwidth=0.0)
        self._track = track

    def set_progress(self, percent: float, label: str = ""):
        percent = max(0.0, min(100.0, percent))
        self._label_text.set(label)
        self._pct_text.set(f"{percent:.0f}%" if percent > 0 else "")
        self._fill.place(relwidth=percent / 100.0)
        self.update_idletasks()

    def reset(self):
        self.set_progress(0.0, "")
