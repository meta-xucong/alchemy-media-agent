# Doc206 — Character Card MCP Pending Candidate Resume Order

Status: implemented after Doc205.

## Problem

During the fresh MCP `expression.laugh` validation, the system had a pending
handoff for candidate 2. After submission/resume, the Character Card
preparation service still restarted its slot candidate loop from candidate 1.
That allowed a previous candidate to be planned again and opened a new MCP
handoff for an earlier candidate index.

This is a resume-order bug, not a Provider, Brain, policy, or visual-quality
failure.

## Rule

When a Character Card stage is blocked on MCP materialization or MCP review for
a specific slot and candidate index, the next resume must start from that exact
candidate index.

It must not:

- re-run earlier candidates in the same slot/round;
- ask Brain for a new prompt for an earlier candidate;
- create a new handoff for an earlier candidate;
- reinterpret a pending MCP checkpoint as a full slot retry.

The rule applies only to MCP pending/review checkpoints. Ordinary shared review
failures still exhaust the configured candidate budget, and user-confirmed
failed-slot retry rounds remain governed by Doc202.

## Scope

The fix lives in `CharacterCardPreparationService`, which owns slot candidate
ordering. `ProductApiAnchorPackPreparationHost` still owns per-candidate
generation, Provider/MCP transport, shared review, and slot acceptance.

No Prompt text, Vision gate, Provider behavior, retry budget, or specialized
deliverable map is changed.

## Tests

The Doc203 resume test now asserts that an `expression.laugh` MCP pending
checkpoint at candidate 2 resumes with candidate 2 first and does not call
candidate 1 again.

This complements Doc205:

- Doc205 recovers a unique orphan handoff for an exact operation.
- Doc206 prevents the service from going backward before it reaches that
  operation.

## Validation status

The real validation directory keeps all previous outputs and handoffs as
append-only evidence. Any handoff created by the old resume-order bug remains
historical evidence and must still pass the normal shared review before it can
become a slot winner.
