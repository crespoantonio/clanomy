# Story 1.1: Project Initialization & Containerized Environment

Status: done

## Story

As a Developer,
I want to initialize the repository with FastAPI and Podman Compose,
so that I have a consistent, "Cloud-Ready" development environment.

## Acceptance Criteria

1. **Given** a clean directory, **when** I run `podman-compose up`, **then** a FastAPI server and a PostgreSQL database are running and connected.
2. **And** all core dependencies (`fastapi[all]`, `sqlmodel`, `cryptography`, `ollama`, `faster-whisper`, `python-telegram-bot`) are installed in the container.
3. **And** the project follows the service-layer directory structure defined in the Architecture Decision Document.
4. **And** a health check endpoint returns 200 OK and confirms database connectivity.

## Tasks / Subtasks

- [x] **Project Structure Initialization** (AC: 3)
  - [x] Create directory tree: `src/{api/routes,core,services,db}`, `tests/{api,services}`, `scripts/`
- [x] **Dependency Management** (AC: 2)
  - [x] Create `requirements.txt` with latest stable versions:
    - `fastapi[all]>=0.136.1`
    - `sqlmodel>=0.0.38`
    - `cryptography>=48.0.0`
    - `ollama>=0.6.2`
    - `faster-whisper>=1.2.1`
    - `python-telegram-bot>=22.7`
    - `pydantic-settings`
- [x] **Containerization with Podman** (AC: 1)
  - [x] Create `Containerfile` (Dockerfile) for FastAPI app (Python 3.12-slim recommended for stability).
  - [x] Create `podman-compose.yaml` orchestrating `app` and `db` (PostgreSQL 16).
  - [x] Configure volume persistence for PostgreSQL data.
- [x] **Base Application Setup** (AC: 1, 4)
  - [x] Create `src/core/config.py` using `BaseSettings` for `.env` management.
  - [x] Create `src/db/session.py` for SQLModel engine and session factory.
  - [x] Implement `src/main.py` with a `/health` endpoint that pings the DB.
- [x] **Verification** (AC: 1, 4)
  - [x] Run `podman-compose up` and verify logs show successful DB connection.

### Review Findings

- [x] [Review][Patch] Secret exposure in image [Containerfile]
- [x] [Review][Patch] Missing version for pydantic-settings [requirements.txt]
- [x] [Review][Patch] Health check leaks error details [src/main.py]
- [x] [Review][Patch] Missing files defined in architecture structure
- [x] [Review][Defer] Performance/Permission issues with Windows volume bind [docker-compose.yaml] — deferred, pre-existing

## Dev Notes

### Architecture Compliance
- **Directory Structure:** Must match the tree in `architecture.md#Project Structure & Boundaries`.
- **Naming:** Enforce `snake_case` for all files and directories.
- **Service Layer:** Even for this init, keep `session.py` and `config.py` in their respective folders.
- **Rootless Podman:** Ensure the `podman-compose.yaml` is compatible with rootless environments (standard for many dev setups).

### Technical Requirements
- **Postgres:** Use `postgres:16-alpine` for a lightweight footprint.
- **Environment:** Use `.env` for `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`.
- **Inference Ready:** Although not implemented yet, ensure the `app` container has enough overhead (shared memory) for later AI tasks.

### Project Structure Notes
- The repo currently contains BMad artifacts. The source code starts under the project root.
- **Conflict Avoidance:** Do not move or delete `_bmad` or `_bmad-output` folders.

### References
- [Architecture Decision Document: Project Structure](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L192)
- [Architecture Decision Document: Selected Starter](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L61)
- [PRD: Technical Success](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/prd.md#L50)

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

- `requirements.txt`
- `Containerfile`
- `docker-compose.yaml` (renamed for compatibility)
- `.env.example`
- `.env`
- `src/main.py`
- `src/core/config.py`
- `src/core/security.py` (placeholder)
- `src/core/encryption.py` (placeholder)
- `src/db/session.py`
- `src/db/models.py` (placeholder)
- `src/api/deps.py` (placeholder)
- `src/api/routes/` (dir)
- `src/services/` (dir)
- `tests/api/` (dir)
- `tests/services/` (dir)
- `scripts/` (dir)
