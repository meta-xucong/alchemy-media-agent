# Doc234: Character Card Generic Shared Review Receipt Projection

Date: 2026-07-24

## Root cause

`expression.anger` reached a verified shared Vision `post_generation_review_package`, but
`ProductApiAnchorPackPreparationHost._character_card_candidate_and_review()` only projected
structured shared review receipts for `expression.laugh`.

That left non-laugh Character Card slots with:

- `AnchorReviewDecision.status == "pass"`;
- generic shared Vision score and issue evidence present in the review package;
- `AnchorReviewDecision.shared_review_receipts == []`.

Downstream, `CharacterCardSharedRuntimeReceipt` and
`validate_character_card_slot_success_receipt()` require at least one safe shared review
receipt with review dimensions. Therefore a visually verified anger candidate could not be
persisted as an official slot winner, and the candidate loop could continue into the next
candidate without completing the core path:

```text
candidate -> shared review -> winner -> slot receipt
```

## Authoritative rule

Every Character Card candidate that consumes a shared Vision inspection must project a
safe, durable, generic shared visual review receipt.

`expression.laugh` remains special only because it has an additional Enhanced quality
contract for laugh affect and face.front framing. The generic receipt must not become an
anger-specific, sad-specific, body-specific, or private Character Card reviewer.

## Implementation boundary

The fix is limited to the shared review projection layer:

1. Add a foundation-owned generic visual review receipt:
   `v3_character_card_generic_slot_review_receipt_v1`.
2. Project only already-observed shared Vision facts:
   verification status, pass/fail status, issue codes, score dimension names, and observed
   framing dimension names.
3. Attach that generic receipt to every Character Card candidate review.
4. Keep the existing `expression.laugh` affect/framing receipt and evidence gates unchanged.

This does not change:

- prompts;
- provider/MCP materialization;
- Vision thresholds;
- candidate budget;
- retry budget;
- slot activation policy;
- laugh, sad, or body generation behavior.

## Candidate count note

The real `expression.anger` checkpoint contained a generic planning-level
`candidate_count=4`, inherited from broader V3 planning metadata. The official
Character Card service still uses `CharacterCardPreparationService.CANDIDATE_COUNT == 3`,
and the materialized generation plan for the single MCP handoff used `candidate_count=1`.

Treat the planning-level `4` as metadata leakage to audit separately. It must not expand
the Character Card three-candidate budget.

## Acceptance tests

Required focused coverage:

- a verified generic anger inspection round-trips into a shared review receipt;
- the receipt can be attached to the Character Card stage receipt;
- the projected slot success receipt validates for `expression.anger`;
- existing laugh affect/framing receipt behavior remains unchanged;
- lifecycle receipt persistence and public-safe projection continue to pass.
