# Doc123 V3 Retry-Failure and Manual-Confirmation Truth

Status: corrective shared-foundation authority discovered during the controlled
Doc118/Doc121 General reference acceptance. It applies to every V3 template
and does not add a child, apparel, product, E-Commerce, Photography, or
General prompt branch.

## 0. Observed defect

A generated candidate was correctly withheld after a verified shared review
returned `fail_retryable`. Its one bounded retry then ended in a Provider 400
without a retry pixel. The public retry projection treated the retry record's
`failed` state as `manual_confirmation_required`, even though the final
delivery gate exposed no output that a user could confirm or receive.

This made the public warning inaccurate: retry execution status was being
mistaken for a delivery entitlement.

## 1. Corrected invariant

1. Only the final-delivery projection may assert
   `manual_confirmation_required`.
2. A retry record with `failed` or `blocked` remains visible as bounded
   workflow provenance, but never by itself creates a manual-confirmation
   route.
3. If a reviewed output is eligible for retained/manual delivery, that
   final-delivery decision is forwarded unchanged to the public retry summary.
4. If all reviewed candidates are withheld, public status must show the
   withheld-review failure, not claim that a user can approve an unavailable
   candidate.

## 2. Boundaries

- This correction does not retry another time, relax review, promote rejected
  pixels, or expose hidden candidates.
- It does not disclose provider exceptions, retry patches, prompts, file
  paths, endpoints, credentials, or raw upstream details.
- It applies equally to General and specialized templates and does not add a
  subject-specific visual or repair rule.

## 3. Required regression

- A failed retry record with no final-delivery confirmation must project
  `manual_confirmation_required: false`.
- The same retry record must preserve `manual_confirmation_required: true`
  when the final-delivery gate explicitly supplied it.
- The public retry record must still be redacted to safe attempt status and
  issue codes.

## 4. Acceptance consequence

The controlled job remains append-only historical evidence. Its initial pixel
is withheld by verified review and its Provider-failed retry provides no
candidate for manual action. The corrected UI/API projection now communicates
that terminal state honestly; it does not convert the withheld job into a
visual-quality pass.
