# Doc255 — Doc252 Phase5 Review Evidence Seam

## Purpose

Doc252 is an Enhanced quality module. Phase4 connected the trusted Face
`standard_front` Host seam and the Face-local Doc248 + Doc252 composite
eligibility adapter, but it did not yet prove that canonical shared Vision would
produce Doc252 micro-realism evidence.

Phase5 closes that evidence seam without changing Formal Core, route selection,
MCP/Provider recovery, slot receipts, activation, Expression, Body, 25-degree
auxiliary views, or Doc253 numeric framing.

## Root cause

The trusted Host can request Doc252 and the Face adapter can evaluate Doc252, but
the canonical shared Vision contract previously did not request the Doc252
micro-realism dimensions. A real generated candidate could therefore pass
generic shared Vision and Doc248 while still failing Doc252 only because no
micro evidence was ever asked for.

That is a review-contract gap, not a winner, receipt, prompt, route, retry, or
slot-lifecycle problem.

## Authority split

| Decision | Owning layer | Phase5 rule |
| --- | --- | --- |
| Whether Doc252 applies | Trusted Face Host metadata | Only `character_card_face_identity:standard_front` with server provenance |
| Which dimensions Vision should inspect | Shared Vision contract | Request Doc252 required dimensions and optional applicability sentinels only when Doc252 applies |
| Candidate evidence labels | Face Host review adapter | Project safe `micro_*` evidence from canonical score dimensions only |
| Candidate eligibility | Face-local Doc248 + Doc252 adapter | Required Doc252 proof must pass when enabled |
| Winner / receipt / activation | Formal Core and formal receipt lifecycle | Unchanged |

## Evidence shape

When Doc252 applies, canonical shared Vision must request:

1. required micro-realism dimensions from
   `REQUIRED_STANDARD_FRONT_MINIMUM_GROUP_DIMENSIONS`;
2. optional visible dimensions from `OPTIONAL_VISIBLE_DIMENSIONS`;
3. safe optional applicability sentinels such as
   `<dimension>_not_applicable_outside_frame`,
   `<dimension>_not_applicable_occluded`, or
   `<dimension>_not_applicable_insufficient_resolution`.

The Face Host may project:

- `micro_<dimension>_verified` only from a score at or above the Doc252 floor;
- `micro_<dimension>_visible` only when a score exists but fails the floor;
- `micro_<dimension>_not_applicable_<reason>` only from a canonical sentinel
  score.

If an optional dimension has neither a verified score nor a canonical
not-applicable reason, Doc252 remains fail-closed. The Host must not invent
visibility or outside-frame evidence.

## Non-goals

Phase5 does not:

- enable real generation;
- choose a winner;
- write a Face slot or FormalSlotReceipt;
- alter Doc248;
- change Provider/MCP route selection, Brain planning, retry, budget, prompt,
  age, reference ownership, recovery, or public projection;
- enable Doc253 numeric framing calibration.

## Verification model

Red/green tests must prove:

1. trusted Face `standard_front` Doc252 metadata causes shared Vision to request
   the Doc252 dimensions;
2. forged, disabled, non-Face, non-standard-front, or ordinary metadata does not
   request Doc252 dimensions;
3. Host evidence projection consumes only canonical score/applicability
   dimensions;
4. missing optional applicability remains fail-closed;
5. existing Doc248, Formal Core, Expression, Body, and historical auxiliary
   behavior remains unchanged.
