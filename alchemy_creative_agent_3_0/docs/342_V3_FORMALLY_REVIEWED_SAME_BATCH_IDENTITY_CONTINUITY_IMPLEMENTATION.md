# Doc342 - V3 Formally Reviewed Same-Batch Identity Continuity Implementation

Status: **development contract; design audit passed; implementation and acceptance pending**.

Scope: V3 Foundation generation, shared visual review, and frozen provider input.

## 1. Objective

Make later images in an eligible human-identity batch use the first planned
image as an identity continuity reference, while preserving the product rule
that only a formally eligible first output can become that reference or the
project continuity anchor.

The current mismatch is that `CentralCreativeBrain` disables same-batch
continuity whenever a frozen `ReferenceInputPlan` exists. Removing that gate
alone is insufficient: a production Provider consumes the frozen plan and
does not read the dynamic `reference_assets` metadata. The first output also
cannot be used before the existing formal visual review says it is eligible.

## 2. Authority and correction model

Apply these existing authorities together:

- Doc73 decides when a text-only human suite may use the first output as a
  same-batch identity continuity reference.
- Doc287 owns the canonical source/target binding and treats continuity as
  advisory transport context, never as formal person-identity evidence.
- Doc322 owns project-level binding. The project anchor is claimed only after
  the existing final delivery gate accepts the first planned output. Manual
  binding wins; manual unbind disables automatic promotion.
- The frozen `ReferenceInputPlan` remains the Provider input authority.

The first image may become a same-batch reference only after the existing
formal review and final-delivery projection mark its canonical output eligible.
It is not written as the project anchor at that point. If the first output is
not eligible, keep its output and review evidence, stop before generating later
images, and leave project binding unchanged. A later output never replaces the
first planned output.

## 3. Minimal implementation

### 3.1 Brain decision and per-output plan

In `creative_core/central_brain.py`:

1. Preserve the current Doc73 eligibility decision for the same-batch chain:
   real, multi-output, human/photoreal, non-E-Commerce, text-only Standard
   generation with no explicit references, no active continuity anchor, and
   `anchor_auto_enabled=true` in the frozen plan. Preserve mock,
   manual-unbind, and template policy gates.
2. This text-only/no-explicit-input condition scopes only the optional
   same-batch chain. It must not suppress Doc322's separate project-level
   automatic anchor candidacy after a formally eligible first output; in
   particular, Standard direct references do not by themselves disable that
   project-level candidacy.
3. Keep the original Job-level frozen plan unchanged.
4. After the first planned output is persisted and the internal review callback
   returns eligible, derive a per-output plan containing the validated Doc287
   source. Do not mutate the project anchor or infer from file paths.
5. Attach that derived plan to later `GenerationRequest`s. Do not rely on
   `reference_assets` metadata alone.

In `reference_input_plan.py`, add one narrow derivation method for a
Doc287-validated, same-Job advisory reference. It must:

- require an auto-enabled plan with no active anchor and the eligible
  text-only Standard mode;
- preserve `project_id`, `job_id`, `project_mode`, original sources, and
  authority fields;
- keep the temporary reference distinct from `continuity_anchor` and from
  user/project truth;
- recompute the plan digest and physical reference count for the derived plan;
- let existing `references()`, Provider materialization, and receipt binding
  consume the exact derived plan.

Do not add another source selector or allow the Provider to merge arbitrary
metadata references.

### 3.2 First-output review boundary

Use one internal callback, passed as a callable through
`Product API -> ScenarioRuntime.generate_job -> creative_core.pipeline ->
CentralCreativeBrain.run_generation_loop`. The callable is not request data,
serialized metadata, or a public API field.

After planned position 0 is persisted, Central Brain supplies a partial result
containing that canonical output to the callback. Scenario Runtime applies its
existing result-enrichment steps before the callback reaches Product API.
Product API runs the existing `_attach_post_generation_review()` and uses the
existing `_public_final_delivery_projection()` `eligible_output_ids` as the
eligibility authority. Do not create a second meaning for `pass`, or replace
the existing accepted-warning behavior.

The callback returns the reviewed result/evidence and eligibility to the
Brain. Only an eligible canonical position-0 output may be converted to the
existing Doc287 same-batch reference. The Brain then continues the same Job
with the original frozen series plan and remaining positions. A Doc287 receipt
alone is not proof of review eligibility: on retry or process recovery, reuse
the source only when the exact canonical source still has its complete formal
review evidence and remains in `eligible_output_ids`; otherwise stop before
later generation and require the existing review path to complete first.

If review fails, is unavailable, or cannot bind exact evidence to the canonical
output, stop before position 1. Preserve the partial generation and formal
review package in the existing blocked/review lifecycle. Keep the requested
count unchanged; do not return a one-image success or substitute a later
output.

### 3.3 Batch-final review reuse

At the normal batch-final review, do not inspect position 0 twice. Reuse its
existing `VisualInspectionReport`, `ReviewEvidencePlan`, and digest only when
the canonical output ID, output bytes, and frozen review contract still match.
Run the existing inspector for the remaining outputs and call the existing
`review_merger` on the complete set. Do not use the one-image review package as
the batch package and do not introduce a new review cache or validator.

Doc322's existing post-delivery `_maybe_claim_continuity_anchor()` remains the
only project anchor writer.

## 4. Compatibility and isolation

- Existing plans without the new derived same-batch field remain readable.
- Existing active manual/project anchors continue to win and are used as-is.
- Explicit uploaded or mode-bound inputs retain their current reference path
  and suppress only this optional same-batch chain; they do not suppress
  Doc322 project-level automatic anchor candidacy.
- Manual unbind, retry, extra Provider outputs, refinement outputs, and failed
  position 0 cannot create or replace the source.
- Continuity remains excluded from formal truth/evidence channels.
- No changes to V1, V2, Lab, Sub2API, public APIs, frontend, or deployment
  configuration.

## 5. Required regression evidence

Use deterministic providers, temporary stores, and a controlled fake reviewer;
no external model/provider calls in simulation.

1. A four-image eligible batch generates position 0, formally reviews it, then
   generates positions 1-3 with the same canonical source in each derived plan.
2. The real production Provider's reference resolution and materialization
   receipt show that the same source bytes were sent for each later image.
3. Final review contains all four canonical outputs, reuses the first review
   exactly once, and inspects each later image once.
4. First-output fail, manual review, unavailable reviewer, or evidence mismatch
   stops before another Provider call, preserves the first output/review, keeps
   the job incomplete, and does not bind a project anchor.
5. Existing active anchor, explicit input, manually unbound state, retry,
   refinement, extra output, mock generation, and non-human/non-eligible cases
   retain existing behavior. A bare Doc287 receipt without the matching formal
   review evidence must not resume later-image generation.
6. A final successful batch still binds only the first formally eligible
   planned output through the existing Doc322 service.

## 6. Acceptance sequence

1. Independently audit this document against Docs 73, 287, 322 and current call
   paths. Resolve findings before implementation.
2. Add the focused failing regression tests before implementation.
3. Implement only the bounded changes above; run focused tests and the existing
   Doc73/Doc322 reference and continuity suites.
4. Have an independent code auditor review the frozen diff. Fix findings and
   rerun the affected tests.
5. Run deterministic local simulations, including production Provider
   materialization, without external requests.
6. After all local gates pass, run a controlled local V3 real-generation test
   for the intended multi-image human suite. Preserve job/output/review
   evidence and report success, timing, and any limitations. Do not push to VPS.

Passing one phase authorizes the next phase only; total acceptance requires all
phases above and a final integrated local result.
