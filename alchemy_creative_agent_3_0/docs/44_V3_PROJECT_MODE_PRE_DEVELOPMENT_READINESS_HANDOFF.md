# 44 V3 Project Mode Pre-Development Readiness Handoff

This document is the development-entry handoff for the next V3 Project Mode code
phase.

It collects all pre-development materials required before coding starts.

## 1. Readiness Verdict

V3 Project Mode is ready to enter the next development phase after this
pre-development audit.

The next code phase should start with:

```text
Document 38 + Document 43 first
then Document 39
then Document 41 if template registry hardening is needed before any new template
Document 40 only when explicit cross-project Brand Memory reuse is requested
Document 42 only after 38, 39, 41, and 43 are accepted
```

The immediate recommended implementation boundary is:

```text
V3.8D Project Workspace Continuation UX
+ V3.8H Product Experience Quality Gate
```

This means: improve the project detail workspace, make it image-first and
beginner-facing, add useful workflow summaries and continuation controls, but do
not activate E-Commerce and do not introduce the full document 39 persistence
model until the workspace behavior is verified.

## 2. Current Accepted Architecture

Do not change the architecture shape:

```text
V3 Foundation
  -> Project
      -> Template
          -> Scenario Pack
              -> Job
```

Mandatory interpretation:

```text
Project wraps Job.
Template wraps Scenario Pack.
General Template is the only active Project Mode template.
E-Commerce Template is visible but locked.
Future templates require manifest, gate, tests, and their own accepted spec.
Brand Memory updates require explicit confirmation.
```

## 3. Required Reading Before Coding

Minimum reading for the next code phase:

```text
alchemy_creative_agent_3_0/docs/00_ROOT_RULES.md
alchemy_creative_agent_3_0/docs/13_STEP_BY_STEP_DELIVERY_PLAN.md
alchemy_creative_agent_3_0/docs/32_V3_PROJECT_MODE_CORE_CONTROL_SPEC.md
alchemy_creative_agent_3_0/docs/33_V3_PROJECT_MODE_COMPATIBILITY_AND_MIGRATION_SPEC.md
alchemy_creative_agent_3_0/docs/34_V3_PROJECT_CONTRACT_AND_CONTEXT_SPEC.md
alchemy_creative_agent_3_0/docs/35_V3_PROJECT_FIRST_FRONTEND_UX_SPEC.md
alchemy_creative_agent_3_0/docs/36_V3_GENERAL_TEMPLATE_PROJECT_FLOW_SPEC.md
alchemy_creative_agent_3_0/docs/37_V3_TEMPLATE_INTERFACE_AND_AUDIT_SPEC.md
alchemy_creative_agent_3_0/docs/38_V3_PROJECT_WORKSPACE_CONTINUATION_UX_AND_STATE_SPEC.md
alchemy_creative_agent_3_0/docs/43_V3_PROJECT_MODE_PRODUCT_EXPERIENCE_QUALITY_GATE_SPEC.md
```

Read document 39 only when implementing real reference/feedback persistence.

Read document 41 before changing template activation behavior.

Read document 42 only when beginning E-Commerce unfreeze.

## 4. Current Code Baseline To Inspect

Backend Project Mode:

```text
alchemy_creative_agent_3_0/app/project_mode/contracts.py
alchemy_creative_agent_3_0/app/project_mode/service.py
alchemy_creative_agent_3_0/app/project_mode/store.py
alchemy_creative_agent_3_0/app/product_api/route_handlers.py
src_skeleton/app/main.py
```

Frontend V3 shell and project UI:

```text
src_skeleton/app/static/index.html
src_skeleton/app/static/styles.css
src_skeleton/app/static/app.js
src_skeleton/app/mobile_static/mobile.js
```

Existing tests:

```text
alchemy_creative_agent_3_0/tests/test_v3_project_mode.py
tests/test_v3_commercial_frontend_shell.py
tests/test_api_smoke.py
```

Existing persistent project storage:

```text
.media_storage/v3_projects
```

Do not use this storage as a schema authority. The schema authority is the V3
contracts and documents 34, 38, 39, and 43.

## 5. Immediate Phase Goal

The next code phase should make project detail feel like a real continuation
workspace rather than a shallow project wrapper.

