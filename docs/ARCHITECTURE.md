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
│   │   ├── analysis/        assessment cache + evidence helpers
│   │   ├── animation/       pure motion planners + GSAP hooks (unit-tested)
│   │   ├── api/             typed API clients (axios + session events)
│   │   ├── auth/            AuthProvider + session context
│   │   ├── components/      ui/, plant/, monitor/, dashboard/, auth/, three/
│   │   ├── dashboard/       pure dashboard view-state derivation
│   │   ├── hooks/           TanStack Query hooks
│   │   ├── layout/          viewport + graph-orientation classifiers
│   │   ├── layouts/         AppLayout (workspace shell), PublicLayout
│   │   ├── pages/           route components
│   │   ├── routes/          route table + ProtectedRoute
│   │   ├── search/          pure search-plan mirror (Part 7)
│   │   ├── telemetry/       stream state machine
│   │   ├── three/           landing digital-twin scene (lazy)
│   │   ├── types/           API/domain mirrors
│   │   └── utils/           validation, error message helpers
│   ├── tests/               node --test pure-module suites (87 tests)
│   ├── .env.example
│   └── package.json
│
├── Backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── ai/              allowlisted agent tools + provider transport
│   │   ├── analyses/        autonomous analysis pipeline (Part 9)
│   │   ├── api/             routers (auth, plants, simulations, searches, …)
│   │   ├── auth/            Argon2id + JWT session
│   │   ├── core/            settings, security headers, rate limits
│   │   ├── database/
│   │   ├── models/
│   │   ├── safety/          deterministic safety engine
│   │   ├── schemas/
│   │   ├── search/          bounded boundary search (Part 7)
│   │   ├── simulator/       lumped deterministic process model
│   │   └── telemetry/       current/history/SSE
│   ├── tests/               pytest suites (326 tests)
│   ├── .env.example
│   └── requirements.txt
│
├── scripts/
│   ├── dev.mjs              `npm run dev` — backend + frontend in one command
│   └── test.mjs             `npm test` — lint → unit → build → pytest
│
├── docs/
│   ├── SAFEFLUX_MASTER.md
│   ├── ARCHITECTURE.md
│   ├── SESSION_LOG.md
│   ├── QA_TEST_PLAN.md
│   ├── QA_PART1_REPORT.md
│   └── QA_PART2_REPORT.md
│
├── package.json             root one-commands (dev / build / test)
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
- Three.js (landing hero only, dynamically imported)

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
src/layout/graphLayout.ts     chooseGraphOrientation(w,h) -> horizontal|vertical
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

### Part 7 frontend modules

```text
src/types/search.ts           mirror of the search API document
src/search/plan.ts            pure mirror of the server bounds + presets + presentation
src/search/SearchControls.tsx plan editor rendered from GET /searches/capabilities
src/search/SearchResults.tsx  tabbed, paginated, filterable evidence viewer
src/pages/AnalysisNewPage.tsx one-viewport composition (panes on wide, tabs on narrow)
src/api/searches.ts           GET /searches/capabilities, POST /searches/run
src/hooks/useSearches.ts      capability query + run mutation (pending state = double-click guard)
```

The browser never composes a search the server would reject: `draftIssues()` mirrors
`SearchLimits.validation_errors()` so Run is disabled with a reason, and per-request budgets
can only tighten. Presets are filtered against the capabilities payload, and presets encode
a *plan*, never a verdict.

Part 8 adds **no frontend module**. The investigation API is implemented and tested
server-side, and `/analysis/:id/live` still renders its placeholder — the live investigation
UX belongs to Part 9. Nothing in Part 8 is claimed as a UI feature.

### Visual-transformation modules (implemented, 2026-10-08)

