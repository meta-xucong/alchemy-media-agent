# V3 Review Provider Attempt and Certification Semantics Repair

**Status:** implemented; targeted and V3 regression verification completed
**Scope:** Product API public review projection and post-generation Vision review evidence
**Related evidence:** Doc260 review handoff; deployed baseline commit `3c17cfd63c27dcc0e9237f1d12b67402f51fd910`

## 1. Problem statement

The post-generation Vision inspector records provider-call evidence in the durable inspection row. A successful provider response records `provider_review_attempts`; a terminal `VisionInspectionProviderError` or timeout also records a positive attempt count and returns `manual_review` with `verification_failed`.

The Product API currently derives `real_pixel_review_attempted` from `bool(certified_output_ids)`. That projection is incorrect when the provider was called but did not certify an output: the public state says that no review was attempted even though the durable evidence says otherwise.

This is a diagnostic truth error. It does not authorize delivery because certification and final delivery already fail closed.

## 2. Contract

The two public facts have separate meanings:

- **attempted:** at least one eligible Vision provider call has a positive, well-typed attempt count in the retained inspection evidence.
- **certified:** every ready output is covered by a complete, error-free receipt and a verified inspection whose evidence explicitly sets `provider_pixel_result_certified=True`.

A positive attempt never implies certification. A certification row without a positive attempt count is malformed and cannot be treated as a provider attempt.

The attempt projection must accept only a positive integer on an eligible Vision inspection
mode (`vision_model` or `hybrid`). Boolean values, strings, floats, missing evidence, and
non-positive counts are not valid attempt evidence.

## 3. Required state table

| Situation | Provider call evidence | attempted | certified | Delivery |
| --- | --- | ---: | ---: | --- |
| Provider not called; source unavailable or digest drift | absent | false | false | withheld |
| Provider called; response is timeout or `VisionInspectionProviderError` | attempts > 0; `verification_failed` | true | false | manual review / withheld |
| Provider called; response succeeds but receipt or output coverage is incomplete | attempts > 0 | true | false | withheld |
| Provider called; valid response, complete receipt, all ready outputs verified | attempts > 0 and certified evidence | true | true | eligible under existing gate |

The provider-error row must never be converted into a pass by changing thresholds, skipping Vision review, or auto-delivering the retained image.

## 4. Implementation boundary

1. Keep `VisionOutputInspector` responsible for recording the actual provider attempt count and failure classification.
2. Change `V3ProductApiService._public_post_generation_review` to derive `real_pixel_review_attempted` from positive integer `provider_review_attempts` across raw inspections.
3. Keep `real_pixel_review_certified` tied to the existing complete-receipt, ready-output coverage, verified-state, and explicit provider certification checks.
4. Keep `_doc280_public_review_summary` as a projection of the corrected public review object; it must not recalculate certification.
5. Preserve source digest drift behavior: do not call the Vision provider when the frozen input summary is invalid or changed.

## 5. Regression matrix

The local suite must cover all of the following:

- no provider call: `attempted=false`, `certified=false`, no delivery;
- provider called and raises `VisionInspectionProviderError`: `attempted=true`, `certified=false`, `manual_review`, `verification_failed`, and no delivery;
- provider called and times out: same attempt/certification separation;
- provider succeeds and passes: `attempted=true`, `certified=true` only with complete evidence;
- incomplete output coverage: attempted may be true, certification remains false;
- frozen source digest drift: provider call count is zero and attempted remains false;
- valid ecommerce product reference: Product Truth selection, provider input scope, and review evidence remain aligned.

## 6. Audit and release gates

Before any deployment or paid generation:

- run the targeted Doc260 and Vision review tests;
- run the complete V3 acceptance subset and require zero failures;
- run `compileall` and `git diff --check`;
- inspect the diff for fail-open changes, new provider bypasses, unbounded retries, prompt or token leakage, and accidental changes to source-digest enforcement;
- keep the existing real job/output as evidence; do not regenerate it.

The existing VPS `provider_error` root cause (authentication, quota, timeout, network, or response parsing) is a separate operational diagnosis. It must be established from redacted logs before a single controlled real verification is considered.

## 7. Acceptance evidence format

For every verification case, report status as **pass**, **fail**, or **blocked**, with:

- deployed or local commit and runtime version;
- project, job, and output identifiers;
- provider/model and attempt count;
- public `attempted` and `certified` values;
- review status, verification state, and final delivery status;
- redacted provider error category where applicable.

Never include API keys, session tokens, or full user prompts.
