---
title: 'Setup Alembic Database Migrations Engine'
type: 'feature'
created: '2026-08-26'
status: 'done'
baseline_commit: '52cb8b09fcf702be267d5064adaea378baec5d46'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Clanomy currently relies on `SQLModel.metadata.create_all()`, which only creates new tables but cannot perform `ALTER TABLE` schema updates on existing QA and Production PostgreSQL databases.

**Approach:** Configure Alembic with dynamic `settings.DATABASE_URL` resolution, generate a baseline schema migration, and integrate automated `alembic upgrade head` into the FastAPI lifespan startup for seamless multi-environment deployments.

## Boundaries & Constraints

**Always:**
- Dynamic Database URL: Alembic must read `DATABASE_URL` directly from `src.core.config.settings` (preserving environment variable overrides from Render QA/Prod).
- Auto-Migration on Boot: The application startup lifecycle (`lifespan`) must safely execute pending migrations before accepting webhooks.
- Multi-Database Compatibility: Support both PostgreSQL (`psycopg` / `postgresql://`) and SQLite (`sqlite:///`) test engines.
- Test Suite Parity: All existing 189 unit and integration tests must continue passing with zero regressions.

**Ask First:**
- Deleting or altering existing column names in production tables.

**Never:**
- Hardcode database credentials or URLs in `alembic.ini` or migration scripts.
- Rely on manual SSH execution for production database upgrades.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Container Startup (New Schema) | Deployment with unapplied migration | `alembic upgrade head` applies new revision automatically | Logs error and prevents broken boot |
| Container Startup (Up to date) | Database already at `head` | Checks `alembic_version` in ~2ms, does nothing, boots normally | N/A |
| Multi-Environment Parity | Render QA vs Render Prod DB URLs | Alembic connects to active `settings.DATABASE_URL` dynamically | Fails fast if DB unreachable |
| Test Suite Execution | SQLite in-memory / temporary DB | Executes `init_db()` or migrations cleanly without file lock errors | Fallback to `create_all` for ephemeral in-memory SQLite |

</frozen-after-approval>

## Code Map

- `requirements.txt` -- Add `alembic>=1.13.0` dependency
- `alembic.ini` -- Alembic global configuration file pointing to `alembic/`
- `alembic/env.py` -- Migration environment importing `src.core.config.settings` and `SQLModel.metadata`
- `alembic/script.py.mako` -- Migration template with SQLModel / SQLAlchemy support
- `alembic/versions/0001_initial_baseline.py` -- Baseline migration for `family`, `user`, `transaction`, `familyinvite` tables
- `src/db/session.py` -- Add `run_migrations()` helper using Alembic Python command API
- `src/main.py` -- Invoke `run_migrations()` during FastAPI `lifespan` startup
- `tests/db/test_migrations.py` -- Test suite verifying Alembic configuration, upgrade command, and schema parity

## Tasks & Acceptance

**Execution:**
- [x] `requirements.txt` -- Add `alembic>=1.13.0` -- Ensure production containers install Alembic
- [x] `alembic.ini` -- Create configuration file -- Standard configuration for Alembic CLI and programmatic runner
- [x] `alembic/env.py` -- Configure target metadata and dynamic database connection -- Bind `SQLModel.metadata` and `settings.DATABASE_URL`
- [x] `alembic/script.py.mako` -- Create migration file template -- Standard Mako template for version generation
- [x] `alembic/versions/0001_initial_baseline.py` -- Author initial baseline revision -- Capture complete existing schema
- [x] `src/db/session.py` -- Implement `run_migrations()` function -- Programmatic `alembic.command.upgrade(alembic_cfg, "head")`
- [x] `src/main.py` -- Update `lifespan` handler -- Execute migrations on application startup
- [x] `tests/db/test_migrations.py` -- Add unit tests for Alembic execution -- Verify migration engine reliability

**Acceptance Criteria:**
- Given an application boot in any environment, when `lifespan` runs, then Alembic automatically upgrades the target database to `head`.
- Given a QA or Production database connection string in `DATABASE_URL`, when Alembic executes, then it connects dynamically without reading hardcoded local strings.
- Given the full test suite, when `pytest` runs, then 100% of tests pass.

## Spec Change Log

*(Empty - completed cleanly on initial iteration)*

## Verification

**Commands:**
- `.\venv\Scripts\python.exe -m pytest tests/db/test_migrations.py` -- expected: All migration tests pass
- `.\venv\Scripts\python.exe -m pytest` -- expected: 100% pass rate across all 193 tests

## Suggested Review Order

**Core Migration Runner & Startup Integration**

- Dynamic database URL resolution and metadata binding
  [`env.py:28`](../../alembic/env.py#L28)

- Programmatic upgrade head runner with safe fallback
  [`session.py:14`](../../src/db/session.py#L14)

- Lifespan invocation executing migrations on container boot
  [`main.py:10`](../../src/main.py#L10)

**Schema Baseline & Config**

- Initial baseline schema definition for existing tables
  [`0001_initial_baseline.py:18`](../../alembic/versions/0001_initial_baseline.py#L18)

- Global Alembic configuration and logging
  [`alembic.ini:1`](../../alembic.ini#L1)

- Dependency declaration for Alembic
  [`requirements.txt:13`](../../requirements.txt#L13)

**Test Suite & Verification**

- Migration runner and schema verification tests
  [`test_migrations.py:19`](../../tests/db/test_migrations.py#L19)