```text
src/index.css                     design tokens + utilities (panel, panel-inset, stat-num, grid-bg, glow-*)
src/components/ui/Panel.tsx       standard instrument panel (title, hint, actions, internal scroll)
src/components/ui/Instrument.tsx  InstrumentTile + radial Gauge (mono numerals, limit tick, sparkline, rail)
src/components/ui/StatusBadge.tsx semantic safety chip (label always present — colour is never the only signal)
src/components/ui/Icons.tsx       one inline icon set (no icon dependency)
src/components/auth/AuthShell.tsx shared dark split shell for login/signup (+ decorative signal sweep)
src/components/TwinCanvas.tsx     lazy Three.js host: idle-load, intersection/visibility gating, dispose
src/three/reactorTwin.ts          stylized reactor skid scene + status mapping (normal/warning/critical)
src/animation/failureSequence.ts  pure ordering of the engine's recorded findings (unit-tested)
src/animation/agentStages.ts      pure mapping of recorded pipeline events to the stage rail (unit-tested)
src/animation/routeTransitionPlan.ts pure decision of which navigations may animate (unit-tested)
```

Rules this layer obeys:

- **One surface language.** Pages compose `Panel` / `InstrumentTile` / `Gauge` / `TabBar`;
  raw `slate-800`-style surfaces do not appear in new work, and safety colour comes from the
  `safe` / `warn` / `crit` tokens only.
- **Motion is planned, never improvised.** Each animation has a pure planner that returns
  what may move (or nothing under reduced motion) and is unit-tested; the React hook applies
  it inside `gsap.context()` and reverts on unmount.
- **The 3D twin carries no data.** It illustrates the process *shape* (feed → pump → reactor →
  outlet) and mirrors only the existing health probe; every number in the product still comes
  from the backend.
- **Nothing new is loaded globally.** `three` is reached through `import()` from the landing
  hero after first paint, so no authenticated route pays for it.

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
regions.

The graph adds a second, independent decision: `chooseGraphOrientation(width, height)`
keeps the conventional horizontal P&ID while it still renders at a legible scale and
rotates it to a vertical spine otherwise, so the five-stage line is never merely present-
but-unreadable in a tall, narrow box. React Flow's zoom floor sits below the scale the
layout needs, and a `ResizeObserver` re-fits on resize — without that, a resized window
keeps a stale transform and clips the outlet units, and the default 0.5 floor alone was
enough to cut off the valve and product tank at 1366×768. Because React Flow caches each
node's measured size **on the node object**, the graph is rebuilt only when a displayed
value changes; rebuilding it on every render makes React Flow re-measure forever and drop
the edges entirely (which is what happened on the monitor, where every streamed frame
re-renders the page).

**Verified in a real browser** at 1920×1080, 1366×768, 768×1024 and 390×844, both on load
and across live resizes: zero page scroll, zero horizontal overflow, and every graph node
inside its canvas at each size.

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

React Flow mounts — and re-mounts — its edge elements after measuring the nodes, and a
remount discards the inline dash styles GSAP wrote. The pipeline tween is therefore applied
to whichever main-flow paths are still unstyled, on mount and again on every graph change
(an observer on the graph subtree, with new tweens registered through `ctx.add`), so the
flow survives both the initial measurement pass and a layout change. Verified live: the
four main-flow edges carry an advancing `strokeDashoffset` while telemetry is present, the
warning pulse yoyos, and the pump rotor stays `transform: none` while the pump is stopped.
The pipeline is deliberately static when no telemetry exists — a flowing line would claim
data that is not there.

**Visual transformation (2026-10-08).** The design-system shell, dashboard, live monitor,
analysis creation, live investigation, failure detail, root cause, safeguards, re-verify,
history and report screens were re-laid-out on the instrument language above, and motion was
extended with three further planned behaviours: the recorded-sequence reveal on evidence
screens (staggered, inline-styled, killed with its styles on unmount), the stage rail driven
by the engine's own events, and 200–500 ms page transitions that reduced motion removes.

**Three.js (2026-10-08).** Earlier revisions judged a 3D scene unnecessary next to a 2D
P&ID diagram, and that judgement held for the workspace. It now exists in exactly one place —
the landing hero — because the marketing surface benefits from a process visual, and it is
engineered as a guest: dynamic `import()` after first paint, animation loop bound to
intersection + tab visibility, simplified geometry under 560 px, a single static frame under
`prefers-reduced-motion`, a static SVG schematic when WebGL is missing, and a `dispose()` that
releases every geometry, material and the renderer. No workspace page renders 3D.

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
hard simulation compute budgets.

