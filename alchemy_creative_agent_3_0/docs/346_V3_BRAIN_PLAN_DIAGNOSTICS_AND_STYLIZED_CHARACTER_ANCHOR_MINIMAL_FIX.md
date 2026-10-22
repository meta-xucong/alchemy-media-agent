# Doc346 — V3 Brain Plan Diagnostics and Stylized-Character Anchor Minimal Fix

Status: **Local implementation, focused verification, and independent code audit passed; GitHub/VPS release and live four-image acceptance remain pending.** This spec
turns the findings in [Doc345](345_V3_OCT22_FOX_CHARACTER_PLANNING_AND_CONTINUITY_ERROR_ANALYSIS.md)
into two bounded Foundation corrections. It does not authorize code changes,
provider calls, deployment, commit, or push.

## 1. Goal and frozen scope

Restore two intended behaviors with the smallest complete change:

1. When the existing Brain validator rejects `image_set_plan`, preserve enough
   already-sanitized diagnostic evidence on the durable blocked-job outcome to
   identify the rejection class later. Doc277's public planning-operation
   projection continues to expose its safe failure code and linked job ID; it
   does not need to expose detailed Brain diagnostics.
2. Treat typed `stylized_character` as the same character-continuity subject
   class already promised by Doc344, allowing the existing first-accepted
   output anchor and next-job reuse path to operate.

Classification: **V3 Foundation** (shared Brain diagnostics and identity
continuity). General Template remains scenario-neutral. The incident prompt is
only a regression fixture.

Frozen workflow classification for this documentation phase: **D0 / I0 / A1**.
The implementation direction is fixed by the existing validators and
Doc322/Doc344 contracts; this phase changes only two documents; independent
review must check cross-module evidence and scope boundaries. Baseline is
`main` at `081eb99f454b2034a2974894d9eb0b4417c4e03a`, equal to
`origin/main`. Existing untracked validation material and the active unrelated
worktree are preserved. The sole writer for these documents is the main
session.

### Non-goals

- No change to image-set acceptance/cardinality rules, Brain creativity, prompt
  wording, output count, retry budget, provider selection, or review thresholds.
- No automatic retry, deterministic fallback, extra validation framework,
  second anchor service, new persisted state flag, backfill, or migration.
- No rewrite of Doc322 manual bind/replace/unbind behavior or Doc344's
  first-formally-accepted planned-output selection.
- No edits to V1, V2, General Template contracts, specialized templates, UI,
  or VPS deployment in this document phase.

## 2. Frozen correction model

### 2.1 Brain planning diagnostics

**Authority:** the existing `V3LLMBrainAdapter` validation result. Rejections
remain authoritative. The operational outcome is only a safe diagnostic
projection, never a second validator.

Trace the current data path from adapter audit, through
`ScenarioRuntime._remote_creative_brain_block`,
`V3ProductApiService._public_remote_brain_lifecycle_outcome`, blocked Product
Job metadata, and Doc277's durable operation failure. The current active VPS
release was read-only verified as clean revision
`081eb99f454b2034a2974894d9eb0b4417c4e03a`, matching the local main baseline.
At this revision, the runtime builds safe cardinality/validation summaries,
but the Product API lifecycle projection drops those two fields before storing
the blocked-job outcome. The historical task is not tied to the exact release
or process that served it, so this is the proven current code path to correct,
not a proven process-level cause of that historical record. Confirm the call
path with a deterministic fixture before changing it; do not add duplicate
diagnostics to Doc277's public operation record.
Reuse the current allowlisted fields where they already exist:

- cardinality: `expected_image_count`, `remote_image_count`,
  `remote_shot_plan_count`, `cardinality_valid`;
- schema/contract: bounded `validation_error_count`, safe error paths/types,
  and section-level contract audit when already generated.

If the local deterministic test confirms the finding, make the smallest
adjustment to the existing Product API job-outcome projection so it preserves
only the already-sanitized image-set audit fields. Keep the blocked job as the
diagnostic record. Do not copy the audit into the public Doc277 operation
record; its reason code and linked job ID remain the operation-to-job link.
This avoids widening the public operation contract or creating competing
diagnostic copies.

Do not persist raw remote JSON, the full prompt, model chain-of-thought,
provider error bodies, secrets, absolute paths, or user asset content. Do not
add a generic telemetry subsystem. Preserve Doc277's terminal failure and
single manual review action.

### 2.2 Character continuity classification

