# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

FastAPI backend for the System 6 aquaculture monitoring platform. Provides REST APIs for authentication, water quality monitoring, alert workflows, density analysis, benefit reporting, edge device ingestion, and LLM-powered recommendations.

## Commands

```bash
uv sync                                                          # install dependencies
uv run uvicorn aquaculture_api.main:app --app-dir src --reload   # dev server (port 8000)
uv run pytest                                                    # run all tests
uv run pytest tests/test_health.py                               # run single test file
uv run pytest -k "test_name"                                     # run test by keyword
uv run pytest --tb=short                                         # short traceback on failure
uv run ruff check .                                              # lint
uv run ruff format --check .                                     # format check
uv run ruff format .                                             # auto-format
uv run mypy src                                                  # type check (strict mode)
```

Set `SEED_DATA=true` to seed demo data on startup. `start-demo.bat` from the project root does this automatically.

## Architecture

### Application factory

- **main.py** — `create_app(settings?)` builds the FastAPI app. Registers trace-id middleware (adds `X-Trace-Id` header), `ApiError` exception handler, health endpoint (`GET /api/health`), and all route modules. Module-level `app = create_app()` is the ASGI entry point.

### Configuration

- **config.py** — `Settings` frozen dataclass. `from_environment()` reads env vars: `APP_ENV`, `JWT_SECRET`, `EDGE_SECRET`, `DATABASE_URL`, `SEED_DATA`, `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`. Non-demonstration environments require real secrets (not `demo-only-*`).

### Data layer

- **models.py** — SQLAlchemy 2.0 declarative models with `Mapped[]` annotations. Key entities: `User`, `Pond`, `Device`, `WaterReading`, `Recommendation`, `ControlExecution`, `Alert`, `NotificationDelivery`, `MediaSample`, `DensityAnalysis`, `ThresholdRule`, `BenefitMetric`, `ExportRecord`, `ArchiveRecord`, `SyncBatch`, `EdgeNonce`, `AuditLog`.
- **store.py** — `create_store(settings)` → `Store(engine, sessions)`. Creates tables via `Base.metadata.create_all()`. Seeds demo data (3 users, 2 ponds, 1 device, threshold rules, benefit metrics, reference CSV readings) when `SEED_DATA=true` or DB is in-memory. Reference data loaded from `data/guangxi_reference_readings.csv`.

### Dependencies and security

- **deps.py** — FastAPI dependency injection. Module-level `_store`/`_settings` set by `configure()` at startup. Key dependencies: `session_dependency` (yields SQLAlchemy session), `current_user` (JWT auth), `scoped_pond` (RBAC pond access), `role_required` (role gate), `trace_id`. `ApiError` is the app-wide exception class caught by the global handler.
- **security.py** — `hash_credential`/`validate_credential` (PBKDF2-SHA256), JWT token issuance (`issue_access_token`, `issue_refresh_token`, `issue_offline_grant`), `validated_subject` for token verification, `sign_edge_payload`/`valid_edge_signature` for HMAC-SHA256 edge device authentication.

### Services

- **services.py** — Pure functions only. `make_id(prefix)` generates `{prefix}-{uuid12}`. `audit()` writes audit log entries. Payload serializers (`pond_payload`, `reading_payload`, `recommendation_payload`, etc.) convert ORM models to API response dicts.

### Schemas

- **schemas.py** — Pydantic `BaseModel` request/response models. All use strict field validation (e.g., `Field(ge=0, le=30)` for dissolved oxygen).

### Routes

Each route module in `routes/` exports a `router()` function returning an `APIRouter`:

- **auth** — `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/offline-grants`
- **ponds** — CRUD for ponds, devices, and water readings
- **recommendations** — Review, confirm, execute recommendations with state machine enforcement
- **alerts** — Alert lifecycle: acknowledge, resolve, close, quick-response
- **density** — Media sample creation, density analysis, review workflow
- **reports** — Benefit metrics, export with redaction, archive with approval
- **operations** — Health dashboard, threshold rule management, audit log access
- **edge** — HMAC-signed batch reading ingestion from edge devices with nonce replay protection
- **demo** — Low-oxygen scenario injection for demo/testing
- **agent** — LLM recommendation and analysis endpoints via DeepSeek agent

### Agent

- **agent.py** — `DeepSeekAgent` wraps DeepSeek chat API with aquaculture-specific system prompts. Falls back to `get_agent_response_fallback()` (rule engine) on API failure. Used by `routes/agent` and `routes/demo`.

### Testing

- Tests in `tests/`. Pytest with in-memory SQLite (`conftest.py` creates `TestClient` with `seed=True`).
- Fixtures: `app` (TestClient), `client`, `farmer_headers`/`technician_headers`/`admin_headers` (pre-authenticated JWT headers), `seeded_alert` (creates a demo alert).
- `make_edge_headers()` helper for HMAC-signed edge requests.
- `make_reading_event()` helper for water reading payloads.

### Alembic

Alembic is configured (`alembic.ini` + `alembic/`) for database migrations. `prepend_sys_path = ./src` so models are importable. Default DB URL: `sqlite+pysqlite:///./aquaculture.db`.

## Code Style

- 4-space indent, 100-char line length, Python 3.12 target.
- Ruff rules: `E4, E7, E9, F, I, B, UP, ANN` (pyupgrade + flake8-bugbear + type annotations).
- Mypy strict mode with `pydantic.mypy` plugin.
