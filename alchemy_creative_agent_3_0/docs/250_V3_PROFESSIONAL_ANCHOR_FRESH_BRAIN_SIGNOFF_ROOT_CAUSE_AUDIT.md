# Doc250 — V3 Professional Anchor Fresh Brain Signoff Root-Cause Audit

## Scope

This document is a theory-first audit for the blocked Absolute Portrait
Realism controlled comparison. It does not authorize code changes, prompt
changes, route changes, retries, slot writes, or new image generation.

The observed blocker is upstream of MCP handoff creation:

```text
fresh standard_front planning
  -> ScenarioRuntime requires professional_anchor_view_decision_v3
  -> Remote Brain canonical prompt finalizer does not provide an acceptable receipt
  -> runtime blocks before Provider/MCP pixels
```

The owning layer is Brain / ScenarioRuntime professional anchor signoff, not
Doc248 Absolute Portrait Realism, FormalSlotAcceptanceCore, receipt lifecycle,
MCP recovery, or Provider pixel rendering.

## Evidence

### Gate1 controlled comparison

The comparison worktree was based on `origin/main@6752e62`.

Gate0 passed with:

- canonical source asset: `v3_asset_054b1c4728614187`
- source hash:
  `afe6ac2e7b116e0b1802cf44d63790dc51fe32a686796204476db70b0991b35d`
- view: `standard_front`
- capture scope: `character_card_face_identity`
- intended route: explicit trusted MCP

Candidate1 Gate1 did not create a job/handoff/output. Two inline harness
attempts failed before Product API execution because the validation harness
import path did not resolve `app.providers`. That is closed as a harness
failure and is not a candidate attempt.

The exact-bound source-job check then found no prior signed MCP source job for
the current binding. The only old signed job found, `job_8330259dfb`, has a
`v3_professional_anchor_view_decision_v3` receipt but is not an exact-bound MCP
source:

- `generation_channel = provider`
- `mcp_operation_id = null`
- missing current `source_sha256` binding
- missing current rendering contract
- different project id
- empty operation context

Therefore it cannot be reused for the current MCP candidate.

### Previous Doc248 attempts

Two earlier absolute-realism attempts remain append-only evidence:

1. `job_8330259dfb` reached Remote Brain finalizer and returned a valid
   `professional_anchor_view_decision_v3`, plus human realism, reference
   channel, developmental age, developmental presence, and provider-admission
   signoffs. It then failed later on the Provider path.
2. `job_f8341ed806` stopped earlier with:

```text
remote_creative_brain_outcome.state = blocked
reason_code = remote_creative_brain_prompt_signoff_unavailable
outcome_class = remote_prompt_signoff_unavailable
llm_used = true
fallback_used = false
remote_provider_available = true
required_failures = portrait_identity, reference_channel_policy, human_realism
generation_channel = provider
professional_reference_stage = standard_front
professional_anchor_capture_scope = character_card_face_identity
```

It produced no planning result, generation result, handoff, output, Vision
inspection, Doc248 proof, FormalSlotReceipt, or slot write.

## Code path traced

### 1. Product API / trusted host context

`V3ProductApiService.create_professional_anchor_preparation_job()` is the
server-owned entry for professional Face Identity anchor preparation. It binds:

- `professional_anchor_pack_preparation`
- `professional_reference_stage`
- `professional_anchor_capture_scope`
- `professional_anchor_reference_assets`
- `generation_channel`
- `mcp_operation_id`

When `generation_channel="mcp"` and a `stage_plan_source_job_id` is supplied,
Doc249 can inject trusted reuse metadata, but only when the source and current
binding match exactly. The public route cannot set the internal trusted reuse
flag.

### 2. ScenarioRuntime requirement construction

`ScenarioRuntime` projects the professional planning metadata into
`canonical_prompt_context.professional_anchor_view_decision`.

For `standard_front + character_card_face_identity`, the required receipt is
strict:

