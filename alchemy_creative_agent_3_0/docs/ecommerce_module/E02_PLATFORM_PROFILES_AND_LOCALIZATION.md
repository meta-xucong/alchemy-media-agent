# E02 Platform Profiles, Market Adaptation, and Localization

## Design principle

Platform preferences are operational profiles, not permanent facts in code.
Each profile has `profile_id`, `platform`, `market`, `version`, `source_notes`,
`effective_at`, `reviewed_at`, and `status`.

The planner may use a profile only when its status is active. Unknown or stale
profiles degrade to a generic commerce profile and emit a review warning.

## Initial strategic profiles

| Profile family | Default visual strategy | Typical roles |
| --- | --- | --- |
| Amazon | compliant product-first sequence with narrative secondary images | main, benefit, detail, use, size/compatibility, trust/A+ |
| Ozon | mobile-readable scene-led commerce images with concise Russian copy when needed | scene hero, benefit, detail, size, use, trust |
| Taobao/Tmall | high-impact first impression plus rich detail-page storytelling | hero, angle, detail, benefit, scene, size, service/trust |
| JD | clear product, parameters, quality and service confidence | main, function, specification, detail, scene, trust |
| Pinduoduo | immediate product/benefit/quantity comprehension | hero, benefit, quantity, comparison, use, promotion-safe cover |
| TikTok Shop | scroll-stopping but truthful real-use and creator-friendly visuals | hook, hand-held/use, detail, proof, cover, listing main |
| Shopify/independent site | brand-consistent product story across page and campaign | hero, product, lifestyle, detail, proof, brand story |

These are planning defaults. Actual platform policies must be imported or
maintained as versioned data and reviewed before production use.

## Profile contract

```text
MarketplaceRuleProfile
  platform
  market
  version
  status
  image_slots
  main_image_rules
  secondary_image_rules
  allowed_text_modes
  recommended_aspect_ratios
  safe_area
  export_rules
  prohibited_or_risky_claims
  source_notes
  reviewed_at
```

## Localization contract

```text
LocalizationProfile
  locale
  language
  market
  terminology_policy
  max_copy_length_by_slot
  typography_policy
  decimal_and_unit_policy
  required_human_review
```

Initial locales: `en-US`, `ru-RU`, `zh-CN`, with `ja-JP` and EU language packs
later. Copy generation must preserve user-provided product names, trademarks,
measurements, and claims exactly unless the user requests translation.

## Text pipeline

```text
selling point
→ localized short copy
→ copy validation
→ layout/safe-area plan
→ image generation with reserved space
→ deterministic text render
→ OCR, overflow, spelling, and claim review
```

Main images default to `text_forbidden`. Text-enabled slots must declare the
language, exact text, position, maximum length, and whether post-render text is
mandatory.

## Profile update policy

- Never silently change an in-flight job's profile.
- Freeze profile versions into the job and export manifest.
- New profile versions affect only new jobs unless explicitly migrated.
- A profile change requires focused tests and at least three materially
  different product/category fixtures.

