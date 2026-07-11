# E09 Implementation Log and Parallel-Safe Delivery Record

## Purpose

Record independently deliverable E-Commerce milestones, their boundary, test
evidence, and integration dependency. This log does not replace the roadmap;
it makes later rebase and integration decisions auditable.

## E1 — category and marketplace planning baseline

Status: implemented and verified on `codex/ecommerce-module-docs`.

Delivered:

- Versioned category profiles for apparel, beauty, electronics, home/kitchen,
  and food/beverage.
- Category aliases and evidence/review metadata.
- Ozon marketplace profile with a mobile-readable, scene-led default suite.
- Category-priority selection when a requested image count constrains a suite.

Boundary:

- Only `app/scenario_packs/ecommerce/` and E-Commerce tests changed.
- No Central Brain, provider, shared capability, Project Mode public contract,
  General Template, or shared frontend changes.

Verification:

```text
focused E-Commerce tests: 15 passed
full V3 tests: 401 passed
```

Commit: `1ddda11`

## E2 — localization, copy review, and export metadata

Status: implemented and verified on `codex/ecommerce-module-docs`.

Goal:

```text
versioned locale profile
→ slot-safe copy plan
→ metadata-only copy/claim review
→ locale-aware export manifest
```

Rules:

- The first release does not invent translations. It uses user-supplied localized
  copy when present and otherwise marks derived copy for localization review.
- Main images remain text-forbidden when the platform slot policy requires it.
- Exact product names, trademarks, measurements, and confirmed claims remain
  protected data.
- No OCR renderer, provider path, or public API change belongs to this milestone.

Delivered:

- Versioned `en-US`, `ru-RU`, and `zh-CN` locale resolution from platform,
  market, or explicit user locale.
- Slot-safe copy plans: main/hero slots reject overlay text; other slots record
  text, source, locale, truncation, and review state.
- User-supplied localized copy is preserved within slot limits.
- Derived non-English copy is explicitly marked for native-language review
  rather than presented as a translated claim.
- Commerce Critic and export metadata carry localization-review state.

Verification:

```text
focused E-Commerce tests: 19 passed
full V3 tests: 405 passed
```

Integration dependency: none beyond normal rebase before integration.
