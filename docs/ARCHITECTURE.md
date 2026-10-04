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

---

## 6. Animation Architecture

GSAP is used only for meaningful state transitions:

- process flow,
- status transitions,
- agent loop,
- failure chains.

Clean up timelines, prefer transform/opacity, respect reduced motion, avoid decorative infinite animation.

Three.js is optional.

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
Endpoint-specific budgets for AI/simulation/search arrive with their features.

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

Input:

PlantConfig + initial state + scenario + duration + timestep.

Output:

time-series + extrema + events + version metadata.

Model:

- material balance,
- feed/outlet,
- heating/cooling,
- temperature,
- simplified pressure,
- equipment effects,
- fault injection.

Use NumPy/SciPy. Document simplifications. No random core telemetry.

---

## 18. Safety Engine

Statuses:

SAFE, NEAR_LIMIT, SAFEGUARD_ACTIVATED, VIOLATION.

A SafetyFinding records type, timestamp, measured value, configured limit, scenario and status.

Safeguards track trigger, response and violation timing.

AI never determines numeric threshold truth.

---

## 19. Telemetry

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

Prefer SSE unless WebSocket is genuinely required.

No LLM per tick. Bound history, secure streams, clean connections.

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
