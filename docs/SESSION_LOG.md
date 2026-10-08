# SafeFlux — Session Log

**Rule:** Keep newest checkpoint at the top. Record real decisions and do not rewrite history merely to make the project appear cleaner.

---

# Current Checkpoint — 2026-10-08 · VISUAL TRANSFORMATION COMPLETE (UI REDESIGN)

**Status:** 🟢 The product was not rebuilt — it was re-skinned, re-laid-out and given motion
without touching a single backend contract. Frontend builds green, `npm run lint` clean,
87 frontend unit tests passing, backend suite still passing (326 tests, exit 0). The whole
engineer workflow was re-walked in the browser after the redesign: signup/login, plant,
dashboard, monitor (real SSE run), analysis creation (real `POST /analyses/run` →
`status=complete`, 9 recorded events), failure detail, root cause, safeguards, re-verify,
history, report.
**Project:** SafeFlux — Autonomous Process-Safety Hunter
**Track:** Best Apps & Agents

## What the visual transformation changed

### Design system (commit `783b010`)

Dark-first instrument language in `src/index.css`: near-black surface stack
(`--color-void/graphite/panel/surface/surface-2/surface-3`), thin technical borders
(`edge`, `edge-strong`), one electric-cyan accent (`--color-accent #00d9ff`) with a violet
secondary reserved for the AI layer, and safety colours that mean exactly one thing
(`--color-safe/warn/crit`). Utilities `grid-bg`, `panel`, `panel-inset`, `stat-num`
(mono tabular numerals), `glow-accent`, `glow-crit`. Radii stay restrained (6–10 px). The
React Flow attribution is quietened but always legible.

### Shell, pages, motion, 3D

| Work | Commit |
| --- | --- |
| Control-room shell: top status header + labelled sidebar rail + system block | `5b2cd86` |
| Dashboard as a command centre (status row, graph, instruments, findings) | `e321355` |
| Live monitor: process & safety panel, instrument tiles, per-series chart tabs with limit/violation markers | `4a1111d` |
| Analysis creation ("What changed?") + live investigation stage rail from recorded events | `1194bb3` |
| Evidence screens: failure detail, root cause, safeguards on one time axis, split re-verify, history, report tabs — with the recorded-sequence reveal | `b3cea08` |
| Landing digital twin (Three.js) + premium auth surfaces + plant wizard on tokens | `a07c8ff` |
| Status colour unified on `safe/warn/crit`; React Flow attribution restored | `7338fb3` |

### Three.js (the only new runtime dependency)

`src/three/reactorTwin.ts` builds a stylized reactor skid (tank → pump → vessel with cooling
coils, pressure ring, outlet, status beacon). `src/components/TwinCanvas.tsx` loads it through
a dynamic `import()` **after first paint**, starts the loop only while the canvas intersects
the viewport and the tab is visible, simplifies geometry below 560 px, gives
`prefers-reduced-motion` a single static frame, and disposes every geometry/material/renderer
on unmount. WebGL unavailable → a labelled static SVG schematic, never a fake animation. The
twin is decoration of the *process shape* only; it carries no numbers and mirrors just the
health probe the page already displays.

### Motion

GSAP remains the only animation library. Pure, unit-tested planners decide what may move
(`motion.ts`, `failureSequence.ts`, `agentStages.ts`, `routeTransitionPlan.ts`); hooks apply
them inside `gsap.context()` and revert on unmount. `prefers-reduced-motion` collapses the
plans to static — no flow, rotor, pulse, reveal or page transition. Page transitions stay
200–500 ms and never delay navigation.

## Verification recorded for this checkpoint

- `npm run build` (tsc -b + vite) green; `npm run lint` 0 warnings / 0 errors; `npm run
test:unit` 87/87; backend `pytest` exit 0 with no failures.
- One-viewport audit in the real browser: `/dashboard`, `/plant`, `/monitor`, `/analysis/new`,
  `/analysis/:id/live`, `/investigation`, `/safeguards`, `/reverify`, `/history`,
  `/reports/:id`, `/failures/:id` all report `document.scrollHeight <= innerHeight` at
  1366×768, 1280×720, 1024×768 and 375×812; 1600×900, 1440×900 and 1920×1080 checked on the
  densest screens. Login and signup keep their whole form inside one viewport at 1280×720.
- Console clean on every visited route (one deprecated `THREE.Clock` warning and the React
  Flow attribution warning were fixed, not silenced).
- Backend/business logic untouched: no route, schema, simulator equation, safety rule or
  auth contract changed anywhere in this work.

## Honest limitations of this checkpoint

- Screenshots could not be captured in this environment (the preview webview reported no
  compositing frames), so layout claims rest on DOM measurements and accessibility-tree
  snapshots rather than images.
- Reduced motion is verified by unit tests over the planners and by code inspection
  (one-frame render, static plans); it was not emulated in the browser session.
- `src/search/SearchControls.tsx` and `src/search/SearchResults.tsx` still carry the
  pre-redesign styling. They are **not imported by any route** (the Part-9 workspace renders
  its own search context, and the server drives the bounded search), so they are unreachable
  dead mirror code. They were left in place because deleting documented Part-7 modules is an
  architecture decision, not a visual one; `src/pages/ComingSoon.tsx` was deleted, since the
  Part-9 `/plant` route replaced it and nothing referenced it.

---

# Checkpoint — 2026-10-07 · PART 9 IMPLEMENTED, END-TO-END WORKFLOW COMPLETE

