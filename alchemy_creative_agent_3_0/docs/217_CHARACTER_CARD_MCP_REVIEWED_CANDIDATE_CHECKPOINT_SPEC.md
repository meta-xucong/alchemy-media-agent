# Doc217 — Character Card MCP Reviewed-Candidate Checkpoint

## Status

Implemented as a lifecycle/state projection correction for Professional Character Card MCP validation.

## Root cause

The Expression Set MCP path previously treated a reviewed-but-failed candidate as an in-memory event and immediately advanced to the next candidate inside the same stage call. If the next candidate then paused at Remote Brain, MCP handoff creation, or artifact materialization, the earlier official pixel review was not persisted into the Character Card state before the process boundary.

That created a misleading state:

- an official output and shared Vision review existed;
- the Character Card still showed a pending MCP handoff;
- `last_shared_runtime_failure` could report zero reviewed attempts;
- the UI looked stuck even though the previous candidate had already reached a real pixel verdict.

This is a slot-lifecycle projection bug, not a prompt-quality problem, Provider problem, or framing threshold problem.

## Authoritative behavior

For Provider generation, a stage may continue through its normal candidate budget because no external handoff boundary exists.

For MCP generation, Character Card stages are candidate-checkpointed:

1. A pending MCP materialization remains a pause at the same candidate.
2. A pending MCP review remains a pause at the same candidate.
3. A reviewed candidate whose shared review does not allow the slot is immediately persisted as a blocked checkpoint for that candidate.
4. The next explicit resume continues at the next candidate in the same retry round, until the three-candidate budget is exhausted.
5. A consumed handoff must not remain the public pending state once its official output and shared review are available.

This preserves the existing three-candidate budget and does not loosen the shared framing, affect, identity, or prompt/reference parity gates.

## Non-goals

- No manual winner override.
- No relaxation of Expression Set laugh evidence.
- No relaxation of fixed face.front framing parity.
- No new Provider, MCP adapter, reviewer, retry loop, or storage path.
- No prompt wording tweak as a substitute for lifecycle correctness.

## Superseded behavior

Older Doc203 fixture behavior allowed candidate 1 to fail review and candidate 2 to become pending inside the same `prepare_expression_set()` call. That behavior is superseded for MCP because it hides the candidate-1 reviewed failure when the candidate-2 boundary pauses or times out.

The replacement behavior is:

- first call: candidate 1 reviewed failure is checkpointed;
- next call: candidate 2 is attempted;
- if candidate 2 becomes pending, pending belongs to candidate 2 and no prior reviewed evidence is erased.

## Acceptance tests

- MCP reviewed failure checkpoints before the next candidate is generated.
- MCP resume after a reviewed failure starts at the next candidate.
- Existing MCP pending/review-pending behavior still resumes the same candidate.
- Provider behavior remains unchanged.
