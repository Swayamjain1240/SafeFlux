# SafeFlux — QA Part 2 Report (System / E2E / UAT / Non-functional / Release)

**Date:** 2026-10-08
**Scope owner:** Final QA Part 2 of 2
**Companion artifacts:** [QA_TEST_PLAN.md](QA_TEST_PLAN.md) · [QA_PART1_REPORT.md](QA_PART1_REPORT.md)
**Verdict:** **APPROVED WITH WARNINGS** (no S0/S1 open; two S2 defects found, fixed and regression-tested)

---

## 1. Environment

| Item | Value |
| --- | --- |
| Backend | FastAPI + uvicorn on `http://127.0.0.1:8000` (Python venv, SQLite `Backend/safeflux.db`) |
| Frontend | Vite dev server on `http://localhost:5173` (React 19, TanStack Query v5, React Flow, Recharts, GSAP) |
| Browser | Chromium driven through the Freebuff preview bridge (live DOM geometry + network/console capture) |
| AI provider | No `NEBIUS_API_KEY` in this environment → the analysis pipeline ran its deterministic path (see §12) |
| Part 1 gate | Re-run first: backend **326 passed**, frontend **72 passed**, lint 0, `tsc -b && vite build` green |

No hosted deployment exists in this repository (no Vercel/Render/Fly/Docker config; README claims none).
Deployment validation was therefore performed as **production-configuration validation** (§11) and the
hosted-environment pass is marked **BLOCKED — no environment to test** (not PASS).

## 2. Test matrix (executed)

| Category | Result | Evidence |
| --- | --- | --- |
| Unit | **PASS** | Part 1 suite re-run (326 backend + 72 frontend) |
| Integration | **PASS** | Part 1 integration suites + live two-server integration |
| API | **PASS** | E2E-001 script 28/28 against the live stack |
| System | **PASS** | Browser walk of the complete product on real state |
| Functional | **PASS WITH WARNINGS** | §5 page matrix; BUG-01/BUG-02 found and fixed |
| End-to-end | **PASS** | §3 |
| UAT | **PASS** | §4 |
| Security | **PASS** | §11 |
| Performance | **PASS** | §9 |
| Reliability / recovery | **PASS** | §10 |
| Accessibility | **PASS WITH WARNINGS** | §8 (practical checks, no automated axe run) |
| Responsive / one-viewport | **PASS** | §6/§7 |
| Compatibility | **PASS WITH WARNINGS** | Chromium only in this environment; no Firefox/Safari pass |
| Deployment | **BLOCKED** | No hosted environment exists |
| Nebius/NVIDIA runtime | **BLOCKED — no key** | Part 8's operator probe used a local fake catalogue; deleted-key probe documented in SESSION_LOG |

## 3. End-to-end E2E-001

Re-run against the live stack with fresh users (11.3 s wall time):

`signup 201 (+ HttpOnly cookie, Secure only in production) → /auth/me → POST /plants 201 →
GET plant/state → POST /simulations/run (deterministic verdict) → POST /analyses/run 200 in 2.0 s
→ row complete with disclaimer → 9 pipeline events, monotonic cursor → result document → failure
detail (case feed_factor=3.3125, violations + peaks) → counterfactual rows → POST reverify 200 in
3.1 s (before/after document) → history paginated → report payload → report.pdf 200
(application/pdf, no-store, 6870 bytes, %PDF magic) → user B IDOR battery: 4× 404 → logout 200 →
protected calls 401.` **28/28 PASS.**

Browser E2E additionally walked the same flow through the UI (signup → plant wizard 5 steps →
dashboard → monitor live telemetry → analysis page → live event timeline → counterfactuals →
failure detail timeline → safeguard events → reverify verdict → history → report + PDF download →
logout → protected route).

## 4. UAT acceptance scenarios

| # | Criterion | Result | Evidence |
| --- | --- | --- | --- |
| A | Configure a process without internals | PASS | 5-step wizard, server-side bounds mirrored in UI |
| B | Describe an engineering change naturally | PASS | "Increase production throughput by 30%." accepted; interpreted, not parsed as code |
| C | Product investigates automatically | PASS | bounded search ran autonomously (9 violation findings, boundary refinement) |
| D | Unsafe claims backed by simulator evidence | PASS | every finding carries a deterministic case, peaks and limit violations |
| E | AI reasoning distinguishable from simulation evidence | PASS | evidence sections are labelled; AI explanation is a separate, validated field |
| F | Understand why a scenario failed | PASS | failure detail: trajectory vs limit, first violation, timeline |
| G | Counterfactual results support the causal explanation | PASS | restore-feed reverify used new simulations (before/after rows), not AI guesses |
| H | Safeguard timing inspectable | PASS | trigger/response/violation timestamps from the simulator |
| I | Mitigation tested and re-verified | PASS | mitigation allowlist + before/after document with required wording |
| J | Never certifies a real plant | PASS | disclaimers on landing/auth/report/PDF; revertify verdict scopes claims to "tested simulation scenarios" |

