# Doc287 - V3 Multi-Output Identity Anchor And Evidence Binding Closure

Status: **implementation authority for the shared V3 foundation**.

This document defines the smallest complete repair for multi-output V3 jobs in
which later images use the first image from the same batch as a continuity
anchor. It closes the known evidence-binding, ordering, retry, replay, and
historical-source compatibility defects without replacing the V3 architecture.

This is a local implementation specification. It does not authorize a GitHub
push, VPS deployment, Provider/MCP/ImageGen call, V1/V2 change, or Sub2API
change.

## 1. Objective

Make a multi-output V3 job deterministic and provenance-safe when the shared
Brain decides that later outputs should preserve the first output's identity.

The repaired behavior is:

```text
first planned output
  -> server-persisted canonical output record
  -> immutable same-batch continuity binding
  -> later outputs consume that binding as Provider input context
  -> formal review evidence remains independent
  -> retry and fresh-service replay reuse the same source
```

The repair must simultaneously guarantee:

1. A generated continuity anchor never becomes user truth merely because it is
   present in `reference_assets`.
2. Only the first planned, initial, persisted output can become the automatic
   anchor.
3. A retry, extra Provider output, later asset, or file path cannot replace it.
4. Every source and target relationship is validated against canonical
   OutputStore records and actual file bytes.
5. Existing explicit uploaded references and explicitly selected historical
   outputs retain their current strict evidence rules.
6. Public project/history projections contain no private binding data.
7. The same rules work for General and Professional V3 without scenario
   keywords, regular expressions, or vertical-specific prompt recipes.

## 2. Authority And Scope

| Concern | Authoritative source | Required behavior |
| --- | --- | --- |
| Whether automatic continuity applies | Frozen Brain task/profile and capability plan | Brain makes the semantic decision; runtime only verifies typed facts. |
| Creative meaning and prompt | Frozen Brain canonical prompt | No local prompt reconstruction or keyword interpretation. |
| Source/target identity | OutputStore records | Provider output IDs, paths, filenames, and response order are not authority. |
| Planned position | Frozen server series/output plan | Do not infer position from lexicographic IDs or Provider response order. |
| Automatic continuity | Private Doc287 binding | Input transport context only; never formal user truth. |
| Uploaded/project-selected truth | Existing Doc93/Doc95/Doc260/Doc285 contracts | Remains formal evidence and remains strictly validated. |
| Review certification | Exact Review Evidence Resolver and shared Vision Review | Keep the existing strict gate for formal evidence. |
| Retry | Existing Product API retry owner | Retry is append-only and reuses the original anchor. |
| Public visibility | Existing safe final/review projection | Strip all private IDs, digests, paths, prompts, and Provider data. |

This is shared foundation work. It must not add an E-Commerce deliverable map,
change General scenario semantics, or alter E-Commerce product-truth
authority. Doc269/Doc270/Doc281 output-plan and source-library bindings remain
independent from Doc287 continuity semantics.

## 3. Terminology And Origin Types

Every reference entering the shared runtime must have one explicit server-owned
origin. The new path uses exact typed values, never substring inference.

```text
explicit_uploaded_truth
explicit_project_selected_truth
historical_selected_output_truth
professional_server_owned_truth
auto_batch_continuity
```

Only `auto_batch_continuity` is introduced by this document. It is not a
formal review evidence channel and it is not a memory promotion event.

The four existing review channels remain:

```text
product_truth
person_identity
prompt_semantics
selected_output
```

No public fifth channel is added for continuity.

## 4. Current Defects To Close

### 4.1 Continuity is promoted to formal truth (P0)

The current central loop creates a `generated_first_output` reference and the
Provider's reference-truth package can classify it as portrait identity truth.
The review resolver then consumes it as a formal `person_identity` source.

This produces a deterministic false hold such as:

```text
review_evidence_person_identity_invalid
selected_output_content_integrity
source_job_binding
```

The image pixels may be valid; the failure is the source's semantic origin.

### 4.2 The fallback re-promotes the same source (P0)

Using `reference_truth_source_ids or reference_asset_ids` means removing an
automatic source from `reference_truth_source_ids` is insufficient. The
generic reference list raises it back into formal evidence.

### 4.3 Any reference entry becomes required (P0)

