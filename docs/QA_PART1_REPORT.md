# SafeFlux — QA Part 1 Report

**Phase:** FINAL QA — Testing Part 1 of 2 (unit, integration, API, contract, database,
auth/authz, simulator, safety engine, scenario search, AI/agent, security regression)
**Date:** 2026-10-07
**Plan:** [QA_TEST_PLAN.md](QA_TEST_PLAN.md)
**QA Part 1 STATUS: PASS WITH WARNINGS**

Warnings: (1) one S3 defect found and fixed during baseline (test isolation, see BUG-01);
(2) the one controlled **real** Nebius/Nemotron inference remains **BLOCKED** — no
`NEBIUS_API_KEY` exists in `Backend/.env` (verified by variable-name listing only; values
never read or printed). Mocked provider coverage is complete.

---

## 1. Test environment

| Component | Version |
| --- | --- |
| OS | Windows (Git Bash), local checkout `main` @ `c543865` |
| Python | 3.12.10, venv at `Backend/.venv` |
| Key packages | fastapi 0.142.2, pydantic 2.13.5, SQLAlchemy 2.1.3, numpy 2.5.3, scipy 1.18.1, PyJWT 2.15.1, argon2-cffi 25.1.0, httpx 0.28.1 |
| Node | v22.23.1, npm (frontend: React 19 + Vite) |
| Test DB | per-test isolated SQLite via `Backend/tests/conftest.py`; no production DB touched |
| AI provider | **not configured** (no key on this machine) — faked with `ScriptedProvider` everywhere |

Commands (all reproducible):

```bash
cd Backend  && .venv/Scripts/python.exe -m pytest -p no:warnings   # 326 passed
cd frontend && npm run lint        # 0 warnings
cd frontend && npm run test:unit   # 65 passed
cd frontend && npm run build       # tsc strict + vite, green
```

## 2. Totals

| Suite | Passed | Failed | Skipped | Blocked |
| --- | --- | --- | --- | --- |
| Backend (pytest, 27 files) | **326** | 0 | 0 | 0 |
| Frontend unit (node --test) | **65** | 0 | 0 | 0 |
| Frontend lint + build | clean | — | — | — |
| Real Nebius inference (probe) | — | — | — | **1** (no API key) |

Baseline before fixes: 325 passed / 1 failed (`test_config.py::test_get_settings_fails_with_field_names_only`) → BUG-01.

## 3. Unit testing results — PASS

- **Auth utilities** (`test_auth.py`, 26): Argon2id hash/verify, wrong password, unique
  hashes per call (salted), JWT create/decode, expiry, tampered token, wrong issuer,
  missing claims, malformed token, unknown user; plaintext never stored (hash column
  format asserted), hash never returned by any response.
- **Validation** (schemas across `test_plants.py`, `test_search_api.py`, `test_auth.py`,
  `test_simulations_api.py`, `test_analyses_api.py`): boundary/minimum/maximum/negative/
  >100% values, invalid enums, missing required, unknown fields (`extra="forbid"`),
  oversized bodies (413 before parse); validation errors never echo submitted values.
- **Simulator** (`test_simulator.py`, 21): determinism (byte-identical result documents),
  baseline, increased feed, increased heating, reduced cooling, complete cooling loss,
  outlet restriction, valve stuck, pump variation, shutdown delay, combined failures;
  engineering-direction invariants (higher heating never cooler, stronger cooling never
  hotter, greater outlet restriction never increases throughput, feed increase raises
  inventory); **true vs observed state**: sensor bias/freeze change only observed series.
- **Safety engine** (`test_safety.py`, 16): all four statuses per variable, near-limit band
  (configurable, clamped 0.5–1.0), worst-status roll-up, direction (weaker cooling never
  classified safer), finding evidence fields.
- **Safeguards**: trigger/response/violation timestamps computed from the trajectory;
  early shutdown ⇒ `prevented`, long delay ⇒ `too late`; trip driven by the high-alarm
  setpoint so prevention is physically reachable.
- **Scenario search** (`test_search.py` 24): deterministic linspaces, safe-end-first sweep,
  **bisection only when monotonic** (densify otherwise — assumption verified), budget
  enforcement (scenarios/combinations/depth/evaluations/timeout with injected clock),
  reproducibility, no value echo.
- **Counterfactuals** (analyses pipeline tests): restore-cooling / restore-outlet /
  reduce-feed rows are produced by **real re-simulations** (asserted against engine
  outputs); no LLM substitute possible (AI text stored separately).
