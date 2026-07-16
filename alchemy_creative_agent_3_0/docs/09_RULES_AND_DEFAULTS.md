# 09 Rules and Defaults

> **Doc135 authority:** deterministic defaults below are limited to technical
> validation, safety and archived compatibility. They cannot author or amend a
> new renderer-facing creative prompt.

> **Current text-image direction (2026-07-13):** [Doc111](111_V3_PROVIDER_NATIVE_TEXT_AND_ECOMMERCE_CREATIVE_DIRECTION_CORRECTION.md) supersedes any external-overlay, local-font, fixed-copy-region, or deterministic text-rendering default in this historical rules document. New work uses LLM creative direction and provider-native complete-image generation.

This document freezes first-pass deterministic rules for Alchemy Creative Agent 3.0.

The V3.0 foundation should be testable offline. Therefore, the first implementation should use rule-based and stub behavior rather than hidden LLM calls.

## 1. Rule Philosophy

Rules are not the final intelligence of the product.

They are the deterministic foundation that allows:

- stable tests
- predictable Codex implementation
- clear schema validation
- repeatable behavior before LLM agents are connected

Later versions may replace or enhance rules with LLM-based agents, retrieval, scoring models, or provider-specific adapters.

## 2. Input Normalization

Normalize user input before rule matching:

```text
1. trim whitespace
2. preserve original raw text
3. convert full-width punctuation where useful
4. keep Chinese words unchanged
5. lowercase English tokens
6. do not translate the original input in-place
```

Store both:

```text
raw_user_input
normalized_input
```

if implementation needs it.

## 3. Industry Detection Rules

### 3.1 Beverage

Match any:

```text
奶茶
茶饮
果茶
咖啡
饮品
冷饮
柠檬茶
coffee
milk tea
beverage
```

Result:

```text
industry: beverage
```

Default visual tones:

```text
fresh
clean
commercial
appetizing
```

### 3.2 Restaurant / Barbecue

Match any:

```text
烧烤
烤串
夜宵
烤肉
barbecue
bbq
```

Result:

```text
industry: restaurant_barbecue
```

Default visual tones:

```text
appetite
warm
night_food
clean
commercial
```

### 3.3 Restaurant / Hotpot

Match any:

```text
火锅
麻辣烫
冒菜
锅底
hotpot
```

Result:

```text
industry: restaurant_hotpot
```

Default visual tones:

```text
warm
appetite
rich
lively
commercial
```

### 3.4 Restaurant General

Match any:

```text
餐厅
饭店
小吃
快餐
中餐
西餐
料理
外卖店
restaurant
food
```

Result:

```text
industry: restaurant_general
```

### 3.5 E-Commerce Product

Match any:

```text
淘宝
天猫
京东
拼多多
电商
主图
详情页
商品图
产品图
耳机
手机壳
服装
鞋子
包包
ecommerce
product image
main image
```

Result:

```text
industry: ecommerce_product
```

### 3.6 Beauty / Local Service

Match any:

```text
美甲
美睫
美容
美发
皮肤管理
按摩
 spa
开业优惠
nail
beauty
salon
```

Result:

```text
industry: local_service_beauty
```

### 3.7 Hospitality

Match any:

```text
酒店
民宿
客栈
度假
温泉
hotel
homestay
resort
```

Result:

```text
industry: hospitality
```

### 3.8 Unknown

If no match:

```text
industry: unknown
```

Unknown industry must not block planning.

Use generic commercial defaults.

## 4. Platform Detection Rules

### 4.1 Xiaohongshu

Match any:

```text
小红书
红书
种草
xiaohongshu
rednote
```

Result:

```text
platform: xiaohongshu
aspect_ratio: 4:5
```

### 4.2 WeChat Moments

Match any:

```text
朋友圈
微信朋友圈
私域
wechat
moments
```

Result:

```text
platform: wechat_moments
aspect_ratio: 3:4 or 4:5
```

First-pass default:

```text
4:5
```

### 4.3 Delivery App

Match any:

```text
外卖
美团
饿了么
团购
到店
delivery
meituan
eleme
```

Rules:

```text
美团 → meituan
饿了么 → eleme
外卖 without exact platform → delivery_app
```

Aspect ratio:

```text
1:1
```

### 4.4 E-Commerce

Match any:

```text
淘宝
天猫
京东
拼多多
电商
主图
详情页
商品图
taobao
jd
ecommerce
```

Rules:

```text
淘宝 / 天猫 → taobao
京东 → jd
else → ecommerce_generic
```

Aspect ratio:

```text
1:1
```

### 4.5 Douyin

Match any:

```text
抖音
douyin
tiktok
短视频封面
```

Aspect ratio:

```text
9:16
```

### 4.6 Store Screen

Match any:

```text
门店屏幕
电视屏
大屏
横屏
店内展示
store screen
```

Aspect ratio:

```text
16:9
```

### 4.7 Print Poster

Match any:

```text
打印
印刷
海报打印
A4
门店张贴
print
```

Aspect ratio:

```text
A4
```

## 5. Default Platform Fallback

If no platform is detected, create default asset series:

```text
main_poster:
  platform: generic_social
  aspect_ratio: 4:5

social_cover:
  platform: xiaohongshu
  aspect_ratio: 4:5

square_product:
  platform: delivery_app or ecommerce_generic depending on industry
  aspect_ratio: 1:1
```

Industry-specific square asset:

```text
restaurant / beverage → delivery_app 1:1
ecommerce_product → ecommerce_generic 1:1
other → generic_social 1:1
```

## 6. Visual Tone Mapping

### 6.1 Clean

Match:

```text
干净
清爽
简洁
高级干净
clean
minimal
simple
```

Normalize to:

```text
clean
```

### 6.2 Premium

Match:

```text
高级
质感
精致
高端
premium
luxury
refined
```

Normalize to:

```text
premium
```

### 6.3 Fresh

Match:

```text
清新
夏天
夏季
冰爽
水果
fresh
summer
refreshing
```

Normalize to:

```text
fresh
```

### 6.4 Appetite

Match:

```text
有食欲
诱人
好吃
烟火气
热气腾腾
appetizing
foodie
```

Normalize to:

```text
appetite
```

### 6.5 Warm

Match:

```text
温暖
温馨
冬季
热闹
warm
cozy
```

Normalize to:

```text
warm
```

### 6.6 Tech

Match:

```text
科技感
未来感
数码
智能
tech
futuristic
```

Normalize to:

```text
tech
```

### 6.7 Gentle

Match:

```text
温柔
柔和
女性化
优雅
gentle
soft
elegant
```

Normalize to:

```text
gentle
```

### 6.8 Lively

Match:

```text
热闹
活泼
节日
喜庆
lively
festival
```

Normalize to:

```text
lively
```

## 7. Negative Style Mapping

Match phrases such as:

```text
不要太土
不要杂乱
不要廉价
不要暗黑
不要赛博
不要太花
```

Map to `negative_direction` or `rejected_style_tags`:

```text
avoid_tacky
avoid_clutter
avoid_cheap_look
avoid_dark_style
avoid_cyberpunk
avoid_overdecorated
```

## 8. Scenario Detection Rules

### 8.1 New Product

Match:

```text
新品
上新
新品上市
new product
launch
```

Scenario:

```text
new_product_promotion
```

### 8.2 Opening Promotion

Match:

```text
开业
新店
开业优惠
opening
new store
```

Scenario:

```text
opening_promotion
```

### 8.3 Festival Promotion

Match:

```text
端午
中秋
春节
圣诞
七夕
节日
festival
```

Scenario:

```text
festival_promotion
```

### 8.4 Set Meal / Package

Match:

```text
套餐
双人餐
团购
package
set meal
```

Scenario:

```text
set_meal_promotion
```

### 8.5 Generic Promotion

Match:

```text
促销
优惠
活动
立减
折扣
promotion
discount
campaign
```

Scenario:

```text
generic_promotion
```

Default:

```text
brand_or_commercial_poster
```

## 9. Business Goal Defaults

By scenario:

```text
new_product_promotion → drive awareness and trial purchase
opening_promotion → attract first-time customers
festival_promotion → seasonal campaign conversion
set_meal_promotion → sell package / group-buying offer
generic_promotion → drive purchase or inquiry
brand_or_commercial_poster → improve brand recognition and commercial presentation
```

## 10. Industry Creative Defaults

### 10.1 Beverage

Creative defaults:

```text
bright commercial beverage photography
clean background
fresh light
product centered
ice / fruit / condensation allowed
soft premium color palette
```