**Status:** 🟢 Part 9 (autonomous analysis, safeguard and re-verification UX) implemented and
test-verified: backend 326 tests passing (31 new), frontend builds with lint/typecheck green
and 65 unit tests passing. The Part 8 real Nebius inference remains pending `NEBIUS_API_KEY`
— nothing about the real model has been claimed.
**Project:** SafeFlux — Autonomous Process-Safety Failure Hunter
**Track:** Best Apps & Agents

## What is complete (Part 9)

### The rule that shaped everything

One analysis is one bounded, autonomous run over an owned plant, and every page reads that
run's **recorded reality**. Each event row is written by the code that actually did the work,
with the real elapsed time; nothing is replayed from timers and no event exists that no code
produced. The UI never pretends the agent is active.

### Backend (7 commits)

- `app/analyses/` — constants (kinds, statuses incl. honest `interrupted`, 12 event kinds,
  storage bounds, fixed verdict language), `events.py` (EventRecorder with injected clock),
  `interpret.py` (deterministic goal → interpreted change), `runner.py` (the real pipeline:
  understand → map → plan → run → observe → refine → find violations → counterfactuals →
  safeguard check → optional AI summary), `service.py` (transaction + duplicate 409 + failure
  marking), `pipeline.py` (failure-detail / reverify / report builders), `summary.py`
  (optional narration stored separately from evidence), `pdf.py` (dependency-free, escaped).
- `app/api/routes/analyses.py` — the 9 endpoints; every id through `get_owned_or_404`;
  rate-limited per user; goal sanitized before storage; mitigation allowlist with bounds.
- Tests: 16 unit + 15 endpoint (full workflow with the real simulator, no-failure language,
  events cursor, 409 duplicate, per-user rate limit, sanitization, mitigation bounds, IDOR
  across analysis/failure/scenario/history/report/reverify, history scoping).

### Frontend

`/analysis/new` (goal → interpreted change → FIND HIDDEN RISKS, duplicate-safe),
`/analysis/:id/live` (cursor-polled real events + step navigator), failure detail
(trajectories, limits, first violation, peaks, safeguard events), investigation
(SIMULATION EVIDENCE vs AI EXPLANATION), safeguards (trigger/response/violation in the
required language), reverify (mitigation form → before/after), `/history` (paginated),
`/reports/:id` (six tabs + PDF download). Build, lint, typecheck green.

### Bugs the tests caught (and the fixes)

- EventRecorder used the wall clock instead of the injected clock (deterministic tests).
- The analysis service never committed — the run and its events would have been lost.
- The runner's lazy evaluator builder was never invoked.
- `make_case` required enum keys; three call sites passed raw strings.
- The failure page re-simulates from the plant's *current* configured limits (live source of
  truth), not a stored copy.

### Remaining

Part 10 (hardening/deployment/audit) and the one controlled real Nebius inference.

---

# Previous Checkpoint — 2026-10-06 · PART 8 IMPLEMENTED, REAL INFERENCE PENDING KEY

**Status:** 🟡 Part 8 (hybrid Nebius/Nemotron investigation agent) implemented, documented and
verified against a scripted provider — the one controlled **real** inference has not run
yet, because `Backend/.env` does not exist on this machine.
**Project:** SafeFlux — Autonomous Process-Safety Failure Hunter
**Track:** Best Apps & Agents

## Part 8 — pre-flight contract (answered before any provider code)

| Question | Answer |
| --- | --- |
| Provider | Nebius Token Factory (OpenAI-compatible inference API) |
| API key required | yes — for the AI step only; every other part works without one |
| Environment variable | `NEBIUS_API_KEY` |
| Base URL variable | `NEBIUS_BASE_URL` |
| Model variable | `NEBIUS_MODEL` |
| Purpose | investigation **planner and narrator** — never a source of numbers or verdicts |
| Backend or frontend | **backend only**; the frontend bundle contains no provider reference |

**No model id is hard-coded.** The account's own catalogue
(`GET {NEBIUS_BASE_URL}/models`) is the source of truth and `NEBIUS_MODEL` is set from it, so a
model documented publicly but absent from the account cannot be silently substituted.

## What is complete (Part 8)

### Division of labour (the whole point)

**Nemotron** decides *what deserves investigation* — which variable, which action, what to
look at next — and explains the evidence afterwards. The **deterministic search (Part 7)**
decides every numeric test value and where the boundary is; the **simulator (Part 4)** decides
what the process does; the **safety engine (Part 5)** decides the threshold result. Every
result carries the sentence that states this, so the model can never be mistaken for the
source of physical truth.

### Modules (14 commits)

- `app/ai/constants.py` — hard ceilings, `AgentState`, `AgentStopReason`,
  `ProviderErrorCategory`, `GuardVerdict`, the log allowlist/denylist, `AI_DISCLAIMER`.
- `app/ai/schemas.py` — strict `AgentDecision` (closed action enum, `TOOL_FOR_ACTION`,
  allowlisted `variables`, bounded `arguments`, `extra="forbid"`), `AgentExplanation`,
  `ToolResultRecord`, `InvestigationBudgetState`, `InvestigationResult`.
- `app/ai/security.py` — untrusted-text sanitizer, 8 named injection patterns, marker wrapper
  that survives a forged closing marker, secret redaction (JWT/bearer/`sk-…`/long tokens, with
  exemptions so a plain UUID is not mangled), allowlisted `log_event`.
- `app/ai/prompts.py` — pure prompt builders; untrusted text is always wrapped as data.
- `app/ai/parsing.py` — string-aware balanced-JSON extraction, strict decision parse (invalid
  output is *rejected*, never repaired into a guess), curated value-free explanation parse.
