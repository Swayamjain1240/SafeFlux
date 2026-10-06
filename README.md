# SafeFlux

**Autonomous Process-Safety Failure Hunter** — Nebius × NVIDIA Global AI Hackathon, *Best Apps & Agents*.

> **AI searches for danger → Simulator proves it → Engineer decides.**

SafeFlux lets a process-safety engineer describe a proposed engineering change, autonomously
searches a digital process simulation for hidden unsafe conditions, verifies findings
deterministically, and presents evidence for human review.

It is a simulation and decision-support prototype. **It never controls real industrial
equipment** — no PLC/DCS actuation, no real valve or pump control, ever.

---

## Status

Build **Part 7 of 10 — deterministic scenario search** is complete.

| Area | State |
| --- | --- |
| FastAPI bootstrap, `/api/v1`, health endpoint | ✅ |
| Environment validation + secret-safe config | ✅ |
| Error envelopes, security headers, strict CORS, rate limiting | ✅ |
| React/Vite/TS/Tailwind app shell + public/protected routing | ✅ |
| One-viewport workspace layout + loading/error foundations | ✅ |
| Signup / login / logout / session (Argon2id + HttpOnly cookie) | ✅ |
| `get_current_user()`, protected APIs, ownership foundation | ✅ |
| Auth rate limiting + request body-size guard | ✅ |
| Plant domain models + owned plant CRUD APIs | ✅ |
| Viewport-safe 5-step plant wizard + React Flow topology preview | ✅ |
| Deterministic simulator (NumPy/SciPy) + fault injection | ✅ |
| Authenticated `POST /api/v1/simulations/run` with compute budgets | ✅ |
| Deterministic safety engine (SAFE/NEAR_LIMIT/SAFEGUARD_ACTIVATED/VIOLATION) | ✅ |
| Safeguard timing (trigger / response / violation, prevented vs too late) | ✅ |
| Live simulated telemetry: current / bounded history / SSE stream | ✅ |
| One-viewport live monitor (telemetry cards + chart tabs) | ✅ |
| Engineering dashboard on live plant + telemetry data | ✅ |
| Animated React Flow process graph (GSAP, reduced-motion aware) | ✅ |
| Central session-expiry handling + one-viewport authenticated pages | ✅ |
| Deterministic scenario search: sweep, bounded refinement, sensitivity, combinations | ✅ |
| Allowlisted search variables + strict Pydantic schemas + hard budgets | ✅ |
| `GET /api/v1/searches/capabilities` + `POST /api/v1/searches/run` (owner-scoped, rate-limited) | ✅ |
| One-viewport search workspace (`/analysis/new`) with paginated, filtered evidence | ✅ |
| Backend test suite (pytest) | ✅ 184 passing |
| Frontend unit tests (node) | ✅ 65 passing |
| Nebius + NVIDIA Nemotron investigation agent | ⏳ Part 8 |
| Investigation UX / hardening | ⏳ Parts 9–10 |

---

## Repository layout

```text
SafeFlux/
├── frontend/          React + Vite + TypeScript + Tailwind
├── Backend/           FastAPI + Pydantic service
├── docs/              source-of-truth project docs
│   ├── SAFEFLUX_MASTER.md   what / why / non-negotiable rules
│   ├── ARCHITECTURE.md      how the system is built
│   └── SESSION_LOG.md       what is done / current / next
├── .gitignore
├── README.md
└── LICENSE
```

## Prerequisites

- Python 3.12+
- Node.js 20+ (npm 10+)

## Backend setup

```bash
cd Backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # Windows: copy .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(64))"   # → JWT_SECRET

uvicorn app.main:app --reload --port 8000
```

Health check: <http://localhost:8000/api/v1/health>

> The backend fails fast at startup and prints **variable names only** (never values)
> if required environment variables are missing or invalid.

## Frontend setup

```bash
cd frontend
npm install
cp .env.example .env               # Windows: copy .env.example .env
npm run dev                        # http://localhost:5173
```

## Tests & checks

