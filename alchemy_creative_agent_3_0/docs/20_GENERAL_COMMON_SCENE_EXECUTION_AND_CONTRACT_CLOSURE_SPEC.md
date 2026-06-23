# 20 General Common Scene Execution and Contract Closure Specification

Source mapping: this is the V3 repository placement of the draft
`17.2_GENERAL_COMMON_SCENE_EXECUTION_AND_CONTRACT_CLOSURE_SPEC.md`. It is
numbered as document 20 here because documents 17, 18, and 19 are already used
for the Scenario Pack platform, General Creative product/runtime, and V3 product
integration execution prompt.

This document closes the remaining execution-contract gaps after:

```text
18_GENERAL_CREATIVE_PRODUCT_AND_RUNTIME_SPEC.md
19_GENERAL_CREATIVE_QUICK_START_PRESETS_SPEC.md
```

It is the final General Creative module supplement before beginning the first specialization-pack document, such as:

```text
future ecommerce scenario-pack specification
```

The purpose of this document is to make sure that the General Creative quick-start preset chosen in the UI becomes a deterministic, auditable, schema-safe execution hint for the existing V3 Central Creative Brain, without creating a second runtime, hidden template engine, or vertical specialization layer.

The target closure is:

```text
V3 Scenario Hub
→ General Creative card
→ Quick-Start Preset Gallery
→ GeneralCreativeDraft
→ GeneralCommonSceneResolution
→ CreateCreativeJobRequest.scenario_selection.parameters
→ ScenarioRuntime
→ GeneralCreativeScenarioPack
→ DefaultCommercialPack
→ existing Central Creative Brain
→ CommercialBrief / CreativePlan / SeriesPlan / AssetSpec / LayoutPlan
→ existing candidate, selection, regeneration, text-rendering, brand-memory, and export flows
```

---

## 1. Document Status and Authority

### 1.1 Additive Closure Specification

This document is an additive companion to:

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
19_GENERAL_CREATIVE_QUICK_START_PRESETS_SPEC.md
```

It adds only:

```text
GeneralCommonSceneResolution
preset-to-scene execution mapping
core-safe aspect-ratio normalization
field normalization for exact text, named slots, context, and controls
content segmentation for long structured common-scene inputs
render-revision activation route
cross-document acceptance gates for freezing the General Creative module
```

It does not replace or weaken documents 17, 18, or 19.

### 1.2 Precedence

If a conflict appears, use this order:

```text
1. 00_ROOT_RULES.md
2. frozen V3 core schema and provider contracts
3. existing Central Creative Brain behavior
4. 17_SCENARIO_PACK_PLATFORM_EXTENSION_SPEC.md
5. 18_GENERAL_CREATIVE_PRODUCT_AND_RUNTIME_SPEC.md
6. 19_GENERAL_CREATIVE_QUICK_START_PRESETS_SPEC.md
7. this document
8. future specialization-pack specifications
```

This document may clarify document 19 and define canonical closure behavior. It must not add required fields to frozen core schemas.

### 1.3 Compatibility Statement

The General Creative module is complete only when documents 18, 19, and 20 are implemented together.

```text
18     = General Creative workspace and application runtime
19     = common-scene quick-start preset UI and catalog
20     = preset selection to execution-plan contract closure
```

---

## 2. Why Document 20 Exists

Documents 18 and 19 close most of the General Creative product layer:

```text
workspace UI
job runtime
candidate actions
text-only revision
brand-memory confirmation
export
preset gallery
preset dynamic fields
preset registry
preset-to-draft mapping
```

However, without this document, one important ambiguity remains:

```text
When the user selects a common-scene preset such as Knowledge Card or Brand Style Exploration,
how does that explicit scene choice deterministically influence the existing SeriesPlan and AssetSpec output
without becoming a hidden vertical pack or a separate template engine?
```

This document answers that question.

---

## 3. Non-Goals

This document must not be interpreted as permission to:

```text
create a separate General Creative generation pipeline
create provider-specific preset generation endpoints
turn Quick-Start Presets into a fixed visual-template runtime
add marketplace template licensing, template thumbnails, template slots, or PSD/SVG template assets
inject hidden prompt patches from General Creative presets
activate a vertical specialization pack from a General Creative preset
change DefaultCommercialPack behavior for free-create requests
add new required fields to CreativeJob, CommercialBrief, SeriesPlan, AssetSpec, LayoutPlan, or CommercialAssetPack
pass unsupported AspectRatio enum values into core schemas
bypass existing text-overlay rendering rules
silently summarize, truncate, or rewrite exact user-provided text
silently apply brand memory
```

Quick-Start Presets are still declarative user-facing entry helpers, not vertical strategy packs.

---

## 4. Final General Creative Coverage Audit

### 4.1 Coverage After Documents 18 and 19

| Area | Status before document 20 |
|---|---|
| General Creative card and workspace | Covered by 18 |
| Product modes: auto series, single asset, brand continuation | Covered by 18 |
| Job, run, attempt, candidate lifecycle | Covered by 18 |
| Candidate selection and regeneration | Covered by 18 |
| Text-only revision creation | Covered by 18 |
| Brand-memory confirmation | Covered by 18 |
| Export flow | Covered by 18 |
| Quick-start preset gallery | Covered by 19 |
| Preset catalog and field definitions | Covered by 19 |
| Dynamic form behavior | Covered by 19 |
| Preset version pinning | Covered by 19 |
| Preset selection to deterministic SeriesPlan / AssetSpec hints | Open before document 20 |
| Core-safe aspect-ratio mapping for non-enum ratios | Open before document 20 |
| Exact text vs named slots vs context mapping | Open before document 20 |
| Negative direction normalization | Open before document 20 |
| Structured long-content segmentation | Open before document 20 |
| Render revision history activation route | Open before document 20 |

### 4.2 Coverage After Document 20

After implementing this document, the General Creative module is considered complete for:

```text
common-scene image generation entry
front-end preset selection
front-end dynamic field collection
application-layer request normalization
schema-safe core handoff
common-scene series-shape hints
common-scene text and content handling
existing job runtime reuse
existing generation, candidate, refinement, rendering, brand, and export flow reuse
```

The following remain deliberately outside the General Creative closure:

```text
fixed visual-template asset library
industry-specific platform rules
conversion scoring for ecommerce
algorithmic content strategy for social platforms
private-community lifecycle automation
Brand IP bible and character consistency system
AI comic/drama storyboard and episode continuity system
```

These belong in later specialization or template-system documents.

---

## 5. Core Principle: Explicit Preset Selection Is a User Constraint

A General Quick-Start Preset may influence the output only because the user explicitly selected it, or because an API client explicitly supplied it.

It is therefore treated as a visible user constraint, not as a hidden pack-level prompt patch.

Allowed:

```text
User clicks Knowledge Card
→ UI shows Knowledge Card fields and summary
→ request carries preset_id and scene resolution metadata
→ application maps the selection into scenario_selection.parameters
→ Central Creative Brain receives schema-safe hints and user-visible constraints
→ SeriesPlanner may produce card-like AssetSpec purposes
```

Forbidden:

```text
User selects General Creative without a preset
→ system secretly chooses ecommerce-like conversion layout
→ GeneralCreativeScenarioPack injects hidden prompt fragments
→ DefaultCommercialPack is replaced
→ provider is called directly
```

Regression rule:

```text
A free-create request with no preset_id must remain equivalent to the existing General Creative behavior,
except for harmless audit metadata.
```

---

## 6. New Application DTO: GeneralCommonSceneResolution

### 6.1 Purpose

`GeneralCommonSceneResolution` is an application-layer DTO.

It records how a visible General Creative quick-start preset has been resolved into execution-safe creative hints for the existing V3 core.

It is not a frozen core schema.

It is not stored as a required field on `CreativeJob`.

It is copied into:

```text
CreateCreativeJobRequest.scenario_selection.parameters.general_common_scene_resolution
CreativeJob.metadata["general_common_scene_resolution"]
PlanningResult.metadata["general_common_scene_resolution"]
CommercialAssetPack.metadata["general_common_scene_resolution"]
```

Where necessary, short summaries may also be copied into existing fields such as:

```text
CreativeJob.requested_output
CreativeJob.explicit_constraints
CommercialBrief.scenario
SeriesPlan.metadata
AssetSpec.metadata
```

But no new required core fields may be added.

### 6.2 DTO Definition

```python
from pydantic import BaseModel, Field
from typing import Literal