The current channel builder treats every resolved entry as
`applicability=required`, even when the entry is only transport context. An
invalid continuity transport reference therefore blocks formal certification.

### 4.4 The source is selected before canonical eligibility is known (P0)

The central loop can create the anchor from a selected candidate's file path
and candidate metadata. It does not require a canonical persisted output, a
matching server plan position, a source digest, or a source record digest.

### 4.5 "First" is not enforced (P0)

The current condition is effectively "the first selected candidate that exists"
rather than "the first planned asset at position zero". If the first planned
asset fails, a later asset can become the anchor. A Provider extra output can
also be selected even though it is not the planned first output.

### 4.6 Retry does not carry one immutable anchor (P0)

The retry request is rebuilt from the original request metadata. The dynamic
anchor created during the first Brain run is not a durable batch fact, so a
retry can lose the original anchor or create a second anchor.

### 4.7 Candidate, response, and packaged output may diverge (P1)

Provider response order, candidate selection, and the packager's per-asset
dictionary can disagree about which image is the selected output. The source
used by Brain must be the same canonical record later reviewed and displayed.

### 4.8 Review can fall back to an unbound path (P1)

The output resolver can construct a ready resolution from a candidate/file
path when no OutputStore record is found. Formal review and Doc287 binding
must require a canonical persisted record.

### 4.9 Historical selected-output fields are incomplete (P1)

Some older selected generated outputs have a valid project-level
`source_integrity_id` but lack a record-level `content_sha256`. The current
resolver can reject a valid file because it trusts only the incomplete record
metadata. This is a separate origin from same-batch continuity and must use
the existing Doc285 compatibility boundary.

### 4.10 New semantic rules must not use string heuristics (P1)

The Provider still has legacy helpers that inspect role, filename,
`source_type`, or lock-target text. They may remain for reading legacy records,
but the new Doc287 path must use exact typed origin and Brain-signed policy
facts. No new keyword table, regular expression, or language-specific branch
is allowed.

### 4.11 Concurrent first-source claims need one authority (P1)

The normal Brain loop is serial, but independent workers or a retry race can
attempt to claim an anchor for the same Job. The Job's anchor receipt needs an
atomic first-writer-wins claim or an equivalent existing store lock.

## 5. Invariants

The implementation is correct only if all of these remain true:

1. Automatic continuity is enabled only by a frozen typed Brain profile:
   human/portrait-led, real-image, non-stylized, at least two planned outputs,
   no explicit user/project truth source, and not E-Commerce.
2. The source is exactly frozen series plan position `0` and Doc281 output-plan
   index `1` where that plan is present.
3. The source is from the initial materialization, not a retry, refinement,
   extra Provider response, or MCP resume without an explicit contract.
4. The source has a canonical OutputStore record and actual bytes whose SHA-256
   matches the server binding.
5. The source binding is immutable for the entire logical Job.
6. Every later target points to that same source binding; no target can become a
   new source.
7. Continuity references are Provider input context, not formal review truth.
8. An ordinary current-Job selected output remains invalid under Doc260/285.
9. A historical selected output is valid only through a server-owned binding
   with project, source Job, output, and integrity checks.
10. Public projections never expose Doc287 or other private evidence facts.

## 6. Minimal Data Contract

### 6.1 Source skeleton and finalized binding

Reuse the existing server-owned digest-only envelope pattern used by Doc281,
but keep the key and semantics separate. The pre-save skeleton contains only
facts already frozen by the server:

```json
{
  "schema_version": "doc73_auto_identity_anchor_binding_v1",
  "origin": "auto_batch_continuity",
  "policy_version": "doc73_v1",
  "job_id": "server-job-id",
  "project_id": "server-project-id",
  "batch_plan_digest": "sha256",
  "source_asset_id": "server-asset-id",
  "source_plan_position": 0,
  "source_output_index": 1,
  "source_candidate_id": "server-candidate-id",
  "binding_digest": "sha256"
}
```

At the `save_base64_output` boundary, the OutputStore finalizer adds and
recomputes the source fields that only exist after persistence:

```text
source_output_id
source_content_sha256
source_record_binding_digest
```

The finalized envelope, not the skeleton, is the only value eligible for a
later continuity request. No Provider-supplied output ID, URL, path, prompt,
account, or model field may author either phase of the envelope.

### 6.2 Target binding

Each later persisted output may carry a private target binding derived from the
same immutable source receipt:

```json
{
  "schema_version": "doc73_auto_identity_anchor_binding_v1",
  "origin": "auto_batch_continuity",
  "job_id": "same-server-job-id",
  "project_id": "same-server-project-id",
  "batch_plan_digest": "same-sha256",
  "source_binding_digest": "same-sha256",
  "source_output_id": "canonical-source-output-id",
  "target_asset_id": "server-target-asset-id",
  "target_plan_position": 1,
  "target_output_id": "canonical-target-output-id",
  "target_record_binding_digest": "sha256",
  "binding_digest": "sha256"
}
```

The target output ID and target record digest are finalized by OutputStore.
The binding is private and is never copied to public project/history output.

### 6.3 Job-level receipt

Use one immutable Job-level `doc73_auto_identity_anchor_receipt` as the
canonical source claim. Output records mirror its digest for local validation;
they do not create competing anchor decisions.

```text
missing receipt              -> no automatic anchor
valid receipt                -> reuse its exact source
present malformed receipt    -> fail closed to no automatic anchor
concurrent claim conflict    -> keep the first valid claim only
```

## 7. Corrected Lifecycle

### 7.1 Brain decision

The Brain supplies typed semantic facts. Runtime checks only the frozen
contract:

```text
auto_anchor_enabled =
    real_image_generation
    and requested_count >= 2
    and frozen_subject_type is human/portrait-led
    and frozen_rendering_mode is photoreal/non-stylized
    and no explicit truth reference exists
    and scenario is not ecommerce
```

Do not recover missing facts from raw prompt words. If the typed profile is
absent or contradictory, disable the optional automatic chain rather than
guessing.

### 7.2 First output claim

Only after output position zero has been materialized:

1. Validate the frozen series plan and Doc281 output-plan position.
2. Require initial attempt/refinement round zero.
3. Require the selected candidate to be the planned first candidate, not an
   extra response item.
4. Require a canonical OutputStore record and readable bytes.
5. Recompute the actual SHA-256 and record binding digest.
6. Require the existing typed no-hard-failure/anchor-eligible result.
7. Atomically claim the Job-level receipt.
8. Only then expose a private Doc287 continuity reference to later requests.

If any step fails, no replacement anchor is invented. The later output either
uses the existing text-only contract or stops at the explicit Provider input
boundary when the frozen Brain contract says continuity is mandatory.

### 7.3 Later outputs

Later requests receive a separate internal continuity collection. The Provider
may use its image bytes for identity continuity, but the collection is not
passed to the formal evidence source list.

```text
formal_truth_references     -> uploaded/project-selected truth only
continuity_reference        -> validated Doc287 source only
```

The exact `origin=auto_batch_continuity` marker is preserved until the review
metadata is assembled, where it is consumed as advisory comparison context or
removed. It must not be interpreted by `_is_human_truth_reference` or another
substring classifier.

### 7.4 Review

The Exact Review Evidence Resolver must:

1. Parse formal truth IDs only from the explicit formal-truth field when that
   field is present; do not use `or reference_asset_ids` as a truth fallback.
2. Preserve each source's exact origin while collecting candidates.
3. Route `auto_batch_continuity` to a dedicated binding validator, not the
   ordinary historical selected-output resolver.
4. Validate source/target Job, project, plan position, output ID, candidate ID,
   SHA, record digest, and actual bytes.
5. Treat a valid automatic anchor as advisory continuity context, never as a
   required `person_identity` evidence entry.
6. When only automatic continuity exists, keep `person_identity` at
   `not_applicable` rather than manufacturing an invalid evidence failure.
7. Preserve the strict four-channel gate for actual requested formal truth.

An invalid Doc287 binding is recorded as private non-certifying continuity
diagnostic data or omitted. It must not be converted into
`review_evidence_person_identity_invalid` solely because the automatic source
was not formal evidence.

### 7.5 Retry and replay

Retry metadata must carry the immutable Job receipt and source binding through
the existing server-owned runtime metadata path. A retry:

- reuses the original source output ID and binding digest;
- may create a target output binding for its own target;
- never becomes the source anchor;
- never uses Provider response order to select a replacement;
- remains append-only and reviewable under existing final-delivery rules.

Fresh service instances must read the same receipt and OutputStore records with
zero Provider or analyzer calls.

