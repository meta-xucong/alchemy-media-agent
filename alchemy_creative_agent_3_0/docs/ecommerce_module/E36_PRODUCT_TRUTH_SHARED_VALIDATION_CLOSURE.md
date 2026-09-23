# E36 Product-truth selection contract closure

## Correction model and scope

This supersedes E35's minimal implementation where rules were still duplicated.
Product-truth selection is a Brain/Runtime shared contract, not image quality
review and not Provider retry logic. The defect is acceptance of a structurally
valid but semantically invalid Brain plan before Runtime activation. PR #13
adds early rejection and a bounded re-answer; this follow-up closes remaining
authority, type, context and testing gaps on main (including PR #10 and #12).

This is specialized E-Commerce work. General, Photography, Vision thresholds,
output reads, worker cancellation and Provider transport policy remain owned by
their existing layers. No local code chooses, truncates or repairs a Brain asset
selection. Reusing an asset across outputs is legal; repeating it within one
output is not.

## Authority and execution order

1. Product API owns Doc263 admission and its ordered canonical sources, content
   hashes and source-binding digest. Preserve that existing authority.
2. Shared E-Commerce contracts resolve product assets: a nonempty explicit
   channel takes precedence; only an empty/missing channel falls back to role.
   Adapter and Runtime use this same resolver and selection/budget validator.
3. At the Brain boundary, validate the local pool and budget before any upstream
   request. A corrupt local pool or budget cannot be repaired by the Brain;
   stop with a safe diagnostic and zero semantic recovery attempts.
4. Freeze a planning-input digest (ordered product pool and reference claims,
   per-output budget, output count and job binding). The validated Brain result
   carries it locally. Runtime compares the current context before activation.
   This is a consistency receipt, not a replacement for Doc263 authorization.
5. Validate raw Brain selections before fallback merging. On a response defect,
   send only allowlisted field paths and codes through the existing single
   semantic re-answer. Validate the entire second answer again. A second defect
   blocks generation. Preserve the same frozen request through both calls.
6. Runtime reuses the shared validator and only projects accepted selections.
7. Provider admission reuses shared per-output selection semantics, retaining
   separate file-integrity, authorization, Doc263/269 projection and transport
   checks. These are different responsibilities, not duplicate selection rules.

Doc269 projection is created AFTER selection. It must not be an input to the
pre-Brain digest (which would be circular). Existing Doc263 content verification
and Doc269 digest/physical-capacity checks continue protecting changed bytes and
final physical references. Do not hash local file paths into upstream diagnostics.

## Contract rules and diagnostics

The shared module owns valid selection roles, detail-only two-source selection,
positive integer budgets (1 or 2, excluding bool/float/string coercions), exact
asset membership, duplicate detection and complete unique output indexes 1..N.
Pool entries must be well formed, unique and match the current product assets;
an explicit conflicting channel cannot be overridden by a product role.

Keep stable outer failure codes for existing clients; safe detail codes distinguish
invalid role/index, unknown or duplicate asset, missing/invalid budget, exceeded
budget, invalid pool, context mismatch and output-count mismatch. Diagnostics
contain no rejected values, filenames, URLs, paths, secrets or internal IDs.
Normalize through allowlisted diagnostics at the outbound recovery boundary.

Doc270/E31 retains its existing server-issued view selection authority. It is not
a new Brain role and must not gain an unverified bypass through this change.
Old persisted results without the new planning digest still pass the complete
shared defensive checks; newly produced Adapter results always carry the digest.

## Implementation and acceptance matrix

| Area | Required evidence |
| --- | --- |
| Shared contract | role, ID, duplicate, missing/malformed budget, role/count constraints |
| Asset context | explicit channel priority, empty channel fallback, duplicate/malformed pool |
| Snapshot | asset order/claims/budget/count changes detected; original request unchanged |
| Adapter | invalid first response corrected once; twice invalid stops; safe diagnostics |
| Local context | invalid local input stops before Brain, zero image-provider calls |
| Runtime integration | actual generate_job: valid/corrected plan dispatches; invalid plan never dispatches |
| Provider admission | shared selection validation plus existing file/digest/projection checks |
| Isolation | non-E-Commerce and Doc270/E31 regressions |
| Existing fixes | Brain/transport, Vision worker lifecycle, scoped output reading regressions |
| Static | compileall and git diff --check |

## Delivery and remaining production acceptance

Complete local audits and deterministic simulations before pushing and merging.
Do not overwrite concurrent branch changes. Verify the exact merged head.
The VPS acceptance remains a separate production gate: submit a new job with
the previously failing request/assets, confirm actual dispatch, persisted pixels,
project status and count. Simulated success must never be reported as VPS pixel
acceptance. Record actual commands/counts/commits below once validated.


## 2026-09-23 code audit correction model

The merged implementation did not fully implement the authority/order described above. This audit closes five concrete boundaries: malformed budgets are rejected before numeric comparisons; invalid local pools are blocked before Brain dispatch and consume zero recovery attempts; channel resolution is shared and duplicate product identities remain visible for validation; the context digest is carried on accepted Brain results and checked on frozen Runtime activation; and recovery diagnostics use an explicit allowlist including output-count mismatch. Product API and Provider inputs reject non-list/non-string asset ID fields instead of coercing them.