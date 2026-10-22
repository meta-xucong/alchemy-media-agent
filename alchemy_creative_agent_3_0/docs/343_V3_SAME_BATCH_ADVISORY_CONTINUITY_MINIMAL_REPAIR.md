# Doc343 - V3 Same-Batch Advisory Continuity Minimal Repair

Status: **implementation and deterministic checks passed; final local integrated
real acceptance completed in Doc344 section 8; VPS deployment excluded**.

Scope: V3 Foundation, Doc73/Doc287 same-batch advisory continuity and Doc322
frozen Provider inputs.

Scope amendment: Doc344 supersedes this document's photo-only character scope
and the persistent anchor's position-zero/original-only restrictions. The
same-batch temporary source remains the immutable Doc287 position-zero source.
Historical acceptance evidence below is retained without reinterpretation.
Doc344 section 8 supersedes the pending acceptance status below with new positive
real evidence; the earlier review-withheld runs remain failures as recorded.

## 1. Objective and observed defect

For an eligible text-only human portrait batch, use the first canonical output
as temporary identity continuity context for the remaining outputs. After the
normal full-batch visual review, the existing Doc322 path may bind that first
output as the project's persistent anchor only if it is formally eligible.

The observed four-image job produced four outputs but its frozen
`ReferenceInputPlan` contained no continuity source, and its policy had
`enabled=false` / `applied=false`. The immediate Brain gate requires
`frozen_reference_plan is None`; removing that predicate alone would still
fail because Production Provider returns only `plan.references()` when a
frozen plan exists and ignores dynamic `reference_assets` metadata.

## 2. Selected behavior and authority

The user selected the simple advisory-first behavior. This document makes the
following distinction explicit:

- **Same-batch advisory reference:** Doc73/Doc287 job-local transport context.
  It may be consumed by later outputs before the batch's formal visual review.
  It is not a project binding, formal identity truth, or a claim that the first
  image passed.
- **Project continuity anchor:** Doc322 persistent project state. Only the
  first planned output that satisfies the existing final-delivery review and
  canonical binding requirements may be bound. No later image can replace it;
  manual binding/unbinding remains authoritative.

Doc343 narrows the Doc322 wording “first formally passing image as later
continuity reference”: “later continuity reference” means the persistent
project reference for subsequent jobs. Intra-job temporary context remains
governed by Doc73/Doc287. The matching clarification is recorded in Doc322
§1, §4.1, and §4.2.

No review timing changes, added review calls, new eligibility rules, new
module, new public contract, or project-state mutations are introduced.

## 3. Minimal implementation

### 3.1 Central Brain predicate

In `creative_core/central_brain.py`, allow the existing Doc73 eligibility
decision when a frozen plan is present if all existing conditions still hold:

- real, multi-output text-only Standard generation;
- human/portrait-led photoreal output;
- no explicit user or mode-scoped reference input;
- not E-Commerce and no template policy disabling generated-output chaining;
- no active anchor and no manually unbound/invalid state;
- the frozen plan's `anchor_auto_enabled` is true.

The stale “no frozen plan” predicate is removed. Existing active project anchor,
manual unbind, explicit references, mock runs, and unsupported template modes
retain their current behavior. The explicit-reference condition applies only
to this Doc73 same-batch chain; it must not disable Doc322's separate project
anchor candidacy for a directly uploaded Standard task.

The first source stays the existing Doc287 source: only the canonical persisted
output at plan position 0 with the valid receipt may be used. Do not choose the
first arbitrary candidate or allow position 1 to replace a missing source.

### 3.2 Freeze the actual later-image input

In `app/reference_input_plan.py`, add one narrow derivation method for a
validated Doc287 source. It creates a per-output `ReferenceInputPlan` for the
later image while leaving the Job-level plan unchanged.

The derived plan stores `same_batch_continuity_reference` as its own
job-local advisory field, separate from `continuity_anchor`, direct references,
and `derived_evidence`. Its `references()` view includes the advisory image
only when the plan is auto-enabled, has no active project anchor or explicit
mode inputs, and the mode is `standard`. The plan digest and Standard physical
reference count include that exact source. Existing file/hash and Provider
materialization receipt checks continue to run unchanged against the derived
plan.

In the Brain, derive that plan for each output after position 0 has produced
the existing valid Doc287 receipt. Keep `auto_batch_identity_anchor_applied`,
the receipt/reference metadata, and the plan in sync, but never depend on the
metadata copy as the Provider's input authority.

### 3.3 Review and project binding remain at the current boundary

The existing Product API full-batch review remains unchanged. Continuity stays
advisory under Doc287 and is not promoted to a formal person-identity evidence
source. Existing `_maybe_claim_continuity_anchor()` remains the only project
anchor writer and continues to require the canonical first output and the
current final-delivery eligibility evidence.

If the first image later fails review, the batch's outputs and review findings
remain available under the existing result flow, but no project anchor is
created. That does not retroactively change which same-batch advisory input was
used. Manual unbind continues to disable project auto-promotion according to
Doc322; it also disables the Doc73 same-batch auto chain.

## 4. Compatibility and isolation

- Existing frozen plans lacking `same_batch_continuity_reference` remain
  readable and have no derived reference.
- A derived per-output plan is internal to that output request; it does not
  rewrite the persisted Job request or project's anchor snapshot.
- Provider and MCP consume only the derived frozen plan. Arbitrary dynamic
  metadata references are not merged.
- No V1/V2/Lab, Sub2API, frontend, public API, or deployment changes.
- No extra Vision call, new review gate, retry, or identity threshold.

## 5. Focused regression tests

Write failing tests before implementation. Use deterministic images and stores;
do not invoke external providers.

