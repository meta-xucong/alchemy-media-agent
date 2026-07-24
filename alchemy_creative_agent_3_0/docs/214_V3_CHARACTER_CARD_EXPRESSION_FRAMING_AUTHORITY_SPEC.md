# Doc214: Character Card Expression Framing Authority

Date: 2026-07-24

## Root cause

Fresh MCP validation produced an `expression.laugh` candidate whose shared
Vision laugh evidence passed.  The same candidate still failed Character Card
slot acceptance because its `face.front` framing deltas exceeded the fixed
card limits:

- face area grew beyond the approved front card;
- bottom margin changed beyond tolerance;
- eye line moved beyond tolerance.

This is not a laugh-quality failure and must not be solved by lowering the
shared expression/framing gate.  The failure belongs to the materialization
side: the expression slot was not giving the renderer a clear full-frame
framing authority.  The reference package carried identity/detail crops and the
full `face.front` image, but the full-frame image was not explicitly marked as
the card-framing authority for Expression Set.

## Authoritative rule

Expression Set outputs must keep the same `face.front` modeling-card skeleton:

- vertical 2:3 white-background card;
- same camera distance and subject scale;
- same head-top margin, eye-line height, centered head position;
- same neck and upper-shoulder crop, shoulder span and white padding;
- same lighting, white balance and visual finish channels.

Only facial expression and very small natural head/shoulder energy may change.

## Implementation rule

For Professional Character Card `expression_set`, the approved `face.front`
winner must be carried as:

1. identity/detail evidence through the existing portrait identity derivatives;
2. one explicit full-frame `card_framing` reference using the existing
   `character_card_full_frame_framing_reference` contract.

The native reference budget remains three images.  This does not add a new
Provider/MCP path, candidate budget, reviewer, or storage layer.

## MCP prompt-current rule

An `expression.laugh` MCP handoff is current only if the canonical prompt
contains both:

- the laugh expression intent;
- the full-frame `face.front` framing authority directive.

Older handoffs that only say “preserve front-card framing” without the
full-frame authority cannot be resumed as current.

## Non-goals

- Do not relax `EXPRESSION_FRAMING_DELTA_MAX`.
- Do not reinterpret a framing failure as a laugh failure.
- Do not increase the retry/candidate budget.
- Do not add child-specific or style-specific prompt branches.
- Do not promote `v3_output_eb353a12dc9e4c26b161` or other already-failed
  candidates as winners.

## Acceptance

Focused tests must prove:

1. Expression Set Provider/MCP reference packaging emits two identity crops plus
   one `card_framing` full-frame reference while keeping a count of three.
2. The generated full-frame reference is marked with
   `identity_evidence_scope=card_framing` and
   `derivative_kind=character_card_full_frame_framing_reference`.
3. `expression.laugh` handoff freshness requires the framing authority
   directive.
4. Existing shared expression review gates remain strict.