### 7.6 Final-delivery project projection

When a modern real-pixel review gate applies, the Job's public
`post_generation_review.recommended_output_ids` is the authoritative final set
for the Project result surface and recent-project thumbnails. Per-output
`delivery_preferred_output` metadata may support legacy attempt comparison, but
it must not widen or replace that exact Job-owned set. If a compatible status
does not expose the list, only exact verified `pass`/`warning` review rows may
be used; an output without its own eligible row remains review-only.

## 8. Historical Selected-Output Compatibility

Doc287 must not merge historical selected-output truth with automatic
continuity. The existing Doc285 path remains authoritative:

```text
server project association
  -> canonical source output_id + source_job_id
  -> OutputStore record
  -> actual file hash
  -> frozen source_integrity_id compatibility check
  -> formal person_identity evidence
```

For a legacy record without a record-level `content_sha256`, the exact
server-frozen project `source_integrity_id` may certify the file after the
runtime recomputes its SHA. Any present record-level digest must also match.

The following remain invalid:

- missing or malformed project binding;
- wrong source Job or project;
- swapped output ID;
- changed file bytes;
- ordinary current-Job selected output;
- browser/client-selected IDs without a server-owned binding.

No broad historical rewrite is required for the first implementation.

## 9. Candidate And Output Consistency

Make the existing selected-candidate path use one authoritative key:

```text
(server asset_id, frozen plan position, selected candidate_id, output_id)
```

The packager must not let a later candidate silently overwrite an earlier
candidate for the same asset. The output resolver must prefer canonical
OutputStore records and must not return a review-ready resolution from a bare
path when a formal binding is being evaluated.

Provider response fields such as `request_index`, output URLs, and
Provider-supplied output IDs are diagnostic only. They cannot author plan
position, source identity, or disclosure.

## 10. Compatibility And Failure Behavior

| Condition | Result |
| --- | --- |
| Valid automatic source binding | Later Provider inputs may use continuity context; no formal identity evidence is created. |
| Missing/malformed automatic binding | Omit optional continuity or close at the input boundary with a clear private code. Never create formal invalid identity evidence. |
| First planned output missing | No later output becomes the anchor. |
| First candidate hard failure | No automatic anchor. |
| Extra Provider output | Never an automatic anchor. |
| Retry output | Never an automatic anchor; points to original source if valid. |
| Explicit upload/project truth exists | Automatic anchor disabled; existing truth path wins. |
| Ordinary current-Job selected output | Remains invalid. |
| Valid historical selected output | Existing Doc285 formal path may certify it. |
| Public projection | Only existing safe final/review-visible output fields remain. |

## 11. Minimal Implementation Surface

The implementation should remain within existing boundaries:

1. `creative_core/doc281_output_plan_binding.py` or its adjacent existing
   envelope helper: add the small Doc287 issuer/validator with an independent
   schema key; do not build a second queue or state machine.
2. `creative_core/central_brain.py`: claim only the first canonical planned
   output and pass typed continuity metadata.
3. `generation_router/providers.py`: keep continuity references separate from
   formal truth; stop legacy classifiers from interpreting the new marker.
4. `product_api/outputs.py`: finalize source/target binding at the existing
   OutputStore persistence boundary.
5. `product_api/service.py`: carry the immutable receipt through retry and
   replay; preserve append-only result behavior.
6. `shared_capabilities/visual_cluster/review_evidence.py`: separate formal
   truth parsing from continuity validation and preserve requested-channel
   semantics.
7. `product_api/output_resolver.py`: require canonical records for formal
   review/binding paths.
8. `asset_pack/packager.py`: preserve the server-selected candidate/output
   relationship by plan position.
9. Existing Doc73/Doc95/Doc285 documentation and focused tests: update the
   semantic boundary and add integration regressions.

No changes are required to V2, Sub2API, E-Commerce product truth, the public
API schema, the frontend, or Provider retry policy unless a regression proves a
projection defect at that boundary.

## 12. Required Regression Matrix

All tests use a deterministic fake Provider and temporary OutputStore. They do
not call a real Provider, MCP, ImageGen, GitHub, or VPS.

### 12.1 Normal two-output flow

- First planned output is persisted as the sole source anchor.
- Second output receives exactly that source as continuity input.
- Review produces no `review_evidence_person_identity_invalid` solely because
  of the automatic anchor.
