# 23 One-Shot Dev Agent Handoff

This document is the single execution entry for testing whether Alchemy Dev Agent / Alchemy Dev Lab can complete the current V3 product integration in one continuous run.

It does not add new product scope. It converts the existing V3 documents into an unambiguous autonomous-development contract.

---

## 1. One-Shot Objective

Given the current `alchemy-media-agent` repository, complete the current V3 product-integration stage without stopping after intermediate milestones.

The run must deliver:

```text
V3-owned runtime contracts already specified by docs 00-16
Scenario Pack extension framework from doc 17
General Creative product/runtime from doc 18
General Creative quick-start presets from doc 19
General Common Scene closure from doc 20
Shared shell 3.0 navigation + Scenario Hub integration from doc 21
Full-roadmap one-shot execution contract from doc 22
V1 / V2 / Alchemy Lab regression smoke validation
```

The visible user-facing target is:

```text
Existing shared site shell
  -> 3.0 navigation entry
  -> V3 Scenario Hub
  -> General Creative available card
  -> General Creative beginner-first workspace
  -> placeholder cards for ecommerce, new media, private community, and brand IP
```

---

## 2. Non-Stop Execution Rule

The agent must not stop merely because one phase is complete.

Required loop:

```text
read all required docs
analyze implementation gaps
implement the next missing contract
run focused tests
audit against docs
fix defects
continue to the next missing contract
repeat until the current-stage Definition of Done is satisfied
run final regression and smoke validation
prepare final report
```

The agent may stop only when:

```text
all current-stage requirements pass
or
a real external blocker prevents progress
or
the repository state is unsafe to modify without human decision
```

Examples that are not valid stop reasons:

```text
V3.0 foundation is complete
backend tests pass but frontend is not mounted
Scenario Hub exists but General Creative cannot create a job
General Creative works but V1/V2/Alchemy Lab smoke checks were not run
placeholder cards exist but can still trigger jobs
```

---

## 3. Required Reading Order

Read documents in this order before writing code:

```text
alchemy_creative_agent_3_0/README.md
alchemy_creative_agent_3_0/docs/00_ROOT_RULES.md
alchemy_creative_agent_3_0/docs/13_STEP_BY_STEP_DELIVERY_PLAN.md
alchemy_creative_agent_3_0/docs/16_V3_FOUNDATION_EXECUTION_GUARDRAILS.md
alchemy_creative_agent_3_0/docs/17_SCENARIO_PACK_PLATFORM_EXTENSION_SPEC.md
alchemy_creative_agent_3_0/docs/18_GENERAL_CREATIVE_PRODUCT_AND_RUNTIME_SPEC.md
alchemy_creative_agent_3_0/docs/19_GENERAL_CREATIVE_QUICK_START_PRESETS_SPEC.md
alchemy_creative_agent_3_0/docs/20_GENERAL_COMMON_SCENE_EXECUTION_AND_CONTRACT_CLOSURE_SPEC.md
alchemy_creative_agent_3_0/docs/21_V3_PRODUCT_INTEGRATION_EXECUTION_PROMPT.md
alchemy_creative_agent_3_0/docs/22_FULL_ROADMAP_ONE_SHOT_EXECUTION_SPEC.md
alchemy_creative_agent_3_0/docs/23_ONE_SHOT_DEV_AGENT_HANDOFF.md
```

If implementation requires older contract details, read the referenced docs from `00` through `15`; do not assume they were already implemented correctly.

---

## 4. Baseline Reconciliation

Before editing:

```text
1. Identify current branch and commit.
2. Inspect git status.
3. Detect untracked runtime artifacts.
4. Confirm whether V3 code already exists under alchemy_creative_agent_3_0/.
5. Compare current implementation against docs 17-23.
6. Build a gap checklist.
```

Do not delete or overwrite existing V1, V2, Alchemy Lab, or local media output files.

Do not stage:

```text
.media_storage/
.pytest_cache/
__pycache__/
*.pyc
local env files
logs
screenshots unless explicitly used as test evidence
```

---

## 5. Mandatory Implementation Scope

### 5.1 Shared Shell

The existing frontend shell must add a visible `3.0` navigation entry next to the existing V1, V2, Alchemy Lab, and video entries.

