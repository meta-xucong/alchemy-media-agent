# Doc237: Character Card Acceptance Mode Legacy Receipt Readback

Date: 2026-07-24

## Root cause

Doc236 added explicit Character Card slot receipt fields:

- `acceptance_mode`
- `reviewed_candidate_count`

The code initially defaulted missing legacy values to:

- `acceptance_mode=standard_three_candidate`
- `reviewed_candidate_count=candidate_count`

That could make an older target-only recovery receipt appear to be a complete
three-candidate acceptance. This is a receipt readback/projection bug, not an
image quality, MCP, Provider, prompt, threshold, budget, or retry issue.

## Correct behavior

1. New slot receipts must explicitly carry `acceptance_mode` and
   `reviewed_candidate_count`.
2. `standard_three_candidate` remains strict: it requires
   `reviewed_candidate_count=3`.
3. `target_only_existing_candidate_collection` is allowed only for recovery
   collection of an existing official output with shared review evidence. It
   must never be reported as a standard three-candidate run.
4. Legacy receipts missing these fields are classified as
   `legacy_unclassified` / `missing_acceptance_mode` during safe readback.
5. Legacy unclassified receipts may be loaded for compatibility, but they are
   fail-closed for strict activation and must not be marked as verified in the
   public projection.
6. A controlled local migration may add explicit mode/count to known current
   acceptance evidence when the original workflow identity is known and no
   image/candidate/output is changed.

## Current controlled evidence migration

The current six-year-old Character Card validation asset had two older receipts
created before Doc236:

- `expression.laugh` → `v3_output_a27b83988d28f9010cd1`
- `expression.anger` → `v3_output_c05279ede4b2b8148dce`

Both were target-only existing-output collections, not complete fresh
three-candidate validations. The local controlled validation catalog was updated
to add:

- `acceptance_mode=target_only_existing_candidate_collection`
- `reviewed_candidate_count=1`

No Provider/MCP image generation, handoff submission, candidate creation, output
rewrite, prompt change, gate change, budget change, retry change, `sad` slot, or
Body Silhouette work was performed.

The pending candidate2 handoff remains append-only evidence and must not be
materialized without explicit authorization:

- `mcp_handoff_f5f0ac2a41`

## Tests

Focused regression covers:

- legacy missing acceptance mode fails strict validation;
- legacy receipts can still load as `legacy_unclassified` for safe catalog
  compatibility;
- public projection marks legacy receipts as unverified;
- standard receipts with fewer than three reviewed candidates fail closed;
- target-only recovery receipts preserve explicit mode/count.