- `app/ai/provider.py` — `validate_base_url` (https or loopback only), `ProviderConfig` from
  settings (the `SecretStr` key is unwrapped exactly once), bounded retries for transient
  failures only, `ProviderError.to_dict()` as a loggable vocabulary.
- `app/ai/tools.py` — the nine allowlisted tools (`get_plant_configuration`, `get_current_state`,
  `get_safety_limits`, `get_recent_history`, `run_simulation`, `run_scenario_search`,
  `compare_scenarios`, `get_failure_details`, `check_safeguards`), each with its own strict
  argument model, plus `ToolBudget` charged *before* work, `call_tool` re-validating everything
  and rejecting oversized payloads by raw handler output size.
- `app/ai/guards.py` — `InFlightGuard` releasing on every exit path.
- `app/ai/machine.py` — `InvestigationAgent.run`: explicit state machine, budget checked before
  each iteration, refusals kept as evidence, two consecutive refusals stop the run, the goal
  text is scanned for injection by the machine itself.
- `app/ai/service.py` + `deps.py` — provider + budget + tools + plant context behind
  `get_ai_service`; an unconfigured deployment returns `not_configured` without touching the
  network.

### API, budgets and rate limiting (commits 15–17)

- `GET /api/v1/investigations/capabilities` — provider state, tool catalogue, allowlist,
  resolved bounds.
- `POST /api/v1/investigations/run` — verified session, `get_owned_or_404` (cross-user → `404`),
  strict request schema, own rate-limit bucket keyed by **authenticated user** (not IP), and
  `409` for a duplicate click while a run for that `(user, plant)` is in flight.
- `AI_MAX_STEPS`, `AI_MAX_MODEL_CALLS`, `AI_MAX_SIMULATIONS`, `AI_MAX_TOKENS`,
  `AI_TIMEOUT_SECONDS`, `AI_PROVIDER_TIMEOUT_S`, `AI_PROVIDER_MAX_ATTEMPTS`, `AI_TEMPERATURE`,
  `AI_RATE_LIMIT_RUNS`, `AI_RATE_LIMIT_WINDOW_SECONDS` — each clamped at startup to an engine
  ceiling by per-field validators, so a bad environment variable cannot uncap a run.
- `httpx` promoted from a test-only to a runtime dependency (it was already the HTTP client in
  use); nothing new was installed.

### Tests (commits 18–19)

`test_ai_security.py`, `test_ai_parsing.py`, `test_ai_provider.py`,
`test_ai_tools.py`, `test_ai_agent.py`, `test_investigations_api.py` — valid structured output,
invalid output, malformed JSON, tool rejection, budget exhaustion, provider down / rate limit /
timeout mapping, max agent steps, prompt injection, cross-user analysis, duplicate run. The
provider is the only thing faked (`ScriptedProvider` records every call, prompt and system
prompt); the simulator, safety engine and search engine inside the tools are the real ones.

### Real bugs found and fixed while building Part 8

1. Secret redaction missed a bare `sk-live-…` credential — added a token-shape pattern and
   exemptions so identifiers stay readable.
2. `compare_scenarios` silently sorted caller-supplied values, which could sign-flip the
   comparison — it now returns an explicitly ordered `lower`/`upper` pair.
3. `check_safeguards` was missing from the expensive-action set, so it was not budget-charged.
4. Pydantic copies list fields, so writing the trace *after* building the result document
   dropped the `DONE` state — the trace is now written before construction.
5. An injected provider factory was blocked by the not-configured gate, which made the whole
   mock-test path unreachable; `gate_on_settings` separates the two concerns.
6. The oversized-payload guard was unreachable because it measured the request rather than the
   raw handler output — it now measures the handler's bytes.

### Checks

- Backend: **295** pytest tests passing (exit 0), of which 111 are Part 8.
- A small operator probe (`Backend/scripts/nebius_probe.py`) closes the gap between
  "implemented" and "the real inference can run": it lists the Nemotron-family models the
  account can actually call (`models`), verifies the configured key/URL/model triple with one
  tiny completion (`check`), and runs one controlled investigation for an owned plant through
  the same `InvestigationService` the endpoint uses (`investigate`). The key is read only from
  `Backend/.env` — never a command-line argument, never printed — so it cannot leak into shell
  history or a transcript. The probe is tested against a local OpenAI-compatible fake on
  loopback, which also proves the https-or-loopback transport rule with real HTTP.
- Frontend: **65** node tests still passing, `oxlint` clean, `tsc -b && vite build` OK.
- Part 8 adds **no frontend module**: `/analysis/:id/live` still renders its placeholder and the
  live investigation UX belongs to Part 9. Nothing in Part 8 is claimed as a UI feature.
- Provider secrets: `Backend/.env` is git-ignored and absent; only `.env.example` is tracked and
  its three AI values are empty. No key appears in any tracked file or in Git history.

### Git

Part 8 is 23 commits on `main` (19 implementation/test, 2 documentation, the operator probe and
its tests), each a coherent change with the required trailer, no push.

## Blocked

**The one controlled real inference cannot run yet.** `Backend/.env` does not exist on this
machine (checked repeatedly: the only env files present are `Backend/.env.example` and
`frontend/.env.example`, and the AI values in the example are empty). No key was ever pasted
in chat and no key is fabricated here. When the key is placed in `Backend/.env`, the remaining
work is three commands (`python -m scripts.nebius_probe models`, then `check`, then
`investigate`) — and the key must **not** be pasted into the chat.

## Next action

1. User creates `Backend/.env` with the three variables (key never in chat).
2. List `GET {NEBIUS_BASE_URL}/models`, filter for the Nemotron family, and record the exact
   **account-eligible** model id in `NEBIUS_MODEL` only.
