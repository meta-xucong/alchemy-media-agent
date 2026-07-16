# 19 General Creative Quick-Start Presets, UI, and Resolution Specification

> **Doc135 authority:** preset selection may preserve an explicit user control
> or technical canvas requirement, but must not expand into a local creative
> recipe, prompt word stack, text slot or renderer patch.

Source mapping: this is the V3 repository placement of the draft
`17.1_GENERAL_CREATIVE_QUICK_START_PRESETS_SPEC.md`. It is numbered as document
19 here because documents 17 and 18 are already used for the Scenario Pack
platform and General Creative product/runtime specifications.

This document completes the **common-scene image-generation entry layer** for the General Creative product defined in document 18.

It is an additive companion specification. It does not replace, rename, or fork:

```text
the V3 core runtime
the Central Creative Brain
the frozen core schemas
the DefaultCommercialPack
the Scenario Pack Platform
the General Creative job and action runtime
the experimental template-matched mode
```

Its purpose is to close the remaining gap between:

```text
a complete General Creative workspace
```

and:

```text
a complete General Creative landing experience
with familiar, clickable creation scenarios for non-design users
```

The target interaction is:

```text
V3 Scenario Hub
→ General Creative card
→ General Quick-Start Preset Gallery
→ user chooses a familiar creation goal or keeps Free Create
→ UI reveals only relevant optional fields and suggestions
→ user describes the request in natural language
→ backend resolves visible defaults into typed application parameters
→ existing GeneralCreativeScenarioPack
→ DefaultCommercialPack
→ existing Central Creative Brain
→ existing job, candidate, refinement, text-rendering, brand, and export flows
```

The first complete preset catalog defined here includes:

```text
Free Create
Campaign Poster
Product or Service Showcase
Social Media Visual
Website Banner / Hero
Festival or Seasonal Visual
Brand Style Exploration
Knowledge Card / Infographic
Service Package / Price Card
Announcement / Notice
Event Invitation / Registration
Recruitment Poster
```

These are **general commercial creation presets**, not vertical specialization packs.

---

## 1. Document Status, Authority, and Compatibility

### 1.1 Additive Companion Specification

This document is implemented after:

```text
00_ROOT_RULES.md
01_PRODUCT_VISION.md
02_SYSTEM_ARCHITECTURE.md
03_AGENT_AND_MODULE_SPEC.md
07_SCHEMA_CONTRACTS.md
09_RULES_AND_DEFAULTS.md
10_BRAND_MEMORY_SPEC.md
11_EVALUATION_AND_REFINEMENT_SPEC.md
12_PROVIDER_INTERFACES.md
15_PRODUCT_BOUNDARY_AND_VERTICAL_AGENT_ARCHITECTURE.md
17_SCENARIO_PACK_PLATFORM_EXTENSION_SPEC.md
18_GENERAL_CREATIVE_PRODUCT_AND_RUNTIME_SPEC.md
```

It adds only:

```text
a General Creative quick-start preset catalog
preset-driven common-scene UI
preset application DTOs
preset registry and resolution services
preset-to-GeneralCreativeDraft mapping
preset-to-existing CreateCreativeJobRequest mapping
preset version pinning and audit metadata
preset tests and acceptance gates
```

### 1.2 Precedence

If any requirement appears to conflict, use this order:

```text
1. 00_ROOT_RULES.md
2. frozen V3 core schema and provider contracts
3. existing Central Creative Brain behavior
4. 17_SCENARIO_PACK_PLATFORM_EXTENSION_SPEC.md
5. 18_GENERAL_CREATIVE_PRODUCT_AND_RUNTIME_SPEC.md
6. this document
7. future specialization-pack specifications
```

This document may clarify document 18. It may not weaken its invariants.

### 1.3 No Product-Version Renaming

`17.1` is a document sequence label, not a replacement for V3.0, V3.1, V3.2, or later implementation waves.

Implementation phases inside this document use:

```text
Q0, Q1, Q2, Q3, Q4, Q5
```

### 1.4 Required Baseline

Before this work begins, the accepted implementation should provide:

```text
Scenario Hub
General Creative registry card
shared ScenarioWorkspace
GeneralCreativeScenarioPack
DefaultCommercialPack binding
General Creative product modes
GeneralCreativeDraft
CreateCreativeJobRequest
JobApplicationService
job status and event model
candidate selection and regeneration
brand continuation and confirmation
text revision and renderer path
export path
capability-gated UI
```

This document must not be used to hide unfinished document-17 behavior inside preset code.

### 1.5 Required Manifest Version Relationship

Document 17 recommends General Creative pack version `1.1.0`.

After this document is implemented, the built-in General Creative pack should normally advance to:

```text
pack_version: 1.2.0
```

The scenario manifest schema may remain:

```text
manifest_version: 1.0
```

No frozen manifest field needs to be removed or renamed.

---

## 2. Product Objective

A non-design user should not need to translate a business goal into design terminology before using General Creative.

The product should let the user begin from a familiar goal such as:

```text
“做活动海报”
“做产品展示图”
“做公众号或朋友圈配图”
“做官网横幅”
“做一组品牌风格方向”
“做知识卡片”
```

Selecting a preset should:

```text
explain what the preset is for
show a contextual natural-language placeholder
show relevant optional text fields
show relevant upload suggestions
suggest useful ratios and output mode
preserve all user control
keep the existing General Creative runtime unchanged
```

The preset layer must reduce the user's blank-page problem without turning General Creative into a complex form builder.

The primary interaction remains:

```text
natural-language request
```

Preset fields are optional helpers, not a replacement for natural language.

---

## 3. Non-Negotiable Preset Rules

### 3.1 A Quick-Start Preset Is Not a Visual Template

A quick-start preset represents:

```text
creation goal
UI guidance
visible default values
recommended optional inputs
application-level parameter mapping
```

It does not represent:

```text
PSD file
fixed layout file
copied design
provider prompt
model workflow
rendering code
style checkpoint
ControlNet graph
```

### 3.2 A Quick-Start Preset Is Not `template_matched`

The following concepts must remain separate:

```text
Quick-start preset
  = common-scene UI and visible default package

Product mode
  = auto series, single asset, brand continuation, template matched

Visual template
  = future V3-owned, versioned structural/layout asset

Scenario specialization pack
  = industry/channel strategy and policy module
```

Selecting `campaign_poster` must not populate `optional_template_id`.

The experimental `template_matched` mode remains capability-gated under document 18.

### 3.3 Presets Must Remain Policy-Neutral

General presets must not add:

```text
industry-specific strategy
platform-algorithm assumptions
conversion-scoring weights
provider preferences
hidden prompt fragments
model-specific settings
vertical compliance rules
vertical evaluation policy
```

Every General preset still executes through:

```text
GeneralCreativeScenarioPack
→ DefaultCommercialPack
```

`GeneralCreativeScenarioPack.build_policy_bundle(...)` remains empty or baseline-equivalent.

### 3.4 No New Creative Pipeline

Correct:

```text
Preset UI
→ GeneralPresetResolver
→ existing CreateCreativeJobRequest
→ existing JobApplicationService
→ existing ScenarioRuntime
→ existing General Creative path
```

Incorrect:

```text
Campaign Poster preset
→ poster-only generation pipeline

Social Media preset
→ social-only agent pipeline
```

### 3.5 Preset Defaults Are Visible and Overridable

A preset may provide defaults only when:

```text
the value is visible to the user or included in the input summary
the user can override it
the default is applied with set-if-missing semantics
the applied value is auditable
```

A preset must not silently transform the visible request into an unrelated request.

### 3.6 Original User Input Is Immutable

The UI and backend must preserve the exact original natural-language text.

Preset resolution may create:

```text
normalized application parameters
explicit visible constraints
exact-text mappings
asset-role mappings
user-safe input summary
```

It must not overwrite `user_input`.

### 3.7 No Automatic Preset Switching in the First Release

The first release may recommend a preset based on text, but it must not automatically activate or switch a preset after the user starts editing.

Selection sources allowed in the first release:

```text
explicit_ui
deep_link
saved_draft
none
```

Natural-language inference may be added later as a non-binding suggestion.

### 3.8 Preset-Specific Fields Are Optional

Except for the existing required General Creative natural-language input, preset-specific fields must not become blocking requirements in the first release.

The system should still work when the user:

```text
chooses a preset
enters one rough sentence
leaves all helper fields empty
```

### 3.9 No Provider Details in Presets

Preset manifests must not contain:

```text
provider names
model names
samplers
seeds
LoRAs
workflow node ids
raw generation prompts
remote executable URLs
```

### 3.10 Missing Preset Data Must Degrade to Baseline General Creative

If no preset is selected, or `free_create` is selected:

```text
General Creative behavior must remain baseline-equivalent
```

If a non-default preset fails validation before submission:

```text
do not execute the invalid preset
preserve the user's draft
fall back to an explicit no-preset state only after informing the user
```

The backend must never silently replace a requested active preset with a different preset.

---

## 4. Terminology

### 4.1 General Quick-Start Preset

A trusted, declarative, V3-owned package that describes one common creation goal.

Example:

```text
campaign_poster
```

### 4.2 Preset Catalog

The versioned list of available General Creative presets, categories, display ordering, and compatibility metadata.

### 4.3 Preset Field

An optional input exposed only because it is useful for the selected common scene.

Example:

```text
headline
event_time
location
cta
```

### 4.4 Preset Default

A visible, overridable value applied only when the corresponding user-controlled value is absent.

Example:

```text
default mode suggestion = single_asset
```

### 4.5 Preset Selection Record

The application-layer record that pins:

```text
preset id
resolved preset version
catalog version
default checksum
selection source
applied defaults
ignored defaults
user overrides
```

### 4.6 Touched Field

A draft field explicitly modified by the user.

Touched fields must not be overwritten when switching presets.

### 4.7 General Common Scene

A high-frequency commercial visual goal that can be served without industry-specific or platform-specific strategy.

### 4.8 Specialized Scene

A scene that requires domain rules, channel rules, scoring changes, compliance behavior, or a specialized asset recipe.

Examples:

```text
Taobao high-conversion main image
Amazon listing image set
Xiaohongshu seeding cover optimization
WeChat group lifecycle campaign
brand-IP character consistency matrix
```

These belong in future specialization packs, not this catalog.

---

## 5. Scope and Boundaries

### 5.1 In Scope

```text
preset gallery inside General Creative
preset categories and cards
preset detail and contextual examples
preset-specific optional field groups
preset-specific upload suggestions
preset-specific ratio suggestions
preset mode suggestions
preset catalog API
preset registry and validation
preset resolver
preset version pinning
preset-aware draft behavior
preset-aware input summary
preset-aware telemetry
preset tests
```

