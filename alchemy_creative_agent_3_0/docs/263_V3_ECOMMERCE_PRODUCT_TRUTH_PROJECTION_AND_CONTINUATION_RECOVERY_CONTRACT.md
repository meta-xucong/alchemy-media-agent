# Doc263 - V3 E-Commerce Product Truth Projection And Continuation Recovery Contract

## 1. Status And Scope

This document corrects a V3 Professional E-Commerce control-flow defect.
It extends Doc262. Doc262 remains the authority for upload-content
deduplication and stale browser upload cleanup.

This work is specialized E-Commerce template execution and Project Mode UX.
It must not alter General Template deliverable planning, visual-asset library
identity authority, Brain creative authority, ImageGen provider routing, or
the shared review acceptance core.

The total objective is reliable project creation and continuation when a
project has product originals and a locked visual-asset person. A user must
not be blocked because the system confused the complete product evidence set
with the small set of physical images sent to the renderer for one output.

## 2. Observed Mismatch

For the affected Professional E-Commerce project, four canonical product
originals and three locked Face identity references were correct. The frozen
product-truth pool also contained those same four product asset IDs. No
ImageGen request was sent.

The provider path currently runs generic adaptive reference selection before
Professional E-Commerce product-truth validation. Product originals that are
not marked `provider_input_required` can therefore be reduced first. The
later validation incorrectly compares the reduced physical list with the
complete frozen product-truth pool and closes with
`ecommerce_product_truth_pool_mismatch`.

This is an internal projection-order defect. It is not proof that the user
uploaded the wrong product images, that the provider is unavailable, or that
the provider rejected a request.

## 3. Correction Model

Two separate, server-owned concepts are required.

```text
ProductTruthAdmission
  The complete canonical product evidence for the project and job.
  It is authoritative for product truth, planning, source continuity, and
  review evidence.

PhysicalProductReferenceProjection
  The one or two product originals selected for one planned output.
  It is authoritative only for the physical ImageGen reference inputs for
  that output.
```

The full truth pool must be validated before any physical-reference projection
or adaptive selection. A physical projection is not a reduced truth pool.

The required ordering is:

```text
canonical project references
  -> ProductTruthAdmission validation and freeze
  -> Brain-owned per-output product selection
  -> PhysicalProductReferenceProjection freeze
  -> attach locked Face identity references
  -> generic adaptive selection of only noncritical references
  -> unchanged provider capacity gate
  -> ImageGen request
```

The renderer receives selected product original(s) plus any separately
required Face identity inputs. It never receives every product original merely
to prove that the full product truth pool exists. The review path still knows
the complete product truth admission through its exact evidence contract.

## 4. Authority And Data Contracts

### 4.1 ProductTruthAdmission

The Product API is the owner. It resolves current active project product
references from the upload store, after Doc262 content-hash canonicalization.
It freezes an immutable admission with:

- project ID and fresh job or continuation-attempt ID;
- ordered canonical product asset IDs;
- content SHA-256 for each canonical asset;
- role `product_reference`, readiness, file-integrity, provenance, consent,
  and rights receipts already required by the upload contract;
- a non-secret `source_binding_digest`;
- the product-truth plan digest and admission schema version.

It must reject duplicate IDs, missing files, inactive or noncanonical entries,
role/truth drift, digest drift, and public metadata forgery before planning.
The public request cannot supply, replace, or mark this admission valid.

### 4.2 PhysicalProductReferenceProjection

The Brain-selected deliverable metadata is the semantic selector, but the
Product API and provider boundary validate and freeze the physical projection.
For each output it contains:

- job ID, output index, and ProductTruthAdmission binding digest;
- selected ordered product asset IDs, a nonempty subset of the admitted pool;
- one selected source normally, or two only for an explicit
  `product_detail_or_print_view` selection;
- selection source
  `remote_brain_image_set_plan.evidence_dimensions_by_output`;
- selection role, cap reservation, schema version, and projection digest.

Selected product references are marked internally as physical-required before
generic adaptive selection. This mark is server-owned and cannot be asserted
by browser metadata. Generic selection may rank or omit only noncritical
references; it must retain every selected product reference and every
separately required Face reference. The ordinary route cap remains
authoritative. Capacity is checked after the frozen physical projection is
assembled, with no silent trim.

### 4.3 Error Taxonomy

The old broad error must be split:

- `product_truth_admission_invalid`: the complete canonical product evidence
  is genuinely missing, corrupted, inactive, or no longer matches the frozen
  project truth. This is a user-resolvable input state.
- `reference_projection_drift`: the admitted full pool is valid but an
  internal projection or legacy job path lost selected evidence. This is an
  internal recovery state, never an instruction to upload the same images
  again.
- `reference_input_capacity_unavailable`: the frozen required Face inputs and
  selected product input(s) cannot fit the configured provider limit. Do not
  silently remove either class of hard input.
- `ecommerce_product_truth_selection_invalid`: the Brain plan did not provide
  a valid selected subset. This remains a planning contract failure.

No local contract failure sends an ImageGen request. Provider availability,
provider policy, and post-generation review failures remain distinct from all
four states above.

## 5. Continuation And Legacy Recovery

Continuation is a new command against the current canonical project state,
not a replay of arbitrary old job metadata.

1. A terminal historical failure remains append-only history.
2. A continuation command resolves the active canonical project product pool,
   current locked visual-asset Face chain, and selected generated directions
   independently of stale failed-job `uploaded_assets`.
