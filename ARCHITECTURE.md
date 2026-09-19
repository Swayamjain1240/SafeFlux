# SafeFlux — Architecture

**Status:** Pre-implementation architecture baseline  
**Last updated:** 2026-09-19

This document describes **how SafeFlux should be structured**. It is intentionally concrete enough to guide implementation, but individual library choices may change if a simpler or more reliable option is discovered.

---

## 1. Architecture Principles

1. **AI reasons; deterministic software computes.**
2. **Experiments happen in a digital simulation, never on a real plant.**
3. **The user describes an engineering change; the system explores the parameter space automatically.**
4. **The LLM is not fed every telemetry sample.** Numerical services monitor state continuously; the LLM is invoked for planning/analysis when useful.
5. **Every important claim shown to the engineer should be traceable to simulation evidence.**
6. **Keep the MVP modular but small.** Do not build enterprise infrastructure before the core loop works.

---

## 2. High-Level System

```text
┌─────────────────────────────────────────────────────────────┐
│                         FRONTEND                            │
│ React / Vite / Tailwind / React Flow / charts             │
│                                                             │
│ Plant view | telemetry | proposed change | scenario results │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / WebSocket or SSE
                               ↓
┌─────────────────────────────────────────────────────────────┐
│                          FASTAPI                            │
│                                                             │
│  API routes                                                 │
│  application services                                      │
│  run orchestration                                         │
└───────┬──────────────────┬──────────────────┬───────────────┘
        │                  │                  │
        ↓                  ↓                  ↓
┌──────────────┐   ┌────────────────┐   ┌───────────────────┐
│ TELEMETRY    │   │ AGENT / SEARCH │   │ PERSISTENCE       │
│ STATE LAYER  │   │ ORCHESTRATOR   │   │                   │
└──────┬───────┘   └───────┬────────┘   └───────────────────┘
       │                   │
       │                   ├──────────────→ Nebius Token Factory
       │                   │                 ↓
       │                   │           NVIDIA Nemotron
       │                   │
       │                   ↓
       │             Scenario Engine
       │                   ↓
       │            Process Simulator
       │                   ↓
       │             Safety Evaluator
       │                   ↓
       └────────────── Results / Evidence
```

---

## 3. Recommended Repository Layout

Initial target:

```text
safeflux/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── plant/
│   │   │   ├── telemetry/
│   │   │   ├── analysis/
│   │   │   └── scenarios/
│   │   ├── services/
│   │   └── app/
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── agents/
│   │   ├── simulation/
│   │   ├── scenarios/
│   │   ├── safety/
│   │   ├── telemetry/
│   │   └── persistence/
│   ├── tests/
│   └── pyproject.toml
│
├── docs/
│   ├── SAFEFLUX_MASTER.md
│   ├── ARCHITECTURE.md
│   └── SESSION_LOG.md
│
├── .env.example
├── LICENSE
└── README.md
```

Do not create every folder just because it appears here. Add modules when there is real code for them.

---

## 4. Core Domain Objects

These names are conceptual; Pydantic models can implement them.

### `PlantConfig`

Mostly static information.

```text
reactor volume/capacity
normal operating ranges
hard simulation limits
pump/heater/cooling capacities
valve properties
safeguard definitions
```

### `ProcessState`

A snapshot at one simulation time.

```text
time
flow
temperature
pressure
level
cooling
valve_position
pump_state
heater_state
shutdown_state
```

### `EngineeringChange`

What the engineer wants to investigate.

Example:

```json
{
  "type": "throughput_change",
  "relative_change": 0.30
}
```

### `FaultInjection`

A scenario disturbance.

Examples:

```text
cooling effectiveness = 0.4
outlet valve stuck at 0.55
sensor frozen
shutdown delay = 15 sec
```

### `Scenario`

```text
base process state
engineering change
one or more injected faults
simulation horizon
metadata / why this test was chosen
```

### `SimulationResult`

```text
time series
max/min values
threshold crossings
safeguard activations
final state
status
```

### `SafetyFinding`

```text
safe / near-limit / violation
violated constraint
first violation time
evidence references
scenario ID
```

---

## 5. Process Simulator

The simulator is the numerical truth source for the MVP.

### Responsibilities

- advance process state through time,
- model simplified flow/level/temperature/pressure behavior,
- apply equipment states,
- apply fault injections,
- apply safeguard logic,
- return reproducible time-series results.

### Non-responsibilities

- natural-language reasoning,
- deciding what scenario is interesting,
- writing engineering explanations.

### Suggested implementation

Python using:

- NumPy
- SciPy
- custom simplified equations
- `scipy.integrate.solve_ivp` where appropriate

The first simulator should intentionally be **small and testable**, not a full chemical-process package.

### Determinism

Given the same:

```text
PlantConfig + base ProcessState + Scenario + simulation settings
```

the simulator should produce the same result unless stochastic behavior is explicitly enabled.