### 5.2 Out of Scope

```text
fixed visual template library
PSD / Figma / Canva import
automatic template retrieval
third-party template marketplace
arbitrary user-authored form schemas
arbitrary frontend plugins
new core schema fields
new core agents
new provider routes
new evaluation weights
platform-specific e-commerce optimization
short-video generation
vertical social-media strategy
private-community operation strategy
brand-IP consistency strategy
```

### 5.3 Boundary Examples

Allowed in General Creative:

```text
“社交媒体图片” preset
ratio suggestions: 1:1, 4:5, 9:16
optional target-platform selector
```

Not allowed until a New Media specialization pack exists:

```text
Xiaohongshu click-through scoring
Douyin hook strategy
TikTok retention strategy
platform-algorithm heuristics
```

Allowed in General Creative:

```text
“产品或服务展示图” preset
product upload suggestion
selling-point text slots
```

Not allowed until an E-Commerce specialization pack exists:

```text
Taobao main-image conversion rules
Pinduoduo price-density strategy
Amazon image-policy validation
Shopify PDP funnel strategy
```

---

## 6. Target User Experience

### 6.1 Route

The route remains the General Creative route defined in document 18:

```text
/v3/creative-agent/scenarios/general_creative
```

Optional validated deep links:

```text
/v3/creative-agent/scenarios/general_creative?preset=campaign_poster
/v3/creative-agent/scenarios/general_creative?preset=product_service_showcase
```

Unknown or unavailable preset ids must not execute.

The page should preserve the draft and show a non-blocking unavailable message.

### 6.2 Initial Page Order

Recommended order:

```text
1. ScenarioHeader
2. QuickStartPresetGallery
3. GeneralModeSelector
4. NaturalLanguageInput
5. contextual preset helper fields
6. BrandPicker and AssetUploader
7. OptionalQuickControls
8. create action
9. recent compatible jobs / examples
```

On small screens, the gallery may appear as a horizontally scrollable category section, but keyboard and screen-reader access must remain complete.

### 6.3 Natural-Language-First Rule

The preset gallery must not push the main composer below an unreasonable amount of content.

Recommended behavior:

```text
show 6 featured cards initially
show “更多场景” to expand the full catalog
keep the composer visible within the first viewport on common desktop sizes
use a compact two-row card layout
```

### 6.4 Desktop Empty-State Wireframe

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ 通用创作                                                返回场景中心     │
│ 描述你的需求，或先选择一个常见场景                                       │
├──────────────────────────────────────────────────────────────────────────┤
│ 常用场景                                                                 │
│ [自由创作] [活动海报] [产品/服务展示] [社交媒体图片] [Banner] [更多场景] │
├──────────────────────────────────────────────────────────────────────────┤
│ 创作方式： [自动系列] [单张图片] [延续品牌风格]                           │
├──────────────────────────────────────────────────────────────────────────┤
│ 描述你想做什么……                                                         │
│ ┌──────────────────────────────────────────────────────────────────────┐ │
│ │ 帮我做一张咖啡店周末活动海报，突出第二杯半价，年轻、清爽。           │ │
│ └──────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│ 当前场景：活动海报                                                       │
│ [标题] [时间] [地点] [优惠] [行动按钮]   （均为可选）                    │
│                                                                          │
│ [选择品牌] [上传产品/Logo/参考图] [比例：自动] [高级选项]                │
│                                                        [开始创作]       │
└──────────────────────────────────────────────────────────────────────────┘
```

### 6.5 Mobile Empty-State Wireframe

```text
通用创作

常用场景
[自由创作] [活动海报] [产品展示] →

创作方式
[自动系列 ▼]

描述需求
[多行输入框]

活动海报信息（可选）
[标题]
[时间 / 地点]
[优惠 / CTA]

[上传素材]
[选择品牌]
[快速设置]