- **AI parsing/security** (`test_ai_parsing.py`, `test_ai_security.py`): strict decision
  parse (invalid ⇒ reject, never repair), balanced-JSON extraction, sanitizer, 8 named
  injection patterns, forged wrapper markers neutralised, secret redaction (JWT/bearer/
  `sk-…`), log allowlist/denylist.
- **Frontend pure modules** (65 tests): viewport classification, graph orientation,
  dashboard view-state, API failure classification, motion plan (reduced-motion ⇒ static),
  telemetry stream state machine, search planning mirror.

## 4. API testing results — PASS

All implemented endpoints exercised (inventory = the 30+ routes under `/api/v1`):
auth (5), plants (6), simulations (1), telemetry (3), searches (2), investigations (2),
analyses (9), health. Verified per endpoint where applicable: 200/201/204 success,
401 unauthenticated, 404 missing + cross-user, 409 duplicate signup / duplicate run,
413 oversized body, 422 schema violations with per-field details and **no value echo**,
429 with `Retry-After`, 500 generic safe envelope. Contract: `{success:true,data}` /
`{success:false,error:{code,message}}` asserted by `test_health.py`/`test_errors.py`;
no stack traces, SQL, file paths, or secrets in any client-visible error.

## 5. Integration testing results — PASS

Real chains through the API with the real simulator/safety engine/search engine:
auth→persisted user→login→authenticated request; plant create→persist→retrieve;
`PlantConfig+State+Scenario→Simulator→SimulationResult`; `result→SafetyEngine→findings`;
simulation→telemetry store→SSE replay; search→simulator→safety→evidence; analysis run
(goal→plan→search→observe→refine→counterfactuals→safeguards→document); failure→altered
scenario→simulator→comparison (counterfactual); mitigation→re-run→before/after (reverify).

## 6. Authentication results — PASS

Signup (201, session cookie), duplicate email (409, case-insensitive), invalid email,
empty/short password, very long payload (413), wrong password (401 generic), valid login,
logout (idempotent, cookie cleared), `/me` + `/session` aliases, expired/tampered/
malformed tokens, missing cookie. Cookie: HttpOnly always, Secure in production,
SameSite=Lax. Timing equalization on unknown emails. `password_hash` never in any
response; no session token in any body.

## 7. Authorization / IDOR results — PASS

Two-user (A/B) cross-user matrix asserted **404** (no existence leak) for: plant
(get/state/patch/delete/list scoping), simulation on foreign plant, telemetry
(current/history/stream), foreign search, foreign investigation run, and — Part 9 —
foreign analysis, failure, scenario, history item, report and reverification.
`owner_id` is never accepted from request bodies (server assigns session user).

## 8. Database results — PASS

Isolated per-test SQLite; user uniqueness; ownership FKs; cascade plant delete; PATCH
consistency guard rolls back (state unchanged on rejected update); analysis transaction
commit + failure marking; interrupted-run reconciliation. Static scan: **no raw SQL, no
`text()`/f-string executes, no user-controlled SQL strings, no hard-coded credentials**
in `app/` (all access via SQLAlchemy ORM). No `*.db` file tracked.

## 9. Simulator results — PASS

See §3. Highlight: identical inputs ⇒ identical full result documents; seeded unsafe
region (cooling loss crossing 150 °C limit) reproduced deterministically; delayed
shutdown fires at crossing + configured delay (grid-resolved re-integration).

## 10. Safety / safeguard results — PASS

Statuses, boundaries, band semantics, safeguard timing and prevented/too-late verdicts
all match ARCHITECTURE §18; timestamps derive from trajectory data, never invented.

## 11. Scenario search results — PASS

Sweep/refinement/sensitivity/combinations; budgets enforced **before** compute; request
may only tighten limits (loosening ⇒ 422, never silent clamp); non-monotonic brackets are
densified, not bisected; identical requests ⇒ identical evidence documents.

## 12. AI / provider / agent results — PASS (mocked); real inference BLOCKED

Provider: URL validation (https-or-loopback), bounded transient-only retries, error
vocabulary, key unwrapped once and never logged/echoed. Agent: bounded loop (steps,
model calls, simulations, tokens, wall clock) with reported stop reasons; two consecutive
refusals stop the run; tool layer re-validates every argument against strict schemas;
9-tool allowlist with no shell/eval/exec/SQL/file access; oversized tool payloads rejected;
prompt-injection strings are recorded, never obeyed. **Real Nebius inference: BLOCKED** —
`Backend/.env` contains no `NEBIUS_*` variables (names-only inspection).

