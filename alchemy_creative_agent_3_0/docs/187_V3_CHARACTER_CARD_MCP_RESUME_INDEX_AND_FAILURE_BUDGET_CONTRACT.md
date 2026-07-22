# Doc187 — Character Card MCP Resume Index and Failure Budget Contract

## Purpose

Character Card Face Identity may be generated through either the normal Provider channel or the MCP materialization channel. Both channels must share the same Brain-owned prompt, reference budget, shared Vision review, winner selection, and slot writeback contract.

MCP adds one extra state boundary: the runtime may first return opaque handoff receipts, then later resume when an artifact is submitted. That resume boundary must not change candidate identity or silently create unlimited new candidates.

## Contract

1. A failed Face Identity pack may persist public-safe candidate failure receipts.
2. A candidate failure receipt may contain only:
   - stage;
   - view role;
   - candidate index;
   - safe failure code;
   - optional opaque MCP handoff id.
3. It must not contain prompt text, filesystem paths, provider response bodies, reviewer prose, API endpoints, secrets, or raw pixel evidence.
4. On MCP resume, a handoff is consumed by its frozen `(view_role, candidate_index)` identity, not by list position.
5. A submitted candidate that has already completed shared review and failed quality must not be generated again by automatic resume.
6. A pending MCP materialization resumes only through the original handoff id.
7. Transient non-review generation failures may still be retried by an explicit later resume; Doc187 does not remove existing recovery for ordinary provider/runtime faults.
8. If all three candidates for a slot have completed shared review and failed, automatic resume must return a blocked state without creating a new handoff batch.

## Non-goals

- Do not relax shared Vision review.
- Do not add a private reviewer, retry path, Provider, Brain, or storage layer.
- Do not make MCP a separate asset type.
- Do not expose prompts, paths, provider internals, or raw review details in the public Character Card state.

## Acceptance

- Resuming with only candidate 2 submitted still sends that artifact through candidate index 2.
- Previously reviewed failed candidates are not regenerated.
- Three reviewed failures produce a stable blocked state with no new MCP handoffs.
- Existing provider-failure resume behavior remains available.
