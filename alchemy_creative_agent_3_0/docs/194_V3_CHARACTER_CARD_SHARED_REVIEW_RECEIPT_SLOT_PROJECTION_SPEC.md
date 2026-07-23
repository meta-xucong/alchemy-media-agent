# Doc194 — Character Card shared review receipt slot projection

## Purpose

Character Card Face Identity slots must accept or reject candidates from the
shared V3 review receipt, not from a second local prompt or angle recipe.

This document supersedes any older Doc190/Doc192 wording that implied a local
numeric yaw estimate or a long prompt-keyword checklist can override a verified
shared Vision pass for the same slot.

## Root cause

A fresh MCP left-front 45-family candidate could receive a shared Vision receipt
with:

- `verification_state=verified`
- `status` or public `review_status=pass`
- passing same-person, pose-compliance, visual-quality and overall scores

but Character Card Host/writeback still recorded the candidate as a generic
`shared_visual_review_failed`. The failure was caused by two projection issues:

1. Host receipt parsing recognized only one status spelling (`status`) and did
   not consistently normalize public receipt aliases such as `review_status`
   or score names such as `same-person`.
2. A local face-view/yaw heuristic could override a verified shared slot-pose
   pass and mark a valid 45-family modeling card as too shallow or too deep.

## Current rule

The shared Vision receipt owns Character Card slot pose quality.

When a Face Identity candidate has a verified shared review and the shared
receipt passes the slot-specific `pose_compliance` floor, Host must treat the
slot pose as verified. Local face-view metrics are retained only as fallback
diagnostics when the shared receipt is missing, unverified, non-passing, or
below the slot pose floor.

Host may still fail-closed for:

- prompt/reference parity failure;
- missing or invalid Provider reference localization for identity evidence;
- missing score dimensions that cannot be mapped from the shared receipt;
- Character Card commercial clarity or identity floors below bar;
- full-card framing parity failures;
- explicit shared Vision failure issue codes.

## Simplification rule

Do not add more prompt keyword gates for ears, nose direction, eye size, chin
line, or exact 25/45-degree wording. The runtime should pass the target slot as
structured metadata, the Remote Brain should sign the typed receipt, and shared
Vision should judge the actual pixels.

The only acceptable local text checks are coarse stale-handoff guards:

- the pending MCP handoff must still target the requested slot family;
- `reverse_three_quarter` must not mean rear/back view;
- `rear_head` must not claim a front-facing visible-face portrait.

Already consumed MCP artifacts should resume into shared review even if their
older frozen prompt predates a later wording contract. Once pixels exist, the
review/winner path, not prompt-string age, decides whether they can fill a slot.

## Tests

Doc194 coverage must include:

- a verified/pass left-front 45-family receipt projected through
  `review_status=pass` and `same-person` score alias entering slot acceptance;
- consumed MCP handoff resume preserving existing generated pixels instead of
  re-planning from Brain;
- focused Character Card/Professional/MCP regression.
