# SafeFlux — Session Log

**Rule:** Keep newest checkpoint at the top. Record real decisions and do not rewrite history merely to make the project appear cleaner.

---

# Current Checkpoint — 2026-10-04 · PART 3 COMPLETE

**Status:** 🟢 Part 3 (Plant Setup + Configuration) implemented and tested  
**Project:** SafeFlux — Autonomous Process-Safety Failure Hunter  
**Track:** Best Apps & Agents

## What is complete (Part 3)

### Backend

- **Plant domain models** (`app/models/plant.py`): five tables modelling one plant —
  `Plant` (UUID PK, `owner_id` FK→`users.id`, indexed, identity + timestamps),
  `PlantConfig` (static engineered configuration: feed flow, cooling, valve, heater,
  shutdown delay), `PlantState` (dynamic initial condition incl. `pump_running`),
  `SafetyLimits` (trip limits), `SafeguardConfig` (armed safeguards + trip delay).
  Child rows are one-to-one (`unique` `plant_id`, `ON DELETE CASCADE`) and cascade with
  the plant; `pump_running` lives on `PlantState` because it is equipment state, not config.
- **Schemas** (`app/schemas/plant.py`): `extra="forbid"`; conservative engineering bounds
  (feed 0–500 L/min, cooling/valve/heater 0–100 %, delays 0–3600 s, T −50–1000 °C,
  P 0–500 bar, level 0–100 %); `PlantCreate` enforces initial state ≤ trip limits;
  `PlantUpdate` is all-optional with nested blocks replaced wholesale; out-models never
  expose `owner_id`.
- **Endpoints** (`app/api/routes/plants.py`, prefix `/api/v1/plants`): `POST` (201),
  `GET` list, `GET/{id}`, `PATCH/{id}`, `DELETE/{id}` (204), `GET/{id}/state`. Every route
  requires `get_current_user`; owner is always the session user; reads/writes go through
  `get_owned_or_404` (404 for missing **and** cross-user). A post-PATCH consistency guard
  re-checks state ≤ limits and rolls back with a `422 VALIDATION_ERROR` otherwise.
- **Router** (`app/api/router.py`): plants router mounted.

### Frontend

- **API client** (`src/api/client.ts`): added `apiPatch` and `apiDelete` (204-safe).
- **Plants API + hooks** (`src/api/plants.ts`, `src/hooks/usePlants.ts`): CRUD via React Query
  with cache invalidation (`plantKeys`).
- **Types** (`src/types/plant.ts`): mirrors the backend schemas + MVP defaults.
- **Wizard validation** (`src/utils/plantValidation.ts`): per-step client rules incl. the
  state-below-limits consistency check; draft→payload conversion.
- **5-step viewport-safe wizard** (`src/components/plant/PlantWizard.tsx`): identity →
  conditions → equipment → safety → review; each step fits one viewport, Back/Next visible.
- **Process topology preview** (`src/components/plant/ProcessTopology.tsx`, React Flow
  `@xyflow/react`): Feed Tank → Pump P-101 → Heated Reactor R-101 → Outlet Valve V-101 →
  Product Tank. Purely static — no fake live movement, no control implication.
- **Plant page** (`src/pages/PlantSetupPage.tsx`): list / detail / wizard, delete with confirm;
  `/plant` route now wired (replaces the Part 3 `ComingSoon`).

### Docs

- `README.md` (status, Part 3 section, security baseline), `ARCHITECTURE.md` §10/§15/§16,
  this checkpoint.

## Tests run

- Backend: `python -m pytest` → **79 passed** (28 Part 1 + 26 Part 2 + 25 Part 3). Part 3
  covers create-with-full-config, auth required, list-is-own-only, detail + state, missing →
  404, invalid-range parametrization, initial-state-above-limit rejection, unknown-field
  rejection, state-not-persisted-on-rejected-update, and IDOR read/list/state/update/delete.
- Frontend: `npm run lint` → 0 warnings/errors; `npm run build` green (tsc strict).
- Browser: full 5-step wizard driven end-to-end (created a plant, values persisted),
  React Flow preview rendered in review **and** detail; verified at 1440×900, 834×1112 and
  390×844 with **0 document overflow** and every step fitting the content region.
