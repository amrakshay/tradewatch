# ADR-002 — Alembic for Database Migrations

| Field | Value |
|-------|-------|
| Date | 2024-01 |
| Status | Accepted |
| Deciders | Akshay |

## Context

The initial schema is defined once, but TradeWatch will evolve: new columns may be added to support new strategies, new tables may be introduced. The DB file lives on the user's machine and must be upgradable without data loss.

## Decision

Use Alembic (SQLAlchemy's official migration tool) for all schema changes. The initial schema is captured as migration `0001_initial_schema`. `alembic upgrade head` is the canonical way to initialize or upgrade the database.

Schema creation via `Base.metadata.create_all()` is **not used** in production — only in testing (in-memory SQLite). Seeding (default `app_config` row) is handled by a separate `scripts/seed_db.py` script run after migrations.

## Rationale

- **Versioned schema**: every change is auditable in `alembic/versions/`
- **Safe upgrades**: users can upgrade TradeWatch and run `alembic upgrade head` without losing data
- **Autogenerate**: Alembic can diff SQLAlchemy models against the live DB and generate migration files automatically
- **Industry standard**: well-maintained, works with SQLAlchemy 2.x

## Workflow

```bash
# Initial setup
alembic upgrade head
python scripts/seed_db.py

# Adding a column
alembic revision --autogenerate -m "add_column_xyz"
# Review generated file
alembic upgrade head
```

## Consequences

- Team members must run `alembic upgrade head` after pulling schema changes — not just restart the server
- SQLite has limited `ALTER TABLE` support; Alembic works around this with `batch_alter_table` for column operations
- `alembic/versions/` must be committed to git so all environments use identical migration history

## Alternatives Considered

- **`Base.metadata.create_all()` only**: rejected — no incremental migration capability; existing data lost on schema change
- **Manual SQL migration scripts**: rejected — error-prone, no version tracking