## 13. Security audit findings

- Rate limiting: separate buckets (global, auth signup/login, simulation, search, AI
  per-user, analyses per-user) — 429 + Retry-After verified.
- Headers on every response (`test_security_headers.py`): nosniff, DENY framing,
  CSP `frame-ancestors 'none'`, Referrer-Policy, Permissions-Policy, HSTS production-only.
- CORS strict allowlist, credentials allowed, never `*` (`test_cors.py`).
- Debug: forbidden in production config; `/docs`+`/openapi.json` disabled in production.
- Errors: 500 ⇒ generic envelope; no traceback/SQL/path/secret leakage (tested).
- Body-size guard: 413 before parse.

## 14. Secret-scan result — CLEAN

Full-history scan (`git log --all -p`) for key/token/private-key/connection-string
patterns: only **test fixtures** (diceware example password in `Backend/tests/*`;
deliberately fake `sk-live-1234567890abcdefghijklmnop` used to prove redaction).
No real credential ever committed ⇒ **no rotation required**. `Backend/.env` (present,
untracked, gitignored) and `*.db` files are untracked; only `.env.example` files tracked.

## 15. Dependency audit — CLEAN

- `npm audit` (prod and incl. dev): **0 vulnerabilities**.
- `pip-audit` on the backend venv: **No known vulnerabilities found**.
- No unused packages identified in either manifest (every dep traced to runtime use;
  `httpx` was promoted to runtime in Part 8). No duplicate packages. No breaking major
  upgrades required.

## 16. Bugs found

| ID | Severity | Component | Reproduction | Root cause | Status | Regression test |
| --- | --- | --- | --- | --- | --- | --- |
| BUG-01 | S3 | Backend tests / config | Run full suite on a machine that has a real `Backend/.env` ⇒ `test_get_settings_fails_with_field_names_only` fails (DID NOT RAISE SystemExit) | `Settings` reads `env_file=".env"`; the test cleared process env but the loader re-supplied `JWT_SECRET` from the local file — environment-dependent test, product behaviour correct | **FIXED** (`c543865`) | same test, now loader-isolated; full suite re-run: 326 passed |
| BUG-02 | S3 | Git discipline / Part 9 frontend | `git status` showed 12 Part 9 frontend files untracked although docs recorded Part 9 complete | Part 9 frontend was never committed after implementation | **FIXED** (`df84ee5`) | verified before landing: lint 0 warnings, 65 unit tests, strict build green |

## 17. Files changed

- `Backend/tests/test_config.py` (BUG-01 fix)
- `frontend/src/api/analyses.ts`, `frontend/src/hooks/useAnalyses.ts`,
  `frontend/src/types/analysis.ts`, `frontend/src/pages/{AnalysisNewPage,AnalysisLivePage,
  FailureDetailPage,HistoryPage,InvestigationPage,ReportPage,ReverifyPage,SafeguardsPage}.tsx`,
  `frontend/src/routes/index.tsx` (BUG-02 landing)
- `docs/QA_TEST_PLAN.md`, `docs/QA_PART1_REPORT.md` (this document)

## 18. Git commits created

1. `df84ee5` — feat(analysis): land the Part 9 analysis workspace pages
2. `c543865` — test(config): isolate the missing-JWT_SECRET startup test from a local .env
3. *(this docs commit — see log)*

## 19. Remaining risks

1. Real Nebius/Nemotron inference unverified (BLOCKED on API key) — hackathon integration
   rule 23 depends on it; nothing about the real model is claimed.
2. In-memory rate-limit state is per-process (known limitation; revisit for multi-worker
   production deployment).
3. UI/E2E/UAT/performance/viewport/accessibility deliberately deferred to **QA Part 2**.
4. Firefox/Safari browser matrix to be assessed in Part 2 (Chromium available here).

## 20. READY FOR QA PART 2?

**READY** — Part 1 exit criteria met: all CRITICAL suites green (326 + 65), auth/IDOR pass,
simulator/safety/search deterministic tests pass, agent security tests pass, no S0/S1
defects, no leaked active credentials, suite reproducible; the only blocked item (real
provider inference) is external and explicitly marked BLOCKED.