- `contract_version = v3_professional_anchor_view_decision_v3`
- `owner = remote_v3_llm_brain`
- `target_view_role = standard_front`
- `capture_presentation = neutral_identity_evidence_capture`
- `capture_continuity = establish_neutral_capture`
- `capture_scope = character_card_face_identity`
- `framing_standard = consistent_head_and_upper_shoulders_reference_crop`
- `crop_policy = head_top_margin_full_face_neck_and_upper_shoulders_visible`
- `torso_scope = upper_shoulders_only_no_half_body_or_big_head_crop`
- `aspect_ratio_standard = honor_frozen_rendering_size_as_reference_card_aspect_ratio`
- `source_viewpoint_inheritance = identity_only_do_not_inherit_source_pose_angle`
- `front_pose_normalization = normalize_to_symmetric_camera_facing_front`
- `face_axis_alignment = face_midline_vertical_eyes_level_nose_centered`

This confirms the local runtime does construct the correct “must sign” context.

### 3. Brain prompt schema and adapter validation

`build_remote_payload()` includes `professional_anchor_view_decision` in the
canonical provider prompt return schema only when the required context is
present and valid.

`V3LLMBrainAdapter.finalize_canonical_provider_prompts()` then checks whether
every expected output carries a matching `professional_anchor_view_decision`.
If not, it may apply Doc249 exact-bound trusted reuse; otherwise it raises
`BrainProfessionalAnchorViewDecisionMissing`.

This confirms the adapter is intentionally fail-closed. Missing signature is
not allowed to fall through to Provider/MCP.

### 4. Runtime failure projection

If the finalizer still lacks the signed receipt after the one same-context
re-answer path, `ScenarioRuntime` maps it to:

```text
reason_code = professional_anchor_view_decision_missing
outcome_class = remote_prompt_signoff_unavailable
```

For broader signoff failures, the safe public outcome may show
`remote_creative_brain_prompt_signoff_unavailable`.

## Root-cause tree

### Branch A — Remote Brain did not produce the receipt

Most likely for `job_f8341ed806` and the fresh comparison path.

Evidence:

- Runtime had the server-owned standard_front requirement.
- Adapter requires the exact receipt and fail-closes.
- Remote outcome says Brain was used and remote provider was available.
- No Provider/MCP output exists.

Correction direction:

- Repair the Brain prompt/output contract or remote Brain behavior so fresh
  `standard_front + character_card_face_identity` returns the required
  `professional_anchor_view_decision_v3`.
- Do not use prompt wording tweaks or retries as a substitute.

### Branch B — Local ScenarioRuntime or adapter dropped a valid receipt

Possible but not proven by current evidence.

Required proof before code changes:

- Capture a raw remote response containing a valid v3 decision.
- Show that `V3LLMBrainAdapter` rejects or drops it incorrectly.

Correction direction if proven:

- Fix only the Brain / ScenarioRuntime adapter layer.
- Preserve fail-closed validation for malformed, missing, duplicate, wrong
  owner/version/status, or mismatched receipts.

### Branch C — Capability activation contract drift

Possible for `job_f8341ed806` because required failures are:

```text
portrait_identity
reference_channel_policy
human_realism
```

This may mean the capability activation plan or canonical prompt finalizer no
longer receives enough active capability context to emit all required receipts,
or that the failure is being collapsed into required capability failures after
prompt-signoff failure.

Correction direction if proven:

- Audit the capability activation plan and `active_semantic_capability_contracts`
  that enter `canonical_prompt_context`.
- Repair capability activation projection if it is missing or stale.
- Do not move capability-specific logic into Doc248 or Formal Core.

### Branch D — Exact-bound reuse precondition missing

Confirmed for the current comparison Gate1.

Doc249 reuse is structurally correct, but the current run has no acceptable
source job. Old Provider jobs cannot be treated as MCP source jobs.

Correction direction:

- Either create a fresh valid remote Brain signature for the current MCP
  operation, or obtain a new trusted signed source that already contains the
  exact project/source/view/capture/reference/rendering/candidate/operation
  binding.
- Do not broaden reuse binding.

## Authoritative rule