Implemented in Part 7: `search_rate_limit(request)` gives `POST /searches/run` the
**tightest bucket in the API** (`SEARCH_RATE_LIMIT_RUNS` / `SEARCH_RATE_LIMIT_WINDOW_SECONDS`,
default 20 per minute), stored on `app.state.search_limiters`, because one accepted request
runs many simulations. All three server-side limiters now share one lazy-cache helper
(`_server_limiter`) and one enforcement helper (`_enforce`), so the `429 RATE_LIMITED`
envelope and `Retry-After` header are identical everywhere while the buckets stay isolated
per endpoint. The AI analysis bucket arrives with Part 8.

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

## 20. Scenario Search (implemented, Part 7)

Pipeline, and nothing else in it:

```text
Search → Simulator → Safety Engine → Evidence
```

No AI participates. The search is deterministic: identical inputs produce identical
results, and every returned number was produced by the simulator and the safety engine.

### Backend modules

```text
app/search/constants.py     engine + method versions, every hard ceiling, disclaimer
app/search/variables.py     the allowlist: name -> typed simulator effect (no eval/exec)
app/search/budgets.py       SearchLimits (the plan) + SearchBudget (runtime counter)
app/search/spec.py          SearchSpec, SearchMode, axes, canonical case keys
app/search/evaluate.py      one cached, budget-charged case evaluation
app/search/sweep.py         coarse sweep, safe-end-first traversal
app/search/monotonic.py     monotonicity classification of a sampled series
app/search/refine.py        bisection when monotonic, densify otherwise
app/search/sensitivity.py   one-at-a-time influence ranking
app/search/combinations.py  bounded two-variable grid
app/search/result.py        counts, failures, boundary candidates, evidence document
app/search/engine.py        orchestration + versions()
app/schemas/search.py       strict request schemas (allowlist enum, ceilings)
app/api/routes/searches.py  GET /searches/capabilities, POST /searches/run
```

### Bounded by construction

Two layers: `SearchLimits` (max scenarios, combinations, refinement depth, timeout, max
duration, min time step, max samples) and `SearchBudget`, the runtime counter charged
*before* every simulation. A request may only tighten a limit — a larger value is a `422`
rejection, never a silent clamp. When a limit does stop a search, the result is marked
`truncated`, the reason is recorded in `budget`/`notes`, and the evidence found so far is
still returned: a partial search that says it is partial is useful; one that pretends to be
complete is a hazard. The refinement pass is additionally capped by
`MAX_REFINEMENT_EVALUATIONS`, independent of depth, so a wide range cannot explode the
budget.

### Monotonicity is the justification for bisection

`classify_monotonic` labels a sampled series `increasing`, `decreasing`, `non_monotonic` or
`insufficient`. `refine_boundary` bisects **only** for a monotonic axis; otherwise it
densifies the bracket. On a decreasing-risk axis the boundary is reported with
`last_safe > first_unsafe`; on an increasing axis the reverse. Every candidate carries its
method, monotonicity, evaluation count and uncertainty, so the evidence states *how* the
boundary was obtained, not just where it is.

### Evidence document

`SearchResult` returns: `counts` (scenarios, safe, near-limit, safeguard-activated,
violation, failing, observation-only, evaluations, cache hits, distinct cases, boundary
candidates), `failures` (rank-ordered, bounded by `MAX_REPORTED_FAILURES`), `boundaries`,
`sensitivity`, `trace` (bounded by `MAX_TRACE_ENTRIES`), `budget`, `config` (versions, spec,
limits, thresholds) and `notes`. Case keys are canonical strings (`name=value;…` sorted), so
the same case is the same simulation across runs.

### API and UI

`GET /searches/capabilities` publishes the allowlist, modes and effective budgets;
the UI renders its controls from it, so a variable cannot become searchable in the browser by
accident. `POST /searches/run` requires a verified session, loads the plant with
`get_owned_or_404` (cross-user → `404`), validates the whole plan before any compute and is
rate-limited on its own bucket. `/analysis/new` is a one-viewport workspace: plan editor on
one side, tabbed/paginated evidence viewer on the other, tabs instead of stacking on narrow
screens.

---

## 21. AI Provider (implemented, Part 8)

Nebius Token Factory is the provider: an OpenAI-compatible inference API. The client is a
thin, validated wrapper, and the only module in the codebase that knows an external AI
service exists.

