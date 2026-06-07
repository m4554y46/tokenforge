import os
import hashlib
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _get_machine_key():
    key_material = os.environ.get("COMPUTERNAME", "tokenforge-default")
    key_material += os.environ.get("USERNAME", "user")
    salt = b"tokenforge-salt-v1"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(key_material.encode()))
    return key


_cipher = None


def _get_cipher():
    global _cipher
    if _cipher is None:
        _cipher = Fernet(_get_machine_key())
    return _cipher


def encrypt_api_key(api_key):
    cipher = _get_cipher()
    return cipher.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key):
    cipher = _get_cipher()
    return cipher.decrypt(encrypted_key.encode()).decode()


def mask_api_key(api_key):
    if len(api_key) <= 8:
        return "****"
    return api_key[:4] + "..." + api_key[-4:]