**Authority:** typed `visual_task_profile.subject_entities` for whether the
job depicts a character; Doc344's final accepted output and Doc322's binding
service remain the promotion authorities.

At the existing `_is_human_identity_context` entity-classification point,
accept the existing character types plus the exact Brain-emitted
`stylized_character` type (or normalize that one type there to `character`).
Use one implementation point; do not add separate booleans or persist a new
classification field. Preserve the E-Commerce exclusion, mock-generation
exclusion, template/reference policy, canonical review eligibility, planned
order, and explicit anchor precedence.

When the first one-image character job completes with an eligible canonical
output, the existing finalizer binds the first formally accepted output in
planned order. A subsequent project task freezes that anchor into its existing
reference plan. Manual unbind sets the existing state to `unbound` with
`auto_enabled=false`; thereafter the system must neither reuse that anchor nor
automatically bind a later output. Restoring continuity requires an explicit
user binding/replacement through the existing service. Manual replacement
continues through the existing binding service and version checks.

## 3. Allowed implementation boundary

Expected code boundary, subject to confirming the actual deployed/local
boundary:

- `alchemy_creative_agent_3_0/app/product_api/service.py` only where a focused
  regression covers its existing safe outcome projection;
- `alchemy_creative_agent_3_0/app/creative_core/central_brain.py` for the
  single `stylized_character` classification alias;
- focused existing tests for Brain blocked outcomes, planning failure
  projection, candidate eligibility, anchor binding, reuse, unbind, and
  replacement.

No file is authorized merely by being listed here. If diagnostics are already
persisted in the actual current path, do not add another copy; document the
evidence and narrow implementation to the missing VPS/code-version difference.
Expand scope only if the source trace proves the owning contract requires it.

## 4. Regression-first test plan

Write focused failing tests against the old code before implementation.

### Planning failure

1. A complete four-image plan with mismatched `image_count` reports the
   existing safe cardinality audit and still blocks before generation.
2. A four-item count with a three-entry `shot_plan` reports the actual safe
   counts and still blocks before generation.
3. A schema-invalid `image_set_plan` with valid cardinality reports bounded
   schema paths/types and still blocks before generation.
4. The durable blocked job retains the diagnostic and reason code; the public
   operation projection links the failed operation to the same job and remains
   limited to its safe failure code/action without leaking prompt/provider/
   private data.
5. A valid four-image plan preserves existing success semantics. No new retry,
   provider dispatch, output, or candidate is created by tests of blocked
   planning.

Use deterministic adapter/job/operation fixtures. Do not call the real Brain,
image provider, VPS, or generation UI as a debugger.

### Continuity

1. Given the exact profile type `stylized_character`, the existing candidate
   predicate is true when current policy otherwise allows it; the first
   eligible planned output binds through the existing Doc322 service.
2. The next project task freezes exactly that anchor in its reference plan.
3. Typed `character` behavior remains unchanged; missing typed profile,
   product-only/E-Commerce, mock generation, and explicit template opt-out
   remain excluded.
4. Manual unbind prevents both anchor reuse and automatic re-binding; explicit
   manual binding/replacement chooses only the user-selected canonical output
   and respects the existing binding version/CAS behavior. A later eligible
   generated output still cannot rebind automatically while `auto_enabled` is
   false.
5. Rendering mode and style remain prompt-owned. The test does not add prompt
   or realism guidance and does not alter same-batch transport semantics.

Reuse existing Doc322/Doc344 suites and add only the narrow missing cases.
Avoid duplicated tests for already covered manual binding behavior.

## 5. Verification and phased acceptance

### Phase A — source trace and regression proof

- Confirm current `main`, `origin/main`, and the deployed clean release agree;
  preserve unrelated working state.
- Trace adapter audit through durable job and operation storage to identify
  the exact loss point before choosing any persistence edit.
- Run the focused new regressions against old code and capture expected
  failures. Do not issue a real provider call.

### Phase B — bounded implementation and local verification

- Make one minimal fix at the proven diagnostic loss boundary and one
  classification alias correction.
- Run Brain adapter/runtime/blocked-job/Doc277 tests and the focused
  Doc322/Doc344 anchor/reuse/manual-action suite.
- Run `git diff --check`; review exact changed symbols and verify no unrelated
  worktree content was included.
- Independent read-only audit against this document and the frozen diff.

### Phase C — controlled VPS acceptance (separate authorization/gate)

