# ADR-003 — FastAPI as Backend Framework

| Field | Value |
|-------|-------|
| Date | 2024-01 |
| Status | Accepted |
| Deciders | Akshay |

## Context

TradeWatch needs a backend that can serve REST API requests from the React frontend, run background scheduled jobs, and make async I/O calls to the Dhan API and Telegram. The scanner needs to fan out 500 concurrent API requests efficiently.

## Decision

Use FastAPI (Python 3.11) as the backend framework.

## Rationale

- **Native async/await**: scanning 500 stocks concurrently via `asyncio.gather()` is natural; no thread pool workarounds needed
- **Auto-generated OpenAPI docs**: `/docs` (Swagger UI) available immediately for manual testing
- **Pydantic v2 integration**: request/response validation and serialization are first-class
- **Lifespan context manager**: clean startup/shutdown hooks for scheduler init and token validity checks
- **Single process**: APScheduler, API server, and services all run in one process — no IPC complexity

## Consequences

- SQLAlchemy's sync ORM requires `run_in_executor()` wrappers when called from async route handlers — or using synchronous endpoints (FastAPI supports both). Decision: use sync endpoints + async services where I/O-bound work occurs.
- Must be careful not to block the event loop in scheduler jobs — use `async def` for all job functions.

## Alternatives Considered

- **Django + DRF**: rejected — too much ceremony for a small single-user API; no native async
- **Flask**: rejected — no native async, requires workarounds for concurrent Dhan API calls
- **Sanic**: rejected — less mature ecosystem, smaller community
