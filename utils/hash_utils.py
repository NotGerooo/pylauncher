"""
hash_utils.py
-------------
Verificación de integridad de archivos descargados.
"""
import hashlib
import os
from utils.logger import get_logger
log = get_logger()

_CHUNK_SIZE = 8192


def compute_sha1(file_path: str):
    if not os.path.isfile(file_path):
        return None
    sha1 = hashlib.sha1()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(_CHUNK_SIZE):
                sha1.update(chunk)
        return sha1.hexdigest()
    except OSError:
        return None


def compute_sha256(file_path: str):
    if not os.path.isfile(file_path):
        return None
    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(_CHUNK_SIZE):
                sha256.update(chunk)
        return sha256.hexdigest()
    except OSError:
        return None


def verify_sha1(file_path: str, expected_hash: str) -> bool:
    actual = compute_sha1(file_path)
    if actual is None:
        return False
    return actual.lower() == expected_hash.lower()


def verify_sha256(file_path: str, expected_hash: str) -> bool:
    actual = compute_sha256(file_path)
    if actual is None:
        return False
    return actual.lower() == expected_hash.lower()