```text
app/ai/provider.py   validate_base_url, ProviderConfig, ProviderError, NebiusProvider, build_provider
```

Required configuration — **backend only**; the frontend bundle contains no provider
reference at all:

| Variable | Meaning |
| --- | --- |
| `NEBIUS_API_KEY` | bearer token, held as `SecretStr`, unwrapped once and used only to build the `Authorization` header |
| `NEBIUS_BASE_URL` | endpoint root, e.g. `https://api.tokenfactory.nebius.com/v1` |
| `NEBIUS_MODEL` | the model id, resolved from the account catalogue (below) |

Rules the client enforces:

- **No hard-coded model id.** The account's own catalogue is the source of truth:
  `GET {NEBIUS_BASE_URL}/models` lists what this account can actually call, and `NEBIUS_MODEL`
  is set from that list. A model that is public in the docs but absent from the account fails
  as `auth`/`invalid_response` — never a silent substitution.
- **`https`, or nothing.** A public `http://` base URL is refused before any request is made,
  so a mistyped environment variable cannot send the key in clear text. Loopback `http` is
  allowed for a local gateway.
- **Errors become a vocabulary, not a stack trace:** `auth`, `rate_limit`, `timeout`,
  `connection`, `server`, `invalid_response`. Only the category and the latency are loggable.
- **Retries are bounded and transient-only:** a connection drop or a 5xx is retried at most
  `AI_PROVIDER_MAX_ATTEMPTS` times; an auth or validation failure never is.
- **The key never leaves the client** — not into a prompt, a response body, an error message or
  a log line.
- **Absence is a supported state.** With any of the three variables unset, `ai_configured` is
  `false`, the endpoint answers `not_configured` and no network call happens. Parts 1–7 keep
  working with no key at all.

---

## 22. Agent Loop (implemented, Part 8)

An explicit, bounded state machine — not a framework. LangGraph was considered and rejected:
this loop is small, the states are few, and a hand-written machine is easier to bound, test
and audit than a graph runtime.

```text
UNDERSTAND → IDENTIFY → CHOOSE → CALL_TOOL → OBSERVE → DECIDE → … → EXPLAIN → DONE
```

```text
app/ai/constants.py  AgentState, AgentStopReason, ProviderErrorCategory, GuardVerdict, ceilings
app/ai/schemas.py    AgentDecision, AgentExplanation, ToolResultRecord, InvestigationResult
app/ai/prompts.py    system / decision / explanation prompt builders (pure, sanitizing)
app/ai/parsing.py    find_json_object, parse_decision, parse_explanation, safe_excerpt
app/ai/tools.py      the nine allowlisted tools, ToolBudget, call_tool
app/ai/guards.py     InFlightGuard (duplicate-run protection)
app/ai/machine.py    InvestigationAgent.run — the state machine
app/ai/service.py    InvestigationService — provider + budget + tools + plant context
app/ai/deps.py       get_ai_service
```

The budget is checked at the top of every iteration, *before* it is spent. Every bound is hard
and clamped at startup to an engine ceiling: `AI_MAX_STEPS`, `AI_MAX_MODEL_CALLS`,
`AI_MAX_SIMULATIONS`, `AI_MAX_TOKENS`, `AI_TIMEOUT_SECONDS`. Model calls and simulations are
charged by the **tool layer**, so a model that keeps asking for the same expensive tool runs
out of budget instead of looping. Reaching a bound is a **reported stop reason** — `completed`,
`max_steps`, `max_model_calls`, `max_simulations`, `max_tokens`, `timeout`, `invalid_output`,
`duplicate`, `provider_error` — never a hang and never an unmarked truncation.

What the model may do: choose one action per iteration from a closed enum, mapped to exactly
one tool by `TOOL_FOR_ACTION`. What it may not do: anything else. `app/ai` contains no shell,
no `eval`/`exec`, no generated Python, no SQL, no file access, no permission change, and no
path to a secret or to real equipment. The tool layer re-validates every argument against its
own strict schema, so an invented variable, an out-of-range value or an extra field is
refused; two consecutive refusals stop the run, with the refusals preserved as evidence.

---

## 23. Prompt Injection (implemented, Part 8)