3. Run one controlled investigation through `POST /api/v1/investigations/run` against a plant
   with a seeded weakness, and confirm a real model decision, a real tool call and real
   deterministic evidence — then Part 8 is genuinely complete.
4. Part 9 — live investigation / reverify / report UX.

---

# Checkpoint — 2026-10-06 · PART 7 COMPLETE

**Status:** 🟢 Part 7 (Deterministic Scenario Search) implemented, tested and verified live  
**Project:** SafeFlux — Autonomous Process-Safety Failure Hunter  
**Track:** Best Apps & Agents

## What is complete (Part 7)

### The promise: search finds the danger, not the engineer

The engineer chooses a **variable and a resolution**; the search chooses the values. Pipeline,
with nothing else in it: **Search → Simulator → Safety Engine → Evidence**. No AI is involved
anywhere in this part, no provider is contacted, and no API key is required.

### Core engine (commits 1–13)

- `app/search/variables.py` — the **allowlist**: a name selects a row of a fixed table that
  maps it to a typed simulator effect (process fault, safeguard delay, sensor fault). No
  `eval`, no `exec`, no generated code, no shell anywhere in the package. Sensor variables are
  marked observation-only: they change reported values, never the true trajectory.
- `app/search/budgets.py` — two layers: `SearchLimits` (the plan) and `SearchBudget` (the
  runtime counter charged *before* every simulation). Ceilings: scenarios, combinations,
  refinement depth, timeout, duration, time step, samples; refinement additionally capped by
  `MAX_REFINEMENT_EVALUATIONS` independent of depth.
- `app/search/sweep.py`, `monotonic.py`, `refine.py` — coarse sweep (safe end first),
  monotonicity classification, and **bisection only when monotonic**; otherwise the bracket
  is densified, because bisection on a non-monotonic series converges on the wrong point.
- `app/search/sensitivity.py`, `combinations.py` — one-at-a-time influence ranking and a
  bounded two-variable grid.
- `app/search/result.py` + `engine.py` — reproducible evidence document: counts (scenarios,
  safe, near-limit, safeguard, violation, failing), failure scenarios, boundary candidates
  with method/monotonicity/uncertainty, the search trace, budget usage, and the
  configuration/version block with `deterministic: true, ai_involved: false`.

### API and validation (commits 14–19)

- `GET /api/v1/searches/capabilities` publishes the allowlist, modes and effective budgets;
  the UI renders its controls from this, so a variable cannot become searchable by accident.
- `POST /api/v1/searches/run` requires a verified session, loads the plant with
  `get_owned_or_404` (cross-user → 404), validates the whole plan **before any compute**, and
  is rate-limited on its own bucket (the tightest in the API: one request runs many
  simulations).
- Per-request budgets may only **tighten** the configured limits; anything larger is a `422`
  rejection rather than a silent clamp.
- Small security fix found by the API tests: unknown field *names* were being reflected back
  in validation errors. They are now reported against the body (`errors.py`), so no submitted
  name or value is echoed, while real field paths stay intact.

### Frontend (commits 20–21)

- `/analysis/new` replaced the Part 6 coming-soon placeholder with the one-viewport search
  workspace: plan editor (plant, preset, method tabs, variable + resolution, advanced budgets)
  beside a tabbed, paginated evidence viewer (summary counts, failures with filters,
  boundaries, influence ranking, trace). Narrow/short viewports switch panes via tabs.
- `src/search/plan.ts` is a pure mirror of the server bounds: `draftIssues()` explains every
  rejection before submitting, presets are filtered against the capabilities payload, and
  parsing can never put `NaN` in a payload. Run is disabled while a run is in flight, so one
  click is one search.
- Presets are starting *plans*, never verdicts — a preset that finds nothing is an honest
  result.

### Live verification (real servers, real data)

- Backend on `:8000` and Vite on `:5173`, a signed-up user, one configured plant, then a
  cooling sweep from the UI: **15 scenarios → 12 safe, 2 safeguard, 1 violation, 1 boundary**
  (`cooling_factor` 1.0 … 0.125 safe, 0.0 violation with a 162.5 °C peak against the 150 °C
  limit). Refinement: *last safe 0.0957, first unsafe 0.0938, bisection, ±0.0020*.
  The same request through the API returned byte-identical evidence except for `elapsed_s`.
- The seeded unsafe region was found **without telling the search where it is**.

### Checks

- Backend: `184` pytest tests passing (24 engine + 22 API for Part 7 alone).
- Frontend: `65` node tests passing, `oxlint` clean (0 warnings), `tsc -b && vite build` OK.
- No new dependency was added in Part 7; no secret, key or generated code exists in the part.

### Git

Part 7 landed as 23 commits on `main` (21 code and test commits, then these two documentation
commits), each one coherent change with the required trailer and no push.

## Next action

Part 8 — Nebius Token Factory + NVIDIA Nemotron investigation agent. **Before writing any
provider code:** confirm provider / API key / env vars / base URL / model variables / purpose /
backend-only, confirm an eligible Nemotron model in the actual account, and request the API
key explicitly (rule 22). AI decides *what deserves investigation*; the deterministic search
from Part 7 still decides the values.

---

# Checkpoint — 2026-10-05 · PART 6 COMPLETE

**Status:** 🟢 Part 6 (Engineering Dashboard + Visualization) implemented and tested  
**Project:** SafeFlux — Autonomous Process-Safety Failure Hunter  
**Track:** Best Apps & Agents

## What is complete (Part 6)

### Dependency decision

