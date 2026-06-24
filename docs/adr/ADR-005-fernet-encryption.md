# ADR-005 — Fernet Symmetric Encryption for Stored Credentials

| Field | Value |
|-------|-------|
| Date | 2024-01 |
| Status | Accepted |
| Deciders | Akshay |

## Context

TradeWatch stores sensitive values in SQLite: Dhan access token and Telegram bot token. These are stored on disk and could be exposed if the DB file is accessed directly. A mechanism to encrypt them at rest is needed.

## Decision

Use Python's `cryptography` library (Fernet symmetric encryption, AES-128-CBC with HMAC-SHA256) to encrypt sensitive fields before writing to DB and decrypt on read.

The encryption key is stored at `backend/.secret_key` (path resolved as `Path(__file__).resolve().parents[2] / ".secret_key"` — always relative to the actual source file location, not cwd).

## Key Facts

- **Algorithm**: Fernet = AES-128-CBC + HMAC-SHA256
- **Key storage**: `backend/.secret_key` — auto-generated on first run if absent
- **Key exclusion**: `.secret_key` is in `.gitignore`; never committed
- **Fields encrypted**: `dhan_access_token`, `telegram_bot_token`
- **Masked display**: UI receives `****<last4>` — actual ciphertext never sent to frontend
- **Overwrite guard**: ConfigService checks `_is_masked(value)` before writing — masked display values are ignored silently

## Key Path Resolution

```python
KEY_PATH = Path(__file__).resolve().parents[2] / ".secret_key"
```

`parents[2]` from `backend/app/services/encryption.py` resolves to `backend/` — correct regardless of `cwd` at runtime.

## Consequences

- If `.secret_key` is lost, stored tokens cannot be decrypted and must be re-entered via Settings
- Fernet tokens are deterministic per key — the same plaintext always produces a different ciphertext (due to random IV), which is correct
- Adding new sensitive fields requires encrypting them in `ConfigService.update_config()` and decrypting in `get_decrypted_config()`

## Alternatives Considered

- **Plaintext storage**: rejected — trivially exposable via `sqlite3` CLI
- **OS keychain / Keyring**: considered — provides stronger key protection; rejected as it adds platform-specific dependencies and complexity; Fernet with a local key file is sufficient for this threat model
- **bcrypt / argon2 (hashing)**: rejected — tokens must be recoverable for API calls; hashing is one-way
