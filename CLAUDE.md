# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Smart aquaculture monitoring and control platform (System 6). Collects dissolved oxygen, pH, sonar density and image data; analyzes water quality and stocking density; outputs aeration, water exchange and stocking/harvest recommendations; validates farming benefits and stability under complex weather.

## Tech Stack

- **Frontend**: Vue 3 + TypeScript + Vite + Vue Router + Pinia + Element Plus (auto-imported via unplugin)
- **Backend**: Python 3.12 + FastAPI + SQLAlchemy (async-ready) + Uvicorn
- **Database**: SQLite (dev/demo), with Alembic migrations configured
- **AI Agent**: DeepSeek LLM integration for aquaculture recommendations (falls back to rule engine)
- **Quality tools**: ESLint + Oxlint + Prettier + vue-tsc + Vitest (frontend); Ruff + Mypy + Pytest (backend)

## Commands

### Run all checks (from project root)

```bash
npm run check
```

### Frontend

```bash
cd frontend
npm install
npm run dev              # dev server (proxies /api to localhost:8000)
npm run build            # type-check + vite build
npm run lint             # oxlint then eslint
npm run lint:fix         # auto-fix lint issues
npm run format           # prettier write
npm run format:check     # prettier check
npm run test:unit -- --run   # single run of vitest
npm run type-check       # vue-tsc --build
```

### Backend

```bash
cd backend
uv sync                                    # install dependencies
uv run uvicorn aquaculture_api.main:app --app-dir src --reload   # dev server
uv run pytest                              # run all tests
uv run pytest tests/test_health.py         # run single test file
uv run pytest -k "test_name"               # run test by keyword
uv run ruff check .                        # lint
uv run ruff format --check .               # format check
uv run ruff format .                       # auto-format
uv run mypy src                            # type check
```

### Demo startup (Windows)

`start-demo.bat` — deletes old DB, starts backend with `SEED_DATA=true` on port 8000, starts frontend on port 4173.

Demo accounts: `13800000001`/`13800000002`/`13800000003` (password: `demo-246810` for farmer/technician/admin roles).

## Architecture

### Backend (`backend/src/aquaculture_api/`)

- **main.py** — `create_app()` factory; registers middleware (trace-id), exception handlers, and all route modules. Entry: `aquaculture_api.main:app`.
- **config.py** — `Settings` dataclass loaded from env vars (`APP_ENV`, `JWT_SECRET`, `EDGE_SECRET`, `DATABASE_URL`, `SEED_DATA`, `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`). Non-demonstration envs require injected secrets.
- **models.py** — SQLAlchemy declarative models: `User`, `Pond`, `Device`, `WaterReading`, `AuditLog`, `Recommendation`, `ControlExecution`, `Alert`, `NotificationDelivery`, `MediaSample`, `DensityAnalysis`, `ThresholdRule`, `ExportRecord`, `BenefitMetric`, `ArchiveRecord`, `SyncBatch`, `EdgeNonce`.
- **store.py** — `create_store()` builds engine + session factory; seeds demo data (users, ponds, devices, thresholds, benefit metrics, reference CSV readings) when `SEED_DATA=true` or in-memory DB.
- **deps.py** — FastAPI dependency injection: `session_dependency`, `current_user` (JWT auth), `scoped_pond` (RBAC), `role_required`, `ApiError` exception class. Uses module-level `_store`/`_settings` configured at startup.
- **security.py** — JWT access/refresh/offline tokens (PyJWT), PBKDF2 credential hashing, HMAC edge payload signing.
- **services.py** — Pure functions: `make_id()`, `audit()`, and payload serializers for each model.
- **schemas.py** — Pydantic request/response models for all API endpoints.
- **agent.py** — `DeepSeekAgent` class calling DeepSeek chat API with aquaculture-specific system prompts; `get_agent_response_fallback()` for offline/fallback mode.
- **routes/** — One module per domain: `auth`, `ponds`, `recommendations`, `alerts`, `density`, `reports`, `operations`, `edge`, `demo`, `agent`. Each exports a `router()` function returning an `APIRouter`.

### Frontend (`frontend/src/`)

- **main.ts** — Creates Vue app with Pinia + Vue Router.
- **router/index.ts** — Routes: `/login`, `/dashboard`, `/monitoring`, `/alerts`, `/reports`, `/operations`, `/density`. Role-based guard (`farmer`, `technician`, `admin`). Offline guard reads cached grant from sessionStorage.
- **stores/platform.ts** — Single Pinia store (`usePlatformStore`) managing all app state: auth, observations, alert workflow (inject → review → confirm → execute → resolve → close), reports, operations, density analysis, agent advice. All API calls go through `createRequest()`.
- **utils/api.ts** — `createRequest()` factory: attaches Bearer token, handles 401 redirect.
- **utils/loading.ts** — Per-action loading state helper.
- **utils/storage.ts** — sessionStorage key constants and typed read helpers.
- **types/domain.ts** — Core domain types: `UserRole`, `Observation`, `OxygenAlert`, `AlertStatus`, `BenefitReport`, `DensityResult`, `AgentAdvice`, etc.
- **views/** — Page components: `LoginView`, `AppShellView` (layout), `DashboardView`, `MonitoringView`, `AlertsView`, `ReportsView`, `OperationsView`, `DensityView`.
- **components/** — `AgentPanel`, `TrendChart`, `VoiceLogin`.

### Key patterns

- **Role-based access control**: Three roles (farmer, technician, admin) with scoped pond access. Backend enforces via `role_required()` and `scoped_pond()`.
- **Source mode tracking**: Every data record carries a `source_mode` field (`simulation`, `auto`, `external_observation`) for provenance.
- **Edge ingestion**: HMAC-signed batch reading ingestion at `/api/v1/edge/readings:batch` with nonce replay protection.
- **Offline support**: JWT offline grants with permission scoping; frontend caches observations in sessionStorage.
- **Alert workflow state machine**: `generated → reviewed → confirmed → completed → resolved → closed` (or `rejected`).
- **Demo injection**: `/api/v1/demo/ponds/{id}/low-oxygen` creates a full alert+recommendation+notification chain for testing.
- **API proxy**: Vite dev server proxies `/api` to `http://localhost:8000`.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `demonstration` | Environment name; non-demo requires real secrets |
| `JWT_SECRET` | `demo-only-jwt-secret-not-for-production` | JWT signing key |
| `EDGE_SECRET` | `demo-only-edge-secret-not-for-production` | HMAC key for edge ingestion |
| `DATABASE_URL` | `sqlite+pysqlite:///./aquaculture.db` | SQLAlchemy database URL |
| `SEED_DATA` | `false` | Seed demo data on startup |
| `DEEPSEEK_API_KEY` | (empty) | DeepSeek API key for LLM agent |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API base URL |

## Code Style

- **Python**: 4-space indent, 100-char line length, Ruff rules `E4, E7, E9, F, I, B, UP, ANN`. Mypy strict mode with Pydantic plugin.
- **TypeScript/Vue**: 2-space indent, LF line endings. Linting: Oxlint then ESLint (Vue essential + TS + Vitest). Prettier for formatting.
- **Element Plus**: Auto-imported via `unplugin-vue-components` + `unplugin-auto-import`; no manual imports needed.
