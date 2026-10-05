# SafeFlux — Architecture

**Status:** Architecture baseline; Part 2 (authentication + authorization) implemented  
**Last updated:** 2026-10-04

---

## 1. Architecture Principles

1. AI reasons; deterministic software computes.
2. Experiments happen in a digital simulation, never on a real plant.
3. The engineer describes a change; SafeFlux explores the parameter space.
4. LLM calls are event-driven, not made for every telemetry tick.
5. Every important finding must trace back to deterministic evidence.
6. Backend authorization is authoritative.
7. Model output is untrusted until validated.
8. Security is continuous across every build part.
9. Authenticated product screens fit one viewport without clipping.
10. Existing working code is inspected before being rewritten.

---

## 2. Target Repository Layout

```text
SafeFlux/
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── features/
│   │   ├── hooks/
│   │   ├── layouts/
│   │   ├── pages/
│   │   ├── routes/
│   │   ├── stores/
│   │   ├── animations/
│   │   ├── types/
│   │   └── utils/
│   ├── .env.example
│   └── package.json
│
├── Backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── auth/
│   │   ├── core/
│   │   ├── database/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── simulator/
│   │   ├── safety/
│   │   ├── telemetry/
│   │   ├── search/
│   │   ├── agents/
│   │   ├── reports/
│   │   └── services/
│   ├── tests/
│   ├── .env.example
│   └── requirements.txt
│
├── docs/
│   ├── SAFEFLUX_MASTER.md
│   ├── ARCHITECTURE.md
│   └── SESSION_LOG.md
│
├── .gitignore
├── README.md
└── LICENSE
```

Any intentional architecture change must be documented.

---

## 3. High-Level System

```text
Frontend: React + TypeScript + Tailwind + React Flow + Recharts + GSAP
                              ↓ HTTPS / SSE
FastAPI: auth + APIs + orchestration + validation + authorization
             ↓               ↓                  ↓
       Persistence      Simulator/Safety    Agent/Reasoner
       SQLAlchemy       NumPy/SciPy         Nemotron
                                                ↓
                                       Nebius Token Factory
```

---

## 4. Frontend Architecture

Core stack:

- React
- Vite
- TypeScript
- Tailwind
- React Router
- Axios
- TanStack Query
- React Flow
- Recharts
- GSAP
- optional Three.js

Public routes:

```text
/
/login
/signup
```

Protected routes:

```text
/dashboard
/plant
/monitor
/analysis/new
/analysis/:id/live
/analysis/:id/failures/:failureId
/analysis/:id/investigation
/analysis/:id/safeguards
/analysis/:id/reverify
/history
/reports/:id
```

Frontend route protection does not replace backend authorization.

### Part 6 frontend modules

Implemented in Part 6 on real backend data only (no fixtures):

```text
src/layout/viewport.ts        classifyViewport(w,h) -> mobile|tablet|laptop|desktop
src/layout/useViewport.ts     rAF-throttled live measurement
src/dashboard/viewState.ts    deriveDashboardView() -> loading|offline|session-expired|error|empty|ready
src/api/failure.ts            classifyApiFailure() -> offline|session|unknown|null
src/api/sessionEvents.ts      one central session-expired event
src/animation/motion.ts       buildMotionPlan() -> pure motion plan from state
src/animation/useProcessMotion.ts  applies the plan in a gsap.context() (reverted on unmount)
src/analysis/assessmentStore.ts    in-memory cache of the last backend SafetyAssessment
src/hooks/useAssessment.ts    reactive views of that cache
src/components/plant/ProcessGraph.tsx   React Flow graph (Animated)
src/components/dashboard/{MetricGrid,FindingsPanel}.tsx
src/components/ui/{StatePanel,StatusBadge,TabBar}.tsx
```

