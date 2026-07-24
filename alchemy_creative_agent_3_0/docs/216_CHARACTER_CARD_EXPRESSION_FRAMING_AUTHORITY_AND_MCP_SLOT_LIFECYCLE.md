# Doc216 — Character Card Expression Framing Authority and MCP Slot Lifecycle

Date: 2026-07-24

Status: implemented as a bounded correction on top of Doc214/Doc215.

## Root cause

Fresh MCP Expression Set validation produced laugh candidates with acceptable commercial finish, but the outputs drifted into a tighter head crop than the approved `face.front` modeling card. Shared Vision correctly rejected the candidate through framing-delta evidence. This was not a reason to loosen the gate or manually write a winner.

Two implementation mismatches caused repeated loops:

1. Expression Set renderer inputs sent tight identity crops before the full-frame `face.front` card. The prompt said to inherit card framing, but the native image reference order gave the model stronger early evidence for a close-up crop.
2. Character Card slots already own a three-candidate stage lifecycle, while ordinary post-generation visual auto-retry opened a second job-local retry loop. In the MCP channel this can pause on a new materialization handoff instead of returning the reviewed failed candidate to the slot lifecycle.

## Authoritative behavior

Expression Set slots are expression deltas on the approved `face.front` card, not new camera captures. Therefore:

- the approved full-frame `face.front` image is the first provider/MCP reference and is the framing authority;
- identity crops remain allowed, but only after the full-frame card as auxiliary feature/geometry evidence;
- shared Vision framing and affect evidence remains mandatory;
- candidates with framing drift remain failed history and must not be manually written into the slot;
- Character Card stage jobs disable ordinary visual auto-retry so failures return to the Character Card slot lifecycle.

## Conflict resolution

Doc214 remains the hard framing-gate authority. Its older test expectation that placed tight identity crops before the full-frame card is superseded by this document. The gate is not weakened; the renderer input order is corrected so the existing gate can be met.

Any future product need for manual acceptance of a framing-failed image requires explicit user authorization and a separate product design. It must not be introduced as an implicit recovery path.

## Validation

Focused tests:

- `test_doc216_expression_set_uses_front_full_frame_as_first_provider_reference`
- `test_doc215_character_card_reenters_same_interrupted_mcp_job_without_replanning`
- `test_doc215_existing_mcp_handoff_still_uses_normal_handoff_resume_not_reentry`

Regression batches:

- `test_v3_professional_identity_reference_budget.py`
- `test_v3_doc203_mcp_handoff_resume.py`

