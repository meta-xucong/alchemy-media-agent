# 08 Golden Cases

This document defines golden test cases for the V3 foundation pipeline.

Codex should use these cases to implement deterministic tests and avoid arbitrary interpretation.

## 1. Purpose

Golden cases define expected behavior for:

- intent parsing
- industry detection
- platform detection
- asset series planning
- layout defaults
- text rendering policy
- prompt compilation notes
- brand memory behavior
- evaluation defaults

These cases are not final product UX examples only. They are implementation anchors.

## 2. Global Assertions for All Cases

Every golden case should satisfy:

```text
1. Pipeline completes without importing V1/V2 runtime modules.
2. CreativeJob.raw_user_input equals the original input.
3. CommercialBrief.industry is not unknown unless no keyword matches.
4. SeriesPlan has at least one AssetSpec.
5. Every AssetSpec has platform, aspect_ratio, purpose, and asset_type.
6. Poster-like LayoutPlan uses html_overlay text rendering by default.
7. PromptCompilationResult warns against fake final Chinese text when html_overlay is used.
8. GenerationPlan.provider_strategy is planning_only in V3.0 foundation.
9. CommercialAssetPack.planning_only is true in V3.0 foundation.
10. Metadata exists for all major outputs.
```

## 3. Case 1: Milk Tea Summer Promotion

### Input

```text
帮我做一组奶茶店夏季新品促销图，要清爽、高级一点，适合小红书和外卖平台。
```

### Expected CommercialBrief

```text
industry: beverage
scenario: summer_new_product_promotion or equivalent
target_platforms include: xiaohongshu, delivery_app
business_goal: promotion / drive purchase / new product launch
visual_tone includes: fresh, clean, premium
commercial_hooks include: summer, new product, promotion
```

### Expected SeriesPlan

Must include at least:

```text
xiaohongshu asset:
  platform: xiaohongshu
  aspect_ratio: 4:5
  asset_type: social_cover or main_poster

delivery asset:
  platform: delivery_app
  aspect_ratio: 1:1
  asset_type: delivery_cover
```

### Expected LayoutPlan

```text
text_rendering: html_overlay
product_area: center or equivalent
headline_area: top area
cta_area: bottom or lower area
reserved_text_regions not empty
```

### Expected PromptCompilationResult

Must include ideas similar to:

```text
clean commercial beverage photography
summer freshness
premium but approachable
reserve clean text areas
avoid fake final Chinese text
```

### Brand Memory Behavior

If no brand id is supplied:

```text
create temporary BrandProfile
visual_tone includes fresh / clean / premium
industry: beverage
```

## 4. Case 2: Barbecue Late-Night Promotion

### Input

```text
帮我做一组烧烤店夜宵促销图，干净高级一点，适合朋友圈和美团。
```

### Expected CommercialBrief

```text
industry: restaurant_barbecue
target_platforms include: wechat_moments, meituan or delivery_app
business_goal: late-night promotion / local conversion
visual_tone includes: clean, premium, appetite
commercial_hooks include: late night, barbecue, promotion
```

### Expected SeriesPlan

Must include:

```text
wechat asset:
  platform: wechat_moments
  aspect_ratio: 3:4 or 4:5
  asset_type: wechat_moments_poster

meituan/delivery asset:
  platform: meituan or delivery_app
  aspect_ratio: 1:1
  asset_type: delivery_cover or group_buying_image
```

### Expected Prompt Notes

Should include:

```text
appetizing barbecue food
clean premium dining atmosphere
not dirty, not smoky chaos
warm night-food mood
```

## 5. Case 3: Hotpot Winter Set Meal

### Input

```text
做一个火锅店冬季套餐推广图，要热闹、有食欲，但不要太土。
```

### Expected CommercialBrief

```text
industry: restaurant_hotpot
scenario: winter_set_meal_promotion
target_platforms: default platforms because none specified
visual_tone includes: warm, appetite, lively, modern
negative/risk notes include: avoid outdated / tacky / cluttered style
```

### Expected Default SeriesPlan

If no platform is specified, create default commercial series:

```text
main_poster 4:5
social_cover 4:5
square_product or delivery_cover 1:1
```

### Expected Prompt Notes

```text
warm steam
rich hotpot ingredients
modern clean restaurant mood
avoid tacky composition
```

## 6. Case 4: Beauty / Nail Salon Opening Offer

