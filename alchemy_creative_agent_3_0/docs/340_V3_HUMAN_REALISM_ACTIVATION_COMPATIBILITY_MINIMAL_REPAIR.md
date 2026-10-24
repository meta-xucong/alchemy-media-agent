# Doc340 — V3 Human Realism Activation Compatibility: Minimal Repair

Status: implementation contract. Document audit must PASS before source edits.

Baseline: `main` and `origin/main` at
`a3b1216d0870c3af8a6aa56b508c4f8750663ac6`.
The working tree already contains the separately requested private activation
failure receipt in `scenario_runtime/runtime.py` and its focused regression.
Preserve those changes and all pre-existing untracked files.

## 1. Total objective and current phase

**Total objective:** make V3's Human Realism activation plan, executor and
runtime agree on one frozen rendering decision, so a contradictory capability
proposal cannot stop image generation before a Provider request. Keep the
correction small, retain private failure diagnostics, and demonstrate the
photoreal-person, whole-image-stylized-person, and object-surface-artwork cases
through focused simulation and isolated local V3 real generation.

**Current phase:** freeze this contract and obtain an independent read-only
document audit. No compatibility code or real Provider call is authorized in
this phase. After document PASS, implement the bounded change, freeze the diff,
obtain independent code audit, run focused tests and no-provider simulations,
then run the three controlled local V3 real cases. Final acceptance requires
every phase; a document or test pass alone is not delivery acceptance.

## 2. Evidence and root cause

The recent V3 failure stopped during capability activation, before image
materialization. The runtime reported
`human_realism_execution_mismatch` and rebuilt an empty
`CapabilityRunResult`. The failed record did not preserve the frozen profile
or full activation plan, so the exact input branch that produced the mismatch
is not proven. The planner/executor path below is a source-verified mechanism
that can produce this class of mismatch and is the correction target.

The source contains two separate activation paths:

1. `CapabilityActivationPlanner._shared_required_capabilities` freezes
   Human Realism when a visible-person entity has affirmative
   `visible_person` or `real_human_output` evidence, unless the task profile
   explicitly marks the whole image stylized.
2. Model-proposed `required` capabilities are processed independently by the
   planner's requested-capability candidate path. That path can activate
   Human Realism without applying the same whole-image stylization rule.
3. The enforced Human Realism executor then vetoes a planned activation when
   the frozen intent says whole-image stylization.
4. `_validate_frozen_capability_execution` turns that executor outcome into a
   fatal runtime block. This produces no image request and gives the user no
   image to evaluate.

This is duplicated decision-making across planner and executor. More runtime
assertions cannot reconcile it; the decision must be normalized before the
executor runs. The existing runtime guard remains as protection for a genuine
contradiction or execution failure after normalization.

## 3. Authorities and conflict resolution

The frozen `VisualTaskProfile.rendering_intent` is the semantic authority.
The activation plan is the single execution authority derived from that
profile and the existing trusted template policy. An LLM-proposed capability
mode is evidence for planning, not permission to contradict the frozen
rendering intent.

The following existing rules remain in force:

- A visible person in a non-stylized whole image activates shared Human
  Realism, even if the Brain omits the capability.
- An explicit whole-image stylized intent leaves Human Realism inactive.
- Object-surface artwork does not make a photoreal whole image stylized.
- Brain-owned creative direction and canonical Provider prompts remain
  unchanged.

This document does not supersede Doc134's required-execution invariant. It
prevents the known contradictory plan from being constructed in the normal
planning path. Doc134's existing guard remains authoritative if a frozen plan
still says Human Realism is active while the frozen rendering intent says the
whole image is stylized, or if a required executor actually fails.

## 4. Minimal correction

### 4.1 Normalize the plan once

After merging trusted template requirements, Brain proposals, and the existing
shared visible-person rule, normalize `human_realism` against the frozen
profile:

| Frozen profile | Final plan |
| --- | --- |
| Visible-person entity with affirmative `visible_person` or `real_human_output` evidence; whole image not explicitly stylized | Active and required |
| Whole image explicitly stylized | Inactive with the existing `stylized_request` reason code |
| No typed visible-human evidence | Keep existing planner behavior |

Apply this normalization regardless of whether the candidate originated from
the template policy, a Brain `required` request, or automatic shared
activation. Do not add prompt matching, new classifiers, confidence
thresholds, fallbacks, capability modules, or a second plan.

### 4.2 Preserve the executor's existing conflict behavior

Do not change the Human Realism executor's existing frozen-style conflict
behavior. A normally normalized active plan is limited to a visible-person
profile whose whole-image rendering intent is not explicitly stylized; it
executes the existing style-aware guidance builder. If an inconsistent frozen
plan still marks Human Realism required while the frozen profile explicitly
marks the whole image stylized, preserve the existing structured
`frozen_rendering_intent_conflict` result with `applies=false`. When the plan
is inactive, the executor must not reactivate Human Realism through the legacy
keyword path. This keeps the planner as the normal decision authority and the
existing executor/runtime path as protection for stale or inconsistent plans.

### 4.3 Keep the existing execution guard

