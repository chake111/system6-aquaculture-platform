# Aquaculture Monitoring Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a runnable aquaculture monitoring and control demonstration platform covering FR-01 through FR-12, with traceable official water-quality observations and explicitly labelled simulation flows.

**Architecture:** Keep the existing Vue/FastAPI baseline. The backend uses SQLAlchemy entities and services behind REST endpoints; public reference observations are imported from a committed, reproducible crawler output while control, notifications and edge events use clearly identified simulated adapters. The Vue application consumes those contracts through typed data and exposes the five-minute operational workflow with role-aware views.

**Tech Stack:** Vue 3, TypeScript, Vite, Pinia, Element Plus, Vitest; FastAPI, SQLAlchemy, Pydantic, pytest, Ruff and Mypy.

---

## File Map

| Area | Files | Responsibility |
| --- | --- | --- |
| Official observations | `backend/scripts/fetch_reference_readings.py`, `backend/data/usgs_reference_readings.csv`, `doc/data-sources.md` | Retrieve and document at least 20 authentic paired DO/pH observations from an official source. |
| Backend platform | `backend/src/aquaculture_api/{models,schemas,security,store,services,main}.py` | Persistence, authentication, scope checks, domain workflows, adapters and API routes. |
| Backend tests | `backend/tests/test_platform_api.py`, `backend/tests/test_reference_data.py` | API permissions, lifecycle workflows, provenance, idempotency and safety labels. |
| Frontend application | `frontend/src/{App.vue,router/index.ts,stores/platform.ts,types/domain.ts,views/*.vue,styles/main.css}` | Field-friendly role-based application, monitoring, control, alerts, reports and operations views. |
| Frontend tests | `frontend/src/__tests__/{App,workflow}.spec.ts` | Navigation, labels, role visibility and closed-loop interaction behavior. |
| Evidence | `doc/{demo-script,acceptance-results,deployment}.md`, `doc/tasks/progress.md` | Reproducible execution evidence and honest completion status. |

### Task 1: Data Provenance And Core Contract

**Files:**
- Create: `backend/scripts/fetch_reference_readings.py`
- Create: `backend/data/usgs_reference_readings.csv`
- Create: `doc/data-sources.md`
- Create: `backend/tests/test_reference_data.py`

- [ ] **Step 1: Write failing tests for public observation provenance**

Assert that the imported fixture contains at least 20 records, includes paired `dissolved_oxygen_mg_l` and `ph`, identifies the official URL/station, and is marked `external_observation` rather than `simulation`.

- [ ] **Step 2: Confirm RED**

Run: `uv --directory backend run pytest tests/test_reference_data.py -q`

Expected: failure because the importer and data file do not exist.

- [ ] **Step 3: Implement the official-data fetcher and tracked dataset**

Fetch USGS NWIS instantaneous values for station `01463500`, parameters `00300` and `00400`, retain 24 paired observations, and write provenance fields alongside each record. Document that the source is environmental reference monitoring rather than the Guangdong demonstration pond.

- [ ] **Step 4: Confirm GREEN**

Run: `uv --directory backend run pytest tests/test_reference_data.py -q`

Expected: all provenance and minimum-row assertions pass.

### Task 2: Auth, Scope And Monitoring Backend

**Files:**
- Create: `backend/src/aquaculture_api/{models,schemas,security,store,services}.py`
- Modify: `backend/src/aquaculture_api/main.py`
- Create: `backend/tests/test_platform_api.py`

- [ ] **Step 1: Write failing API tests**

Cover login for farmer/technician/admin, rejected anonymous access, restricted admin endpoints, listed ponds, external readings latest/history, source labels and audit creation.

- [ ] **Step 2: Confirm RED**

Run: `uv --directory backend run pytest tests/test_platform_api.py -q`

Expected: missing platform endpoints.

- [ ] **Step 3: Implement SQLAlchemy-backed contracts**

Add scoped users/ponds/readings/audit models, demo credential issuance, HMAC bearer validation, source-aware seeded readings and `/api/v1` auth/pond/readings APIs while preserving `/api/health`.