Engineering-change text, plant names and notes — anything the user or the plant supplies — is
untrusted **data**. It is something to reason about, never something to obey.

Defence in depth:

1. **Sanitize** — `sanitize_untrusted_text` drops control characters, collapses whitespace and
   truncates to a bounded length, so hostile text cannot reshape the prompt structure.
2. **Detect and record** — `detect_injection` matches named patterns ("ignore your
   instructions", "reveal your system prompt", "reveal the API key", "run a shell command",
   "bypass search limits", "act as …", "you are now …", "disregard the above"). A hit is
   recorded as evidence — never obeyed, never hidden — and the machine scans the goal itself
   rather than trusting a caller to have done it.
3. **Wrap** — `wrap_untrusted` delimits untrusted text with markers, and a forged closing marker
   inside the text is neutralised, so the text cannot pretend to be the framework.
4. **Constrain the output** — the decision schema is strict: action from a closed enum,
   variables from the allowlist, bounded arguments, `extra="forbid"`. Anything else is
   `invalid_output` and stops the run; there is no best-effort parse of a decision.
5. **Enforce independently** — the tool layer ignores what the prompt said. It checks
   authorization, ownership, the variable allowlist, argument ranges and the budget on its own.
   Even a fully persuaded model cannot exceed a bound, reach another user's plant or read a
   secret, because none of those is expressible as a tool call.

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

## 24a. Autonomous Analysis (implemented, Part 9)

One analysis is one bounded, autonomous run over an owned plant. Everything the UI shows is
**recorded reality**: each `AnalysisEvent` row is written by the code that actually did the
work (with the real elapsed time), and the stored `result` document is assembled only from
Part 4/5/7 outputs. Nothing is replayed from timers.

### Domain

- `app/analyses/constants.py` — `AnalysisKind` (auto / counterfactual / reverify),
  `AnalysisStatus` (running / complete / failed / **interrupted** — the honest state after a
  process restart), the 12 event kinds with their human labels, storage bounds
  (≤400 cases, ≤600 events, ≤25 failures per document) and the fixed verdict language
  ("No unsafe condition was detected within the tested simulation scenarios.").
- `app/analyses/events.py` — `EventRecorder`: monotonically numbered events, injected clock
  for tests, `elapsed_s` from the injected clock (never wall-clock guesses).
- `app/analyses/interpret.py` — deterministic goal interpretation (keyword→variable mapping)
  producing the *interpreted change* shown before/while a run starts. No AI involved.
- `app/analyses/runner.py` — the pipeline itself: understand → map → plan → run → observe →
  refine → find violations → counterfactuals (original / restore cooling / restore outlet /
  reduce feed) → safeguard check → optional AI summary → complete. Every stage emits a real
  event; the document stores bounded cases, failures, counterfactual rows, safeguard timings,
  versions and notes.
- `app/analyses/service.py` — transaction, duplicate guard (409 on a concurrent run for the
  same plant), failure marking, and the interrupted-run reconciliation.
- `app/analyses/pipeline.py` — pure builders: `failure_detail` (trajectories via a real
  re-simulation, configured limits, first violation, peaks, safeguard events, search
  context), `locate_failure` (exact key match only), `build_reverify_document` (per-failing-
  case before/after rows from real re-runs; verdict drawn only from the fixed strings).
- `app/analyses/summary.py` — the optional AI narration, stored **separately** from the
  simulation evidence; unconfigured provider ⇒ empty explanation + a stated note.
- `app/analyses/pdf.py` — dependency-free multi-page PDF writer; every text field escaped.

### API

`POST /analyses/run` (rate-limited per user, 409 on duplicates), `GET /analyses` (paginated,
page_size ≤ 50), `GET /analyses/{id}` / `/events?after_seq=` / `/result`,
`GET /analyses/{id}/failures/{failure_id}` (real re-simulation for the page),
`POST /analyses/{id}/reverify` (allowlisted mitigations with bounds, re-runs only the parent's
failing cases), `GET /analyses/{id}/report` and `GET /analyses/{id}/report.pdf`.

Every id is resolved through `get_owned_or_404`: another user's analysis, failure, scenario,
history item, report or reverification is a 404 (covered by the cross-user IDOR test).

### Frontend