CommonSceneSource = Literal[
    "explicit_user_preset",
    "explicit_api_preset",
    "deep_link_preset",
    "free_create",
    "legacy_or_auto"
]

CreativeTaskType = Literal[
    "free_create",
    "single_commercial_visual",
    "campaign_poster",
    "product_or_service_showcase",
    "social_media_visual",
    "web_banner_hero",
    "festival_or_seasonal_visual",
    "brand_style_exploration",
    "knowledge_card_or_infographic",
    "service_package_or_price_card",
    "announcement_or_notice",
    "event_invitation_or_registration",
    "recruitment_poster"
]

SeriesShape = Literal[
    "core_default",
    "single_asset",
    "small_asset_series",
    "multi_card_series",
    "visual_direction_set",
    "banner_only"
]

class GeneralCommonSceneResolution(BaseModel):
    common_scene_id: str
    preset_id: str | None = None
    preset_version: str | None = None

    source: CommonSceneSource = "free_create"
    visible_to_user: bool = True

    creative_task_type: CreativeTaskType = "free_create"
    requested_series_shape: SeriesShape = "core_default"

    requested_asset_count: int | None = None
    requested_asset_count_min: int | None = None
    requested_asset_count_max: int | None = None

    requested_asset_purposes: list[str] = Field(default_factory=list)
    requested_asset_types: list[str] = Field(default_factory=list)

    target_platforms_hint: list[str] = Field(default_factory=list)
    aspect_ratio_selection: "AspectRatioSelection | None" = None

    content_structure_hint: str | None = None
    layout_intent: str | None = None
    exact_text_policy: str | None = None
    segmentation_policy_id: str | None = None

    user_visible_summary: str | None = None
    warnings: list[str] = Field(default_factory=list)

    metadata: dict = Field(default_factory=dict)
```

Implementation may avoid forward references by placing `AspectRatioSelection` before this DTO.

### 6.3 Required Invariants

```text
common_scene_id must be stable for audit.
preset_id must match the resolved quick-start preset when source is explicit_user_preset or explicit_api_preset.
preset_version must be pinned at job creation time.
visible_to_user must be true for UI-selected presets.
requested_asset_types must use only values allowed by the frozen AssetType enum.
target_platforms_hint must use only values allowed by the frozen Platform enum.
aspect_ratio_selection.core_aspect_ratio must use only values allowed by the frozen AspectRatio enum.
metadata may preserve richer non-core UI values.
```

### 6.4 How Core Agents Consume It

The application layer may expose scene resolution to existing agents as:

```text
visible user constraints
CreativeJob.metadata
CommercialBrief.scenario hint
SeriesPlan.metadata hints
AssetSpec.metadata hints
```

The existing agents retain final responsibility for:

```text
commercial intent interpretation
brand memory loading
creative direction
series planning
layout planning
prompt compilation
generation routing
evaluation and refinement
packaging
```

---

## 7. Core-Safe Aspect Ratio Normalization

### 7.1 Problem

The frozen first-pass V3 `AspectRatio` enum allows:

```text
1:1
3:4
4:5
9:16
16:9
A4
custom
```

Some General Quick-Start Presets display useful ratios such as:

```text
21:9
3:1
2:1
```

These must not be passed into core schemas directly.

### 7.2 DTO Definition

```python
class CustomDimensions(BaseModel):
    width: int
    height: int
    ratio: str
    unit: str = "px"

class AspectRatioSelection(BaseModel):
    display_ratio: str | None = None
    core_aspect_ratio: str = "custom"
    custom_dimensions: CustomDimensions | None = None
    source: str = "preset_default"
    metadata: dict = Field(default_factory=dict)
