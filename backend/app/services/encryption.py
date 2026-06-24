from pathlib import Path
from cryptography.fernet import Fernet

# encryption.py is at backend/app/services/encryption.py → parents[2] = backend/
_DEFAULT_KEY_PATH = Path(__file__).resolve().parents[2] / ".secret_key"


class EncryptionService:
    def __init__(self, key_path: Path = _DEFAULT_KEY_PATH):
        key_path = Path(key_path)
        if not key_path.exists():
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_bytes(Fernet.generate_key())
        self._fernet = Fernet(key_path.read_bytes())

    def encrypt(self, value: str) -> str:
        """Encrypt a plaintext string. Returns base64 Fernet token."""
        if not value:
            return ""
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, token: str) -> str:
        """Decrypt a Fernet token back to plaintext."""
        if not token:
            return ""
        return self._fernet.decrypt(token.encode()).decode()

    def mask(self, value: str) -> str:
        """Return a display-safe masked version: first 2 + '...' + last 3 chars."""
        if not value or len(value) <= 6:
            return "***"
        return value[:2] + "..." + value[-3:]

    def is_set(self, encrypted_token: str) -> bool:
        """Return True if a non-empty encrypted value is stored."""
        return bool(encrypted_token)


# Module-level singleton — import this everywhere
encryption_service = EncryptionService()