- API: login → `GET /plants` and `GET /plants/{id}/state` returned the wizard-created plant
  with matching values (feed 120 L/min, 30 °C · 2.5 bar · 40 %).

## Security audit (Part 3 · rules 1–25)

- **Secrets:** none introduced; DB is env-based and `*.db` stays gitignored; no new keys.
- **Authorization:** all plant routes authenticated; `owner_id` never accepted from the
  client; `get_owned_or_404` returns 404 for cross-user access (no existence leak).
- **Input/XSS:** Pydantic `extra="forbid"` + range bounds re-validated server-side; the
  create validator and the PATCH consistency guard block states above trip limits; errors
  never echo submitted values; frontend renders via React-escaped children only.
- **Simulation-only:** plant setup is a *design input* to a simulation model — no path to
  real equipment control; the topology preview is explicitly static.
- **Dependencies:** 1 new frontend dep (`@xyflow/react@12.12.0`), used; build/lint clean.
- **API path decision:** brief's `/api/plants/*` implemented as `/api/v1/plants/*`
  (single canonical prefix from Part 1) — recorded in ARCHITECTURE §16.

## Next action

Part 4 — Simulator: deterministic process simulation consuming `PlantConfig` + initial
`PlantState` + scenario + duration/timestep, producing time-series telemetry.

---

# Checkpoint — 2026-10-04 · PART 2 COMPLETE

**Status:** 🟢 Part 2 (Authentication + Authorization) implemented and tested  
**Project:** SafeFlux — Autonomous Process-Safety Failure Hunter  
**Track:** Best Apps & Agents

## What is complete (Part 2)

### Backend

- **Database layer** (`app/database/__init__.py`): SQLAlchemy 2.x engine/session factory,
  declarative `Base`, `init_db()` (tables created on startup), `get_db()` request session.
- **User model** (`app/models/user.py`): UUID string PK (non-enumerable), unique+indexed
  lower-cased email, Argon2id `password_hash`, `is_active`, timestamps; `__repr__` excludes
  the hash.
- **Auth core** (`app/auth/`): `passwords.py` (Argon2id hash/verify + `burn_verify_time`
  timing equalization), `tokens.py` (HS256 JWT, `iss`/`typ`/`sub` claims, rejects expired/
  tampered/wrong-issuer), `session.py` (HttpOnly cookie set/clear), `dependencies.py`
  (`get_current_user`), `ownership.py` (`get_owned_or_404`, `ensure_owner`).
- **Endpoints** (`app/api/routes/auth.py`): `POST /api/v1/auth/signup|login|logout`,
  `GET /api/v1/auth/me`, hidden alias `GET /api/v1/auth/session`.
- **Schemas** (`app/schemas/auth.py`): `extra="forbid"`, `EmailStr`, name 2–120,
  password 8–128, responses expose only `{id, fullName, email}`.
- **Rate limiting** (`app/core/rate_limit.py`): extracted `FixedWindowLimiter`; per-app
  `auth_rate_limit(request, bucket)` for signup/login (separate buckets, `429` +
  `Retry-After`).
- **Body-size guard** (`app/core/body_limit.py`): `413 PAYLOAD_TOO_LARGE` before parsing.
- **Config** (`app/core/config.py`): `SESSION_TTL_MINUTES`, `AUTH_RATE_LIMIT_ATTEMPTS`,
  `AUTH_RATE_LIMIT_WINDOW_SECONDS`, `MAX_REQUEST_BODY_BYTES`, all validated.
- **Middleware stack** (`app/main.py`): lifespan calls `init_db()`; `app.state.auth_limiters`.

### Frontend

- Login/Signup placeholder copy replaced with real behavior notes; `ErrorPanel` now
  surfaces backend `details[]` field errors (React-escaped).
- `AuthProvider` queries `/auth/session`; `ProtectedRoute` fails closed.

### Docs

- `README.md` (auth section, 54 tests, new env vars), `ARCHITECTURE.md` §9/§10/§13,
  `Backend/.env.example` updated; this checkpoint added.

## Tests run