```bash
# Backend (from Backend/)
python -m pytest -q -p no:warnings # 184 tests

# Frontend (from frontend/)
npm run lint                       # oxlint, 0 warnings
npm run test:unit                  # node --test, 65 tests
npm run build                      # tsc --strict + vite production build
```

## Environment variables

### Backend (`Backend/.env.example`)

| Variable | Required | Purpose |
| --- | --- | --- |
| `ENVIRONMENT` | yes | `development` \| `staging` \| `production` |
| `DEBUG` | no (false) | log verbosity only; forced off in production |
| `DATABASE_URL` | yes | `sqlite:///...` (MVP) or `postgresql://...` |
| `JWT_SECRET` | yes | ≥16 chars dev, ≥32 chars production |
| `FRONTEND_URL` | yes | strict CORS allowlist (comma-separated origins) |
| `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` | no | baseline API rate limit |
| `SESSION_TTL_MINUTES` | no (1440) | session cookie / JWT lifetime (5..43200) |
| `AUTH_RATE_LIMIT_ATTEMPTS` / `AUTH_RATE_LIMIT_WINDOW_SECONDS` | no | tighter signup/login rate limit |
| `MAX_REQUEST_BODY_BYTES` | no (65536) | reject oversized request bodies (≥1024) |
| `SIM_MAX_DURATION_S` / `SIM_MIN_TIME_STEP_S` / `SIM_MAX_SAMPLES` | no | hard simulation compute budgets |
| `SIM_RATE_LIMIT_RUNS` / `SIM_RATE_LIMIT_WINDOW_SECONDS` | no | simulation per-IP rate limit |
| `SAFETY_NEAR_LIMIT_FRACTION` | no (0.9) | near-limit band / alarm setpoint as a fraction of each limit |
| `SEARCH_MAX_SCENARIOS` / `SEARCH_MAX_COMBINATIONS` | no (150 / 36) | hard ceilings for one search |
| `SEARCH_MAX_REFINEMENT_DEPTH` / `SEARCH_TIMEOUT_SECONDS` | no (6 / 90) | boundary-refinement levels / overall search timeout |
| `SEARCH_RATE_LIMIT_RUNS` / `SEARCH_RATE_LIMIT_WINDOW_SECONDS` | no | search per-IP rate limit (tightest bucket in the API) |
| `TELEMETRY_MAX_HISTORY` / `TELEMETRY_MAX_PLANTS` | no | retained frames per plant / plants per process |
| `TELEMETRY_MAX_STREAMS[_PER_PLANT|_PER_USER]` | no | concurrent SSE stream limits |
| `TELEMETRY_REPLAY_INTERVAL_MS` / `TELEMETRY_HISTORY_DEFAULT_LIMIT` | no | stream pacing / default history size |
| `NEBIUS_API_KEY` / `NEBIUS_BASE_URL` / `NEBIUS_MODEL` | Part 8 | AI provider — **backend only** |

### Frontend (`frontend/.env.example`)

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | backend API base URL (public by design) |

**Never commit a real `.env`.** Only `.env.example` files are tracked.

## API conventions

Success:

```json
{ "success": true, "data": {} }
```

Error:

```json
{ "success": false, "error": { "code": "NOT_FOUND", "message": "The requested resource was not found." } }
```

Stack traces, SQL, file paths, secrets and provider details are never returned.

## Authentication (Part 2)

