# Doc235: Character Card Prior Reviewed Candidate Collection

Date: 2026-07-24

## Root cause

After Doc234, `expression.anger` candidate 1 can produce a valid generic shared
review receipt. However the real validation state already contained a later
candidate 2 MCP handoff in `pending` state.

The previous single-slot resume path treated that later auxiliary pending
handoff as the active blocker and did not offer a clean way to collect the
already reviewed candidate 1 into the standard slot.

## Authoritative rule

For explicit Character Card single-slot review-only collection:

```text
existing reviewed candidate -> shared review receipt -> winner -> slot receipt
```

is a complete Core path. A later MCP `pending` handoff for the same slot is
append-only Auxiliary evidence and must not force new materialization or block
the already complete candidate from being selected.

## Implementation boundary

When all of the following are true:

- the call is an explicit single expression slot;
- `review_only_resume=True`;
- `generation_channel=mcp`;
- the card is blocked on the same slot with `mcp_materialization_pending`;
- the pending attempt index is greater than 1;

the Host first scans prior candidate operations for official generated records.
For each prior candidate it reuses the existing job/output/review package,
projects the shared receipt, and passes the reviewed candidates through
`SlotAcceptanceCore`.

If a reviewed prior candidate passes, the Host returns a normal review-stage
`CharacterCardStageResult`; the existing lifecycle then persists the slot
receipt in the standard path.

The path does not:

- create a job;
- create or submit a handoff;
- materialize a new output;
- alter prompts;
- alter Vision gates;
- alter candidate or retry budgets;
- activate the whole Expression Set;
- touch `expression.laugh`, `expression.sad`, or Body Silhouette.

## Failure behavior

If no prior reviewed candidate can be uniquely recovered, the Host returns to
the existing fail-closed behavior. It must not fall back to consuming the later
pending handoff unless the user explicitly authorizes that next candidate.

## Acceptance

The focused regression proves that a blocked `expression.anger` card with:

- candidate 1 already reviewed and pass;
- candidate 2 held at `mcp_materialization_pending`;

can collect candidate 1 into the `expression.anger` slot through the normal
shared receipt path, while candidate 2 remains unsubmitted append-only evidence.
