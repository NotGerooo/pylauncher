import json
import os
import uuid
import hashlib
import urllib.request
from utils.logger import get_logger

log = get_logger()

_ACCOUNTS_FILE = os.path.join("data", "accounts.json")


class AccountError(Exception):
    pass


class Account:
    def __init__(self, username, account_id=None, skin_url="", cape_url=""):
        self.id = account_id or str(uuid.uuid4())
        self.username = username
        self.skin_url = skin_url
        self.cape_url = cape_url

    @property
    def player_uuid(self):
        prefix = f"OfflinePlayer:{self.username}"
        raw = bytearray(hashlib.md5(prefix.encode("utf-8")).digest())
        raw[6] = (raw[6] & 0x0F) | 0x30
        raw[8] = (raw[8] & 0x3F) | 0x80
        h = raw.hex()
        return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "skin_url": self.skin_url,
            "cape_url": self.cape_url,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            username=data["username"],
            account_id=data.get("id"),
            skin_url=data.get("skin_url", ""),
            cape_url=data.get("cape_url", ""),
        )

    def __repr__(self):
        return f"Account({self.username!r})"


class AccountManager:
    def __init__(self, accounts_file=_ACCOUNTS_FILE):
        self._file = accounts_file
        self._accounts: dict[str, Account] = {}
        self._active_id: str = ""
        self._load()

    def create_account(self, username: str) -> Account:
        username = username.strip()
        if not (3 <= len(username) <= 16):
            raise AccountError("El nombre debe tener entre 3 y 16 caracteres")
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
        if any(c not in allowed for c in username):
            raise AccountError("Solo letras, números y guiones bajos")
        if any(a.username.lower() == username.lower() for a in self._accounts.values()):
            raise AccountError(f"Ya existe una cuenta con el nombre '{username}'")

        skin_url, cape_url = self._fetch_skin_info(username)
        account = Account(username=username, skin_url=skin_url, cape_url=cape_url)
        self._accounts[account.id] = account
        if not self._active_id:
            self._active_id = account.id
        self._save()
        log.info(f"Cuenta creada: {username}")
        return account

    def get_all_accounts(self) -> list[Account]:
        return list(self._accounts.values())

    def get_account(self, account_id: str) -> Account | None:
        return self._accounts.get(account_id)

    def get_active_account(self) -> Account | None:
        return self._accounts.get(self._active_id)

    def set_active_account(self, account_id: str):
        if account_id not in self._accounts:
            raise AccountError("Cuenta no encontrada")
        self._active_id = account_id
        self._save()

    def delete_account(self, account_id: str):
        if account_id not in self._accounts:
            raise AccountError("Cuenta no encontrada")
        del self._accounts[account_id]
        if self._active_id == account_id:
            self._active_id = next(iter(self._accounts), "")
        self._save()

    def refresh_skin(self, account_id: str):
        account = self._accounts.get(account_id)
        if not account:
            raise AccountError("Cuenta no encontrada")
        skin_url, cape_url = self._fetch_skin_info(account.username)
        account.skin_url = skin_url
        account.cape_url = cape_url
        self._save()
        log.info(f"Skin actualizada para {account.username}: {skin_url or 'default'}")

    def _fetch_skin_info(self, username: str) -> tuple[str, str]:
        try:
            url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
            req = urllib.request.Request(url, headers={"User-Agent": "PyLauncher/0.1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                player_uuid = data.get("id", "")
            if not player_uuid:
                return "", ""
            profile_url = f"https://sessionserver.mojang.com/session/minecraft/profile/{player_uuid}"
            req2 = urllib.request.Request(profile_url, headers={"User-Agent": "PyLauncher/0.1.0"})
            with urllib.request.urlopen(req2, timeout=5) as resp2:
                profile = json.loads(resp2.read().decode())
            import base64
            for prop in profile.get("properties", []):
                if prop.get("name") == "textures":
                    textures_raw = json.loads(base64.b64decode(prop["value"]).decode())
                    textures = textures_raw.get("textures", {})
                    skin_url = textures.get("SKIN", {}).get("url", "")
                    cape_url = textures.get("CAPE", {}).get("url", "")
                    return skin_url, cape_url
        except Exception as e:
            log.debug(f"No se pudo obtener skin de {username}: {e}")
        return "", ""

    def _load(self):
        if not os.path.isfile(self._file):
            return
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for a in data.get("accounts", []):
                acc = Account.from_dict(a)
                self._accounts[acc.id] = acc
            self._active_id = data.get("active_id", "")
            log.info(f"Cuentas cargadas: {len(self._accounts)}")
        except Exception as e:
            log.error(f"Error cargando cuentas: {e}")

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._file), exist_ok=True)
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump({
                    "accounts": [a.to_dict() for a in self._accounts.values()],
                    "active_id": self._active_id,
                }, f, indent=4)
        except Exception as e:
            log.error(f"Error guardando cuentas: {e}")