[开始创作]
```

### 6.6 Selection Interaction

When a user selects a preset:

```text
set selected preset id in the draft
load localized preset detail
apply default mode only if mode is untouched
apply suggested ratio only if ratio is untouched and the preset defines one default
change composer placeholder
show preset-specific optional fields
show preset-specific upload hints
show a concise input summary
keep existing user text, uploads, brand, and touched values
```

### 6.7 Switching Presets

When switching from preset A to preset B:

```text
preserve original user_input
preserve selected brand
preserve uploaded assets
preserve all touched fields
remove only untouched defaults owned by preset A
apply only missing defaults from preset B
move no-longer-relevant touched fields into “其他已填写信息” rather than deleting them
show a warning only when a value cannot be mapped safely
```

### 6.8 Clearing a Preset

Clearing a preset returns to no-preset / Free Create state.

It must:

```text
preserve user_input
preserve uploads
preserve brand selection
preserve explicitly entered exact text
remove only untouched preset defaults
return the contextual placeholder to the General Creative default
```

### 6.9 Mode and Preset Relationship

The mode selector and preset gallery are independent controls.

Rules:

```text
explicit user-selected mode wins
preset default mode applies only when mode is untouched
preset switch must not overwrite an explicitly selected mode
mode incompatibility must be explained before submission
```

Example:

```text
preset = campaign_poster
preset default mode = single_asset
user explicitly chooses auto_commercial_series
result = auto_commercial_series
```

### 6.10 Result Workspace

After submission, the result workspace remains exactly the shared General Creative workspace defined in document 18.

Preset-specific changes are limited to:

```text
human-readable job summary
preset badge in metadata
contextual asset naming suggestions
contextual empty / retry copy
```

The preset must not replace:

```text
AssetSeriesViewer
CandidateSelector
RegenerateDialog
TextRevisionPanel
ContinueStyleDialog
BrandSaveDialog
ExportDialog
```

---

## 7. Catalog Structure and Categories

### 7.1 Required Categories

The first catalog should provide these stable category ids:

```text
recommended
promotion
showcase
content
brand
business_information
```

Localized display labels are UI data.

The UI may show an additional virtual category:

```text
all
```

`all` is computed by the frontend or catalog service. It is not required on each preset.

### 7.2 Initial Active Presets

| Preset id | Chinese label | Category | Default mode suggestion | Primary output intent |
|---|---|---|---|---|
| `free_create` | 自由创作 | recommended | `auto_commercial_series` | baseline General Creative |
| `campaign_poster` | 活动海报 | promotion | `single_asset` | one promotional poster |
| `product_service_showcase` | 产品 / 服务展示 | showcase | `auto_commercial_series` | coordinated showcase visuals |
| `social_media_visual` | 社交媒体图片 | content | `auto_commercial_series` | generic social images |
| `web_banner_hero` | Banner / 官网头图 | showcase | `single_asset` | horizontal hero or banner |
| `festival_seasonal_visual` | 节日 / 节气营销图 | promotion | `auto_commercial_series` | seasonal campaign visuals |
| `brand_style_exploration` | 品牌风格探索 | brand | `auto_commercial_series` | several visual directions |
| `knowledge_card_infographic` | 知识卡片 / 信息图 | content | `auto_commercial_series` | structured information cards |
| `service_package_price_card` | 服务套餐 / 价目卡 | business_information | `single_asset` | readable offer or price card |
| `announcement_notice` | 通知 / 公告图 | business_information | `single_asset` | clear announcement visual |
| `event_invitation_registration` | 活动邀请 / 报名图 | promotion | `single_asset` | invitation or registration image |
| `recruitment_poster` | 招聘海报 | business_information | `single_asset` | recruitment communication visual |

### 7.3 Card Ordering

Recommended default order:

```text
1. free_create
2. campaign_poster
3. product_service_showcase
4. social_media_visual
5. festival_seasonal_visual
6. web_banner_hero
7. brand_style_exploration
8. knowledge_card_infographic
9. service_package_price_card
10. announcement_notice
11. event_invitation_registration
12. recruitment_poster
```

Ordering is catalog-driven and may be changed without editing the gallery component.

---

## 8. Preset Definitions

All fields below are optional helpers unless explicitly stated otherwise.

The existing General Creative `user_input` remains required.

### 8.1 `free_create`

Purpose:

```text
Use baseline General Creative without a common-scene assumption.
```

Defaults:

```text
default mode suggestion: auto_commercial_series
requested output: baseline mode mapping
ratio: auto
platform: auto
```

Suggested assets:

```text
none
```

Contextual placeholder:

```text
描述你的业务目标、想做的图片、风格、使用场景和必须出现的文字。
```

Boundary:

```text
must be output-equivalent to no preset selected
```

### 8.2 `campaign_poster`

Purpose:

```text
General promotional poster for an event, opening, offer, launch, class,
exhibition, store activity, or campaign.
```

Default mode suggestion:

```text
single_asset
```

Suggested ratios:

```text
3:4
4:5
9:16
1:1
```

Optional fields:

```text
headline
event_name
subtitle
event_time
location
offer
cta
footnote
```

Suggested asset purposes:

```text
logo
product_photo
store_photo
preferred_style_reference
```

Contextual placeholder:

```text
例如：帮我做一张咖啡店周末活动海报，突出第二杯半价，年轻、清爽，适合朋友圈。
```

General boundary:

```text
no platform-specific CTR rules
no industry-specific conversion rules
```

### 8.3 `product_service_showcase`

Purpose:

```text
Show a product, service, package, solution, or business offering clearly.
```

Default mode suggestion:

```text
auto_commercial_series
```

Suggested ratios:

```text
1:1
4:5
16:9
3:4
```

Optional fields:

```text
product_or_service_name
headline
selling_points
price
offer
cta
supporting_note
```

Suggested asset purposes:

```text
product_photo
logo
store_photo
preferred_style_reference
```

Contextual placeholder:

```text
例如：帮我做一组家政深度清洁服务展示图，突出专业、安心和透明收费。
```

General boundary:

```text
not a Taobao/Pinduoduo/Amazon/Shopify listing optimizer
no e-commerce platform policy validation
```

### 8.4 `social_media_visual`

Purpose:

```text
Create generic social-media covers or post images for broad communication needs.
```

Default mode suggestion:

```text
auto_commercial_series
```

Suggested ratios:

```text
1:1
4:5
9:16
3:4
```

Optional fields:

```text
topic
headline
subtitle
key_points
cta
account_or_brand_name
```

Suggested asset purposes:

```text
logo
product_photo
preferred_style_reference
previous_poster
```

Contextual placeholder:

```text
例如：帮我做一组关于夏季护肤小贴士的社交媒体图片，干净、轻松、可信。
```

General boundary:

```text
may accept a target platform as a normal General Creative control
must not add algorithm-specific hooks, engagement scoring, or platform content strategy
```

### 8.5 `web_banner_hero`

Purpose:

```text
Create a horizontal website hero, landing-page header, or broad banner.
```

Default mode suggestion:

```text
single_asset
```

Suggested ratios:

```text
16:9
21:9
3:1
2:1
```

Optional fields:

```text
headline
subtitle
cta
supporting_note
safe_text_side
```

Suggested asset purposes:

```text
product_photo
logo
preferred_style_reference
```

Contextual placeholder:

```text
例如：帮我做一张官网首页横幅，介绍我们的企业 AI 培训服务，专业但不要沉闷。
```

General boundary:

```text
safe_text_side is a user-facing layout preference, not a provider parameter
```

### 8.6 `festival_seasonal_visual`

Purpose:

```text
Create general festival, seasonal, anniversary, or calendar-event visuals.
```

Default mode suggestion:

```text
auto_commercial_series
```

Suggested ratios:

```text
1:1
4:5
9:16
3:4
16:9
```

Optional fields:

```text
occasion_name
headline
blessing_or_message
offer
cta
date_or_period
```

Suggested asset purposes:

```text
logo
product_photo
preferred_style_reference
previous_poster
```

Contextual placeholder:

```text
例如：帮我做一组端午节品牌祝福图，雅致、现代，保留品牌蓝色。
```

General boundary:

```text
festival selection supplies context only
it does not imply a channel-specific promotion strategy
```

### 8.7 `brand_style_exploration`

Purpose:

```text
Explore several general visual directions before establishing or updating a brand style.
```

Default mode suggestion:

```text
auto_commercial_series
```

Suggested ratios:

```text
1:1
4:5
16:9
```

Optional fields:

```text
brand_or_business_name
business_description
target_audience
brand_traits
preferred_colors
avoid_directions
direction_count
```

Suggested default:

```text
direction_count = 3
```

Suggested asset purposes:

```text
logo
product_photo
brand_color_reference
preferred_style_reference
```

Contextual placeholder:

```text
例如：为一家新的精品咖啡品牌探索三种视觉方向，要年轻、克制、有品质感。
```

Required behavior:

```text
the direction-count default is visible and editable
saving any direction to persistent brand memory still requires document-17 confirmation
```

General boundary:

```text
not a Brand IP Operations pack
no character bible, world-building system, or long-term IP content matrix
```

### 8.8 `knowledge_card_infographic`

Purpose:

```text
Turn structured information into readable knowledge cards, lists, steps, comparisons,
or simple infographics.
```

Default mode suggestion:

```text
auto_commercial_series
```

Suggested ratios:

```text
3:4
4:5
1:1
9:16
```

Optional fields:

```text
title
intro
key_points
steps
comparison_items
source_note
cta
```

Suggested asset purposes:

```text
logo
preferred_style_reference
other_reference
```

Contextual placeholder:

```text
例如：把“第一次露营的五项准备”做成一组清晰、轻松的知识卡片。
```

Required behavior:

```text
exact text must remain editable through the document-17 renderer flow
long content must be summarized or split visibly rather than silently truncated
```

General boundary:

```text
no factual verification claim is implied by selecting this preset
user-supplied facts remain user-supplied content
```

### 8.9 `service_package_price_card`

Purpose:

```text
Create a readable service package, offer list, membership card, or price card.
```

Default mode suggestion:

```text
single_asset
```

Suggested ratios:

```text
3:4
4:5
1:1
9:16
```

Optional fields:

```text
headline
package_lines
offer
validity_period
cta
terms_note
```

Suggested asset purposes:

```text
logo
store_photo
preferred_style_reference
```

Contextual placeholder:

```text
例如：帮我做一张美甲店开业套餐价目卡，三档套餐，价格清楚、年轻但不廉价。
```

Required behavior:

```text
price and package text should use exact-text slots when supplied
text-only corrections use RenderRevision instead of image regeneration
```

General boundary:

```text
no vertical pricing strategy or local-platform promotion policy
```

### 8.10 `announcement_notice`

Purpose:

```text
Create a clear announcement, schedule notice, closure notice, update, or public-information image.
```

Default mode suggestion:

```text
single_asset
```

Suggested ratios:

```text
1:1
3:4
4:5
16:9
```

Optional fields:

```text
headline
announcement_body
effective_date
time_period
contact
footnote
```

Suggested asset purposes:

```text
logo
store_photo
preferred_style_reference
```

Contextual placeholder:

```text
例如：帮我做一张门店临时调整营业时间的通知图，信息清楚、语气友好。
```

Required behavior:

```text
clarity and exact text are user-visible requirements
no hidden emergency or legal interpretation is added
```

### 8.11 `event_invitation_registration`

Purpose:

```text
Create an invitation, event registration image, webinar notice, or attendance reminder.
```

Default mode suggestion:

```text
single_asset
```

Suggested ratios:

```text
3:4
4:5
9:16
1:1
```

Optional fields:

```text
event_name
headline
event_time
location_or_online_link
host
registration_instruction
cta
capacity_or_deadline
```

Suggested asset purposes:

```text
logo
store_photo
other_reference
preferred_style_reference
```

Contextual placeholder:

```text
例如：帮我做一张线下读书会邀请图，周六下午三点，温暖、安静，预留报名二维码位置。
```

Required behavior:

```text
uploaded QR code is treated as a user-owned reference/overlay asset
system must not fabricate a working QR destination
```

### 8.12 `recruitment_poster`

Purpose:

```text
Create a general recruitment or hiring communication image.
```

Default mode suggestion:

```text
single_asset
```

Suggested ratios:

```text
3:4
4:5
9:16
1:1
```

Optional fields:

```text
company_or_brand_name
role_title
location
employment_type
role_highlights
requirements
compensation_note
contact_or_application
```

Suggested asset purposes:

```text
logo
store_photo
other_reference
preferred_style_reference
```

Contextual placeholder:

```text
例如：帮我做一张咖啡师招聘海报，强调培训、友好团队和成长空间，简洁有活力。
```

General boundary:

```text
no legal-compliance guarantee
no inferred protected-class targeting
all employment claims remain user-provided content
```

---


### 8.13 Normative Field-Mapping Matrix

This matrix freezes the first-release field ids, component types, and application target paths.

A future compatible preset revision may add optional fields. It must not silently change the semantic meaning of an existing field id.

Common mapping rules:

```text
text values preserve the user's exact Unicode content
textarea values preserve original text and line breaks
context.* values remain structured application context
exact_text.* values enter the existing exact-text/rendering flow
controls.* values enter existing General Creative quick controls
asset roles resolve only to document-17 upload purposes
```

#### `free_create`

```text
No preset-specific fields.
```

#### `campaign_poster`

| Field id | Type | Target path | Suggested limit | Meaning |
|---|---|---|---:|---|
| `headline` | text | `exact_text.headline` | 80 | primary poster headline |
| `event_name` | text | `context.event_name` | 100 | event or campaign name |
| `subtitle` | text | `exact_text.subtitle` | 120 | supporting line |
| `event_time` | text | `exact_text.event_time` | 80 | date/time shown on output |
| `location` | text | `exact_text.location` | 120 | venue or applicable location |
| `offer` | text | `exact_text.offer` | 100 | promotion or benefit |
| `cta` | text | `exact_text.cta` | 40 | action phrase |
| `footnote` | text | `exact_text.footnote` | 180 | terms or small-print note |

#### `product_service_showcase`

| Field id | Type | Target path | Suggested limit | Meaning |
|---|---|---|---:|---|
| `product_or_service_name` | text | `context.product_or_service_name` | 120 | offering identity |
| `headline` | text | `exact_text.headline` | 80 | primary display headline |
| `selling_points` | textarea | `context.selling_points` | 600 | user-supplied feature/benefit points |
| `price` | text | `exact_text.price` | 60 | exact price when required |
| `offer` | text | `exact_text.offer` | 100 | offer or promotion |
| `cta` | text | `exact_text.cta` | 40 | action phrase |
| `supporting_note` | text | `exact_text.footnote` | 180 | support or terms note |

#### `social_media_visual`

| Field id | Type | Target path | Suggested limit | Meaning |
|---|---|---|---:|---|
| `topic` | text | `context.topic` | 120 | content topic |
| `headline` | text | `exact_text.headline` | 80 | cover or post headline |
| `subtitle` | text | `exact_text.subtitle` | 120 | supporting line |
| `key_points` | textarea | `context.key_points` | 800 | points to communicate |
| `cta` | text | `exact_text.cta` | 40 | optional action phrase |
| `account_or_brand_name` | text | `exact_text.account_or_brand_name` | 80 | optional account or brand signature |

#### `web_banner_hero`

| Field id | Type | Target path | Suggested limit | Meaning |
|---|---|---|---:|---|
| `headline` | text | `exact_text.headline` | 80 | primary hero headline |
| `subtitle` | text | `exact_text.subtitle` | 140 | supporting proposition |
| `cta` | text | `exact_text.cta` | 40 | primary action phrase |
| `supporting_note` | text | `exact_text.footnote` | 180 | optional note |
| `safe_text_side` | select | `context.safe_text_side` | n/a | `auto`, `left`, or `right` layout preference |

Allowed `safe_text_side` options:

```text
auto
left
right
```

#### `festival_seasonal_visual`

| Field id | Type | Target path | Suggested limit | Meaning |
|---|---|---|---:|---|
| `occasion_name` | text | `context.occasion_name` | 80 | festival, season, anniversary, or date marker |
| `headline` | text | `exact_text.headline` | 80 | campaign headline |
| `blessing_or_message` | text | `exact_text.message` | 160 | greeting or seasonal message |
| `offer` | text | `exact_text.offer` | 100 | optional promotion |
| `cta` | text | `exact_text.cta` | 40 | optional action phrase |
| `date_or_period` | text | `exact_text.date_or_period` | 80 | applicable date range |

#### `brand_style_exploration`

| Field id | Type | Target path | Suggested limit | Meaning |
|---|---|---|---:|---|
| `brand_or_business_name` | text | `context.brand_or_business_name` | 100 | brand identity |
| `business_description` | textarea | `context.business_description` | 600 | business and offering summary |
| `target_audience` | textarea | `context.target_audience` | 400 | intended audience |
| `brand_traits` | textarea | `context.brand_traits` | 400 | desired personality and tone |
| `preferred_colors` | text | `context.preferred_colors` | 160 | user preference, not a forced palette |
| `avoid_directions` | textarea | `controls.negative_directions` | 400 | visible directions to avoid |
| `direction_count` | select | `context.direction_count` | n/a | number of visual directions |

Allowed first-release `direction_count` options:

```text
2
3
4
```

Default:

```text
3
```

#### `knowledge_card_infographic`

| Field id | Type | Target path | Suggested limit | Meaning |
|---|---|---|---:|---|
| `title` | text | `exact_text.headline` | 100 | card-set title |
| `intro` | text | `exact_text.subtitle` | 180 | introductory line |
| `key_points` | textarea | `context.key_points` | 1600 | facts or points supplied by the user |
| `steps` | textarea | `context.steps` | 1600 | ordered steps supplied by the user |
| `comparison_items` | textarea | `context.comparison_items` | 1600 | comparison content supplied by the user |
| `source_note` | text | `exact_text.footnote` | 240 | optional source or disclaimer |
| `cta` | text | `exact_text.cta` | 40 | optional action phrase |

At least one of `key_points`, `steps`, or `comparison_items` should normally be present, but the first release should warn rather than block when the natural-language request already contains sufficient information.

#### `service_package_price_card`

| Field id | Type | Target path | Suggested limit | Meaning |
|---|---|---|---:|---|
| `headline` | text | `exact_text.headline` | 80 | price-card headline |
| `package_lines` | textarea | `exact_text.package_lines` | 1600 | exact package names, inclusions, and prices |
| `offer` | text | `exact_text.offer` | 100 | optional promotion |
| `validity_period` | text | `exact_text.validity_period` | 100 | offer validity |
| `cta` | text | `exact_text.cta` | 40 | action phrase |
| `terms_note` | text | `exact_text.footnote` | 240 | terms or exclusions |

`package_lines` must preserve line order and exact price strings.

#### `announcement_notice`

| Field id | Type | Target path | Suggested limit | Meaning |
|---|---|---|---:|---|
| `headline` | text | `exact_text.headline` | 100 | notice headline |
| `announcement_body` | textarea | `exact_text.body` | 1000 | exact notice content |
| `effective_date` | text | `exact_text.effective_date` | 80 | effective date |
| `time_period` | text | `exact_text.time_period` | 100 | business hours or applicable period |
| `contact` | text | `exact_text.contact` | 120 | contact information |
| `footnote` | text | `exact_text.footnote` | 240 | optional note |

#### `event_invitation_registration`

| Field id | Type | Target path | Suggested limit | Meaning |
|---|---|---|---:|---|
| `event_name` | text | `context.event_name` | 120 | event identity |
| `headline` | text | `exact_text.headline` | 100 | invitation headline |
| `event_time` | text | `exact_text.event_time` | 100 | exact date and time |
| `location_or_online_link` | text | `exact_text.location_or_link` | 200 | venue or user-supplied online address |
| `host` | text | `exact_text.host` | 120 | organizer or host |
| `registration_instruction` | textarea | `exact_text.registration_instruction` | 500 | registration steps |
| `cta` | text | `exact_text.cta` | 40 | action phrase |
| `capacity_or_deadline` | text | `exact_text.capacity_or_deadline` | 100 | capacity or deadline |

Asset semantics:

```text
host, venue, and QR-code images are uploaded through the existing
other_reference or store_photo purpose and labeled in preset field metadata
```

#### `recruitment_poster`

| Field id | Type | Target path | Suggested limit | Meaning |
|---|---|---|---:|---|
| `company_or_brand_name` | text | `exact_text.company_or_brand_name` | 100 | employer identity |
| `role_title` | text | `exact_text.headline` | 100 | role being recruited |
| `location` | text | `exact_text.location` | 120 | work location |
| `employment_type` | text | `exact_text.employment_type` | 80 | full-time, part-time, internship, or user wording |
| `role_highlights` | textarea | `context.role_highlights` | 800 | opportunity highlights |
| `requirements` | textarea | `context.requirements` | 1000 | user-supplied requirements |
| `compensation_note` | text | `exact_text.offer` | 120 | compensation or benefits wording |
| `contact_or_application` | text | `exact_text.contact` | 160 | application method |

Asset semantics:

```text
workplace and team images use store_photo or other_reference
```

### 8.14 Field-Value Normalization Rules

```text
1. Preserve the raw submitted value for audit and edit restoration.
2. Normalize only whitespace required by existing application validation.
3. Keep exact_text values in their original language.
4. For context textareas, the resolver may derive a list from line breaks,
   but it must keep the original textarea value in the application snapshot.
