# Doc219 — Character Card Host Stale MCP Handoff Reuse Guard

Date: 2026-07-24

Status: implemented for local validation

## Problem

Doc218 unified Provider/MCP reference ordering at the rendering boundary, but the live validation resume still pointed at the old pending handoff `mcp_handoff_99e8b5f62b`.

That handoff was crop-first:

1. tight portrait identity crop;
2. pose geometry crop;
3. full-frame `face.front`.

For Character Card Expression Set, this is stale. The full-frame approved `face.front` card image must be the first reference because it owns framing, camera distance, subject scale, head-top margin, eye-line, white background and lighting continuity.

The remaining root cause was one layer higher than Provider/MCP packaging: `ProductApiAnchorPackPreparationHost` could resume an old blocked job whose request still carried the stale pending handoff. In that case the Provider boundary never got a chance to compute a fresh current handoff.

## Intended behavior

The Host must treat `mcp_handoff_id` and `pending_mcp_handoff_ids` as resume hints, not as final authority.

For Character Card `expression_set`:

- a pending handoff is reusable only if its canonical prompt is current and its safe reference contract is current;
- a current expression handoff must put the full-frame `face.front` card-framing reference before the tight identity and geometry crops;
- a stale pending handoff is skipped so the stage can re-plan/rebuild from the authoritative current contract;
- a stale submitted handoff fails closed because it is immutable external evidence and cannot be silently relabeled.

## Safe reference-order check

MCP handoff persistence deliberately stores a safe reference contract. It may not retain full provider-internal derivative metadata. Therefore Host validation accepts either:

1. explicit metadata: first reference has `derivative_kind=character_card_full_frame_framing_reference` and `identity_evidence_scope=card_framing`; or
2. safe asset-id order: the first reference is the unsuffixed `face.front` output, followed by `::portrait_identity_crop` and `::portrait_identity_geometry_crop`.

If the first reference is a crop or geometry crop, the handoff is stale.

## Non-goals

Doc219 does not:

- relax the expression laugh evidence gate;
- relax the fixed framing gate;
- change candidate/retry budgets;
- add a private MCP or Provider path;
- allow a previously generated tight-crop image to become a winner.

## Acceptance coverage

Regression coverage must prove:

- current expression handoffs with full-frame-first safe references still resume;
- crop-first pending expression handoffs are not resumed;
- crop-first submitted expression handoffs fail closed;
- orphan submitted handoff recovery and pending/submitted priority still work when the submitted handoff is current;
- ordinary non-Character-Card MCP materialization remains unaffected.

## Validation implication

The existing `mcp_handoff_99e8b5f62b` must remain append-only evidence and must not be materialized. After Doc219 is committed, the next live resume should not reuse that old blocked job. It should build a fresh handoff from the current full-frame-first expression reference contract.