Keep `_validate_frozen_capability_execution` unchanged. With the plan
normalized, the ordinary stylized request no longer reaches the guard as an
active Human Realism requirement. If a stale or inconsistent frozen plan
still requires Human Realism for an explicitly stylized whole image, the
existing executor returns `applies=false`, which the existing guard blocks.
The guard also continues to block missing required execution. This preserves
Doc134 §3 items 2–3 and existing failure handling. Do not add another guard
or retry.

When the guard blocks, preserve the already-requested safe private diagnostic
summary (profile summary, planned capability IDs, Human Realism
result/reason, executor statuses and sanitized warning codes) without
returning it in public job metadata. The diagnostic is evidence only; it does
not introduce another gate or retry.

## 5. Scope and hard constraints

**Classification:** D0 / I2 / A1. The intended authority and behavior are
clear. I2 is warranted by the concrete planner/executor/runtime conflict. A1
is warranted because this changes a cross-module execution invariant.

**Allowed changes:**

- This document.
- Existing activation planner, Human Realism activation/execution path, and
  Scenario Runtime's redundant Human Realism block.
- Focused existing regression tests for planner, Human Realism, and runtime
  failure projection.
- The already present uncommitted private diagnostic receipt and its test;
  keep it private and avoid expanding its schema beyond the requested fields.

**Hard constraints:**

- One writer at a time; root `main` remains the only mainline checkout.
- Do not edit, clean, reset, or overwrite pre-existing untracked paths.
- No new capability/functionality module, new model/provider route, new retry,
  prompt patch, public response field, or broad refactor.
- No changes to V1, V2, VPS, GitHub, service operation, or deployment.
- Real tests must use an isolated local V3 storage root and bounded test inputs.
- Preserve the exact canonical Brain prompt and Provider behavior.
- Do not commit or push as part of this task.

**Source Fidelity:** no separate reference prototype is in scope. Current
`origin/main` and the cited V3 documents are the frozen source authority;
Doc120/117/134 govern the behavior mapping. Record
`SOURCE_FIDELITY_NOT_REQUIRED_NO_PROTOTYPE`; do not invent a source repository
or run generation from a historical checkout.

**Route provenance:** requested/observed child model and effort are not
available from this session's collaboration evidence. Record
`ROUTE_UNVERIFIED`; do not claim profile compliance. This does not replace the
independent audit requirement.

## 6. Focused regression and simulation

Use the smallest cases that prove the three contract branches:

1. **Planner:** a visible person plus explicit whole-image stylization and a
   Brain-proposed `human_realism=required` yields an inactive Human Realism
   plan, without raising.
2. **Planner:** a visible person with photoreal or non-stylized intent yields
   active required Human Realism even if the Brain proposal omits it.
3. **Object surface:** photoreal person plus stylized artwork scoped to an
   object surface keeps Human Realism active.
4. **Executor:** enforced active plan executes style-aware guidance; enforced
   inactive plan does not re-enable Human Realism from legacy keyword matching.
5. **Runtime:** when the frozen plan marks Human Realism inactive, a
   false/missing `applies` value does not block before image generation;
   when the frozen plan requires Human Realism, a false/missing execution
   result still blocks through the existing guard and failure handling.
6. **Privacy projection:** the private failure receipt serializes in the
   internal capability-run record and remains absent from public summary and
   lifecycle response.

Run focused deterministic tests first. No-provider simulation must prove the
resulting plan and executor behavior without creating image jobs or calling
Brain/Provider services. If any simulation creates durable jobs, outputs, or
external requests, stop and correct the test boundary before real validation.

## 7. Controlled local V3 real acceptance

Run one isolated local V3 job per case after all prior gates pass:

| Case | Required evidence |
| --- | --- |
| Photoreal visible person | Planning completes; Human Realism is active/applied; a real image Provider request reaches completion and persists an output. |
| Explicit whole-image stylized person | Planning completes; Human Realism is inactive; one requested output reaches completion and persists. |
| Photoreal person with object-surface artwork | Human Realism remains active/applied; the object artwork does not change whole-image rendering intent; one requested output persists. |

Run exactly one Job per case with `requested_image_count=1`, no manual restart
or retry, and the existing bounded automatic retry policy unchanged. Stop a
case after its terminal result; do not repeat a provider/network failure. For
each run preserve job ID, profile summary, activation plan, Human Realism
status/reason, Provider request boundary, persisted output count, and final
review status. These runs are local acceptance only and do not authorize a
VPS run, GitHub push, commit, or release. A provider/network/credential failure
is recorded as an external acceptance blocker, not converted into a code pass.

## 8. Audit and final acceptance gates

1. Independent document audit returns `PASS` on this frozen document before
   compatibility source edits.
2. Freeze the implementation diff and run independent read-only code audit.
3. Focused tests, syntax checks, and no-provider simulations pass.
4. All three controlled local real cases pass the table in §7.
5. Final report separates code quality, real-generation acceptance, route
   provenance, and notification status. Overall result is “ready for user
   acceptance” only when every required gate passes; otherwise list the exact
   remaining gate.