All endpoints live under `/api/v1/auth/*` (the API prefix was fixed at `/api/v1` in Part 1):

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/v1/auth/signup` | — | create account, start session |
| `POST` | `/api/v1/auth/login` | — | sign in, start session |
| `POST` | `/api/v1/auth/logout` | — | clear session cookie (idempotent) |
| `GET` | `/api/v1/auth/me` | ✅ | current user |
| `GET` | `/api/v1/auth/session` | ✅ | alias of `/me` (frontend session probe) |

- Passwords hashed with **Argon2id**; plaintext is never stored, logged or returned.
- The session token lives **only** in an `HttpOnly` cookie (`safeflux_session`) — never in
  JavaScript, `localStorage`, or response bodies. `Secure` in production, `SameSite=Lax`.
- `get_current_user()` resolves identity solely from the verified cookie; no endpoint ever
  trusts a client-supplied user id.
- Unknown-email logins still burn Argon2 CPU time, and duplicate emails return `409`, so
  account enumeration is discouraged without leaking whether an account exists.
- Ownership helpers (`get_owned_or_404`, `ensure_owner`) return **404** for cross-user
  access so object existence is never leaked; every owned model carries an `owner_id` FK.

## Plant configuration (Part 3)

All endpoints live under `/api/v1/plants/*` and require an authenticated session:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/plants` | create a plant + configuration (`201`) |
| `GET` | `/api/v1/plants` | list the caller's plants |
| `GET` | `/api/v1/plants/{id}` | full plant detail |
| `PATCH` | `/api/v1/plants/{id}` | partial update |
| `DELETE` | `/api/v1/plants/{id}` | delete the plant + children (`204`) |
| `GET` | `/api/v1/plants/{id}/state` | dynamic initial process state |

A plant is modelled by five records: identity/ownership (`Plant`), static `PlantConfig`,
initial `PlantState`, `SafetyLimits` and `SafeguardConfig`. Ownership is the session user
only — the id is never accepted from the client — and cross-user access returns **404** so
existence is never leaked. All numeric fields are re-validated server-side against
conservative engineering bounds, and the initial state must sit below the configured trip
limits (enforced on create **and** re-checked on every `PATCH`).

The setup UI is a **5-step, one-viewport wizard** (identity → conditions → equipment →
safety → review) with an optional **React Flow** topology preview
(`Feed Tank → Pump P-101 → Heated Reactor R-101 → Outlet Valve V-101 → Product Tank`).
The preview is static: SafeFlux configures a simulation model and never controls real
plant equipment.

## Deterministic simulator (Part 4)

One endpoint, authenticated and owner-scoped:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/simulations/run` | run one deterministic scenario against the caller's plant |

The simulator evolves a **lumped, well-mixed** model of the locked process. Identical
inputs always produce identical outputs — there is **no RNG and no LLM** in the physics.

**Input:** the plant's `PlantConfig` + initial `PlantState`, plus a scenario (duration,
time step, deterministic faults, sensor faults).

**Output (`SimulationResult`):** time-series state, per-variable extrema, events, summary
metrics and version metadata.

**Model (units in the code):** mass balance on reactor volume; gravity-driven outlet
`outlet = K · valve_fraction · √(level)`; heater power and jacket cooling
`cooling = UA · max(T − T_coolant, 0)`; energy balance with feed advection; and a
documented **pressure proxy** (atmospheric + temperature + static head) that is *not* a
real vapour-pressure calculation. Overflow/dry-out clamp the level.

**Deterministic faults:** cooling degradation, complete cooling loss, outlet restriction,
valve stuck, feed-flow increase, pump variation — plus **sensor faults** (bias/freeze)
that change *observed* readings only, so `true_temperature_c` and
`observed_temperature_c` stay separable, and **delayed shutdown** when an armed trip is
crossed.

**Abuse protection:** hard budgets enforced server-side before any integration —
`SIM_MAX_DURATION_S`, `SIM_MIN_TIME_STEP_S`, `SIM_MAX_SAMPLES` — plus a dedicated per-IP
rate-limit bucket (`SIM_RATE_LIMIT_RUNS`) and the existing request body-size guard.

The model is a simplified decision-support prototype for *simulated* behaviour. It is
**not** certified industrial safety software and never drives real equipment.

## Safety engine (Part 5)

Every `POST /api/v1/simulations/run` now also returns a deterministic `safety` verdict.
The engine is pure numeric software — **no LLM decides a safety status**.

Statuses: **SAFE**, **NEAR_LIMIT**, **SAFEGUARD_ACTIVATED**, **VIOLATION**. Each monitored
variable (temperature, pressure, level) produces a `SafetyFinding` recording its type,
timestamp, measured value, configured limit, near-limit band and scenario id. The
near-limit band is configurable (`SAFETY_NEAR_LIMIT_FRACTION`, default 0.9, or per request).

**Safeguard timing** records, for each high alarm and the emergency shutdown, the
**trigger**, **response** and **violation** times and whether the modelled response
*prevented* the violation in the tested simulation or was *too late*. To make that verdict
meaningful, the shutdown is assessed with its trip driven by the high-alarm setpoint
(near-limit) so a short delay can prevent a violation while a long delay still reports
too late. Verdicts are **simulation-only** and never a claim about a real plant
(see [docs/SAFEFLUX_MASTER.md](docs/SAFEFLUX_MASTER.md) §24).

## Live telemetry (Part 5)

Architecture: `Simulator → TelemetryService → CurrentStateStore → SSE/API → Frontend`.
**No LLM is called per telemetry tick.**

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/plants/{id}/telemetry/current` | latest telemetry frame |
| `GET` | `/api/v1/plants/{id}/telemetry/history?limit=` | recent bounded history |
| `GET` | `/api/v1/plants/{id}/telemetry/stream` | SSE replay of the stored frames |

Every route requires a session and resolves the plant with `get_owned_or_404` (cross-user →
**404**). History is bounded server-side per plant and per query, and each SSE stream is
gated by hard connection limits (total / per plant / per user) before it opens. True process
values and observed sensor values remain separate in every frame.

The monitor page (`/monitor`) is a **one-viewport** workspace: process graph, telemetry
cards and a **Recharts** chart with Temperature / Pressure / Level / Flow tabs, plus the
deterministic safety verdict from the last run. It hydrates recent history, streams new
frames over SSE, and reconnects with capped backoff; on mobile it shows one visualization
at a time.

## Engineering interface (Part 6)

Three authenticated pages — `/dashboard`, `/plant`, `/monitor` — read **real backend data
only** (no fixtures): owned plants, plant detail, the current telemetry frame, the health
probe and the safety verdict returned by `POST /api/v1/simulations/run`.

### Dashboard (`/dashboard`)

Plant selector, safety state, live API/telemetry badges, seven operating metrics
(**temperature, pressure, feed flow, level, cooling, valve, pump**), the recent **findings**
from the last deterministic verdict, and an **analysis status** strip. A single pure module
(`src/dashboard/viewState.ts`) maps the inputs to one of
`loading | empty | offline | session-expired | error | ready`, so every panel renders from
one source of truth. Live metrics fall back to configured values (clearly labelled
`configured`) only when no telemetry frame exists — the page never invents numbers.

### Process graph

`React Flow` diagram of the locked process — `Feed Tank → Pump P-101 → Reactor R-101 →
Valve V-101 → Product Tank`, with **Heater**, **Cooling Jacket** and **Sensors** attached to
the reactor. Units are tone-coded from configured limits and live telemetry.

The diagram adapts to the box it is given: it stays horizontal while the whole line still
fits at a legible scale, and rotates to a vertical spine (`src/layout/graphLayout.ts`, pure
and unit-tested) when a narrow container would otherwise shrink every label past reading.
It re-fits on resize, so no unit is ever clipped out of the canvas.

### Motion (GSAP)

Animation communicates state only: pipeline flow, pump rotation, warnings and
critical transitions. A pure planner (`src/animation/motion.ts`) turns the plant/safety
state into a motion plan, and `useProcessMotion` applies it inside a `gsap.context()` that is
reverted on unmount (no leaked timelines). `prefers-reduced-motion` disables all motion, and
effects prefer `transform`/`opacity`.

### Strict one-viewport rule

Every authenticated page fits inside `100dvh` — the shell pins itself to the viewport and
the content region never scrolls as a page. `src/layout/viewport.ts` classifies the window
by **width and height** (`mobile` / `tablet` / `laptop` / `desktop`); wide layouts show all
panels side by side, while narrow or short viewports switch to **tabbed panels** so no
button, card or piece of information is clipped or hidden. The plant page keeps only its
fact grid and plant list as bounded internal scroll regions.

### Session expiry

Any `401` from a protected call emits one central `safeflux:session-expired` event
(`src/api/sessionEvents.ts`); the auth provider drops the cached session so the route guard
redirects to `/login`, and the cached assessment is cleared so a previous verdict never
leaks into the next session. Login/session/logout probes are excluded to avoid redirect
loops.

## Deterministic scenario search (Part 7)

SafeFlux finds dangerous conditions by itself — the engineer never types a list of values
such as 100, 110, 120, 130. Pipeline, in this order and with nothing else in it:

**Search → Simulator → Safety engine → Evidence**

- **Search** picks the values. Deterministic, allowlisted and bounded: no AI, no
  `eval`/`exec`, no generated code, no shell.
- **Simulator** produces the trajectories (the Part 4 model).
- **Safety engine** produces the verdicts (the Part 5 thresholds).
- **Evidence** is the returned document: counts, failure scenarios, boundary candidates, the
  search trace and the configuration/version block.

### Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/searches/capabilities` | allowlisted variables, modes and effective budgets |
| `POST` | `/api/v1/searches/run` | run one bounded search over the caller's plant |

### Methods

| Mode | What it does |
| --- | --- |
| `sweep` | coarse sweep of one variable across its allowlisted range, then a bounded refinement of the first safe/unsafe boundary |
| `sensitivity` | perturbs every allowlisted variable one at a time and ranks its influence |
| `combinations` | bounded two-variable grid |

Refinement is **bisection only when the sampled status is monotonic** along the axis
(decreasing or increasing). When it is not, the bracket is **densified** instead — bisection
on a non-monotonic series converges on the wrong point. Every boundary candidate carries the
method that produced it, its monotonicity class, its uncertainty and its evaluation count.

A real run on the baseline reactor (nine coarse cooling points, then refinement) returns:
`cooling_factor` 1.0 … 0.125 → **safe**, 0.0 → **violation** (peak 162.5 °C against a
150 °C limit), boundary *last safe 0.0957, first unsafe 0.0938, bisection, ±0.0020* — an
edge the engineer could not have found by hand in nine tries.

### Allowlisted variables

`cooling_factor`, `feed_factor`, `outlet_factor`, `valve_target_pct`, `pump_factor`,
`shutdown_delay_s`, `temperature_sensor_bias_c`. A variable name only selects one row of a
fixed table that maps it to a typed simulator fault (or a safeguard delay, or a sensor
fault); anything else fails schema validation, so no client-supplied name can ever reach the
simulator. Sensor variables are marked **observation-only** in the result: they change what
the plant *reports*, never the true trajectory.

### Budgets

Hard, and enforced before compute: max scenarios, max combinations, max refinement depth,
max simulation duration, min time step, max sample count and an overall wall-clock timeout.
A request may only **tighten** a budget — asking for more than the operator configured is a
**422 rejection, never a silent clamp**, because a search that quietly covers less than it
claims is worse than no search. A search that hits a limit returns a result marked
`truncated` with the reason recorded in `budget` and `notes`.

### Reproducibility

Identical requests return identical evidence (counts, cases, failures, boundaries, trace),
apart from the measured elapsed time. Case keys are canonical strings, so the same case is
the same simulation. Every result carries the search engine, method, simulator model and
safety engine versions and states `deterministic: true, ai_involved: false`.

### UI (`/analysis/new`)

One viewport, two panes: a plan editor (plant, preset, method tabs, variable + resolution,
advanced budgets) and a tabbed, paginated result viewer (summary counts, failures with
status/variable/text filters, boundaries, influence ranking, trace). Presets are **starting
plans, never verdicts** — a preset that finds nothing is an honest result. On tablet/mobile
the panes switch via tabs instead of stacking, so nothing is clipped or endlessly scrolled.

## Security baseline

### Part 1


- Fail-fast environment validation; secrets wrapped in `SecretStr`
- Strict CORS allowlist with credentials — never `*`
- Security headers on every response (nosniff, DENY framing, CSP `frame-ancestors 'none'`,
  `Referrer-Policy`, Permissions-Policy; HSTS only in production over HTTPS)
- Production debug off; `/docs` and `/openapi.json` disabled in production
- In-memory fixed-window rate limiting (health probe exempt)
- Safe exception handling: 500s log internally, clients get a generic envelope
- Frontend fails closed: no session → protected routes stay locked
- No `dangerouslySetInnerHTML`; React-escaped rendering only

### Part 2

- Argon2id password hashing (OWASP-aligned library defaults)
- HttpOnly session cookie; token never exposed to JavaScript
- Per-IP rate limits on `/auth/signup` and `/auth/login` (separate buckets)
- Request body-size guard → `413 PAYLOAD_TOO_LARGE` before parsing
- Pydantic `extra="forbid"` schemas; validation errors never echo submitted values
- Responses expose only `{id, fullName, email}` — never the password hash
- Generic `401` messages; timing equalization on unknown accounts

### Part 3

- Every plant route requires a verified session; `owner_id` is server-assigned only
- `get_owned_or_404` → **404** on missing *and* cross-user resources (no existence leak)
- Server-side range validation on all configuration/state/limit fields; `extra="forbid"`
- Initial state must be ≤ trip limits on create, and the same invariant is re-checked (with
  rollback + `422`) after every `PATCH`
- Plant detail/list responses never expose `owner_id`
- Setup is a simulation design input — no code path actuates real equipment

### Part 4

- `POST /api/v1/simulations/run` requires a verified session and loads the plant with
  `get_owned_or_404` — another user's plant returns **404** (IDOR-safe)
- Hard compute budgets (max duration, min time step, max sample count) reject abusive
  requests **before** integration; no request can create unbounded steps
- Dedicated per-IP rate-limit bucket for the expensive simulation endpoint
- Strict `extra="forbid"` scenario schemas with bounded fault counts
- Deterministic physics only — no RNG, no LLM in the numeric path; sensor faults affect
  observed readings, never the true state

### Part 6

- No secrets or keys in the frontend (rule 1) — only the public `VITE_API_BASE_URL`
- The dashboard reads only real, owner-scoped endpoints; failed/expired/offline states are
  surfaced explicitly instead of rendering stale or invented data
- Session expiry is handled centrally from backend `401`s; the frontend still never trusts
  client-side state for authorization
- All rendering is React-escaped text — no `dangerouslySetInnerHTML`; chart data is numeric
- Two dependencies added (`recharts`, `gsap`), both used; `npm audit --omit=dev` → 0
  vulnerabilities

### Part 7

- The search never uses `eval()`, `exec()`, generated Python or shell commands — a variable
  name can only select an entry from the fixed allowlist
- `POST /api/v1/searches/run` requires a verified session and loads the plant with
  `get_owned_or_404`; another user's plant returns **404**
- Oversized searches are rejected (`422`) **before** any simulation runs, and per-request
  budgets may only tighten the configured ceilings
- The search endpoint has the tightest per-IP rate-limit bucket in the API, because one
  request runs many simulations
- Validation errors never echo submitted values, and unknown field names are no longer
  reflected either — they are reported against the body instead
- No AI anywhere in this part: no provider is contacted and no API key is required

### Part 5

- Safety statuses are computed by deterministic software; the LLM never determines
  threshold truth
- Telemetry current/history/stream routes are authenticated **and** owner-scoped; a
  cross-user plant returns **404** rather than leaking existence
- SSE connections are hard-limited (total / per plant / per user) and the slot is always
  released on completion or client disconnect
- Query and history limits are bounded server-side; frames expose only simulated values,
  limits and status — never owner ids or internals
- Streams replay deterministic simulator output only; nothing is routed through the LLM
  per tick, and SafeFlux still exposes no actuation path

## Documentation

- [docs/SAFEFLUX_MASTER.md](docs/SAFEFLUX_MASTER.md) — product rules and scope
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design
- [docs/SESSION_LOG.md](docs/SESSION_LOG.md) — progress checkpoints

## License

MIT — see [LICENSE](LICENSE).