- Backend: `python -m pytest` → **54 passed** (28 Part 1 + 26 Part 2). Part 2 covers signup,
  hardened cookie flags, duplicate/weak/invalid/unknown-field validation, Argon2 storage,
  hash never exposed, login success/failure, unknown-email indistinguishability, `/me` +
  `/session`, expired/tampered/malformed/unknown-user tokens, logout, protected-endpoint
  gating, login rate limit (`429` + `Retry-After`), ownership 404 semantics, oversized body.
- Frontend: `npm run lint` → 0 warnings/errors; `npm run build` green.
- Browser: login and both signup wizard steps verified at 1440×900, 834×1112 and 390×844
  with **0 document overflow** (one-viewport rule).

## Security audit (Part 2 · rules 1–25)

- **Secrets:** `git ls-files` tracks only `Backend/.env.example` and `frontend/.env.example`;
  `git check-ignore` confirms `.env`, `*.db`, `.venv`, `node_modules`, `dist` excluded. Full
  tracked-file scan for key/token/private-key patterns found only test fixtures and
  `postgresql://` documentation strings — **no real secrets**. No rotation required.
- **Auth:** Argon2id hashing; HttpOnly cookie (no localStorage); JWT validated for
  signature/issuer/expiry/`typ`; generic `401`s; timing equalization on unknown accounts;
  `409` on duplicate signup.
- **Authorization:** identity only from the verified cookie; ownership helpers return 404
  on cross-user access; no client-supplied owner IDs trusted.
- **Input/XSS:** Pydantic `extra="forbid"`; errors never echo values; frontend React-escaped.
- **Rate/DoS:** separate signup/login buckets + global limiter + request body-size guard.
- **Dependencies:** 4 new pinned deps (`sqlalchemy`, `argon2-cffi`, `PyJWT`,
  `email-validator`), all used.
- **Known limitation:** rate-limit state is per-process memory (revisit for multi-worker).
- **API path decision:** brief's `/api/auth/*` implemented as `/api/v1/auth/*` (single
  canonical prefix from Part 1) — recorded in ARCHITECTURE §9.

## Next action

Part 3 — Plant Setup + Configuration: owned `PlantConfig`/`PlantState`, CRUD with
`get_owned_or_404`, validation, and one-viewport setup UI.

---

# Checkpoint — 2026-10-02 · PART 1 COMPLETE

**Status:** 🟢 Part 1 (Repository Audit + Secure Foundation) implemented and tested  
**Project:** SafeFlux — Autonomous Process-Safety Failure Hunter  
**Track:** Best Apps & Agents

## Repository audit (before any code)

- `docs/` contained the three canonical files; no source code existed yet.
- Git history: 5 documentation-only commits; no code, no tests, no README/LICENSE.
- `.gitignore` was already comprehensive (env files, keys, venvs, dist, db, logs).
- Secret scan of full history: no credentials found. No rotation required.

## What is complete (Part 1)

### Backend (`Backend/`)

- FastAPI app factory (`app/main.py`) with `/api/v1` router, `GET /health`, root probe.
- Settings layer (`app/core/config.py`): typed pydantic-settings validation,
  `SecretStr` wrapping, production constraints (DEBUG forbidden, JWT_SECRET ≥ 32 chars),
  fail-fast startup that reports variable **names only**.
- Consistent envelope helpers (`app/core/responses.py`) and global exception handlers
  (`app/core/errors.py`): safe messages, sanitized validation details, no stack traces.
- Security middleware (`app/core/security.py`): security headers, HSTS in production
  only, catch-all conversion of unhandled exceptions to safe 500s, strict CORS allowlist
  derived from `FRONTEND_URL` (credentials allowed, never `*`).
- Rate limiting (`app/core/rate_limit.py`): in-memory fixed window per client IP,
  health endpoint exempt, bounded memory.
- `Backend/.env.example` (no secrets), pinned `requirements.txt`.

### Frontend (`frontend/`)

- Vite + React 19 + TypeScript (strict) + Tailwind v4, oxlint clean.
- Axios client unwrapping the `{success,data}` envelope and normalizing failures to
  `ApiError` with safe messages; TanStack Query wiring.
- Public layout (landing/login/signup) and one-viewport authenticated workspace shell
  (`AppLayout`: fixed header/sidebar, internal content scroll, mobile top nav).
