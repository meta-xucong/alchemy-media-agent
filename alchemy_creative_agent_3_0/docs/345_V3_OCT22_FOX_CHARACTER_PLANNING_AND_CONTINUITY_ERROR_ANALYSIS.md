# Doc345 — V3 2026-10-22 Fox Character Planning and Continuity Error Analysis

Status: **Evidence analysis complete; implementation and verification are recorded in Doc346.** This report
separates the blocked planning operation from the continuity-anchor omission.
The VPS evidence identifies the failed contract section, but does not retain
the exact invalid field/value. Read-only SSH verification confirmed the active
release is the same clean source revision reviewed locally.

## 1. Objective and boundaries

Analyze the V3 failure reported for the prompt beginning “9:16 竖版，高精度
3D CG 东方幻想狐妖女性角色海报”, explain why four-image planning stopped,
determine whether the first accepted character output became the project
continuity anchor, and prepare a minimal correction model.

This is **V3 Foundation** work: Brain contract handling and cross-job identity
continuity are shared workflow capabilities. The fox-woman prompt is evidence
and a regression fixture only; it must not create a fox, fantasy, poster, or
General Template-specific branch. The failure occurred under
`general_template`/`campaign_poster`; it does not authorize scenario-specific
deliverables in General Template.

This phase is read-only investigation and documentation. It does not change
code, re-run image generation, create jobs/outputs, alter VPS state, deploy,
commit, or push. The pre-existing untracked validation directories and active
worktree were preserved.

## 2. Executive findings

1. **Four-image task: confirmed pre-generation planning rejection.** VPS
   operation `doc277_project_planning_f4498b2317` ended as failed and attached
   blocked job `job_9a0a440af4`, with
   `remote_creative_brain_image_set_plan_invalid`. The Brain section
   `image_set_plan` was rejected before image generation. The job has no
   generation result and zero outputs. No evidence indicates a Provider
   dispatch for this job.
2. **Exact malformed field: not recoverable from retained VPS evidence.** The
   durable operation/job record gives the reason code but not the sanitized
   cardinality/schema audit that would distinguish the causes. A count or
   shot-plan mismatch is plausible, not proven. Schema/shape validation is
   another supported path to the same section rejection.
3. **Continuity: first output was not bound.** The matching project had no
   selected output and the private anchor state was `none`; first output
   metadata recorded `doc322_auto_anchor_candidate=false`. Its typed profile
   classified the principal as `stylized_character`. The current local
   `_is_human_identity_context` whitelist does not include that exact type, so
   this character-classification check fails despite Doc344's style-independent
   contract. This is a confirmed code gap and a strong explanation for the
   false candidate, but not proven to be the only failed candidate condition:
   the available VPS evidence does not independently establish mock status or
   every reference-chain policy input. It is separate from the planning error.
4. **Manual controls remain a separate contract.** The supplied runtime
   evidence does not establish that manual unbind/replacement was broken.
   Doc344 and Doc322 already define those actions and their binding authority;
   this fix should not rewrite them.

## 3. Runtime evidence

All timestamps below are the durable-record UTC values; China Standard Time is
UTC+8 (the two operations therefore occurred early on 2026-10-23 local time).

| Record | Observed facts | Interpretation |
|---|---|---|
| Project `project_765c4d2422` | Name starts with the supplied 9:16 3D CG fox-character title; created `2026-10-22T19:11:03Z`, updated `2026-10-22T19:37:58Z`. | Identifies the project under review. |
| First operation `doc277_project_planning_a175446d2d` | Opened `19:11:09Z`; completed with `job_0383310299`. | Initial planning/generation path completed. |
| First job `job_0383310299` | Generated, sequence 1, requested count 1, `general_template`, `campaign_poster`, continuation `format_layout_adaptation`; one canonical output `v3_output_768a8170608c493eab86`. | This is the first image that could have become the project anchor, subject to the existing final acceptance rules. |
| Second operation `doc277_project_planning_f4498b2317` | Opened `2026-10-22T19:34:31Z`; failed at `19:37:58Z`; failure code `remote_creative_brain_image_set_plan_invalid`; linked job `job_9a0a440af4`. | Brain planning failed terminally; this is not a browser polling timeout. |
| Second job `job_9a0a440af4` | Blocked, sequence 2, requested count 4, same template/mode, continuation `delivery_suite`; `capability_status=failed`; `generation_result_present=false`; output count 0. | No image set reached the generation stage. |
| Brain outcome/lifecycle failure | `state=blocked`, reason code above, `llm_used=true`, `fallback_used=false`. | The remote Brain was called; no deterministic creative fallback silently continued. |
| Anchor state | Project selected-output list empty; `doc322_continuity_anchor_bindings_v1` had `state=none`, `auto_enabled=true`; first output candidate bit false. | Automatic binding did not occur. |
| First job profile/reference | `subject_entities` included `stylized_character`, `generic_object`, and `scene`; second job had no active/identity reference and no frozen continuity anchor. | The second task did not reuse a project anchor because none existed. |

