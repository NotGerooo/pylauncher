"""
auth_service.py
---------------
Gestiona la autenticación del jugador (modo offline).
"""
import hashlib
from utils.logger import get_logger
log = get_logger()


class AuthError(Exception):
    pass


class PlayerSession:
    def __init__(self, username, player_uuid, access_token, is_online=False):
        self.username = username
        self.uuid = player_uuid
        self.access_token = access_token
        self.is_online = is_online

    def to_dict(self):
        return {"username": self.username, "uuid": self.uuid,
                "access_token": self.access_token, "is_online": self.is_online}

    def __repr__(self):
        mode = "online" if self.is_online else "offline"
        return f"PlayerSession({self.username!r}, {mode})"


class AuthService:
    def create_offline_session(self, username: str) -> PlayerSession:
        self._validate_username(username)
        player_uuid = self._generate_offline_uuid(username)
        session = PlayerSession(
            username=username,
            player_uuid=player_uuid,
            access_token="0",
            is_online=False,
        )
        log.info(f"Sesion offline creada para: {username} (UUID: {player_uuid})")
        return session

    def _generate_offline_uuid(self, username: str) -> str:
        offline_prefix = f"OfflinePlayer:{username}"
        raw = hashlib.md5(offline_prefix.encode("utf-8")).digest()
        raw = bytearray(raw)
        raw[6] = (raw[6] & 0x0F) | 0x30
        raw[8] = (raw[8] & 0x3F) | 0x80
        hex_str = raw.hex()
        return f"{hex_str[0:8]}-{hex_str[8:12]}-{hex_str[12:16]}-{hex_str[16:20]}-{hex_str[20:32]}"

    @staticmethod
    def _validate_username(username: str):
        if not username or not username.strip():
            raise AuthError("El nombre de usuario no puede estar vacio")
        username = username.strip()
        if len(username) < 3:
            raise AuthError("El nombre de usuario debe tener al menos 3 caracteres")
        if len(username) > 16:
            raise AuthError("El nombre de usuario no puede tener mas de 16 caracteres")
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
        invalid = [c for c in username if c not in allowed]
        if invalid:
            raise AuthError(f"Caracteres no permitidos en el nombre: {invalid}")