`/analysis/new` (goal → interpreted change → FIND HIDDEN RISKS, duplicate-safe),
`/analysis/:id/live` (cursor-polled real events, event-step navigator),
`/analysis/:id/failures/:failureId`, `/analysis/:id/investigation` (SIMULATION EVIDENCE vs
AI EXPLANATION), `/analysis/:id/safeguards` (trigger/response/violation in the required
language), `/analysis/:id/reverify` (mitigation form → before/after), `/history` (paginated),
`/reports/:id` (Overview / Scenarios / Failures / Counterfactuals / Safeguards / Evidence tabs
+ PDF download). One-viewport holds on every interactive screen; the PDF is the multi-page
exception because it is an export, not a screen.

### Tests

`tests/test_analyses_pipeline.py` (16 unit tests: recorder clocking, interpretation,
document builders, PDF escaping/structure, verdict language) and `tests/test_analyses_api.py`
(15 endpoint tests: full workflow with the real simulator, no-failure language, events cursor,
409 duplicate, rate limit per user, sanitization, mitigation bounds, IDOR across every object,
history scoping). Backend total: **326 passing**.

---

## 25. Testing

Frontend unit tests (Part 6) cover the pure modules under the Node test runner
(`frontend/tests/*.test.ts`, run with `npm run test:unit`, **87 tests**): viewport
classification (desktop, short laptop, tablet, mobile, degenerate sizes), graph-orientation
choice (including that a rotated line really does render larger than the squashed one),
dashboard view-state derivation (loading/offline/session-expired/error/empty/ready and
tone/motion outputs), API failure classification, the motion plan (including
reduced-motion → fully static), the telemetry stream state machine, (Part 7) the search
planning mirror — allowlist mirror, per-mode axis counts, preset filtering by server
capabilities, request building, optional-budget forwarding, every rejection the UI must
explain, NaN-free parsing, failure filtering and clamped pagination — and (visual
transformation) the recorded-sequence ordering, the agent stage rail derived from recorded
events, the route-transition plan, the auth session cache and the safeguards time axis.

Backend tests (`Backend/tests`, 288 passing) cover the Part 7 engine
(`test_search.py`: deterministic linspaces, safe-end-first traversal, bisection only when
monotonic, densify otherwise, repeatability, combination caps, the scenario budget, the
injectable-clock timeout, no value echo) and the API (`test_search_api.py`: capabilities, a
seeded unsafe region discovered by a sweep, refined boundary, reproducibility, sensitivity,
bounded combinations, auth, cross-user `404`, invalid and malicious values, oversized-search
rejection, and the `429` bucket) — plus Part 8:

```text
test_ai_security.py        sanitizer, injection patterns, marker forgery, redaction, log allowlist
test_ai_parsing.py         balanced-JSON extraction, malformed output, curated reasons
test_ai_provider.py        config/URL validation, error mapping, one bounded retry, no key leaked
test_ai_tools.py           per-tool arg schemas, refusals, budget charging, payload ceiling
test_ai_agent.py           loop bounds, stop reasons, refusals as evidence, goal injection
test_investigations_api.py capabilities, run, not-configured, 409 duplicate, cross-user 404
```

`Backend/tests/ai_fakes.py` holds the shared fakes — notably `ScriptedProvider`, which records
every model call, prompt and system prompt. The provider is the **only** thing faked: the
simulator, safety engine and search engine running behind the tools are the real
deterministic ones, and no test needs a network or a key.

Layout is checked beyond the unit tests by driving the running app in a browser and
measuring the real DOM at each brief target size: document and `main` scroll heights (must
be zero), horizontal overflow, every graph node's rect against its canvas, and the applied
graph transform. That is geometry, not a rendered-image diff — no screenshot or visual-
regression pass is claimed.

Unit:
auth utilities, simulator equations, safety, safeguards, scenario validation, boundary search, provider parsing.

Integration:
auth/session, plant ownership, simulation→safety, search→simulation, telemetry auth, agent tools, provider, investigation run (Part 8).

Security:
cross-user access, malformed input, compute abuse, rate limits, XSS content, invalid auth, prompt injection, malformed AI output, forged wrapper markers, oversized AI tool payloads, duplicate AI runs.

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
7 Scenario search (deterministic, no AI)
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
