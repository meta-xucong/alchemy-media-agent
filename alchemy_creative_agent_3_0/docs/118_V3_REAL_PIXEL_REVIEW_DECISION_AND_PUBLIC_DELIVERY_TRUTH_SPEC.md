# Doc118 V3 Real-Pixel Review Decision and Public Delivery Truth Closure

Status: corrective shared-foundation development and acceptance authority after
Doc117 controlled real-reference acceptance. This document closes a review
decision/projection defect found with an authorized garment reference. It does
not add a child, apparel, E-Commerce, Photography, or General-template recipe.

Scope: shared real-pixel inspection, shared bounded visual retry, Product API
public projection, and browser-facing final-delivery eligibility. It extends
Docs 53, 55, 66, 113, 114, and 117.

## 0. Decision record

The controlled General acceptance produced real GPT Image 2 pixels through one
reference-backed `image_edit` operation. Remote Brain was used without fallback
and the enforced plan froze `human_realism` as required. The failure was not
Provider admission, template routing, or a missing Human Realism activation.

The actual post-generation `hybrid / verified` inspection instead reported:

```text
status: manual_review
confidence: 0.78
issues: low_confidence_review, uncanny_micro_detail
inspection.retryable: false
```

At the same time, the derived real-review signal retained
`uncanny_micro_detail` as retryable, while the AutoRetry decision said that no
clear fixable issue existed. The public General summary also repeated the
planning-time message "No candidate pixels supplied; review is metadata-only."
even though a real-pixel hybrid inspection had completed.

Those states are contradictory. A low-confidence review is a trust boundary:
it may explain why a human must inspect the image, but it must not be converted
back into an automatic repair instruction by a downstream projection.

## 1. Authority and boundaries

The existing `VisualInspectionReport` is the canonical result of one
post-generation inspection. Its final `status`, `retryable`, verification state,
and frozen retry patch jointly govern every downstream side effect.

```text
real pixels
  -> VisualInspectionReport (canonical final status)
  -> shared review package / retry decision
  -> append-only retry only when eligible
  -> public final-delivery projection
```

No later signal package, browser adapter, or template may reinterpret an
individual detected issue and weaken the report's final status.

This document must not:

- add child-, kidswear-, face-, product-, or template-specific retry rules;
- make a low-confidence vision opinion more authoritative by retrying it;
- create a second reviewer, status machine, Provider request, or manual
  certification mechanism;
- reveal source paths, full prompts, raw provider replies, or internal retry
  payloads; or
- expose an unapproved or superseded candidate as a beginner-facing final
  delivery.

Human Realism, Product Identity, Reference Policy, and Universal Visual Quality
continue to publish their existing generic issue contracts. Doc118 changes only
how an already-produced shared inspection becomes a retry decision and a public
delivery state.

## 2. Corrected invariants

### R1. Final inspection status wins over issue-level hints

Automatic retry is eligible only when all of the following are true for the
same inspected output:

```text
inspection.status == fail_retryable
inspection.retryable == true
inspection.verification_state == verified (or the existing deterministic local-artifact check is locally_checked)
at least one issue is retryable
the existing frozen/shared retry patch is non-empty and in scope
```

The existing deterministic `local_image_heuristic` may retain its
`locally_checked` retry eligibility for file/provenance artifacts; it does not
certify final delivery. The only other compatibility exception is an explicit
`fake_for_tests` fixture used by offline executor regressions. It is not a
runtime review mode and must never make an unverified production inspection
retryable.

If `status == manual_review`, `fail_final`, or an inspection is unverified,
there is no automatic retry signal. Any retryable flag carried by an individual
issue remains diagnostic only. It cannot produce retryable candidate IDs,
retryable output IDs, or `commercial_readiness_status=retryable_issue`.
An unverified `fail_retryable` result must create a review hold rather than the
misleading fallback decision "no clear fixable issue".

For `manual_review`, the public-safe outcome is:

```text
manual_confirmation_required: true
automatic_retry: not permitted
automatic_final_delivery: withheld
```

The AutoRetry decision must say that manual confirmation is required; it must
not claim that no clear issue was found.

### R2. A delivery is not the same thing as a generated candidate

Existing internal candidates and output records remain append-only. A
beginner-facing result surface may expose an output as final delivery only when
the corresponding real-pixel report is both verified and has status `pass` or
`warning`.

```text
pass / warning + verified -> eligible final delivery
fail_retryable             -> retained history; wait for bounded retry result
manual_review              -> retained history; final delivery withheld
fail_final                 -> retained history; final delivery withheld
no pixels                  -> no candidate/review/delivery
```

This is a public projection derived from the existing review package. It does
not delete an output, mutate its audit record, or invent a new lifecycle. An
ordinary automatic/default selection endpoint is not a manual certification
mechanism: it must not turn a `manual_review` inspection into a selected final
delivery. If an explicit, auditable human-confirmation flow is introduced in a
future authority document, it must remain separate from automatic review and
must never rewrite a manual-review inspection into a verified automatic pass.

### R3. Post-generation truth supersedes planning-only review hints