1. With an auto-enabled frozen Standard plan and eligible Doc73 text-only
   profile, output 0 has no generated reference and every later output's frozen
   plan contains the same canonical source ID and hash.
2. Run the derived plan through `ProductionImageGenerationProvider` reference
   resolution, `_asset_plan()`, and `_bind_reference_materialization_receipt()`;
   the physical materialization contains exactly that source and its receipt
   digest matches the derived plan.
3. An existing project anchor stays the sole source. Manual unbind, explicit
   same-job references, disabled auto flag, non-Standard mode, E-Commerce,
   mock generation, and a missing/invalid Doc287 receipt create no same-batch
   reference.
4. An existing legal Doc287 receipt can be used for continuity context but
   does not by itself create or promote a Doc322 project anchor; final project
   binding still follows the current review eligibility predicate.
5. Explicit Standard uploaded references continue to suppress only the
   same-batch Doc73 chain; they do not suppress Doc322 project-level anchor
   candidacy after formal review.
6. The first planned output remains the sole source across retries and extra
   Provider results; position 1 never replaces it.

Run the focused Doc73/Doc322 suites, production Provider materialization tests,
and the regression cases above. Then perform independent code audit, bounded
local simulation, and the user-requested controlled local V3 real test only
after all deterministic gates pass.

## 6. Acceptance boundary

Passing the focused tests and simulation authorizes local real validation only.
Total acceptance requires the real local multi-image batch to demonstrate
that all later Provider requests consumed the same first canonical image and
that the project anchor is bound only after the existing formal review accepts
it. A review-withheld run must leave the project anchor empty, but that negative
case alone does not complete integrated acceptance. This document does not
authorize VPS deployment.

## 7. Implementation and acceptance record

- The independent implementation audit passed. It checked the validated
  Doc287 receipt path, rejection of conflicting top-level binding metadata,
  direct-reference suppression, and three-output source stability.
- Focused deterministic tests passed: **54 passed** across
  `test_v3_doc322_reference_plan.py`,
  `test_v3_doc73_first_output_identity_anchor.py`, and
  `test_v3_doc322_project_workflow.py`.
- Two isolated local real V3 Standard batches each requested and generated
  three real images. In both batches output position 0 had no generated
  reference; positions 1 and 2 carried the same canonical position-0 output
  ID, SHA-256, and Doc287 receipt through the Production Image Provider.
  Stored source bytes matched the reference hash in both rounds.
- Both batches completed image generation, but existing visual review returned
  `withheld_review_failure` with no eligible outputs. In both cases the project
  anchor correctly remained empty. This verifies the runtime advisory path and
  the no-promotion-on-review-failure behavior. The positive project-binding
  branch is covered by deterministic Doc322 workflow tests; these real runs do
  not claim a review-approved image or a live project-anchor promotion.
- Real runs used isolated temporary project, job, asset, and output stores.
  No production project or user image was changed. VPS deployment was not run.

Phase acceptance: **same-batch advisory continuity and review-gated
non-promotion observed**. Final integrated real acceptance is pending.
VPS deployment remains out of scope.

## 8. Acceptance re-audit and correction model (2026-10-23)

The previous status overstated phase evidence as final acceptance and narrowed
section 6 after two review-withheld runs. Restore the original acceptance
boundary; do not relax review or change runtime behavior to obtain a pass.

The responsible layer is validation/reporting. The retained live receipt has
`review_state: null` because the temporary runner read `final_delivery` from
generation metadata rather than the canonical final-delivery projection. The
durable output closures establish `withheld_review_failure` for both jobs,
three outputs per job, and zero eligible outputs. They do not retain the
complete per-image review reasons, so the cause of review failure is unresolved.

The temporary runner's binding predicate also accepted an empty anchor when
the source was eligible but the anchor object was missing. That did not turn
either recorded round into a pass (both retained `pass: false`), but it cannot
be reused as proof of successful promotion.

Before the next controlled acceptance run, its observer must:

1. Read `_public_final_delivery_projection(result)` and retain the canonical
   `post_generation_review_package`, including per-output status, verification,
   issues, and receipt errors, in local evidence.
2. Retain each output's physical reference materialization receipt as well as
   the request plan; record anchor state before and after final review.
3. Require a non-empty anchor whose output ID exactly equals the eligible
   first planned source for positive promotion. For an ineligible source,
   require no newly created anchor. Assert these branches separately.
4. For a review-approved source, verify the next job's frozen input plan
   carries that persistent anchor. Preserve failed evidence; do not reroll or
   tune prompts merely to obtain an approved review.

Existing scope boundaries remain visible: automatic candidacy requires a
multi-image photoreal human profile; single-image jobs and stylized/illustrated
profiles do not enter this automatic path. If the first planned output fails
review, a later passing sibling does not replace it automatically. These are
existing predicates, not new behavior introduced by this repair, and this
milestone does not establish universal automatic binding for those cases.

Re-audit evidence:

- All six retained output records were inspected. Each batch's first output
  has zero physical references; both later outputs have one original-frame
  reference to that same first output with the matching SHA-256. All six
  `reference_truth_source_ids` arrays remain empty, as required for advisory
  context rather than formal identity truth.
- Additional binding, reference-isolation, and re-audit suites: **49 passed,
  1 deselected**. The excluded brand-export test constructs the default live
  Brain instead of an isolated planning double; the initial broader run was
  stopped at that test and is not reported as a complete pass. That unrelated
  fixture needs isolation before inclusion in an offline suite.
- No production-code change or new real image generation was made during this
  re-audit. The remaining work is review-failure evidence capture and positive
  real promotion/next-job reuse acceptance, not another speculative runtime
  patch.