- Added `recharts@^3.10.1` and `gsap@^3.15.0` — both used (chart workspace; process motion).
- **Three.js not installed:** a 3D scene would not add genuine value to a 2D
  P&ID-style diagram, so the optional dependency was deliberately skipped.
- No external API key required (rule 22 not triggered); `npm audit --omit=dev` → 0
  vulnerabilities.

### Frontend — real-data dashboard (`/dashboard`)

- `pages/DashboardPage.tsx` rebuilt on live data: owned plant list, plant detail and the
  current telemetry frame (react-query, 5s poll, `retry: false`), plus the health probe and
  the cached last safety verdict. No fixtures, no invented numbers.
- `dashboard/viewState.ts`: one pure function maps the inputs to
  `loading | offline | session-expired | error | empty | ready` with headline/hint, stream
  and safety tones and the motion decision — a single source of truth for every branch.
- `components/dashboard/MetricGrid.tsx`: the seven required metrics (temperature, pressure,
  feed flow, level, cooling, valve, pump), tone-coded against configured limits, labelled
  `telemetry` vs `configured`.
- `components/dashboard/FindingsPanel.tsx`: recent findings from the backend verdict with an
  explicit empty state; `ui/{StatePanel,StatusBadge,TabBar}` are shared primitives.
- `analysis/assessmentStore.ts` + `hooks/useAssessment.ts`: in-memory (non-persisted) cache
  of the last backend `SafetyAssessment` per plant — a cache of the backend's own verdict,
  never a client-side safety computation.

### Frontend — process graph + motion

- `components/plant/ProcessGraph.tsx`: animated **React Flow** graph
  (`Feed Tank → Pump P-101 → Reactor R-101 → Valve V-101 → Product Tank`) with **Heater**,
  **Cooling Jacket** and **Sensors** attached to the reactor via explicit top/bottom handles;
  units tone-coded from limits and live telemetry.
- `animation/motion.ts` (pure motion plan) + `animation/useProcessMotion.ts` (GSAP inside a
  `gsap.context()` that is `revert()`ed on unmount). Motion communicates state only:
  pipeline flow, pump rotation, warnings and critical transitions.
- `animation/useReducedMotion.ts`: `prefers-reduced-motion` makes the plan fully static
  (no flow, rotor, pulse or flash). Effects use transform/opacity.

### Frontend — strict one-viewport rule

- `layouts/AppLayout.tsx` pins the shell to `h-[100dvh]` and the content region no longer
  scrolls as a page; each view manages its own bounded region.
- `layout/viewport.ts` classifies by **width and height** (`mobile`/`tablet`/`laptop`/
  `desktop`); wide layouts show process + metrics/findings side by side, narrow or short
  layouts use `TabBar`s (dashboard: Overview/Process/Findings; monitor: Telemetry/
  Process & safety).
- `pages/PlantSetupPage.tsx` becomes a flex column whose fact grid and plant list are the
  only internal scroll regions. Tested sizes: 1920×1080, 1366×768, tablet, mobile portrait.

### Frontend — session expiry + telemetry chart

- `api/client.ts` + `api/sessionEvents.ts` + `auth/AuthProvider.tsx`: any `401` from a
  protected call emits one central `safeflux:session-expired` event; the auth provider drops
  the cached session so the guard redirects to `/login`, and `clearAssessment()` runs on
  sign-out. Login/session/logout probes are excluded to avoid redirect loops.
- `components/monitor/TelemetryChart.tsx` rebuilt on **Recharts** (Temperature / Pressure /
  Level / Flow tabs, near-limit + limit reference lines, 240-point downsample, animation
  off); the monitor records each run's backend verdict for the dashboard.

### Live verification (real browser, real backend)

Part 6 was verified end-to-end against a running backend and frontend, not only by unit
checks: signup → create plant → `simulations/run` → telemetry current/history through the
API, then the same path through the UI (sign in → dashboard → monitor → run → dashboard).
The dashboard rendered the smoke plant's real frame (`138.9 °C`, `near limit`) and the
recorded verdict appeared as `safeguard activated` with its findings; the monitor's verdict
panel reproduced the backend's safeguard timings exactly.

That pass found and fixed three real defects in the animated P&ID — all of which had still
passed `tsc`, `oxlint` and the build:

1. **Clipped units.** React Flow clamps zoom at 0.5, so the wide five-stage line could not
   fit the narrower column of a 1366×768 workspace and the outlet valve and product tank
   were cut off. Fixed with a lower zoom floor, slightly narrower cards, a wider graph
   column and a `ResizeObserver` re-fit (a resized window also kept a stale transform).
2. **Unreadable when fitted.** A horizontal line cannot be read in a tall narrow box, so
   the orientation is now chosen from the container it is given via a pure, unit-tested
   `chooseGraphOrientation` (horizontal while it clears a legibility floor, rotated else).
3. **Missing edges and no flow.** React Flow caches each node's measured size on the node
   object, so rebuilding nodes every render made it re-measure forever and drop the edges —
   which is what the monitor did for every streamed frame. Graph inputs are now stabilised
   on the displayed values, and the pipeline tween is re-applied when React Flow re-mounts
   its edges (otherwise the flow vanished on a layout change).

Measured after the fixes: 1920×1080, 1366×768, 768×1024 and 390×844 each report zero page
scroll, zero horizontal overflow and every graph node inside its canvas, on load and across
live resizes; the four main-flow edges carry an advancing `strokeDashoffset` while
telemetry is present and the pump rotor stays `none` while the pump is stopped.

### Tests

- New pure-module tests: `viewport`, `dashboardView`, `failure`, `motionPlan` (35 new) and
  `graphLayout` (5) — **51 total**.

