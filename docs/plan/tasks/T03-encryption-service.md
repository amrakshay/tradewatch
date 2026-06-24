# T03 — EncryptionService

| Field | Value |
|-------|-------|
| Phase | 0 |
| Depends on | T01 |
| Unlocks | T04 |
| Estimate | 0.5 day |
| Status | ⬜ Not Started |

## Goal
Implement a Fernet-based encryption service for storing sensitive credentials at rest. Key is generated on first run and stored in `backend/.secret_key`.

## Files to Create

- `backend/app/services/encryption.py`

## Steps

### `backend/app/services/encryption.py`

```python
import os
import html
from pathlib import Path
from cryptography.fernet import Fernet

# Resolve key path relative to this file, not cwd.
# encryption.py is at backend/app/services/encryption.py
# → parents[2] = backend/
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
```

### Add `.secret_key` to `.gitignore`

Verify `backend/.secret_key` is already covered by the `.gitignore` pattern. It should be — check that the file contains:
```
backend/.secret_key
```

## Important Notes

- The `.secret_key` file is auto-generated on first run. If it's deleted, all stored credentials become undecryptable and must be re-entered in Settings.
- Never commit `.secret_key`. Document this clearly in the project README.
- The `encrypt()` method is idempotent for the same value + key, but produces different ciphertext each call (Fernet uses a random IV) — this is correct behaviour.

## Done When
- `python -c "from app.services.encryption import encryption_service; t = encryption_service.encrypt('hello'); print(encryption_service.decrypt(t))"` prints `hello`
- `encryption_service.mask('eyJhbGciOiJIUzI1NiJ9')` returns `"ey...J9"`
- `backend/.secret_key` is created on first instantiation
- Running the same code twice does not regenerate the key (stable key)