Clicking `3.0` must open the V3 Scenario Hub without removing or renaming old entries.

### 5.2 Scenario Hub

The Scenario Hub must render from registry or manifest data, not hard-coded workflow branches.

Required first-screen cards:

```text
General Creative / 通用创作        available
E-Commerce / 电商特调             placeholder
New Media Marketing / 新媒体营销  placeholder
Private Community / 私域社群运营  placeholder
Brand IP Operations / 品牌 IP 运营 placeholder
```

### 5.3 General Creative

General Creative is the only complete current-stage scenario.

It must provide:

```text
one natural-language input
quick-start cards
optional brand selector
optional reference upload
one primary generate button
progress/status area
result area
history area
advanced controls collapsed by default
```

It must route through V3-owned APIs and runtime.

### 5.4 Placeholder Cards

Placeholder cards may display name, description, typical uses, and a "Use General Creative instead" action.

They must not create jobs, call pack-owned APIs, call dedicated agents, or activate pack-specific policies.

---

## 6. Backend/API Contract

V3 product actions must stay under:

```text
/api/v3/creative-agent/*
```

V3 may share platform adapters for account, balance, storage, and deployment only through V3-owned adapter boundaries.

V3 must not route generation through:

```text
/v1/*
/api/v2/*
V1/V2 prompt transform
V1/V2 generation services
V1/V2 ImagePromptPlan
V1/V2 frontend state
```

---

## 7. Test Gate

Run at least:

```text
python -B -m pytest alchemy_creative_agent_3_0/tests -q
python -B -m pytest tests -q
```

If the full root suite depends on unavailable external services, run the closest offline subset and report the limitation.

Also run syntax/static checks for touched frontend files when available:

```text
node --check src_skeleton/app/static/app.js
node --check src_skeleton/app/mobile_static/mobile.js
```

If Node is unavailable, report it and rely on browser smoke tests.

---

## 8. Required Local Smoke Test

When the local environment allows, start or reuse the services:

```text
cd custom_media_agent_2_0
python -m uvicorn app.main:app --host 127.0.0.1 --port 8020

cd src_skeleton
python -m uvicorn app.main:app --host 127.0.0.1 --port 8017
```

Smoke checks:

```text
GET http://127.0.0.1:8017/healthz returns ok
GET http://127.0.0.1:8020/api/v2/health returns ok
http://127.0.0.1:8017/ loads
V1 tab opens
V2 tab opens
Alchemy Lab tab opens
3.0 tab opens
3.0 opens Scenario Hub
General Creative card opens workspace
placeholder cards do not create jobs
General Creative can submit a dry-run or mock planning/generation job
result/progress/history areas render honestly
browser console has no blocking errors
```

The run is incomplete if the shared shell does not visibly show `3.0`.

---

## 9. Final Audit Angles

Before reporting completion, audit from these angles:

```text
document coverage
runtime independence
V1/V2/Alchemy Lab non-regression
frontend navigation and state isolation
Scenario Hub registry/manifest drive
General Creative beginner UX
General Creative API/runtime flow
placeholder non-executability
test evidence
Git cleanliness
```

Any failed angle must trigger another fix-test-audit loop.

---

## 10. Final Report Format

The final report must include:

```text
ONE_SHOT_STATUS: COMPLETE or INCOMPLETE
DOC_COVERAGE_STATUS: PASS or FAIL
SHARED_SHELL_STATUS: PASS or FAIL
SCENARIO_HUB_STATUS: PASS or FAIL
GENERAL_CREATIVE_STATUS: PASS or FAIL
PLACEHOLDER_BOUNDARY_STATUS: PASS or FAIL
V1_V2_ALCHEMY_LAB_REGRESSION_STATUS: PASS or FAIL
INDEPENDENCE_STATUS: PASS or FAIL
TEST_STATUS: PASS or FAIL
SMOKE_STATUS: PASS or FAIL
GITHUB_PR_STATUS: CREATED or NOT_CREATED
```

Also include:

```text
branch and commit
files changed outside alchemy_creative_agent_3_0/
tests run
smoke URLs
known limitations
manual verification steps
```
