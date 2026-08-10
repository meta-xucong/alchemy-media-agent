# E26 / Doc264 Legacy Product Reference Recovery Contract

Status: Phase 0 contract and deterministic red-test milestone only. This
document authorizes no runtime change, Provider/MCP/ImageGen call, deployment,
or production-record mutation.

## 1. Scope And Authority

Doc264 is specialized Professional E-Commerce Project Mode recovery. It
extends Doc262 content-hash canonicalization and Doc263 ProductTruthAdmission /
PhysicalProductReferenceProjection recovery. It does not change General
Template behavior, shared review, Brain creative ownership, provider routing,
or visual-asset ownership.

The owning authority is:

```text
Project Mode current canonical project references
  -> Product API admission / legacy re-attestation boundary
  -> fresh Doc263 command and projection
  -> public E-Commerce project projection
```

The Provider only consumes a current typed admission and projection. It never
repairs legacy records, infers product truth, or receives a request after an
admission failure.

## 2. Observed Mismatch

A historical Professional E-Commerce project has four real product originals,
but duplicated durable product-reference records grew its visible historical
set to eight. Its blocked pre-Doc263 job retains four uploaded asset IDs but
has no `doc263_project_canonical_product_asset_ids`. A new explicit Generate
has no browser-pending uploads and therefore must resolve the current project
references.

The current broad admission failure is exposed as
`product_truth_admission_invalid`. That incorrectly makes a recoverable legacy
record shape look like a request for the user to re-upload correct bytes. It
also risks retaining an old blocked error as the current operation.

Separately, a locked people visual asset is projected as generic `people` or
an internal identifier instead of its server-owned `display_name`.

## 3. Correction Model

An explicit E-Commerce Generate is a new command against current canonical
project state. It is not a resume or replay of an incompatible old frozen
admission.

1. Project Mode derives one ordered active product pool from ready
   project-owned uploaded references using the actual file SHA-256. The order
   is deterministic first-admitted order across distinct upload asset IDs.
2. Same-content duplicate project-owned associations become inactive,
   append-only history: only the duplicate `ProjectReferenceAsset` and its
   matching `uploaded_asset_refs` mirror may change state. The global V3 upload
   record remains `ready` with its durable bytes/SHA unchanged and may still be
   referenced by another project. Duplicate associations are never deleted,
   counted in the active pool, or sent as physical product inputs.
3. Generated or review outputs remain generated/history evidence even when a
   legacy use policy says `product`; they never become ProductTruthAdmission
   sources without an explicit existing user promotion contract.
4. A ready legacy upload without the post-Doc263 upload receipt may be
   re-attested only when the closed persisted
   `v3_legacy_upload_authorization_facts_v1` server fact structure proves:
   `v3_uploaded_asset_store` authority, asset ID, actual readable bytes and
   matching SHA-256, ready state, `product_reference` role, `product_truth`
   channel, and nonblank durable consent and rights facts. Generic upload
   metadata, browser metadata, and caller-provided lookalike objects are not
   an authority.
5. Re-attestation is server-owned and idempotent. It emits one
   standard `v3_upload_authorization_receipt_v1` plus one immutable
   `doc264_legacy_product_reference_reattestation_v1` marker. Both bind the
   asset ID and actual SHA-256; the marker also binds the persisted
   role/channel and source fact schema. Replay neither creates another receipt
   revision nor changes either digest/marker. Re-attestation never trusts
   browser metadata or rewrites bytes.
6. Missing, tampered, non-ready, role/channel-drifted, or unproven
   consent/rights facts fail closed before planning/provider dispatch. Their
   terminal public receipt creates no fresh active planning or generation
   command.
7. Doc264 applies only when the current project has active uploaded product
   originals. A project without active product originals retains the existing
   E-Commerce no-product-reference/text-to-image path; it is not diverted into
   re-attestation or `needs_input`.
8. A successful explicit Generate creates one fresh Doc263 job with a new
   command identity and `supersedes_job_id` only for a server-detected,
   same-project, legacy-incompatible blocked job. Browser history flags,
   warnings, and arbitrary blocked jobs cannot request or qualify for
   supersession. The old job and its diagnostics remain append-only history.
   Replaying the same idempotency action returns that one fresh job only.