The dashboard picks a plant, polls `telemetry/current` (5s), and shows the safety state,
seven metrics (temperature, pressure, feed flow, level, cooling, valve, pump), recent
findings and analysis status. Live values come from the telemetry frame; when no frame
exists the configured/initial plant values are shown and explicitly labelled `configured`
— the UI never fabricates numbers. The safety verdict shown is the one the backend returned
from `POST /simulations/run`; the frontend caches it in memory (dropped with the tab and on
sign-out) and computes nothing about safety itself.

---

## 5. One-Viewport Layout

Authenticated screens use a viewport workspace model.

Rules:

- avoid page-level vertical scrolling,
- never clip content as a shortcut,
- forms → steps,
- tables/lists → pagination,
- sections → tabs/routes,
- charts → switchable views,
- mobile → one major panel at a time,
- dialogs remain viewport-safe.

**Implemented (Part 6).** The app shell is pinned to `h-[100dvh]` and the content region is
`overflow-hidden`, so the document itself never scrolls; each view owns its own bounded
region. `classifyViewport(width, height)` checks **height as well as width**
(`width<768` → mobile, `<1200` → tablet, `>=1200` with `height<800` → laptop, else desktop).
Wide layouts (`laptop`/`desktop`) place the process graph beside the metrics/findings
column; narrow or short layouts switch the panels behind a `TabBar` so every panel stays
reachable. On the plant page only the fact grid and the plant list are internal scroll
regions. Verified for 1920×1080, 1366×768, tablet and mobile portrait.

---

## 6. Animation Architecture

GSAP is used only for meaningful state transitions:

- process flow,
- status transitions,
- agent loop,
- failure chains.

Clean up timelines, prefer transform/opacity, respect reduced motion, avoid decorative infinite animation.

**Implemented (Part 6).** `buildMotionPlan(input)` is a pure function producing
`{pipeline: flow|static, rotor: spin|still, pulse: none|warn|crit, flashOnStateChange}` from
the safety state, pump state and reduced-motion flag. `useProcessMotion` applies it inside
`gsap.context(..., root)` and calls `ctx.revert()` on unmount, so no timeline leaks; it
targets named nodes only — the pipeline edge (`strokeDashoffset`), the pump rotor
(`rotation`), a `[data-sf-pulse]` node (opacity yoyo) and a `[data-sf-state]` flash. Under
`prefers-reduced-motion` the plan is fully static: no flow, no rotor, no pulse, no flash.

Three.js is optional — it was **not** installed, because a Three.js scene would not add
genuine value to a 2D P&ID-style diagram.

---

## 7. Backend Bootstrap

FastAPI owns:

- routing,
- auth,
- validation,
- authorization,
- services,
- orchestration,
- safe errors,
- SSE/live updates,
- provider integration.

Keep `main.py` small. Business logic belongs in services/modules.

---

## 8. Configuration

Backend:

```env
ENVIRONMENT=
FRONTEND_URL=
DATABASE_URL=
JWT_SECRET=
NEBIUS_API_KEY=
NEBIUS_BASE_URL=
NEBIUS_MODEL=
```

Frontend:

```env
VITE_API_BASE_URL=
```

No hard-coded secrets. Real `.env` files stay out of Git.

---

## 9. Authentication

Implemented in Part 2:

```text
Signup/Login
   ↓
Auth Service
   ↓
Argon2id (argon2-cffi)
   ↓
HttpOnly authenticated cookie (safeflux_session)
   ↓
get_current_user()
```

**Endpoints** — the Part 2 brief named `/api/auth/*`; Part 1 fixed the API prefix at
`/api/v1`, so auth endpoints are served at **`/api/v1/auth/*`** (single canonical prefix):

```text
POST /api/v1/auth/signup    → create account, start session (201)
POST /api/v1/auth/login     → sign in, start session (200)
POST /api/v1/auth/logout    → clear session cookie (200, idempotent)
GET  /api/v1/auth/me        → current user (auth required)
GET  /api/v1/auth/session   → strict alias of /me (hidden from schema)
```

