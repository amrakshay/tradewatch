# ADR-006 — Semi-Auto Dhan Token Renewal

| Field | Value |
|-------|-------|
| Date | 2024-01 |
| Status | Accepted |
| Deciders | Akshay |

## Context

SEBI regulations require brokers to issue access tokens with a 24-hour expiry. The Dhan API enforces this. TradeWatch needs to handle token renewal to stay operational across days without manual re-login every day.

Three renewal strategies were evaluated:

1. **Semi-auto (Renew Token API)**: Daily call to `POST /v2/RenewToken` with the active token. Extends expiry by 24h. Requires no additional secrets.
2. **TOTP-based full auto**: Store DHAN_PIN + TOTP secret; regenerate access token daily. Requires storing sensitive credentials (PIN). Dhan's full auth flow involves undocumented browser-based steps.
3. **OAuth flow**: Redirect to Dhan login page; user approves. Requires browser interaction — not automatable headlessly.

## Decision

Use **semi-auto renewal**: daily call to `POST /v2/RenewToken` at 09:00 IST (before market opens). The token in DB is updated on success. On failure: send a Telegram alert prompting the user to renew manually via Settings.

## Rationale

- **Simplest implementation**: no additional secrets stored beyond the access token itself
- **No PIN storage**: avoids storing Dhan PIN in the DB (higher security risk)
- **Reliable window**: 09:00 IST fires 30 minutes before market open; if renewal succeeds, the scanner at 15:45 and alert monitor through the day have a fresh token
- **Graceful failure path**: Telegram notification prompts manual action; user can renew via "Renew Token" button in Settings

## Implementation

```
TokenService.renew_token():
  POST /v2/RenewToken (Authorization: bearer <current_token>)
  On success: update dhan_access_token in DB (encrypted), update token_expires_at
  On failure: log error; send_token_expiry_warning() via Telegram
```

On startup: `check_token_validity()` via `GET /v2/profile`:
- If valid and expiry > 2 hours away: proceed
- If valid but expiring soon (< 2 hours): attempt immediate renewal
- If invalid: log warning; let Telegram alert user

## Consequences

- On weekends and holidays when the 09:00 job fires but market is closed, `POST /v2/RenewToken` still works (Dhan's API is available 24/7)
- If the machine is off at 09:00, `misfire_grace_time=300` gives a 5-minute window; if missed entirely, the token may expire mid-day without renewal
- User must manually re-enter token if it expires while the system is offline for >24h

## Alternatives Rejected

- **TOTP full-auto**: rejected — Dhan's full auth flow is undocumented at the API level; storing PIN creates a higher-value target
- **OAuth**: rejected — requires browser interaction; not automatable without a running browser instance
