"""
accounts_view.py — Gestión de cuentas con paleta actualizada
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import webbrowser
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
BLUE      = "#3d8ff5"


def _btn(parent, text, cmd, primary=True, small=False):
    bg  = GREEN if primary else CARD2_BG
    fg  = TEXT_INV if primary else TEXT_PRI
    abg = GREEN_DIM if primary else BORDER
    f   = ("Segoe UI Variable Text", 9 if small else 10,
           "bold" if primary else "normal")
    return tk.Button(parent, text=text, bg=bg, fg=fg,
                     activebackground=abg, activeforeground=fg,
                     relief="flat", font=f,
                     padx=10 if small else 18, pady=5 if small else 9,
                     cursor="hand2", command=cmd)


class AccountsView(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._photo_refs  = {}
        self._login_cancel = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build()

    def _build(self):
        # Header elevado
        hdr_bg = BG_EL
        hdr = tk.Frame(self, bg=hdr_bg)
        hdr.grid(row=0, column=0, sticky="ew")
        inner_hdr = tk.Frame(hdr, bg=hdr_bg, padx=44, pady=32)
        inner_hdr.pack(fill="x")

        badge_f = tk.Frame(inner_hdr, bg="#0f1e32", padx=10, pady=4)
        badge_f.pack(anchor="w", pady=(0, 12))
        tk.Label(badge_f, text="👤  Cuentas", bg="#0f1e32", fg=BLUE,
                 font=("Segoe UI Variable Text", 9, "bold")).pack()

        tk.Label(inner_hdr, text="Gestión de cuentas",
                 bg=hdr_bg, fg=TEXT_PRI,
                 font=("Segoe UI Variable Display", 26, "bold")).pack(anchor="w")
        tk.Label(inner_hdr,
                 text="Administra tus cuentas de Minecraft offline y Microsoft.",
                 bg=hdr_bg, fg=TEXT_SEC,
                 font=("Segoe UI Variable Text", 11)).pack(anchor="w", pady=(6, 0))
        tk.Frame(hdr, bg=BORDER, height=1).pack(fill="x")

        # Body
        body = tk.Frame(self, bg=BG)
        body.grid(row=1, column=0, sticky="nsew", padx=44, pady=32)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, minsize=260)
        body.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_list(body)
        self._build_active_panel(body)
        self._build_action_bar(body)

    def _build_list(self, parent):
        card = tk.Frame(parent, bg=CARD_BG, padx=20, pady=20)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        tk.Label(card, text="Mis cuentas", bg=CARD_BG, fg=TEXT_PRI,
                 font=("Segoe UI Variable Display", 13, "bold")).grid(
                     row=0, column=0, sticky="w", pady=(0, 14))

        lf = tk.Frame(card, bg=CARD_BG)
        lf.grid(row=1, column=0, sticky="nsew")
        lf.grid_columnconfigure(0, weight=1)
        lf.grid_rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(lf, bg=CARD_BG, highlightthickness=0, width=300)
        sb = ttk.Scrollbar(lf, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sb.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

        self._list_inner = tk.Frame(self._canvas, bg=CARD_BG)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._list_inner, anchor="nw")
        self._list_inner.bind("<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
            lambda e: self._canvas.itemconfig(self._canvas_window, width=e.width))

    def _build_active_panel(self, parent):
        card = tk.Frame(parent, bg=CARD_BG, padx=20, pady=20)
        card.grid(row=0, column=1, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)

        tk.Label(card, text="Cuenta activa", bg=CARD_BG, fg=TEXT_SEC,
                 font=("Segoe UI Variable Text", 9)).grid(
                     row=0, column=0, pady=(0, 14))

        # Avatar placeholder
        self._avatar_label = tk.Label(card, bg=INPUT_BG, width=7, height=3,
                                       text="?", fg=TEXT_DIM,
                                       font=("Segoe UI Variable Display", 28))
        self._avatar_label.grid(row=1, column=0, pady=(0, 12))

        self._active_username = tk.Label(card, text="—", bg=CARD_BG, fg=TEXT_PRI,
                                          font=("Segoe UI Variable Display", 14, "bold"),
                                          wraplength=200)
        self._active_username.grid(row=2, column=0)

        self._active_type = tk.Label(card, text="Sin cuenta", bg=CARD_BG,
                                      fg=TEXT_SEC,
                                      font=("Segoe UI Variable Text", 9))
        self._active_type.grid(row=3, column=0, pady=(3, 18))

        _btn(card, "Cambiar skin", self._on_change_skin,
             primary=False, small=True).grid(row=4, column=0, sticky="ew")

    def _build_action_bar(self, parent):
        bar = tk.Frame(parent, bg=BG)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(18, 0))

        _btn(bar, "+ Cuenta offline", self._on_add_offline,
             primary=False).pack(side="left", padx=(0, 10))
        _btn(bar, "🔑  Microsoft", self._on_microsoft_login,
             primary=True).pack(side="left", padx=(0, 10))
        _btn(bar, "🗑  Eliminar", self._on_remove_account,
             primary=False).pack(side="right")

        self._status_label = tk.Label(bar, text="", bg=BG, fg=TEXT_SEC,
                                       font=("Segoe UI Variable Text", 9))
        self._status_label.pack(side="left", padx=10)

    def on_show(self):
        self._refresh()

    def _refresh(self):
        for w in self._list_inner.winfo_children():
            w.destroy()
        self._photo_refs.clear()

        accounts = self.app.account_manager.get_all_accounts()
        active   = self.app.account_manager.get_active_account()

        if not accounts:
            tk.Label(self._list_inner,
                     text="No hay cuentas.\nAgrega una para empezar.",
                     bg=CARD_BG, fg=TEXT_SEC,
                     font=("Segoe UI Variable Text", 10),
                     justify="center").pack(pady=40)
        else:
            for acc in accounts:
                self._build_account_row(acc, is_active=(active and acc.id == active.id))

        self._update_active_panel(active)

    def _build_account_row(self, account, is_active: bool):
        act_bg   = "#0f2318" if is_active else CARD_BG
        hov_bg   = "#162b1e" if is_active else CARD2_BG
        name_fg  = GREEN    if is_active else TEXT_PRI

        row = tk.Frame(self._list_inner, bg=act_bg, pady=10, padx=14, cursor="hand2")
        row.pack(fill="x", pady=2)
        row.grid_columnconfigure(1, weight=1)

        avatar_lbl = tk.Label(row, bg=act_bg, width=3, height=2,
                               text="👤", font=("Segoe UI", 16))
        avatar_lbl.grid(row=0, column=0, rowspan=2, padx=(0, 12))
        self._load_avatar(account, avatar_lbl, 32)

        tk.Label(row, text=account.username, bg=act_bg, fg=name_fg,
                 font=("Segoe UI Variable Text", 10, "bold"),
                 anchor="w").grid(row=0, column=1, sticky="w")

        type_c = BLUE if account.is_microsoft else TEXT_SEC
        tk.Label(row, text=account.display_type, bg=act_bg, fg=type_c,
                 font=("Segoe UI Variable Text", 8),
                 anchor="w").grid(row=1, column=1, sticky="w")

        if is_active:
            tk.Label(row, text="●", bg=act_bg, fg=GREEN,
                     font=("Segoe UI Variable Text", 8)).grid(
                         row=0, column=2, rowspan=2)

        def click(e, aid=account.id):
            self._set_active(aid)

        def enter(e, f=row):
            f.configure(bg=hov_bg)
            for w in f.winfo_children():
                try: w.configure(bg=hov_bg)
                except: pass

        def leave(e, f=row, c=act_bg):
            f.configure(bg=c)
            for w in f.winfo_children():
                try: w.configure(bg=c)
                except: pass

        for w in [row] + list(row.winfo_children()):
            w.bind("<Button-1>", click)
            w.bind("<Enter>",    enter)
            w.bind("<Leave>",    leave)

    def _update_active_panel(self, account):
        if not account:
            self._active_username.configure(text="Sin cuenta activa")
            self._active_type.configure(text="")
            self._avatar_label.configure(image="", text="?")
            return
        self._active_username.configure(text=account.username)
        self._active_type.configure(text=account.display_type)
        self._load_avatar(account, self._avatar_label, 64)

    def _load_avatar(self, account, label, size=32):
        def load():
            try:
                face_bytes = self.app.skin_service.get_face_bytes(account)
                photo = self._bytes_to_photo(face_bytes, size)
                if photo:
                    self._photo_refs[f"{account.id}_{size}"] = photo
                    label.after(0, lambda: label.configure(image=photo, text=""))
            except Exception as e:
                log.debug(f"Avatar {account.username}: {e}")
        threading.Thread(target=load, daemon=True).start()

    def _bytes_to_photo(self, png_bytes, size):
        try:
            photo = tk.PhotoImage(data=png_bytes)
            cw = photo.width()
            if cw != size and cw > 0:
                factor = size // cw if size > cw else 1
                if factor > 1:
                    photo = photo.zoom(factor)
                elif size < cw:
                    photo = photo.subsample(cw // size)
            return photo
        except Exception as e:
            log.debug(f"PhotoImage error: {e}")
            return None

    def _set_active(self, account_id):
        try:
            self.app.account_manager.set_active_account(account_id)
            self._refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add_offline(self):
        dialog = _OfflineDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            try:
                account = self.app.account_manager.add_offline_account(dialog.result)
                self.app.account_manager.set_active_account(account.id)
                self._refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _on_microsoft_login(self):
        self._set_status("Iniciando login de Microsoft...")
        self._login_cancel = threading.Event()

        def run():
            try:
                auth = self.app.microsoft_auth
                def on_status(msg):
                    self.after(0, lambda: self._set_status(msg))
                auth._on_status = on_status
                code_info  = auth.start_device_flow()
                user_code  = code_info.get("user_code", "")
                verify_url = code_info.get("verification_uri",
                                           "https://microsoft.com/devicelogin")
                self.after(0, lambda: self._show_device_dialog(
                    user_code, verify_url, code_info))
            except Exception as e:
                self.after(0, lambda: self._set_status(""))
                self.after(0, lambda: messagebox.showerror(
                    "Error", f"No se pudo iniciar el login:\n{e}"))

        threading.Thread(target=run, daemon=True).start()

    def _show_device_dialog(self, user_code, verify_url, code_info):
        dialog = _DeviceCodeDialog(self, user_code, verify_url)
        try:
            webbrowser.open(verify_url)
        except Exception:
            pass

        def poll():
            try:
                result = self.app.microsoft_auth.poll_for_token(
                    code_info, cancel_event=self._login_cancel)
                if result is None:
                    self.after(0, lambda: self._set_status("Login cancelado."))
                    return
                account = self.app.account_manager.add_microsoft_account(**result)
                self.app.account_manager.set_active_account(account.id)
                self.app.skin_service.get_skin_path(account)
                self.after(0, dialog.destroy)
                self.after(0, lambda: self._set_status(
                    f"¡Sesión iniciada como {account.username}!"))
                self.after(0, self._refresh)
            except Exception as e:
                self.after(0, dialog.destroy)
                self.after(0, lambda: self._set_status(""))
                self.after(0, lambda: messagebox.showerror("Error de login", str(e)))

        threading.Thread(target=poll, daemon=True).start()

        def on_close():
            if self._login_cancel:
                self._login_cancel.set()
            dialog.destroy()
            self._set_status("")

        dialog.protocol("WM_DELETE_WINDOW", on_close)

    def _on_remove_account(self):
        active = self.app.account_manager.get_active_account()
        if not active:
            messagebox.showwarning("Aviso", "No hay ninguna cuenta seleccionada.")
            return
        if not messagebox.askyesno(
            "Confirmar",
            f"¿Eliminar la cuenta '{active.username}'?\nEsta acción no se puede deshacer."
        ):
            return
        try:
            self.app.skin_service.clear_cache(active.id)
            self.app.account_manager.remove_account(active.id)
            self._refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_change_skin(self):
        active = self.app.account_manager.get_active_account()
        if not active:
            messagebox.showwarning("Aviso", "No hay ninguna cuenta seleccionada.")
            return
        if active.is_microsoft:
            messagebox.showinfo("Skin de Microsoft",
                                "Las cuentas Microsoft usan tu skin oficial.\n"
                                "Puedes cambiarla en minecraft.net")
            return
        path = filedialog.askopenfilename(
            title="Seleccionar skin PNG",
            filetypes=[("PNG", "*.png"), ("Todos", "*.*")])
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

    def _set_status(self, msg):
        self._status_label.configure(text=msg)


# ── Diálogos ──────────────────────────────────────────────────────────────────

class _OfflineDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.result = None
        self.title("Agregar cuenta offline")
        self.resizable(False, False)
        self.configure(bg=BG_EL)
        self.geometry("340x200")
        self.grab_set()
        self.transient(parent)
        self._build()

    def _build(self):
        f = tk.Frame(self, bg=BG_EL, padx=28, pady=28)
        f.pack(fill="both", expand=True)

        tk.Label(f, text="Nombre de usuario", bg=BG_EL, fg=TEXT_SEC,
                 font=("Segoe UI Variable Text", 9)).pack(anchor="w")

        self._var = tk.StringVar()
        e = tk.Entry(f, textvariable=self._var,
                     bg=INPUT_BG, fg=TEXT_PRI, insertbackground=TEXT_PRI,
                     relief="flat", font=("Segoe UI Variable Text", 12))
        e.pack(fill="x", ipady=9, pady=(6, 4))
        e.focus_set()

        tk.Label(f, text="3–16 caracteres. Solo letras, números y _",
                 bg=BG_EL, fg=TEXT_DIM,
                 font=("Segoe UI Variable Text", 8)).pack(anchor="w", pady=(0, 16))

        bf = tk.Frame(f, bg=BG_EL)
        bf.pack(fill="x")
        _btn(bf, "Cancelar", self.destroy, primary=False, small=True).pack(
            side="right", padx=(8, 0))
        _btn(bf, "Agregar", self._confirm, primary=True, small=True).pack(side="right")
        e.bind("<Return>", lambda e: self._confirm())

    def _confirm(self):
        username = self._var.get().strip()
        if username:
            self.result = username
            self.destroy()


class _DeviceCodeDialog(tk.Toplevel):
    def __init__(self, parent, user_code, verify_url):
        super().__init__(parent)
        self.title("Iniciar sesión con Microsoft")
        self.resizable(False, False)
        self.configure(bg=BG_EL)
        self.geometry("420x280")
        self.grab_set()
        self.transient(parent)
        self._build(user_code, verify_url)

    def _build(self, user_code, verify_url):
        f = tk.Frame(self, bg=BG_EL, padx=32, pady=28)
        f.pack(fill="both", expand=True)

        tk.Label(f, text="Login con Microsoft", bg=BG_EL, fg=TEXT_PRI,
                 font=("Segoe UI Variable Display", 15, "bold")).pack()

        tk.Label(f,
                 text="1. El navegador se abrirá automáticamente.\n"
                      "2. Si no, visita la URL de abajo.\n"
                      "3. Ingresa este código cuando se te pida:",
                 bg=BG_EL, fg=TEXT_SEC,
                 font=("Segoe UI Variable Text", 9),
                 justify="left").pack(anchor="w", pady=(14, 10))

        code_f = tk.Frame(f, bg=INPUT_BG, padx=20, pady=12)
        code_f.pack(fill="x")
        tk.Label(code_f, text=user_code, bg=INPUT_BG, fg=GREEN,
                 font=("Cascadia Code", 24, "bold")).pack()

        tk.Label(f, text=verify_url, bg=BG_EL, fg="#3d8ff5",
                 font=("Segoe UI Variable Text", 9),
                 cursor="hand2").pack(pady=(10, 4))

        tk.Label(f, text="⏳  Esperando login...", bg=BG_EL, fg=TEXT_SEC,
                 font=("Segoe UI Variable Text", 9)).pack()

        _btn(f, "Cancelar", self.destroy, primary=False, small=True).pack(pady=(16, 0))