- [ ] **Step 4: Confirm GREEN**

Run: `uv --directory backend run pytest tests/test_platform_api.py -q`

Expected: authentication, monitoring and provenance tests pass.

### Task 3: Control, Alert, Density, Sync, Reports And Operations Backend

**Files:**
- Modify: `backend/src/aquaculture_api/{models,schemas,services,main}.py`
- Modify: `backend/tests/test_platform_api.py`

- [ ] **Step 1: Extend failing workflow tests**

Test low-oxygen simulated ingestion, generated recommendation and alert, confirmation/simulated execution/feedback, alert acknowledgement/resolution/closure, density review, duplicate edge events, benefit report labels, export redaction, health/audit/rule/archive admin restrictions.

- [ ] **Step 2: Confirm RED**

Run: `uv --directory backend run pytest tests/test_platform_api.py -q`

Expected: workflow routes absent.

- [ ] **Step 3: Implement minimal complete business workflows**

Use SQLAlchemy entities and explicit state validation. Simulated adapters must return `source_mode=simulation` or `execution_mode=simulation`; reports must distinguish external reference observations and unverified demonstration outcomes.

- [ ] **Step 4: Confirm GREEN and static checks**

Run: `npm run backend:format:check && npm run backend:lint && npm run backend:type-check && npm run backend:test`

Expected: exit code `0`.

### Task 4: Vue Field Dashboard And Workflow

**Files:**
- Create/Modify: `frontend/src/{App.vue,router/index.ts,stores/platform.ts,types/domain.ts,styles/main.css,views/*.vue}`
- Modify/Create: `frontend/src/__tests__/*.spec.ts`

- [ ] **Step 1: Write failing UI tests**

Assert login selection, role navigation visibility, external observation label, monitoring rows, simulation warning, control feedback, alert lifecycle, report disclaimer and admin operations presence.

- [ ] **Step 2: Confirm RED**

Run: `npm run frontend:test`

Expected: tests fail against the initial Vue welcome page.

- [ ] **Step 3: Implement accepted dashboard concept**

Build responsive, high-contrast Vue views and typed local demo workflow reflecting the backend contracts; make provenance and simulation status visible at all decision points.

- [ ] **Step 4: Confirm GREEN and frontend checks**

Run: `npm run frontend:format:check && npm run frontend:lint && npm run frontend:type-check && npm run frontend:test && npm run frontend:build`

Expected: exit code `0`.

### Task 5: Evidence And Full Gate

**Files:**
- Create: `doc/{deployment,demo-script,acceptance-results}.md`
- Modify: `doc/tasks/progress.md`

- [ ] **Step 1: Record source, commands and limitations**

Document login identities, API/UI workflow, official data retrieval URL/time/row count, simulated adapter boundaries and which production metrics still require real Guangdong pond validation.

- [ ] **Step 2: Execute complete verification**

Run: `npm run check`

Expected: format, lint, type checks, frontend tests/build and backend tests all exit successfully.

- [ ] **Step 3: Update truthful progress**

Check only module/acceptance items supported by the executed tests and evidence; keep real-world outcome and onsite validation limitations explicit.

### Task 6: Offline Access And Field Interaction Closure

**Files:**
- Modify: `frontend/src/stores/platform.ts`
- Modify: `frontend/src/views/{LoginView,AppShellView,MonitoringView}.vue`
- Modify: `frontend/src/types/domain.ts`
- Modify: `frontend/src/__tests__/{App,workflow}.spec.ts`

- [ ] **Step 1: Write failing UI tests for offline and assistive behavior**

Assert that login requests a restricted seven-day offline grant, displays its expiry and permitted cached-only scope, shows online/offline state, falls back visibly when browser speech support is absent, and never exposes sensitive operations while offline.

- [ ] **Step 2: Confirm RED**

Run: `npm run frontend:test -- --run`

Expected: failures because the current page contains only static offline/voice copy and has no grant, network-state or fallback behavior.

- [ ] **Step 3: Implement minimal state and UI behavior**

