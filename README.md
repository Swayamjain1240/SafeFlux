<div align="center">

# SafeFlux

**Autonomous Process-Safety Failure Hunter**

`AI searches for danger` → `Simulator proves it` → `Engineer decides`

[![License: MIT](https://img.shields.io/badge/License-MIT-00C2A8.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.142-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Tests](https://img.shields.io/badge/tests-326%20%C2%B7%2087-2E7D32.svg)](#testing--qa)
[![Nebius × NVIDIA Hackathon](https://img.shields.io/badge/Nebius%20%C3%97%20NVIDIA-Hackathon-7B2FBE.svg)](docs/SAFEFLUX_MASTER.md)

*Nebius × NVIDIA Global AI Hackathon — Best Apps & Agents*

</div>

---

SafeFlux lets a process-safety engineer describe a proposed engineering change, autonomously
searches a digital process simulation for hidden unsafe conditions, verifies every finding
deterministically, and presents the evidence for human review.

> [!IMPORTANT]
> SafeFlux is a **simulation and decision-support prototype**. It never controls real
> industrial equipment — no PLC/DCS actuation, no real valve or pump control, ever. No output
> of this system is a claim about a real plant.

## Contents

- [How it works](#how-it-works)
- [Highlights](#highlights)
- [Status](#status)
- [Tech stack](#tech-stack)
- [Quick start](#quick-start)
- [Repository layout](#repository-layout)
- [Environment variables](#environment-variables)
- [API overview](#api-overview)
- [Security](#security)
- [Design system](#design-system)
- [Testing & QA](#testing--qa)
- [Documentation](#documentation)
- [Known limitations](#known-limitations)
- [License](#license)

---

## How it works

One analysis is one bounded, autonomous run over an owned plant. Every number comes from the
deterministic layers; the AI never supplies one.

```text
  engineer describes a proposed change
                 │
                 ▼
   ┌───────────────────┐   ┌──────────────┐   ┌───────────────────┐   ┌────────────────┐
   │ Scenario search   │──▶│  Simulator   │──▶│  Safety engine    │──▶│  Evidence      │
   │ picks the test    │   │  NumPy/SciPy │   │  SAFE / NEAR_     │   │  report · PDF  │
   │ values (no AI)    │   │  physics     │   │  LIMIT / VIOLATION│   │  · re-verify   │
   └───────────────────┘   └──────────────┘   └───────────────────┘   └────────────────┘
```

The NVIDIA Nemotron agent (via Nebius Token Factory) sits **beside** this pipeline: it decides
*what deserves investigation* and narrates *what was found*. It cannot compute a temperature,
set or relax a limit, decide a verdict, run code, read a secret or touch equipment.

| Who | Decides |
| --- | --- |
| **Nemotron (Nebius)** | which variable to investigate, which action to take, how to explain the evidence |
| **Search engine** | every numeric test value — sampling points, boundary, refinement |
| **Simulator** | what the process does — trajectories, peaks, events |
| **Safety engine** | the threshold verdict — `SAFE` / `NEAR_LIMIT` / `SAFEGUARD_ACTIVATED` / `VIOLATION` |
| **Engineer** | whether to proceed — SafeFlux presents evidence, never a decision |

## Highlights

**Deterministic safety core**
- Lumped, well-mixed process simulator (mass/energy balances, faults, sensor faults) — **no RNG and no LLM in the physics**; identical inputs always give identical outputs.
- Safety engine with four verdicts and safeguard timing (`trigger → response → violation`, *prevented* vs *too late*).
- Scenario search — sweep, sensitivity and combination modes with monotonicity-checked bisection refinement; allowlisted variables only, hard budgets enforced **before** compute, `422` instead of a silent clamp.

**Autonomous analysis (the full engineer workflow)**
- Goal → plan → scenarios → refine → counterfactuals → safeguard check → stored evidence document, every stage writing real events with real elapsed times.
- Live investigation timeline, failure detail with trajectories and first-violation points, counterfactual comparison, bounded re-verification with before/after tables.
- Interactive tabbed report plus a dependency-free multi-page PDF export.

**Hybrid AI agent**
- 9 allowlisted tools, strict Pydantic validation of every model decision, an explicit bounded state machine (steps / model calls / simulations / tokens / time), prompt-injection defence, secret redaction and allowlisted logging.
- Works fully without a key: the investigation endpoint answers `not_configured` instead of failing.

**Product surface**
- Dark control-room design system (tokens, instrument primitives, one-viewport shell), React Flow process graph, Recharts telemetry over SSE, GSAP motion with `prefers-reduced-motion` support, and a lazy Three.js reactor twin on the landing hero.
- Strict **one-viewport rule**: every authenticated page fits `100dvh` at every tested size; long content becomes tabs, pagination or a bounded scroll region.

**Platform**
- FastAPI + Pydantic v2, Argon2id passwords, HttpOnly session cookie, ownership-scoped access (cross-user → `404`), strict CORS, security headers, per-IP and per-user rate limits, request body-size guard, hard compute budgets.

## Status

Build **Part 9 of 10** is implemented and test-verified end to end.

| Area | State |
| --- | --- |
| FastAPI bootstrap, `/api/v1`, env validation, error envelopes, headers, CORS, rate limits | ✅ |
| Auth: signup / login / logout / session, Argon2id + HttpOnly cookie, ownership foundation | ✅ |
| Plant domain, owned CRUD, 5-step one-viewport wizard + React Flow topology preview | ✅ |
| Deterministic simulator, fault injection, hard compute budgets | ✅ |
| Safety engine + safeguard timing + live SSE telemetry + one-viewport monitor | ✅ |
| Engineering dashboard on real backend data (no fixtures) | ✅ |
| Deterministic scenario search (sweep / sensitivity / combinations) + search workspace | ✅ |
| AI investigation agent: allowlisted tools, bounded loop, budgets, injection defence | ✅ |
| Autonomous analyses: run / events / failures / counterfactuals / safeguards / re-verify / report / PDF | ✅ |
| Dark control-room design system, GSAP motion, Three.js hero twin, code-split routes | ✅ |
| Backend test suite (pytest) | ✅ 326 passing |
| Frontend unit tests (`node --test`) | ✅ 87 passing |
| Hardening + security / one-viewport / dependency audit (QA Parts 1–2) | ✅ approved with warnings |
| Hosted deployment | ⏳ no hosted environment yet; production config validated |
| One controlled real Nebius/NVIDIA inference | ⏳ needs `NEBIUS_API_KEY` |

## Tech stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy, SQLite (MVP) / PostgreSQL |
| Numerics | NumPy, SciPy (deterministic integration) |
| Auth | Argon2id (`argon2-cffi`), PyJWT, HttpOnly cookie session |
| AI | Nebius Token Factory, NVIDIA Nemotron, OpenAI-compatible `httpx` client |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4 |
| Data & charts | TanStack Query, axios, Recharts, React Flow |
| Motion & 3D | GSAP, Three.js (single lazy hero asset) |
| Tooling | oxlint, `node --test`, pytest, one-command root scripts |

## Quick start

**Prerequisites:** Python 3.12+ · Node.js 20+ (npm 10+)

```bash
git clone https://github.com/Swayamjain1240/SafeFlux.git
cd SafeFlux
```

**One-time setup**

```bash
# backend
cd Backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(64))"   # → JWT_SECRET
cd ..

# frontend
cd frontend && npm install && cd ..
cp frontend/.env.example frontend/.env
```

**Run everything (one command)**

```bash
npm run dev      # backend :8000 + frontend :5173, prefixed logs, Ctrl+C stops both
```

`scripts/dev.mjs` starts uvicorn and Vite together, labels every line `[backend]` / `[frontend]`,
and stops the surviving process if either service dies — no stray servers. It uses the project
venv when present and never inherits a generic `PORT` (override the API port with
`SAFEFLUX_BACKEND_PORT`).

- API health check: <http://localhost:8000/api/v1/health>
- App: <http://localhost:5173>

> The backend **fails fast at startup** and prints variable *names only* (never values) if a
> required environment variable is missing or invalid.

**Run the whole regression (one command)**

```bash
npm test         # lint → 87 frontend unit tests → typecheck + build → 326 backend tests
```

## Repository layout

```text
SafeFlux/
├── frontend/          React + Vite + TypeScript + Tailwind
│   ├── src/           api, components, pages, routes, auth, animation, three, …
│   └── tests/         unit tests (node --test)
├── Backend/           FastAPI + Pydantic service
│   ├── app/           api, auth, core, models, schemas, simulator, safety,
│   │                  telemetry, search, ai, analyses, reports
│   ├── tests/         pytest suite
│   └── .env.example   backend environment template
├── docs/              source-of-truth project docs
├── scripts/           dev.mjs (run the stack) · test.mjs (run every check)
├── .env.example       root runner port + production checklist
├── README.md
└── LICENSE
```

## Environment variables

Three templates are tracked — **never commit a real `.env`**:

| Template | Read by | Purpose |
| --- | --- | --- |
| [`.env.example`](.env.example) | operator docs | root runner port + production checklist |
| [`Backend/.env.example`](Backend/.env.example) | FastAPI service | every backend setting |
| [`frontend/.env.example`](frontend/.env.example) | Vite build | public `VITE_*` variables only |

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
| `SEARCH_MAX_REFINEMENT_DEPTH` / `SEARCH_TIMEOUT_SECONDS` | no (6 / 90) | refinement levels / overall search timeout |
| `SEARCH_RATE_LIMIT_RUNS` / `SEARCH_RATE_LIMIT_WINDOW_SECONDS` | no | search per-IP rate limit (tightest bucket in the API) |
| `TELEMETRY_MAX_HISTORY` / `TELEMETRY_MAX_PLANTS` | no | retained frames per plant / plants per process |
| `TELEMETRY_MAX_STREAMS[_PER_PLANT\|_PER_USER]` | no | concurrent SSE stream limits |
| `TELEMETRY_REPLAY_INTERVAL_MS` / `TELEMETRY_HISTORY_DEFAULT_LIMIT` | no | stream pacing / default history size |
| `NEBIUS_API_KEY` / `NEBIUS_BASE_URL` / `NEBIUS_MODEL` | Part 8 | AI provider — **backend only**, never exposed to the frontend |
| `AI_MAX_STEPS` / `AI_MAX_MODEL_CALLS` / `AI_MAX_SIMULATIONS` / `AI_MAX_TOKENS` | no (6/8/40/20000) | hard bounds for one investigation |
| `AI_TIMEOUT_SECONDS` / `AI_MAX_OUTPUT_TOKENS` | no (120/700) | wall-clock ceiling / per-call output cap |
| `AI_PROVIDER_TIMEOUT_S` / `AI_PROVIDER_MAX_ATTEMPTS` / `AI_TEMPERATURE` | no (45/2/0) | one provider call: timeout, retries (1..5), temperature |
| `AI_RATE_LIMIT_RUNS` / `AI_RATE_LIMIT_WINDOW_SECONDS` | no (6/300) | per-**user** AI analysis budget |

### Frontend (`frontend/.env.example`)

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | backend API base URL (public by design — the frontend ships no secrets) |

### Root (`.env.example`)

| Variable | Purpose |
| --- | --- |
| `SAFEFLUX_BACKEND_PORT` | port `npm run dev` binds the API to (default 8000) |

## API overview

All endpoints live under `/api/v1`. Every response uses the same envelope:

```json
{ "success": true, "data": {} }
```

```json
{ "success": false, "error": { "code": "NOT_FOUND", "message": "The requested resource was not found." } }
```

Stack traces, SQL, file paths, secrets and provider details are never returned.

| Area | Endpoints |
| --- | --- |
| Health | `GET /health` |
| Auth | `POST /auth/signup` · `POST /auth/login` · `POST /auth/logout` · `GET /auth/me` (`/auth/session`) |
| Plants | `POST /plants` · `GET /plants` · `GET/PATCH/DELETE /plants/{id}` · `GET /plants/{id}/state` |
| Simulations | `POST /simulations/run` (authenticated, owner-scoped, budgeted) |
| Telemetry | `GET /plants/{id}/telemetry/current` · `/history` · `/stream` (SSE) |
| Searches | `GET /searches/capabilities` · `POST /searches/run` |
| Investigations | `GET /investigations/capabilities` · `POST /investigations/run` |
| Analyses | `POST /analyses/run` · `GET /analyses` · `GET /analyses/{id}` · `/events` · `/result` · `/failures/{failureId}` · `POST /analyses/{id}/reverify` · `GET …/report` · `GET …/report.pdf` |

Conventions: ownership is resolved server-side only — another user's plant, analysis, failure or
report is a **404**, never a 403 leak. Expensive endpoints are rate-limited per IP or per user
and answer **409** on a duplicate in-flight run. Validation errors never echo submitted values.

Full reference: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### Running the real Nebius inference (optional)

The key is only ever read from `Backend/.env` — never passed as a command-line argument, so it
cannot leak into shell history:

```bash
# from Backend/
python -m scripts.nebius_probe models                              # ids THIS account can call
# put the chosen id in NEBIUS_MODEL, then:
python -m scripts.nebius_probe check                               # one tiny real completion
python -m scripts.nebius_probe investigate --email you@example.com # one controlled run
```

Without all three `NEBIUS_*` variables the endpoint answers `not_configured`, no model is
contacted, and everything else keeps working.

## Security

- **Fail-fast config**: validated environment, secrets wrapped in `SecretStr`, variable names only in errors.
- **Session**: Argon2id hashing; the token lives only in an `HttpOnly` cookie (`Secure` in production, `SameSite=Lax`) — never in JavaScript, `localStorage` or a response body.
- **Access**: `owner_id` is server-assigned only; `get_owned_or_404` returns **404** for cross-user access so existence is never leaked (IDOR-tested).
- **Transport**: strict CORS allowlist with credentials (never `*`), security headers on every response, HSTS in production, `/docs` disabled in production.
- **Abuse control**: per-IP and per-user rate-limit buckets, request body-size guard → `413`, hard compute budgets rejected **before** integration.
- **Determinism**: no `eval`/`exec`, generated code or shell anywhere; a search variable name only selects a row of a fixed allowlist table.
- **AI surface**: the provider key never reaches the browser, logs or prompts; a public `http://` provider URL is refused; tool arguments are re-validated independently of the model; bounds are clamped at startup; invalid model output stops the run safely.
- **Frontend**: no secrets, no `dangerouslySetInnerHTML`, React-escaped rendering only, centralized 401 session-expiry handling.

Per-part detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · audit results: [docs/QA_PART1_REPORT.md](docs/QA_PART1_REPORT.md), [docs/QA_PART2_REPORT.md](docs/QA_PART2_REPORT.md).

## Design system

SafeFlux is styled as an **industrial control room**, not a SaaS dashboard: near-black graphite
surfaces, thin technical borders, one electric-cyan accent for live state, violet for the AI
layer, and safety colours reserved strictly for meaning.

- **Tokens** (`frontend/src/index.css`): `void / graphite / panel / surface / edge`, `accent`, `ai`, `safe / warn / crit`, plus `grid-bg`, `panel`, `stat-num` (mono, tabular numerals) and `glow-*`.
- **Primitives**: `Panel`, `InstrumentTile`, `Gauge`, `StatusBadge`, `StatePanel`, `TabBar` — the only way a page composes surfaces.
- **Semantic colour rule**: `safe` / `warn` / `crit` always mean safety verdicts, and every critical state also carries an icon and a word — colour is never the only signal.
- **Motion**: planned by pure, unit-tested modules and applied with GSAP inside a reverted `gsap.context()`; transitions stay within 200–500 ms; `prefers-reduced-motion` disables everything.
- **3D**: one lazy Three.js reactor twin on the landing hero — renders only while visible, degrades to SVG without WebGL, disposes every GPU resource on unmount.

## Testing & QA

```bash
npm test              # from the repo root: lint → unit → typecheck+build → pytest

# or individually:
cd frontend
npm run lint          # oxlint, 0 warnings
npm run test:unit     # node --test — 87 tests
npm run build         # tsc --strict + vite production build

cd ../Backend
python -m pytest -q -p no:warnings   # 326 tests
```

Coverage includes determinism (identical inputs → identical outputs), IDOR/ownership, rate
limits and budgets, safety verdict wording, agent bounds and injection defence, stream state
machines, and the one-viewport layout rule. QA reports live in [`docs/`](docs).

## Documentation

| Document | Contents |
| --- | --- |
| [docs/SAFEFLUX_MASTER.md](docs/SAFEFLUX_MASTER.md) | product rules, scope, safety language, ten-part build plan |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | system design, module by module |
| [docs/SESSION_LOG.md](docs/SESSION_LOG.md) | progress checkpoints, what is done / current / next |
| [docs/QA_TEST_PLAN.md](docs/QA_TEST_PLAN.md) | test plan and acceptance criteria |
| [docs/QA_PART1_REPORT.md](docs/QA_PART1_REPORT.md) · [docs/QA_PART2_REPORT.md](docs/QA_PART2_REPORT.md) | executed QA results and release recommendation |

## Known limitations

- No hosted environment yet — deployment config and production validation are done, real hosting is the next step.
- Real Nebius/NVIDIA inference is **blocked** until a `NEBIUS_API_KEY` is supplied; every other feature works without it.
- Rate-limiter state is per-process memory (documented MVP scope); SQLite is the MVP database.
- The simulator is a simplified lumped model with a documented pressure proxy — decision-support prototype, **not** certified safety software.

## License

MIT — see [LICENSE](LICENSE).