```

### 7.3 Normalization Rules

If the selected ratio is one of:

```text
1:1
3:4
4:5
9:16
16:9
A4
custom
```

then:

```text
core_aspect_ratio = selected ratio
custom_dimensions = null unless selected ratio is custom with explicit dimensions
```

If the selected ratio is not a frozen enum value, then:

```text
core_aspect_ratio = "custom"
custom_dimensions = normalized width / height / ratio
metadata.original_display_ratio = selected ratio
```

### 7.4 Canonical First-Release Mappings

| Display ratio | Core aspect ratio | Default custom dimensions | Notes |
|---|---|---:|---|
| `21:9` | `custom` | `2100 x 900` | wide hero or cinematic banner |
| `3:1` | `custom` | `1800 x 600` | website or campaign banner |
| `2:1` | `custom` | `1600 x 800` | wide social or site banner |
| `1.91:1` | `custom` | `1200 x 628` | optional ad-style wide ratio if later exposed |

The values above are safe defaults. Implementations may allow project-level configured dimensions, but must still map into `custom` for the core schema.

### 7.5 UI Display Rule

The UI may continue to display:

```text
21:9
3:1
2:1
```

But the final request summary should show when a ratio will be treated as custom:

```text
Banner ratio: 3:1, implemented as custom 1800x600.
```

### 7.6 Validation Failure Behavior

If a ratio cannot be parsed:

```text
block job creation
show a validation error
preserve the draft
never send an invalid ratio into the core
```

---

## 8. Field Normalization and Canonical Mapping

### 8.1 Purpose

Document 19 defines dynamic preset fields such as:

```text
exact_text.headline
exact_text.event_time
context.key_points
controls.negative_directions
```

Document 20 freezes how these paths are normalized before job creation.

### 8.2 Normalization Result DTO

```python
class GeneralPresetFieldNormalizationResult(BaseModel):
    exact_text: "TextContent"
    context: dict = Field(default_factory=dict)
    controls: dict = Field(default_factory=dict)
    raw_field_values: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
```

`TextContent` is the application-layer text DTO from document 18:

```python
class TextContent(BaseModel):
    headline: str | None = None
    subtitle: str | None = None
    offer: str | None = None
    price: str | None = None
    cta: str | None = None
    footnote: str | None = None
    named_slots: dict[str, str] = Field(default_factory=dict)
```

### 8.3 Standard Exact Text Slots

The following paths map to first-class `TextContent` fields:

```text
exact_text.headline → TextContent.headline
exact_text.subtitle → TextContent.subtitle
exact_text.offer    → TextContent.offer
exact_text.price    → TextContent.price
exact_text.cta      → TextContent.cta
exact_text.footnote → TextContent.footnote
```

### 8.4 Non-Standard Exact Text Slots

Any `exact_text.*` path not listed above must map into `TextContent.named_slots`.

Examples:

```text
exact_text.event_time              → named_slots["event_time"]
exact_text.location                → named_slots["location"]
exact_text.contact                 → named_slots["contact"]
exact_text.account_or_brand_name   → named_slots["account_or_brand_name"]
exact_text.message                 → named_slots["message"]
exact_text.date_or_period          → named_slots["date_or_period"]
exact_text.package_lines           → named_slots["package_lines"]
exact_text.validity_period         → named_slots["validity_period"]
exact_text.body                    → named_slots["body"]
exact_text.effective_date          → named_slots["effective_date"]
exact_text.time_period             → named_slots["time_period"]
exact_text.registration_instruction→ named_slots["registration_instruction"]
```

Rules:

```text
preserve line order
preserve price strings
preserve dates and contact text
trim only leading/trailing whitespace unless the field is multiline
normalize CRLF to LF
never summarize exact_text fields automatically
```

### 8.5 Context Fields

Paths under `context.*` must be copied to:

```text
request.scenario_selection.parameters.common_scene_context
```

and may be copied into:

```text
GeneralCommonSceneResolution.metadata.context_summary
CreativeJob.metadata["common_scene_context"]
```

Context fields may inform planning, segmentation, and visual direction. They are not guaranteed to be rendered verbatim unless promoted into `exact_text` by user action or the text renderer later returns them as editable slots.

Examples:

```text
context.product_or_service_name
context.selling_points
context.topic
context.key_points
context.steps
context.comparison_items
context.safe_text_side
context.direction_count
context.brand_traits
context.target_audience
```

### 8.6 Controls Fields

Paths under `controls.*` are behavioral controls, not rendered copy.

First-release controls:

```text
controls.negative_directions
```

### 8.7 Negative Direction Normalization

Input may be a textarea, chip list, or array. Normalize into `list[str]`.

Splitting delimiters:

```text
new line
Chinese comma: ，
English comma: ,
Chinese semicolon: ；
English semicolon: ;
Chinese pause mark: 、
```

Rules:

```text
trim whitespace
discard empty items
de-duplicate case-insensitively for ASCII text
preserve original wording
preserve original raw text in metadata.raw_negative_directions
limit first-release normalized items to 20
if over limit, keep first 20 and return a warning
```

Mapping:

```text
controls.negative_directions
→ GeneralCreativeDraft.negative_directions
→ CreateCreativeJobRequest.scenario_selection.parameters.controls.negative_directions
→ CreativeJob.explicit_constraints where appropriate
→ CreativePlan.negative_direction where existing agents accept it
```

### 8.8 Field Path Validation

The preset registry validator must reject:

```text
duplicate field ids within the same preset
unknown target root path
invalid exact_text path syntax
invalid context path syntax
invalid controls path syntax
unsupported field type
field id that differs only by case from another field id in the same preset
```

Canonical target roots:

```text
exact_text
context
controls
metadata
```

### 8.9 Canonical Knowledge Card Field List

The canonical first-release `knowledge_card_infographic` field list is:

```text
title
intro
key_points
steps
comparison_items
source_note
cta
```

`comparison_items` appears exactly once in the preset field registry.

Any duplicate mention in prose, examples, or UI copy must be treated as non-canonical documentation text and must not create duplicate field definitions.

---

## 9. Content Segmentation for Structured Common Scenes

### 9.1 Why Segmentation Is Needed

Some common scenes are inherently multi-card or content-heavy:

```text
Knowledge Card / Infographic
Service Package / Price Card
Announcement / Notice
Event Invitation / Registration
Recruitment Poster
```

The system must not silently truncate long content.

The application layer must normalize and segment structured content before the existing SeriesPlanner receives the request.

### 9.2 DTOs

```python
ContentRole = Literal[
    "title",
    "intro",
    "bullet_point",
    "step",
    "comparison_item",
    "package_line",
    "notice_body",
    "event_detail",
    "job_requirement",
    "footer_note",
    "cta",
    "other"
]

