# Doc249 — V3 Professional Anchor View Brain Signoff Contract Recovery

## Purpose

This document records the correction model for the blocked
`standard_front + absolute_portrait_realism_required` controlled test.

The observed failure is not an Absolute Portrait Realism module failure. The
run stopped before planning, MCP handoff creation, Provider pixels, shared
Vision, Doc248 proof, Formal Core, receipt persistence, or slot activation.

The owning layer is the Brain / ScenarioRuntime professional anchor-view
signoff contract.

## Intended behavior

A professional Face Identity `standard_front` candidate must receive a signed
Brain decision before any image transport runs:

```text
source asset + standard_front + character_card_face_identity
  -> remote Brain signs professional_anchor_view_decision_v3
  -> provider/MCP plan materializes one candidate
  -> shared Vision and Enhanced proof review the output
  -> Formal Core can later select a winner after three reviewed candidates
```

The signed decision is not a prompt hint. It is the authority that freezes the
professional face-view contract: view role, capture scope, framing standard,
crop policy, torso scope, aspect ratio standard, source viewpoint inheritance,
front pose normalization, and face-axis alignment.

## Observed mismatch

The controlled Doc248 comparison run produced two append-only blocked jobs:

1. `job_a5d755a4a7` used a non-canonical short preparation intent and stopped
   before MCP.
2. `job_6639e9aaa1` used the canonical preparation intent and still stopped
   before MCP.

For the canonical job, runtime metadata shows:

```text
remote_creative_brain_outcome.state = blocked
reason_code = professional_anchor_view_decision_missing
llm_used = true
fallback_used = false
remote_provider_available = true
required_failures = portrait_identity, reference_channel_policy, human_realism
generation_channel = mcp
professional_reference_stage = standard_front
professional_anchor_capture_scope = character_card_face_identity
professional_absolute_portrait_realism_required = true
```

There was no `planning_result`, `generation_result`, handoff, output, Vision
inspection, Doc248 proof, FormalSlotReceipt, or slot write.

## Evidence from old successful chain

The previous MCP success chain contains a signed
`professional_anchor_view_decision_v3` with:

```text
target_view_role = standard_front
capture_presentation = neutral_identity_evidence_capture
capture_continuity = establish_neutral_capture
capture_scope = character_card_face_identity
framing_standard = consistent_head_and_upper_shoulders_reference_crop
crop_policy = head_top_margin_full_face_neck_and_upper_shoulders_visible
torso_scope = upper_shoulders_only_no_half_body_or_big_head_crop
aspect_ratio_standard = honor_frozen_rendering_size_as_reference_card_aspect_ratio
source_viewpoint_inheritance = identity_only_do_not_inherit_source_pose_angle
front_pose_normalization = normalize_to_symmetric_camera_facing_front
face_axis_alignment = face_midline_vertical_eyes_level_nose_centered
status = approved
owner = remote_v3_llm_brain
```

That chain reached MCP materialization and output metadata. The current chain
does not reach those phases because the same class of signed decision is
missing.

## Layer classification

### Core

Formal slot acceptance remains unchanged:

```text
three reviewed candidates -> shared review -> explicit ranking -> winner -> FormalSlotReceipt
```

Doc249 must not modify `FormalSlotAcceptanceCore`, receipt activation rules, or
slot projection.

### Enhanced

Doc248 Absolute Portrait Realism remains a hot-pluggable Enhanced profile. It
can request candidate-level realism proof after an image exists. It cannot
select transport, synthesize Brain signoff, or repair planning.

### Auxiliary / Brain contract

The failure belongs to Brain / ScenarioRuntime planning authority. Any recovery
must preserve the signed Brain decision contract and fail closed when the
source binding is not exact.

## Conflict rules

1. The local V3 runtime requires a signed `professional_anchor_view_decision_v3`
   for professional `standard_front`.
2. Fresh remote Brain planning may fail to return that signed decision even when
   the remote provider is available.
3. Old successful outputs may contain a valid signed decision, but reusing it is
   safe only when every binding matches the current request.
4. It is not safe to:
   - lower prompt, realism, route, or review gates;
   - auto retry the remote Brain;
   - fabricate a local Brain decision;
   - treat `professional_planning_metadata` as a signed decision;
   - let user metadata enable the path;
   - mix a signed decision from a different source, project, view, capture
     scope, reference contract, rendering contract, or operation context.

## Candidate correction models

### Model A — Local request/schema/adapter contract drift

Use this model if code audit or tests prove the local Brain request, prompt
schema, adapter validation, or ScenarioRuntime audit logic is rejecting a valid
remote Brain answer.

Allowed fix:

- Repair only the Brain / ScenarioRuntime owning layer.
- Add reverse tests proving malformed or unsigned decisions still fail closed.
- Do not touch Doc248, Formal Core, MCP recovery, prompts, thresholds, budgets,
  retries, or slot lifecycle.

### Model B — Exact-bound signed-decision reuse

Use this model if the remote Brain simply does not currently produce the needed
decision for fresh planning, but a prior trusted signed decision exists for the
same professional face-view contract.

Allowed fix:

- Add an Auxiliary reuse adapter that imports a prior signed
  `professional_anchor_view_decision_v3` only when all bindings match:
  project, source asset, source hash, view role, capture scope, reference
  semantics, rendering contract, candidate contract, and operation context.
- Preserve provenance that this is trusted reuse, not a new remote Brain
  signature.
- Fail closed for missing fields, wrong version, wrong owner, wrong status,
  stale binding, mismatched source, mismatched view, mismatched capture scope,
  mismatched rendering, mismatched candidate contract, or untrusted provenance.

Non-goals:

- No broad plan reuse.
- No prompt rewrite.
- No provider/MCP route switch.
- No Doc248 proof changes.
- No output or slot mutation during contract validation.

## Required tests

The repair must include focused tests for:

1. Old valid signed decision still passes.
2. Fresh missing decision reproduces a stable blocked result.
3. Valid exact-bound reuse passes.
4. Wrong source, project, view role, capture scope, version, owner, status,
   reference contract, rendering contract, candidate contract, or operation
   context fails closed.
5. Ordinary user metadata cannot forge reuse or absolute realism activation.
6. Doc248 remains only an Enhanced proof module.
7. Formal Core, receipts, slot lifecycle, MCP recovery, prompts, thresholds,
   budgets, and retries remain unchanged.

## Acceptance

After the correction passes tests and is merged, a separate controlled
three-candidate comparison may run:

```text
canonical source -> standard_front -> exactly three MCP candidates
  -> shared Vision + Doc248 proof for each
  -> Formal Core winner for comparison only
```

That validation must not write the old Face slot or activate a module unless a
separate user authorization says so.
