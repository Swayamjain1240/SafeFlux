# SafeFlux — QA Test Plan

**Project:** SafeFlux — Autonomous Process-Safety Failure Hunter
**Scope owner:** Final QA (Parts 1 and 2)
**Created:** 2026-10-07
**Companion reports:** [QA_PART1_REPORT.md](QA_PART1_REPORT.md) · [QA_PART2_REPORT.md](QA_PART2_REPORT.md)

---

## 1. Scope

Final validation of the completed SafeFlux application (ten-part build plan; Parts 1–9
implemented, Part 10 hardening/audit executed during QA).

- **QA Part 1:** unit, integration, API, contract, database, authentication/authorization,
  simulator, safety engine, scenario search, AI/agent, security regression.
- **QA Part 2:** system, end-to-end, functional, acceptance/UAT, non-functional, responsive,
  one-viewport, accessibility, performance, reliability, error/recovery, compatibility,
  final security validation, deployment validation, release acceptance.

**Golden rule under test:** *AI searches for danger → Simulator proves it → Engineer
decides.* The LLM must never be the source of physical truth (temperature, pressure, flow,
level, thresholds, violation detection, safeguard timing, evidence).

**Out of scope:** hackathon video/submission material; destructive tests against any
production or third-party system; unbounded load against external services.

---

## 2. Environments

| Environment | Configuration | Purpose |
| --- | --- | --- |
| Test (backend) | `Backend/tests` on isolated per-test SQLite DBs (`conftest.py`), no network, provider faked via `ScriptedProvider` | all backend suites |
| Test (frontend) | `node --test` pure-module runner | unit tests |
| Local dev (integrated) | `uvicorn app.main:app` on :8000 + `vite` on :5173, real HTTP, real SQLite file | E2E/system/perf/viewport testing |
| Production-mode check | `ENVIRONMENT=production` settings validation + startup checks (no cloud deployment exists) | deployment validation |

Browsers (Part 2): Chromium (bundled preview browser). Firefox/Safari not available in this
environment — recorded as an environment limitation.

---

## 3. Module inventory, existing coverage, risk

Risk = impact × likelihood of a defect harming the product's safety mission or users.

| Module | What exists | Current test coverage | Risk | Tests required (Part 1 / Part 2) |
| --- | --- | --- | --- | --- |
| Authentication (signup/login/logout/session) | Argon2id, HttpOnly cookie JWT, rate-limited | `test_auth.py` 26 tests: hashing/verification/expiry/tamper/unknown-user timing/cookie flags | **CRITICAL** | keep regression / browser flow |
| Users (model, uniqueness, email normalization) | SQLAlchemy user model, lower-cased unique email | `test_auth.py`, `test_plants.py` fixtures | **CRITICAL** | uniqueness covered / persistence check |
| Authorization / ownership | `get_owned_or_404`, `ensure_owner`; server-side identity only | IDOR tests in plants, simulations, telemetry, searches, investigations, analyses | **CRITICAL** | full cross-user matrix / deep-link repeat |
| Plant / PlantConfig / PlantState / SafetyLimits / SafeguardConfig | 5-table plant domain, bounds, trip-limit invariant | `test_plants.py` 25 tests incl. PATCH consistency guard | **CRITICAL** | covered / wizard E2E |
| Simulator | deterministic lumped model (solve_ivp), faults, sensor faults, shutdown | `test_simulator.py` 21 tests: direction invariants, repeatability, true-vs-observed | **CRITICAL** | covered / live telemetry E2E |
| Fault injection | 6 process faults + sensor bias/freeze | covered in `test_simulator.py` | **HIGH** | covered / failure-detail E2E |
| Safety engine | SAFE/NEAR_LIMIT/SAFEGUARD_ACTIVATED/VIOLATION + findings | `test_safety.py` 16 tests incl. near-limit band, roll-up | **CRITICAL** | covered / verdict UI language |
| Safeguards | trigger/response/violation, prevented vs too late | covered in `test_safety.py` | **HIGH** | covered / safeguards page E2E |
| Telemetry (current/history/SSE) | bounded store, connection limits, owner-scoped | `test_telemetry_api.py` 12 tests | **HIGH** | covered / stream behaviour in browser |
| Scenario search + boundary refinement | allowlist, sweep, monotonic bisection/densify, budgets | `test_search.py` 24 + `test_search_api.py` 22 | **CRITICAL** | covered / search UI E2E |
| Analysis (autonomous pipeline, events) | real-event pipeline, bounded document | `test_analyses_pipeline.py` 16 + `test_analyses_api.py` 15 | **CRITICAL** | covered / live-page E2E |
| Counterfactual analysis | restore-A/B/C re-simulations | covered in analyses tests | **HIGH** | covered / investigation page E2E |
| Reverification | allowlisted mitigations, before/after | covered in analyses tests | **HIGH** | covered / reverify page E2E |
| History | paginated, owner-scoped | covered in analyses tests | **MEDIUM** | covered / pagination E2E |
| Reports (interactive + PDF) | evidence document, escaped PDF | covered in analyses tests (incl. PDF escaping) | **MEDIUM** | covered / report page + PDF E2E |
| AI provider (Nebius client) | validated URL, bounded retries, error vocabulary | `test_ai_provider.py`, probe tested vs loopback fake | **HIGH** | covered / real inference **BLOCKED** (no key) |
| Agent (bounded state machine) | closed action enum, budgets, stop reasons | `test_ai_agent.py` | **CRITICAL** | covered / explanation grounding check |
| AI tools (9 allowlisted) | strict arg schemas, budget charge, payload ceiling | `test_ai_tools.py` | **CRITICAL** | covered |
| Prompt-injection defence | sanitize, detect, wrap, validate, enforce | `test_ai_security.py` | **CRITICAL** | covered / XSS render checks |
| Investigations API | capabilities + run, 409 duplicate, per-user limit | `test_investigations_api.py` | **HIGH** | covered |
| API middleware (envelope, errors, body limit, headers, CORS, rate limits, debug lockdown) | Part 1 middleware stack | `test_health.py`, `test_errors.py`, `test_cors.py`, `test_security_headers.py`, `test_rate_limit.py`, `test_config.py` | **CRITICAL** | covered / live header verification |
| Environment configuration | fail-fast validation, SecretStr, production constraints | `test_config.py` 9 tests | **CRITICAL** | covered / production-mode check |
| Database (SQLite, SQLAlchemy) | ORM only, ownership FKs, cascade delete | exercised by all API suites + PATCH rollback test | **HIGH** | raw-SQL/credential scan (done, clean) / persistence-restart check |
| Frontend pure modules (viewport, layout, viewState, stream, plan, motion) | 65 node unit tests | `frontend/tests/*.test.ts` | **MEDIUM** | covered / DOM geometry audit |
| PDF export | dependency-free writer | tested (escaping) | **LOW** | covered / download E2E |