class ContentBlock(BaseModel):
    block_id: str
    source_field_id: str
    role: ContentRole
    order: int
    text: str
    exact: bool = False
    metadata: dict = Field(default_factory=dict)

class ContentSegment(BaseModel):
    segment_id: str
    title: str | None = None
    blocks: list[ContentBlock] = Field(default_factory=list)
    intended_asset_purpose: str | None = None
    intended_asset_index: int | None = None
    metadata: dict = Field(default_factory=dict)

class ContentSegmentationResult(BaseModel):
    segmentation_policy_id: str
    scene_id: str
    source_fields: list[str] = Field(default_factory=list)
    segments: list[ContentSegment] = Field(default_factory=list)
    suggested_asset_count: int | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
```

### 9.3 Exact vs Context Segmentation

Exact text fields:

```text
must not be summarized automatically
must not be silently truncated
may be split only when the field semantics permit line-level preservation
must preserve original order and text
```

Context fields:

```text
may be summarized by the existing creative agents when necessary
must preserve source text in metadata if summarized
must return a warning when content is materially compressed
```

### 9.4 First-Release Segmentation Policies

#### `segmentation.none`

Used by:

```text
free_create
campaign_poster
web_banner_hero
festival_seasonal_visual
announcement_notice when content is short
```

Behavior:

```text
one segment or no explicit segments
SeriesPlanner uses core defaults
```

#### `segmentation.by_visual_direction`

Used by:

```text
brand_style_exploration
```

Behavior:

```text
create N direction segments
N = context.direction_count when valid
N default = 3
N min = 2
N max = 4
```

Each segment should carry:

```text
visual direction index
brand traits
avoid directions
optional color preferences
```

#### `segmentation.by_bullets_or_steps`

Used by:

```text
knowledge_card_infographic
```

Behavior:

```text
parse key_points into bullet ContentBlocks
parse steps into ordered step ContentBlocks
parse comparison_items into comparison ContentBlocks
create 2 to 6 content segments when enough content exists
```

Default limits:

```text
max blocks per card: 4
max body characters per card: 360 for zh-CN, 520 for en-US
max first-release card count: 6
```

If content exceeds the maximum:

```text
create first 6 segments
add warning: content_over_first_release_card_limit
preserve full source content in metadata
suggest user continue or reduce content
```

#### `segmentation.by_package_lines`

Used by:

```text
service_package_price_card
```

Behavior:

```text
split package_lines by line
preserve line order and prices
single asset if all lines fit
multi-card series only when content exceeds layout capacity and mode allows auto series
```

Default limits:

```text
single price-card line count: 8
max first-release price-card assets: 3
```

#### `segmentation.by_notice_sections`

Used by:

```text
announcement_notice
```

Behavior:

```text
preserve notice body as exact named slot when submitted under exact_text.body
segment into headline, effective date, body, time period, contact, footnote
use single asset by default
warn if notice body exceeds layout capacity
```

#### `segmentation.by_event_details`

Used by:

```text
event_invitation_registration
```

Behavior:

```text
segment event name, time, location, agenda, registration instruction, CTA
single invitation by default
may create supporting social cover in auto series mode
```

#### `segmentation.by_recruitment_sections`

Used by:

```text
recruitment_poster
```

Behavior:

```text
segment position, benefits, requirements, location, contact, CTA
single recruitment poster by default
```

### 9.5 Segmentation Output Mapping

The segmentation result is copied to:

```text
request.scenario_selection.parameters.content_segmentation
CreativeJob.metadata["content_segmentation"]
SeriesPlan.metadata["content_segmentation"]
AssetSpec.metadata["content_segment_id"] where an asset maps to a segment
```

It should not add new required fields to `SeriesPlan` or `AssetSpec`.

### 9.6 User-Facing Warning Requirements

The UI must show warnings when:

```text
content was split into multiple assets
content exceeds first-release card count
content may overflow a single layout
context fields may be summarized by creative planning
exact text cannot fit without typography reflow
```

Warnings must be attached to the job and, where possible, to affected assets.

---

## 10. Preset-to-Execution Canonical Mapping

This section defines the canonical first-release mapping for the initial General Quick-Start Preset catalog.

All `asset_type` values below must use frozen V3 `AssetType` values.

All `platform` values must use frozen V3 `Platform` values.

All aspect ratios must be normalized through `AspectRatioSelection` before reaching core schemas.

### 10.1 Mapping Table

| Preset id | Creative task type | Series shape | Default asset count | Allowed core asset types | Default platform hint | Segmentation policy |
|---|---|---|---:|---|---|---|
| `free_create` | `free_create` | `core_default` | core default | core default | core default | `segmentation.none` |
| `campaign_poster` | `campaign_poster` | `single_asset` | 1 | `main_poster`, `campaign_banner`, `single_image` | `generic` | `segmentation.none` |
| `product_service_showcase` | `product_or_service_showcase` | `small_asset_series` | 3 | `single_image`, `main_poster`, `campaign_banner` | `generic` | `segmentation.none` |
| `social_media_visual` | `social_media_visual` | `small_asset_series` | 3 | `social_cover`, `wechat_moments_poster`, `single_image` | `generic_social` | `segmentation.none` |
| `web_banner_hero` | `web_banner_hero` | `banner_only` | 1 | `campaign_banner`, `single_image` | `generic` | `segmentation.none` |
| `festival_seasonal_visual` | `festival_or_seasonal_visual` | `small_asset_series` | 3 | `main_poster`, `social_cover`, `campaign_banner` | `generic_social` | `segmentation.none` |
| `brand_style_exploration` | `brand_style_exploration` | `visual_direction_set` | `direction_count` default 3 | `brand_style_sample`, `single_image` | `generic` | `segmentation.by_visual_direction` |
| `knowledge_card_infographic` | `knowledge_card_or_infographic` | `multi_card_series` | derived, default 3 | `single_image`, `social_cover` | `generic_social` | `segmentation.by_bullets_or_steps` |
| `service_package_price_card` | `service_package_or_price_card` | `single_asset` or `multi_card_series` | 1, derived up to 3 | `single_image`, `main_poster` | `generic` | `segmentation.by_package_lines` |
| `announcement_notice` | `announcement_or_notice` | `single_asset` | 1 | `single_image`, `main_poster` | `generic` | `segmentation.by_notice_sections` |
| `event_invitation_registration` | `event_invitation_or_registration` | `single_asset` | 1 | `main_poster`, `single_image` | `generic` | `segmentation.by_event_details` |
| `recruitment_poster` | `recruitment_poster` | `single_asset` | 1 | `main_poster`, `single_image` | `generic` | `segmentation.by_recruitment_sections` |

### 10.2 Purpose Hints

Purpose hints are human-readable planning hints, not enum values.

They should be copied into:

```text
GeneralCommonSceneResolution.requested_asset_purposes
AssetSpec.purpose
AssetSpec.metadata["general_common_scene_purpose"]
```

Canonical first-release purpose hints:

| Preset id | Purpose hints |
|---|---|
| `campaign_poster` | `primary campaign poster` |
| `product_service_showcase` | `primary showcase`, `feature highlight`, `usage or benefit visual` |
| `social_media_visual` | `social cover`, `feed visual`, `story visual` |
| `web_banner_hero` | `website hero banner` |
| `festival_seasonal_visual` | `seasonal key visual`, `social greeting visual`, `campaign banner` |
| `brand_style_exploration` | `visual direction A`, `visual direction B`, `visual direction C`, `visual direction D` |
| `knowledge_card_infographic` | `knowledge card cover`, `knowledge card content`, `knowledge card summary` |
| `service_package_price_card` | `price card`, `package comparison`, `offer terms` |
| `announcement_notice` | `notice poster` |
| `event_invitation_registration` | `event invitation` |
| `recruitment_poster` | `recruitment poster` |

### 10.3 Requested Asset Count Rules

#### Free Create

```text
requested_asset_count = null
requested_series_shape = core_default
```

The existing core default applies.

#### Single-Asset Presets

```text
requested_asset_count = 1
requested_series_shape = single_asset or banner_only
```

If the user explicitly requests multiple outputs, the user request wins, but the scene resolution must record the override.

#### Small Asset Series

```text
requested_asset_count = 3
requested_asset_count_min = 2
requested_asset_count_max = 4
```

Used for general showcase, social media, and seasonal visuals.

#### Brand Style Exploration

```text
requested_asset_count = context.direction_count
min = 2
max = 4
default = 3
```

Each output must represent a distinct visual direction, but all directions must remain under the same business and brand brief.

#### Knowledge Card / Infographic

```text
requested_asset_count = content_segmentation.suggested_asset_count
min = 1
max = 6
default = 3 when sufficient content exists
```

If no structured content exists, the planner may create a cover plus two generic content-card concepts, but must warn that the user provided limited content.

---

## 11. Draft-to-Request Closure

### 11.1 Updated GeneralCreativeDraft

Document 18 defined `GeneralCreativeDraft`. Document 19 added `preset_id`
conceptually. Document 20 freezes the application-level draft shape:

```python
class GeneralCreativeDraft(BaseModel):
    mode_id: str = "auto_commercial_series"
    preset_id: str | None = None
    preset_version: str | None = None

    user_input: str = ""

    optional_brand_id: str | None = None
    optional_template_id: str | None = None
    uploaded_asset_ids: list[str] = Field(default_factory=list)

    target_platforms: list[str] = Field(default_factory=list)
    aspect_ratio: str | None = None
    custom_dimensions: dict | None = None

    exact_text: dict[str, str] = Field(default_factory=dict)
    context: dict = Field(default_factory=dict)
    controls: dict = Field(default_factory=dict)
    negative_directions: list[str] = Field(default_factory=list)

    metadata: dict = Field(default_factory=dict)
