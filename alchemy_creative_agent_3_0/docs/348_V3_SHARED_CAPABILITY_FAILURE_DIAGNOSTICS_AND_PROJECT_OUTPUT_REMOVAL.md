# Doc348 — V3 Shared Capability Failure Diagnostics and Project Output Removal

Status: implementation contract.

## 1. Objective and current phase

**Total objective:** prevent the recent V3 pre-provider failure from being
misdiagnosed as a Human Realism planning conflict, preserve enough safe private
evidence to locate the failing shared-capability code path, and ship the
previously requested project-output removal loading/projection correction.

**Current phase:** implement a bounded private diagnostic improvement and
finish the already-started frontend correction. This phase does not claim to
repair an unknown exception inside `VisualCapabilityClusterModule`; that
exception was not retained in the failed VPS job. A source-level repair of that
unknown exception requires evidence identifying its throw site.

## 2. Evidence and causal model

The VPS job `job_c3811e5d90` was blocked on 2026-10-23 before a Provider request.
Its private receipt records:

- frozen rendering intent `photoreal` / `none`;
- `human_realism` required and active in the frozen plan;
- the `visual_capability_cluster` executor failed without returning a result;
- no Human Realism guidance was available to the subsequent execution guard.

The deployed release `doc276-277-499ac057d03c` includes Doc340's planner
normalization. Therefore this incident is not evidence that the Doc340
stylized-request conflict has returned. The observed sequence is:

1. `SharedCapabilityModule.run` catches an exception from the visual cluster
   and creates an error result.
2. The shared runtime has no cluster facts containing required Human Realism
   guidance.
3. `_validate_frozen_capability_execution` correctly blocks the job because
   the frozen plan requires Human Realism.
4. The block is surfaced under the later `human_realism_execution_mismatch`
   code, which obscures that the cluster executor itself failed first.

The underlying exception message and stack were not persisted. The current
failure receipt reads warning metadata, while the exception type is stored on
the capability result metadata, so even that safe field is lost at projection.

### 2.1 Read-only VPS follow-up

After SSH access was confirmed, the active container and the original job were
read directly from the VPS. The active release is
`499ac057d03c62e5db8909e3dbccd183204e459b`; the failed job record confirms:

- top-level warning: `capability_activation_failed`, message
  `human_realism_execution_mismatch`;
- private activation diagnostic: `human_realism_execution.status` is
  `guidance_missing`, and its fallback `disabled_reason` is
  `reason_unavailable`;
- executor result: module `visual_capability_cluster`, status `error`, warning
  `capability_execution_failed`;
- no provider request started; persisted `capability_run.results` is empty, and
  the sanitized executor summary contains no exception type or source frame.

The container retained 120 log lines in the ten-minute interval around the
failure, but none contained a traceback or error entry; there are no application
log files under `/app`. The exact Python exception cannot be recovered from this
historical run. This confirms the gate's downstream error and the failing module,
but not the throw site. Do not weaken the required Human Realism guard. The
already-tested private type/frame instrumentation is still needed on the next
failure before a source-level correction can be selected safely.

## 3. Authorities and safety boundary

- The frozen activation plan remains the execution authority.
- A required Human Realism execution must not be silently skipped when its
  shared executor fails. Keep the existing fail-closed guard.
- The shared-module exception boundary remains responsible for converting an
  unexpected exception into a structured error result.
- Private diagnostics may record an allowlisted exception type and the final
  source frame (basename, line, function). They must not persist the raw
  exception text, prompt, Provider payload, or arbitrary filesystem path.
- This work does not add retries, fallback generation, new capability states,
  or changes to image prompts or Provider requests.

## 4. Minimal implementation

1. When `SharedCapabilityModule.run` catches an exception, add a sanitized
   final traceback frame to the existing result metadata. The exception class
   is already present there. Preserve the existing error result and warning
   code; do not duplicate diagnostics into warning metadata.