---

## 4. Test categories

1. **Unit** — pure functions and modules in isolation (auth utilities, schemas, simulator
   equations, safety classification, search refinement, AI parsing/security, frontend pure modules).
2. **Integration** — real module chains through the API layer with the real simulator/safety
   engine (auth→plant→simulation→safety; search→simulator→safety; analysis pipeline;
   counterfactual; reverify).
3. **API / contract** — every endpoint: success envelope `{success, data}`, error envelope
   `{success:false, error:{code,message}}`, status codes (200/201/204/400/401/404/409/413/422/429/500),
   schema strictness (`extra="forbid"`), no value echo, no secret/stack/path leakage.
4. **Database** — constraints, ownership relations, cascade delete, transaction rollback,
   no raw/user-controlled SQL, no committed credentials.
5. **Security regression** — unauthenticated access, cross-user IDOR, rate limits, body-size
   guard, security headers, CORS, debug lockdown, tool allowlist, prompt injection,
   malformed AI output, secret hygiene (working tree + full git history).
6. **System / E2E (Part 2)** — real backend + real browser, full user journey.
7. **Non-functional (Part 2)** — one-viewport geometry, responsive resizing, accessibility,
   performance, reliability/recovery, session behaviour.

---

## 5. Risks and mitigations

| Risk | Mitigation under test |
| --- | --- |
| LLM output treated as physical truth | golden-rule tests: evidence from Part 4/5/7 only; AI explanation stored/rendered separately; numeric claims grounded (Part 2 §AI grounding) |
| Cross-user data leak (IDOR) | ownership helpers return 404; tested for every owned resource, repeated via deep links in Part 2 |
| Safety verdict fabricated on system error | pipeline marks `interrupted`/`failed`; engine is deterministic; no-failure language is a fixed constant |
| Unbounded compute (simulation/search/agent) | hard budgets + rate limits + 422-before-compute; agent stop reasons |
| Secret exposure (tree, history, bundle, logs) | scans of tree + full history; `.env` gitignored; bundle contains only `VITE_API_BASE_URL`; redaction tested |
| One-viewport violation | DOM geometry audit at all required sizes (Part 2) |
| Real provider not exercised | key absent ⇒ explicitly **BLOCKED**, never claimed as PASS |

---

## 6. Acceptance criteria (Part 1 exit)

1. CRITICAL unit tests pass; integration flows pass; API tests pass.
2. Auth tests pass; IDOR tests pass.
3. Simulator deterministic tests pass; safety engine tests pass; search tests pass.
4. Agent security tests pass.
5. No known S0/S1 defects remain; no leaked active credentials remain.
6. Test suite is reproducible (documented commands, isolated DBs).
7. A test blocked by an external dependency is marked **BLOCKED**, never PASS.

**Part 2 exit:** per `QA_PART2_REPORT.md` §Exit criteria (release matrix + blockers list).

---

## 7. Severity definitions

| Severity | Meaning |
| --- | --- |
| **S0** | Security/critical release blocker (leaked active credential, auth bypass, IDOR, arbitrary code execution, real-plant actuation path) |
| **S1** | Critical functionality blocker (core flow broken, false SAFE result, unbounded loop) |
| **S2** | Major defect (feature broken with workaround, wrong evidence presentation) |
| **S3** | Minor defect (test isolation, cosmetic-but-real behaviour gap, wording) |
| **S4** | Cosmetic/low priority |
