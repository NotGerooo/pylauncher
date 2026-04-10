"""
Auth — modo offline por defecto.
Extiende con flujo Microsoft OAuth según necesites.
"""
import uuid
from dataclasses import dataclass, field


@dataclass
class Account:
    username:     str
    uuid:         str  = field(default_factory=lambda: str(uuid.uuid4()))
    access_token: str  = ""
    is_premium:   bool = False


def offline_account(username: str) -> Account:
    """Crea una cuenta cracked/offline al instante."""
    uid = str(uuid.uuid3(uuid.NAMESPACE_DNS, username))
    return Account(username=username, uuid=uid)