The planning-time `output_review` capability is correctly metadata-only before
pixels exist. Once a `vision_model` or `hybrid` inspection has actually run,
General's user-facing review hints and warning list must use the final
post-generation projection instead.

The stale planning hint may remain in private capability history, but it must
not appear in the final Job/Project/Browser result as though no pixels were
available. A local or metadata-only final inspection does not qualify for this
suppression.

### R4. Safe public delivery/readiness projection

The Product API public projection must provide a compact delivery truth derived
from real inspection records:

```json
{
  "final_delivery_status": "ready | withheld_manual_confirmation | withheld_review_failure | not_evaluated",
  "automatic_delivery_available": true,
  "manual_confirmation_required": false,
  "reviewed_output_count": 1,
  "final_delivery_output_count": 1,
  "delivery_gate_applies": true
}
```

It must not disclose an internal retry patch, candidate provenance, Provider
error, local file path, source image identity, or full prompt. Existing
Doc117 `provider_execution` remains the source for whether pixels were
received; Doc118 must not duplicate it.

`delivery_gate_applies` is true when a real `vision_model` or `hybrid`
post-generation inspection was attempted. It is deliberately separate from
`reviewed_output_count`: an unverified or unavailable real inspection counts
as a reason to withhold automatic delivery, but not as certified real-pixel
review. Existing local deterministic checks and explicit offline fixtures keep
their compatibility semantics; they do not become a substitute certification
or activate the real-review delivery gate. If no real post-generation
inspection was attempted, legacy planned-only status remains distinguishable
and this closure does not invent a review result.

## 3. Implementation plan

### Phase 0 — red contract tests

Add regressions for all of the following, using generic issue codes and test
fixtures only:

1. a `manual_review` inspection containing a diagnostic retryable issue creates
   no auto-retry signal and requires manual confirmation;
2. a verified `fail_retryable` inspection still creates the existing bounded
   retry signal;
3. a verified `manual_review` output is retained internally but excluded from
   public final delivery;
4. a verified `warning` output remains eligible for final delivery;
5. an unverified real `vision_model`/`hybrid` `fail_retryable` report cannot
   trigger retry or a pass-like fallback, and any unverified/unavailable real
   inspection withholds automatic delivery; and
6. a real `vision_model`/`hybrid` inspection removes the stale General
   metadata-only hint, while a true metadata-only inspection retains it; and
7. no-pixel Doc117 behavior remains unchanged: no candidate, visual review,
   retry, or delivery is produced.

### Phase 1 — canonical retry eligibility

Update the shared review merger so its candidate signal derives
`retryable_issue_codes` only from a report eligible under R1. Make
`RealReviewSignalPackage` and `AutoRetryDecision` agree on manual-review
outcomes. Reuse the existing frozen retry-contract filtering; do not create a
new issue-to-prompt mapper.

### Phase 2 — final-delivery projection

Derive delivery eligibility from the real review package while serializing
Product Job status. Filter beginner-facing `asset_series`, corresponding
candidate summaries, and public review output-ID lists to eligible final
output IDs when a real review package exists. Preserve append-only audit and
lifecycle history internally.

`manual_review` and `fail_final` must set safe withheld state. `fail_retryable`
may expose only a final retry winner that itself passes the same gate.

### Phase 3 — General post-generation summary

Keep General scenario-neutral. Replace only the stale pre-generation
metadata-only wording with compact final-review facts: inspection mode,
certification state, and safe delivery/manual-confirmation state. Do not add
garment, child, beauty, scene, or pose text.

### Phase 4 — acceptance

Run the focused shared-review/Product API/Project/Browser regressions, then
repeat the same authorized General reference request with one 1024x1536 image
and `require_real_images=true`:

```text
remote Brain without fallback
-> GPT Image 2 image edit
-> real pixel provenance
-> hybrid or vision_model review
-> bounded retry only when R1 permits it
-> accurate final delivery or explicit manual hold
```

Visual assessment remains a separate quality conclusion. A correct state
projection cannot turn low garment fidelity, synthetic skin, or an unconvincing
image into a quality pass.

## 4. Acceptance matrix

| Case | Retry | Public final delivery | Required public state |
| --- | --- | --- | --- |
| verified `pass` | no | yes | `ready` |
| verified `warning` | no | yes | `ready` |
| verified `fail_retryable` + frozen patch | bounded existing path | only passing/warning winner | retry history folded |
| `manual_review`, including low confidence | no | no | `withheld_manual_confirmation` |
| `fail_final` | no | no | `withheld_review_failure` |
| metadata-only final inspection | no automatic certification | no automatic delivery | `not_evaluated` / manual state |
| Doc117 no-pixel failure | no | no | existing safe Provider failure state |

## 5. Done criteria

Doc118 is complete only when:

1. shared review decision, real-review signal, retry executor, and public
delivery projection agree for every status in the matrix;
2. General no longer says metadata-only after a real-pixel inspection;
3. no new template/vertical/child-specific branch or prompt fragment exists;
4. focused regressions and the relevant full shared suites pass; and
5. a controlled real run is reported strictly from actual pixels and review
evidence, with a manual hold reported as a hold rather than a pass.