## 5. Functional results

| Feature | Result |
| --- | --- |
| Landing, signup (2-step), login, logout, session persistence | PASS (logout bug fixed, §13) |
| Protected routing + deep links (`/dashboard`, `/analysis/:id/...`, `/reports/:id`) | PASS |
| Dashboard (tabs, plant selector, telemetry cards, process graph) | PASS |
| Plant creation wizard (5 steps) + persisted configuration | PASS |
| Monitor (live telemetry, charts, honest baseline verdict) | PASS |
| Analysis creation, status, live timeline (real events only) | PASS |
| Failure detail (trajectories + limits), counterfactual investigation | PASS |
| Safeguards (timings), reverify, history (paginated), report (6 tabs) + PDF | PASS (safeguards deep-link crash fixed, §13) |
| Empty / loading / error / offline states | PASS (§10) |

## 6. One-viewport matrix (live DOM geometry)

Method: real viewport resize; measure `documentElement.scrollHeight/Width` vs viewport and walk every
element for "overflow outside the viewport with no scrollable ancestor" (true clipping).

| Viewport | Views measured | Page scroll Y/X | True clipping |
| --- | --- | --- | --- |
| 1366×768 | dashboard, plant, monitor, analysis/new, live, investigation, safeguards, reverify, failure detail, history, report | 0 / 0 (all) | none |
| 1920×1080 | dashboard | 0 / 0 | none (only React Flow's own clipped pan layer — by design) |
| 1280×720 | dashboard, monitor | 0 / 0 | none |
| 1024×768 | monitor | 0 / 0 | none |
| 768×1024 | monitor | 0 / 0 | none |
| 390×844 | dashboard, monitor | 0 / 0, no horizontal overflow | none |
| 360×640 | report | 0 / 0 | none |

Not directly measured: 1600×900 and 1440×900 desktop cells — both are strictly wider **and taller**
than 1366×768 where every view passes, and the shell is height-driven (`h-[100dvh]`), so the risk is
assessed as low but is listed as a residual gap. Landing/log-in pages may scroll by design.

## 7. Mobile / responsive

- No horizontal overflow at 390×844 / 360×640; compact horizontal nav rendered (10 nav links).
- Buttons/inputs remain reachable; the wizard and report keep their step/tab structure.
- Active resizing between sizes produced no layout jumps or clipped panels; no 100vh-cut issues
  observed (the shell uses `100dvh`).

## 8. Accessibility (practical checks)

- Form fields have programmatic labels (`labels.length` present; dashboard unlabelled inputs = 0).
- Tabs expose `role="tablist"` / `role="tab"`; nav uses semantic links; dialogs and panels render
  text states (not colour-only): "safe", "Telemetry disconnected", "Safeguard response occurred
  after the simulated violation".
- Reduced motion: the animation plans are pure functions with unit coverage (`motionPlan.test.ts`) and
  the app consults `prefers-reduced-motion` via `useReducedMotion`.
- Not performed: automated axe/contrast audit and full keyboard traversal script. Neon-on-dark
  contrast for the primary accent was spot-checked visually; recorded as a warning, not a failure.

## 9. Performance (measured, local dev)

| Measurement | Value |
| --- | --- |
| `GET /health` ×20 concurrent (independent connections) | 20/20 200; p50 ≈ 0.21 s, max 0.22 s |
| `POST /signup` (argon2id m=65536,t=3,p=4) | ≈ 2.2 s |
| `POST /plants` | 0.04 s |
| `POST /simulations/run` (300 s scenario, 1 s step) | 0.11 s |
| `POST /analyses/run` (bounded autonomous pipeline) | ≈ 2.0 s |
| Failure detail | 0.18 s |
| `POST reverify` (3 deterministic re-runs) | ≈ 3.1 s |
| `GET report.pdf` | 6.9 KB, generated on demand |
| Frontend build | `tsc -b && vite build` ≈ 0.8 s; chunk-size warning >500 kB (analysis views are lazy) |

Notes: a uniform ≈2 s latency artifact appeared only inside the Python threaded harness and was
ruled out with independent-connection measurements — it is a harness artifact, not server
serialization. The Vite chunk warning is a bundle-size observation, not a load failure.

## 10. Failure / recovery drills

| Drill | Observed |
| --- | --- |
| Backend stopped mid-session | Dashboard stays stable: "Telemetry disconnected" / "No telemetry yet"; no fabricated values; no crash |
| Backend restarted | State clears by itself; health chip returns; no user action required |
| Cold load with backend down | Fails closed to `/login` (documented fail-closed rule; no misleading offline claim) |
| Session expiry mid-use (401 path) | Immediate `/dashboard → /login`, shell unmounts, no stale content |
| Refresh/deep-link on all analysis views | Correct state recovery |
| Concurrent duplicate analysis on one plant | 1× 200 + 2× 409 "An analysis for this plant is already running" (bounded single-flight) |
| Auth rate limit | Exactly at the configured boundary: 10× 401 then 429 |

## 11. Security final validation

| Check | Result | Detail |
| --- | --- | --- |
| Secrets in git history / tracked files | PASS | no `.env`, `*.db`, keys or certs tracked; only `.env.example` |
| Security headers | PASS | `x-content-type-options: nosniff`, `x-frame-options: DENY`, `referrer-policy: no-referrer` |
| CORS | PASS | allowed origin echoed with credentials; hostile origin → 400 with **no** `access-control-allow-origin` |
| Rate limiting | PASS | global 120/60 s, auth 10/60 s (measured 429), sim 30/60 s, search 20/60 s, AI 6/300 s, analysis 10/300 s |
| Password storage | PASS | argon2id hashes; no plaintext anywhere |
| Session cookie | PASS | HttpOnly; `Secure` only in production; server-side logout |
| Authorization / IDOR | PASS | cross-user plant/analysis/result/report/reverify all 404 through the API; UI has no cross-user surface |
| XSS / output handling | PASS | React-escaped rendering only; no `dangerouslySetInnerHTML`; PDF escapes text |
| Debug in production | PASS | `ENVIRONMENT=production` forbids `DEBUG`; `/docs` disabled in production (unit-tested) |
| Environment variables | PASS | validated at startup, failures name fields only, never values |
| Database | PASS | local SQLite, untracked, `*.db` ignored; no destructive tests against shared data |

## 12. AI evidence grounding & safety language

- The pipeline ran **without an AI provider in this environment**; every finding, timing and verdict in
  the reviewed documents came from the deterministic simulator + safety engine. No claim in the UI
  attributes physical truth to the model.
- Structured output validation, agent tool bounds and prompt-injection posture were covered in Part 1;
  the real-provider runtime call remains **BLOCKED (no key present)** — the honest status is recorded,
  not converted to PASS.
- Safety wording: no "guaranteed safe" / "certifies" claims found; required simulation-scoped wording
  present on the safeguards, revertify, report and PDF surfaces.

## 13. Defect register

| ID | Severity | Status | Component | Summary | Regression test |
| --- | --- | --- | --- | --- | --- |
| BUG-01 | S2 | **FIXED** (`7c4f52d`) | Frontend auth shell | Sign-out left the authenticated shell mounted (401 loop, stale values on screen); `removeQueries` does not clear an actively-mounted query observer, and `LoginPage` bounced the redirect back to `/dashboard` | `frontend/tests/authSession.test.ts` (headless `QueryObserver`, reproduces the stuck-authenticated behaviour) |
| BUG-02 | S2 | **FIXED** (`64fbb00`) | Analysis UI | Deep-linking to a re-verification record's safeguards page crashed with `Cannot read properties of undefined (reading 'note')` (reverify documents have no `safeguards` section) → error boundary | `frontend/tests/safeguardsView.test.ts` (both stored document shapes) |
| OBS-01 | S4 | Open (cosmetic) | Process graph | React Flow logs its attribution warning in console | n/a |
| OBS-02 | S4 | Accepted | Rate limiting | Limiter state is per-process memory (documented MVP scope) | n/a |
| OBS-03 | S4 | Accepted | Dashboard | Dashboard shows "No telemetry yet" until a monitor run — accurate, not a defect | n/a |

Reproduction of BUG-01 (root cause, library-level): with an active `QueryObserver`,
`queryClient.removeQueries(...)` leaves `data` present and `status: success` with **zero** refetches;
`setQueryData(key, null)` flips the derived status synchronously. The fix consequently writes an
explicit `null` and both sign-out and 401-driven expiry now redirect immediately.

## 14. Release blockers check

No active leaked credential · no plaintext password · no auth bypass · no IDOR · no code execution
path · no real actuation path · no simulator correctness failure · no false-SAFE from system error ·
no unbounded loop (single-flight 409 + budgets) · no broken critical E2E flow · no S0/S1 defect.
One-viewport holds across every measured viewport.

**Remaining warnings:** no hosted deployment exists to validate; real Nebius/NVIDIA runtime inference
is BLOCKED in this environment (no key); 1600×900/1440×900 cells inferred rather than measured;
automated accessibility audit not run; only Chromium tested.

## 15. Release recommendation

**APPROVED WITH WARNINGS — ready for the next phase (visual transformation) and hackathon packaging**
once a hosted environment and the real provider key are supplied for the two BLOCKED items.
