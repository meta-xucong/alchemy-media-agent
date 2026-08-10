# Doc260 — V3 Shared Review Evidence Plan and Channel Applicability Contract

Status: **documentation-only correction model and implementation handoff**.
This document does not authorize Provider calls, image generation, retry,
formal-slot receipts, activation, or frontend migration by itself.

Owner layer: shared V3 post-generation review and safe delivery projection.

Related authorities:

- Doc93 — reference-channel policy and prompt ownership;
- Doc113 — normalized execution truth and template ownership;
- Doc117 — real-reference Provider capability and no-pixel failure closure;
- Doc118 — real-pixel review decision and public delivery truth;
- Doc121 — review/reference evidence continuity;
- Doc123 — retry failure and manual-confirmation truth;
- Doc160 — review evidence to Brain repair closure;
- Doc240 — Professional formal-slot Core and reference-bridge governance.

The correction is deliberately shared-foundation work. It must not introduce a
child, apparel, E-Commerce, Photography, or General-template review branch.

## 0. Decision record

The current review path has two independent facts but projects them through
global reference booleans:

1. whether the user supplied a reference for a particular truth channel; and
2. whether the reviewer can resolve the admitted evidence for that channel.

Those facts are not equivalent. A text-directed product generation may have no
product reference by design while still having a person-identity reference.
Conversely, a job may require an admitted person or product reference and lose
that evidence before review. Treating both states as one
`reference_evidence_unavailable` condition can withhold valid output for the
wrong reason, while treating a missing required reference as harmless can
produce a false pass.

The current minimum correction is therefore:

```text
frozen review intent
  -> server-owned channel evidence plan
  -> exact job-scoped evidence resolution
  -> real-pixel inspection whenever pixels exist
  -> channel-aware certification
  -> shared retry / delivery decision
```

The review plan owns applicability and evidence resolution. The Vision
inspection remains the authority for visual findings. Doc118 remains the
authority for retry eligibility and final delivery. No new reviewer or
parallel status machine is introduced.

## 1. Problem statement

### 1.1 Global reference state loses user intent

The following states must remain distinct:

| State | Meaning | Review consequence |
| --- | --- | --- |
| `not_applicable` | The channel is not part of this job's requested truth contract. | Do not require comparison evidence; continue applicable review. |
| `not_provided` | The channel could have been compared, but the user intentionally supplied no reference. | Do not claim reference equivalence; continue prompt and pixel review. |
| `available` | The exact admitted evidence was resolved and is readable for this job/output. | Permit the corresponding comparison or continuity check. |
| `unavailable` | The frozen contract requires evidence, but exact resolution or file verification failed. | Manual/non-certifying review hold; never pass-like fallback. |
| `invalid` | Evidence exists but violates job, source, ownership, or digest binding. | Closed failure; do not substitute another project asset. |

`not_provided` and `unavailable` are especially important. The former is a
valid absence of optional user evidence; the latter is a system failure to
deliver evidence that the frozen job requires.

### 1.2 Pixel review must not depend on reference existence

Once a generated output has pixels, the shared real-pixel inspection remains
required whenever the job's delivery contract requires review. Reference
evidence changes what the reviewer may compare; it does not decide whether the
reviewer examines the output at all.

Therefore:

- no product reference does not disable hand/anatomy, text/watermark,
  composition, realism, artifact, or prompt-semantic review;
- no reference at all does not disable generic pixel review;
- a missing required reference must not be converted into a visual-quality
  finding;
- a metadata-only review must not be presented as a real-pixel pass.

## 2. Corrected authority model

### 2.1 One server-owned plan

Before post-generation review, the Product API or the existing shared review
owner must materialize one immutable, job-scoped `ReviewEvidencePlan`.
Provider and Vision code may consume the plan but may not infer it from public
metadata, project history, filenames, or alphabetic asset ordering.

The plan is internal typed evidence, not a public request field and not a
prompt fragment. Its minimum logical shape is:

```json
{
  "contract_version": "review_evidence_plan_v1",
  "job_id": "<server-owned binding>",
  "output_id": "<exact selected output>",
  "review_mode": "real_pixel | metadata_only",
  "channels": {
    "product_truth": {
      "applicability": "not_applicable | not_provided | required",
      "evidence_state": "not_applicable | not_provided | available | unavailable | invalid",
      "evidence_ids": [],
      "comparison_allowed": false
    },
    "person_identity": {
      "applicability": "not_applicable | not_provided | required",
      "evidence_state": "not_applicable | not_provided | available | unavailable | invalid",
      "evidence_ids": [],
      "comparison_allowed": false
    },
    "prompt_semantics": {
      "applicability": "required",
      "evidence_state": "available",
      "evidence_ids": [],
      "comparison_allowed": false
    },
    "selected_output": {
      "applicability": "required",
      "evidence_state": "available | unavailable",
      "evidence_ids": ["<exact output binding>"],
      "comparison_allowed": false
    }
  },
  "source_binding_digest": "<safe digest>",
  "review_plan_digest": "<safe digest>"
}
```

The concrete implementation may use equivalent typed names, but the following
properties are mandatory:

