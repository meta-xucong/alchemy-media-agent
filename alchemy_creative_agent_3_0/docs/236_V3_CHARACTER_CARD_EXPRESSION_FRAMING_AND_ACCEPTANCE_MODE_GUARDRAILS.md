# Doc236: Character Card Expression Framing and Acceptance Mode Guardrails

Date: 2026-07-24

## Purpose

This document closes two root-level ambiguities found during the `expression.anger`
single-slot acceptance review:

1. `expression.anger` and `expression.sad` did not inherit the same strict
   front-card framing renderer directive that `expression.laugh` used.
2. A target-only recovery collection could be mistaken for the normal
   three-candidate selection flow.

The fix is deliberately small. It does not change prompt style, candidate
budget, retry budget, shared Vision gates, MCP materialization, Provider
routing, or whole-module activation.

## Authoritative behavior

### Shared expression framing

All Character Card Expression Set materialization intents must inherit the same
`face.front` card-framing directive:

- `expression.laugh`
- `expression.anger`
- `expression.sad`
- explicit legacy/extension `expression.smile`

The directive keeps the approved `face.front` image as the framing authority:
vertical 2:3 white-background card skeleton, camera distance, subject scale,
head-top margin, eye-line height, centered head, neck and upper-shoulder crop,
shoulder span, white padding, lighting, and white balance.

Expression-specific text may only describe the emotional delta. It must not
replace or weaken the shared front-card framing contract.

### Acceptance mode

Character Card slot success receipts now distinguish:

- `standard_three_candidate`: the normal slot flow. It requires three reviewed
  candidates before the winner receipt can be persisted.
- `target_only_existing_candidate_collection`: a recovery-only path for an
  already official output with shared review evidence. It may persist fewer than
  three reviewed candidates, but it must be labeled as recovery collection and
  must not be reported as a completed three-candidate selection.

`candidate_count=3` remains the slot budget. `reviewed_candidate_count` records
how many official reviewed candidates were actually used for this receipt.

## Non-goals

- Do not materialize pending MCP handoffs.
- Do not create candidate 2 or candidate 3.
- Do not change image quality thresholds, Vision gates, prompt strength,
  provider routing, retry budget, or standard Character Card candidate budget.
- Do not turn target-only collection into a general low-budget success path.

## Verification

Focused regression now covers:

- all expression slots inherit the same front-card framing directive;
- standard receipts with fewer than three reviewed candidates fail closed;
- target-only recovery receipts explicitly record `reviewed_candidate_count=1`
  and `acceptance_mode=target_only_existing_candidate_collection`;
- the target-only recovery path still requires an existing official output and
  shared review receipt, and creates no new job, handoff, candidate, or output.

