# 07 Schema Contracts

> **Current text-image direction (2026-07-13):** [Doc111](111_V3_PROVIDER_NATIVE_TEXT_AND_ECOMMERCE_CREATIVE_DIRECTION_CORRECTION.md) supersedes any external-overlay, local-font, fixed-copy-region, or deterministic text-rendering contract in this historical schema document. New work uses LLM creative direction and provider-native complete-image generation.

This document freezes the first-pass V3 schema contracts before Codex starts implementation.

The goal is to reduce implementation ambiguity and prevent Codex from inventing incompatible field names.

## 1. Schema Contract Principles

1. V3 schemas are V3-owned.
2. V3 schemas must not import or extend V1/V2 schemas.
3. All schemas should be serializable to JSON.
4. All major schemas should preserve metadata.
5. All generated decisions should be auditable.
6. First-pass schemas may be simple, but field names should be stable.

Recommended implementation: Pydantic models.

## 2. Shared Types and Enums

### 2.1 Locale

```text
zh-CN
en-US
unknown
```

Default:

```text
zh-CN
```

### 2.2 Platform

```text
xiaohongshu
wechat_moments
delivery_app
meituan
eleme
taobao
jd
douyin
ecommerce_generic
store_screen
print_poster
generic_social
generic
```

### 2.3 AspectRatio

Represent as string.

Allowed first-pass values:

```text
1:1
3:4
4:5
9:16
16:9
A4
custom
```

### 2.4 IndustryCategory

```text
beverage
restaurant_barbecue
restaurant_hotpot
restaurant_general
ecommerce_product
local_service_beauty
local_service_general
personal_brand
education
hospitality
unknown
```

### 2.5 AssetType

```text
main_poster
social_cover
wechat_moments_poster
delivery_cover
ecommerce_main_image
product_detail_banner
group_buying_image
store_screen_image
campaign_banner
brand_style_sample
single_image
```

### 2.6 TextRenderingMode

```text
html_overlay
svg_overlay
canvas_overlay
model_text_allowed
no_text
unknown
```

Default for poster-like assets:

```text
html_overlay
```

### 2.7 ProviderStrategy

```text
auto
planning_only
mock_generation
default_image_provider
reference_conditioned_provider
layout_conditioned_provider
external_renderer_only
```

First-pass default:

```text
planning_only
```

### 2.8 Recommendation

```text
accept
retry
reject
manual_review
planning_only
```

### 2.9 Severity

```text
info
warning
error
hard_failure
```

## 3. Base Metadata Rules

Any major schema may include:

```python
metadata: dict = Field(default_factory=dict)
```

Metadata should be used for:

- source agent
- rule ids
- confidence
- inferred defaults
- provider notes
- timestamps if available
- refinement history
- warnings

Do not hide important decisions in free-form logs only.

## 4. CreativeJob

Purpose:

```text
Represents the user's raw request and initial V3 job context.
```

Required fields:

```text
job_id: str
raw_user_input: str
locale: Locale = "zh-CN"
optional_brand_id: str | None = None
optional_template_id: str | None = None
uploaded_asset_ids: list[str] = []
requested_output: str = "commercial_image_series"
explicit_constraints: list[str] = []
implicit_constraints: list[str] = []
requires_clarification: bool = False
clarification_questions: list[str] = []
metadata: dict = {}
```

Rules:

- `job_id` may use deterministic prefix such as `job_` plus uuid.
- `requires_clarification` should default to false.
- First-pass implementation should avoid clarification unless the request is unusable.

## 5. CommercialBrief

Purpose:

```text
Converts user intent into commercial strategy.
```

Required fields:

```text
brief_id: str
job_id: str
industry: IndustryCategory
scenario: str
business_goal: str
target_platforms: list[Platform]
target_audience: str | None = None
commercial_hooks: list[str] = []
selling_points: list[str] = []
visual_tone: list[str] = []
copy_strategy: str | None = None
platform_notes: dict = {}
risks: list[str] = []
confidence: float = 0.0
metadata: dict = {}
```

Rules:

- `confidence` is 0.0 to 1.0.
- If no platform is detected, use default platforms from rules.
- `visual_tone` should include normalized style words such as `clean`, `fresh`, `premium`, `appetite`, `high_contrast`, `tech`.

## 6. BrandProfile

Purpose:

```text
Stores brand identity, style memory, preference memory, and reference assets.
```

Required fields:

