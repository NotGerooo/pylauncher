"""
account_manager.py
------------------
Gestiona todas las cuentas del launcher.

Soporta dos tipos:
  - Cuentas offline (solo username, UUID determinista)
  - Cuentas Microsoft (OAuth 2.0, tokens, UUID oficial)

Responsabilidades:
  - CRUD de cuentas (agregar, eliminar, listar)
  - Persistencia segura en accounts.json
  - Cuenta activa (default)
  - Refresco automático de tokens Microsoft
"""

import json
import os
import uuid
from datetime import datetime
from typing import Optional
from utils.logger import get_logger

log = get_logger()

# ─── Modelos ────────────────────────────────────────────────────────────────

class AccountType:
    OFFLINE   = "offline"
    MICROSOFT = "microsoft"


class Account:
    def __init__(
        self,
        account_id:    str,
        account_type:  str,
        username:      str,
        player_uuid:   str,
        skin_path:     Optional[str] = None,
        access_token:  Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_expiry:  Optional[str] = None,
        avatar_url:    Optional[str] = None,
    ):
        self.id            = account_id
        self.type          = account_type
        self.username      = username
        self.uuid          = player_uuid
        self.skin_path     = skin_path
        self.access_token  = access_token
        self.refresh_token = refresh_token
        self.token_expiry  = token_expiry
        self.avatar_url    = avatar_url

    @property
    def is_microsoft(self) -> bool:
        return self.type == AccountType.MICROSOFT

    @property
    def display_type(self) -> str:
        return "Microsoft" if self.is_microsoft else "Offline"

    @property
    def is_token_expired(self) -> bool:
        if not self.token_expiry:
            return True
        try:
            expiry = datetime.fromisoformat(self.token_expiry)
            return datetime.utcnow() >= expiry
        except ValueError:
            return True

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "type":          self.type,
            "username":      self.username,
            "uuid":          self.uuid,
            "skin_path":     self.skin_path,
            "access_token":  self.access_token,
            "refresh_token": self.refresh_token,
            "token_expiry":  self.token_expiry,
            "avatar_url":    self.avatar_url,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Account":
        return cls(
            account_id    = data["id"],
            account_type  = data["type"],
            username      = data["username"],
            player_uuid   = data["uuid"],
            skin_path     = data.get("skin_path"),
            access_token  = data.get("access_token"),
            refresh_token = data.get("refresh_token"),
            token_expiry  = data.get("token_expiry"),
            avatar_url    = data.get("avatar_url"),
        )

    def __repr__(self):
        return f"Account({self.username!r}, {self.display_type})"


# ─── AccountError ────────────────────────────────────────────────────────────

class AccountError(Exception):
    pass


# ─── AccountManager ──────────────────────────────────────────────────────────