5. Empty optional fields are omitted rather than serialized as creative facts.
6. Select values must come from the preset manifest's options.
7. A preset cannot make a field required unless a future compatible product
   decision explicitly changes the first-release optional-field rule.
```

### 8.15 Initial Supported-Mode Matrix

| Preset | Auto series | Single asset | Brand continuation | Template matched |
|---|---:|---:|---:|---:|
| `free_create` | yes | yes | yes | capability-gated outside preset defaults |
| `campaign_poster` | yes | yes | yes | capability-gated outside preset defaults |
| `product_service_showcase` | yes | yes | yes | capability-gated outside preset defaults |
| `social_media_visual` | yes | yes | yes | capability-gated outside preset defaults |
| `web_banner_hero` | yes | yes | yes | capability-gated outside preset defaults |
| `festival_seasonal_visual` | yes | yes | yes | capability-gated outside preset defaults |
| `brand_style_exploration` | yes | yes | yes | capability-gated outside preset defaults |
| `knowledge_card_infographic` | yes | yes | yes | capability-gated outside preset defaults |
| `service_package_price_card` | yes | yes | yes | capability-gated outside preset defaults |
| `announcement_notice` | yes | yes | yes | capability-gated outside preset defaults |
| `event_invitation_registration` | yes | yes | yes | capability-gated outside preset defaults |
| `recruitment_poster` | yes | yes | yes | capability-gated outside preset defaults |

`template_matched` is never activated merely because a quick-start preset is selected.

---

## 9. Preset Contract Models

These are additive application/UI contracts.

They are not frozen core creative schemas.

### 9.1 `GeneralQuickStartPresetManifest`

Recommended model:

```python
class GeneralQuickStartPresetManifest(BaseModel):
    schema_version: str = "1.0"

    preset_id: str
    preset_version: str
    status: str = "active"

    display_name: dict[str, str]
    description: dict[str, str] = Field(default_factory=dict)
    category_id: str

    card_icon: str | None = None
    card_image_asset: str | None = None
    card_order: int = 100
    featured: bool = False

    default_mode_id: str | None = None
    supported_mode_ids: list[str] = Field(default_factory=list)
    default_requested_output: str | None = None

    composer_placeholder: dict[str, str] = Field(default_factory=dict)
    example_prompts: list[dict[str, str]] = Field(default_factory=list)

    fields: list[GeneralPresetFieldSpec] = Field(default_factory=list)
    suggested_asset_purposes: list[str] = Field(default_factory=list)
    suggested_aspect_ratios: list[str] = Field(default_factory=list)

    default_parameters: dict = Field(default_factory=dict)
    result_label_hints: dict[str, dict[str, str]] = Field(default_factory=dict)

    compatibility: GeneralPresetCompatibility
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
```

Rules:

```text
preset_id is stable lowercase snake_case
preset_version follows semantic versioning
schema_version is validated independently
card_image_asset resolves only from a V3-owned asset root
all target paths use an allowlist
all field ids are unique inside the preset
all mode ids exist in the active General Creative manifest
all asset purposes use the V3 upload-purpose allowlist
all ratio values pass V3 ratio validation
```

### 9.2 `GeneralPresetFieldSpec`

```python
class GeneralPresetFieldSpec(BaseModel):
    field_id: str
    field_type: str

    label: dict[str, str]
    description: dict[str, str] = Field(default_factory=dict)
    placeholder: dict[str, str] = Field(default_factory=dict)

    target_path: str
    semantic_role: str

    required: bool = False
    default_value: object | None = None
    options: list[dict] = Field(default_factory=list)

    max_length: int | None = None
    max_items: int | None = None
    visible_when: dict = Field(default_factory=dict)

    metadata: dict = Field(default_factory=dict)
```

First-pass field types must use the V3-owned component whitelist:

```text
text
textarea
select
multi_select
toggle
asset_upload
reference_asset_picker
```

Recommended target-path allowlist:

```text
exact_text.<slot>
context.<key>
controls.target_platforms
controls.aspect_ratio
controls.negative_directions
assets.<purpose>
```

A manifest must not target:

```text
provider payloads
raw prompts
core-agent internals
filesystem paths
network destinations
arbitrary object paths
```

### 9.3 `GeneralPresetCompatibility`

```python
class GeneralPresetCompatibility(BaseModel):
    general_pack_min: str
    general_pack_max_exclusive: str | None = None
    catalog_schema_versions: list[str] = Field(default_factory=lambda: ["1.0"])
    required_capabilities: list[str] = Field(default_factory=list)
    optional_capabilities: list[str] = Field(default_factory=list)
```

### 9.4 `GeneralPresetCategory`

```python
class GeneralPresetCategory(BaseModel):
    category_id: str
    display_name: dict[str, str]
    order: int = 100
    visible: bool = True
```

### 9.5 `GeneralPresetCatalogView`

```python
class GeneralPresetCatalogView(BaseModel):
    catalog_schema_version: str = "1.0"
    catalog_version: str

    pack_id: str = "general_creative"
    pack_version: str

    default_preset_id: str | None = None
    categories: list[GeneralPresetCategory]
    presets: list[GeneralQuickStartPresetManifest]

    locale: str
    etag: str | None = None
    generated_at: datetime | None = None

    warnings: list[str] = Field(default_factory=list)
```

### 9.6 `PresetSelectionRecord`

```python
class PresetSelectionRecord(BaseModel):
    preset_id: str
    requested_preset_version: str | None = None
    resolved_preset_version: str

    catalog_version: str
    selection_source: str

    defaults_checksum: str
    applied_default_paths: list[str] = Field(default_factory=list)
    ignored_default_paths: list[str] = Field(default_factory=list)
    user_override_paths: list[str] = Field(default_factory=list)

    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
```

Recommended selection sources:

```text
explicit_ui
deep_link
saved_draft
api
```

### 9.7 `PresetApplicationResult`

```python
class PresetApplicationResult(BaseModel):
    selection: PresetSelectionRecord | None = None

    resolved_mode_id: str
    requested_output: str

    scenario_parameters: dict = Field(default_factory=dict)
    explicit_constraints: list[str] = Field(default_factory=list)
    exact_text: dict[str, str] = Field(default_factory=dict)
    asset_role_bindings: dict[str, list[str]] = Field(default_factory=dict)

    input_summary: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