Store the signed offline grant metadata without interpreting it as an online token, retain the last successful monitoring payload with acquisition time, observe connectivity events, render cached-data warnings on offline reads, and encapsulate speech availability/failure as a non-blocking field-input fallback.

- [ ] **Step 4: Confirm GREEN**

Run: `npm run frontend:format:check && npm run frontend:lint && npm run frontend:type-check && npm run frontend:test`

Expected: exit code `0`.

### Task 7: Weak-Network And Alert Reliability Closure

**Files:**
- Modify: `backend/src/aquaculture_api/{models,schemas,main}.py`
- Modify: `backend/tests/{test_platform_api,test_compliance_api}.py`
- Modify: `frontend/src/stores/platform.ts`
- Modify: `frontend/src/views/{AppShellView,OperationsView}.vue`
- Modify: `frontend/src/__tests__/workflow.spec.ts`

- [ ] **Step 1: Write failing backend and frontend tests**

Assert that separate low-oxygen edge events inside the active-alert window do not create duplicate open alerts/recommendations, sync batches expose last acknowledgement for the management display, and an offline page identifies retained cached content rather than live data.

- [ ] **Step 2: Confirm RED**

Run: `npm run backend:test && npm run frontend:test -- --run`

Expected: failures for alert deduplication and weak-network display gaps.

- [ ] **Step 3: Implement the bounded reliability behavior**

Merge an additional active low-oxygen threshold event into the current simulated alert timeline or evidence count instead of generating a parallel open alert; expose sync status already persisted by batch ingestion; display it through the existing operations/connectivity surface without introducing a real-device claim.

- [ ] **Step 4: Confirm GREEN**

Run: `npm run backend:format:check && npm run backend:lint && npm run backend:type-check && npm run backend:test && npm run frontend:test -- --run`

Expected: exit code `0`.

### Task 8: Operational Acceptance Evidence

**Files:**
- Create: `backend/scripts/verify_demo_acceptance.py`
- Create/Modify: `backend/tests/test_acceptance_evidence.py`
- Modify: `doc/{acceptance-results,deployment}.md`
- Modify: `doc/tasks/progress.md`

- [ ] **Step 1: Write a failing evidence test or executable assertion**

Validate that an executable demonstration check records the simulated edge-retention boundary and a 500-request concurrent login run, reports observed success percentage and latency, and labels the result as local demonstration evidence rather than a production capacity claim.

- [ ] **Step 2: Confirm RED**

Run: `uv --directory backend run pytest tests/test_acceptance_evidence.py -q`

Expected: failure until the executable evidence runner exists.

- [ ] **Step 3: Implement and run the evidence runner**

Use the FastAPI demonstration app with bounded local concurrent requests, emit reproducible JSON/text evidence under `doc/evidence/`, and document its environment, fixtures and limitations. Add a deterministic backup/restore rehearsal for demonstration fixture/state data or explicitly leave it unchecked if no actual restoration is executed.

- [ ] **Step 4: Confirm GREEN and record honest status**

Run: `uv --directory backend run pytest tests/test_acceptance_evidence.py -q` and the runner command recorded in `doc/acceptance-results.md`.

Expected: recorded local evidence identifies what was measured and retains unresolved real-deployment/onsite claims as open.

### Task 9: Module Reconciliation And Final Gate

**Files:**
- Modify: `doc/tasks/*.md`
- Modify: `doc/{acceptance-results,demo-script,deployment}.md`

- [ ] **Step 1: Review every module checklist against executed evidence**

Use only implemented paths and fresh command output to mark applicable items; do not mark real notification, real device, onsite operation, production benefit or regulatory destruction as complete.

- [ ] **Step 2: Execute complete verification**

Run: `npm run check`

Expected: exit code `0`, with current frontend and backend test totals recorded in acceptance results.

- [ ] **Step 3: Publish reproducible limitations**

Keep real pond calibration, hardware/provider integration, long-running availability, onsite usability and real-cycle economic outcomes explicitly outside the demonstrated acceptance claim.
