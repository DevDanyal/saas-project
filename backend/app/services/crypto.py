import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


def _fernet() -> Fernet:
    key = hashlib.sha256(settings.encryption_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_text(text: str) -> str:
    if not text:
        return text
    return _fernet().encrypt(text.encode()).decode()


def decrypt_text(token: str) -> str:
    if not token:
        return token
    if not token.startswith("gAAAAA"):
        return token
    return _fernet().decrypt(token.encode()).decode()