1. `job_id`, `output_id`, operation identity, and source binding are server
   owned.
2. Every required channel has an explicit evidence state.
3. An optional channel can be `not_provided` without becoming an error.
4. `unavailable` and `invalid` are never silently downgraded to
   `not_provided`.
5. The plan is frozen before the Vision call and is included in the internal
   review receipt by digest, not by raw path or prompt.

### 2.2 Source resolution is exact and bounded

The resolver must use the same admitted source identity that the Provider
materialization audit recorded:

- uploaded `v3_asset_*` references resolve through the server-owned upload
  store;
- generated `v3_output_*` references resolve through the server-owned output
  store;
- library or Character Card references resolve through their exact
  server-owned binding and output/source digest;
- derived crops are eligible only when their parent source and derivative
  scope are already present in the frozen job evidence.

The resolver must validate, at minimum:

- exact job/operation binding;
- source role and truth layer;
- expected output/source ID;
- file existence and readable bytes;
- stored content digest;
- derivative kind or view scope where applicable;
- no cross-project or later-history substitution.

`list_by_job` or full-library scans are not a license to guess. If the frozen
plan identifies exact output IDs, use targeted resolution. If the required
binding is ambiguous, fail closed as `invalid` or `unavailable` according to
whether the record is contradictory or merely inaccessible.

### 2.3 Public metadata is not an authority

Public Job, Project, Browser, and frontend metadata may display safe review
summaries, but it cannot create or repair a `ReviewEvidencePlan`. In
particular, public booleans such as `has_reference`, `reference_available`, or
`review_reference_evidence_available` must not be used to reconstruct channel
applicability.

The Product API owns the typed plan. The shared reviewer consumes it. The
Provider owns the record of what it actually received. The Vision layer owns
pixel findings. Doc118 owns the delivery/retry consequence.

## 3. Review execution contract

### 3.1 Real-pixel entry

For a candidate with a readable generated output:

```text
output file
  -> shared Vision / hybrid inspection
  -> ReviewEvidencePlan channel context
  -> channel results
  -> canonical VisualInspectionReport
```

The reviewer must receive:

- the exact generated output;
- only the evidence channels marked `available`;
- safe channel instructions derived from the frozen plan;
- no raw provider payload, source path, credential, or unrelated project asset.

For `not_applicable` or `not_provided`, the reviewer receives an explicit
“comparison is not required” state. It must still perform every applicable
generic pixel check.

For `unavailable` or `invalid` required evidence, the reviewer may inspect
generic pixels for diagnostic purposes, but the resulting package is
non-certifying for the affected channel and cannot be projected as an
automatic pass.

### 3.2 Metadata-only entry

If no output pixels exist, the existing no-pixel contract remains authoritative:

- no Vision pixel review is fabricated;
- no reference-equivalence pass is emitted;
- no retry is inferred from a missing review;
- the safe result remains a planning/provider/lifecycle state.

This document does not turn metadata-only evidence into visual certification.

### 3.3 Channel-aware result shape

The internal review package should preserve channel facts separately from the
aggregate report:

```json
{
  "review_evidence_plan_digest": "<digest>",
  "real_pixel_review": true,
  "channels": {
    "product_truth": {
      "comparison": "not_applicable",
      "verification_state": "not_applicable"
    },
    "person_identity": {
      "comparison": "performed",
      "verification_state": "verified"
    },
    "prompt_semantics": {
      "comparison": "performed",
      "verification_state": "verified"
    }
  },
  "aggregate_status": "pass | warning | fail_retryable | fail_final | manual_review",
  "certification_state": "verified | unverified | unavailable"
}
```

The aggregate status remains the existing shared `VisualInspectionReport`
authority. A channel with `not_applicable` must not lower the aggregate status,
and a required channel with `unavailable` or `invalid` must not be hidden by a
generic pixel pass.

## 4. Retry and public delivery consequences

Doc118 remains authoritative:

- only a verified, in-scope `fail_retryable` inspection can trigger the
  existing bounded retry;
- an unavailable reference is not itself a visual retry instruction;
- `manual_review`, unverified, or unavailable evidence withholds automatic
  delivery;
- a `not_provided` optional reference does not create a retry or manual hold
  by itself;
- no-pixel/provider-policy failures remain governed by Docs117, 119, 122, and
  123.

The safe public projection may expose compact facts such as:

```json
{
  "real_pixel_review_attempted": true,
  "final_delivery_status": "ready",
  "manual_confirmation_required": false,
  "reference_comparison": {
    "product_truth": "not_applicable",
    "person_identity": "verified"
  }
}
```

It must not expose:

- local file paths or raw reference payloads;
- full prompts or Provider replies;
- private source/output IDs unless an existing safe public contract already
  permits them;
- internal retry patches or resolver diagnostics.

When a real-pixel review has completed, stale planning text such as “review was
metadata-only” must not survive in the final public summary. When no real-pixel
review happened, the old metadata-only state must remain distinguishable from a
real pass.

## 5. Legacy compatibility and migration

Existing jobs may contain only global reference booleans or old review
metadata. They must not be silently treated as equivalent to the new plan.

The compatibility adapter may derive a plan only from server-owned, job-scoped
records:

1. an explicitly recorded source role maps to the corresponding channel;
2. an exact admitted evidence record maps to `available`;
3. an explicit user omission maps to `not_provided` only when the job contract
   proves that the channel was optional;
4. missing or contradictory legacy facts map to `unavailable` or `invalid`;
5. ambiguous legacy state is never promoted to an automatic pass.

Reinspection of an existing output is allowed:

- append a new plan and review package;
- reuse the existing output;
- do not create a new generation job;
- preserve the historical review package;
- permit delivery only through the current verified review authority.

## 6. Implementation handoff

The implementation should be delivered as one shared correction with no
template-specific branch.

### Phase 0 — red contract tests

Add deterministic tests that fail before implementation:

1. text-directed product generation with no product reference and a valid
   person reference creates `product_truth=not_provided` or
   `not_applicable`, resolves person evidence, and still enters real-pixel
   review;
2. no references still enters generic real-pixel review when output pixels
   exist;
3. a required product/person reference whose exact file is missing becomes
   `unavailable` and cannot produce a certified pass;
4. a generated `v3_output_*` person reference resolves through the output store
   rather than the upload store;
5. a wrong job/output/source binding becomes `invalid` and does not fall back
   to another asset;
6. a real `vision_model`/`hybrid` inspection suppresses the stale planned-only
   public hint, while a true metadata-only result retains it;
7. an optional missing reference does not trigger retry or manual hold by
   itself;
8. a verified retryable visual defect still follows the existing bounded retry
   path; and
9. legacy ambiguous booleans remain non-certifying and do not become a
   pass-like review.

### Phase 1 — typed plan and exact resolver

Implement the smallest shared typed plan/resolver seam in the Product API or
existing shared review owner. Reuse existing source/output stores and
Doc121 continuity rules. Do not add a new provider route or a new Vision
authority.

Required negative behavior:

- missing required evidence: closed non-certifying result;
- wrong source/job/output: closed invalid result;
- missing output pixels: existing no-pixel behavior;
- public metadata attempting to forge the plan: rejected;
- unrelated project/history asset: never selected.

### Phase 2 — Vision/review integration

Pass the plan digest and safe channel state into the existing shared review
attachment seam. Preserve the canonical `VisualInspectionReport`, issue
thresholds, retry budget, and review provider contract. Add evidence to the
internal receipt only through safe typed projection.

### Phase 3 — public delivery projection

Project only compact applicability and certification facts. Ensure the
beginner-facing result surface distinguishes:

- no comparison requested;
- comparison requested and verified;
- required evidence unavailable;
- pixels not reviewed.

Do not expose raw IDs, paths, prompts, or Provider bodies.

### Phase 4 — readback and acceptance

Run focused shared-review, Product API, output-store, and public-projection
regressions. Then perform one controlled reinspection of an existing output
with no new generation request. A real Provider/ImageGen run is not required
to accept the contract correction; if one is later authorized, it must use the
same frozen plan and bounded review gate.

## 7. Acceptance matrix

| Scenario | Pixel review | Reference comparison | Expected result |
| --- | --- | --- | --- |
| Text-only product, no product reference | Yes | Product `not_provided` | Generic review continues; no reference failure |
| Person continuity reference available | Yes | Person `available` | Person channel may certify |
| No references at all | Yes | All optional channels `not_provided` | Generic review continues |
| Required reference file missing | Yes, diagnostic only | Required channel `unavailable` | Non-certifying/manual hold |
| Wrong output/source binding | No certification | Required channel `invalid` | Closed failure; no fallback |
| Visible pixel defect, no product reference | Yes | Product `not_applicable` | Explicit visual issue; existing retry rules apply |
| Vision service unavailable | No completed real review | Any | Review unavailable; no pass-like delivery |
| Existing output reinspection | Yes | Rebuilt from server-owned history | No new generation; append-only review |

## 8. Non-goals and supersession

This document does not:

- change Doc93 reference ownership;
- make an ordinary portrait or generated output inherit style, wardrobe,
  scene, hair, or lighting channels;
- turn product/person examples into shared runtime branches;
- weaken Doc118 retry or delivery gates;
- replace Doc121 evidence continuity;
- make metadata-only review equivalent to real-pixel review;
- add a local prompt recipe, threshold adjustment, fallback reviewer, or
  Provider retry;
- authorize a real generation or activation gate.

Any older wording that uses one global “reference available” boolean to decide
whether the entire output may receive real-pixel review is superseded by this
document. Older records remain historical evidence and are not rewritten.

## 9. Handoff to implementation

Implementation owner: mainline V3 shared review/Product API owner.

The receiving implementation thread must:

1. acknowledge Doc260 as the contract authority;
2. add the Phase 0 red tests before changing runtime;
3. keep the change in a dedicated feature worktree;
4. preserve the existing review, retry, receipt, and activation authorities;
5. report exact changed files and focused results before integration;
6. avoid real generation until deterministic regressions are green.

Review outcome for this handoff:

```text
approved for deterministic contract-test and shared-runtime implementation;
not approved for Provider/ImageGen generation, retry, or activation by the
document-only milestone.
```