```

This draft remains frontend/application-layer only.

### 11.2 Request Mapping

The final request must use the existing document-16 envelope:

```python
class CreateCreativeJobRequest(BaseModel):
    user_input: str
    optional_brand_id: str | None = None
    optional_template_id: str | None = None
    uploaded_asset_ids: list[str] = Field(default_factory=list)
    explicit_constraints: list[str] = Field(default_factory=list)

    scenario_selection: ScenarioSelection | None = None
    metadata: dict = Field(default_factory=dict)
```

Mapping:

```text
draft.user_input
→ request.user_input

draft.optional_brand_id
→ request.optional_brand_id

draft.optional_template_id
→ request.optional_template_id

draft.uploaded_asset_ids
→ request.uploaded_asset_ids

draft.mode_id
→ request.scenario_selection.mode_id

draft.preset_id / preset_version
→ request.scenario_selection.parameters.quick_start_preset

general_common_scene_resolution
→ request.scenario_selection.parameters.general_common_scene_resolution

field_normalization_result.exact_text
→ request.scenario_selection.parameters.exact_text

field_normalization_result.context
→ request.scenario_selection.parameters.common_scene_context

field_normalization_result.controls
→ request.scenario_selection.parameters.controls

content_segmentation_result
→ request.scenario_selection.parameters.content_segmentation