3. For a legacy failure classified as `reference_projection_drift`, the
   server creates one fresh clean continuation attempt that records
   `supersedes_job_id`. It does not mutate the historical failed job.
4. The fresh attempt starts with no inherited terminal error text, no stale
   client `File` objects, and no duplicate product asset IDs.
5. A truly invalid current ProductTruthAdmission stops before planning and
   exposes a single action to adjust current product originals.

Every generate or continue click carries one server-issued idempotency key
scoped to the project, current reference binding digest, requested operation,
and client action. Repeated desktop clicks, mobile taps, reloads, polling, or
network replays return the same active or terminal command result. They do not
create duplicate uploads, jobs, or provider submissions.

## 6. User-Facing Project Model

The project UI must present four visibly separate groups:

1. **Original product inputs**: active canonical uploaded product originals.
   Duplicate content is shown once. This group is the current product truth.
2. **Locked person identity**: the selected visual-asset Face chain used for
   the person, separate from product truth.
3. **Selected continuation directions**: only generated results the user has
   explicitly selected to guide a later continuation. Generated images never
   become product originals automatically.
4. **Generated and review history**: delivered images, review-withheld images,
   rejected candidates, and failed attempts. This is historical inspection,
   not a default source group.

The creation screen must allow a user to select or lock a visual asset before
the first generate action. The continuation screen uses the same groups and
does not hide the ordinary generation controls once an asset is selected.

## 7. Frontend State Machine

The server terminal state is authoritative. The browser may poll but must
never infer that polling means generation is still running.

```text
ready
  -> validating_inputs
  -> planning
  -> queued_or_generating
  -> reviewing
  -> delivered | manual_confirmation | needs_input | retry_available
  -> failed_no_delivery
```

- `queued_or_generating` is shown only while the server declares a nonterminal
  operation.
- A terminal local contract state closes the pending surface immediately and
  presents one actionable message.
- `reference_projection_drift` triggers server-side fresh-continuation
  recovery where the current admission is valid; it is not shown as a stale
  re-upload instruction.
- A reload rehydrates the latest server operation by idempotency key and
  replaces old messages. A new attempt never displays an earlier attempt's
  error as its own.
- Polling has a finite visible retry/refresh cadence. If the server has no
  active operation and no terminal delivery, the screen leaves
  `queued_or_generating` and offers a safe next action; it cannot remain
  indefinitely at "preparing".
- Failure and review-withheld records remain accessible in history, while
  homepage or delivery carousels show only formal delivery outputs.

Public copy must contain no paths, hashes, provider payloads, prompts,
internal IDs, or raw stack traces.

## 8. Non-Goals And Security Boundaries

- Do not make all product originals physical renderer inputs to avoid the
  defect.
- Do not increase the provider image cap as a workaround.
- Do not silently trim required Face or selected product inputs.
- Do not promote generated output to product truth, product reference, or
  locked identity without an explicit user action and its existing contract.
- Do not delete duplicate upload records, historical jobs, output files, or
  review evidence as part of recovery.
- Do not expose product file paths, full hashes, provider details, or private
  admission records in browser projections.
- Do not alter Body modeling, Face-card formal acceptance, General Template,
  or unrelated provider routes.

## 9. Required Regression Matrix

The implementation starts with deterministic red tests, then adds focused
runtime and browser tests.

1. Four canonical product originals plus three locked Face references produce
   a valid ProductTruthAdmission and one or two frozen physical product inputs
   within the five-image cap.
2. With adaptive selection active, selected product input(s) survive and only
   noncritical references are eligible for generic trimming.
3. The full product pool is validated before physical projection; a selected
   subset does not raise a full-pool mismatch.
4. Invalid full-pool evidence stops before the provider call and reports the
   correct user-input error.
5. A legacy or injected projection drift produces
   `reference_projection_drift`, sends no provider request, and can create
   exactly one fresh clean continuation from current canonical project state.
6. Duplicate upload bytes result in one active canonical product original.
   Reopen, refresh, and continue do not create a second upload or expand a
   product pool.
7. A fresh continuation does not inherit stale failed-job input IDs, pending
   browser files, or old failure text.
8. Repeated click, refresh, mobile reload, and polling all preserve one
   command identity and resolve terminal states out of the preparing surface.
9. Desktop and mobile browser tests show the four source/history groups,
   selected visual assets before first generation, one actionable error, and
   a reachable continue control at narrow viewport widths.
10. Existing product review evidence, visual-asset identity binding, ordinary
    V3 generation, and non-E-Commerce routes remain isolated.

## 10. Delivery Plan And Rollback

1. Land the implementation on an isolated feature branch based on the latest
   `origin/main`; rebase before integration.
2. Run focused provider, Product API, Project Mode, frontend, and browser
   suites, followed by adjacent shared reference/review regressions.
3. Integrate only through the unique main checkout after a final diff and
   contract audit. Push the exact main commit to GitHub.
4. Deploy with the existing VPS release procedure. Verify health endpoints,
   desktop and mobile assets, one no-provider local contract smoke, and
   browser navigation for a new and a recovered project. Do not use real
   ImageGen as an exploratory test.
5. If health or browser acceptance fails, roll back the deployed release to
   the prior verified Git commit using the established VPS deployment
   procedure. Preserve all project/job history and append deployment evidence.

Completion requires the complete matrix above, the GitHub push, a successful
VPS deployment, and post-deploy desktop/mobile acceptance. A code-only or
single-unit-test pass is not final completion.
