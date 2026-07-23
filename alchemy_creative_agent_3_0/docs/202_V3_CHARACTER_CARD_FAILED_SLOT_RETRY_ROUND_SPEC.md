# Doc202 — Character Card Failed-Slot Retry Round Contract

Date: 2026-07-24

## 1. Problem

Doc201 makes `expression.laugh` a structured foundation-owned affective intent.
After that fix, a fresh validation round must not reuse the three failed
pre-Doc201 `expression.laugh` candidates. However the Character Card MCP
operation identifier was still scoped only by:

```text
people_asset_id : module : slot_key : candidate_index
```

When a slot exhausts its three-candidate budget and the user explicitly
continues later, the next run can collide with the old operation identifiers.
That risks reading old candidates or handoffs instead of creating a genuinely
new round.

## 2. Contract

Character Card must distinguish:

- normal resume of a pending MCP handoff;
- user-confirmed retry after a slot has exhausted its candidate budget.

Normal resume keeps the original operation id and consumes the frozen handoff.
User-confirmed retry increments a per-slot retry round and creates fresh
operation ids for the next three candidates.

## 3. Safety rules

- A retry round requires explicit confirmation.
- A retry round is only valid when the failed slot has no pending MCP handoff
  and has exhausted the current three-candidate budget.
- Old failed candidates remain append-only history and must not become winners.
- Candidate budget remains three candidates plus at most one shared bounded
  repair per round.
- No review, scoring, Provider, MCP, Brain, or storage path is duplicated.
- Provider and MCP remain equivalent materialization channels; the round only
  changes the durable operation identity.

## 4. Routing

The public Character Card prepare route may accept:

```json
{
  "stage": "expression_set",
  "generation_channel": "mcp",
  "retry_failed_slot": true,
  "confirm_retry": true
}
```

The server chooses the failed slot from the persisted Character Card checkpoint.
Callers cannot submit prompt text, scores, paths, candidate ids, or review
overrides.

## 5. Validation

Tests must prove:

- unconfirmed retry is rejected;
- retry is rejected while an MCP handoff is still pending;
- a confirmed retry increments the failed slot round without clearing previous
  winners;
- fresh MCP operation ids include the retry round only after round one, so old
  round-one handoffs cannot be resumed accidentally;
- route payload stays narrow and does not open prompt or reviewer injection.
