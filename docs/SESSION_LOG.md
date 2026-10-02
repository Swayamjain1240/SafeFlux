# SafeFlux — Session Log

**Rule:** Keep newest checkpoint at the top. Record real decisions and do not rewrite history merely to make the project appear cleaner.

---

# Current Checkpoint — 2026-10-02

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
