# 10 Brand Memory Spec

This document defines how Alchemy Creative Agent 3.0 should implement brand memory and consistency.

Brand memory is a first-class V3 capability. It is not a cosmetic feature.

## 1. Purpose

The system should not generate isolated beautiful images.

It should build commercial continuity across time:

```text
same brand tone
same visual direction
same color logic
same layout preference
same copywriting tone
same product appearance when references exist
same platform-appropriate commercial structure
```

Brand memory allows the user to say:

```text
沿用上次风格
还是那个奶茶店风格
继续做端午节活动图
换成小红书版本
```

and receive consistent outputs.

## 2. Independence Rule

V3 brand memory must be stored and read by V3-owned code only.

Forbidden:

```text
reading V2 user_variables
reading V2 generation records directly
using V2 ImagePromptPlan as memory object
sharing V2 provider state
```

Allowed:

```text
copy useful ideas from V2 into V3-owned schemas
manually import old assets later through a V3 import tool
```

## 3. First-Pass Storage

Use a simple local JSON store for V3.0 / V3.1.

Recommended path:

```text
alchemy_creative_agent_3_0/data/brand_memory/
```

Recommended file structure:

```text
alchemy_creative_agent_3_0/data/brand_memory/
  brands/
    brand_<id>.json
  references/
    <brand_id>/
      reference_manifest.json
```

If the repository should not commit runtime data, add `.gitkeep` only and ensure generated memory files are ignored later.

## 4. Brand ID Rules

Brand id format:

```text
brand_<short_uuid>
```

Temporary brand id format:

```text
temp_brand_<job_id>
```

Rules:

```text
1. If optional_brand_id exists and is found, load persistent profile.
2. If optional_brand_id exists but is not found, create temporary profile and emit warning metadata.
3. If no optional_brand_id exists, create temporary profile from CommercialBrief.
4. Temporary profile can influence the current job but should not be persisted unless explicitly promoted later.
```

## 5. BrandProfile Fields

Use the schema defined in `07_SCHEMA_CONTRACTS.md`.

Important fields:

```text
brand_id
brand_name
industry
is_temporary
visual_tone
color_palette
layout_preference
typography_preference
copywriting_tone
reference_assets
successful_asset_ids
rejected_style_tags
platform_history
metadata
```

## 6. How Brand Memory Is Created

### 6.1 From CommercialBrief

If no brand exists, create a temporary profile:

```text
industry ← CommercialBrief.industry
visual_tone ← CommercialBrief.visual_tone
platform_history ← CommercialBrief.target_platforms
copywriting_tone ← CommercialBrief.copy_strategy
color_palette ← industry/tone default if available
layout_preference ← platform/industry default
```

### 6.2 From User Assets Later

Later versions may create BrandProfile from:

```text
logo
old poster
product image
store photo
preferred generated image
manual brand colors
```

This is not required in V3.0 foundation.

## 7. How Brand Memory Influences Planning

### 7.1 CommercialBrief

BrandProfile may refine:

```text
visual_tone
platform priorities
copywriting tone
commercial risks
```

### 7.2 CreativePlan

BrandProfile should influence:

```text
visual_direction
composition_strategy
color_strategy
consistency_strategy
negative_direction
```

### 7.3 LayoutPlan

BrandProfile should influence:

```text
layout preference
typography preference
logo area
text hierarchy
```

### 7.4 PromptCompilationResult

BrandProfile should appear in:

```text
style_notes
hard_constraints
provider_notes
metadata
```

Example provider note:

```text
Preserve the brand tone: fresh, clean, premium. Use mint green and cream white as the main visual palette.
```

### 7.5 ConditionPlan

If reference assets exist, BrandProfile may enable:

```text
style_condition
product_condition
identity_condition
```

First pass may create a Noop or planning-only condition.

## 8. Reference Asset Policy

Reference assets should be explicit records, not raw hidden file paths.

Each reference asset should have:

```text
asset_id
asset_type
source
purpose
style_tags
file_path or uri
score
metadata
```

Possible asset types:

```text
logo
product_photo
previous_final_output
preferred_style_reference
store_photo
brand_color_reference
```

## 9. Memory Update Policy

Do not blindly update brand memory.

Allowed update signals:

```text
1. user explicitly selects a final image
2. candidate passes quality threshold and is accepted
3. user asks to keep this style
4. later analytics or feedback indicates success
```

Forbidden update signals:

```text
1. rejected candidate
2. mock candidate from planning-only phase
3. failed generation
4. low scoring output
5. temporary style exploration unless accepted
```

## 10. MemoryUpdate Lifecycle

A MemoryUpdate may be:

```text
proposed
applied
rejected
```

V3.0 foundation should usually produce proposed updates only.

V3.1 may apply updates for accepted outputs.

## 11. Temporary vs Persistent Brand Profiles

### Temporary Profile

Used for one job.

```text
is_temporary: true
```

Should not be saved by default.

### Persistent Profile

Used across jobs.

```text
is_temporary: false
```

Can be saved, loaded, updated, and used for continuation requests.

## 12. Continuation Request Rules

If user says:

```text
沿用上次风格
继续上次
保持之前风格
还是那个品牌风格
```

Then:

```text
1. If optional_brand_id exists, load it.
2. If no brand_id exists but local last-used brand exists later, use it with metadata warning.
3. If no brand can be resolved, create temporary profile and add warning.
```

V3.0 only needs to support optional_brand_id behavior.

## 13. Rejected Style Handling

If user says:

```text
不要太土
不要赛博
不要暗黑
不要杂乱
```

Store in:

```text
rejected_style_tags
negative_direction
```

These should influence future prompt compilation.

## 14. Brand Memory Tests

Required tests:

```text
1. temporary BrandProfile is created when no brand_id exists
2. persistent BrandProfile can be saved and loaded from V3-owned JSON store
3. missing brand_id creates warning metadata and temporary fallback
4. BrandProfile visual_tone influences CreativePlan
5. BrandProfile color_palette influences PromptCompilationResult
6. rejected_style_tags appear in negative prompt or negative direction
7. mock candidate does not update persistent memory
8. accepted output can produce proposed MemoryUpdate
9. V3 brand store imports no V1/V2 runtime modules
```

## 15. V3.1 Brand Memory Goal

V3.1 should make brand memory operational.

Required V3.1 deliverables:

```text
1. JSON-backed BrandProfile store
2. profile creation from CommercialBrief
3. profile loading by brand_id
4. profile influence on CreativePlan and PromptCompilationResult
5. proposed MemoryUpdate creation
6. tests for continuation behavior
```

## 16. V3.2 Brand Memory Goal

V3.2 should connect memory to generation results.

Required V3.2 deliverables:

```text
1. save accepted candidate as reference asset
2. update successful_asset_ids
3. update platform_history
4. record user-selected style tags
5. support style continuation across generated asset packs
```

## 17. Later Brand Memory Extensions

Future extensions:

```text
visual embedding extraction
color palette extraction from images
style tag extraction by vision model
brand reference strength recommendation
analytics-based memory update
multi-brand user workspace
asset library UI
```

These are not required before V3.2.