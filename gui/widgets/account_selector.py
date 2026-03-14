"""
account_selector.py
-------------------
Widget compacto que muestra la cuenta activa y permite cambiarla rápidamente.

Se usa en home_view.py para mostrar qué cuenta se usará al lanzar Minecraft.

Muestra:
  - Avatar pequeño del jugador (32x32)
  - Nombre de usuario
  - Tipo de cuenta (Offline / Microsoft)
  - Botón de dropdown para cambiar de cuenta sin ir a la vista de cuentas

Integra con:
  - AccountManager (app.account_manager)
  - SkinService    (app.skin_service)
"""

import tkinter as tk
from tkinter import ttk
import threading

from utils.logger import get_logger
log = get_logger()


class AccountSelector(tk.Frame):
    """
    Widget compacto para seleccionar la cuenta activa.

    Uso en home_view.py:
        self._account_selector = AccountSelector(parent, self.app)
        self._account_selector.grid(...)

        # Obtener sesión lista para lanzar:
        session = self._account_selector.get_active_session()
    """

    def __init__(self, parent, app, on_account_changed=None):
        """
        Args:
            parent             : Widget padre Tkinter
            app                : Instancia de App (tiene account_manager, skin_service)
            on_account_changed : Callback() llamado cuando el usuario cambia de cuenta
        """
        super().__init__(parent, bg="#16213e")
        self.app                = app
        self._on_account_changed = on_account_changed
        self._photo_refs        = {}
        self._popup             = None
        self.grid_columnconfigure(1, weight=1)
        self._build()

    # ─── Construcción

    def _build(self):
        # Avatar
        self._avatar_label = tk.Label(
            self, bg="#0f3460",
            width=32, height=32,
            cursor="hand2"
        )
        self._avatar_label.grid(row=0, column=0, rowspan=2, padx=(0, 10))

        # Nombre
        self._username_label = tk.Label(
            self, text="Sin cuenta",
            bg="#16213e", fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
            anchor="w", cursor="hand2"
        )
        self._username_label.grid(row=0, column=1, sticky="sw")

        # Tipo
        self._type_label = tk.Label(
            self, text="Agregar cuenta",
            bg="#16213e", fg="#a0a0b0",
            font=("Segoe UI", 8),
            anchor="w", cursor="hand2"
        )
        self._type_label.grid(row=1, column=1, sticky="nw")

        # Botón dropdown ▼
        self._dropdown_btn = tk.Label(
            self, text="▼",
            bg="#16213e", fg="#a0a0b0",
            font=("Segoe UI", 8),
            cursor="hand2", padx=6
        )
        self._dropdown_btn.grid(row=0, column=2, rowspan=2)

        # Bindings para abrir el popup
        for widget in (self._avatar_label, self._username_label,
                        self._type_label, self._dropdown_btn, self):
            widget.bind("<Button-1>", self._toggle_popup)

    # ─── API pública

    def refresh(self):
        """Actualiza el widget con la cuenta activa actual."""
        account = self.app.account_manager.get_active_account()

        if not account:
            self._username_label.configure(text="Sin cuenta")
            self._type_label.configure(text="Haz clic para agregar")
            self._avatar_label.configure(image="", text="?",
                                         fg="#606080", font=("Segoe UI", 14))
            return

        self._username_label.configure(text=account.username)

        type_color = "#4ec9b0" if account.is_microsoft else "#a0a0b0"
        self._type_label.configure(text=account.display_type, fg=type_color)

        # Cargar avatar en thread
        def load_avatar():
            try:
                face_bytes = self.app.skin_service.get_face_bytes(account)
                photo = self._bytes_to_photo(face_bytes, 32)
                if photo:
                    self._photo_refs["active"] = photo
                    self._avatar_label.after(
                        0, lambda: self._avatar_label.configure(image=photo, text="")
                    )
            except Exception as e:
                log.debug(f"Error cargando avatar del selector: {e}")

        threading.Thread(target=load_avatar, daemon=True).start()

    def get_active_session(self) -> dict | None:
        """
        Retorna el diccionario de sesión de la cuenta activa.
        Retorna None si no hay ninguna cuenta.

        El dict tiene: username, uuid, access_token, is_online
        """
        account = self.app.account_manager.get_active_account()
        if not account:
            return None
        try:
            return self.app.account_manager.build_session(account.id)
        except Exception as e:
            log.error(f"Error al construir sesión: {e}")
            return None

    def get_active_account(self):
        """Retorna la Account activa, o None."""
        return self.app.account_manager.get_active_account()

    # ─── Popup de switcher

    def _toggle_popup(self, event=None):
        """Abre o cierra el popup de cambio de cuenta."""
        if self._popup and self._popup.winfo_exists():
            self._popup.destroy()
            self._popup = None
            return
        self._open_popup()

    def _open_popup(self):
        """Abre el popup flotante con la lista de cuentas."""
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.configure(bg="#0f3460")
        self._popup = popup

        accounts = self.app.account_manager.get_all_accounts()
        active   = self.app.account_manager.get_active_account()

        if not accounts:
            tk.Label(
                popup, text="No hay cuentas.\nAbre la sección Cuentas.",
                bg="#0f3460", fg="#a0a0b0",
                font=("Segoe UI", 9),
                padx=12, pady=10
            ).pack()
        else:
            for acc in accounts:
                is_active = active and acc.id == active.id
                self._build_popup_row(popup, acc, is_active)

        # Separator + opción de ir a cuentas
        tk.Frame(popup, bg="#1a3060", height=1).pack(fill="x")
        manage_row = tk.Label(
            popup, text="  ⚙ Gestionar cuentas",
            bg="#0f3460", fg="#4ec9b0",
            font=("Segoe UI", 9),
            anchor="w", padx=8, pady=6,
            cursor="hand2"
        )
        manage_row.pack(fill="x")
        manage_row.bind("<Button-1>", self._go_to_accounts)

        # Posicionar popup debajo del widget
        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 2
        popup.geometry(f"+{x}+{y}")

        # Cerrar al hacer clic fuera
        popup.bind("<FocusOut>", lambda e: self._close_popup())
        popup.focus_set()

    def _build_popup_row(self, parent, account, is_active: bool):
        """Construye una fila del popup."""
        bg = "#1a3060" if is_active else "#0f3460"

        row = tk.Frame(parent, bg=bg, cursor="hand2", padx=8, pady=6)
        row.pack(fill="x")
        row.grid_columnconfigure(1, weight=1)

        # Indicador activo
        dot = "● " if is_active else "  "
        dot_color = "#e94560" if is_active else "#0f3460"

        tk.Label(
            row, text=dot,
            bg=bg, fg=dot_color,
            font=("Segoe UI", 8)
        ).grid(row=0, column=0, rowspan=2)

        tk.Label(
            row, text=account.username,
            bg=bg, fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            anchor="w"
        ).grid(row=0, column=1, sticky="w")

        type_color = "#4ec9b0" if account.is_microsoft else "#a0a0b0"
        tk.Label(
            row, text=account.display_type,
            bg=bg, fg=type_color,
            font=("Segoe UI", 7),
            anchor="w"
        ).grid(row=1, column=1, sticky="w")

        def on_click(event, acc_id=account.id):
            self._select_account(acc_id)

        row.bind("<Button-1>", on_click)
        for child in row.winfo_children():
            child.bind("<Button-1>", on_click)

    def _select_account(self, account_id: str):
        """Cambia la cuenta activa desde el popup."""
        try:
            self.app.account_manager.set_active_account(account_id)
            self._close_popup()
            self.refresh()
            if self._on_account_changed:
                self._on_account_changed()
        except Exception as e:
            log.error(f"Error al cambiar cuenta: {e}")

    def _go_to_accounts(self, event=None):
        """Navega a la vista de cuentas."""
        self._close_popup()
        try:
            self.app._show_view("accounts")
        except Exception:
            pass

    def _close_popup(self):
        if self._popup and self._popup.winfo_exists():
            self._popup.destroy()
        self._popup = None

    # ─── Helpers

    def _bytes_to_photo(self, png_bytes: bytes, size: int):
        try:
            photo = tk.PhotoImage(data=png_bytes)
            current_w = photo.width()
            if current_w > 0 and current_w != size:
                if size > current_w:
                    factor = size // current_w
                    photo = photo.zoom(factor)
                else:
                    sub_factor = current_w // size
                    photo = photo.subsample(sub_factor)
            return photo
        except Exception as e:
            log.debug(f"Error convirtiendo avatar PNG: {e}")
            return None