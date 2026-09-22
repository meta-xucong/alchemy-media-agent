# E35 / Doc281 E-Commerce Brain Product-Truth Selection Recovery Contract

## 1. Observed mismatch

The VPS job `job_5127f5db08` stopped during planning with
`ecommerce_product_truth_selection_invalid` and did not start an image
provider request. The persisted record has no raw Brain response, so the
exact offending field is not recoverable. The runtime gate nevertheless
narrows the failure to the product-truth selection semantics: output index,
selection role, selected asset cardinality, duplicate/unknown IDs, or the
per-output provider reference budget. Upload integrity and provider transport
were not the failing layer.

## 2. Correction model

The Brain adapter previously checked only that the response contained one
entry per output, a non-empty role, and a non-empty list. ScenarioRuntime then
performed the stricter product-truth validation. That split allowed a response
to be accepted as a remote Brain result, skip the bounded Brain recovery, and
fail later at capability activation.

The authoritative contract remains server-owned product truth and the frozen
provider budget. The adapter must validate the same semantic rules before it
accepts `image_set_plan` and must never invent, trim, reorder, or replace
product references locally. A semantic mismatch is a remote contract
failure, so the existing one-time same-request Brain re-answer is the only
repair path. If that re-answer is still invalid, the run remains fail-closed
before image generation.

## 3. Minimal implementation

1. Move the allowed product-truth roles and detail-role identity into the
   E-Commerce contract module so the adapter and runtime share one authority.
2. Extend the adapter gate to enforce role enum, exact pool membership when
   the server supplied a pool, duplicate IDs, one/two-source rules, and the
   provider reference budget.
3. Emit only safe field paths and reason types as validation diagnostics; do
   not persist or send source IDs, paths, prompts, or raw Brain text.
4. Include those safe diagnostics in the bounded recovery envelope so the
   upstream Brain can correct the field instead of receiving only the generic
   section name.
5. Keep Runtime's final gate in place as defense in depth. No local creative
   fallback, default asset choice, silent trimming, or extra provider retry is
   introduced.

## 4. Acceptance matrix

| Case | Expected result |
| --- | --- |
| valid role, pool ID, and budget | adapter accepts the plan without recovery |
| invalid role / wrong index / empty selection | adapter rejects the section and performs one bounded Brain re-answer |
| unknown or duplicate asset ID | adapter rejects with safe diagnostics; no local repair |
| two IDs for a non-detail role or over budget | adapter rejects with safe diagnostics |
| second answer valid | valid plan continues to Runtime/provider |
| second answer invalid | fail closed; zero image-provider calls |

## 5. Scope and non-goals

This is an E-Commerce Brain contract/recovery fix. It does not change image
quality review, prompt meaning, reference ownership, provider selection, or
frontend copy. The real VPS retry is a post-deployment acceptance phase and
must use a newly submitted job with the same user request and assets.