## 4. Failure And Public Projection

Current invalid input and recoverable legacy migration are distinct:

| State | Meaning | Public state |
| --- | --- | --- |
| `ecommerce_legacy_reference_recovery_required` | Current canonical bytes and durable legacy facts can be re-attested. | Server performs the bounded re-attestation, then creates a fresh command. |
| `ecommerce_product_input_needs_attention` | Current product evidence is missing, unreadable, mismatched, or lacks required durable facts. | Terminal `needs_input`, `pending=false`, exactly one `review_product_inputs` action. |
| `reference_projection_drift` | A valid current admission lost an internal physical projection. | Existing Doc263 fresh-continuation recovery applies. |

Raw internal codes, file paths, hashes, Provider payloads, and historical error
text do not enter `current_operation` or public job status. A terminal invalid
input must not leave a preparing/polling state and must not auto-dispatch.

The E-Commerce project view remains exactly four groups:

1. `original_product_inputs`
2. `locked_person_identity`
3. `selected_continuation_directions`
4. `generated_and_review_history`

The locked-person item includes the catalog-resolved server-owned
`display_name`. Desktop and mobile use it as the locked-person card's primary
label. Internal identifiers may be secondary detail only; `asset_type` such
as `people` is not the selected asset's name. A missing catalog asset uses the
safe generic label `已绑定人物资产`; it never guesses from or trusts caller
metadata.

## 5. Boundaries And Non-Goals

- No automatic promotion of generated/review images to product truth.
- No deletion of duplicate history, old jobs, bytes, or review records.
- No browser-provided admission, receipt, canonical digest, lineage, or
  re-attestation authority.
- No generic fallback that silently treats missing facts as consent/rights.
- No Provider/MCP/ImageGen call on a closed admission.
- No General Template, Photography, shared foundation, or Provider-routing
  behavior change.

## 6. Phase Plan

Phase 0 adds this contract and deterministic red tests only.

Phase 1 may implement Project Mode canonicalization plus the Product API
re-attestation boundary after pre-implementation audit approval.

Phase 2 may add the public recovery projection and desktop/mobile presentation
after focused runtime tests pass.

Phase 3 requires separate local integration, browser, GitHub/main, and guarded
deployment review. Passing any phase is not full product acceptance.

## 7. Required Regression Matrix

The runtime implementation must make all of the following deterministic tests
green without external services:

1. Four pairs of separate upload asset IDs with identical bytes canonicalize
   in first-admitted order to four active sources, retain four inactive
   noncanonical references and four inactive legacy mirrors, and do not
   re-upload or rewrite bytes. The duplicate upload records remain ready and
   content-identical, and may still be associated with another project.
2. Valid ready legacy uploads with only the closed persisted server fact
   structure receive one exact standard receipt plus one bound re-attestation
   marker, then form a fresh Doc263 admission. Replay leaves both unchanged.
3. Missing, SHA-drifted, role/channel-drifted, or consent/rights-missing facts
   fail closed before both Brain planning and Provider dispatch and project a
   sanitized terminal `needs_input` action without a fresh active planning or
   generation command. The same applies to a non-ready legacy record.
4. Only a server-detected same-project pre-Doc263 incompatible blocked job is
   superseded by one clean fresh command from current canonical references; a
   replay returns that same command and does not expose stale error text.
   Browser flags and unrelated blocked jobs cannot request supersession.
5. Generated/review sources never enter recovered original product truth.
6. The exact selected visual asset
   `visual_asset_0000_professional_card_rebuild_fresh_20260726` projects
   `Six-Year-Old Child Professional Character Card` as its public display
   name, and both desktop and mobile render that name as the locked-card
   primary label. Missing catalog resolution uses only the safe generic label.
7. A new or existing E-Commerce project with no active uploaded product
   originals retains the existing no-product-reference/text-to-image route and
   does not receive Doc264 re-attestation or `needs_input`.
