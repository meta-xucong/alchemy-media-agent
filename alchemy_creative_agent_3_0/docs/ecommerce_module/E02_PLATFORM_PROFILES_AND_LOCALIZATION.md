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
| Amazon | clean white-background product-first main image with narrative secondary images | main, benefit, detail, use, size/compatibility, trust/A+ |
| Ozon | mobile-readable scene-led commerce images with concise Russian copy when needed | scene hero, benefit, detail, size, use, trust |
| Taobao/Tmall | high-impact first impression plus rich detail-page storytelling | hero, angle, detail, benefit, scene, size, service/trust |
| JD | clear product, parameters, quality and service confidence | main, function, specification, detail, scene, trust |
| Pinduoduo | immediate product/benefit/quantity comprehension | hero, benefit, quantity, comparison, use, promotion-safe cover |
| TikTok Shop | scroll-stopping but truthful real-use and creator-friendly visuals | hook, hand-held/use, detail, proof, cover, listing main |
| Shopify/independent site | brand-consistent product story across page and campaign | hero, product, lifestyle, detail, proof, brand story |

These are planning defaults. Actual platform policies must be imported or
maintained as versioned data and reviewed before production use.

The active internal planning profile also resolves one named visual direction
per suite role. For example, Amazon distinguishes a white-background main
image from narrative benefit/detail/use images; Ozon prioritizes mobile-readable
scene-led product storytelling; Taobao/Tmall separates a high-impact first
impression from richer detail-page proof. These are art-direction defaults, not
claims of current marketplace compliance or approval.

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
seller facts and approved literal copy
→ LLM creative reasoning
→ provider-native complete-image generation
→ final-pixel OCR/vision/claim review
→ provider-native targeted revision when needed
```

Main images default to `text_forbidden`. A text-enabled image may carry
approved literal wording and locale, but the LLM/provider—not a slot
coordinate, maximum-length rule, or post-render layer—decides the visual
expression. Final-pixel review decides whether it is accepted.

## Profile update policy

- Never silently change an in-flight job's profile.
- Freeze profile versions into the job and export manifest.
- New profile versions affect only new jobs unless explicitly migrated.
- A profile change requires focused tests and at least three materially
  different product/category fixtures.
