# SafeFlux — Master Project Context

**Project:** SafeFlux  
**Tagline:** Autonomous Process-Safety Failure Hunter  
**Hackathon:** Nebius × NVIDIA Global AI Hackathon  
**Track:** Best Apps & Agents  
**Owner:** Swayam Jain  
**Last updated:** 2026-10-04

---

## 1. Purpose

SafeFlux is an AI-assisted process-safety verification system for process and chemical engineers.

The user describes a proposed engineering change, for example:

> Increase production throughput by 30%.

SafeFlux then explores a digital process simulation, searches for hazardous operating combinations, identifies near-limit and unsafe conditions, verifies findings with deterministic simulation, investigates likely failure drivers using counterfactual tests, checks safeguard timing, and presents evidence for human review.

### Golden rule

> **AI searches for danger → Simulator proves it → Engineer decides.**

SafeFlux is a simulation and decision-support product. It is not an autonomous industrial controller and must never directly control a real plant.

---

## 2. Primary User

Primary users for the hackathon MVP:

- Process Safety Engineer
- Chemical Process Engineer

Future secondary users may include:

- Operations engineers
- Instrumentation/control engineers
- Plant safety teams
- Engineering review teams

The MVP is designed around one primary workflow:

> A process-safety engineer reviews a proposed process change before approving it.

---

## 3. Core Problem

After a process change, engineers may need to repeatedly:

- identify affected equipment,
- enumerate deviations and failure modes,
- try combinations of operating conditions,
- run calculations/simulations,
- check temperature/pressure/flow/level behavior,
- inspect safety thresholds,
- verify whether safeguards act early enough,
- identify approximate unsafe boundaries,
- compare counterfactual cases,
- document evidence.

SafeFlux automates repetitive scenario discovery and verification while keeping final engineering judgment with the engineer.

---

## 4. Locked Hackathon MVP

SafeFlux is not a universal plant simulator.

The MVP uses one intentionally constrained process:

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

### Main variables

- feed flow
- temperature
- pressure
- liquid level
- cooling effectiveness
- outlet valve position
- pump state
- heater power
- shutdown state/delay

### Initial failure modes

- cooling degradation
- complete cooling loss
- outlet restriction
- valve stuck/restricted
- feed-flow increase
- pump variation
- temperature-sensor failure
- pressure-sensor failure
- delayed emergency shutdown
- selected combinations of the above

### Explicitly out of scope for MVP

- arbitrary real P&ID ingestion
- real PLC/DCS actuation
- direct valve/pump control
- universal chemical thermodynamics
- plant certification
- replacing qualified engineers
- fully autonomous real-world safety decisions

---

## 5. Core User Workflow

```text
1. User signs up / logs in
          ↓
2. User creates or selects a plant
          ↓
3. SafeFlux loads base configuration/current simulated state
          ↓
4. Engineer describes a proposed engineering change
          ↓
5. AI interprets the change
          ↓
6. Affected equipment/variables are identified
          ↓
7. Scenario/search engine generates useful tests
          ↓
8. Deterministic simulator executes scenarios
          ↓
9. Safety engine evaluates limits/safeguards
          ↓
10. Near-limit regions are refined automatically
          ↓
11. Unsafe combinations/counterexamples are discovered
          ↓
12. Counterfactual simulations investigate likely causes
          ↓
13. Safeguard timing is checked
          ↓
14. Engineer reviews evidence
          ↓
15. Engineer may test a simulated mitigation
          ↓
16. SafeFlux re-verifies relevant scenarios
```

The user should not manually test hundreds of values.

---

## 6. Product Pages

The intended application includes:

- Landing page
- Signup
- Login
- Dashboard
- Plant configuration
- Plant view
- Live monitoring
- New analysis
- Live autonomous investigation
- Failure detail
- Root-cause/counterfactual investigation
- Safeguard verification
- Re-verification
- Analysis history
- Engineering report

Authenticated application screens must follow the one-viewport rule defined below.

---

## 7. Tech Stack

### Frontend

- React
- Vite
- TypeScript
- Tailwind CSS
- React Router
- React Flow
- Recharts
- GSAP
- Three.js only if it materially improves a small digital-twin view
- Axios
- TanStack Query

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- SQLite for local MVP
- PostgreSQL-ready persistence

### Simulation / engineering

- NumPy
- SciPy
- `scipy.integrate.solve_ivp` where appropriate
- NetworkX only where graph analysis materially helps

### Agentic AI

- NVIDIA Nemotron
- Nebius Token Factory
- LangGraph or a small explicit state machine
- Pydantic structured outputs

### Testing

- Pytest
- deterministic seeded benchmark scenarios

---

## 8. AI vs Deterministic Responsibility

### AI may

- interpret engineering changes,
- identify affected systems,
- select useful failure modes,
- choose investigation direction,
- decide when more focused testing is useful,
- explain deterministic evidence.

### Deterministic software owns