- Only final/review-eligible outputs enter existing delivery projections.

### 12.2 Source eligibility and ordering

- First planned output missing: no anchor.
- First candidate hard-failed: no anchor.
- Second planned output succeeds first: it cannot become the anchor.
- Provider returns multiple outputs: only planned output position zero may
  source; extra outputs cannot source.
- Provider output IDs and response indexes are forged: server identity wins.

### 12.3 Binding integrity

Each mutation must fail closed without becoming formal invalid identity truth:

- source output missing;
- source file missing or changed;
- source SHA changed;
- source record digest changed;
- source Job/project changed;
- source asset or plan position changed;
- target output ID swapped;
- target record digest missing or changed;
- source/target binding digest changed;
- foreign Job or project;
- missing or malformed envelope.

### 12.4 Retry and replay

- Retry reuses the original source binding.
- Retry output never replaces the source.
- Extra/retry output without an envelope is not disclosure-eligible as an
  anchor.
- Fresh service/review replay performs zero Provider/analyzer calls.
- Concurrent first claims are first-writer-wins and deterministic.

### 12.5 Formal truth compatibility

- Explicit uploaded portrait/product truth remains formal and strict.
- Historical selected-output truth remains formal and strict.
- Legacy selected output with only a valid server-frozen integrity digest can
  be read after actual hash verification.
- Ordinary current-Job selected output remains invalid.
- Removing automatic truth IDs cannot cause a fallback from
  `reference_asset_ids` to re-promote continuity.

### 12.6 Foundation generality and privacy

Run the same shared tests with materially different scenes:

- adult group portrait;
- lifestyle/person scene;
- product-on-person scene.

No test may require an ancient-style, kidswear, or other narrow branch. Public
projection tests must prove no Doc287 envelope, source ID, SHA, file path,
prompt, Provider, account, or private review rationale is emitted.

## 13. Implementation Order And Audit Gates

### Gate A - contract and failing regressions

1. Add this Doc287 authority and cross-reference Doc73/Doc95/Doc285.
2. Add the real two-output OutputStore/review regression before production
   edits.
3. Add source-order, retry, tamper, historical compatibility, and public
   projection regressions.

### Gate B - one bounded runtime repair

1. Add the private Doc287 envelope issuer/validator.
2. Move the anchor claim to the canonical first-output persistence boundary.
3. Separate continuity transport from formal truth in Provider and review.
4. Carry one immutable receipt through retries and replay.
5. Tighten candidate/output resolver consistency.

### Gate C - local acceptance

The focused matrix, adjacent V3 foundation/Professional suites, Python
compile, JavaScript checks, and `git diff --check` must pass from a fresh
temporary store. No remote action is permitted before this gate.

### Gate D - controlled real validation

Only after Gate C may a separately authorized local or VPS real-image run be
considered. The run must use an existing authorized project, record source and
target output IDs, verify the private binding, and confirm that the public
review result does not classify the continuity source as formal identity truth.

## 14. Stop Conditions

Stop and return to theory-first audit if implementation requires:

- a new retry subsystem or duplicate retry counter;
- global relaxation of the evidence gate;
- acceptance of all current-Job outputs;
- client/browser metadata as authority;
- Provider response order or filenames as identity;
- prompt keyword/regular-expression classification;
- a General/E-Commerce/Photography-specific branch in shared code;
- public exposure of private binding facts;
- automatic memory promotion of unselected generated outputs;
- V2, Sub2API, or unrelated frontend changes.

## 15. Acceptance Definition

Doc287 is complete only when:

1. The observed same-batch false evidence failure is eliminated by origin
   separation, not by weakening the review gate.
2. A real two-output materialization proves source and target canonical
   bindings.
3. Missing, stale, tampered, swapped, extra, retry, and cross-Job sources fail
   closed without selecting a replacement anchor.
4. Historical selected-output compatibility passes through the existing Doc285
   server-owned path.
5. Fresh-service replay is deterministic and provider-free.
6. Explicit truth, Professional paths, General neutrality, and E-Commerce
   product truth remain unchanged.
7. Public output remains safe.
8. All focused and adjacent tests plus static checks pass.

Passing a metadata-only Doc73 unit test is not sufficient. The integration
acceptance must exercise real OutputStore persistence, review resolution,
retry/replay metadata, and public projection.