**Session token** — JWT HS256 signed with `JWT_SECRET`, claims `sub`, `iat`, `exp`,
`iss="safeflux"`, `typ="session"`; TTL from `SESSION_TTL_MINUTES`. Delivered **only** in
the `safeflux_session` cookie: `HttpOnly` always, `Secure` in production only,
`SameSite=Lax`, `Path=/`, `Max-Age` matching the token TTL. No `localStorage`.

User:

```text
id            (UUID string — non-enumerable)
full_name
email         (unique, indexed, stored lower-cased)
password_hash (Argon2id)
is_active
created_at
updated_at
```

Never return password hashes. Login failures are generic (`401 Invalid email or
password.`); unknown emails burn comparable Argon2 time so timing cannot enumerate
accounts; duplicate signups return `409` case-insensitively.

---

## 10. Authorization / Ownership

Resources:

```text
User
 ├── Plant
 ├── AnalysisRun
 │    ├── Scenario
 │    ├── SimulationResult
 │    ├── SafetyFinding
 │    └── AgentDecision
 └── Report
```

Load resources with authenticated ownership checks.

Never trust frontend-provided owner IDs.

Test IDOR/cross-user access.

Implemented in Part 2 (`app/auth/ownership.py`): every owned model carries an `owner_id`
FK to `User.id`, and access goes through `get_owned_or_404(db, model, id, user)` or
`ensure_owner(resource, user)`. Cross-user and missing resources both return **404** so an
unauthorized caller cannot learn whether an object exists. The verified session user is
the only identity used for the check — never a client-supplied `user_id`/`owner_id`.
Ownership is exercised against a test resource in `Backend/tests/test_auth.py`; the
Plant model adopts the same helpers in Part 3 (`Backend/app/api/routes/plants.py`), and
AnalysisRun / Report follow in Parts 6–9.

Part 3 (`Plants`): every route requires `get_current_user`, `owner_id` is set from the
session user on create and never read from the payload, and all reads/writes/deletes go
through `get_owned_or_404`. `Backend/tests/test_plants.py` covers IDOR for read, list,
state, update and delete.

---

## 11. Input and XSS

Backend uses Pydantic for types, ranges, lengths, enums and compute budgets.

Frontend validation is UX, not the security boundary.

Avoid raw HTML. Treat LLM/user content as untrusted. If Markdown is introduced, render safely.

---

## 12. CORS / Headers

CORS uses explicit origins. Never wildcard credentials.

Security headers should include sensible versions of:

- X-Content-Type-Options
- Referrer-Policy
- frame/CSP protection
- CSP where practical
- HSTS in production HTTPS when appropriate

---

## 13. Rate Limiting

Rate-limit at minimum:

- signup/login
- AI analysis
- simulation
- search
- re-verification
- other expensive endpoints where needed

Also enforce hard request budgets.

Implemented in Part 1: in-memory fixed-window limiter per client IP over `/api/v1/*`
(`app/core/rate_limit.py`), health probe exempt, configured via `RATE_LIMIT_REQUESTS` /
`RATE_LIMIT_WINDOW_SECONDS`.

Implemented in Part 2: `auth_rate_limit(request, bucket)` gives sensitive endpoints their
own tighter per-IP buckets. `/auth/signup` and `/auth/login` use separate buckets (so
failed logins never block session checks), configured via `AUTH_RATE_LIMIT_ATTEMPTS` /
`AUTH_RATE_LIMIT_WINDOW_SECONDS`; a breach returns `429 RATE_LIMITED` with `Retry-After`.
Buckets live on `app.state.auth_limiters` so each app instance uses its own Settings.

A `BodySizeLimitMiddleware` (`app/core/body_limit.py`) rejects oversized request bodies
with `413 PAYLOAD_TOO_LARGE` (via `MAX_REQUEST_BODY_BYTES`) before the body is parsed.

