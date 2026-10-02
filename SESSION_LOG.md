# SafeFlux — Session Log

This file is the chronological checkpoint log for SafeFlux.

**Rule:** Keep newest session at the top. Do not rewrite history just to make the project look cleaner. If a decision changes, record the new decision and why.

---

# Current Checkpoint

**Date:** 2026-09-19  
**Status:** 🟢 Ready to begin architecture/repository setup  
**Project:** SafeFlux — Autonomous Process-Safety Failure Hunter  
**Track:** Best Apps & Agents

## What is complete

- Hackathon requirements reviewed.
- Project-search phase completed.
- SafeFlux selected and name locked.
- Primary user defined: process-safety / chemical-process engineer.
- Core problem defined.
- Hackathon MVP narrowed to a small heated reactor/tank system.
- Data strategy defined:
  - initial plant configuration,
  - simulator-generated dynamic telemetry for hackathon,
  - future read-only industrial connectors possible.
- Main user workflow defined.
- Agent-vs-simulator responsibility defined.
- Autonomous failure/boundary hunting concept defined.
- Counterfactual root-cause approach defined.
- Real-plant safety boundary defined: no autonomous control.
- Proposed tech stack defined.
- Nebius/NVIDIA integration strategy defined at architecture level.
- `Debugging Duck` checkpoint protocol established.
- Persistent project documentation established.

## Core project sentence

> **SafeFlux lets a process engineer describe a proposed change, then autonomously searches a digital process simulation for hidden unsafe conditions, verifies them deterministically, and returns evidence for human review.**

## Golden rule

> **AI searches for danger → Simulator proves it → Engineer decides.**

## Current MVP

```text
Feed Tank
    ↓
Pump
    ↓
Heated Reactor / Tank
 ┌──┼──────────────┐
 │  │              │
Heat Cooling     Sensors
    ↓
Outlet Valve
    ↓
Product Tank
```

Variables currently planned:

- flow
- temperature
- pressure
- level
- cooling
- valve position
- pump/heater state
- shutdown state/delay

Initial failure modes:

- cooling degradation/loss
- outlet restriction
- feed increase
- sensor failure
- shutdown delay
- selected combinations

## Intended hackathon data flow

```text
Plant configuration
      +
Python simulator
      ↓
telemetry/current state
      ↓
engineer describes change
      ↓
agent plans investigation
      ↓
scenario engine
      ↓
simulator
      ↓
safety evaluator
      ↓
agent observes evidence
      ↓
focused search / counterfactual tests
      ↓
engineer-facing findings
```

## Nebius / NVIDIA status

- Final project must make genuine runtime use of Nebius Token Factory or Nebius AI Cloud.
- Final project must use at least one NVIDIA open-source model.
- Intended reasoning model family: NVIDIA Nemotron through Token Factory.
- Exact model ID: **not locked yet**; verify actual catalog/account access first.
- Builder/Token Factory access: **pending / needs re-check when integration work starts**.

## Decisions intentionally NOT made yet

- LangGraph vs custom orchestration loop
- exact process equations
- SQLite vs PostgreSQL
- SSE vs WebSocket
- exact NVIDIA model ID
- Nebius Serverless Jobs usage

These are implementation decisions, not reasons to delay the first simulator prototype.

## Known risks

### Risk 1 — Simulator credibility

If the simulator is too fake/random, the project loses its engineering value.

**Mitigation:** start with explicit simplified equations, deterministic seeded cases, unit tests, and clearly label it as an MVP process model rather than a certified industrial simulator.

### Risk 2 — AI becomes decorative

If SafeFlux simply calls Nemotron once to write a report, it becomes a generic wrapper.

**Mitigation:** implement a real iterative loop where the model selects investigation direction/tools based on previous simulator evidence.

### Risk 3 — Agent chooses all numeric values poorly

LLMs are not numerical optimizers.

**Mitigation:** use hybrid search: model chooses meaningful variables/failure modes; deterministic algorithms sweep/refine/boundary-search values.

### Risk 4 — Scope explosion

P&ID parsing, real PLC integration, advanced thermodynamics, every safety methodology, and enterprise deployment could overwhelm a solo hackathon build.

**Mitigation:** keep the heated-reactor MVP and one strong end-to-end story.

### Risk 5 — Nebius access delay

Model/API access may remain a blocker for final compliance.

**Mitigation:** build the simulator and provider abstraction independently, but do not consider the final submission ready until genuine qualifying Nebius/NVIDIA runtime integration works.

## Next action

**Create the SafeFlux repository structure and begin with the backend domain model + deterministic simulator skeleton.**

Recommended first engineering target:

```text
Given:
- PlantConfig
- ProcessState
- Scenario

When:
- simulator runs for N seconds

Then:
- it returns a reproducible time-series SimulationResult
- safety engine can identify threshold violations
```

No LLM is needed for this first target.

---

# Debugging Duck 🦆

When Swayam says `Debugging Duck` (or an obvious typo such as `debugging dub`):

1. read `SAFEFLUX_MASTER.md`, `ARCHITECTURE.md`, and this file,
2. inspect the actual repository/code,
3. compare implementation against documented product/architecture,
4. report one of:
   - **ON TRACK ✅**
   - **DRIFTING ⚠️**
   - **BLOCKED / BROKEN ❌**
5. identify the smallest useful correction/next step,
6. update documentation when a real decision has changed.

The repository is the technical source of truth; conversation memory must not override the current code.

---

# Session — 2026-09-19: Project Lock + Persistent Memory

## Decisions

- Project renamed from HazardForge to **SafeFlux**.
- Subtitle: **Autonomous Process-Safety Failure Hunter**.
- Track: **Best Apps & Agents**.
- Goal clarified: enjoy the hackathon, learn deeply, and finish a real project; winning is not the primary goal.
- Persistent project-memory approach chosen using three docs:
  - `SAFEFLUX_MASTER.md`
  - `ARCHITECTURE.md`
  - `SESSION_LOG.md`
- Checkpoint protocol named **Debugging Duck**.

## Product understanding established

The user should not manually enter every test value. SafeFlux should take a proposed change and automatically explore the process state space.

The intended separation is:

```text
LLM/Nemotron
    → reasoning, planning, investigation direction, explanation

Search code
    → parameter exploration and boundary refinement

Simulator
    → process behavior

Safety engine
    → pass/fail/threshold evidence

Engineer
    → final judgment
```

## Data-source decision

Hackathon:

```text
Python simulator → generated telemetry → SafeFlux
```

Future real product:

```text
Sensors → PLC/DCS → SCADA/Historian → OPC-UA/MQTT/API → SafeFlux
```

Real industrial integration is future scope and should be read-only for the analysis workflow.

## End-of-session state

Concept work is sufficiently complete to begin implementation. No more project-search phase unless a genuine technical blocker invalidates SafeFlux.

---

## Official References

- Hackathon rules: https://nebiusglobalaihackathon.devpost.com/rules
- Judging guidance: https://nebiusglobalaihackathon.devpost.com/updates/46204-here-s-how-judging-works
- Nebius Token Factory docs: https://docs.tokenfactory.nebius.com/

