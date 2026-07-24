# Doc220 — Character Card Stale MCP Hint Scrub

Date: 2026-07-24

Status: implemented for local validation

## Problem

Doc219 correctly prevented the Character Card Host from resuming a blocked job whose MCP handoff was still crop-first. However, the next live resume created a new job that still copied the stale card-level `mcp_handoff_id` into the new request metadata.

That meant the new job was born with:

- a current operation id;
- current Character Card stage metadata;
- but a stale `mcp_materialization` hint pointing back to the old crop-first handoff.

The job then stalled before a fresh MCP handoff could be created.

## Intended behavior

Card-level `mcp_handoff_id` and `pending_mcp_handoff_ids` are resume hints only. They must never be copied into a new job unless the handoff is still current for the requested slot.

For Character Card Expression Set:

- stale pending handoff hints are removed before new job creation;
- stale submitted handoff hints still fail closed;
- current handoff hints continue through the existing resume path;
- new jobs created after a stale pending hint must not contain `mcp_materialization` until the Provider/MCP boundary creates a fresh handoff from the current reference contract.

## Non-goals

Doc220 does not change:

- expression/laugh quality gates;
- framing thresholds;
- candidate or retry budgets;
- Provider/MCP materialization APIs;
- shared Vision review behavior.

## Acceptance coverage

Regression coverage proves that a stale crop-first pending expression handoff:

1. is not resumed as an existing job;
2. is not copied into the newly created stage job request;
3. still allows the stage to rebuild a fresh handoff from the current full-frame-first reference contract.

Current handoffs and ordinary explicit MCP materialization paths remain compatible.
