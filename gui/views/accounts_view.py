"""
accounts_view.py
----------------
Vista de gestión de cuentas del launcher.

Secciones:
  1. Cuenta activa — muestra avatar, username, tipo de cuenta
  2. Lista de cuentas — todas las cuentas con selector
  3. Acciones — agregar offline, login Microsoft, eliminar

La vista muestra el avatar del jugador usando PhotoImage de Tkinter
(PNG 32x32 generado por SkinService).

Integra con:
  - AccountManager (services/account_manager.py)
  - MicrosoftAuth  (services/microsoft_auth.py)
  - SkinService    (services/skin_service.py)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import webbrowser
import io

from utils.logger import get_logger
log = get_logger()


class AccountsView(tk.Frame):
    """
    Vista principal de gestión de cuentas.

    Requiere que app tenga:
        app.account_manager  : AccountManager
        app.microsoft_auth   : MicrosoftAuth
        app.skin_service     : SkinService
    """

    def __init__(self, parent, app):
        super().__init__(parent, bg="#1a1a2e")
        self.app = app
        self._photo_refs = {}         # Mantener referencias de PhotoImage (evita GC)
        self._login_cancel = None     # threading.Event para cancelar login MS
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build()

    # ─── Construcción de UI ──────────────────────────────────────────────────

    def _build(self):
        main = tk.Frame(self, bg="#1a1a2e", padx=32, pady=24)
        main.grid(row=0, column=0, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        # Título
        tk.Label(
            main, text="Cuentas",
            bg="#1a1a2e", fg="#ffffff",
            font=("Segoe UI", 18, "bold")
        ).grid(row=0, column=0, sticky="w")

        tk.Label(
            main, text="Gestiona tus cuentas de Minecraft",
            bg="#1a1a2e", fg="#a0a0b0",
            font=("Segoe UI", 10)
        ).grid(row=1, column=0, sticky="w", pady=(2, 20))

        # Layout horizontal: lista (izq) + panel activo (der)
        content = tk.Frame(main, bg="#1a1a2e")
        content.grid(row=2, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=0)
        content.grid_rowconfigure(0, weight=1)

        self._build_account_list(content)
        self._build_active_panel(content)
        self._build_action_bar(main)

    def _build_account_list(self, parent):
        """Panel izquierdo — lista de cuentas."""
        frame = tk.Frame(parent, bg="#16213e", padx=16, pady=16)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        tk.Label(
            frame, text="Mis cuentas",
            bg="#16213e", fg="#ffffff",
            font=("Segoe UI", 11, "bold")
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))

        # Canvas + scrollbar para la lista
        list_frame = tk.Frame(frame, bg="#16213e")
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(
            list_frame, bg="#16213e",
            highlightthickness=0, width=280
        )
        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical",
            command=self._canvas.yview
        )
        self._canvas.configure(yscrollcommand=scrollbar.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self._list_inner = tk.Frame(self._canvas, bg="#16213e")
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._list_inner, anchor="nw"
        )

        self._list_inner.bind("<Configure>", self._on_list_resize)
        self._canvas.bind("<Configure>", self._on_canvas_resize)

    def _build_active_panel(self, parent):
        """Panel derecho — cuenta activa con avatar grande."""
        frame = tk.Frame(parent, bg="#16213e", padx=20, pady=20, width=220)
        frame.grid(row=0, column=1, sticky="nsew")
        frame.grid_propagate(False)
        frame.grid_columnconfigure(0, weight=1)

        tk.Label(
            frame, text="Cuenta activa",
            bg="#16213e", fg="#a0a0b0",
            font=("Segoe UI", 9)
        ).grid(row=0, column=0)

        # Avatar grande (64x64)
        self._avatar_label = tk.Label(
            frame, bg="#0f3460",
            width=64, height=64,
            relief="flat"
        )
        self._avatar_label.grid(row=1, column=0, pady=(10, 8))

        self._active_username = tk.Label(
            frame, text="—",
            bg="#16213e", fg="#ffffff",
            font=("Segoe UI", 13, "bold"),
            wraplength=180
        )
        self._active_username.grid(row=2, column=0)

        self._active_type = tk.Label(
            frame, text="Sin cuenta",
            bg="#16213e", fg="#a0a0b0",
            font=("Segoe UI", 9)
        )
        self._active_type.grid(row=3, column=0, pady=(2, 16))

        ttk.Button(
            frame,
            text="Cambiar skin",
            style="Secondary.TButton",
            command=self._on_change_skin,
        ).grid(row=4, column=0, sticky="ew")

    def _build_action_bar(self, parent):
        """Barra de acciones en la parte inferior."""
        bar = tk.Frame(parent, bg="#1a1a2e")
        bar.grid(row=3, column=0, sticky="ew", pady=(16, 0))

        ttk.Button(
            bar,
            text="+ Agregar cuenta offline",
            style="Secondary.TButton",
            command=self._on_add_offline,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            bar,
            text="🔑 Iniciar sesión con Microsoft",
            style="Primary.TButton",
            command=self._on_microsoft_login,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            bar,
            text="🗑 Eliminar cuenta",
            style="Danger.TButton" if hasattr(ttk.Style(), "theme_names") else "Secondary.TButton",
            command=self._on_remove_account,
        ).pack(side="right")

        # Label de estado (para el flujo de login MS)
        self._status_label = tk.Label(
            bar, text="",
            bg="#1a1a2e", fg="#a0a0b0",
            font=("Segoe UI", 9)
        )
        self._status_label.pack(side="left", padx=8)

    # ─── Refresh de la lista ─────────────────────────────────────────────────

    def on_show(self):
        """Llamado por app.py cuando la vista se hace visible."""
        self._refresh()

    def _refresh(self):
        """Reconstruye la lista de cuentas y actualiza el panel activo."""
        # Limpiar lista
        for widget in self._list_inner.winfo_children():
            widget.destroy()
        self._photo_refs.clear()

        accounts = self.app.account_manager.get_all_accounts()
        active   = self.app.account_manager.get_active_account()

        if not accounts:
            tk.Label(
                self._list_inner,
                text="No hay cuentas.\nAgrega una para empezar.",
                bg="#16213e", fg="#a0a0b0",
                font=("Segoe UI", 10),
                justify="center"
            ).pack(pady=30)
        else:
            for acc in accounts:
                self._build_account_row(acc, is_active=(active and acc.id == active.id))

        # Actualizar panel activo
        self._update_active_panel(active)

    def _build_account_row(self, account, is_active: bool):
        """Construye una fila para una cuenta en la lista."""
        bg_color    = "#1a3060" if is_active else "#16213e"
        hover_color = "#1e3a75" if is_active else "#1a2a4a"

        row = tk.Frame(self._list_inner, bg=bg_color, pady=8, padx=10, cursor="hand2")
        row.pack(fill="x", pady=2)
        row.grid_columnconfigure(1, weight=1)

        # Avatar pequeño (32x32)
        avatar_label = tk.Label(row, bg=bg_color, width=32, height=32)
        avatar_label.grid(row=0, column=0, rowspan=2, padx=(0, 10))
        self._load_avatar(account, avatar_label, size=32)

        # Nombre
        tk.Label(
            row, text=account.username,
            bg=bg_color, fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
            anchor="w"
        ).grid(row=0, column=1, sticky="w")

        # Tipo
        type_color = "#4ec9b0" if account.is_microsoft else "#a0a0b0"
        tk.Label(
            row, text=account.display_type,
            bg=bg_color, fg=type_color,
            font=("Segoe UI", 8),
            anchor="w"
        ).grid(row=1, column=1, sticky="w")

        # Indicador de activo
        if is_active:
            tk.Label(
                row, text="●",
                bg=bg_color, fg="#e94560",
                font=("Segoe UI", 8)
            ).grid(row=0, column=2, rowspan=2)

        # Click → activar cuenta
        def on_click(event, acc_id=account.id):
            self._set_active(acc_id)

        for widget in row.winfo_children():
            widget.bind("<Button-1>", on_click)
        row.bind("<Button-1>", on_click)

        # Hover
        def on_enter(e, f=row, c=hover_color):
            f.configure(bg=c)
            for w in f.winfo_children():
                try: w.configure(bg=c)
                except: pass

        def on_leave(e, f=row, c=bg_color):
            f.configure(bg=c)
            for w in f.winfo_children():
                try: w.configure(bg=c)
                except: pass

        row.bind("<Enter>", on_enter)
        row.bind("<Leave>", on_leave)

    def _update_active_panel(self, account):
        """Actualiza el panel derecho con la cuenta activa."""
        if not account:
            self._active_username.configure(text="Sin cuenta activa")
            self._active_type.configure(text="")
            self._avatar_label.configure(image="", text="?", fg="#a0a0b0",
                                         font=("Segoe UI", 24))
            return

        self._active_username.configure(text=account.username)
        self._active_type.configure(text=account.display_type)
        self._load_avatar(account, self._avatar_label, size=64)

    # ─── Avatar / Skin ───────────────────────────────────────────────────────

    def _load_avatar(self, account, label: tk.Label, size: int = 32):
        """Carga el avatar del jugador en el Label, en un thread."""
        def load():
            try:
                face_bytes = self.app.skin_service.get_face_bytes(account)
                photo      = self._bytes_to_photo(face_bytes, size)
                if photo:
                    self._photo_refs[f"{account.id}_{size}"] = photo
                    label.after(0, lambda: label.configure(image=photo, text=""))
            except Exception as e:
                log.debug(f"No se pudo cargar avatar de {account.username}: {e}")

        threading.Thread(target=load, daemon=True).start()

    def _bytes_to_photo(self, png_bytes: bytes, size: int):
        """Convierte bytes PNG a PhotoImage de Tkinter."""
        try:
            # Tkinter PhotoImage puede leer PNG directamente desde datos
            photo = tk.PhotoImage(data=png_bytes)
            # Escalar si es necesario
            current_w = photo.width()
            if current_w != size and current_w > 0:
                factor = size // current_w if size > current_w else 1
                if factor > 1:
                    photo = photo.zoom(factor)
                elif size < current_w:
                    sub_factor = current_w // size
                    photo = photo.subsample(sub_factor)
            return photo
        except Exception as e:
            log.debug(f"Error convirtiendo PNG a PhotoImage: {e}")
            return None

    # ─── Handlers de acciones ────────────────────────────────────────────────

    def _set_active(self, account_id: str):
        """Activa una cuenta de la lista."""
        try:
            self.app.account_manager.set_active_account(account_id)
            self._refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add_offline(self):
        """Abre diálogo para agregar cuenta offline."""
        dialog = _OfflineAccountDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            try:
                account = self.app.account_manager.add_offline_account(dialog.result)
                self.app.account_manager.set_active_account(account.id)
                self._refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _on_microsoft_login(self):
        """Inicia el flujo de login Microsoft en un thread."""
        import threading

        self._set_status("Iniciando login de Microsoft...")
        self._login_cancel = threading.Event()

        def run_login():
            try:
                auth = self.app.microsoft_auth

                # Callback de estado que actualiza la UI
                def on_status(msg):
                    self.after(0, lambda: self._set_status(msg))

                auth._on_status = on_status

                # Paso 1: Obtener código de dispositivo
                code_info = auth.start_device_flow()
                user_code = code_info.get("user_code", "")
                verify_url = code_info.get("verification_uri", "https://microsoft.com/devicelogin")

                # Mostrar el diálogo con el código al usuario
                self.after(0, lambda: self._show_device_code_dialog(
                    user_code, verify_url, code_info
                ))

            except Exception as e:
                self.after(0, lambda: self._set_status(""))
                self.after(0, lambda: messagebox.showerror("Error", f"No se pudo iniciar el login:\n{e}"))

        threading.Thread(target=run_login, daemon=True).start()

    def _show_device_code_dialog(self, user_code: str, verify_url: str, code_info: dict):
        """Muestra el diálogo del código de dispositivo."""
        dialog = _DeviceCodeDialog(self, user_code, verify_url)
        # Abrir browser automáticamente
        try:
            webbrowser.open(verify_url)
        except Exception:
            pass

        # Hacer polling en un thread
        import threading
        def poll():
            try:
                result = self.app.microsoft_auth.poll_for_token(
                    code_info, cancel_event=self._login_cancel
                )
                if result is None:
                    self.after(0, lambda: self._set_status("Login cancelado."))
                    return

                account = self.app.account_manager.add_microsoft_account(**result)
                self.app.account_manager.set_active_account(account.id)

                # Descargar skin en segundo plano
                self.app.skin_service.get_skin_path(account)

                self.after(0, dialog.destroy)
                self.after(0, lambda: self._set_status(
                    f"¡Sesión iniciada como {account.username}!"
                ))
                self.after(0, self._refresh)

            except Exception as e:
                self.after(0, dialog.destroy)
                self.after(0, lambda: self._set_status(""))
                self.after(0, lambda: messagebox.showerror("Error de login", str(e)))

        threading.Thread(target=poll, daemon=True).start()

        # Si el usuario cierra el diálogo, cancelar el polling
        def on_close():
            if self._login_cancel:
                self._login_cancel.set()
            dialog.destroy()
            self._set_status("")

        dialog.protocol("WM_DELETE_WINDOW", on_close)

    def _on_remove_account(self):
        """Elimina la cuenta activa tras confirmación."""
        active = self.app.account_manager.get_active_account()
        if not active:
            messagebox.showwarning("Aviso", "No hay ninguna cuenta seleccionada.")
            return
        if not messagebox.askyesno(
            "Confirmar",
            f"¿Eliminar la cuenta '{active.username}' ({active.display_type})?\n\n"
            f"Esta acción no se puede deshacer."
        ):
            return
        try:
            self.app.skin_service.clear_cache(active.id)
            self.app.account_manager.remove_account(active.id)
            self._refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_change_skin(self):
        """Permite cambiar la skin de una cuenta offline."""
        active = self.app.account_manager.get_active_account()
        if not active:
            messagebox.showwarning("Aviso", "No hay ninguna cuenta seleccionada.")
            return
        if active.is_microsoft:
            messagebox.showinfo(
                "Skin de Microsoft",
                "Las cuentas Microsoft usan tu skin oficial de Minecraft.\n"
                "Puedes cambiarla en minecraft.net"
            )
            return

        path = filedialog.askopenfilename(
            title="Seleccionar skin de Minecraft",
            filetypes=[("Imagen PNG", "*.png"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return

        try:
            skin_path = self.app.skin_service.save_offline_skin(active.id, path)
            self.app.account_manager.update_skin(active.id, skin_path)
            self.app.skin_service.clear_cache(active.id)
            self._refresh()
            messagebox.showinfo("Listo", "Skin actualizada correctamente.")
        except ValueError as e:
            messagebox.showerror("Skin inválida", str(e))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ─── Helpers

    def _set_status(self, msg: str):
        self._status_label.configure(text=msg)

    def _on_list_resize(self, event):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)


# ─── Diálogos auxiliares ─────────────────────────────────────────────────────

class _OfflineAccountDialog(tk.Toplevel):
    """Diálogo para crear una cuenta offline."""

    def __init__(self, parent):
        super().__init__(parent)
        self.result = None
        self.title("Agregar cuenta offline")
        self.resizable(False, False)
        self.configure(bg="#1a1a2e")
        self.geometry("320x180")
        self.grab_set()
        self._build()
        self.transient(parent)

    def _build(self):
        frame = tk.Frame(self, bg="#1a1a2e", padx=24, pady=24)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame, text="Nombre de usuario",
            bg="#1a1a2e", fg="#a0a0b0",
            font=("Segoe UI", 9)
        ).pack(anchor="w")

        self._var = tk.StringVar()
        entry = tk.Entry(
            frame, textvariable=self._var,
            bg="#0f3460", fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat", font=("Segoe UI", 12),
            width=24
        )
        entry.pack(fill="x", ipady=7, pady=(4, 4))
        entry.focus_set()

        tk.Label(
            frame, text="3–16 caracteres: letras, números y _",
            bg="#1a1a2e", fg="#606080",
            font=("Segoe UI", 8)
        ).pack(anchor="w", pady=(0, 12))

        btn_frame = tk.Frame(frame, bg="#1a1a2e")
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="Cancelar", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(
            btn_frame, text="Agregar",
            style="Primary.TButton",
            command=self._confirm
        ).pack(side="right")

        entry.bind("<Return>", lambda e: self._confirm())

    def _confirm(self):
        username = self._var.get().strip()
        if not username:
            return
        self.result = username
        self.destroy()


class _DeviceCodeDialog(tk.Toplevel):
    """Diálogo que muestra el código de dispositivo Microsoft."""

    def __init__(self, parent, user_code: str, verify_url: str):
        super().__init__(parent)
        self.title("Iniciar sesión con Microsoft")
        self.resizable(False, False)
        self.configure(bg="#1a1a2e")
        self.geometry("400x260")
        self.grab_set()
        self.transient(parent)
        self._build(user_code, verify_url)

    def _build(self, user_code: str, verify_url: str):
        frame = tk.Frame(self, bg="#1a1a2e", padx=28, pady=24)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame, text="Login con Microsoft",
            bg="#1a1a2e", fg="#ffffff",
            font=("Segoe UI", 14, "bold")
        ).pack()

        tk.Label(
            frame,
            text="1. El navegador se abrirá automáticamente.\n"
                 "2. Si no se abre, visita la URL de abajo.\n"
                 "3. Ingresa este código cuando se te pida:",
            bg="#1a1a2e", fg="#a0a0b0",
            font=("Segoe UI", 9),
            justify="left"
        ).pack(anchor="w", pady=(12, 8))

        # Código grande
        code_frame = tk.Frame(frame, bg="#0f3460", padx=16, pady=10)
        code_frame.pack(fill="x")
        tk.Label(
            code_frame, text=user_code,
            bg="#0f3460", fg="#e94560",
            font=("Courier New", 22, "bold"),
            letter_spacing=4 if False else 0
        ).pack()

        tk.Label(
            frame, text=verify_url,
            bg="#1a1a2e", fg="#4ec9b0",
            font=("Segoe UI", 9),
            cursor="hand2"
        ).pack(pady=(8, 4))

        self._status = tk.Label(
            frame, text="⏳ Esperando login...",
            bg="#1a1a2e", fg="#a0a0b0",
            font=("Segoe UI", 9)
        )
        self._status.pack()

        ttk.Button(
            frame, text="Cancelar",
            command=self.destroy
        ).pack(pady=(12, 0))