```text
brand_id: str
brand_name: str | None = None
industry: IndustryCategory | None = None
is_temporary: bool = True
visual_tone: list[str] = []
color_palette: list[str] = []
layout_preference: str | None = None
typography_preference: str | None = None
copywriting_tone: str | None = None
reference_assets: list[ReferenceAsset] = []
successful_asset_ids: list[str] = []
rejected_style_tags: list[str] = []
platform_history: list[Platform] = []
metadata: dict = {}
```

ReferenceAsset fields:

```text
asset_id: str
asset_type: str
source: str
purpose: str | None = None
style_tags: list[str] = []
file_path: str | None = None
uri: str | None = None
score: float | None = None
metadata: dict = {}
```

Rules:

- Temporary brand profiles can be created from CommercialBrief.
- Persistent brand profiles should be loaded from V3-owned storage only.
- No V2 state should be used.

## 7. CreativePlan

Purpose:

```text
Defines the art direction and commercial creative direction for the job.
```

Required fields:

```text
creative_plan_id: str
job_id: str
brief_id: str
brand_id: str | None = None
concept: str
visual_direction: str
composition_strategy: str
lighting_strategy: str | None = None
color_strategy: list[str] = []
materials_and_props: list[str] = []
copy_strategy: str | None = None
consistency_strategy: str | None = None
negative_direction: list[str] = []
metadata: dict = {}
```

Rules:

- CreativePlan should be influenced by BrandProfile when available.
- It should not be just an expanded prompt.
- It should describe commercial design decisions.

## 8. SeriesPlan and AssetSpec

Purpose:

```text
Defines the set of commercial assets to produce.
```

SeriesPlan required fields:

```text
series_plan_id: str
job_id: str
assets: list[AssetSpec]
series_strategy: str | None = None
metadata: dict = {}
```

AssetSpec required fields:

```text
asset_id: str
asset_type: AssetType
platform: Platform
aspect_ratio: AspectRatio
purpose: str
priority: int = 1
requires_text_overlay: bool = True
requires_brand_consistency: bool = True
metadata: dict = {}
```

Rules:

- If the user names platforms, create assets for those platforms.
- If no platform is named, create default assets.
- First-pass default series count should be 3 unless platform-specific request implies more.

## 9. LayoutPlan

Purpose:

```text
Defines composition and typography layout for one AssetSpec.
```

Required fields:

```text
layout_plan_id: str
asset_id: str
platform: Platform
aspect_ratio: AspectRatio
text_rendering: TextRenderingMode = "html_overlay"
visual_hierarchy: list[str] = []
product_area: LayoutRegion
headline_area: LayoutRegion | None = None
subtitle_area: LayoutRegion | None = None
cta_area: LayoutRegion | None = None
logo_area: LayoutRegion | None = None
reserved_text_regions: list[LayoutRegion] = []
typography_strategy: str | None = None
background_strategy: str | None = None
metadata: dict = {}
```

LayoutRegion fields:

```text
name: str
position: str
priority: int = 1
relative_box: dict | None = None
notes: str | None = None
```

First-pass `relative_box` format:

```json
{"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
```

Rules:

- Poster-like assets should default to `html_overlay`.
- LayoutPlan should reserve clean text regions.
- PromptCompilationResult should reference these regions.

## 10. PromptCompilationResult

Purpose:

```text
Compiles CreativePlan + LayoutPlan + BrandProfile into provider-neutral prompt instructions.
```

Required fields:

```text
prompt_compilation_id: str
asset_id: str
visual_prompt: str
negative_prompt: str | None = None
hard_constraints: list[str] = []
text_policy: str
style_notes: list[str] = []
layout_notes: list[str] = []
provider_notes: dict = {}
metadata: dict = {}
```

Required provider note for poster-like assets:

```text
Generate the product / background / atmosphere only. Reserve clean regions for real text overlay. Do not render fake final Chinese text inside the image.
```

Rules:

- Should include brand tone when BrandProfile exists.
- Should include platform and aspect ratio notes.
- Should avoid fake text when external rendering is planned.

## 11. ConditionPlan

Purpose:

```text
Defines optional style, layout, identity, or product conditioning.
```

Required fields:

```text
condition_plan_id: str
asset_id: str
style_condition: ConditionSpec | None = None
layout_condition: ConditionSpec | None = None
identity_condition: ConditionSpec | None = None
product_condition: ConditionSpec | None = None
metadata: dict = {}
```

ConditionSpec fields:

```text
enabled: bool
provider: str
reference_asset_ids: list[str] = []
strength: float | None = None
notes: str | None = None
metadata: dict = {}
```