- Fail-closed `AuthProvider` + `ProtectedRoute` — no session ⇒ locked routes.
- Routes match `ARCHITECTURE.md` §4; placeholder pages mark which part unlocks them.
- Landing is a **single-viewport marketing screen**: hero + switchable tab panels
  (investigation loop / boundary hunting / guardrails) instead of a scrolling page.
  `PublicLayout` keeps the document itself from scrolling; overflow lives only inside
  the tab panel region (nothing clipped). Verified at 1440×900, 834×1112 and 390×844.
- Signup is a 2-step wizard (one-viewport form rule); loading/error foundations
  (`ErrorBoundary`, `LoadingFallback`, `ErrorPanel`).
- `frontend/.env.example` (public config only).

### Docs

- `README.md` (real setup instructions), `LICENSE` (MIT) added;
  this checkpoint written; ARCHITECTURE status line updated.
- `SAFEFLUX_MASTER.md` untouched — no product requirement changed.

## Tests run

- Backend: `python -m pytest` → **28 passed** (health, envelope contract, 404/405/422/500
  safety, security headers, HSTS prod-only, docs lockdown in production, CORS allow/deny,
  rate limit + window recovery, config validation, secret-safe failure messages).
- Frontend: `npm run lint` → 0 warnings/errors; `npm run build` (tsc strict + vite) green.
- Live smoke: backend on :8000, frontend on :5173 — health envelope ✅, CORS allow ✅,
  CORS deny (no ACAO) ✅, headers ✅, safe 404/500 ✅, bad config fails with field names ✅.
- Browser verified: landing API badge reads “API online · v0.1.0 · development”,
  `/dashboard` redirects to `/login`, login submit surfaces the backend’s safe error
  envelope in the UI.

## Security audit (Part 1 rules 1–25)

- No secrets committed; only `.env.example` files tracked; `git check-ignore` confirms
  `.env`, `.venv`, `node_modules`, `dist`, `*.db` are excluded.
- Production bundle scanned: no API keys/JWT/NEBIUS material (only the public
  `VITE_API_BASE_URL` fallback). Rule 22: no new external API integrated in Part 1 —
  Nebius vars exist in `.env.example` but are unused until Part 8.
- Dependency review: backend 6 pinned direct deps (all used); frontend deps limited to
  the locked stack + Tailwind; template leftovers removed (App.css, stock assets/README).
- Known limitation: rate-limit state is per-process memory (fine for the MVP; revisit
  if multi-worker deployment is added).

## Decisions

1. Session check fails **closed**: `/auth/session` 404 (Part 2 endpoint) → unauthenticated.
2. FastAPI `debug` is always `False`; `DEBUG` only controls log verbosity.
3. `/docs` and `/openapi.json` are disabled in production.
4. Validation errors return sanitized `details[]` (field + message) without echoing
   submitted values.
5. Backend `.env` files are never created in the repo; local runs pass env vars directly.

## Next action

Part 2 — Authentication + Authorization: Argon2/bcrypt hashing, HttpOnly cookie sessions,
`get_current_user()`, ownership-scoped resources, IDOR/cross-user tests, auth rate limits.

---

# Checkpoint — 2026-10-02 (documentation restored)

**Status:** 🟡 Documentation restored; ready for a pre-implementation Duck audit  
**Project:** SafeFlux — Autonomous Process-Safety Failure Hunter  
**Track:** Best Apps & Agents

## What is complete

The persistent SafeFlux project documentation has been rebuilt to incorporate both the original project architecture and the later development requirements.

Restored source-of-truth files:

```text
docs/SAFEFLUX_MASTER.md
docs/ARCHITECTURE.md
docs/SESSION_LOG.md
```

The restored docs include:

- locked SafeFlux MVP,
- deterministic simulator vs AI responsibilities,
- authentication,
- server-side access control,
- the 25 permanent security/engineering rules,
- one-viewport authenticated UI rule,
- GSAP animation constraints,
- testing after every feature,
- Git commit discipline,
- Nebius/NVIDIA credential policy,
- 10-part build plan,
- Debugging Duck protocol.

---

## Core project sentence

> SafeFlux lets a process engineer describe a proposed engineering change, autonomously searches a digital process simulation for hidden unsafe conditions, verifies findings deterministically, and presents evidence for human review.

## Golden rule

> **AI searches for danger → Simulator proves it → Engineer decides.**