The second job's aspect metadata was `requested_aspect_label="自动"` even
though the title contains 9:16. This discrepancy is recorded for completeness,
but there is no evidence that it caused the Brain rejection; it is not included
in the proposed fix.

## 4. Planning failure: code-path reconstruction

The observed reason maps to this path in the current V3 code:

```text
Project planning operation
  -> create/plan Product Job
  -> remote Brain returns image_set_plan
  -> adapter validates complete-set contract
  -> ScenarioRuntime sees image_set_plan in
     remote_contract_rejected_sections
  -> blocked job with remote_creative_brain_image_set_plan_invalid
  -> durable Project planning operation becomes planning_failed
```

Relevant source points at baseline `081eb99f454b2034a2974894d9eb0b4417c4e03a`:

- `app/llm_brain/adapter.py`, `_validate_remote_contract` (around line 1613):
  for a complete image set, the raw remote `image_count` and non-empty
  `shot_plan` cardinality are compared with the frozen expected count before
  contract fallback can mask the remote section.
- `app/llm_brain/adapter.py`, `_image_set_cardinality_audit` (around line
  2898): records expected count, remote count, shot-plan count, and validity.
- `app/llm_brain/adapter.py`, `_merge_validated_section_with_audit` (around
  line 4687): a section can also be rejected by `BrainRunResult` schema
  validation after cardinality passes.
- `app/scenario_runtime/runtime.py`, `_run_remote_creative_brain` (around
  lines 1498–1504): rejected `image_set_plan` is raised as the observed
  reason code.
- `src_skeleton/app/main.py`, `_v3_blocked_planning_failure_code` (around line
  942): keeps the trusted job-bound Brain reason in the operation failure.
- `app/project_mode/service.py`, durable planning operation lifecycle follows
  Doc277: a terminal planning failure exposes the safe manual review action;
  it does not generate or retry automatically.

The adapter and runtime have allowlisted helpers for safe cardinality and
validation diagnostics. `ScenarioRuntime._remote_creative_brain_block` places
these summaries in the typed safe outcome. Read-only SSH verification found
the current active VPS release at
`/opt/alchemy-media-agent-releases/doc276-277-081eb99f454b`, revision
`081eb99f454b2034a2974894d9eb0b4417c4e03a`, with a clean checkout matching
local `main`. In this source,
`V3ProductApiService._public_remote_brain_lifecycle_outcome` and the blocked
job-status projection do not copy `remote_image_set_cardinality_audit` or
`remote_image_set_validation_audit`. Thus, **if this release handled the
historical task**, this projection explains why those diagnostics would be
absent from the durable blocked-job outcome. The evidence does not tie the
historical job to the exact release/process serving it at the time, so this is
a confirmed current-code loss path and a plausible explanation of the
historical record, not a proven historical process-level cause. The retained
operation record preserves the reason code and job link, but cannot
distinguish whether the remote response had (a) the wrong `image_count`, (b)
too few/many shot directions, (c) a malformed schema field, or (d) another
contract-shape problem.

### Cause confidence

| Statement | Confidence |
|---|---|
| The `image_set_plan` section failed its existing remote contract acceptance. | Confirmed by the reason code and current branch mapping. |
| The current reviewed control flow raises on this planning contract error before image dispatch; the stored job has no generation result or outputs. | Confirmed for the reviewed source and stored result; the historical serving process is not independently linked to the current release. |
| The remote image count or shot-plan length was wrong. | Plausible, not confirmed; audit values were absent. |
| A mismatch between requested `4` and frozen Brain expected count caused it. | Not proven. The job count is four, but the actual Brain audit was not retained. |
| The `自动` aspect label caused the error. | Unsupported; do not attribute causality. |
| Retrying or relaxing validation is needed. | Unsupported and contrary to the fail-closed contract. |

## 5. Continuity failure: code-path reconstruction