aspect_ratio_selection
→ request.scenario_selection.parameters.aspect_ratio_selection
```

### 11.3 ScenarioSelection Example

```json
{
  "pack_id": "general_creative",
  "mode_id": "auto_commercial_series",
  "source": "explicit_ui",
  "allow_general_fallback": false,
  "parameters": {
    "quick_start_preset": {
      "preset_id": "knowledge_card_infographic",
      "preset_version": "1.0.0"
    },
    "general_common_scene_resolution": {
      "common_scene_id": "general.knowledge_card_infographic.v1",
      "creative_task_type": "knowledge_card_or_infographic",
      "requested_series_shape": "multi_card_series",
      "requested_asset_count": 3,
      "requested_asset_count_min": 1,
      "requested_asset_count_max": 6,
      "requested_asset_purposes": [
        "knowledge card cover",
        "knowledge card content",
        "knowledge card summary"
      ],
      "segmentation_policy_id": "segmentation.by_bullets_or_steps",
      "source": "explicit_user_preset",
      "visible_to_user": true
    },
    "exact_text": {
      "headline": "3 steps to choose the right plan",
      "subtitle": "A quick checklist",
      "cta": "Save this"
    },
    "common_scene_context": {
      "key_points": "Budget\nFeatures\nSupport\nUpgrade path\nHidden costs"
    },
    "content_segmentation": {
      "segmentation_policy_id": "segmentation.by_bullets_or_steps",
      "scene_id": "knowledge_card_infographic",
      "suggested_asset_count": 3
    }
  },
  "metadata": {
    "ui_surface": "general_quick_start_gallery"
  }
}
```

---

## 12. SeriesPlan and AssetSpec Handoff Rules

### 12.1 No New Core Schema Fields

The SeriesPlanner must continue to output the existing `SeriesPlan` and `AssetSpec` structures.

The scene resolution may influence them through:

```text
existing user input
existing explicit constraints
existing metadata
existing purpose field
existing asset_type enum
existing platform enum
existing aspect_ratio enum
```

### 12.2 AssetSpec Hints

When an asset is created because of a common scene resolution, attach metadata:

```python
AssetSpec.metadata["general_common_scene"] = {
    "common_scene_id": "general.knowledge_card_infographic.v1",
    "preset_id": "knowledge_card_infographic",
    "content_segment_id": "seg_002",
    "purpose_hint": "knowledge card content",
    "source": "explicit_user_preset"
}
```

Do not expose internal provider settings.

### 12.3 Allowed AssetType Values

Only use frozen V3 AssetType values such as:

```text
main_poster
social_cover
wechat_moments_poster
campaign_banner
brand_style_sample
single_image
```

Do not introduce:

```text
knowledge_card
price_card
recruitment_card
website_banner_hero
```

as new `AssetType` enum values in this phase.

If a product-specific name is needed, put it in:

```text
AssetSpec.purpose
AssetSpec.metadata["purpose_hint"]
```

### 12.4 Allowed Platform Values

Use frozen V3 Platform values such as:

```text
generic
generic_social
wechat_moments
xiaohongshu
store_screen
print_poster
```

General Quick-Start Presets should usually use:

```text
generic
generic_social
print_poster
```

They must not imply platform-specific rules such as Taobao, Amazon, or TikTok unless the user explicitly names the platform. Even then, General Creative should pass the named platform as a target hint, not activate a vertical specialization pack.

### 12.5 Existing DefaultCommercialPack Binding

All common-scene executions remain bound to:

```text
GeneralCreativeScenarioPack
DefaultCommercialPack
```

Preset-driven outputs are allowed to differ from free-create outputs only because the user explicitly selected a visible scene card or supplied explicit API parameters.

---

## 13. Text Revision Activation API

### 13.1 Problem

Document 18 defines:

```text
POST /jobs/{job_id}/assets/{asset_id}/render-revisions
GET  /jobs/{job_id}/assets/{asset_id}/render-revisions
```

It also says users can restore previous render revisions.

Document 20 adds the missing activation route.

### 13.2 Route

```text
POST /api/v3/creative-agent/jobs/{job_id}/assets/{asset_id}/render-revisions/{revision_id}/activate
```

### 13.3 Request DTO

```python
class ActivateRenderRevisionRequest(BaseModel):
    run_id: str | None = None
    expected_job_version: int | None = None
    expected_active_revision_id: str | None = None
    metadata: dict = Field(default_factory=dict)
```

### 13.4 Response DTO

```python
class ActivateRenderRevisionResponse(BaseModel):
    job_id: str
    asset_id: str
    active_render_revision_id: str
    previous_active_render_revision_id: str | None = None
    job_version: int
    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