Implemented in Part 4: `simulation_rate_limit(request)` gives the expensive
`POST /simulations/run` endpoint its own per-IP bucket (`SIM_RATE_LIMIT_RUNS` /
`SIM_RATE_LIMIT_WINDOW_SECONDS`), stored on `app.state.simulation_limiters`, on top of the
hard simulation compute budgets. Endpoint-specific budgets for AI/search arrive with
their features.

Implemented in Part 5: telemetry **SSE stream connections** are capped by
`TELEMETRY_MAX_STREAMS` / `TELEMETRY_MAX_STREAMS_PER_PLANT` / `TELEMETRY_MAX_STREAMS_PER_USER`
(`app/telemetry/service.py`); an over-limit request gets `429 RATE_LIMITED` with
`Retry-After` before the stream opens, and the slot is released on disconnect.

---

## 14. API Format

Success:

```json
{"success": true, "data": {}}
```

Error:

```json
{
  "success": false,
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Safe message"
  }
}
```

Do not expose stack traces, SQL details, file paths or secrets.

---

## 15. Database

Development: SQLite.  
Production-ready: PostgreSQL-compatible SQLAlchemy.

Rules:

- ORM/parameterized queries,
- env-based DB URL,
- ownership filters,
- no committed DB files,
- migrations when schema stabilizes.

Implemented entities:

- `users` (Part 2),
- `plants`, `plant_configs`, `plant_states`, `safety_limits`, `safeguard_configs` (Part 3).

Planned entities:

AnalysisRun, EngineeringChange, Scenario, SimulationResult, SafetyFinding, SafeguardEvent, AgentDecision, Report.

---

## 16. Plant Domain

Implemented in Part 3 (`Backend/app/models/plant.py`, `app/schemas/plant.py`,
`app/api/routes/plants.py`). Endpoints are `/api/v1/plants/*` (the brief's `/api/plants/*`
maps onto the single canonical `/api/v1` prefix fixed in Part 1).

The locked MVP process:

```text
Feed Tank → Pump P-101 → Heated Reactor R-101 → Outlet Valve V-101 → Product Tank
```

One plant is five rows (all owned by `Plant`, cascading on delete):

- **`Plant`** — identity + ownership (`owner_id` → `users.id`, indexed) + timestamps.
- **`PlantConfig`** — static engineered configuration: `feed_flow_lpm` (0–500),
  `cooling_pct` / `valve_position_pct` / `heater_power_pct` (0–100), `shutdown_delay_s`
  (0–3600).
- **`PlantState`** — dynamic initial condition: `pump_running`, `temperature_c`
  (−50–1000), `pressure_bar` (0–500), `level_pct` (0–100). The pump flag lives here
  because it is equipment state, not configuration.
- **`SafetyLimits`** — configured trip limits: `max_temperature_c`, `max_pressure_bar`,
  `max_level_pct`.
- **`SafeguardConfig`** — `auto_shutdown_enabled`, per-variable high trips, `trip_delay_s`.

Rules:

- every endpoint is authenticated and owner-scoped (`get_owned_or_404`);
- `PlantCreate` rejects an initial state already above a trip limit, and every `PATCH`
  re-checks the same invariant (rollback + `422 VALIDATION_ERROR`) so a partial update can
  never leave an inconsistent plant;
- `extra="forbid"` + server-side range bounds on every numeric field; errors never echo
  values; responses never expose `owner_id`.

These values are **design inputs to the simulation** — SafeFlux has no path to real
industrial equipment. For sensor faults (Parts 5+), keep true process state separate from
observed sensor state.

UI: `frontend/src/components/plant/PlantWizard.tsx` (5-step, one-viewport) and
`ProcessTopology.tsx` (static React Flow preview; no fake live movement).

---

## 17. Simulator

Implemented in Part 4 (`Backend/app/simulator/`): constants, scenario/fault data model,
compute budgets, the process model, the deterministic engine and the result container.
Endpoint `POST /api/v1/simulations/run` (`app/api/routes/simulations.py`), owner-scoped.

