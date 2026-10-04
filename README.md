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

Build **Part 4 of 10 — deterministic process simulator** is complete.

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
| Backend test suite (pytest) | ✅ 111 passing |
| Safety engine / dashboard / search / AI agent | ⏳ Parts 5–8 |
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
python -m pytest                   # 54 tests

# Frontend (from frontend/)
npm run lint                       # oxlint, 0 warnings
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

## Documentation

- [docs/SAFEFLUX_MASTER.md](docs/SAFEFLUX_MASTER.md) — product rules and scope
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design
- [docs/SESSION_LOG.md](docs/SESSION_LOG.md) — progress checkpoints

## License

MIT — see [LICENSE](LICENSE).
