# E28 / Doc267 Post-Generation Review Closure And Professional E-Commerce Delivery Contract

Status: Phase 0 red-contract preparation. This document authorizes no runtime
change, Provider/MCP/ImageGen call, deployment, project/job write, or mutation
of historical production evidence.

## 1. Observed Fact And Correction Model

The observed Professional E-Commerce project `project_65432102a2` produced
real provider pixels for `job_770b54df53`; output `asset_6428fd41d9` was
persisted. Final review then failed while `ExactReviewEvidenceResolver` emitted
the duplicate `person_identity_source_job_binding` reason identifier for three
valid complementary face references. `ReviewEvidenceChannel` correctly rejects
duplicate identifiers, but the failure was not closed at the post-pixel
finalization boundary. The background worker subsequently surfaced
`background_generation_request_invalid`, which is a false public explanation.

The correction is not a retry, prompt change, Provider change, or historical
record repair. The intended flow is:

```text
persisted provider pixels
  -> exact output-scoped review evidence assembly
  -> complete certified receipt OR durable closed non-delivery receipt
  -> review/history-only public output and one terminal project operation
```

Strict identifier uniqueness remains authoritative. The resolver must perform
stable ordered deduplication of repeated reason codes before constructing a
closed `ReviewEvidenceChannel`. It must retain every distinct evidence ID and
source; deduplicating a reason is never permission to drop a face reference.

## 2. Ownership And Boundaries

1. Doc263 product admission/projection and Doc264/Doc265 project-owned
   canonical-reference/channel rules remain unchanged.
2. Product API owns the durable output-scoped finalization receipt after pixels
   exist. A finalization failure is not an external request-validation failure.
3. Project Mode owns the sanitized E-Commerce current operation and the
   four-group public projection. It never reconstructs product truth from
   generated/review history.
4. Desktop and mobile consume that same server operation. They do not infer a
   competing pending state from an older job record.
5. The Provider receives the final server-owned plan only. No Provider routing,
   prompt, MCP, General Template, or Photography behavior changes are in scope.

## 3. Closed Post-Pixel Receipt

When output bytes have been durably stored and final review assembly or
inspection fails, Product API must append a server-owned receipt with a closed
non-delivery state such as `review_withheld_finalization_failed`. The receipt
must bind the current job, output, persisted pixel integrity, and the safe
closure classification. It must state that automatic delivery, replay, retry,
and refinement are disabled, while manual confirmation is required.

The output remains append-only and visible only under
`generated_and_review_history.review_withheld_outputs`. It is not a homepage
thumbnail or a delivered result. Historical projects, jobs, and outputs are
never replayed, rewritten, deleted, or otherwise mutated by this recovery.

`background_generation_request_invalid` is reserved for external/public
generation-payload validation before dispatch. A post-pixel finalization fault
uses a distinct sanitized terminal condition. Raw exception text, filesystem
paths, reason internals, hashes, prompts, and provider bodies remain private.

The public classification pair is closed: a genuine public
`invalid_v3_request` before dispatch maps to
`background_generation_request_invalid`; an already-persisted output followed
by review/finalization failure maps to
`post_generation_review_finalization_failed`. The background worker must
preserve this distinction when it closes the Project Mode job.

`real_pixel_review` is true only when an output has both a complete review
receipt and certified provider-pixel inspection. A metadata-only, incomplete,
or closed receipt cannot consume a refine budget, create a reject
recommendation/package, or automatically deliver an output.

This gate applies inside `OutputQualityReviewMerger.build_package()` before it
computes auto-retry decisions, real-review signal recommendations, hidden
outputs, or user-visible retry wording. Setting `real_pixel_review=false`
after package construction is insufficient: it leaves a metadata-only or
closed receipt able to spend refinement/reject authority that it never earned.
When the receipt is not complete, or any ready output lacks certified
provider-pixel inspection, the package must emit only a non-consuming
manual-review disposition and the durable history/operation receipt.

## 4. Professional E-Commerce Reference Authority

A locked People Visual Asset is server-owned hard identity authority. It wins
over a generic caller control such as `preserve_person_identity=false`. The
final Provider reference plan contains exactly one canonical deduplicated
identity source set, with exact role, channel, pixel, and digest binding and a
count no greater than the negotiated Provider capability.

Product originals remain `product_truth` only. The renderer receives the
per-output `PhysicalProductReferenceProjection` selected product input, not
the whole product pool, and it never treats People identity or history as
product truth.

For Professional E-Commerce N=1, the default deliverable is a
product-primary presentation view. A lifestyle interaction is an explicit
separate deliverable role and may not silently replace the primary product
view merely because the request count is one.

`product_primary_presentation` is a server-issued schema migration for the
N=1 Professional E-Commerce deliverable role. Older valid plans remain
readable through their historical role value, but a new N=1 command must
normalize to the product-primary role and cannot infer a lifestyle interaction
as its main delivery. Explicit multi-deliverable or caller-selected lifestyle
roles remain separately readable and permitted.

## 5. Public Operation And UI

Project Mode publishes one terminal operation for a withheld finalization,
with `terminal=true`, `pending=false`, a manual-review action, and no raw
failure detail. This operation wins over stale planned/generating job state.

Desktop and mobile render the same review-withheld state, expose an explicit
history/review action, suppress preparing/generating/polling presentation, and
make no automatic POST. Opening review is navigation only; a new explicit
Generate remains the sole generation command.

## 6. Compatibility, Security, And Migration

The receipt is additive and append-only. Existing valid delivery receipts keep
their current behavior. Old failed jobs remain history and are not reclassified
until a server-owned read can prove persisted pixels plus finalization closure.
Browser metadata, browser job lineage, raw warnings, and caller-supplied
identity/reference facts are never authority for receipt creation or recovery.

The public projection exposes only safe state, channel class, and action. It
does not disclose source IDs, local paths, digests, exception text, Provider
messages, or review internals.

## 7. Phase Plan And Production Gate

Phase 0: this contract, E00 index update, and deterministic red tests only.

Phase 1: narrow Product API finalization closure, resolver reason dedupe, and
Professional E-Commerce reference/deliverable corrections after audit.

Phase 2: Project Mode public operation and desktop/mobile rendering after
audit, with no General or Photography leakage.

Phase 3: focused local Product API, Project Mode, Doc263-265, UI/browser, and
Provider-output contract verification.

Phase 4: only after merged local acceptance, a guarded production release may
read historical evidence and verify the new release. It must not generate,
replay, retry, mutate, or delete the historical project/job/output.

Production acceptance requires a complete finalization receipt for every
delivery candidate, review-only retention for closed receipts, one terminal
public operation on desktop and mobile, exact Professional E-Commerce identity
and physical-product scope, and zero false request-invalid projections after
pixels are stored.