Avoid:

```text
messy table
cheap plastic look
fake unreadable text
```

### 10.2 Barbecue

Creative defaults:

```text
appetizing skewers or grilled food
warm night-food mood
clean premium dining environment
controlled smoke or steam
strong food focus
```

Avoid:

```text
dirty smoke
chaotic fire
greasy low-end look
```

### 10.3 Hotpot

Creative defaults:

```text
warm steam
abundant ingredients
rich table setting
modern restaurant mood
clear central food focus
```

Avoid:

```text
outdated festive clutter
overly red cheap poster style
```

### 10.4 Beauty

Creative defaults:

```text
soft premium lighting
gentle color palette
clean hands / product / service detail
simple elegant background
```

Avoid:

```text
medical fear style
messy salon background
cheap overdecorated poster
```

### 10.5 E-Commerce Product

Creative defaults:

```text
clean product hero shot
high contrast product separation
feature-focused composition
platform-friendly square image
premium background
```

Avoid:

```text
unclear product shape
text generated by image model
busy background
```

## 11. Asset Series Defaults

### 11.1 If User Names Platforms

Create one asset per detected platform.

If more than three platforms are detected, cap first-pass output at three assets unless user explicitly asks for a full series.

### 11.2 If User Says “一组” or “系列”

Generate multiple assets.

Minimum:

```text
3 assets
```

### 11.3 If User Asks Single Image

If user says:

```text
一张
单张
one image
```

Generate one primary asset, but still run through V3 planning pipeline.

### 11.4 Default Series

```text
main_poster 4:5
social_cover 4:5
square_product 1:1
```

## 12. Layout Defaults

### 12.1 Poster Layout

Default:

```text
headline: top_center
product_area: center
cta: bottom_right or bottom_center
logo: top_left or bottom_left
reserved_text_regions: top 20%, bottom 20%
```

### 12.2 Delivery / E-Commerce Square Image

Default:

```text
product_area: center_large
feature_tags: left or right side
price_or_offer: bottom area
background: clean, low clutter
```

### 12.3 Store Screen

Default:

```text
headline: left or top
product_area: right or center
cta: bottom
large readable text
```

## 13. Text Rendering Defaults

Poster-like assets:

```text
text_rendering: html_overlay
```

Product-only images:

```text
text_rendering: no_text or html_overlay depending on selling points
```

When exact Chinese text is present in user input:

```text
text_rendering: html_overlay
model should not render final Chinese text
```

Required provider note:

```text
Generate the product / background / atmosphere only. Reserve clean regions for real text overlay. Do not render fake final Chinese text inside the image.
```

## 14. Generation Defaults

V3.0 foundation:

```text
provider_strategy: planning_only
candidate_count: 4
quality_threshold: 0.78
max_refine_rounds: 2
```

V3.1 and later may switch to mock or real generation providers.

## 15. Evaluation Defaults

First-pass mock scores should be deterministic.

Default mock planning score:

```text
aesthetic_score: 0.75
commercial_score: 0.75
brand_consistency_score: 0.70 if temporary brand, 0.78 if persistent brand
layout_score: 0.78 if text regions exist
text_region_score: 0.80 if html_overlay
platform_fit_score: 0.80 if platform ratio matches rules
overall_score: weighted average
recommendation: planning_only
```

## 16. Clarification Defaults

Avoid asking questions by default.

Ask only if:

```text
1. raw input is empty
2. user request is impossible to classify at all and no generic asset can be created
3. user requests exact brand continuation but supplied brand_id is missing and no local default exists
4. required legal / safety / rights issue blocks generation later
```

For V3.0 foundation, case 1 is the only required clarification behavior.

## 17. Rule Versioning

Add a rule version string in metadata:

```text
rules_version: v3.0-foundation-rules-001
```

This allows later rule upgrades without confusing old test outputs.

## 18. Required Tests

Tests should verify:

```text
1. keyword mapping for milk tea / barbecue / hotpot / beauty / ecommerce
2. platform mapping for Xiaohongshu / WeChat / delivery / Taobao / store screen
3. tone mapping for clean / premium / fresh / appetite / tech
4. default series when no platform is specified
5. single-image behavior when user asks for one image
6. text rendering policy for explicit Chinese text
7. rule version appears in metadata
```