---

## 6. Telemetry Layer

The analysis engine should consume telemetry through an abstraction rather than coupling directly to the simulator.

Conceptual interface:

```python
class TelemetrySource:
    def get_current_state(self) -> ProcessState: ...
    def get_recent_history(self, seconds: int): ...
```

### Hackathon implementation

```text
SimulatorTelemetrySource
        ↓
State store / stream
        ↓
Frontend + analysis services
```

### Future adapters

Possible future read-only implementations:

```text
OPC-UA
MQTT
SCADA API
historian API
```

These are future product paths, **not MVP requirements**.

---

## 7. Scenario Engine

The scenario engine transforms a proposed engineering change and a test specification into executable simulator inputs.

Responsibilities:

- clone the base state,
- apply the proposed change,
- inject one or more failures,
- enforce parameter bounds,
- assign a scenario ID,
- pass the scenario to the simulator,
- store results.

The user should not manually enumerate numeric tests.

---

## 8. Safety Engine

The safety engine is deterministic.

Responsibilities:

- evaluate process constraints,
- find first threshold-crossing time,
- classify results,
- evaluate safeguard timing/effect,
- calculate distance/margin to selected limits,
- produce machine-readable evidence for the agent/UI.

Example output:

```json
{
  "scenario_id": "scn_042",
  "status": "violation",
  "constraint": "max_pressure",
  "limit": 4.0,
  "observed": 4.16,
  "first_violation_s": 71.0
}
```

The LLM should receive this evidence rather than raw speculation.

---

## 9. Agent / Search Orchestrator

This is the agentic heart of SafeFlux.

### Responsibilities

- understand the engineering change,
- select affected variables/components,
- create an initial search plan,
- request executable scenarios,
- observe structured simulator/safety results,
- focus future tests on informative regions,
- request counterfactual tests,
- stop based on budget/coverage criteria,
- generate an evidence-grounded explanation.

### Core loop

```text
START
  ↓
Get base state + change
  ↓
Plan candidate scenarios
  ↓
Execute scenario batch
  ↓
Observe structured evidence
  ↓
Interesting / near limit / violated?
  │
  ├─ no → broaden/finish
  │
  └─ yes
       ↓
focus search / boundary hunt
       ↓
execute more simulations
       ↓
run counterfactuals
       ↓
produce findings
```

### Search strategy

Do not ask the LLM to select every numeric value from scratch.

Use a hybrid approach:

```text
LLM/Nemotron
    → decides which variables/failure modes matter

Deterministic search code
    → sweeps / narrows values / performs boundary search

Simulator
    → determines outcome

LLM/Nemotron
    → interprets structured evidence and chooses next investigation direction
```

Potential deterministic algorithms:

- bounded parameter sweep for coarse exploration,
- binary search for a one-dimensional boundary,
- grid/random/Latin-hypercube-style sampling for small multi-variable spaces,
- sensitivity analysis,
- budgeted local refinement around near-failure points.

Choose the simplest method that produces a convincing working MVP.

---

## 10. Nebius / NVIDIA Model Layer

Use a provider abstraction.

Conceptual interface:

```python
class ReasoningModel:
    async def plan_scenarios(self, context): ...
    async def select_next_investigation(self, evidence): ...
    async def analyze_failure(self, evidence): ...
    async def explain_findings(self, evidence): ...
```

Implementation target:

```text
NebiusReasoningModel
       ↓
Nebius Token Factory API
       ↓
eligible NVIDIA Nemotron model
```

### API configuration

Token Factory supports an OpenAI-compatible API style. Expected configuration pattern:

```python
from openai import OpenAI
import os

client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ["NEBIUS_API_KEY"],
)
```

The exact NVIDIA model ID must be verified from the model catalog available to Swayam's account before integration is locked.

### Hackathon requirement

The final application must make genuine qualifying runtime use of Nebius Token Factory or Nebius AI Cloud and use at least one NVIDIA open-source model.

Do not fake/mock the qualifying model call in the submitted build.

---

## 11. Structured AI Output

Prefer structured outputs for tool orchestration.

Example conceptual scenario proposal:

```json
{
  "focus": "cooling_and_outlet_interaction",
  "reason": "Previous simulation approached the pressure limit while cooling degraded.",
  "variables": ["cooling_effectiveness", "outlet_valve_position"],
  "action": "refine_search"
}
```

The scenario engine validates all requested values against allowed ranges before simulation.

---

## 12. LLM Call Policy

Do not call the LLM every telemetry tick.

Bad:

```text
84.1 → LLM
84.2 → LLM
84.3 → LLM
```

Preferred:

```text
continuous numerical monitoring
        ↓
meaningful event / user request / completed batch
        ↓
LLM reasoning call
```

This reduces latency, cost, and noise.

---

## 13. Persistence

Minimum persisted entities may include:

```text
PlantConfig
AnalysisRun
EngineeringChange
Scenario
SimulationResult
SafetyFinding
AgentDecision summary
```

