# E06 Quality Review, Retry, Copy, and Export

## Review layers

### Universal V3 review

Use the shared foundation for artifacts, composition, exposure, finish,
watermarks, anatomy, reference integrity, and general image usability.

### E-Commerce observational review

Review the final provider pixels against:

- product truth and visible product identity;
- verified platform/content/claim constraints;
- seller-approved claim and literal-copy fidelity;
- relevant buyer-question coverage;
- output-set differentiation;
- packaging/logo/label integrity; and
- commercial direct-use warnings.

The reviewer observes actual results. It does not turn category evidence into
a local visual recipe or reimplement shared Human Realism/Product Identity.

## Retry policy

Retry is bounded, append-only, and issue-specific.

```text
reviewed issue
-> shared Brain/provider-native revision path
-> regenerate the affected opaque output
-> compare candidates in the shared review path
-> retain the best reviewed delivery result
```

Do not retry merely because a newer image exists. Do not activate a dormant
capability after review without the shared auditable-plan amendment. Do not
replace a failed Brain decision with a static E-Commerce role, prompt, or shot.

## Copy policy

- Product names, trademarks, numbers, and confirmed claims are protected.
- Unconfirmed claims become warnings or are omitted.
- A verified platform text restriction applies only when relevant to the
  requested output and is sent as Brain/provider context.
- Requested text is generated as part of the provider image and checked from
  final pixels. A failure requests only a bounded provider-native revision.
- Translation never changes product facts or claim strength.
- No local font, overlay, canvas, coordinate, safe area, OCR compositor, or
  deterministic text repair may be introduced.

## Export manifest

```text
project_id
template_id
platform
market
profile_version
category_id
category_version
selected_output_ids
delivery_files
copy_locale
review_summary
publish_checklist
generated_at
```

The package distinguishes final delivery, rejected outputs, and
retry-superseded history. It includes factual/evidence provenance and the
Brain-returned output intent where useful for audit, but never promises
marketplace approval or performance.
