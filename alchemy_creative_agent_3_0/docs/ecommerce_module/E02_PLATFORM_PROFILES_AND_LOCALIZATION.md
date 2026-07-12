# E02 Platform Evidence, Placement Adaptation, and Localization

## Core rule

Platform profiles are versioned evidence records, not a way to turn common
seller aesthetics into platform law. Each job separates three decisions:

```text
verified platform constraint
→ evidence the shopper must see
→ seller-selected creative strategy
```

Only the first decision may describe a platform requirement. The second is
owned by the E-Commerce template and product category. The third is an explicit
seller choice and must never be presented as a compliance result.

## Evidence tiers

| Tier | Meaning | Runtime use |
| --- | --- | --- |
| `verified_requirement` | A current primary source supports a narrow requirement. | May add a named constraint, still subject to category/region checks. |
| `documented_operation` | A primary source confirms media workflow, ordering, or supported media. | May guide delivery structure, not visual styling. |
| `internal_strategy` | A conversion or art-direction hypothesis. | Available only through an explicit creative-strategy choice. |
| `seller_configuration_required` | Theme, campaign, category, or merchant settings determine the answer. | Do not hard-code a platform default. |

Source review date for this document: 2026-07-12. Profiles remain
`internal_draft` until a release process records the relevant country, category,
placement, effective date, and source review.

## Verified or documented baseline by platform family

| Platform family | Supported baseline | Template implication |
| --- | --- | --- |
| Amazon US | The primary image has a pure-white, actual-product baseline and excludes unrelated props, added text, badges, borders, and watermarks; category and regional exceptions still require review. Secondary images can show angles, details, scale, and use. | Keep the Amazon main-image constraint. Build secondary images around product evidence, not a fixed narrative style. |
| Ozon | Official seller material documents a primary-image order, review/moderation, up to 15 photos, plus video and rich content. It does not establish a universal scene-led primary-image rule. | Use a clear primary view plus angle/detail/size/use evidence. Offer scene or infographic treatment only as a seller choice. |
| Taobao/Tmall | No current public primary source was verified here for one universal visual style; category, campaign, device, and placement rules can differ. | Treat high-impact hero and rich detail storytelling as internal strategies, never default compliance. |
| JD | Truthful and complete product information is a documented baseline; a universal picture style was not verified here. | Make supplied parameters and product truth auditable; keep visual density as a seller choice. |
| Pinduoduo | No current public primary source was verified here for one universal visual style. | Make product type, supplied quantity, and scale clear when relevant; never infer price or promotion claims. |
| TikTok Shop | Official guidance for detail pages recommends clear product media including a front view, other angles, close-up, and use image. Creator/video hooks are a separate content mode. | Default to listing evidence; expose `content_hook` only for content-cover or ad roles. |
| Shopify | Shopify is merchant and theme configured. It supports images, video, and 3D media; product variants can have assigned images. | Do not impose marketplace ratios or a brand-story package. Let page placement, theme, and variant needs choose the output. |

Primary source registry:

- Amazon Seller Central: [product image requirements](https://sellercentral.amazon.com/seller-forums/discussions/t/5eef969a1508af21fb64e9db01ba5a7e)
- Ozon Seller Help: [product management and media](https://docs.ozon.com/global/ozon-seller-app/product-management/)
- TikTok Shop Seller: [high-quality detail-page media](https://seller.tiktokglobalshop.com/business/us/newsroom/detail/10022408)
- Shopify Help: [product media types](https://help.shopify.com/en/manual/products/product-media/product-media-types), [product photography](https://help.shopify.com/en/manual/products/product-media/product-photography), and [variant images](https://help.shopify.com/en/manual/products/product-media/add-images-variants)
- JD Global: [platform rules and truthful product information](https://global.m.jd.com/rules.html)

## E-Commerce evidence map

Every listing role has a product-evidence duty independent of platform
aesthetics:

```text
primary product truth
feature proof
material/component detail
verified use context
scale or quantity clarity
evidence-backed trust
content or collection context
```

The product/category pack decides which of these roles is needed. A requested
scene is allowed only when it preserves product truth; a requested measurement
or quantity image must use supplied facts or degrade to relative-scale proof.

## Creative strategy contract

The E-Commerce workspace exposes an optional strategy under existing
`commerce_profile.metadata.creative_strategy`:

| Strategy | Intended use | Boundary |
| --- | --- | --- |
| `evidence_first` | Default product listing suite. | Does not add platform aesthetic assumptions. |
| `scene_story` | Appropriate scene, collection, or campaign support images. | Does not override a verified primary-image constraint. |
| `information_rich` | Secondary images that need visual hierarchy and future approved-copy space. | It plans space; it does not render final text pixels. |
| `content_hook` | Content covers, ad covers, and benefit hooks. | It is not a generic listing-main-image default. |
| `brand_story` | Merchant-defined Shopify or branded landing-page media. | Requires merchant/theme/page context; it is not a Shopify requirement. |

## Canvas and export placement

No current profile treats a fixed aspect ratio or export pixel size as a
universal platform fact. The planner uses, in order:

1. explicit requested output size;
2. future verified seller/category/placement configuration;
3. a neutral internal fallback recorded as such.

Safe-area intent remains E-Commerce planning metadata. It may reserve space for
the future shared typography layer but does not promise text pixels, final
dimensions, or marketplace acceptance.

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

Initial locales are `en-US`, `ru-RU`, and `zh-CN`. Copy generation preserves
user-provided product names, trademarks, measurements, and claims unless the
user explicitly requests translation. Market and platform may provide a
default locale, but the seller can choose a supported locale.

## Text pipeline

```text
seller facts and approved literal copy
→ LLM creative reasoning
→ provider-native complete-image generation
→ shared provider-native delivery and claim acceptance
```

The E-Commerce template keeps main and hero images text-free as a conservative
module default unless a future verified category/placement rule safely changes
that decision. A text-enabled image may carry only approved literal wording
and locale to the provider; the provider, rather than a coordinate,
maximum-length rule, or post-render layer, decides its visual expression.
The accepted delivery remains subject to the shared provider-native path and
Doc111 Gate C/D evidence.

## Profile update policy

- Never silently change an in-flight job's profile.
- Freeze profile version, evidence tier, strategy, and source notes into each
  job and export manifest.
- New profile versions affect only new jobs unless explicitly migrated.
- A verified-constraint change requires a primary source, scope/effective-date
  record, focused tests, and at least three materially different fixtures.
- An internal strategy may evolve through product testing, but it must remain
  selectable, reversible, and visibly distinct from a platform requirement.