## Fixes after live verification

- `frontend/src/layout/graphLayout.ts` + `frontend/tests/graphLayout.test.ts` (new).
- `frontend/src/components/plant/ProcessGraph.tsx`: responsive orientation, zoom floor,
  resize re-fit, stabilised graph inputs.
- `frontend/src/animation/useProcessMotion.ts`: pipeline re-applied on edge (re)mount.
- `frontend/src/pages/DashboardPage.tsx`: graph column is the wider of the two.

### Docs

- `README.md` (Part 6 status + sections, test counts, new deps), `ARCHITECTURE.md` §4/§5/§6/
  §19/§25, `SAFEFLUX_MASTER.md` §26 synced, this checkpoint.

## Tests run

- Backend: `python -m pytest -q -p no:warnings` → **139 passed** (28 Part 1 + 26 Part 2 +
  25 Part 3 + 21 simulator + 11 simulation API + 16 safety + 12 telemetry API). Unchanged in
  Part 6 — no backend code was modified.
- Frontend: `npm run test:unit` → **51 passed** (`node --test`); `npm run lint` → 0 warnings
  (oxlint); `npm run build` → `tsc -b` + `vite build` OK; `npx tsc -b` exit 0.
- Pure modules tested: viewport classification (desktop, short laptop, tablet, mobile,
  degenerate), graph orientation (including that a rotated line renders larger than the
  squashed one), dashboard view-state (all six statuses + tone/motion outputs), API failure
  classification (offline / session / unknown), the motion plan (reduced-motion → fully
  static), and the telemetry stream state machine.
- **Layout verified by DOM geometry in a real browser** at 1920×1080, 1366×768, 768×1024 and
  390×844 (scroll heights, overflow, node rects, applied transform). This is measurement,
  not an image diff — no screenshot or visual-regression pass is claimed.

## Security audit (Part 6 · rules 1–25)

- **Secrets/keys:** none in the frontend (rule 1); only the public `VITE_API_BASE_URL`.
  No external key required, so rule 22 was not triggered.
- **Routes/auth:** all three pages stay behind `ProtectedRoute`; frontend protection does not
  replace backend authorization, which is unchanged and owner-scoped.
- **Data integrity:** the dashboard reads only real, owner-scoped endpoints and surfaces
  failed/offline/expired states explicitly instead of rendering stale or invented data.
- **XSS:** React-escaped text only; no `dangerouslySetInnerHTML`; chart data is numeric.
- **Dependencies:** two added (`recharts`, `gsap`), both used; `npm audit --omit=dev` → 0
  vulnerabilities; no unused packages introduced. Live verification used a local smoke
  account and plant in a gitignored SQLite DB, and no external service was called.
- **Safety language:** the verdict shown is the backend's deterministic result with a
  simulation-only disclaimer; the AI never decides a status (rule 24 / MASTER §24).

## Next action

Part 7 — Scenario Engine + Boundary Search — then continue the build plan part by part,
running Debugging Duck after each part.

---

# Checkpoint — 2026-10-05 · PART 5 COMPLETE

**Status:** 🟢 Part 5 (Safety Engine + Telemetry) implemented and tested  
**Project:** SafeFlux — Autonomous Process-Safety Failure Hunter  
**Track:** Best Apps & Agents

## What is complete (Part 5)

### Backend — safety engine (`app/safety/`)

- **Statuses + thresholds** (`findings.py`, `constants.py`): `SafetyStatus`
  (SAFE / NEAR_LIMIT / SAFEGUARD_ACTIVATED / VIOLATION), a configurable near-limit band
  (default 0.9, clamped 0.5–1.0), `SafetyFinding` (type, status, severity, timestamp,
  measured value, limit, near-limit, scenario id) and `SafetyAssessment` roll-up.
- **Classifier** (`evaluator.py`): reads simulator series + events and classifies each of
  temperature / pressure / level. Actual exceedance → VIOLATION; a trip kept within limit by
  the applied guard → SAFEGUARD_ACTIVATED; near-limit band → NEAR_LIMIT; else SAFE.
- **Safeguard timing** (`safeguards.py`): per high alarm and the emergency shutdown, records
  trigger / response / violation times and whether the modelled response *prevented* the
  violation or was *too late*.
- **Alarm-driven assessment** (`assess.py`): the shutdown is assessed with its trip driven
  by the high-alarm setpoint (`near_limit_fraction · limit`) via a new default-1.0
  `SafeguardSettings.trip_fraction` on the simulator, so prevention is physically
  reachable; a too-long delay still reports *too late*.
- **Integration** (`app/api/routes/simulations.py`): `POST /simulations/run` now returns
  `{result, safety}` and feeds telemetry; the near-limit fraction is per-request or
  `SAFETY_NEAR_LIMIT_FRACTION`.

### Backend — telemetry (`app/telemetry/`, `app/api/routes/telemetry.py`)

- **Frames + bounded store** (`frames.py`, `store.py`): one `TelemetryFrame` per sample
  (true values vs observed sensor values kept separate), a cheap per-frame status from the
  near-limit band, and a thread-safe `CurrentStateStore` retaining only the latest frame
  plus a bounded per-plant history under a bounded plant count.
- **Service** (`service.py`): ingests a result and replays stored frames; counts every
  stream connection against total / per-plant / per-user limits and releases the slot in a
  `finally`.
- **Routes**: `GET .../telemetry/current`, `GET .../telemetry/history?limit=`, and
  `GET .../telemetry/stream` (SSE, finite deterministic replay ending in `complete`), all
  authenticated and owner-scoped with bounded history and pre-open connection limits.
