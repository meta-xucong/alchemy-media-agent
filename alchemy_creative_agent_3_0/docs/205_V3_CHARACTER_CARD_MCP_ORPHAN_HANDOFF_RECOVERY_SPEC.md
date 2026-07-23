# Doc205 — Character Card MCP Orphan Handoff Recovery

Status: implemented on main after Doc204.

## Problem

Real MCP validation exposed an interrupted-resume edge case in the
Professional Character Card Expression Set.

The MCP materialization handoff can be durably created or even submitted while
the corresponding Product API planned job record is absent, stale, or not
projected back into the Character Card `pending_mcp_handoff_ids` field. When
the next stage resume sees no explicit handoff id, the Host may ask Brain for a
new candidate prompt for the same asset/module/slot/candidate/round operation.
That creates a second handoff with a different prompt hash and strands the
already submitted artifact outside the official review path.

This is not an image-quality issue and must not be solved by more retries,
weaker review, or prompt tuning.

## Principle

For MCP materialization, the handoff file is the frozen renderer contract:

- operation id;
- canonical prompt and prompt hash;
- reference assets and hashes;
- rendering contract;
- submitted artifact receipt.

If a unique unconsumed handoff exists for the exact Character Card operation,
the Host must treat it as the resume fact and continue through the ordinary
Provider/MCP output, shared Vision review, expression receipt, and slot gate.

If more than one unconsumed handoff exists for the same operation and no caller
explicitly identifies the intended handoff, the system must fail closed instead
of choosing one silently.

## Scope

This is a shared MCP materialization recovery fix. It does not:

- change the laugh expression quality bar;
- add more candidates or retries;
- bypass Brain, Provider, Vision review, or Character Card slot acceptance;
- create a Character Card private image path;
- promote old smile/laugh failures into winners.

## Contract

`McpMaterializationHandoffStore` exposes an internal
`list_unconsumed_by_operation(operation_id)` query returning only `pending` and
`submitted` handoffs for an exact operation id.

`ProductApiAnchorPackPreparationHost` uses that query only when:

1. the request is on the MCP materialization channel;
2. no explicit `mcp_handoff_id` was projected into the candidate request;
3. the operation id is exact for asset/module/slot/candidate/round;
4. the stored prompt is still current for the requested Character Card slot.

Outcomes:

- zero matches: proceed with ordinary planning;
- one match: attach its handoff id to the request and resume it;
- more than one match: raise `mcp_materialization_operation_ambiguous`.

The recovered handoff still enters the ordinary Provider/MCP path. A submitted
artifact must still be consumed by the MCP provider and then reviewed by the
shared Vision/expression receipt gate before it can become a slot winner.

## Tests

Focused coverage:

- orphan submitted handoff without a planned job is reattached before
  planning a new candidate;
- ambiguous unconsumed handoffs for one operation fail closed;
- existing Doc203 explicit-handoff and ScenarioRuntime projection tests remain
  green.

## Current validation status

The fresh six-year-old Character Card validation remains in progress. Face
Identity is active. `expression.laugh` is still under validation and must not
be marked complete until a candidate passes the shared expression/framing
receipt and the module is activated.