2. Extend the existing private activation-failure receipt to copy only the
   allowlisted exception class and sanitized source frame from the failing
   result metadata. Keep these fields out of public job and lifecycle
   projections.
3. Add a deterministic regression proving that a thrown exception becomes a
   failed capability result and that the private receipt captures the safe
   diagnostic fields without its message or raw path.
4. Complete the existing frontend removal correction: show an inline busy
   spinner on the clicked desktop/mobile action, update the project output
   projection from the successful response before refreshing, and exclude
   unselected/rejected outputs from the mobile final-output list. Keep the
   server's history and image files untouched.

## 5. Scope and non-goals

Allowed source changes:

- `alchemy_creative_agent_3_0/app/shared_capabilities/base.py`
- `alchemy_creative_agent_3_0/app/scenario_runtime/runtime.py`
- focused shared-capability/runtime tests
- `src_skeleton/app/static/app.js`
- `src_skeleton/app/mobile_static/mobile.js`
- the existing project reference UI regression test
- this document

Non-goals:

- guessing or masking the unobserved exception's source-level cause;
- weakening required Human Realism activation or the execution guard;
- launching a real image-generation job as an exploratory debugger;
- changing V1/V2, prompts, routing, provider behavior, retry budgets, or storage;
- cleaning unrelated workspace changes or temporary data.

## 6. Acceptance evidence

1. A synthetic shared-module exception produces a failed result with safe
   exception type/source-frame metadata; the private blocked receipt contains
   those fields and excludes raw exception text/path.
2. The existing active-Human-Realism missing-execution guard still blocks.
3. Focused project-output UI tests prove desktop/mobile busy state and that a
   successful removal disappears from the project projection without deleting
   the historical image.
4. Independent read-only audit returns `PASS` on the frozen diff.
5. Focused tests and `git diff --check` pass.
6. GitHub and VPS synchronization occur only after the evidence above passes.

Passing these checks closes the opaque-diagnostic and project-output UI
defects. It does **not** establish that the unknown visual-cluster exception
cannot recur; after this instrumentation identifies its source frame, that
specific defect must be corrected and validated before claiming the generation
failure itself is eliminated.

## 7. Same-prompt reproduction update (2026-10-23)

The first local real run used an older fox-character prompt from a temporary harness, not the prompt stored on the failed VPS job. It is retained as historical evidence but does not count as reproduction. The exact original `user_input` was then read from `job_c3811e5d90` and used verbatim in a new isolated local run.

- The exact-prompt run generated one real `gpt-image-2` output. Its `capability_run` completed, `visual_capability_cluster` succeeded, and the Human Realism guidance reported `applies=true`.
- The original VPS job had `project_mode=true`, mode `campaign_poster`, variation `delivery_suite`, and one selected prior output. The successful isolated run used a fresh project with mode `freeform`, variation `auto`, and no selected prior output.
- A provider-free simulation then combined the original project-context snapshot, mode, variation, selected-output metadata, active capability IDs, and frozen rendering/age summary with the successful run's Brain profile and prior capability results. It also completed with Human Realism guidance applied. This is a bounded comparison, not a byte-for-byte replay of the original Brain response or its full runtime inputs.
- The historical VPS receipt still identifies the failing executor as `visual_capability_cluster` with warning `capability_execution_failed`; it contains no exception type, traceback frame, or message. The relevant visual-cluster source files are unchanged between deployed commit `499ac057d03c62e5db8909e3dbccd183204e459b` and local `HEAD`.

**Conclusion:** the same prompt can pass with Human Realism active, and the available context simulation also passes. The original exception is therefore not reproducible from the retained evidence. No source-level root-cause fix is supported yet. Keep the fail-closed execution guard and the minimal private exception type/source-frame instrumentation. Do not claim the generation failure is fixed or publish this diagnostic-only change as the root-cause repair. A source fix and final GitHub/VPS release remain pending a captured exception frame from the failing V3 executor path.