Input: the plant's `PlantConfig` + initial `PlantState`, plus a scenario (duration, time
step, deterministically scheduled faults, sensor faults). Output (`SimulationResult`):
columnar time series, per-variable extrema, events, summary metrics and version metadata.

### State and equations

State vector `y = [volume_l, temperature_c]`; everything else is algebraic. Units: `L`,
`lpm`, `°C`, `bar`, `s`, `kW`, `kJ/(L·K)`.

```text
level_pct      = 100 · V / V_nominal                                  (clamped 0–100)
feed_lpm       = feed_flow_lpm · fault_feed · pump_factor             (0 if pump off)
valve_fraction = (valve_position_pct / 100) · fault_outlet
outlet_lpm     = K_out · valve_fraction · sqrt(level/100)
heater_kw      = HEATER_MAX_KW · heater_power_pct / 100
cooling_kw     = UA_max · cooling_pct/100 · fault_cooling · max(T − T_coolant, 0)
pressure_bar   = P_atm + k_T · max(T − T_ref, 0) + k_L · (level/100)

dV/dt = feed_lpm/60 − outlet_lpm/60
dT/dt = (heater_kw − cooling_kw + CP·Q_feed·(T_feed − T)) / (CP·max(V, V_min))
```

Expanding `d(V·T)/dt` with `dV/dt = feed − outlet` cancels the outlet enthalpy term, so
only *feed* advection appears — draining a well-mixed vessel does not by itself change its
temperature. At the level bounds the volume derivative is zeroed (excess feed spills at
100 %; no liquid drains at 0 %). Cooling never adds heat (the driving force is clamped at
zero), and a dry vessel holds its temperature.

### Determinism and integration

SciPy `solve_ivp` (`RK45`, fixed `rtol=1e-9`/`atol=1e-11`) integrates **one call per
smooth segment** between scheduled fault changes, so step changes are honoured rather than
smeared across an adaptive step. There is no RNG: identical inputs give identical output,
and tests assert that by comparing whole result documents.

### Faults

Deterministic step changes, applied in start-time order: cooling degradation, complete
cooling loss, outlet restriction, valve stuck, feed increase, pump variation. **Sensor
faults** (bias or freeze) affect *observed* series only — `true_temperature_c` vs
`observed_temperature_c` — so a failed sensor can never change the physics. **Shutdown
delay**: the first armed limit crossing schedules an emergency shutdown `trip_delay_s`
later (grid-resolved) — stop the feed pump and cut the heater — and the run is
re-integrated once with it applied. A dry vessel (no liquid) holds its temperature rather
than heating an empty shell.

### Abuse protection

Budgets are enforced before integration: `SIM_MAX_DURATION_S`, `SIM_MIN_TIME_STEP_S`,
`SIM_MAX_SAMPLES`; the endpoint also has its own per-IP rate-limit bucket
(`SIM_RATE_LIMIT_RUNS` / `SIM_RATE_LIMIT_WINDOW_SECONDS`) and the global body-size guard.

### Assumptions and limitations

Surfaced in every result's `metadata.assumptions` / `metadata.limitations`: perfectly-mixed
single volume, water-like constant properties, fixed feed temperature, linear jacket
cooling, gravity-driven outlet, level clamping, and a **pressure proxy that is not vapour
pressure**. No reaction kinetics, no heat-exchanger dynamics, no pump curve, no pipe
hydraulics. The model is a decision-support prototype — never certified, never a
controller. Nominal equipment magnitudes (e.g. the 2 MW heater) are illustrative values
chosen to exercise the model, not vendor data.

No random core telemetry.

---

## 18. Safety Engine

Implemented in Part 5 (`Backend/app/safety/`, tests in `Backend/tests/test_safety.py`).
Pure deterministic software: it reads simulator series and events and classifies each
monitored variable against configured limits. **No LLM decides numeric threshold truth.**

