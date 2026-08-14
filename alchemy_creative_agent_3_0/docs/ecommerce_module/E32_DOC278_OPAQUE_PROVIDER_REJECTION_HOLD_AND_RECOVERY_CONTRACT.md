# E32 / Doc278 Opaque Provider Rejection Hold And Recovery Contract

## 1. Purpose

Doc278 closes a narrow Professional E-Commerce continuation defect. A durable,
non-retryable, zero-pixel `image_edit_invalid_request_unattributed` failure can
be an opaque upstream rejection even where the complete Doc263 product-truth
pool, Doc264 re-attestation, Doc265 continuation boundary, and Doc269 physical
reference plan are valid. Repeating the exact same server-owned command should
not create another futile Job merely because the upstream failure is not an
attributable content-policy decision.

This is an E-Commerce-only command hold. It is not a policy classifier, prompt
rewriter, Provider workaround, source matcher, or retry strategy.

## 2. Authority And Precedence

1. Doc263/264 admit the full current canonical product-original pool first.
   Doc278 never reduces it, requests a re-upload for an already admitted
   original, or treats a selected product projection as the full truth pool.
2. Doc269 remains the only final physical renderer-reference authority. A
   Doc278 receipt binds the frozen selected-product, locked-People, optional
   Doc265 continuation, and per-output physical plan facts; it never rebuilds
   or substitutes them.
3. Doc93 and Doc265 retain People identity and explicit continuation authority.
   Visual Assets, generated/review history, and implicit continuation are not
   opaque-hold product candidates.
4. Doc271 has precedence. A complete exact explicit
   `provider_policy_blocked` / `content_policy_violation` closure returns its
   existing `delivery_route_unavailable` operation. Doc278 must not downgrade,
   relabel, or duplicate it.
5. General and Photography do not consume Doc278 receipts or operations.

## 3. Server-Owned Receipt

Phase 1 may persist one append-only private
`ambiguous_provider_request_hold_receipt` only from a terminal Professional
E-Commerce Job with all of the following durable facts:

- no delivered output records, output IDs, or readable pixel files;
- `final_status=failed`,
  `final_classification=non_retryable_provider_failure`, and
  `final_failure_code=image_edit_invalid_request_unattributed`;
- a server-owned image-edit execution audit with exact capability, provider,
  model, operation, and route identity;
- a verifiable terminal Job receipt digest plus current project/job linkage;
- canonical project goal and explicit command-direction binding;
- current project source-library binding, complete Doc263 admission binding,
  selected-product projection, locked visual-asset binding, selected Doc265
  continuation admission if present, and all Doc269 per-output physical-plan
  bindings.

The opaque failure text, HTTP status, browser metadata, filenames, keywords,
ages, garments, and provider-created classifications are not receipt authority.
A generic 400, retryable failure, partial delivery, missing field, malformed
legacy record, cross-project record, or forged self-consistent metadata fails
open and creates no hold.

## 4. Exact Repeat And Recovery

Before idempotency, Brain planning, Product API Job creation, physical
materialization, or Provider dispatch, Project Mode compares the new explicit
E-Commerce command with the newest readable same-project verified receipt. It
must compare the exact current goal/direction, requested output count, canonical
source and selected-product bindings, locked People binding, selected
continuation binding, per-output physical plans, and configured execution
identity.

An exact match returns no `job_id` and one public terminal operation only:

```json
{
  "state": "ambiguous_provider_request_hold",
  "terminal": true,
  "pending": false,
  "next_actions": [{"id": "review_generation_conditions"}]
}
```

The public response contains no historical Job ID, asset/source ID, path,
digest, provider error, or opaque upstream code. It does not mutate
`project.job_ids`, append a Job, plan, materialize, dispatch, replay history,
or automatically retry/reroute.

A new command is eligible only after an explicit server-observable change to
the goal/direction, active source/reference or selected-product binding, locked
visual-asset binding, selected continuation admission, or separately configured
route identity. It never changes a person, product fact, age, garment, or
reference channel to obtain a result.

## 5. Historical And UI Projection

A fully verifiable pre-Doc278 terminal opaque record may be recognized
read-only for the current project view and exact pre-dispatch check. Recognition
does not write a receipt into historical metadata, replay the Job, or hide its
history. Incomplete history remains ordinary terminal history.

Desktop and H5 consume only the server operation. On the hold they clear
busy/loading, progress, polling, recovery timers, and any active Doc268
submission receipt; they render one local review/adjust action and never show
preparing, generating, recovering, or raw failure diagnostics. The action does
not POST `/jobs` automatically.

## 6. Phase 0 Test Boundary

Phase 0 is documentation plus deterministic red tests only. Tests use local
Project Mode/Product API stores, deterministic no-pixel Provider doubles, and
local browser fixtures. They do not contact Provider, MCP, ImageGen, VPS, or
live projects/jobs/outputs.
