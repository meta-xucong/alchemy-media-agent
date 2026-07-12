# E01 E-Commerce Module Scope, Goals, and Boundary

## Product promise

Turn a product reference and a short request into a coherent, reviewable,
platform-aware commerce image suite. The system should explain the purpose of
each image in plain language and allow one slot to be regenerated without
restarting the entire project.

## In scope

- Product truth extraction and user correction.
- Platform/market profile selection.
- Category-specific evidence and suite planning.
- Selling-point prioritization.
- Optional localized provider-native image copy intent and final-pixel review.
- Product-first, lifestyle, detail, comparison, trust, and ad roles.
- Per-slot generation, review, bounded retry, selection, and export.
- Project continuation using selected product references and rejected directions.
- Versioned platform and category profiles.

## Out of scope for the first release

- Guaranteed marketplace approval, sales lift, or legal compliance.
- Full listing-title/bullet/description generation.
- Automatic scraping of live competitor listings.
- Automatic publishing to marketplace accounts.
- Arbitrary user-uploaded executable plugins.
- Provider-specific controls in the public API.
- A new image-generation runtime.
- Moving commerce rules into General Template or shared visual plugins.

## Layer ownership

| Layer | Owns | Must not own |
| --- | --- | --- |
| V3 foundation | visual quality, provider-native complete-image generation, review, retry, reference integrity | marketplace deliverable maps or local text rendering |
| General Template | neutral single images and simple product scenes | listing suites, A+ roles, platform assumptions |
| E-Commerce Template | platform/category suite roles and export | generic human/product rendering implementation |
| Platform profile | market expectations, slots, text/export policy evidence | product facts, typography coordinates, or generation provider choice |
| Platform profile | verified placement constraints, seller-configured placement, locale/export hints | product facts, unsupported style claims, typography coordinates, or generation provider choice |
| Category pack | buyer evidence and category slots | marketplace policy truth |
| Product truth | confirmed facts and unknowns | invented claims or unsupported specs |

## Two-axis planning model

The planner computes:

```text
product_truth
× marketplace compliance evidence
× category evidence suite
× user_request
× requested_count
× localization_profile
× seller-selected creative strategy
```

The result is a list of independent `EcommerceAssetRecipe` records. Verified
constraints, evidence needs, and creative strategy remain separately auditable.
Only verified constraints may be described as a marketplace rule; creative
strategy is an opt-in seller choice.

## Non-negotiable product rules

1. Product shape, quantity, label, logo, color, material, and visible structure
   are preserved unless the user explicitly requests a redesign.
2. Unknown facts remain unknown; the system must not invent capacity,
   certification, ingredients, performance, or warranty claims.
3. Main-image restrictions are slot-specific. A platform profile must not make
   all images look like the main image.
4. Approved copy is expressed in the LLM/provider creative brief and reviewed
   from final pixels; it is never locally overlaid after generation.
5. Retry outputs remain append-only internally; delivery surfaces show only the
   final requested count.
6. Every slot has one primary business purpose.