Statuses: **SAFE**, **NEAR_LIMIT**, **SAFEGUARD_ACTIVATED**, **VIOLATION**. A
`SafetyFinding` records `type` (variable), `status`, `severity`, `timestamp_s`,
`measured_value`, `limit`, `near_limit` and `scenario_id`. The near-limit band is
configurable (`SafetyThresholds.near_limit_fraction`, default 0.9; clamped 0.5–1.0).

Per-variable precedence:

- **VIOLATION** — the actual (guarded) trajectory exceeds the limit;
- **SAFEGUARD_ACTIVATED** — the variable tripped in the unprotected pass and the applied
  emergency shutdown kept the tested run within its limit;
- **NEAR_LIMIT** — entered the near-limit band but never exceeded the limit;
- **SAFE** — nothing approached the limit.

The overall `SafetyAssessment.status` is the worst finding status.

**Safeguard timing** (`evaluate_safeguards`) records, per high alarm and for the emergency
shutdown, `trigger_time_s`, `response_time_s`, `violation_time_s`, `prevented` and a note.
To make *prevented* vs *too late* physically meaningful, the shutdown is assessed with its
trip driven by the **high-alarm setpoint** (`near_limit_fraction · limit`) via the
simulator's `SafeguardSettings.trip_fraction` (default 1.0 keeps Part 4 behaviour). A pure
trip-at-the-limit model can only ever be too late, because the limit is already exceeded
when the trip fires. Verdicts are simulation-only and never a claim about a real plant.

`POST /api/v1/simulations/run` returns `{result, safety}` and feeds telemetry.

---

## 19. Telemetry

Implemented in Part 5 (`Backend/app/telemetry/`, routes in
`Backend/app/api/routes/telemetry.py`, tests in `Backend/tests/test_telemetry_api.py`).

```text
Simulator
  ↓
TelemetryService
  ↓
CurrentStateStore
  ↓
SSE/API
  ↓
Frontend
```

A run's deterministic result is converted to one `TelemetryFrame` per sample (true values
and observed sensor values kept separate). The `CurrentStateStore` keeps only the latest
frame plus a **bounded** per-plant history under a bounded number of plants, so a long run
can never grow memory without limit.

Routes (all authenticated and owner-scoped via `get_owned_or_404`; cross-user → 404):

- `GET /api/v1/plants/{id}/telemetry/current` — latest frame (or `null`);
- `GET /api/v1/plants/{id}/telemetry/history?limit=` — recent bounded history;
- `GET /api/v1/plants/{id}/telemetry/stream` — SSE replay of stored frames, ending with a
  `complete` event (the MVP replays a finite deterministic trajectory; clients reconnect
  and immediately receive current state).

**SSE, not WebSocket** — the traffic is server→client only. Connection limits
(`TELEMETRY_MAX_STREAMS` / `_PER_PLANT` / `_PER_USER`) are enforced *before* the stream
opens (over-limit → `429`), and the slot is released in the stream's `finally` on
completion or client disconnect. **No LLM per tick.**

The monitor (`frontend/src/pages/MonitorPage.tsx`, `hooks/useTelemetry.ts`) hydrates recent
history, streams new frames, and reconnects with capped backoff; the pure reconnect/merge
logic lives in `frontend/src/telemetry/streamState.ts` and is unit-tested with the Node
test runner (`frontend/tests/streamState.test.ts`).

The chart workspace (`frontend/src/components/monitor/TelemetryChart.tsx`) is built on
**Recharts** with switchable Temperature / Pressure / Level / Flow series, near-limit and
limit `ReferenceLine`s, and the series downsampled to 240 points so a long run stays cheap.
Animation is disabled because frames already replay one by one and `prefers-reduced-motion`
must hold without extra configuration.

Future real telemetry adapters remain read-only.

---

## 20. Scenario Search

Deterministic search may use:

- coarse sweeps,
- refinement,
- binary-search-style refinement when monotonicity is justified,
- sensitivity analysis,
- bounded combinations.

