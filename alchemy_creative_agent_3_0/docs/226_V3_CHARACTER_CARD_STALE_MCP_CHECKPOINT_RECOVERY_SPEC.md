# Doc226 — Character Card stale MCP checkpoint recovery closure

Date: 2026-07-24

## Problem

Doc225 correctly projects Character Card stage metadata from the Product API
request into `planning_result.generation_plans[0].metadata`, which lets the
Provider/MCP boundary derive the current Expression Set reference contract:
the approved `face.front` full-frame card-framing reference first, followed by
identity detail and head-geometry crops.

Fresh validation still found crop-first MCP handoffs because Host resume could
reuse older durable jobs for the same MCP operation by checking only
`request.metadata`. Those older jobs had correct top-level operation, stage,
slot and reference identifiers, but their frozen generation-plan metadata came
from the pre-Doc225 runtime and lacked the Character Card transport fields.

The result was a stale checkpoint loop: the current code was correct, but the
resume layer kept re-entering the old frozen provider plan and therefore never
created a current full-frame-first handoff.

## Authoritative rule

For Character Card MCP resume, `operation_id` is necessary but not sufficient.
A durable job can be resumed only when both layers agree:

1. `record.request.metadata` proves which operation/stage/slot/reference chain
   the job belongs to.
2. `record.planning_result.generation_plans[*].metadata` proves the frozen
   Provider/MCP contract is current for that same operation.

If the request metadata matches but the frozen generation-plan metadata is
missing, incomplete, mismatched, or still uses a stale reference contract, the
record is a historical checkpoint. It must not be reused to generate, consume a
handoff, or write a winner. The Host may create a new current job/revision when
there is no current submitted artifact that must fail closed.

Submitted stale handoffs remain fail-closed. Pending stale handoffs remain
append-only and are skipped. Valid current interrupted checkpoints still resume
without asking Brain to replan.

## Current Character Card MCP resume contract

A resumable Character Card job must have generation-plan metadata with:

- `professional_character_card_preparation=true`
- `generation_channel=mcp`
- the exact `mcp_operation_id`
- `professional_identity_reference_strategy=character_card_shared_identity_v1`
- `professional_reference_stage=character_card_expression_set` or
  `character_card_body_silhouette`
- matching Character Card `stage`, `slot`, `source_class`, `attempt_round`
  and `reference_output_ids`
- for Expression Set, `professional_anchor_reference_assets` ordered with
  `character_card_full_frame_framing_reference` / `card_framing` first

This is a resume/admission rule only. It does not change prompt content,
Provider selection, MCP materialization, shared Vision review, candidate
budget, retry budget, or activation gates.

## Regression coverage

The focused regression reproduces the real failure shape:

- request top-level metadata is correct;
- old durable job uses the same operation id;
- old job has a frozen planning result whose generation-plan metadata is
  missing Character Card transport fields;
- Host must treat it as stale, must not generate from it, must not consume the
  old handoff, and must create a new current-contract job.

Existing Doc203/Doc215/Doc219/Doc221/Doc223-C tests continue to prove:

- valid current interrupted checkpoints still resume;
- current explicit handoff resume remains exact-operation/exact-reference
  guarded;
- stale submitted handoffs fail closed;
- stale pending handoff hints are not copied into new jobs;
- exact operation lookup still works beyond recent-window limits.