---

## Locked MVP

```text
Feed Tank
    ↓
Pump P-101
    ↓
Heated Reactor R-101
 ┌──────┼──────────┐
 │      │          │
Heater Cooling   Sensors
    ↓
Outlet Valve V-101
    ↓
Product Tank
```

Main variables:

- feed flow
- temperature
- pressure
- level
- cooling
- valve
- pump
- heater
- shutdown timing

Initial failures:

- cooling degradation/loss
- outlet restriction
- feed increase
- pump variation
- sensor failures
- shutdown delay
- selected combinations

---

## Permanent 25-Point Engineering Checklist

Every development part must preserve:

1. hidden API keys,
2. env validation,
3. protected private routes,
4. proper auth,
5. backend access control,
6. validated/sanitized forms,
7. XSS protection,
8. rate limiting,
9. secure API format,
10. strict CORS,
11. security headers,
12. production debug off,
13. dependency review,
14. unused-package removal,
15. exposed-file checks,
16. secure database,
17. password hashing,
18. Git secret scanning,
19. full security audits,
20. meaningful commit/push after coherent feature or ~300 meaningful LOC; target 50+ across full project without fake commit spam,
21. continuous security,
22. explicit API-key request before external integration,
23. tests after each feature,
24. README/docs synchronized,
25. one-viewport authenticated screens without clipping.

---

## One-Viewport Rule

Do not disable scrolling and hide content.

Use:

```text
long form    → steps
long list    → pagination
table        → pagination
many panels  → tabs/routes
many charts  → switcher
mobile       → one major panel at a time
```

Landing/marketing may intentionally scroll. Authenticated application screens should behave like contained app workspaces.

---

## Ten-Part Build Plan

1. Repository Audit + Secure Foundation
2. Authentication + Authorization
3. Plant Setup + Configuration
4. Deterministic Process Simulator
5. Safety Engine + Telemetry
6. Engineering Dashboard + Visualization
7. Scenario Engine + Boundary Search
8. Nebius + NVIDIA Nemotron Agent
9. Investigation + Safeguards + Re-verify UX
10. Final Hardening + Audit + Deployment

After every part:

```text
implement → test → commit/push → Duck → next part
```

Submission/video work begins only after Part 10 passes.

---

## API Credential Policy

Before adding any new external service, the coding agent must state:

```text
Provider:
Purpose:
Environment variable:
Frontend or backend:
```

Expected AI provider:

```text
Provider: Nebius Token Factory
Purpose: NVIDIA Nemotron reasoning
Environment:
NEBIUS_API_KEY
NEBIUS_BASE_URL
NEBIUS_MODEL
Location: backend only
```

Exact model ID remains unlocked until actual catalog/account access is checked.

---

## Known Risks

### Simulator credibility
Avoid fake/random telemetry. Use explicit simplified equations, deterministic output and seeded tests.

### AI becomes decorative
Avoid a one-call report wrapper. Use an iterative bounded tool loop.

### AI becomes numerical truth
Simulator and safety engine remain authoritative.

### Scope explosion
Avoid unrelated enterprise infrastructure and real PLC control.

### Security regression from AI coding agents
Use the 25-point checklist, tests, secret scans and Duck after each part.

### Incorrect no-scroll implementation
Do not clip. Redesign with steps, tabs, pagination and responsive panel switching.

---

## Current Repository Note

The project files previously existed in an inconsistent location. The canonical source-of-truth location is now:

```text
docs/
```

Old duplicate root-level copies should not be treated as authoritative and should be removed once the canonical docs are confirmed.

---

## Next Action

Run Debugging Duck against the repository.

If the canonical `docs/` files exist and no blocker is found, begin Prompt 1/10.

---

# Debugging Duck 🦆

Trigger:

`Duck`
`Debugging Duck`
or an obvious close typo.

Procedure:

1. inspect GitHub,
2. read all three canonical docs,
3. inspect current implementation,
4. compare requirements vs code,
5. check all 25 rules,
6. check one-viewport rule,
7. check tests/commits/dependencies/secrets,
8. report:
   - ON TRACK ✅
   - DRIFTING ⚠️
   - BLOCKED / BROKEN ❌
9. state the smallest useful next action,
10. update docs when a real decision changes.