### Input

```text
帮我做一个美甲店开业优惠图，适合小红书和朋友圈，风格要高级、温柔、干净。
```

### Expected CommercialBrief

```text
industry: local_service_beauty
scenario: opening_promotion
target_platforms include: xiaohongshu, wechat_moments
visual_tone includes: premium, gentle, clean
business_goal: attract opening customers
```

### Expected SeriesPlan

```text
xiaohongshu: 4:5
wechat_moments: 3:4 or 4:5
```

### Expected Prompt Notes

```text
soft premium beauty salon atmosphere
clean hands / nail detail / elegant background
reserve text region for opening offer
```

## 7. Case 5: E-Commerce Bluetooth Headphones

### Input

```text
帮我做一组蓝牙耳机淘宝主图，要科技感、干净、突出降噪和续航。
```

### Expected CommercialBrief

```text
industry: ecommerce_product
target_platforms include: taobao or ecommerce_generic
business_goal: product conversion
visual_tone includes: tech, clean, premium
selling_points include: noise cancellation, battery life
```

### Expected SeriesPlan

Must include at least:

```text
ecommerce_main_image:
  platform: taobao or ecommerce_generic
  aspect_ratio: 1:1
  purpose: product main image

product_detail_banner or campaign_banner:
  purpose: feature highlight
```

### Expected Text Policy

```text
html_overlay or svg_overlay for feature labels
avoid model-generated Chinese feature text
```

## 8. Case 6: Continue Previous Brand Style

### Input

```text
沿用上次奶茶店的清爽风格，帮我做一个端午节活动图。
```

### Optional Context

```text
optional_brand_id exists and BrandProfile exists
```

### Expected Behavior

```text
BrandMemoryAgent loads BrandProfile.
CreativePlan references existing style.
PromptCompilationResult includes brand consistency notes.
ConditionPlan may enable style_condition if reference assets exist.
```

### Expected CommercialBrief

```text
industry: beverage
scenario: festival_promotion
target_platforms: default if not specified
visual_tone includes existing brand tone plus festival adaptation
```

### Expected Memory Policy

```text
Do not overwrite existing brand profile during planning.
Create a proposed MemoryUpdate only after accepted output later.
```

## 9. Case 7: Minimal Input

### Input

```text
做一张咖啡店海报。
```

### Expected Behavior

The system should not fail.

Expected defaults:

```text
industry: beverage or restaurant_general
scenario: generic_promotion or brand_poster
target_platforms: default platforms
visual_tone: clean, commercial, inviting
series count: default 3
requires_clarification: false
```

### Rationale

Target users often provide very short requests. The system should make useful defaults rather than demanding expert input.

## 10. Case 8: Print-Like Poster With Explicit Text

### Input

```text
做一张火锅店海报，标题写“冬季双人套餐 128 元”，下面写“今日下单送小酥肉”。
```

### Expected Behavior

```text
CommercialBrief captures offer details.
LayoutPlan includes headline and CTA text.
text_rendering: html_overlay or svg_overlay
PromptCompilationResult tells image model not to render fake final Chinese text.
```

### Expected Layout Fields

```text
headline_area.text or metadata contains: 冬季双人套餐 128 元
cta_area.text or metadata contains: 今日下单送小酥肉
```

### Important

The image model should generate the food/background visual only. Real text should be rendered by the layout layer later.

## 11. Case 9: Unknown Industry But Clear Platform

### Input

```text
帮我做一个活动宣传图，适合小红书，风格要高级。
```

### Expected Behavior

```text
industry: unknown or local_service_general
platform: xiaohongshu
aspect_ratio: 4:5
visual_tone includes: premium
requires_clarification: false
```

### Rationale

Unknown industry should not block planning. The system can create generic commercial creative plans.

## 12. Required Test Names

Recommended tests:

```text
test_golden_milk_tea_xiaohongshu_delivery
test_golden_barbecue_wechat_meituan
test_golden_hotpot_default_series
test_golden_beauty_xiaohongshu_wechat
test_golden_ecommerce_taobao_headphones
test_golden_brand_continuation
test_golden_minimal_input_defaults
test_golden_explicit_chinese_text_overlay
test_golden_unknown_industry_platform_still_plans
```

## 13. Golden Case Success Definition

The V3.0 foundation is not expected to create final images.

It is successful if these cases generate correct planning structures and deterministic tests pass.