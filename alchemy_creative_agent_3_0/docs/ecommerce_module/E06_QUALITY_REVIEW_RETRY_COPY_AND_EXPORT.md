# E06 Quality Review, Retry, Copy, and Export

## Review layers

### Universal V3 review

Use the shared foundation for artifacts, composition, exposure, finish,
watermarks, anatomy, and general image usability.

### Commerce review

Review:

- product truth and visible product identity;
- source, verification state, and slot binding of E-Commerce product facts;
- platform slot fit;
- selling-point clarity;
- buyer-question coverage;
- suite differentiation;
- requested-text correctness and final-pixel legibility;
- unsupported claims, fake certificates, and invented specifications;
- packaging/logo/label integrity;
- commercial direct-use readiness.

### Category review

Only the active category pack may add category-specific checks. A product-only
image must not receive person/skin/portrait checks unless a visible person is
actually planned and activated through the shared Human Realism capability.

## Retry policy

Retry is bounded, append-only, and issue-specific.

```text
review issue
→ map issue to active capability/commerce contract
→ create minimal patch
→ regenerate the affected slot
→ compare candidates
→ retain best reviewed result
```

Do not retry solely because a newer result exists. Do not activate a dormant
capability after review without an auditable plan amendment.

## Copy policy

- Product names, trademarks, numbers, and confirmed claims are protected.
- Unconfirmed claims become warnings or are omitted.
- Facts marked blocked by the E-Commerce fact ledger are omitted from recipe
  bindings and overlay copy. Facts requiring confirmation produce an export
  publish-check warning; D4 will add persisted owner confirmation.
- Export records retain the E-Commerce category role, plain-language purpose,
  fact-channel intent, review checks, and differentiation key for each slot.
  These are planning/audit metadata, not a claim of pixel-level verification.
- Main-image text is forbidden by the E-Commerce module's conservative default.
  A verified platform restriction may strengthen that default, but the default
  itself is not represented as universal marketplace policy.
- A text-enabled slot may pass approved literal copy and locale only as part of
  a provider-native complete-image request. The E-Commerce module never uses
  local fonts, OCR, composition, coordinates, safe areas, or a private retry
  loop to create or repair text pixels.
- Historical local-text inputs are readable only as `provider_native_required`.
  A production text suite remains unavailable until Doc111 Provider Gate C/D
  has real authorized-material evidence.
- Translation must not change product facts or claim strength.

## Export manifest

```text
project_id
template_id
platform
market
profile_version
category_id
category_version
category_slot_role_id
category_slot_purpose
category_slot_fact_channels
category_slot_review_checks
category_slot_differentiation_key
delivery_scope_id
delivery_scope_version
delivery_scope_source
legacy_suite_scope
delivery_scope_status
delivery_scope_missing_requirements
delivery_scope_text_pixel_delivery_promised
selected_slot_ids
delivery_files
copy_locale
evidence_intent_id
platform_compliance_intent_id
platform_compliance_evidence_tier
creative_strategy_id
creative_strategy_applied
product_fact_ledger_version
product_fact_bindings
pending_product_fact_ids
review_summary
publish_checklist
generated_at
```

The export package must distinguish:

- final delivery outputs;
- rejected outputs;
- retry-superseded history;
- warnings requiring user review.

It must never claim guaranteed approval or guaranteed performance.

An export may preserve a seller-selected creative strategy for traceability,
but that value is never evidence that a marketplace requires or approves the
chosen visual style.

`listing_only` is the default delivery scope. A+ modules, content assets, and
storefront assets use separate role IDs. A+ and storefront plans without their
required placement context carry an attention check and no substitute listing
role; A+ planning never claims final text-pixel delivery.
