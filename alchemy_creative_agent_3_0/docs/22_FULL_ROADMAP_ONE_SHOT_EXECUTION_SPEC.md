# 22 Full Roadmap One-Shot Execution Spec

This document is the integration contract for running Alchemy Creative Agent 3.x through an autonomous development system such as Alchemy Dev Lab.

It exists to prevent the executor from reading only one phase prompt, completing that phase, and incorrectly handing off while later required work remains.

## Core Rule

When the user asks to develop the whole V3 product from the supplied documents, the root contract is the complete V3 document package, not only `06_CODEX_TASK_PROMPT.md`.

The executor must:

1. read all documents under `alchemy_creative_agent_3_0/docs/`;
2. expand any referenced documents before planning;
3. classify phase-local limits separately from global limits;
4. build a full roadmap from every required phase;
5. execute each phase in dependency order;
6. run phase audit, tests, and repair before promotion;
7. continue automatically into the next phase;
8. run final full-system audit, simulation tests, and real tests before handoff.

## Required Document Set

The one-shot executor should treat these documents as the canonical V3 contract:

```text
00_ROOT_RULES.md
01_PRODUCT_VISION.md
02_SYSTEM_ARCHITECTURE.md
03_AGENT_AND_MODULE_SPEC.md
04_OPEN_SOURCE_REFERENCE_MAP.md
05_DEVELOPMENT_ROADMAP.md
06_CODEX_TASK_PROMPT.md
07_SCHEMA_CONTRACTS.md
08_GOLDEN_CASES.md
09_RULES_AND_DEFAULTS.md
10_BRAND_MEMORY_SPEC.md
11_EVALUATION_AND_REFINEMENT_SPEC.md
12_PROVIDER_INTERFACES.md
13_STEP_BY_STEP_DELIVERY_PLAN.md
14_CODEX_TASK_PROMPTS_PHASE_2_AND_3.md
15_PRODUCT_BOUNDARY_AND_VERTICAL_AGENT_ARCHITECTURE.md
16_V3_FOUNDATION_EXECUTION_GUARDRAILS.md
17_SCENARIO_PACK_PLATFORM_EXTENSION_SPEC.md
18_GENERAL_CREATIVE_PRODUCT_AND_RUNTIME_SPEC.md
19_GENERAL_CREATIVE_QUICK_START_PRESETS_SPEC.md
20_GENERAL_COMMON_SCENE_EXECUTION_AND_CONTRACT_CLOSURE_SPEC.md
21_V3_PRODUCT_INTEGRATION_EXECUTION_PROMPT.md
22_FULL_ROADMAP_ONE_SHOT_EXECUTION_SPEC.md
23_ONE_SHOT_DEV_AGENT_HANDOFF.md
```

`06_CODEX_TASK_PROMPT.md` remains valid as the first Foundation worker prompt, but it must not be interpreted as the full product boundary when the root objective asks for complete delivery.

## Full Roadmap Interpretation

The executor must classify the roadmap as:

```text
V3.0 Foundation
V3.1 Brand Consistency Foundation
V3.2 Generation Loop MVP
V3.3 Commercial Poster Rendering
V3.4 Reference Conditioning Sidecars
V3.5 Product API and Minimal UX
V3.6 Scenario Pack Framework and V3 Home UI
V3.7 General Creative Workspace and Runtime Flow
V3.8+ Future Vertical Packs and Heavy Provider Expansion (optional unless explicitly requested)
```

The exact phase numbering may be normalized by the executor, but the work above must not be dropped when the root objective is full completion.

V3.8+ future expansion is not part of the current one-shot acceptance target unless
the user explicitly asks to build full dedicated vertical packs or heavy provider
integrations in the same run.

## Global Constraints

These constraints apply across every phase:

- V3 must remain independent from V1/V2 runtime modules.
- V3 may share only platform-level shell, account, balance, deployment, and navigation infrastructure through V3-owned adapters.
- V1/V2 and Alchemy Lab behavior must not be broken.
- Protected V1/V2/Lab files may be changed only when the current phase explicitly requires shared shell navigation or platform boundary integration.
- No destructive GitHub or production action may run without explicit delivery policy.

## Phase-Local Constraints

Some earlier documents intentionally restrict only the Foundation phase.

Examples:

```text
Do not implement real image generation yet.
Do not implement full frontend UI in this task.
Do not integrate heavy sidecars yet.
```

In full-roadmap mode, those statements mean:

```text
Do not do this during V3.0 Foundation.
Schedule later phases if the roadmap requires the capability.
```

They must not erase V3.1+ or UI/product phases from the roadmap.

## Current Frontend Boundary

Documents 17, 18, 19, 20, 21, 22, and 23 define the current frontend/product scope:

- build the registry-driven Scenario Pack framework;
- add a shared-shell V3 / 3.0 entry consistent with V1/V2/Alchemy Lab visual language;
- create the V3 home / scenario hub;
- show first-screen cards for General Creative, E-Commerce, New Media Marketing, Private Community Operations, and Brand IP Operations;
- make only General Creative fully usable in the current stage;
- keep E-Commerce, New Media Marketing, Private Community Operations, and Brand IP Operations as manifest-backed placeholders.

The placeholder packs must not open complex dedicated forms, call pack-owned APIs, run pack-owned agents, or implement dedicated generation strategies during this stage.

## Autonomous Audit And Test Loop

After every phase, the central controller must challenge the result from these angles:

- source document coverage;
- protected-path boundary;
- phase-local versus global constraint handling;
- V1/V2/Lab regression risk;
- UI route and navigation safety;
- schema/API/runtime contract consistency;
- deterministic tests and smoke tests;
- user-facing acceptance criteria.

If any angle fails and no external blocker exists, the controller must write a repair task and rerun the phase.

After the last phase, the controller must run:

- full-source reread audit;
- cross-phase consistency audit;
- simulation tests;
- real local tests where available;
- frontend smoke test when UI exists;
- final handoff report.

## One-Sentence Mode

If the user gives only a natural-language objective and no detailed documents, the executor must first create a development document package, audit that package, then run the same full-roadmap loop.

One-sentence mode is allowed to be lower confidence, but it may not skip planning, audit, tests, or final verification.

## Done Definition

A one-shot V3 run is done only when:

- every required phase from the full roadmap is completed or explicitly waived with evidence;
- all phase gates pass;
- V3 independence tests pass;
- V1/V2/Alchemy Lab regression checks pass;
- V3 UI entry and General Creative flow match documents 17, 18, 19, 20, 21, 22, and 23 when those phases are in scope;
- placeholders remain placeholders;
- final audit status is PASS;
- simulation test status is PASS;
- real test status is PASS or has an explicit accepted blocker;
- the final handoff report lists what changed, how to run it, and how to inspect the result.

Stopping after V3.0 Foundation alone is valid only when the user explicitly asks for Foundation only.