- **Config** (`config.py`, `.env.example`): `SAFETY_NEAR_LIMIT_FRACTION`, `TELEMETRY_*`
  budgets and replay pacing knobs.

### Frontend

- **Live monitor** (`pages/MonitorPage.tsx`): one-viewport layout with plant/scenario
  selectors, deterministic safety verdict panel, process graph, telemetry cards and a
  dependency-free SVG chart with Temperature / Pressure / Level / Flow tabs.
- **Streaming** (`hooks/useTelemetry.ts`, `api/telemetry.ts`): hydrates bounded history then
  streams SSE frames, reconnecting with capped backoff.
- **Pure state machine** (`telemetry/streamState.ts`): frame merge by sequence (reconnect
  dedupe), bounded retention, lifecycle + backoff — unit-tested with the Node runner.

### Docs

- `README.md` (status, Part 5 sections, security baseline), `ARCHITECTURE.md` §13/§18/§19,
  `SAFEFLUX_MASTER.md` §26 synced, this checkpoint.

## Tests run

- Backend: `python -m pytest -q -p no:warnings` → **139 passed** (28 Part 1 + 26 Part 2 +
  25 Part 3 + 21 simulator + 11 simulation API + 16 safety + 12 telemetry API).
- Safety tests assert status and direction (weaker cooling is never classified safer), the
  configurable near-limit band, evidence fields, the worst-status roll-up, and safeguard
  timing where an early shutdown prevents the violation and a late one reports it.
- Telemetry tests cover current/history reads, bounded limits/retention, SSE replay
  completion, unauthenticated (401) and cross-user (404) access, the per-plant connection
  limit (429), and slot release on completion and early disconnect.
- Frontend: `npm run test:unit` → **11 passed**; `npm run lint` → 0 warnings;
  `npm run build` → tsc + vite OK.

## Security audit (Part 5 · rules 1–25)

- **Secrets:** no new external API key (rule 22 not triggered); `*.db`/`.env` still
  gitignored and the smoke DB was removed.
- **Access control:** telemetry current/history/stream all require a session and load the
  plant via `get_owned_or_404`; cross-user access returns 404 (tested).
- **Abuse/DoS:** SSE connections are hard-limited before opening (429 + Retry-After), the
  history window is bounded per plant and per query, and no request can grow memory
  unboundedly.
- **Input/XSS:** query limits bounded server-side; the frontend renders escaped text and
  uses no `dangerouslySetInnerHTML`; chart data is numeric only.
- **Determinism:** safety statuses and telemetry are computed by deterministic software; no
  RNG, and no LLM call per tick.
- **Dependencies:** none added — the chart is plain SVG and the unit tests use the Node test
  runner.
- **Safety language:** verdicts carry a simulation-only disclaimer and are never a claim
  about a real plant (rule 24 / MASTER §24).

## Next action

Part 6 — Engineering Dashboard + Visualization — then continue the build plan part by part,
running Debugging Duck after each part.

---

# Checkpoint — 2026-10-04 · PART 4 COMPLETE

**Status:** 🟢 Part 4 (Deterministic Process Simulator) implemented and tested  
**Project:** SafeFlux — Autonomous Process-Safety Failure Hunter  
**Track:** Best Apps & Agents

## Pre-work audit (docs vs code, Parts 1–3)

- OpenAPI paths (`/api/v1/auth/*`, `/api/v1/health`, `/api/v1/plants/*`) match the README
tables exactly; ARCHITECTURE §15/§16 match the models; **79/79** tests passed.
- One drift found and fixed in this part: `SAFEFLUX_MASTER.md` §26 still described the
project as "as of 2026-10-02 … next action: begin Prompt 1/10".

## What is complete (Part 4)

### Backend

- **Deps** (`requirements.txt`): `numpy==2.5.3`, `scipy==1.18.1`.
- **Constants** (`app/simulator/constants.py`): units, nominal equipment magnitudes,
  simulator/model version and the documented assumptions + limitations surfaced in every
  result.
- **Scenario + faults** (`scenario.py`): `Scenario`, `FaultSpec`, `SensorFault` data model;
  deterministic, RNG-free.
- **Compute budgets** (`limits.py`): `SimulationLimits` with sample-count and
  `validation_errors()` used before any integration.
- **Model** (`model.py`): `ProcessParameters` (pure), mass balance, gravity-driven outlet,
  heater/jacket cooling, energy balance with feed advection, level clamping, and a
  documented **pressure proxy**.
- **Fault injection** (`faults.py`): cooling degradation/loss, outlet restriction, valve
  stuck, feed increase, pump variation; `apply_sensor_faults` touches observed readings
  only.
- **Result** (`result.py`): columnar series, extrema, summary, events, metadata.
- **Engine** (`engine.py`): segmented `solve_ivp`, uniform sampling, observed-vs-true
  separation, grid-resolved delayed shutdown (one re-integration), events/extrema/summary.
- **API**: strict schemas (`app/schemas/simulation.py`) and authenticated
  `POST /api/v1/simulations/run` (`app/api/routes/simulations.py`) with owner-scoped plant
  loading, configurable budgets and a dedicated per-IP rate-limit bucket.
- **Config**: `SIM_MAX_DURATION_S`, `SIM_MIN_TIME_STEP_S`, `SIM_MAX_SAMPLES`,
  `SIM_RATE_LIMIT_RUNS`, `SIM_RATE_LIMIT_WINDOW_SECONDS` (+ `.env.example`).

### Docs

- `README.md` (status, Part 4 section, security baseline), `ARCHITECTURE.md` §13/§17,
  `SAFEFLUX_MASTER.md` §26 synced, this checkpoint.