Existing Doc344 says character continuity is style-independent, and its tests
cover photo, anime/stylized, and illustration rendering intent. The current
implementation still relies on exact typed-entity membership:

- `app/creative_core/central_brain.py`, `_llm_profile_subject_entity_types`
  (around line 1531) returns normalized entity names without alias
  normalization.
- `_is_human_identity_context` (around line 1520) accepts
  `person`, `human`, `character`, `portrait`, `portrait_subject`, and
  `human_subject`, with an E-Commerce exclusion. It omits
  `stylized_character`.
- `doc322_auto_anchor_candidate` is set only when this predicate passes (and
  generation is non-mock and the existing reference-chain policy allows it).
- `project_mode/service.py`, `_maybe_claim_continuity_anchor` (around line
  14441) returns immediately when that stored candidate bit is not true; the
  existing canonical final-delivery projection and binding service are never
  reached for automatic promotion.

The remote first job's typed principal is exactly `stylized_character`, and
the stored candidate bit is false. This type mismatch is one definite failed
eligibility condition and strongly explains the observed missing candidate.
Since the stored bit is a conjunction and the VPS record does not prove all
its other inputs, do not attribute the whole project outcome to this condition
alone. Doc344's rendering-mode test does not by itself establish coverage of
this distinct entity-type spelling. The exact positive regression must use the
Brain profile type `stylized_character` and assert the persisted binding, not
merely the same-batch image-edit chain.

Because no anchor was bound, the next job's frozen reference plan correctly
contained no anchor under Doc277/Doc322 authority. This explains why subsequent
images could lack cross-job continuity. It cannot explain why the planning
operation itself failed: automatic anchor binding occurs after output review,
whereas the second job was blocked during planning and produced no output.

## 6. Root-cause model

| Finding | Owning layer | Authoritative state/rule | Minimal correction |
|---|---|---|---|
| Four-image plan rejected with weak postmortem detail | Brain contract diagnostics through the blocked-job outcome projection | Existing adapter validation and fail-closed `image_set_plan` contract | Preserve the already-sanitized cardinality/schema audit on the blocked job only; keep the Doc277 operation projection limited to its safe failure code and job link. Do not change acceptance criteria until evidence proves the validator wrong. |
| Stylized character did not qualify for auto-anchor | Shared Foundation identity classification in Central Brain | Typed `subject_entities` plus Doc322 binding service and Doc344 first-accepted final-output rule | Recognize `stylized_character` in the existing character-context predicate (or normalize it to the existing `character` alias at that single authority), then retain the current binding service unchanged. This repairs a confirmed missed eligibility class; confirm other candidate conditions before assigning it as the sole incident cause. |

No additional state flag, retry branch, review gate, provider fallback, project
registry, or General Template behavior is required.

## 7. Existing protections to preserve

- `image_set_plan` contract failure remains fail-closed; no silent local plan
  substitution or provider dispatch after invalid Brain output.
- No automatic Brain retry is added. A user-triggered manual retry is a new
  explicit planning action under Doc277.
- Diagnostics are bounded and allowlisted. Never persist raw prompt, full
  remote Brain response, provider-native error, credentials, private paths, or
  unfiltered validation payload into the public operation projection.
- Project anchor is still selected only after existing final-output review and
  canonical binding checks; the first formally accepted output in planned
  order remains authoritative under Doc344.
- Manual replacement/unbind stays owned by Doc322's binding service and keeps
  its current compare-and-swap/version semantics.
- Character identity handling stays in V3 Foundation. No style prompt, fox
  heuristic, poster package, or domain-specific rule is added to General
  Template.

## 8. Documents and phase result

- This report is the runtime/code diagnosis and evidence ledger.
- [Doc346](346_V3_BRAIN_PLAN_DIAGNOSTICS_AND_STYLIZED_CHARACTER_ANCHOR_MINIMAL_FIX.md)
  is the implementation-ready correction and acceptance plan.
- Existing authorities: Doc277 (durable planning operation), Doc322
  (continuity anchor/reference plan), Doc344 (first accepted character anchor),
  AGENTS.md (code-first, theory-first and Foundation/template separation).

Documentation phase result at the time this report was prepared:
**ready for independent audit**. The later user-authorized implementation,
local test, and audit status is recorded in Doc346 §8. GitHub/VPS release and
the live four-image acceptance are still pending; this report's historical
documentation-phase status does not describe those later phases.