Start with SQLite unless a stronger requirement appears.

Do not store secrets in the database/repository.

---

## 14. Frontend Experience

The MVP UI should emphasize **visual evidence**, not chat.

Suggested screens/panels:

### Plant View

- visual process topology
- current state values
- selected equipment

### Proposed Change

- short natural-language input
- optionally a structured confirmation of interpreted change

### Autonomous Analysis

- scenarios executed
- currently explored variables/failure mode
- safe / near-limit / violation counts based on actual runs
- progress/event stream

### Finding Detail

- exact scenario parameters
- time-series chart
- first violation point
- safeguard events
- causal/counterfactual evidence

### Re-verify

- alter a simulated mitigation
- rerun affected scenarios
- compare before/after results

The product should work even if a chat panel is omitted entirely.

---

## 15. API Sketch

Not final route names, but the backend likely needs flows equivalent to:

```text
GET  /plant
GET  /plant/state
POST /analysis-runs
GET  /analysis-runs/{id}
GET  /analysis-runs/{id}/scenarios
GET  /scenarios/{id}
POST /analysis-runs/{id}/reverify
```

For live updates use one of:

- Server-Sent Events (simpler), or
- WebSocket (only if bidirectional real-time behavior is needed).

Prefer SSE unless a real need for WebSocket appears.

---

## 16. Testing Strategy

### Unit tests

- process equations
- state updates
- constraint evaluation
- safeguard activation
- scenario validation
- boundary-search logic

### Integration tests

- scenario → simulator → safety finding
- analysis run with deterministic search
- agent tool schema validation
- Nebius provider adapter

### Seeded evaluation cases

Maintain fixtures with known expected outcomes:

```text
safe baseline
cooling-loss violation
outlet restriction violation
combined hidden violation
successful safeguard
late safeguard
```

---

## 17. Observability

Every analysis run should be reproducible and inspectable.

Record:

- input engineering change,
- base state/config version,
- scenario parameters,
- simulator version/settings,
- deterministic result,
- agent decision summary,
- model/provider used,
- timestamps,
- errors.

Avoid storing raw secrets or unnecessary sensitive input.

---

## 18. Security Basics

For the hackathon MVP:

- API keys only via environment variables,
- never send `NEBIUS_API_KEY` to the frontend,
- validate all numeric ranges server-side,
- constrain tool calls to allowed scenario operations,
- do not implement real PLC actuation,
- rate-limit expensive analysis endpoints if the public demo requires it,
- provide `.env.example`, not `.env`.

---

## 19. Deployment Concept

Minimum viable deployment:

```text
Frontend host
      ↓
FastAPI backend host
      ↓
Nebius Token Factory runtime inference
```

The official hackathon rules define a runtime call to Token Factory inference as qualifying Nebius use. Nebius Serverless is optional for the Best Apps & Agents track.

Possible later enhancement:

```text
Nebius Serverless Jobs
    → asynchronous/background simulation batches
```

Only add this if it helps the working product and time permits.

---

## 20. Build Order

Recommended implementation order:

```text
1. Domain models
2. Deterministic single-scenario simulator
3. Safety constraints + seeded tests
4. Scenario injection
5. Coarse automated search / boundary hunt
6. Analysis-run orchestration
7. Basic FastAPI endpoints
8. Basic frontend visualization
9. Nebius/Nemotron reasoning adapter
10. Hybrid agent loop
11. Counterfactual investigation
12. Re-verification workflow
13. UI polish + evaluation + deployment
```

Reason: **if the simulator is not trustworthy, the agent has nothing trustworthy to reason over.**

---

## 21. Architecture Decisions Still Open

Do not treat these as locked until implemented/tested:

- LangGraph vs custom explicit orchestration loop
- SQLite vs PostgreSQL
- SSE vs WebSocket
- exact simulator equations
- exact NVIDIA Nemotron model ID
- whether NetworkX is necessary
- whether Nebius Serverless Jobs add enough value

Decisions should be based on working requirements, not resume keywords.

---

## 22. Debugging Duck Architecture Check

On `Debugging Duck`, compare this document to the repository and verify:

```text
Does code still preserve AI vs simulator separation?
Does the LLM avoid becoming the numerical truth source?
Are experiments still confined to the digital copy?
Is telemetry abstracted from analysis logic?
Is the agent actually iterative, not a one-call prompt?
Are findings traceable to simulation evidence?
Did we add unnecessary infrastructure?
Does the current build still satisfy the hackathon runtime-model requirement?
```

If implementation intentionally differs, update this file rather than silently letting it go stale.

---

## Official References

- Hackathon rules: https://nebiusglobalaihackathon.devpost.com/rules
- Judging guidance: https://nebiusglobalaihackathon.devpost.com/updates/46204-here-s-how-judging-works
- Token Factory documentation: https://docs.tokenfactory.nebius.com/