class AccountManager:

    _FILENAME = "accounts.json"

    def __init__(self, data_dir: str = "data"):
        self._data_dir  = data_dir
        self._file_path = os.path.join(data_dir, self._FILENAME)
        self._accounts: dict[str, Account] = {}
        self._active_id: Optional[str] = None
        self._load()

    # ─── CRUD ────────────────────────────────────────────────────────────────

    def add_offline_account(self, username: str) -> Account:
        self._validate_username(username)
        if self._find_by_username(username):
            raise AccountError(f"Ya existe una cuenta con el nombre '{username}'.")

        account_id  = str(uuid.uuid4())
        player_uuid = self._offline_uuid(username)

        account = Account(
            account_id   = account_id,
            account_type = AccountType.OFFLINE,
            username     = username,
            player_uuid  = player_uuid,
        )

        self._accounts[account_id] = account
        if not self._active_id:
            self._active_id = account_id

        self._save()
        log.info(f"Cuenta offline agregada: {username} (UUID: {player_uuid})")
        return account

    def add_microsoft_account(
        self,
        username:      str,
        player_uuid:   str,
        access_token:  str,
        refresh_token: str,
        token_expiry:  str,
        avatar_url:    Optional[str] = None,
    ) -> Account:
        existing = self._find_by_mc_uuid(player_uuid)
        if existing:
            existing.username      = username
            existing.access_token  = access_token
            existing.refresh_token = refresh_token
            existing.token_expiry  = token_expiry
            existing.avatar_url    = avatar_url
            self._save()
            log.info(f"Cuenta Microsoft actualizada: {username}")
            return existing

        account_id = str(uuid.uuid4())
        account = Account(
            account_id    = account_id,
            account_type  = AccountType.MICROSOFT,
            username      = username,
            player_uuid   = player_uuid,
            access_token  = access_token,
            refresh_token = refresh_token,
            token_expiry  = token_expiry,
            avatar_url    = avatar_url,
        )

        self._accounts[account_id] = account
        if not self._active_id:
            self._active_id = account_id

        self._save()
        log.info(f"Cuenta Microsoft agregada: {username} (UUID: {player_uuid})")
        return account

    def remove_account(self, account_id: str) -> bool:
        if account_id not in self._accounts:
            raise AccountError(f"Cuenta no encontrada: {account_id}")

        username = self._accounts[account_id].username
        del self._accounts[account_id]

        if self._active_id == account_id:
            remaining = list(self._accounts.keys())
            self._active_id = remaining[0] if remaining else None

        self._save()
        log.info(f"Cuenta eliminada: {username}")
        return True

    def set_active_account(self, account_id: str):
        if account_id not in self._accounts:
            raise AccountError(f"Cuenta no encontrada: {account_id}")
        self._active_id = account_id
        self._save()
        log.info(f"Cuenta activa: {self._accounts[account_id].username}")

    def get_active_account(self) -> Optional[Account]:
        return self._accounts.get(self._active_id)

    def get_account(self, account_id: str) -> Optional[Account]:
        return self._accounts.get(account_id)

    def get_all_accounts(self) -> list[Account]:
        accounts = list(self._accounts.values())
        accounts.sort(key=lambda a: (a.id != self._active_id, a.username))
        return accounts

    def get_account_by_username(self, username: str) -> Optional[Account]:
        """Retorna la cuenta cuyo username coincide (case-insensitive), o None."""
        return self._find_by_username(username)

    def update_skin(self, account_id: str, skin_path: str):
        account = self._accounts.get(account_id)
        if not account:
            raise AccountError(f"Cuenta no encontrada: {account_id}")
        if account.is_microsoft:
            raise AccountError("Las cuentas Microsoft usan la skin oficial automáticamente.")
        account.skin_path = skin_path
        self._save()
        log.info(f"Skin actualizada para {account.username}: {skin_path}")

    def update_tokens(
        self,
        account_id:    str,
        access_token:  str,
        refresh_token: str,
        token_expiry:  str,
    ):
        account = self._accounts.get(account_id)
        if not account:
            raise AccountError(f"Cuenta no encontrada: {account_id}")
        account.access_token  = access_token
        account.refresh_token = refresh_token
        account.token_expiry  = token_expiry
        self._save()
        log.debug(f"Tokens actualizados para: {account.username}")

    def build_session(self, account_id: str) -> dict:
        account = self._accounts.get(account_id)
        if not account:
            raise AccountError(f"Cuenta no encontrada: {account_id}")
        return {
            "username":     account.username,
            "uuid":         account.uuid,
            "access_token": account.access_token or "0",
            "is_online":    account.is_microsoft,
        }

    # ─── Helpers privados ────────────────────────────────────────────────────

    def _validate_username(self, username: str):
        import re
        if not username or not username.strip():
            raise AccountError("El nombre de usuario no puede estar vacío.")
        username = username.strip()
        if len(username) < 3:
            raise AccountError("El nombre de usuario debe tener al menos 3 caracteres.")
        if len(username) > 16:
            raise AccountError("El nombre de usuario no puede superar los 16 caracteres.")
        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            raise AccountError("El nombre solo puede contener letras, números y guiones bajos.")

    def _offline_uuid(self, username: str) -> str:
        return str(uuid.uuid3(uuid.NAMESPACE_DNS, f"OfflinePlayer:{username}"))

    def _find_by_username(self, username: str) -> Optional[Account]:
        u = username.lower()
        for acc in self._accounts.values():
            if acc.username.lower() == u:
                return acc
        return None

    def _find_by_mc_uuid(self, player_uuid: str) -> Optional[Account]:
        for acc in self._accounts.values():
            if acc.uuid == player_uuid and acc.is_microsoft:
                return acc
        return None

    # ─── Persistencia ────────────────────────────────────────────────────────

    def _save(self):
        os.makedirs(self._data_dir, exist_ok=True)
        data = {
            "active_id": self._active_id,
            "accounts":  [acc.to_dict() for acc in self._accounts.values()],
        }
        with open(self._file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log.debug(f"Cuentas guardadas: {len(self._accounts)} cuenta(s)")

    def _load(self):
        if not os.path.isfile(self._file_path):
            log.debug("accounts.json no encontrado, iniciando lista vacía.")
            return
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._active_id = data.get("active_id")
            for raw in data.get("accounts", []):
                acc = Account.from_dict(raw)
                self._accounts[acc.id] = acc
            log.info(f"Cuentas cargadas: {len(self._accounts)}")
        except (json.JSONDecodeError, KeyError) as e:
            log.error(f"Error al cargar accounts.json: {e}")