```

### 13.5 Behavior

```text
activation changes the active pointer only
activation does not delete render revision history
activation does not regenerate the base visual
activation does not call image providers
activation may re-run export packaging metadata if needed
activation must be auditable
```

### 13.6 Idempotency

If the requested revision is already active:

```text
return 200
return current active revision
include warning or metadata: already_active = true
```

### 13.7 Concurrency

If `expected_job_version` is supplied and stale:

```text
return 409 conflict
preserve draft state
return current job_version and active_render_revision_id
```

If `expected_active_revision_id` is supplied and does not match the current active revision:

```text
return 409 conflict
```

### 13.8 Error Cases

| Case | Status | Behavior |
|---|---:|---|
| job not found | 404 | no mutation |
| asset not found in job | 404 | no mutation |
| revision not found for asset | 404 | no mutation |
| revision belongs to another asset | 409 | no mutation |
| job cancelled | 409 | no mutation |
| unauthorized | 403 | no mutation |

---

## 14. UI Closure Requirements

### 14.1 Preset Summary Before Submit

Before job creation, the UI should show a compact summary:

```text
Scene: Knowledge Card
Mode: Auto series
Expected output: 3 cards, derived from your key points
Ratio: 4:5
Text rendering: editable exact text layer
Brand: selected brand or temporary brand
```

This summary is important because scene resolution is treated as a visible user constraint.

### 14.2 Warnings Before Submit

The UI should warn when:

```text
ratio will be treated as custom
long content will be split into multiple assets
content exceeds first-release card count
some context fields may be summarized by planning agents
required display text is likely too long for a single layout
```

The user does not need to approve every warning, but the warning must be visible and stored in job metadata.

### 14.3 Editable Result Slots

After generation, the text editor should include:

```text
standard slots: headline, subtitle, offer, price, cta, footnote
named slots returned by backend
content-segment slots when segmentation produced multiple cards
```

The UI must not hide named slots such as:

```text
event_time
location
contact
package_lines
body
registration_instruction
```

### 14.4 Render Revision Restore UI

The text editor must provide:

```text
revision history list
current active marker
restore action
conflict handling if another tab changed the active revision
```

The restore action uses the route in section 13.

### 14.5 Free Create Regression UI

When no preset is selected:

```text
show no forced scene summary
keep user input as the dominant intent
use existing General Creative defaults
```

---

## 15. Backend Services to Add or Finalize

### 15.1 `GeneralCommonSceneResolutionService`

Responsibilities:

```text
resolve preset_id and preset_version
merge preset defaults with explicit user selections
build GeneralCommonSceneResolution
select segmentation policy
validate asset counts
emit user-visible summary and warnings
```

### 15.2 `AspectRatioNormalizationService`

Responsibilities:

```text
validate selected ratio
map unsupported display ratios to custom
produce AspectRatioSelection
reject invalid custom dimensions
```

### 15.3 `GeneralPresetFieldNormalizer`

Responsibilities:

```text
normalize exact_text fields
map non-standard exact_text fields to named_slots
copy context fields
normalize controls
normalize negative directions
preserve raw field values
return warnings
```

### 15.4 `ContentSegmentationService`

Responsibilities:

```text
parse structured text fields
create ContentBlock objects
split content into ContentSegment objects
suggest asset count
return overflow warnings
preserve exact text
```

### 15.5 `RenderRevisionActivationService`

Responsibilities:

```text
validate revision ownership
activate previous render revision
handle idempotency
handle optimistic concurrency
record audit event
```

### 15.6 Recommended Module Paths

```text
alchemy_creative_agent_3_0/app/general_common_scenes/
  __init__.py
  models.py
  resolution_service.py
  aspect_ratio_normalizer.py
  field_normalizer.py
  content_segmenter.py
  preset_execution_map.py
  validators.py

alchemy_creative_agent_3_0/app/services/
  render_revision_activation_service.py
```

Frontend paths may be adapted to the actual UI stack, but should remain V3-owned.

---

## 16. API Additions and Validation Endpoints

### 16.1 Existing Routes Reused

The main job route remains:

```text
POST /api/v3/creative-agent/jobs
```

No preset-specific generation route is allowed.

### 16.2 Optional Preset Resolution Preview

To let the UI show a deterministic summary before job creation, an optional validation/preview endpoint may be added under the existing V3 namespace:

```text
POST /api/v3/creative-agent/scenario-packs/general_creative/presets/{preset_id}/resolve-preview
```

Request:

```python
class ResolveGeneralPresetPreviewRequest(BaseModel):
    draft: GeneralCreativeDraft
    locale: str = "zh-CN"
    metadata: dict = Field(default_factory=dict)
```

Response:

```python
class ResolveGeneralPresetPreviewResponse(BaseModel):
    preset_id: str | None = None
    preset_version: str | None = None
    scene_resolution: GeneralCommonSceneResolution
    aspect_ratio_selection: AspectRatioSelection | None = None
    field_normalization: GeneralPresetFieldNormalizationResult
    content_segmentation: ContentSegmentationResult | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