```

This model is application-layer output.

It is converted into the existing document-17 request and application objects.

---

## 10. General Creative Draft Extension

Document 17 defines `GeneralCreativeDraft` as a frontend-local, non-core model.

It may be extended additively:

```python
class GeneralCreativeDraft(BaseModel):
    mode_id: str = "auto_commercial_series"
    user_input: str = ""

    optional_brand_id: str | None = None
    optional_template_id: str | None = None
    uploaded_asset_ids: list[str] = Field(default_factory=list)

    target_platforms: list[str] = Field(default_factory=list)
    aspect_ratio: str | None = None
    exact_text: dict[str, str] = Field(default_factory=dict)
    negative_directions: list[str] = Field(default_factory=list)

    quick_start_preset_id: str | None = None
    quick_start_requested_version: str | None = None
    quick_start_field_values: dict = Field(default_factory=dict)
    quick_start_touched_paths: list[str] = Field(default_factory=list)

    metadata: dict = Field(default_factory=dict)
```

### 10.1 Client Trust Boundary

The client may submit:

```text
preset id
requested preset version
field values
explicit touched/override paths
```

The client must not be trusted to submit:

```text
resolved preset defaults
resolved checksum
capability result
compatibility result
server-owned catalog version
```

The backend reloads and resolves the preset from its trusted catalog.

### 10.2 Backward Compatibility

A draft without quick-start fields remains valid.

A legacy create-job request without a preset remains valid.

No preset must be required by the API.

---

## 11. Preset Resolution and Merge Semantics

### 11.1 Resolution Flow

```text
GeneralCreativeDraft
→ validate General Creative mode
→ resolve requested preset from trusted catalog
→ validate preset status and compatibility
→ validate preset field values
→ resolve mode suggestion only when mode is untouched
→ resolve default parameters with set-if-missing semantics
→ map exact-text fields
→ map context fields
→ map asset roles
→ produce user-safe input summary
→ produce existing CreateCreativeJobRequest
```

### 11.2 Required Precedence

This document inserts preset defaults into document 18's existing precedence without changing higher-priority rules:

```text
1. safety, rights, legal, and hard product constraints
2. explicit UI controls and explicit preset-field values entered by the user
3. explicit natural-language constraints
4. persistent brand constraints
5. visible untouched preset defaults
6. existing General Creative inferred defaults
```

### 11.3 Default Operation

All preset defaults use:

```text
set_if_missing
```

They may not use:

```text
forced_replace
hidden_append_to_prompt
provider_override
```

### 11.4 User-Selected Mode Wins

Mode resolution:

```text
1. explicit user-selected mode
2. persisted touched mode in a saved draft
3. selected preset default_mode_id
4. document-17 default mode
```

### 11.5 Natural-Language Conflict

Example:

```text
preset = campaign_poster
untouched preset default = single_asset
user_input = “帮我做一组三张活动图”
```

Recommended behavior:

```text
natural-language request for a series wins over untouched preset default
resolved mode = auto_commercial_series when existing intent rules support it
record preset_default_ignored_due_to_explicit_user_intent
show summary before or immediately after submission
```

If the user explicitly selected `single_asset`, the explicit mode wins and the conflict is recorded according to document 18.

### 11.6 Exact Text Mapping

Preset fields that target `exact_text.<slot>` map into the existing `exact_text` dictionary.

Rules:

```text
preserve Unicode exactly
trim only according to existing text-field rules
never translate automatically
never paraphrase exact text
validate maximum length
allow renderer overflow handling under document 18
```

### 11.7 Context Mapping

Fields that target `context.<key>` map into:

```text
request.scenario_selection.parameters.general_quick_start.context
```

The application service may convert confirmed values into visible structured constraints accepted by the existing core request boundary.

It must not directly edit PromptCompilationResult or provider prompts.

### 11.8 Asset Role Mapping

Uploaded assets remain owned by the existing UploadService.

Preset role mapping stores only validated associations:

```text
upload id → logical asset purpose
```

No preset may access arbitrary files or remote URLs.

### 11.9 `free_create` Resolution

`free_create` returns:

```text
empty preset-specific context
no required field mapping
no hidden constraints
baseline-equivalent defaults
```

A regression test must prove that:

```text
no preset
```

and:

```text
free_create with no user overrides
```

produce equivalent core inputs and outputs, excluding approved preset audit metadata.

### 11.10 Failure Behavior

| Failure | Required behavior |
|---|---|
| unknown preset id | `preset_not_found`; preserve draft |
| incompatible preset version | `preset_incompatible`; do not execute requested preset |
| disabled/deprecated preset for new job | explain unavailable; offer Free Create |
| invalid field path | registry validation failure; preset not activated |
| invalid field value | field-level validation error |
| unavailable optional capability | hide or degrade affected field; keep preset usable where safe |
| catalog unavailable | General Creative remains usable without preset gallery only when General pack itself is healthy |

The catalog being unavailable must not create a second product route.

---

## 12. Create-Job Mapping

### 12.1 Request Shape

Use the existing document-17 request.

Add preset data inside `scenario_selection.parameters` and normal metadata only.

Example:

```json
{
  "user_input": "帮我做一张咖啡店周末活动海报，突出第二杯半价，年轻、清爽。",
  "optional_brand_id": "brand_123",
  "optional_template_id": null,
  "uploaded_asset_ids": [
    "upload_logo",
    "upload_drink"
  ],
  "explicit_constraints": [
    "必须保留产品杯身外观"
  ],
  "scenario_selection": {
    "pack_id": "general_creative",
    "mode_id": "single_asset",
    "source": "explicit_ui",
    "parameters": {
      "target_platforms": ["wechat_moments"],
      "aspect_ratio": "4:5",
      "exact_text": {
        "headline": "周末限定",
        "offer": "第二杯半价",
        "cta": "到店尝鲜"
      },
      "general_quick_start": {
        "preset_id": "campaign_poster",
        "requested_preset_version": "1.0.0",
        "field_values": {
          "event_time": "本周六至周日",
          "location": "全门店"
        },
        "user_override_paths": [
          "controls.aspect_ratio",
          "exact_text.headline",
          "exact_text.offer",
          "exact_text.cta"
        ]
      }
    },
    "allow_general_fallback": false
  },
  "metadata": {
    "client": "v3_web",
    "draft_version": "2",
    "preset_catalog_seen": "1.0.0"
  }
}
```

### 12.2 Server-Resolved Metadata

The client request must not be treated as the final audit record.

The backend adds server-owned metadata:

```json
{
  "general_quick_start": {
    "preset_id": "campaign_poster",
    "resolved_preset_version": "1.0.0",
    "catalog_version": "1.0.0",
    "selection_source": "explicit_ui",
    "defaults_checksum": "sha256:...",
    "applied_default_paths": [
      "mode_id"
    ],
    "ignored_default_paths": [],
    "user_override_paths": [
      "controls.aspect_ratio",
      "exact_text.headline",
      "exact_text.offer",
      "exact_text.cta"
    ]
  }
}
```

### 12.3 Job View

The application-level `JobView` may add an optional safe view:

```python
class GeneralQuickStartView(BaseModel):
    preset_id: str
    preset_version: str
    display_name: str
    category_id: str
    selection_source: str
    applied_defaults: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
