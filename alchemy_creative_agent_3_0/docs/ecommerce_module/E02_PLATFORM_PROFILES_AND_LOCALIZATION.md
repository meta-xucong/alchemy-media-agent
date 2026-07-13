# E02 Platform Constraints, Market Adaptation, and Localization

## Design principle

Platform knowledge is sourced, versioned constraint evidence—not a permanent
style catalogue or a local set of images to make. Each record has
`profile_id`, `platform`, `market`, `version`, `source_notes`, `effective_at`,
`reviewed_at`, and `status`.

An active record is supplied as factual E-Commerce context to the remote
Central Brain. An unknown or stale record produces a warning. It must not
degrade into a locally invented generic suite, default scene, or fallback role.

## Initial strategic profiles

| Profile family | Useful evidence for the Brain | Explicitly not a local output map |
| --- | --- | --- |
| Amazon | verified listing restrictions and accepted product-first constraints | a main/benefit/detail sequence |
| Ozon | verified market, mobile/readability, and Russian-language constraints | a default scene-led sequence |
| Taobao/Tmall | verified market/detail-page and Chinese-language constraints | a fixed hero/angle/detail sequence |
| JD/Pinduoduo | verified listing, content, and claim constraints | a conversion-role table |
| TikTok Shop | verified truthfulness and market constraints | a fixed creator or use shot |
| Shopify/independent site | seller-approved brand/campaign constraints | a local brand-story recipe |

Actual platform policies must be sourced, reviewed, frozen into the job, and
validated on real provider outputs before production activation.

## Profile contract

```text
MarketplaceConstraintProfile
  platform
  market
  version
  status
  verified_constraints
  claim_and_content_risks
  requested_canvas_constraints
  text_policy
  export_rules
  source_notes
  reviewed_at
```

`verified_constraints` may say what is forbidden or required. It must never
encode an automatic slot list, a camera/crop, a scene, a visual lane, a
marketing phrase, or a default image count.

## Localization contract

```text
LocalizationContext
  locale
  language
  market
  user_approved_literal_copy
  terminology_policy
  decimal_and_unit_policy
  required_human_review
```

Initial locale evidence supports `en-US`, `ru-RU`, and `zh-CN`; new locales are
added only with source/review provenance. User-provided product names,
trademarks, measurements, and claims are preserved exactly unless the user
explicitly requests translation.

## Text path

```text
seller facts and approved literal copy
-> remote Brain creative reasoning
-> provider-native complete-image generation
-> final-pixel vision/claim review
-> bounded provider-native revision when necessary
```

Where a verified restriction forbids text for a particular requested output,
that restriction is given to the Brain. Otherwise the Brain/provider decides
whether and how approved literal wording appears. No field may prescribe a
coordinate, line length, font, safe area, or post-render layer.

## Profile update policy

- Never silently change an in-flight job's profile.
- Freeze profile versions and evidence provenance into the job/export manifest.
- New versions affect only new jobs unless the user explicitly starts a new
  continuation with the changed evidence.
- A profile change requires focused tests and real-provider fixtures across at
  least three materially different products before it becomes production-ready.