Required user-visible result:

```text
1. V3 home remains project-first.
2. Clicking a project opens an image-first project detail workspace.
3. Project detail shows generated/selected images before dense summaries.
4. Project detail shows useful references.
5. Project detail shows a simple workflow progress layer.
6. Project detail shows plain next actions.
7. General Template can continue inside the project.
8. E-Commerce remains locked and cannot create project jobs.
9. Engineering language remains hidden from normal users.
```

## 6. First Code Phase Functional Checklist

Implement or verify:

```text
project cards show meaningful thumbnails when available
project detail has an output board section
selected outputs appear as useful reference image tiles
workflow progress cards explain what V3 has done in plain language
continuation action rail is visible after project open
continue same style creates a new project job under the same project
upload new reference continue is visible; if full persistence is not implemented, mark persistence as current-job-only or disabled
negative feedback control is either implemented or clearly disabled until document 39
timeline items are meaningful and clickable or at least expandable
locked E-Commerce card shows a beginner-facing locked message and creates no job
normal UI hides provider, job id, asset ref, manifest, prompt compiler, and context package
mobile layout puts images and actions before dense summaries
```

## 7. Backend Boundary For First Code Phase

Prefer using existing Project Mode APIs first:

```text
GET  /api/v3/creative-agent/projects
POST /api/v3/creative-agent/projects
GET  /api/v3/creative-agent/projects/{project_id}
GET  /api/v3/creative-agent/projects/{project_id}/timeline
POST /api/v3/creative-agent/projects/{project_id}/jobs
POST /api/v3/creative-agent/projects/{project_id}/jobs/{job_id}/generate
POST /api/v3/creative-agent/projects/{project_id}/jobs/{job_id}/select
```

Do not add the full document 39 endpoints in the first code phase unless the
frontend cannot meet the accepted UX without them.

If a document 39 endpoint is needed, add the smallest safe slice and test it.

## 8. Data Rules For First Code Phase

Allowed:

```text
read existing project summary
read existing timeline
read current selected_output_refs
read generated output URLs from project/job payloads
derive plain workflow summary from existing project/timeline/job state
```

Not allowed yet:

```text
silently treating all generated outputs as positive references
persisting negative feedback without the document 39 contract
writing Brand Memory
activating E-Commerce
reading V1/V2/Lab runtime history directly
```

## 9. Product Experience Requirements

The first code phase must pass document 43.

The UI must answer these user questions:

```text
这个项目要做什么？
现在有哪些图？
哪些图会被后续参考？
V3 已经做了哪几步？
下一步我可以怎么继续？
哪里需要我检查？
```

The UI must not ask the user to understand:

```text
provider
job id
asset ref
manifest
scenario runtime
prompt compiler
context package
capability module
```

## 10. Suggested Implementation Order

Recommended order:

```text
1. Add or update frontend tests describing the new project detail layout.
2. Refactor project detail rendering into image board, useful references, workflow progress, next actions, and timeline.
3. Make project cards use project thumbnail/selected output preview when available.
4. Add image-first output board and selected reference board.
5. Add workflow progress cards using existing project/timeline state.
6. Add continuation action rail for same-style generation.
7. Add disabled or clearly scoped controls for future document 39 features.
8. Ensure locked E-Commerce cannot create jobs from project detail.
9. Add mobile ordering and CSS polish.
10. Run focused tests, then broader regression.
```

## 11. Required Test Commands

Focused first:

```powershell
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_project_mode.py tests/test_v3_commercial_frontend_shell.py -q
```

Frontend syntax:

```powershell
node --check src_skeleton/app/static/app.js
node --check src_skeleton/app/mobile_static/mobile.js
```

Compile:

```powershell
python -m compileall -q alchemy_creative_agent_3_0 src_skeleton
```

V3 package:

```powershell
python -m pytest alchemy_creative_agent_3_0/tests -q
```

Main smoke:

```powershell
python -m pytest tests/test_api_smoke.py tests/test_v3_commercial_frontend_shell.py -q
```

Root regression before handoff:

```powershell
python -m pytest -q
```

Diff check:

```powershell
git diff --check
```

Long-running state validation when using the long-running workflow:

```powershell
python "%USERPROFILE%/.codex/skills/long-running-task/scripts/validate_state.py" --project .
```

## 12. Manual QA Script

Run the local app using the existing project convention. If no server is already
running:

```powershell
python -m uvicorn src_skeleton.app.main:app --host 127.0.0.1 --port 8017
```

Manual checks:

```text
1. Open /creative-agent-v3.
2. Confirm the V3 home shows project cards and project history, not raw job history.
3. Create a project with one short request.
4. Open the project detail page.
5. Generate with General Template.
6. Confirm images appear in the output board.
7. Select one image.
8. Confirm it appears as a useful reference.
9. Continue same style.
10. Confirm a new job/timeline item appears under the same project.
11. Click E-Commerce Template.
12. Confirm it shows locked copy and creates no job.
13. Refresh and reopen the project.
14. Confirm the project still shows useful images, summaries, next actions, and timeline.
15. On mobile width, confirm images and actions appear before dense text.
```

## 13. Required Scope Audit

Run searches after implementation:

```powershell
rg -n "provider|job id|asset ref|manifest|prompt compiler|context package|scenario runtime|capability module" src_skeleton/app/static/index.html src_skeleton/app/static/app.js src_skeleton/app/static/styles.css tests/test_v3_commercial_frontend_shell.py
```

If matches exist, verify they are hidden debug/test-only strings or remove them
from normal user-visible UI.

Check locked E-Commerce:

```powershell
rg -n "ecommerce_template|template_locked|locked" alchemy_creative_agent_3_0/app/project_mode src_skeleton/app/static/app.js tests/test_v3_commercial_frontend_shell.py
```

Check V1/V2/Lab runtime isolation:

```powershell
rg -n "custom_media_agent|media_agent|alchemy_lab|v1|v2" alchemy_creative_agent_3_0/app/project_mode alchemy_creative_agent_3_0/app/product_api/route_handlers.py
```

Any match must be reviewed as documentation text, compatibility wording, or a
clear violation.

## 14. Known Constraints

Current constraints:

```text
No destructive migration.
No E-Commerce activation in the next code phase.
No automatic Brand Memory write.
No V1/V2/Lab runtime dependency.
No advanced engineering dashboard in normal UI.
No standalone project job outside project_id.
```

## 15. Development Entry Checklist

The project may enter development when all are true:

```text
docs 32-44 exist and are indexed
README points current work to docs 32-44
13_STEP_BY_STEP_DELIVERY_PLAN points current work to Project Mode first
document 43 is referenced as a required product experience gate
existing long-running state shows no blockers
current code baseline already has Project Mode APIs and persistent project store
existing tests for Project Mode and frontend shell are known
first code phase boundary is document 38 + document 43
test commands are listed
manual QA script is listed
the historical E-Commerce freeze rule applies to this document 38 + 43 boundary
```

Historical note:

```text
The E-Commerce freeze line above applied to the document 38 + 43 coding
boundary. Current template activation state is governed by document 42 and the
template registry. Document 51 does not change template activation; it defines
shared commercial consistency modules used by active templates.
```

If this checklist passes, coding can begin.

## 16. Handoff Prompt For Next Coding Phase

Use this prompt when starting implementation:

```text
Implement V3 Project Mode development phase 38 + 43 only.

Goal:
Upgrade the existing V3 project detail workspace into an image-first,
beginner-facing continuation workspace. Keep the existing V3 architecture. Do
not activate E-Commerce. Do not write Brand Memory. Do not implement the full
document 39 persistence model unless a minimal slice is required and tested.

Required docs:
00, 13, 32-38, 43, and this 44 handoff.

Primary code areas:
src_skeleton/app/static/index.html
src_skeleton/app/static/styles.css
src_skeleton/app/static/app.js
alchemy_creative_agent_3_0/app/project_mode/*
alchemy_creative_agent_3_0/app/product_api/route_handlers.py
src_skeleton/app/main.py

Required tests:
focused Project Mode and frontend shell tests first, JS syntax, compile,
V3 package, main smoke, root pytest, diff check.

Stop condition:
Stop after 38 + 43 are implemented, tested, audited, and ready for user review.
```