```

Historical display must use the stored preset snapshot or localized fallback label.

It must not require the current catalog entry to remain active.

---

## 13. Backend Services

### 13.1 `GeneralPresetCatalogService`

Responsibilities:

```text
load built-in preset manifests
validate schema
validate ids and versions
validate mode references
validate target-path allowlist
validate asset-purpose allowlist
validate capabilities
filter by status and feature flag
localize views
produce ETag/checksum
return deterministic ordering
```

Must not:

```text
call creative agents
call providers
edit prompts
store user state
```

### 13.2 `GeneralPresetResolver`

Responsibilities:

```text
resolve one trusted preset
validate submitted field values
merge visible defaults
map fields to existing request locations
record applied and ignored defaults
produce PresetApplicationResult
```

Must be:

```text
deterministic
pure where practical
offline-testable
free of provider calls
```

### 13.3 `GeneralPresetDraftMapper`

Frontend or shared UI responsibility:

```text
apply preset to draft
track touched fields
remove only preset-owned untouched defaults
preserve user-entered values
```

The backend remains authoritative.

### 13.4 `GeneralPresetSnapshotService`

Recommended responsibility:

```text
store the minimum manifest snapshot needed to render historical jobs
```

Minimum snapshot:

```text
preset id
preset version
display name by supported locale
category id
default checksum
field ids used by the job
```

Do not copy executable or unnecessary catalog data into every job.

---

## 14. API Routes

All routes remain inside the V3-owned API namespace.

### 14.1 Catalog Routes

Recommended:

```text
GET /api/v3/creative-agent/scenario-packs/general_creative/presets
GET /api/v3/creative-agent/scenario-packs/general_creative/presets/{preset_id}
```

Optional generic shape for later pack reuse:

```text
GET /api/v3/creative-agent/scenario-packs/{pack_id}/quick-start-presets
```

Do not implement both forms unless the route strategy is intentionally standardized.

### 14.2 Query Parameters

Supported first pass:

```text
locale
category
include_experimental=false
```

The backend filters inactive or incompatible entries.

### 14.3 Catalog Response Example

```json
{
  "catalog_schema_version": "1.0",
  "catalog_version": "1.0.0",
  "pack_id": "general_creative",
  "pack_version": "1.2.0",
  "default_preset_id": null,
  "locale": "zh-CN",
  "categories": [
    {
      "category_id": "recommended",
      "display_name": {
        "zh-CN": "常用",
        "en-US": "Recommended"
      },
      "order": 10,
      "visible": true
    }
  ],
  "presets": [
    {
      "schema_version": "1.0",
      "preset_id": "campaign_poster",
      "preset_version": "1.0.0",
      "status": "active",
      "display_name": {
        "zh-CN": "活动海报",
        "en-US": "Campaign Poster"
      },
      "category_id": "promotion",
      "card_icon": "poster",
      "card_order": 20,
      "featured": true,
      "default_mode_id": "single_asset",
      "supported_mode_ids": [
        "single_asset",
        "auto_commercial_series",
        "brand_continuation"
      ],
      "suggested_aspect_ratios": [
        "3:4",
        "4:5",
        "9:16",
        "1:1"
      ],
      "fields": [],
      "compatibility": {
        "general_pack_min": "1.2.0",
        "general_pack_max_exclusive": "2.0.0",
        "catalog_schema_versions": ["1.0"],
        "required_capabilities": [],
        "optional_capabilities": ["renderer"]
      },
      "tags": ["poster", "promotion"],
      "metadata": {}
    }
  ],
  "etag": "W/\"general-presets-1.0.0-zh-CN\"",
  "warnings": []
}
```

### 14.4 HTTP Semantics

```text
200 catalog returned
304 not modified
400 invalid query
404 preset not found
409 requested version incompatible
503 catalog unavailable
```

Use the existing V3 error envelope.

### 14.5 Caching

Preset catalogs are read-heavy and versioned.

Recommended:

```text
ETag
short public or private cache according to authentication boundary
stale-while-revalidate where host architecture supports it
client memory cache per locale
```

A stale catalog may display cards, but submission must always be resolved against the current trusted backend catalog.

---

## 15. Manifest Integration Without Core-Schema Conflict

Document 16 defines `ScenarioUIManifest.metadata` and `quick_actions`.

Use those existing fields rather than adding a required field to the frozen scenario manifest.

Recommended General Creative manifest addition:

```json
{
  "ui": {
    "quick_actions": [
      {
        "action_id": "select_quick_start_preset",
        "component_id": "GeneralQuickStartPresetGallery"
      },
      {
        "action_id": "select_mode",
        "component_id": "GeneralModeSelector"
      },
      {
        "action_id": "select_brand",
        "component_id": "BrandPicker"
      },
      {
        "action_id": "upload_assets",
        "component_id": "AssetUploader"
      },
      {
        "action_id": "quick_controls",
        "component_id": "OptionalQuickControls"
      }
    ],
    "metadata": {
      "quick_start_presets": {
        "enabled": true,
        "catalog_endpoint": "/api/v3/creative-agent/scenario-packs/general_creative/presets",
        "component_id": "GeneralQuickStartPresetGallery",
        "initial_featured_count": 6,
        "allow_deep_link": true,
        "default_behavior": "no_preset_baseline"
      }
    }
  }
}
```

Rules:

```text
component_id must exist in the V3-owned component registry
catalog_endpoint must match an approved same-origin V3 route
manifest cannot inject remote code
manifest cannot specify arbitrary component source
```

---

## 16. Frontend Component Specification

### 16.1 `GeneralQuickStartPresetGallery`

Responsibilities:

```text
load catalog
render featured presets
render categories
manage selected preset state
support keyboard navigation
support expanded catalog
surface unavailable state
emit validated preset-selection events
```

Must not:

```text
construct core requests directly
apply unvalidated target paths
call providers
hard-code the full preset list
```

### 16.2 `GeneralQuickStartPresetCard`

Display:

```text
icon or V3-owned thumbnail
localized name
one-line description
selected state
experimental/unavailable label when applicable
```

Interaction:

```text
single click/tap selects
second click may keep selected; clearing uses an explicit clear action
Enter or Space selects
selected state is exposed to assistive technology
```

### 16.3 `GeneralPresetCategoryTabs`

Requirements:

```text
data-driven labels
All virtual category
keyboard navigation
visible selected state
no category required for submission
```

### 16.4 `GeneralPresetContextPanel`

Shown after selection.

Display:

```text
preset name
short explanation
contextual composer placeholder
optional helper fields
suggested uploads
suggested ratios
clear preset action
```

The panel should be compact and progressively disclosed.

### 16.5 `GeneralPresetFieldRenderer`

Requirements:

```text
render only allowlisted field types
validate max length and option values
map only allowlisted target paths
track touched fields
show field source when useful
preserve values during compatible preset switching
```

### 16.6 `SelectedPresetChip`

Use in compact or mobile layouts.

Display:

```text
selected preset name
clear action
change action
```

### 16.7 `PresetInputSummary`

Before submission or immediately after job creation, show:

```text
selected scene
mode
brand
platform
ratio
required text
uploaded asset roles
major contextual values
```

The summary must remain user-safe and editable before submission when the product flow supports a confirmation step.

### 16.8 Existing Components Reused

The following remain owned by document 18:

```text
GeneralModeSelector
NaturalLanguageInput
AssetUploader
BrandPicker
OptionalQuickControls
JobProgress
AssetSeriesViewer
CandidateSelector
RegenerateDialog
TextRevisionPanel
ContinueStyleDialog
BrandSaveDialog
ExportDialog
WarningsPanel
MetadataSummary
```

Do not duplicate them inside the preset feature.

---

## 17. Frontend State Model

Recommended additive states:

```text
preset_catalog_loading
preset_catalog_ready
preset_catalog_unavailable
preset_none
preset_selected
preset_switching
preset_field_invalid
preset_version_stale
```

These states compose with document 18's General Creative UI states.

### 17.1 Loading

While loading presets:

```text
show a small skeleton for the gallery
do not block the baseline General Creative composer
```

If the General Creative manifest is valid but the preset catalog is temporarily unavailable:

```text
show Free Create baseline
show a non-blocking “常用场景暂不可用” notice
allow normal job creation without preset
```

### 17.2 Stale Catalog at Submission

If the selected preset changed incompatibly since the client loaded it:

```text
return version conflict
refresh catalog
preserve draft
show changed fields/defaults
require resubmission
```

Do not silently execute changed defaults.

### 17.3 Local Draft Persistence

The browser may persist:

```text
selected preset id
preset field values
field touched paths
mode
user text
non-sensitive control values
```

It must not persist:

```text
permanent upload access URLs
sensitive asset bytes
server-owned checksums
private provider metadata
```

---

## 18. Responsive, Accessibility, and Localization

### 18.1 Responsive

Desktop:

```text
2 to 6 columns according to width
compact card height
composer remains prominent
```

Tablet:

```text
2 to 4 columns
context panel below gallery
```

Mobile:

```text
horizontal featured list or two-column grid
full catalog in bottom sheet or page section
preset fields in one column
sticky create action only when it does not cover fields
```

### 18.2 Accessibility

Required:

```text
keyboard-selectable cards
visible focus state
aria-selected or equivalent semantic state
localized accessible card labels
no information conveyed only by color
thumbnail alt text or decorative handling
minimum usable touch targets
error association with the corresponding field
```

### 18.3 Localization

Machine identifiers remain stable and language-neutral.

Localized fields:

```text
display name
description
composer placeholder
field labels
field descriptions
examples
category labels
```

Do not use localized display text as a programmatic id.

Fallback order:

```text
requested locale
product default locale
English fallback
stable preset id as last-resort diagnostic only
```

---

## 19. Versioning, Activation, and Removal

### 19.1 Preset Versioning

Use semantic versioning:

```text
patch: copy, examples, non-semantic display fixes
minor: additive optional fields or compatible defaults
major: incompatible field semantics or behavior
```

Changing a visible default that may change output should normally require at least a minor preset version.

### 19.2 Catalog Versioning

The catalog version changes when:

```text
preset membership changes
category order changes materially
active status changes
preset version references change
```

### 19.3 Job Pinning

Every submitted job using a preset must pin:

```text
preset id
resolved preset version
catalog version
default checksum
```

### 19.4 Deprecation

Deprecated preset behavior:

```text
not shown for new users by default
historical jobs remain readable
saved drafts show migration notice
user may switch to a recommended replacement
no automatic replacement at execution time
```

### 19.5 Removal

Removing a preset from the active catalog must not break:

```text
General Creative
other presets
historical JobView
exports
brand memory
core regression tests
```

---

## 20. Security and Rights

### 20.1 Trusted Catalog Boundary

First release catalogs must load only from:

```text
V3-owned Python package
or V3-owned validated JSON/YAML files
```

No remote third-party preset registry is allowed.

### 20.2 Manifest Safety

Reject:

```text
HTML
JavaScript
CSS injection
iframe configuration
remote executable URLs
arbitrary component names
arbitrary target paths
provider payload fragments
filesystem paths
```

### 20.3 Upload Safety

Preset upload hints do not bypass document-17 UploadService validation.

QR codes, product photos, team photos, logos, and references must follow the same:

```text
ownership
file type
size
content safety
storage
access control
```

requirements as all General Creative uploads.

### 20.4 Text Safety

Preset text fields use existing sanitization and renderer escaping.

No field may cause raw HTML or SVG execution.

### 20.5 Claims and Compliance

General presets do not certify:

```text
advertising-law compliance
employment-law compliance
platform-policy compliance
factual accuracy
price legality
medical or financial claims
```

Where the broader product has relevant safety checks, those checks remain authoritative.

---

## 21. Observability and Product Analytics

### 21.1 Required Trace Metadata

Record:

```text
job_id
pack_id
pack_version
preset_id
preset_version
catalog_version
selection_source
defaults_checksum
applied default paths
ignored default paths
user override count
resolved mode
```

### 21.2 Product Events

Recommended events:

```text
general_preset_catalog_viewed
general_preset_selected
general_preset_cleared
general_preset_switched
general_preset_field_completed
general_preset_submit_started
general_preset_submit_succeeded
general_preset_submit_failed
```

### 21.3 Privacy

Do not place full user prompts or exact commercial text into general analytics events unless the platform has an explicit, approved data policy.

Prefer:

```text
preset id
field completion booleans
counts
status codes
latency
```

### 21.4 Success Metrics

Useful product metrics:

```text
preset selection rate
blank-page abandonment rate
selection-to-submit conversion
field completion rate
mode override rate
ratio override rate
job completion rate by preset
regeneration rate by preset
text-revision rate by preset
export rate by preset
```

Metrics are product diagnostics. They must not become hidden creative policy in General Creative.

---

## 22. Testing Strategy

### 22.1 Core Regression Gate

For equivalent requests:

```text
no preset
free_create
```

must produce equivalent core pipeline inputs and outputs, excluding approved application metadata.

Preset implementation must not modify:

```text
CommercialBrief semantics beyond visible user inputs
DefaultCommercialPack binding
core agent order
provider routing
candidate evaluation policy
brand-memory authority
```

### 22.2 Catalog Contract Tests

Required:

```text
all ids unique
all versions valid
all categories valid
all card orders deterministic
all mode references exist
all field ids unique per preset
all field types allowlisted
all target paths allowlisted
all asset purposes allowlisted
all ratios valid
all localized required labels present
no executable content
```

### 22.3 Resolver Tests

Required:

```text
explicit values beat preset defaults
natural-language explicit constraints beat untouched defaults
brand constraints beat preset defaults
preset defaults beat General inferred defaults
user-selected mode beats preset mode suggestion
free_create is baseline-equivalent
switching presets preserves touched values
clearing preset removes only owned untouched defaults
exact text remains exact
asset roles validate ownership
```

### 22.4 API Tests

Required:

```text
catalog list
category filter
locale fallback
ETag / 304
single preset read
unknown preset 404
incompatible version 409
catalog unavailable 503
submission resolves current trusted version
client cannot forge resolved checksum
```

### 22.5 UI Contract Tests

Required:

```text
gallery is manifest/catalog-driven
composer remains available during catalog loading
featured and expanded states work
cards are keyboard selectable
selected state is accessible
preset switch preserves user input
mode touched state is respected
context fields map correctly
mobile layout works
unavailable catalog falls back to baseline General Creative
```

### 22.6 Security Tests

Required:

```text
reject arbitrary target path
reject arbitrary component id
reject remote script or HTML
reject path traversal in card asset
escape all text fields
validate upload ownership
cross-user draft/job access denied
```

### 22.7 Offline Tests

Catalog and resolver tests must run without:

```text
GPU
external generation provider
external storage
external event bus
network access
V1/V2 runtime
```

### 22.8 Per-Preset Mapping Tests

Every active preset must have at least one mapping test asserting:

```text
resolved mode behavior
field target paths
suggested asset roles
ratio list
boundary metadata
request serialization
```

---

## 23. End-to-End Acceptance Cases

### 23.1 Free Create

Input:

```text
帮我做一组新工作室开业宣传视觉，简洁、年轻。
```

Expected:

```text
baseline General Creative path
no preset constraints
DefaultCommercialPack
normal series output
```

### 23.2 Campaign Poster

Input:

```text
帮我做一张咖啡店周末活动海报，第二杯半价。
```

Expected:

```text
campaign_poster pinned
single_asset suggested unless user requests otherwise
headline/offer exact-text mapping when supplied
existing renderer path available
```

### 23.3 Product or Service Showcase

Input:

```text
帮我做一组宠物上门洗护服务展示图，突出安心、方便和透明价格。
```

Expected:

```text
product_service_showcase pinned
auto series suggested
no e-commerce platform policy
```

### 23.4 Social Media Visual

Input:

```text
做一组夏季办公室健康提醒配图，轻松、清晰。
```

Expected:

```text
social_media_visual pinned
generic platform/ratio controls only
no platform-algorithm strategy
```

### 23.5 Website Banner

Input:

```text
做一张官网首页横幅，介绍我们的 AI 企业培训。
```

Expected:

```text
web_banner_hero pinned
single asset suggested
horizontal ratio suggestions
```

### 23.6 Festival Visual

Input:

```text
沿用品牌风格做一组端午节祝福图。
```

Expected:

```text
festival_seasonal_visual pinned
brand_continuation may win when explicitly selected
brand memory rules unchanged
```

### 23.7 Brand Style Exploration

Input:

```text
为新的精品烘焙品牌探索三种视觉方向。
```

Expected:

```text
brand_style_exploration pinned
direction_count visible
persistent memory not updated until confirmation
```

### 23.8 Knowledge Cards

Input:

```text
把新手摄影的五个构图技巧做成一组知识卡片。
```

Expected:

```text
knowledge_card_infographic pinned
structured exact text preserved
content split instead of silent truncation
```

### 23.9 Service Package / Price Card

Input:

```text
做一张三档健身私教套餐价目卡。
```

Expected:

```text
service_package_price_card pinned
price text exact
text-only price correction uses RenderRevision
```

### 23.10 Announcement

Input:

```text
做一张国庆期间营业时间调整通知图。
```

Expected:

```text
announcement_notice pinned
clear exact text
single asset suggested
```

### 23.11 Event Invitation

Input:

```text
做一张周六读书会邀请图，预留二维码位置。
```

Expected:

```text
event_invitation_registration pinned
QR asset handled as user upload
no fabricated working QR destination
```

### 23.12 Recruitment Poster

Input:

```text
做一张咖啡师招聘海报，突出培训和成长空间。
```

Expected:

```text
recruitment_poster pinned
single asset suggested
no inferred discriminatory targeting
```

---

## 24. Additive Directory Structure

Preserve the actual V3-owned layout if it differs.

Responsibility boundaries are normative.

```text
alchemy_creative_agent_3_0/
  docs/
    19_GENERAL_CREATIVE_QUICK_START_PRESETS_SPEC.md

  app/
    application/
      general_presets/
        __init__.py
        models.py
        errors.py
        catalog.py
        registry.py
        resolver.py
        validation.py
        snapshot.py

    scenario_packs/
      packs/
        general_creative/
          presets/
            catalog.json
            free_create.json
            campaign_poster.json
            product_service_showcase.json
            social_media_visual.json
            web_banner_hero.json
            festival_seasonal_visual.json
            brand_style_exploration.json
            knowledge_card_infographic.json
            service_package_price_card.json
            announcement_notice.json
            event_invitation_registration.json
            recruitment_poster.json

    app_shell/
      general_preset_routes.py
      general_preset_contracts.py

  v3-frontend/
    features/
      general-creative/
        quick-start/
          GeneralQuickStartPresetGallery.tsx
          GeneralQuickStartPresetCard.tsx
          GeneralPresetCategoryTabs.tsx
          GeneralPresetContextPanel.tsx
          GeneralPresetFieldRenderer.tsx
          SelectedPresetChip.tsx
          PresetInputSummary.tsx
          presetDraftMapper.ts
          presetTypes.ts

  tests/
    application/
      general_presets/
        test_catalog_validation.py
        test_registry.py
        test_resolver.py
        test_merge_precedence.py
        test_free_create_regression.py
        test_preset_snapshot.py

    api/
      test_general_preset_catalog_api.py
      test_general_preset_submission.py

    frontend/
      general-creative/
        generalQuickStartPresetGallery.test.tsx
        generalPresetDraftMapper.test.ts
        generalPresetAccessibility.test.tsx

    golden/
      general_presets/
        free_create.json
        campaign_poster.json
        product_service_showcase.json
        social_media_visual.json
        web_banner_hero.json
        festival_seasonal_visual.json
        brand_style_exploration.json
        knowledge_card_infographic.json
        service_package_price_card.json
        announcement_notice.json
        event_invitation_registration.json
        recruitment_poster.json
