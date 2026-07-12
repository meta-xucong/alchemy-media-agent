# E06 Quality Review, Retry, Copy, and Export

## Review layers

### Universal V3 review

Use the shared foundation for artifacts, composition, exposure, finish,
watermarks, anatomy, and general image usability.

### Commerce review

Review:

- product truth and visible product identity;
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
- Main-image text is forbidden by default where the profile requires it.
- Requested text must be generated as part of the provider image, then checked
  from final pixels; a failure requests a provider-native revision and never a
  local font/overlay repair.
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
selected_slot_ids
delivery_files
copy_locale
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