First-pass default:

```text
Noop provider with enabled=false, unless reference assets exist.
```

## 12. GenerationPlan

Purpose:

```text
Defines how candidates should be generated or planned.
```

Required fields:

```text
generation_plan_id: str
asset_id: str
provider_strategy: ProviderStrategy = "planning_only"
candidate_count: int = 4
quality_threshold: float = 0.78
max_refine_rounds: int = 2
scorers: list[str] = []
rendering_required: bool = False
metadata: dict = {}
```

Rules:

- First-pass can use `planning_only`.
- Candidate count should default to 4 for real generation later.
- Do not execute real image generation in V3.0 foundation.

## 13. CandidateResult

Purpose:

```text
Represents one generated or mock candidate.
```

Required fields:

```text
candidate_id: str
asset_id: str
file_path: str | None = None
uri: str | None = None
provider: str | None = None
prompt_compilation_id: str | None = None
condition_plan_id: str | None = None
is_mock: bool = True
metadata: dict = {}
```

## 14. EvaluationReport

Purpose:

```text
Normalizes scoring and critique for one candidate or planning output.
```

Required fields:

```text
evaluation_id: str
candidate_id: str | None = None
asset_id: str
aesthetic_score: float
commercial_score: float
brand_consistency_score: float
layout_score: float
text_region_score: float
platform_fit_score: float
overall_score: float
recommendation: Recommendation
problems: list[EvaluationProblem] = []
metadata: dict = {}
```

EvaluationProblem fields:

```text
code: str
message: str
severity: Severity
repair_hint: str | None = None
metadata: dict = {}
```

Rules:

- Scores are 0.0 to 1.0.
- First-pass mock evaluation must be deterministic.

## 15. RefinementPlan

Purpose:

```text
Defines what to change if a candidate is weak.
```

Required fields:

```text
refinement_plan_id: str
asset_id: str
source_evaluation_id: str
action: Recommendation
prompt_modifications: list[str] = []
layout_modifications: list[str] = []
condition_modifications: list[str] = []
provider_modifications: list[str] = []
reason: str | None = None
metadata: dict = {}
```

Rules:

- `action` should normally be `retry`, `reject`, or `manual_review`.
- Refinement steps must be auditable.

## 16. CommercialAssetPack

Purpose:

```text
Packages final or planned outputs for the user.
```

Required fields:

```text
asset_pack_id: str
job_id: str
brand_id: str | None = None
assets: list[PackagedAsset] = []
manifest: dict = {}
brand_memory_update: MemoryUpdate | None = None
planning_only: bool = True
metadata: dict = {}
```

PackagedAsset fields:

```text
asset_id: str
asset_type: AssetType
platform: Platform
aspect_ratio: AspectRatio
purpose: str
file_path: str | None = None
uri: str | None = None
layout_plan_id: str | None = None
prompt_compilation_id: str | None = None
evaluation_id: str | None = None
metadata: dict = {}
```

## 17. MemoryUpdate

Purpose:

```text
Represents proposed or applied updates to BrandProfile.
```

Required fields:

```text
memory_update_id: str
brand_id: str
action: str
accepted_asset_ids: list[str] = []
new_reference_assets: list[ReferenceAsset] = []
new_style_tags: list[str] = []
new_rejected_style_tags: list[str] = []
notes: str | None = None
applied: bool = False
metadata: dict = {}
```

Rules:

- V3.0 foundation may create proposed updates only.
- Do not apply updates from mock rejected candidates.

## 18. PlanningResult Optional Wrapper

For the foundation milestone, returning a planning wrapper is acceptable.

Recommended fields:

```text
planning_result_id: str
creative_job: CreativeJob
commercial_brief: CommercialBrief
brand_profile: BrandProfile
creative_plan: CreativePlan
series_plan: SeriesPlan
layout_plans: list[LayoutPlan]
prompt_compilations: list[PromptCompilationResult]
condition_plans: list[ConditionPlan]
generation_plans: list[GenerationPlan]
evaluation_reports: list[EvaluationReport]
asset_pack: CommercialAssetPack
metadata: dict = {}
```

## 19. Required Contract Tests

Codex should implement tests that verify:

```text
1. all schemas serialize to dict/json
2. all required ids exist
3. score fields are normalized between 0 and 1
4. text_rendering defaults to html_overlay for posters
5. ProviderStrategy defaults to planning_only in V3.0
6. BrandProfile can be temporary
7. CommercialAssetPack can be planning_only
8. no V3 schema imports V1/V2 modules
```