- physical/process state evolution,
- temperature,
- pressure,
- flow,
- level,
- safety limits,
- safeguard timing,
- pass/fail/near-limit classification,
- numerical search/refinement.

### Engineer owns

- final approval,
- real-world interpretation,
- plant operating decisions.

The LLM must never invent process numbers and present them as simulated evidence.

---

## 9. Boundary Hunting

SafeFlux should search toward useful boundaries rather than only generate random scenarios.

Example:

```text
Cooling 100% → SAFE
Cooling 70%  → SAFE
Cooling 50%  → NEAR_LIMIT
Cooling 40%  → VIOLATION
```

Then refine:

```text
45% → SAFE
42% → SAFE
41% → VIOLATION
```

Results must be described as simulated/observed boundaries under the selected model, never certified real-world safety limits.

---

## 10. Counterfactual Root-Cause Investigation

SafeFlux must not ask the LLM to simply guess the cause of a failure.

For a failing scenario:

```text
A + B + C → VIOLATION
```

Run controlled counterfactuals:

```text
without A
without B
without C
```

Evidence priority:

1. simulator result
2. safety/constraint violation
3. counterfactual result
4. sensitivity/boundary evidence
5. LLM explanation grounded in that evidence

---

## 11. Telemetry Boundary

Hackathon:

```text
Python Process Simulator
        ↓
Telemetry Service
        ↓
Current State Store
        ↓
SafeFlux
```

Future real product:

```text
Sensors
   ↓
PLC / DCS
   ↓
SCADA / Historian
   ↓
OPC-UA / MQTT / API
   ↓
Read-only SafeFlux Adapter
```

SafeFlux must never expose an LLM-driven path to real plant actuation.

---

## 12. Authentication and Access Control

SafeFlux includes:

- signup
- login
- logout
- session/current-user endpoint

Passwords must be hashed with Argon2 or bcrypt.

Prefer secure HttpOnly cookie-based authentication.

Private application routes must be protected in the frontend, but frontend protection is only UX.

The backend must independently authorize every protected endpoint.

User-owned resources include, at minimum:

- plant configurations
- analysis runs
- scenarios/results
- reports

Object-level access control must prevent IDOR/cross-user access.

Never trust `user_id` or `owner_id` sent by the frontend as authorization truth.

---

## 13. Permanent Security Rules

These rules apply to every development part.

1. Hide all API keys and secrets.
2. Validate environment variables.
3. Protect private routes.
4. Maintain proper authentication.
5. Enforce server-side access control.
6. Validate and sanitize forms/inputs.
7. Prevent XSS and unsafe HTML rendering.
8. Rate-limit auth, AI, simulation, and other expensive endpoints.
9. Maintain a consistent secure API response/error format.
10. Use a strict CORS allowlist.
11. Add security headers.
12. Keep production debug mode off.
13. Review dependency security and update carefully.
14. Remove unused packages.
15. Check for exposed/private files.
16. Secure database access and credentials.
17. Hash passwords; never store plaintext.
18. Scan current Git tree/history for leaked secrets.
19. Perform recurring and final security audits.
20. Commit/push after each coherent feature or roughly 300 meaningful LOC; target 50+ meaningful commits across the full project, not fake commit spam.
21. Security is continuous, not a final patch.
22. Before a new external API integration, explicitly state which API key/provider/env variable is required.
23. Test every feature immediately after implementation.
24. Keep README and project docs synchronized with real code.
25. Every authenticated application screen must fit inside one usable viewport without page-level vertical scrolling.

---

## 14. One-Viewport UI Rule

Authenticated product screens should behave like a desktop application workspace, not a long website.

### Non-negotiable

Do not solve the requirement by applying `overflow: hidden` and cutting off content.

Instead:

- long forms → multi-step wizard,
- long lists → pagination,
- large tables → pagination,
- many sections → tabs or separate routes,
- large charts → switchable chart tabs,
- mobile → one primary panel at a time,
- dialogs/modals → viewport-safe internal layout.

Test desktop, tablet, and mobile.

No inaccessible buttons, clipped content, or hidden fields.

A marketing landing page may intentionally scroll if required, but authenticated application screens should remain viewport-contained.

---

## 15. Animation Rule

Animations must communicate system state.

Use GSAP for:

- process-flow animation,
- active pipeline indication,
- state transitions,
- PLAN → SIMULATE → OBSERVE → INVESTIGATE,
- causal-chain visualization,
- restrained warning/critical pulses.

Do not animate everything.

Respect `prefers-reduced-motion`.

Three.js is optional and should remain small and purposeful.

---

## 16. API and Secret Rules

Expected environment variables:

```env
ENVIRONMENT=
FRONTEND_URL=
DATABASE_URL=
JWT_SECRET=

NEBIUS_API_KEY=
NEBIUS_BASE_URL=
NEBIUS_MODEL=
```

Frontend public configuration:

```env
VITE_API_BASE_URL=
```

Never expose:

- `NEBIUS_API_KEY`
- `JWT_SECRET`
- database credentials
- session tokens
- private keys

A real `.env` must never be committed.

Only `.env.example` should be tracked.

---

## 17. Secure API Convention

Prefer consistent responses.

Success:

```json
{
  "success": true,
  "data": {}
}
```

Error:

```json
{
  "success": false,
  "error": {
    "code": "SOME_ERROR",
    "message": "Safe user-facing message"
  }
}
```

Never return internal stack traces or secrets.

---

## 18. AI Security Rules

Treat model output as untrusted.

- validate all structured output with Pydantic,
- use allowlisted tools,
- enforce numeric bounds,
- never execute arbitrary model-generated code,
- never give shell access,
- never expose filesystem access,
- never expose arbitrary SQL access,
- never send secrets in prompts,
- defend against prompt-injection attempts from user engineering text,
- use bounded agent loops,
- set maximum model calls/simulations/timeouts.

---

## 19. Required Testing Philosophy

Every feature is tested before moving on.

Minimum deterministic benchmark set:

- safe baseline
- cooling-loss violation
- outlet-restriction violation
- feed increase
- hidden combined failure
- safeguard activates in time
- safeguard activates too late

Security tests must include:

- unauthenticated access
- invalid/expired session
- cross-user object access
- malformed input
- rate limits
- XSS-prone content rendering
- excessive simulation/search request rejection
- malformed AI output
- provider failure
- prompt-injection attempt

---

## 20. Git Discipline

After each coherent feature or roughly every 300 meaningful lines:

```text
implement
   ↓
test/lint
   ↓
inspect git diff
   ↓
meaningful commit
   ↓
push
```

Use meaningful commit messages.

Do not create artificial commits only to increase count.

Target: 50+ meaningful commits across the complete project if the work naturally supports it.

---

## 21. Documentation Rule

Persistent project files:

```text
docs/SAFEFLUX_MASTER.md
docs/ARCHITECTURE.md
docs/SESSION_LOG.md
README.md
```

Priority:

- `SAFEFLUX_MASTER.md` = what/why/non-negotiable product rules
- `ARCHITECTURE.md` = how the system is built
- `SESSION_LOG.md` = what is completed/current/next
- `README.md` = public project documentation

Never let docs claim a feature is complete if code is not complete.

---

## 22. Ten-Part Build Plan

### Part 1 — Repository Audit + Secure Foundation
### Part 2 — Authentication + Authorization
### Part 3 — Plant Setup + Configuration
### Part 4 — Deterministic Process Simulator
### Part 5 — Safety Engine + Telemetry
### Part 6 — Engineering Dashboard + Visualization
### Part 7 — Scenario Engine + Boundary Search
### Part 8 — Nebius + NVIDIA Nemotron Agent
### Part 9 — Investigation + Safeguards + Re-verify UX
### Part 10 — Final Hardening

Submission/video work begins only after Part 10 passes.

---

## 23. Hackathon Integration Rule

Final build must include genuine runtime use of:

- Nebius Token Factory or eligible Nebius infrastructure
- an eligible NVIDIA open-source model, intended to be Nemotron

Do not permanently hard-code a model ID before verifying actual account/catalog availability.

---

## 24. Safety Language

Never claim:

> This process is guaranteed safe.

Prefer:

> No unsafe condition was detected within the tested simulation scenarios.

SafeFlux is a hackathon research prototype and decision-support system, not certified industrial safety software.

---

## 25. Debugging Duck Protocol 🦆

Trigger:

`Duck`
`Debugging Duck`
or an obvious close typo.

When triggered:

1. inspect the current GitHub repository,
2. read:
   - `docs/SAFEFLUX_MASTER.md`
   - `docs/ARCHITECTURE.md`
   - `docs/SESSION_LOG.md`
3. inspect current source code relevant to the active build part,
4. compare documentation against actual implementation,
5. check:
   - product scope
   - architecture
   - AI-vs-simulator separation
   - authentication
   - access control
   - all 25 security rules
   - one-viewport UI rule
   - tests
   - Git/commit discipline
   - dependency hygiene
   - secret exposure
   - hackathon integration
6. report:
   - **ON TRACK ✅**
   - **DRIFTING ⚠️**
   - **BLOCKED / BROKEN ❌**
7. state the smallest useful next action,
8. update/recommend documentation changes if the implementation intentionally changed.

Repository code and current docs are the technical source of truth.

---

## 26. Current State

As of 2026-10-04:

- concept, MVP scope, product workflow and tech stack locked,
- security requirements, one-viewport UI rule, 10-part build plan and Debugging Duck
  protocol locked,
- **Part 1** (secure foundation) complete,
- **Part 2** (authentication + authorization) complete,
- **Part 3** (plant setup + configuration) complete,
- **Part 4** (deterministic process simulator) complete.

### Next action

Part 5 — Safety Engine + Telemetry — then continue the build plan part by part, running
Debugging Duck after each part.
