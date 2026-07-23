# Doc210 — Character Card MCP ambiguous operation confirmed retry

## Scope

Doc210 extends Doc202 for one failure code only:

```text
mcp_materialization_operation_ambiguous
```

It does not relax shared visual review, laugh evidence floors, candidate budgets, Provider/MCP parity, or slot winner
selection.

## Observed mismatch

A real local validation directory can contain multiple `submitted` MCP artifacts for the same scoped Character Card
operation after earlier handoff bugs. The current fail-closed resolver correctly refuses to guess which artifact is
authoritative. However, Doc202 only allowed a user-confirmed new round after all three candidates were exhausted.

When ambiguity occurs at candidate 2, the stage is stuck:

- continuing to candidate 3 would skip a corrupted operation;
- picking one submitted artifact would be an unsafe local guess;
- deleting old artifacts would violate append-only evidence.

## Authoritative rule

For quality failures, Doc202 remains unchanged: a confirmed retry round requires the three-candidate budget to be
exhausted.

For `mcp_materialization_operation_ambiguous`, a confirmed retry round may start before the three-candidate budget is
exhausted, provided:

1. the persisted Character Card has no pending MCP handoff ids;
2. the persisted Character Card has a `last_shared_runtime_failure` receipt for the paused stage;
3. if any candidate was already reviewed before the ambiguity, that receipt preserves the shared review proof rather
   than folding the pixel into an opaque failure;
4. the caller uses the existing narrow `retry_failed_slot=true` and `confirm_retry=true` route;
5. the failed slot is selected from server state, not from caller-supplied prompt/score/path/candidate data;
6. all prior handoffs and outputs remain append-only historical evidence;
7. the new round receives a new operation suffix and starts from candidate 1.

## Non-goals

- Do not mark any ambiguous submitted artifact as winner.
- Do not delete or mutate old handoff files.
- Do not increase the per-round three-candidate budget.
- Do not bypass shared Vision or expression review.
- Do not special-case the six-year-old validation fixture.

## Regression requirement

Tests must prove:

- confirmed retry can start from an ambiguous MCP operation at candidate 2;
- pending handoff ids still block retry even when the failure code is ambiguous;
- ambiguous retry is rejected when the shared runtime failure receipt is missing;
- ordinary non-ambiguous failures still require exhausted candidate budget.