Only after code audit and local regressions pass, plan a user-visible VPS
acceptance. It must use a fresh, explicitly authorized four-image planning
request only if needed and must record the sanitized Brain audit. Separately
verify first accepted anchor binding, subsequent frozen reference reuse,
manual unbind with no automatic re-binding, and explicit replacement. Preserve
existing evidence; do not retry or
mutate the user's prior project as an exploratory test. Deployment is not
included in this document authorization.

Phase A/B pass would be local implementation acceptance only. VPS acceptance
and deployment remain separate; none of these phases alone implies production
readiness.

## 6. Risk and rollback boundary

- Retaining safe diagnostic fields changes only failure observability; it
  must not alter the `planning_failed` lifecycle, failure reason, or
  generation decision.
- Adding the exact typed alias broadens only character continuity eligibility
  for that Brain entity type. Existing output review, binding integrity,
  project ownership, manual actions, E-Commerce exclusion, and opt-outs remain
  unchanged.
- Do not delete, rewrite, or backfill historical jobs, images, project
  bindings, or references. If the code fix is reverted, the existing blocked
  job remains blocked and any active manual binding remains authoritative.

## 7. Definition of done for this specification

This document phase is done when Doc345/Doc346 pass an independent read-only
audit for evidence fidelity, source/authority mapping, minimal scope, and
testability. The total defect-resolution objective remains open until the
future implementation phase passes its own focused tests and independent code
audit, followed by any separately authorized live acceptance/deployment gate.

## 8. Authorized implementation follow-up

The original document-only phase above was completed before this follow-up.
The user subsequently authorized implementation, code audit, local tests,
GitHub push, VPS synchronization, and one four-image real acceptance run using
the original fox-character instruction. This authorization advances the work
past the original Phase C gate; it does not waive the guarded VPS activation
workflow's maintenance acknowledgment or disk-reserve input.

The current patch is limited to the two owning code files and focused tests:
the Product API lifecycle projection retains only bounded, syntax-checked
image-set and contract audit fields already emitted by runtime, while Central
Brain recognizes the exact `stylized_character` type in its existing identity
predicate. Regression-first evidence showed both changes fail on the original
source and pass after implementation. Independent audit found the first
projection attempt insufficiently constrained; syntax filters, bounded counts,
explicit-null handling, and a Brain-to-project binding/reuse regression were
added before the final PASS.

Local verification: the exact Brain diagnostic projection regression passed;
the focused `stylized_character`/Doc73 set passed 14 tests; the Doc322
first-accepted binding, reuse, unbind, replace, and selection set passed 11;
the Doc277/Doc162 image-set planning set passed 19. A broader five-file run
reported 203 passed and one existing unrelated failure: the availability test
configures provider `deepseek`, but the unchanged provider implementation
rejects it as `unsupported_model_route` before the test's expected
`missing_credentials` branch. That fixture was intentionally left untouched to
preserve Doc346's scope.

## 9. Controlled deployment and live acceptance record

The user later confirmed the guarded activation's planned V1/V2 downtime and a
1 GiB minimum-free-space reserve. GitHub Actions workflow
`39869850814` completed successfully for commit
`83fea63c8a6acc0fa229eaf9802dab4727e3770c`. Its release checks reported the
active release as `/opt/alchemy-media-agent-releases/doc276-277-83fea63c8a6a`,
V1/V2 local and public health as 200, V3 project access protection intact, and
historical state unchanged.

After activation, one four-image request using the original fox-character
instruction was submitted through the V3 project's normal durable planning and
generation path. Planning operation `doc277_project_planning_a99c7de4bb`
completed and created job `job_40d8dcf33d`. The job finished as `generated`
with four candidates and four ready project outputs. Each output reported
`review_status=pass` and `verification_state=verified`. The continuity anchor
became active, cites `job_40d8dcf33d`, and resolves to the first candidate in
the job's candidate order (`candidate_2429afe2e4`). The pre-existing successful
job remained generated and the prior failed job remained blocked; neither was
rewritten or retried.

This live run verifies automatic first-candidate binding and four-image
delivery on the deployed build. It does not exercise live manual unbind or
replacement; those behaviors passed the focused local Doc322 tests. The
successful Brain response exposed no image-set or contract audit fields, so
the bounded diagnostic projection was verified by its focused local regression
rather than by this successful live run. No browser page was used for the live
request.

The implementation and controlled VPS activation phases are complete. The
broader test run retains the one unrelated provider-fixture failure recorded
above; no remaining integration dependency is known.
