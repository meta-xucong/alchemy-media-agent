# Doc233 — Character Card pre-handoff logical reference resume boundary

Date: 2026-07-24

## Status

Implemented as a narrow Auxiliary recovery correction for Professional
Character Card MCP validation.

## Problem

The `expression.anger` validation run produced a durable Product API job that
was interrupted after planning and before MCP handoff creation:

- stage: `expression_set`
- slot: `expression.anger`
- status: `generating`
- `planning_result` exists
- `generation_result` is absent
- `mcp_materialization` is absent
- no MCP handoff, output, candidate, or shared review receipt exists

The request metadata and frozen planning metadata identified the correct
Character Card operation and logical `face.front` winner.  However, the Host
resume guard reused the later MCP handoff reference-order rule and required the
planning metadata itself to contain `character_card_full_frame_framing_reference`
and identity crop derivatives.

That mixed two different boundaries:

1. Planning freezes the logical reviewed `face.front` winner.
2. Provider/MCP materialization derives the full-frame card-framing reference
   and identity crops before the durable handoff is created.

As a result, a safe pre-handoff checkpoint could be skipped and a replacement
job could be created for the same operation.

## Authoritative behavior

For a pre-handoff interrupted Character Card MCP job, the Host may resume the
same job only when:

- request metadata matches the exact operation, stage, slot, attempt round, and
  reference output chain;
- planning metadata preserves the same Character Card transport fields;
- planning reference assets are either:
  - already materialized in the current full-frame-first order; or
  - logical selected-output references that exactly match the requested
    `reference_output_ids` and do not claim derivative semantics.

Once a durable MCP handoff or generated output exists, the stricter materialized
reference contract remains authoritative.  Full-frame-first/card-framing
semantic fields must still be verified at the handoff boundary.

## Non-goals

This does not change prompt wording, anger/laugh expression gates, Vision
review, candidate budget, retry budget, MCP submission, slot writing, or module
activation.

## Regression coverage

`test_doc233_character_card_reenters_pre_handoff_job_with_logical_front_reference_plan`
proves that a logical-front pre-handoff job is re-entered through the same
Product API job with `_v3_resume_interrupted_mcp_materialization=true` and does
not create a replacement job.