```

No preset directory may contain a direct provider client.

---

## 25. Implementation Phases

### Q0. Freeze General Creative Baseline

Before code changes:

```text
run document-16 tests
run document-17 tests
capture no-preset golden requests and outputs
verify GeneralCreativeScenarioPack policy bundle is empty/baseline-equivalent
verify current General Creative manifest and workspace
```

Gate:

```text
no unresolved General Creative regression
```

### Q1. Add Preset Contracts and Built-In Catalog

Implement:

```text
preset models
category model
catalog loader
registry validation
initial 12-preset catalog
version/checksum handling
```

Tests:

```text
schema
ids
versions
mode references
field target paths
security
localization
```

### Q2. Add Resolver and Create-Job Mapping

Implement:

```text
GeneralPresetResolver
merge precedence
exact-text mapping
context mapping
asset-role mapping
server-owned selection record
historical snapshot
```

Gate:

```text
free_create and no preset are regression-equivalent
```

### Q3. Add Catalog API and Manifest Integration

Implement:

```text
catalog routes
ETag
locale/category filtering
General Creative quick-action declaration
capability filtering
```

Gate:

```text
frontend can discover presets without hard-coded catalog data
```

### Q4. Add General Quick-Start UI

Implement:

```text
preset gallery
cards
categories
context panel
field renderer
selected chip
mode touched-state behavior
preset switching
mobile behavior
accessibility
local draft persistence
```

Gate:

```text
all 12 presets can create a valid General Creative draft and job request
```

### Q5. End-to-End Hardening

Implement and verify:

```text
per-preset acceptance cases
catalog stale-version behavior
historical job display
offline tests
security tests
analytics events
performance
localization
responsive regression
README index update
```

### Sequential Rule Before Document 18 Implementation

Do not begin production implementation of the E-Commerce specialization pack until:

```text
Q0 baseline is accepted
Q1 catalog contract is accepted
Q2 resolver and free-create regression are accepted
Q3 API discovery is accepted
Q4 common-scene UI is accepted
Q5 Definition of Done is signed off
```

E-Commerce research and design discussion may occur, but its implementation must reuse the frozen contracts completed here.

---

## 26. Definition of Done

Document 17.1 is complete only when all statements below are true:

```text
1. General Creative exposes a catalog-driven common-scene gallery.
2. The gallery is inside the existing shared ScenarioWorkspace.
3. Natural-language input remains primary and required.
4. All preset-specific helper fields are optional in the first release.
5. The initial 12-preset catalog is implemented and validated.
6. Presets are versioned independently from the scenario manifest schema.
7. General Creative pack version is pinned per job.
8. Preset id, version, catalog version, and checksum are pinned per preset job.
9. No-preset behavior remains valid.
10. free_create is core-output-equivalent to no preset.
11. Presets do not change DefaultCommercialPack binding.
12. Presets do not return a non-empty specialization policy bundle.
13. Presets do not call providers.
14. Presets do not contain raw prompt patches.
15. Preset defaults are visible and overridable.
16. Explicit user values beat preset defaults.
17. Explicit natural-language constraints beat untouched preset defaults.
18. Persistent brand constraints beat preset defaults.
19. Preset defaults beat only General inferred defaults.
20. User-selected mode beats a preset mode suggestion.
21. Switching presets preserves user input, brand, uploads, and touched values.
22. Clearing a preset removes only preset-owned untouched defaults.
23. Exact text maps to the existing text and renderer flow.
24. Uploaded assets stay under the existing UploadService and ownership rules.
25. The UI does not expose provider or model controls.
26. The catalog is loaded from a trusted V3-owned source.
27. Manifest and field target paths are allowlisted.
28. Arbitrary HTML, JavaScript, CSS, remote code, and component loading are rejected.
29. The baseline composer remains usable if only the preset catalog is unavailable.
30. Stale preset versions do not execute silently.
31. Historical preset jobs remain readable after deprecation or removal.
32. Desktop, tablet, and mobile layouts are covered.
33. Keyboard, screen-reader, and visible-focus requirements are covered.
34. Locale fallback is deterministic.
35. All active presets have contract, mapping, UI, and acceptance tests.
36. Catalog/resolver tests run offline.
37. General Creative document-17 actions remain unchanged and reusable.
38. No V1/V2 runtime dependency is introduced.
39. No e-commerce, new-media, private-community, or brand-IP strategy leaks into General presets.
40. README/doc index references document 19.
```

---

## 27. Compatibility Mapping

### 27.1 `00_ROOT_RULES.md`

Preserved:

```text
independent V3 UI and API
natural-language-first product
no V1/V2 runtime dependency
commercial output over technical controls
```

### 27.2 `01_PRODUCT_VISION.md`

Completes the common user entry for:

```text
auto commercial series
single image
brand style establishment
brand continuation
common high-frequency commercial visuals
optional future template matching
```

### 27.3 `02_SYSTEM_ARCHITECTURE.md`

Preserved:

```text
one Central Creative Brain
same agent order
same CommercialBrief / CreativePlan / SeriesPlan / LayoutPlan path
same provider and evaluation path
```

### 27.4 `07_SCHEMA_CONTRACTS.md`

Preserved:

```text
no required frozen core-schema change
preset models are application/UI contracts
existing CreateCreativeJobRequest remains the execution boundary
```

### 27.5 `09_RULES_AND_DEFAULTS.md`

Preserved:

```text
existing output defaults
existing platform detection
existing single-image and series behavior
existing clarification minimization
```

Preset defaults are lower-priority visible application defaults.

### 27.6 `10_BRAND_MEMORY_SPEC.md`

Preserved:

```text
brand selection remains optional
brand continuation uses the existing mode and authority
brand updates require allowed signals and confirmation
brand exploration does not auto-write memory
```

### 27.7 `11_EVALUATION_AND_REFINEMENT_SPEC.md`

Preserved:

```text
same scoring
same ranking
same critic
same refinement loop
same accepted-candidate semantics
```

### 27.8 `12_PROVIDER_INTERFACES.md`

Preserved:

```text
no provider calls from preset UI, catalog, or resolver
generation remains behind V3 provider interfaces
text revision remains behind RendererProvider path
```

### 27.9 `15_PRODUCT_BOUNDARY_AND_VERTICAL_AGENT_ARCHITECTURE.md`

Preserved:

```text
one V3 product boundary
DefaultCommercialPack fallback
future vertical packs extend rather than fork
```

### 27.10 `17_SCENARIO_PACK_PLATFORM_EXTENSION_SPEC.md`

Uses:

```text
registry-driven UI
shared workspace
trusted component registry
scenario manifest metadata
version pinning
one primary ScenarioPack per job
```

### 27.11 `18_GENERAL_CREATIVE_PRODUCT_AND_RUNTIME_SPEC.md`

Extends:

```text
empty-state UI
GeneralCreativeDraft
manifest quick actions
create-job request mapping
input summary
frontend state model
testing and Definition of Done
```

Does not alter:

```text
job state machine
candidate semantics
regeneration semantics
continuation semantics
text revision
brand confirmation
export
```

### 27.12 Future Document 18

Future E-Commerce specialization must reuse:

```text
preset gallery patterns where useful
field renderer
mode-control behavior
draft touched-state behavior
job runtime
candidate actions
text renderer
brand flow
export flow
```

But E-Commerce will own its own:

```text
scenario pack
specialization policy
platform rules
specialized modes
specialized preset catalog if needed
specialized evaluation and output rules through approved extension contracts
```

The General catalog must not be expanded with e-commerce-specific rules; future specialization rules belong in later pack-specific documents, not document 19.

---

## 28. Non-Goals Summary

This document does not authorize:

```text
new core agents
new core pipeline
new provider adapter
new scoring model
raw prompt patching
fixed visual template marketplace
user-uploaded executable templates
platform-specific commerce optimization
new-media algorithm strategy
private-community lifecycle automation
brand-IP operations system
```

---

## 29. Non-Negotiable Summary

```text
General Quick-Start Presets solve the blank-page and common-scene entry problem.
They do not solve vertical specialization.
They are declarative, visible, versioned, overridable, and auditable.
They map into existing General Creative application contracts.
They keep GeneralCreativeScenarioPack bound to DefaultCommercialPack.
They never create a second runtime.
They never call providers.
They never replace natural language.
They never become hidden prompt patches.
The General Creative module is not complete until this preset layer passes its gates.
Only then should production implementation move to the E-Commerce specialization pack.
```

---

## Appendix A. Complete Initial Catalog Summary

```json
{
  "catalog_schema_version": "1.0",
  "catalog_version": "1.0.0",
  "pack_id": "general_creative",
  "required_pack_version": ">=1.2.0,<2.0.0",
  "default_preset_id": null,
  "categories": [
    {"category_id": "recommended", "order": 10},
    {"category_id": "promotion", "order": 20},
    {"category_id": "showcase", "order": 30},
    {"category_id": "content", "order": 40},
    {"category_id": "brand", "order": 50},
    {"category_id": "business_information", "order": 60}
  ],
  "presets": [
    {
      "preset_id": "free_create",
      "preset_version": "1.0.0",
      "category_id": "recommended",
      "default_mode_id": "auto_commercial_series",
      "featured": true,
      "card_order": 10,
      "suggested_aspect_ratios": [],
      "suggested_asset_purposes": []
    },
    {
      "preset_id": "campaign_poster",
      "preset_version": "1.0.0",
      "category_id": "promotion",
      "default_mode_id": "single_asset",
      "featured": true,
      "card_order": 20,
      "suggested_aspect_ratios": ["3:4", "4:5", "9:16", "1:1"],
      "suggested_asset_purposes": ["logo", "product_photo", "store_photo", "preferred_style_reference"]
    },
    {
      "preset_id": "product_service_showcase",
      "preset_version": "1.0.0",
      "category_id": "showcase",
      "default_mode_id": "auto_commercial_series",
      "featured": true,
      "card_order": 30,
      "suggested_aspect_ratios": ["1:1", "4:5", "16:9", "3:4"],
      "suggested_asset_purposes": ["product_photo", "logo", "store_photo", "preferred_style_reference"]
    },
    {
      "preset_id": "social_media_visual",
      "preset_version": "1.0.0",
      "category_id": "content",
      "default_mode_id": "auto_commercial_series",
      "featured": true,
      "card_order": 40,
      "suggested_aspect_ratios": ["1:1", "4:5", "9:16", "3:4"],
      "suggested_asset_purposes": ["logo", "product_photo", "preferred_style_reference", "previous_poster"]
    },
    {
      "preset_id": "festival_seasonal_visual",
      "preset_version": "1.0.0",
      "category_id": "promotion",
      "default_mode_id": "auto_commercial_series",
      "featured": true,
      "card_order": 50,
      "suggested_aspect_ratios": ["1:1", "4:5", "9:16", "3:4", "16:9"],
      "suggested_asset_purposes": ["logo", "product_photo", "preferred_style_reference", "previous_poster"]
    },
    {
      "preset_id": "web_banner_hero",
      "preset_version": "1.0.0",
      "category_id": "showcase",
      "default_mode_id": "single_asset",
      "featured": true,
      "card_order": 60,
      "suggested_aspect_ratios": ["16:9", "21:9", "3:1", "2:1"],
      "suggested_asset_purposes": ["product_photo", "logo", "preferred_style_reference"]
    },
    {
      "preset_id": "brand_style_exploration",
      "preset_version": "1.0.0",
      "category_id": "brand",
      "default_mode_id": "auto_commercial_series",
      "featured": false,
      "card_order": 70,
      "suggested_aspect_ratios": ["1:1", "4:5", "16:9"],
      "suggested_asset_purposes": ["logo", "product_photo", "brand_color_reference", "preferred_style_reference"]
    },
    {
      "preset_id": "knowledge_card_infographic",
      "preset_version": "1.0.0",
      "category_id": "content",
      "default_mode_id": "auto_commercial_series",
      "featured": false,
      "card_order": 80,
      "suggested_aspect_ratios": ["3:4", "4:5", "1:1", "9:16"],
      "suggested_asset_purposes": ["logo", "preferred_style_reference", "other_reference"]
    },
    {
      "preset_id": "service_package_price_card",
      "preset_version": "1.0.0",
      "category_id": "business_information",
      "default_mode_id": "single_asset",
      "featured": false,
      "card_order": 90,
      "suggested_aspect_ratios": ["3:4", "4:5", "1:1", "9:16"],
      "suggested_asset_purposes": ["logo", "store_photo", "preferred_style_reference"]
    },
    {
      "preset_id": "announcement_notice",
      "preset_version": "1.0.0",
      "category_id": "business_information",
      "default_mode_id": "single_asset",
      "featured": false,
      "card_order": 100,
      "suggested_aspect_ratios": ["1:1", "3:4", "4:5", "16:9"],
      "suggested_asset_purposes": ["logo", "store_photo", "preferred_style_reference"]
    },
    {
      "preset_id": "event_invitation_registration",
      "preset_version": "1.0.0",
      "category_id": "promotion",
      "default_mode_id": "single_asset",
      "featured": false,
      "card_order": 110,
      "suggested_aspect_ratios": ["3:4", "4:5", "9:16", "1:1"],
      "suggested_asset_purposes": ["logo", "store_photo", "other_reference", "preferred_style_reference"]
    },
    {
      "preset_id": "recruitment_poster",
      "preset_version": "1.0.0",
      "category_id": "business_information",
      "default_mode_id": "single_asset",
      "featured": false,
      "card_order": 120,
      "suggested_aspect_ratios": ["3:4", "4:5", "9:16", "1:1"],
      "suggested_asset_purposes": ["logo", "store_photo", "other_reference", "preferred_style_reference"]
    }
  ]
}
```

This summary is not a substitute for the fully validated per-preset manifest files.

---

## Appendix B. Recommended General Creative Manifest Delta

After implementation, merge the following delta into the document-17 General Creative manifest without removing existing fields:

```json
{
  "pack_version": "1.2.0",
  "ui": {
    "quick_actions": [
      {
        "action_id": "select_quick_start_preset",
        "component_id": "GeneralQuickStartPresetGallery"
      },
      {
        "action_id": "select_mode",
        "component_id": "GeneralModeSelector"
      },
      {
        "action_id": "select_brand",
        "component_id": "BrandPicker"
      },
      {
        "action_id": "upload_assets",
        "component_id": "AssetUploader"
      },
      {
        "action_id": "quick_controls",
        "component_id": "OptionalQuickControls"
      }
    ],
    "metadata": {
      "quick_start_presets": {
        "enabled": true,
        "catalog_endpoint": "/api/v3/creative-agent/scenario-packs/general_creative/presets",
        "component_id": "GeneralQuickStartPresetGallery",
        "catalog_schema_version": "1.0",
        "initial_featured_count": 6,
        "allow_deep_link": true,
        "default_behavior": "no_preset_baseline"
      }
    }
  },
  "tags": [
    "general",
    "commercial_visual",
    "brand_continuation",
    "single_image",
    "quick_start_presets"
  ],
  "metadata": {
    "policy_neutral": true,
    "quick_start_presets_version": "1.0.0"
  }
}
```

---

## Appendix C. Recommended README Index Addition

Add:

```text
alchemy_creative_agent_3_0/docs/19_GENERAL_CREATIVE_QUICK_START_PRESETS_SPEC.md
```

Recommended placement:

```text
immediately after 18_GENERAL_CREATIVE_PRODUCT_AND_RUNTIME_SPEC.md
```

Do not remove or renumber earlier entries.

---

## Appendix D. Minimal Implementation Status Report

```text
GENERAL_QUICK_START_STATUS: PASS or FAIL

Baseline regression:
Preset catalog validation:
Preset resolver:
Free-create equivalence:
Catalog API:
Manifest integration:
Desktop UI:
Mobile UI:
Accessibility:
Localization:
Security:
Offline tests:
Per-preset mapping tests:
Per-preset acceptance cases:
Historical version pinning:
README index:

Unresolved blockers:
```
