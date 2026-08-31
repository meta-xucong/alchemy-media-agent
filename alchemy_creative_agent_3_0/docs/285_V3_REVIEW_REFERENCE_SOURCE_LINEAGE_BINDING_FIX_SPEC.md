# V3 Review Reference Source Lineage Binding Fix

Status: implementation authority for the shared V3 post-generation review
evidence resolver. This document authorizes local code and deterministic test
work only. It does not authorize a Provider, MCP, ImageGen, VPS, or GitHub
operation.

## 1. Observed Failure

The Provider can persist valid pixels for a normal General continuation that
uses a previously selected generated image as a person-identity reference.
The subsequent shared review may nevertheless close as manual review with
`review_evidence_person_identity_invalid` and no automatic delivery.

The persisted Project Mode reference already contains the authoritative
historical `job_id` and `output_id`. The failure occurs because the shared
`ExactReviewEvidenceResolver` only treats the professional anchor list as a
frozen generated-output allowlist. General Project Mode references arrive in
the existing `project_context_snapshot` under selected-output/reference
projections, so the resolver falls through to its source-job-binding failure
case even though the output is a valid project-owned reference.

This is an evidence-lineage projection defect, not a Provider, bridge,
quality-threshold, retry, prompt, or frontend defect.

## 2. Authority And Boundaries

1. Project Mode remains the source of truth for a selected generated output.
   Its server-built context already freezes the output identity, source job,
   project scope, canonical binding, and output file integrity metadata.
2. Output Store remains the source of truth for the persisted output record,
   including its final output ID, owning job ID, and bytes.
3. The shared review resolver may authorize a generated reference only from a
   server-built, canonical Project Mode context projection or the existing
   professional anchor projection. It must never authorize an ID from a
   browser selector, URL, filename, prompt, output order, current history, or
   Provider response alone.
4. The review gate remains strict. Missing, stale, non-canonical, cross-job,
   cross-project, unreadable, or digest-mismatched references remain
   non-certifying and fail closed.
5. This is shared foundation behavior. It must work for General and
   Professional callers without adding scenario-specific branches or
   changing E-Commerce product-truth authority.

## 3. Minimal Correction

Use the existing server-owned project context as an additional frozen
generated-reference binding source:

```text
selected output/reference context
  -> canonical output_id + nonblank source job_id
  -> Output Store record lookup
  -> exact record output_id/job_id match
  -> existing current-job exclusion and byte-integrity checks
  -> available person-identity evidence
```

The resolver should collect bindings from the existing context projections
(`selected_output_assets`, `selected_reference_assets`,
`selected_visual_references`, and `strong_reference_bindings`) only when the
entry carries the existing canonical-output marker and both output identity
and source job identity. The existing professional anchor compatibility path
continues to work; when it supplies a source job, that job is checked too.

The implementation must compare the context source job to the Output Store
record's owning job before returning `available`. A wrong or missing source
job, a missing canonical marker, a swapped output, or a current-job output
must remain invalid/unavailable and must not trigger a provider or retry.

No new persisted state, biometric data, prompt parsing, regex classification,
quality threshold, retry budget, or public disclosure field is required.

## 4. Acceptance Tests

The focused regression must prove:

- a General selected historical output with the exact server context binding
  produces available `person_identity` evidence and a certifying review plan;
- a fresh service/read of the same context reuses the same binding;
- a wrong source job, missing canonical marker, and swapped output remain
  non-certifying;
- a current-job output remains rejected;
- existing professional anchor and ordinary uploaded-reference tests remain
  unchanged;
- public review output contains no private source job, path, digest, prompt,
  or resolver-only identifiers.

Run the focused review suites, the project-mode reference/context suite, the
adjacent provider/MCP and Professional suites, then Python compile and diff
checks. This phase remains local until the complete audit passes; GitHub,
main, and VPS are unchanged.

## 5. Stop Conditions

Stop and re-audit the model if the fix needs a new scenario branch, trusts
client metadata, weakens an existing gate, copies private bindings into a
public projection, or changes Provider/MCP routing. A passing local unit test
does not authorize deployment or real generation by itself.