Fresh standard_front planning must succeed by obtaining a real
`professional_anchor_view_decision_v3` from the Remote Brain, or by using a
trusted exact-bound reuse source that already belongs to the same operation
contract.

The following are explicitly forbidden:

- using Provider `job_8330259dfb` as MCP source;
- fabricating a local Brain signature;
- lowering prompt, gate, threshold, budget, or retry constraints;
- switching routes because Doc248 is enabled;
- letting user metadata set trusted reuse;
- turning `professional_planning_metadata` into a signed decision;
- creating a job/handoff/output while the signoff authority is unresolved.

## Red-test plan before any code change

### A. Fresh Brain signoff contract

1. Build a `standard_front + character_card_face_identity` runtime request with
   active `portrait_identity`, `reference_channel_policy`, and `human_realism`.
   Assert the finalizer request contains the complete
   `professional_anchor_view_decision_v3` requirement.
2. Fake a remote Brain response that omits the receipt. Assert the result blocks
   as `professional_anchor_view_decision_missing` before Provider/MCP.
3. Fake a remote Brain response with a valid v3 receipt. Assert the runtime
   plans successfully and audit records `professional_anchor_view_decision_signed`.
4. Fake v2/wrong owner/wrong status/duplicate/mismatched capture/framing/pose
   receipts. Assert fail-closed.

### B. Capability activation projection

1. Assert fresh professional standard_front planning passes the active
   capability contract set into canonical prompt context.
2. Remove `portrait_identity`, `reference_channel_policy`, or `human_realism`
   from the activation plan. Assert a stable, specific blocker rather than a
   generic prompt-signoff collapse.
3. Assert Doc248 does not change capability activation, transport selection,
   or required Brain signoff semantics.

### C. ScenarioRuntime / adapter loss test

1. Provide a raw remote response containing the exact v3 decision.
2. Assert `V3LLMBrainAdapter` preserves the receipt into canonical prompts and
   audit metadata.
3. Assert `ScenarioRuntime` does not drop it when building `planning_result` or
   `frozen_remote_creative_brain`.

### D. Exact-bound reuse guard

1. Keep Doc249 tests: valid exact-bound reuse passes.
2. Add fixture using the real shape of `job_8330259dfb`; assert it is rejected
   for MCP reuse because it lacks MCP operation/rendering/current source hash
   binding and has a different project.
3. Assert ordinary Provider continuation still does not invoke MCP reuse.
4. Assert public payload and user metadata cannot set trusted reuse.

### E. No-generation invariant

For every failure case above, assert:

```text
jobs may be planned only when Brain signoff succeeds;
handoffs = 0;
outputs = 0;
Provider/MCP materialization not called;
Formal Core and slot lifecycle untouched.
```

## Minimal repair candidates

### Candidate 1 — Remote Brain schema/prompt contract repair

If tests show the remote payload schema is under-specified or no longer forces
the signed field strongly enough, repair only `llm_brain/prompts.py` and
adapter tests. This is the preferred path when the remote model is capable but
not reliably emitting the field.

### Candidate 2 — ScenarioRuntime capability projection repair

If tests show `canonical_prompt_context` lacks active capability context or
confuses required capability failures with prompt-signoff failure, repair
`scenario_runtime/runtime.py` or the capability activation projection owning
layer. Keep Doc248 and Formal Core untouched.

### Candidate 3 — Exact-bound signed-source creation flow

If fresh remote Brain truly cannot emit the receipt in the current environment,
add a separate trusted source-generation/approval flow. It must produce a new
signed source job with the exact MCP binding before candidate1 creation. This
is not a shortcut around Brain; it is a way to acquire the missing authority.

## Current stop condition

The current controlled comparison remains blocked:

```text
blocker = no_exact_bound_signed_mcp_source_job
jobs = 0
handoffs = 0
outputs = 0
```

No further candidate1, candidate2, candidate3, Provider, MCP, slot, or receipt
action is allowed until a separate Brain signoff repair or new trusted signed
source is explicitly approved.
