import os, json, logging
import base64
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

_KEY_FILE = Path(os.environ.get("TOKENFORGE_KEY_DIR", os.path.expanduser("~/.tokenforge"))) / ".key"
_CIPHER_CACHE = None
_LOCK = False


def _ensure_key_file():
    """Generate a random Fernet key on first run, persist it."""
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes().strip()
    key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key + b"\n")
    return key


def _get_cipher():
    global _CIPHER_CACHE, _LOCK
    if _CIPHER_CACHE is not None:
        return _CIPHER_CACHE
    if _LOCK:
        return None
    _LOCK = True
    try:
        key = _ensure_key_file()
        _CIPHER_CACHE = Fernet(key)
    except Exception as exc:
        logger.warning("Falling back to machine-derived key: %s", exc)
        key_material = os.environ.get("COMPUTERNAME", "tokenforge-default")
        key_material += os.environ.get("USERNAME", "user")
        salt = b"tokenforge-salt-v1"
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
        key = base64.urlsafe_b64encode(kdf.derive(key_material.encode()))
        _CIPHER_CACHE = Fernet(key)
    finally:
        _LOCK = False
    return _CIPHER_CACHE


def encrypt_api_key(api_key: str) -> str:
    cipher = _get_cipher()
    if cipher is None:
        raise RuntimeError("Encryption unavailable")
    return cipher.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    cipher = _get_cipher()
    if cipher is None:
        raise RuntimeError("Encryption unavailable")
    try:
        return cipher.decrypt(encrypted_key.encode()).decode()
    except InvalidToken:
        raise ValueError("Invalid encrypted key — token may be corrupted or from a different machine")


def mask_api_key(api_key: str) -> str:
    if not api_key or len(api_key) <= 8:
        return "****"
    return api_key[:4] + "..." + api_key[-4:]