```

Rules:

```text
preview must not create a job
preview must not call providers
preview must not mutate brand memory
preview may use registry and validation services only
```

This endpoint is optional but recommended for better UI transparency.

### 16.3 Render Revision Activation Route

Required for document-17 behavior completeness:

```text
POST /api/v3/creative-agent/jobs/{job_id}/assets/{asset_id}/render-revisions/{revision_id}/activate
```

---

## 17. Worked Examples

### 17.1 Knowledge Card With Five Points

User action:

```text
Selects Knowledge Card / Infographic
Adds title, intro, five key points, CTA
Chooses 4:5
Starts generation
```

Resolution:

```text
creative_task_type = knowledge_card_or_infographic
requested_series_shape = multi_card_series
segmentation_policy_id = segmentation.by_bullets_or_steps
suggested_asset_count = 3
```

Expected assets:

```text
Asset 1: knowledge card cover
Asset 2: key points 1-3
Asset 3: key points 4-5 + summary / CTA
```

Core-safe mapping:

```text
asset_type = single_image or social_cover
platform = generic_social
aspect_ratio = 4:5
```

### 17.2 Website Banner With 3:1 Ratio

User action:

```text
Selects Website Banner / Hero
Chooses 3:1
Adds headline, subtitle, CTA
```

Aspect mapping:

```json
{
  "display_ratio": "3:1",
  "core_aspect_ratio": "custom",
  "custom_dimensions": {
    "width": 1800,
    "height": 600,
    "ratio": "3:1",
    "unit": "px"
  }
}
```

Expected asset:

```text
asset_type = campaign_banner
platform = generic
purpose = website hero banner
```

### 17.3 Brand Style Exploration

User action:

```text
Selects Brand Style Exploration
Sets direction_count = 3
Provides target audience, brand traits, preferred colors, and avoid directions
```

Resolution:

```text
creative_task_type = brand_style_exploration
requested_series_shape = visual_direction_set
requested_asset_count = 3
segmentation_policy_id = segmentation.by_visual_direction
```

Expected assets:

```text
Asset 1: visual direction A
Asset 2: visual direction B
Asset 3: visual direction C
```

Rules:

```text
all directions share the same brand/business brief
directions should differ in visual tone or composition strategy
saving any direction to persistent brand memory still requires explicit document-17 confirmation
```

### 17.4 Price Card With Exact Package Lines

User action:

```text
Selects Service Package / Price Card
Inputs package_lines as multiline exact text
```

Mapping:

```text
exact_text.package_lines
→ TextContent.named_slots["package_lines"]
```

Rules:

```text
preserve line order
preserve price strings
text-only revision can edit package_lines later
if too long, warn before generation or split into multiple assets when mode allows
```

### 17.5 Restoring a Previous Text Revision

User action:

```text
Opens text editor
Views revision history
Restores an older revision
```

Backend route:

```text
POST /api/v3/creative-agent/jobs/{job_id}/assets/{asset_id}/render-revisions/{revision_id}/activate
```

Expected behavior:

```text
active pointer changes
base visual remains unchanged
revision history remains intact
job version increments
```

---

## 18. Test Requirements

### 18.1 Unit Tests

Implement tests for:

```text
AspectRatioNormalizationService maps 21:9, 3:1, 2:1 to custom
AspectRatioNormalizationService rejects invalid custom ratios
GeneralPresetFieldNormalizer maps standard exact_text slots correctly
GeneralPresetFieldNormalizer maps non-standard exact_text fields into named_slots
GeneralPresetFieldNormalizer preserves package_lines line order
GeneralPresetFieldNormalizer normalizes negative_directions into list[str]
Preset registry rejects duplicate field ids
Preset registry rejects invalid field target roots
ContentSegmentationService segments key_points and steps into multiple segments
ContentSegmentationService preserves exact text fields
RenderRevisionActivationService activates existing revisions idempotently
```

### 18.2 Integration Tests

Implement tests for each initial preset:

```text
free_create
campaign_poster
product_service_showcase
social_media_visual
web_banner_hero
festival_seasonal_visual
brand_style_exploration
knowledge_card_infographic
service_package_price_card
announcement_notice
event_invitation_registration
recruitment_poster
```

Each test must verify:

```text
scenario_selection.pack_id = general_creative
DefaultCommercialPack remains selected
preset version is pinned
GeneralCommonSceneResolution is present when preset_id is present
all AssetSpec.asset_type values are from the frozen enum
all AssetSpec.platform values are from the frozen enum
all AssetSpec.aspect_ratio values are from the frozen enum
unsupported display ratios map to custom
common-scene metadata is attached
no provider is called by preset resolution
```

### 18.3 Regression Tests

Free Create regression fixture:

```text
no preset_id
same user_input
same brand context
same uploaded assets
```

Expected:

```text
CommercialBrief, CreativePlan, SeriesPlan, LayoutPlan, PromptCompilationResult, and CommercialAssetPack remain equivalent to document-17 baseline, except allowed audit metadata.
```

### 18.4 End-to-End UI Tests

Cover:

```text
selecting a preset updates fields but does not auto-submit
user can override recommended mode and aspect ratio
custom banner ratio summary is visible before submit
long knowledge-card content shows segmentation warning
job creation carries pinned preset and scene resolution
text editor shows named slots
render revision restore calls the activation route
free-create has no forced scene summary
```

### 18.5 Contract Tests

Add contract tests ensuring:

```text
no new required core schema fields were introduced
no invalid AspectRatio values enter core schemas
no invalid AssetType values enter core schemas
no invalid Platform values enter core schemas
GeneralCommonSceneResolution stays in application metadata and scenario parameters
preset resolution never calls providers
brand memory is not applied during preset resolution
```

---

## 19. Acceptance Gates Before Future Specialization Docs

Future specialization-pack documents must not start until all gates below are satisfied.

### Gate 1: General Runtime Gate

Document 18 is implemented or accepted as the authoritative development spec for:

```text
workspace UI
job runtime
candidate actions
text revision creation
brand memory confirmation
export
```

### Gate 2: Quick-Start Preset Gate

Document 19 is implemented or accepted as the authoritative development spec for:

```text
preset gallery
preset catalog
preset dynamic fields
preset version pinning
preset-to-draft mapping
```

### Gate 3: Execution Closure Gate

This document is implemented or accepted as the authoritative development spec for:

```text
GeneralCommonSceneResolution
aspect ratio normalization
field normalization
content segmentation
preset-to-SeriesPlan / AssetSpec execution hints
render revision activation
```

### Gate 4: No-Conflict Gate

The combined 18 + 19 + 20 docs must satisfy:

```text
no new core pipeline
no new provider route
no hidden prompt patch
no unsupported core enum values
no direct vertical pack activation from General Creative presets
no silent brand-memory application
no text truncation without warning
```

### Gate 5: General Module Freeze Gate

After gates 1-4 pass, the General Creative module is frozen enough to begin:

```text
future ecommerce scenario-pack specification
```

---

## 20. Implementation Checklist

```text
[ ] Add GeneralCommonSceneResolution DTO
[ ] Add AspectRatioSelection and CustomDimensions DTOs
[ ] Add GeneralPresetFieldNormalizationResult DTO
[ ] Add ContentBlock / ContentSegment / ContentSegmentationResult DTOs
[ ] Add GeneralCommonSceneResolutionService
[ ] Add AspectRatioNormalizationService
[ ] Add GeneralPresetFieldNormalizer
[ ] Add ContentSegmentationService
[ ] Add RenderRevisionActivationService
[ ] Add optional preset resolve-preview route
[ ] Add render-revision activate route
[ ] Update job creation service to run preset resolution before ScenarioRuntime execution
[ ] Store scene resolution in scenario_selection.parameters and metadata
[ ] Ensure free_create without preset remains baseline-compatible
[ ] Add registry validation for duplicate field ids
[ ] Add tests for all initial presets
[ ] Add enum-validity tests for AssetType, Platform, AspectRatio
[ ] Add E2E test for Knowledge Card segmentation
[ ] Add E2E test for Website Banner custom ratio
[ ] Add E2E test for render revision activation
```

---

## 21. Final Non-Negotiable Summary

```text
Document 20 closes the gap between preset selection and executable creative planning.
It treats quick-start preset selection as a visible user constraint.
It does not create a new runtime, provider route, template engine, or vertical pack.
It maps common scenes into existing V3 schemas using metadata, purpose hints, and explicit constraints.
It guarantees that unsupported UI ratios are normalized to core-safe custom ratios.
It guarantees that exact text and named slots are handled consistently.
It prevents silent truncation of structured content.
It adds the missing render-revision activation route required by the document-17 UI behavior.
With documents 18, 19, and 20 accepted together, the General Creative module is complete enough to begin a future E-Commerce specialization document.
```
