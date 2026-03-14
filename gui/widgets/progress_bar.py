import tkinter as tk


class ProgressBar(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=kwargs.pop("bg", "#1a1a2e"), **kwargs)
        self._label_text = tk.StringVar(value="")
        self._label = tk.Label(
            self, textvariable=self._label_text,
            bg="#1a1a2e", fg="#a0a0b0", font=("Segoe UI", 9), anchor="w",
        )
        self._label.pack(fill="x", pady=(0, 4))
        bar_bg = tk.Frame(self, bg="#0f3460", height=6)
        bar_bg.pack(fill="x")
        bar_bg.pack_propagate(False)
        self._bar_fill = tk.Frame(bar_bg, bg="#e94560", height=6)
        self._bar_fill.place(x=0, y=0, relheight=1.0, relwidth=0.0)
        self._bar_bg = bar_bg

    def set_progress(self, percent: float, label: str = ""):
        percent = max(0.0, min(100.0, percent))
        self._label_text.set(label)
        self._bar_fill.place(relwidth=percent / 100.0)
        self.update_idletasks()

    def reset(self):
        self.set_progress(0.0, "")
