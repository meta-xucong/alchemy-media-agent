# E31 - Doc270 Phase 4 View-Aware Product Source Activation Contract

Status: Phase 4 runtime contract and deterministic activation authority

## 1. Scope

Phase 4 activates Doc270 source matching only for a new, explicitly issued
Professional E-Commerce command behind a disabled-by-default server gate. It
does not alter General Phase 3 activation, Photography, Brand, Provider
routing, Doc93 People authority, Doc265 continuation authority, or existing
and historical jobs.

The goal is per-output view-aware selection from the full admitted product
original pool. It is not a new product-truth admission system and it is not a
fallback that forwards every uploaded original.

## 2. Authority Order

```text
Doc263 ProductTruthAdmission and Doc264 re-attestation
  -> fresh trusted Doc270 project-source snapshot
  -> server-issued Doc270 Phase 2 requirement/receipt registry lookup
  -> E31 exact view-resolution verification
  -> Doc263 PhysicalProductReferenceProjection freeze
  -> Doc269 PhysicalRendererReferencePlan freeze
  -> existing planning/materialization path
```

1. `ProductTruthAdmission` remains the complete exact current canonical pool.
   Matching never deletes, narrows, reorders, or reclassifies that pool.
2. An E31 receipt may select at most one admitted product original for each
   planned output. Its source must be a current active, readable,
   SHA-matching product-truth association in the complete admission.
3. Doc263 owns the selected per-output product projection. Doc269 owns the
   final physical renderer plan. E31 only supplies the server-verified view
   selection that those existing freezes consume.
4. Unselected originals remain complete pool, Brain, and review evidence only.
   They never become physical references merely because a receipt is absent,
   stale, invalid, or insufficient.
5. Locked People/Visual Asset evidence is separately composed by Doc93 and
   Doc269. Generated and review history remain excluded. A continuation can
   enter only through an existing explicit Doc265 selected-continuation
   admission; it cannot seed product matching or repair product truth.

## 3. Server-Owned Phase 4 Gate

Only a private server capability, typed command identity, and immutable
registry entry can activate E31. They bind exact protocol/version, project,
template, command/plan identity, output identity, requirement nonce/digest,
current source-library snapshot, selected association/asset/SHA, evidence
profile digest, and the Doc263/Doc269 output bindings.

Browser metadata, filename, upload order, role labels, Brain prose, requested
asset IDs, selected IDs, receipt objects, profile objects, registry values, or
digests are ignored and cannot enable the gate. A prior job, retry, refresh,
history navigation, reload, or Doc268 idempotent replay reads its frozen
receipt; it never asks the registry to rematch.

The same server command identity coalesces to one job and one frozen set of
per-output selections. A distinct server-issued identity is a distinct new
command. A stale SHA, missing/unreadable source, wrong project, generated or
history source, duplicate output entry, cross-output selection, mismatched
plan digest, or malformed authority fails closed before Product API planning
or Provider dispatch.

## 4. Hard View Requirement Closure

Phase 4 enables only hard E-Commerce view requirements supplied by the
trusted server registry. A no-match, insufficient, ambiguous, invalid, or
unverifiable hard receipt returns the single terminal public operation:

```json
{
  "state": "needs_input",
  "terminal": true,
  "next_actions": [{"id": "review_product_inputs"}]
}
```

It creates no job, selected projection, Doc269 plan, Brain request, Provider
request, automatic retry, or automatic replan. A no-job closure may return a
synthetic terminal response for the explicit command, but it has no Job
identity and is not appended to `project.job_ids`. Any project readback
operation is server-owned, stable, sanitized, and does not imply a persisted
Job or a completed plan/dispatch; it must not preserve a stale operation from
an older Job. The public operation contains no source IDs, SHA values, file
paths, evidence, registry fields, or raw failure detail. Desktop and H5 retire
busy/progress/recovery state and show only this action; clicking it navigates
locally to product inputs and sends no job POST.

This conservative closure is distinct from E-Commerce text-to-image
compatibility. A new command with no active product originals remains on its
existing prompt-only/text-to-image path when the Phase 4 gate has no hard
product requirement. It is not a hard-match failure.

## 5. Freeze and Public Boundary

For a valid activation, private job metadata records one E31 receipt per
output and the exact selected projection binding. The existing Doc263
projection and Doc269 plan must select the same single product source in the
same output order. The complete admission stays immutable and available to
review. Public project/job views expose at most a safe lifecycle marker and
the existing four E-Commerce groups; they never expose source association or
asset IDs, SHA/digests, paths, registry records, requirement text, or evidence
profiles.

## 6. Required Regression Matrix

1. A front/rear/detail product pool freezes front for a front output, rear
   for a rear output, and detail for a detail output, while the complete
   admission remains intact. The receipt set covers exactly every planned
   output index: missing, extra, duplicate, or cross-output entries close
   before Job creation, planning, or dispatch.
   The receipt binds typed evidence such as `subject_kind=object_or_product`,
   `view_kind=rear`, and an allowlisted affordance; filename, upload order,
   and Brain text cannot substitute for that evidence.
2. A non-apparel object fixture (for example, a ceramic mug with front/rear/
   detail evidence) proves the contract uses typed evidence, not apparel,
   filename, upload order, or Brain-text branches.
3. Missing, unreadable, stale-SHA, cross-project, generated/history, or
   browser-forged candidates create no product projection or physical plan.
4. Locked People evidence remains in its Doc269 identity channel and an
   explicit Doc265 continuation remains separate from the selected product.
5. Same-identity clicks/reload return one receipt without rematching; old
   retry/refresh/history never rematches or changes a frozen plan.
6. Multiple outputs bind one selected admitted product per output and reject
   duplicate, omitted, or cross-output registry entries.
7. Hard no-match is one safe `needs_input` terminal action with no preparing
   copy or POST on action click. Desktop and H5 must expose exactly one local
   `review_product_inputs` action, and clicking it opens the product-input
   review surface without a job POST. General and Photography remain
   unchanged.

## 7. Delivery Boundary

The server gate is enabled only when both of the following are present:

1. A server-owned, versioned JSON policy is valid. With no
   `ALCHEMY_DOC270_ECOMMERCE_VIEW_POLICY_PATH` override, the release uses its
   current packaged policy under `app/project_mode/policies`. An explicit
   unreadable, malformed, or schema-invalid override fails closed and disables
   E31; it never silently falls back. Browser input and uploaded files can
   never provide the policy.
2. A source analyzer is available. A dedicated E31 credential/base/model may
   be configured, otherwise E31 may read only the already-enabled V3
   `LAB_*` vision route. It never falls back to a general Brain, a text-only
   LLM, or an image-generation route.

The dedicated E31 route first uses structured Responses. A gateway protocol
rejection may use one Chat JSON compatibility request. The already-certified
V3 `LAB_*` visual route uses its certified Chat image-JSON protocol directly;
it is never preceded by a duplicate Responses request. A timeout is never
submitted through a second protocol because it may already have reached the
model. Any absent, invalid, or unavailable analysis produces the terminal
source-analysis state; it does not create a generation job or automatically
retry.

E31 reserves one server-owned output budget of 640 tokens for both compatible
source-analysis transports. This E31-only upstream runtime budget leaves room
for a vision model's hidden reasoning and the required structured content; it
does not alter timeout or retry semantics, relax parsing, or change any
Provider-generation budget. The server still accepts only the closed four-field
JSON contract and rejects malformed or incomplete output as unavailable.