## Tests run

- Backend: `python -m pytest` → **111 passed** (28 Part 1 + 26 Part 2 + 25 Part 3 +
  21 simulator + 11 simulation API).
- Simulator tests assert **direction**, not invented numbers: higher heating is not cooler,
  stronger cooling is not hotter, cooling loss crosses the temperature limit, greater outlet
  restriction never increases outlet flow, feed increase raises level, and combined
  feed + cooling degradation is worse in both dimensions.
- Repeatability: identical inputs produce byte-identical result documents; sensor faults
  leave the true trajectory unchanged; delayed shutdown fires `trip_delay_s` after the
  crossing.
- Budgets: over-duration, sub-minimum time step and over-sample requests are rejected with
  `422 VALIDATION_ERROR` and per-field details (no echoed values); the endpoint returns
  `429 RATE_LIMITED` with `Retry-After` past its bucket.
- Reproducible single scenario verified end-to-end through the API (baseline: 301 samples,
  final 58.94 °C; cooling loss crosses the 150 °C limit and shuts down at crossing + delay).

## Security audit (Part 4 · rules 1–25)

- **Secrets:** none introduced; no new external API key (rule 22 not triggered);
  `*.db`/`.env` remain gitignored.
- **Authorization:** the simulation route requires a session and loads the plant via
  `get_owned_or_404`; cross-user simulation returns 404 (tested).
- **Abuse/DoS:** hard duration/time-step/sample budgets enforced before integration, plus a
  dedicated per-IP simulation rate-limit bucket and the shared body-size guard.
- **Input:** strict `extra="forbid"` schemas, bounded fault counts, per-type parameter
  requirements; errors never echo submitted values (tested).
- **Determinism:** no RNG, no LLM; the numeric path is fully reproducible.
- **Dependencies:** 2 new pinned runtime deps (`numpy`, `scipy`), both used; no unused
  packages added.
- **Safety language:** results carry assumptions/limitations and are described as simulated
  behaviour under a simplified model — never certified.

## Next action

Part 5 — Safety Engine + Telemetry: classify simulated trajectories into
SAFE / NEAR_LIMIT / SAFEGUARD_ACTIVATED / VIOLATION, record `SafetyFinding` evidence, and
stream telemetry (SSE) to the frontend.

---

# Checkpoint — 2026-10-04 · PART 3 COMPLETE

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

# Checkpoint — 2026-10-08 (QA Part 2 — system/E2E/one-viewport/security validation)

**Status:** 🟢 QA Part 1 + Part 2 complete — release candidate PASS WITH WARNINGS
**Report:** [docs/QA_PART2_REPORT.md](QA_PART2_REPORT.md)

## What ran

- Part 1 regression first: backend **326 passed**; frontend **72 unit tests passed**; lint 0/0;
  `tsc -b && vite build` green.
- E2E-001 via real HTTP (fresh users): **28/28 in 11.3 s** — signup → plant → baseline simulation →
  autonomous analysis ("Increase production throughput by 30%.") → 9 violation findings → failure
  detail → counterfactuals → revertify → history → report + PDF (6.9 KB, `no-store`) → logout →
  401s. IDOR battery: 4× 404.
- Browser E2E on the live stack: full product walk including the 5-step plant wizard, live
  telemetry, real pipeline events, safeguard timings, reverify verdict, report + PDF download.

## Defects found and fixed (each with a regression test)

- **BUG-01 (S2, auth shell)** — sign-out left the authenticated shell mounted: `removeQueries` on the
  actively-mounted session query kept the observer's last result, so the provider stayed
  `authenticated`, `LoginPage` bounced `navigate('/login')` back to `/dashboard`, and every later
  request 401'd until a manual reload. Fixed by writing an explicit `null` via `setQueryData`
  (`frontend/src/auth/session.ts`), pinned by headless `QueryObserver` tests that reproduce the old
  stuck-authenticated behaviour. Commit `7c4f52d`.
- **BUG-02 (S2, analysis UI)** — deep-linking to a re-verification record's safeguards page crashed
  (`Cannot read properties of undefined (reading 'note')`): reverify documents have no `safeguards`
  section. Fixed with an optional-section view helper + explicit empty state linking to the parent
  analysis. Tests cover both stored document shapes. Commit `64fbb00`.

## One-viewport audit (live DOM geometry)

- 1366×768 — all eleven authenticated views (dashboard, plant, monitor, analysis/new, live,
  investigation, safeguards, reverify, failure detail, history, report): **0/0 page scroll, zero
  truly clipped elements**.
- 1920×1080 dashboard, 1280×720 dashboard+monitor, 1024×768 monitor, 768×1024 monitor, 390×844
  dashboard+monitor, 360×640 report: **all 0/0**.
- Only flagged "clipping" was React Flow's own pan/zoom layer, clipped by design.

## Failure / recovery drills

- Backend stopped mid-session → "Telemetry disconnected / No telemetry yet", no crash, no fabricated
  values; restart clears the state by itself. Cold load with the backend down fails closed to
  `/login` (documented rule).
- Session expiry mid-use → immediate `/dashboard → /login`, shell unmounts (BUG-01 mechanism).
- Concurrent duplicate analysis on one plant → 1× 200 + 2× 409 single-flight; auth limit measured
  exactly at the boundary (10× 401 then 429).

## Remaining warnings

- No hosted deployment exists (deployment validation BLOCKED); real Nebius/NVIDIA runtime inference
  BLOCKED in this environment (no key). 1600×900/1440×900 viewport cells inferred, not measured.
  React Flow attribution warning is cosmetic upstream noise.

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