Every run has limits for scenario count, duration, samples, refinement depth and timeout.

No eval/exec.

---

## 21. AI Provider

Provider abstraction hides Nebius details.

Required:

NEBIUS_API_KEY, NEBIUS_BASE_URL, NEBIUS_MODEL.

Backend only. Exact model ID verified against actual account/catalog.

---

## 22. Agent Loop

```text
UNDERSTAND
→ IDENTIFY
→ CHOOSE DIRECTION
→ CALL ALLOWLISTED TOOL
→ DETERMINISTIC SEARCH/SIMULATION
→ OBSERVE
→ NEXT ACTION
→ COUNTERFACTUAL/SAFEGUARD
→ EXPLAIN
```

Bound steps, model calls, simulations, timeout and cost.

No shell, arbitrary Python, arbitrary SQL, arbitrary files or real plant control.

---

## 23. Prompt Injection

Engineering-change text is untrusted.

The agent must not obey attempts to reveal prompts/secrets, change tool permissions, bypass budgets or execute code.

Tools independently enforce auth, ownership and numeric limits.

---

## 24. Reports

Reports are generated from stored evidence:

- change,
- affected equipment,
- scenarios,
- failures,
- boundaries,
- counterfactuals,
- safeguards,
- AI explanation,
- limitations.

AI explanations cannot overwrite deterministic values.

---

## 25. Testing

Frontend unit tests (Part 6) cover the pure modules under the Node test runner
(`frontend/tests/*.test.ts`, run with `npm run test:unit`): viewport classification
(desktop, short laptop, tablet, mobile, degenerate sizes), dashboard view-state derivation
(loading/offline/session-expired/error/empty/ready and tone/motion outputs), API failure
classification, the motion plan (including reduced-motion → fully static), and the
telemetry stream state machine. Visual/layout states are exercised through these pure
modules plus `tsc`, `oxlint` and a production build; the environment provides no browser
frame capture, so no screenshot pass is claimed.

Unit:
auth utilities, simulator equations, safety, safeguards, scenario validation, boundary search, provider parsing.

Integration:
auth/session, plant ownership, simulation→safety, search→simulation, telemetry auth, agent tools, provider.

Security:
cross-user access, malformed input, compute abuse, rate limits, XSS content, invalid auth, prompt injection, malformed AI output.

Seeded:
safe baseline, cooling loss, outlet restriction, feed increase, hidden combined failure, successful safeguard, late safeguard.

---

## 26. Dependency / Secret Hygiene

At every part:

- review dependencies,
- remove unused ones,
- avoid blind major upgrades,
- inspect tracked files,
- scan Git for secrets,
- check frontend bundle for server secrets,
- verify .gitignore.

If a secret appears in Git history, rotate it.

---

## 27. Logging

May log IDs, model/provider, scenario, timing and error category.

Never log passwords, hashes, JWTs, cookies, API keys or authorization headers.

---

## 28. Git Workflow

```text
test → lint → diff review → meaningful commit → push
```

Use coherent commits. Do not fake commit count.

---

## 29. Ten-Part Mapping

```text
1 Secure foundation
2 Auth + authorization
3 Plant setup
4 Simulator
5 Safety + telemetry
6 Dashboard
7 Scenario search
8 Nebius/Nemotron agent
9 Investigation/reverify/report UX
10 Hardening/deployment/audit
```

Run Duck after each part.

---

## 30. Debugging Duck Architecture Checks

On `Duck`, verify:

- MASTER alignment
- auth/access control
- env/secrets
- CORS/headers/debug
- input/XSS/rate limits
- DB/password security
- Git secret scan
- deterministic simulator
- AI not numerical truth
- bounded allowlisted agent
- evidence traceability
- one-viewport UI
- tests
- docs
- meaningful Git history

Report ON TRACK ✅ / DRIFTING ⚠️ / BLOCKED/BROKEN ❌ and the smallest next action.
