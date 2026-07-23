# Doc203 — Character Card MCP submitted-handoff resume contract

Status: implemented in mainline after Doc202.

## Problem

Character Card MCP validation can pause with a durable `mcp_materialization_pending`
handoff. After the local MCP/ImageGen client submits one artifact, the next
stage resume must consume that exact submitted handoff and continue into the
shared Provider-equivalent materialization and Vision/review path.

The previous slot service retained only opaque pending handoff IDs on the
card, but it did not pass the resumable handoff ID back into the matching
`CharacterCardCandidateRequest`. In addition, the public retry checkpoint used
the number of failure events as `last_failure_attempt_count`; when a reviewed
candidate failed and the next candidate paused for MCP materialization, that
count could point to the wrong candidate. The result was a repeated pending
handoff loop: submitted MCP artifacts stayed append-only, but the stage opened a
new handoff instead of consuming the submitted one.

A second provider-boundary issue can appear after repeated same-operation
handoffs already exist: the generation request carried `generation_channel` and
`mcp_operation_id`, but not the explicit `mcp_materialization` receipt. In that
case the MCP provider can fall back to operation/prompt based lookup and consume
a stale submitted handoff for the same operation. The explicit handoff receipt
must therefore cross the canonical Provider request boundary.

## Contract

1. A submitted MCP artifact is never promoted locally. It must be consumed by
   the same shared Product API / Provider-equivalent / Vision / Character Card
   slot path used by Provider outputs.
2. Resume may pass an opaque `mcp_handoff_id` only when all of these match the
   current card checkpoint:
   - failed module;
   - failed slot;
   - `mcp_materialization_pending` or `mcp_review_pending`;
   - candidate index;
   - exactly one pending handoff ID.
3. Candidate attempt count records the candidate index where the slot stopped,
   not the length of the failure list.
4. The handoff ID remains opaque to the public Character Card state. Prompt,
   paths, hashes, provider details, and raw review payloads stay in controlled
   stores and receipts.
5. This does not change candidate budget, shared review thresholds, retry
   limits, Provider/MCP parity, or Expression/Body slot semantics.
6. Provider request construction must preserve an explicit
   `mcp_materialization` receipt. When present, the MCP provider consumes that
   handoff only; it must not choose a stale submitted handoff with the same
   operation ID.

## Acceptance

- A pending candidate-2 handoff records `last_failure_attempt_count == 2`.
- Resuming that card passes the pending handoff only to candidate 2.
- Candidate 1 and candidate 3 do not inherit that handoff.
- Existing Doc202 failed-slot retry rules still reject superseding any pending
  MCP handoff.
- Provider request projection preserves explicit `mcp_materialization`.
- The MCP provider consumes the explicit handoff and leaves stale same-operation
  submissions untouched.
- Real MCP validation may continue after commit by submitting the pending
  handoff artifact and verifying that it becomes a normal reviewed candidate or
  a structured review failure.
