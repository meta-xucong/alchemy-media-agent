# 02 System Architecture

This document defines the target architecture for Alchemy Creative Agent 3.0.

## 1. Architecture Principle

V3 is an independent commercial creative system.

It should not be designed as a single prompt enhancer.

It should be designed as a multi-agent creative production pipeline:

```text
Natural Language Input
  ↓
Intent Understanding Agent
  ↓
Commercial Brief Builder
  ↓
Brand Memory Engine
  ↓
Creative Director Agent
  ↓
Series Planner
  ↓
Layout & Typography Planner
  ↓
Prompt Compiler
  ↓
Reference Conditioning Engine
  ↓
Generation Router
  ↓
Candidate Scoring + Critic + Refinement Loop
  ↓
Commercial Asset Pack
```

Each layer should have explicit inputs, outputs, schemas, and metadata.

## 2. Core Concept: Creative Core

The central system should be called:

```text
Creative Core
```

Creative Core owns:

- business intent interpretation
- commercial brief generation
- brand memory usage
- creative planning
- asset series planning
- layout planning
- prompt compilation
- generation planning
- scoring and refinement coordination
- final asset manifest generation

Creative Core is the V3 product brain.

It does not directly depend on V2.

## 3. Core Intermediate Representation

V3 must define its own intermediate representation, or IR.

The IR should separate business meaning from provider implementation.

Recommended core schemas:

```text
CreativeJob
CommercialBrief
BrandProfile
CreativePlan
SeriesPlan
AssetSpec
LayoutPlan
PromptCompilationResult
ConditionPlan
GenerationPlan
CandidateResult
EvaluationReport
RefinementPlan
CommercialAssetPack
MemoryUpdate
```

The IR is the most important architectural layer because it allows V3 to replace providers without rewriting product logic.

For example:

```text
InstantStyle can be replaced later.
IP-Adapter can be replaced later.
ControlNet can be replaced later.
ImageReward can be replaced later.
GPT Image can be replaced later.
```

The product contract should remain stable.

## 4. High-Level Data Flow

### 4.1 Input

```json
{
  "user_input": "帮我做一组奶茶店夏季新品促销图，要清爽、高级一点，适合小红书和外卖平台。",
  "optional_brand_id": "brand_123",
  "optional_template_id": null,
  "optional_assets": []
}
```

### 4.2 CreativeJob

```json
{
  "job_id": "job_001",
  "raw_user_input": "...",
  "language": "zh-CN",
  "requested_output": "commercial_image_series",
  "constraints": [],
  "metadata": {}
}
```

### 4.3 CommercialBrief

```json
{
  "industry": "beverage",
  "scenario": "summer_new_product_promotion",
  "business_goal": "drive attention and purchase",
  "target_platforms": ["xiaohongshu", "delivery_app"],
  "target_audience": "young local consumers",
  "commercial_hooks": ["summer freshness", "new product", "limited offer"],
  "tone": ["fresh", "clean", "premium"]
}
```

### 4.4 BrandProfile

```json
{
  "brand_id": "brand_123",
  "brand_name": "茶小满",
  "industry": "beverage",
  "visual_tone": ["fresh", "clean", "young"],
  "color_palette": ["mint green", "cream white", "warm yellow"],
  "layout_preference": "center product, top headline, bottom CTA",
  "reference_assets": ["asset_best_001"],
  "negative_style": ["dark cyberpunk", "messy background"]
}
```

### 4.5 CreativePlan

```json
{
  "concept": "夏日清爽新品上市",
  "visual_direction": "bright commercial beverage photography",
  "composition_strategy": "large centered product with clean text area",
  "lighting": "soft daylight with refreshing highlights",
  "materials": ["ice", "fruit", "condensation", "clean gradient background"],
  "copy_strategy": "short Chinese headline with clear offer"
}
```

### 4.6 SeriesPlan

```json
{
  "assets": [
    {
      "asset_id": "main_poster",
      "platform": "xiaohongshu",
      "ratio": "4:5",
      "purpose": "social cover and campaign poster"
    },
    {
      "asset_id": "delivery_cover",
      "platform": "delivery_app",
      "ratio": "1:1",
      "purpose": "delivery platform product image"
    }
  ]
}
```

### 4.7 LayoutPlan

```json
{
  "asset_id": "main_poster",
  "text_rendering": "html_overlay",
  "headline": {
    "text": "夏日新品 清爽上市",
    "position": "top_center",
    "priority": 1
  },
  "product_area": {
    "position": "center",
    "size": "large"
  },
  "cta": {
    "text": "今日下单立减 8 元",
    "position": "bottom_right",
    "priority": 2
  },
  "reserved_text_regions": ["top_20_percent", "bottom_20_percent"]
}
```

### 4.8 PromptCompilationResult

```json
{
  "asset_id": "main_poster",
  "visual_prompt": "A clean premium summer milk tea commercial product shot...",
  "negative_prompt": "messy background, unreadable text, distorted cup, low quality...",
  "text_policy": "do_not_render_final_text_in_image_model",
  "provider_notes": {
    "reserve_clean_text_areas": true,
    "avoid_fake_chinese_text": true
  }
}
```

### 4.9 ConditionPlan

```json
{
  "style_condition": {
    "enabled": true,
    "provider": "style_reference_provider",
    "reference_assets": ["asset_best_001"],
    "strength": 0.65
  },
  "layout_condition": {
    "enabled": true,
    "provider": "layout_map_provider",
    "strength": 0.5
  },
  "identity_condition": {
    "enabled": false
  }
}
```

### 4.10 GenerationPlan

```json
{
  "candidate_count": 6,
  "provider_strategy": "auto",
  "quality_threshold": 0.78,
  "max_refine_rounds": 2,
  "scorers": [
    "aesthetic_scorer",
    "commercial_critic",
    "brand_consistency_scorer",
    "layout_scorer"
  ]
}
```

### 4.11 EvaluationReport

```json
{
  "candidate_id": "candidate_003",
  "overall_score": 0.84,
  "aesthetic_score": 0.86,
  "commercial_score": 0.82,
  "brand_consistency_score": 0.79,
  "layout_score": 0.88,
  "problems": [],
  "recommendation": "accept"
}
```

### 4.12 CommercialAssetPack

```json
{
  "job_id": "job_001",
  "assets": [
    {
      "asset_id": "main_poster",
      "platform": "xiaohongshu",
      "file": "main_poster.png",
      "purpose": "campaign cover"
    }
  ],
  "brand_profile_update": {
    "new_reference_asset": "main_poster.png",
    "style_notes": ["fresh", "clean", "premium"]
  },
  "manifest": {}
}
```

## 5. Module Layers

### 5.1 creative_core

Owns orchestration.

Responsibilities:

- accepts user input
- creates CreativeJob
- calls intent, brief, brand, creative, layout, prompt, generation, scoring, and refinement modules
- returns CommercialAssetPack

### 5.2 schemas

Owns all V3 Pydantic models.

Must not import V2 schemas.

### 5.3 agents

Owns all V3 agent contracts and prompt specifications.

Suggested agents:

- IntentAgent
- CommercialStrategyAgent
- BrandMemoryAgent
- CreativeDirectorAgent
- SeriesPlannerAgent
- LayoutAgent
- PromptCompilerAgent
- GenerationRouterAgent
- CriticRefinerAgent

### 5.4 brand_memory

Owns persistent brand profiles and historical preference memory.

Responsibilities:

- read brand profile
- create new brand profile
- update profile based on selected outputs
- store reference assets
- summarize successful visual patterns

### 5.5 layout_engine

Owns commercial layout and text rendering plans.

Responsibilities:

- layout JSON generation
- platform-specific aspect ratio handling
- text region reservation
- HTML / SVG / Canvas rendering in future implementation

### 5.6 prompt_compiler

Owns provider-neutral prompt compilation.

Responsibilities:

- compile CreativePlan + LayoutPlan + BrandProfile into provider-ready visual prompts
- preserve hard constraints
- avoid final text rendering when external text rendering is required
- produce metadata

### 5.7 condition_engine

Owns style, reference, layout, and identity conditioning plans.

Responsibilities:

- select reference assets
- choose style strength
- choose layout conditioning
- prepare provider-specific conditioning payloads

External projects such as InstantStyle, IP-Adapter, ControlNet, PhotoMaker, and InstantID should be implemented here later as providers, not core dependencies.

### 5.8 generation_router

Owns provider selection.

Responsibilities:

- choose generation backend
- choose batch size
- choose retry strategy
- create candidate records

### 5.9 evaluation

Owns scoring and critique.

Responsibilities:

- aesthetic score
- commercial score
- brand consistency score
- layout score
- text risk score
- final accept/reject decision

External projects such as ImageReward may be integrated here later.

### 5.10 asset_pack

Owns final output packaging.

Responsibilities:

- asset manifest
- platform names
- aspect ratios
- final files
- metadata export
- brand memory update payload

## 6. Provider Interface Pattern

Each external capability should implement a V3-owned interface.

Example:

```python
class StyleConditionProvider:
    def build_condition(self, brand_profile, asset_spec, creative_plan):
        ...
```

Example implementations:

```text
InstantStyleProvider
IPAdapterProvider
SimpleReferenceProvider
NoopStyleProvider
```

Core code should depend on `StyleConditionProvider`, not directly on InstantStyle or IP-Adapter.

## 7. Refinement Loop

The refinement loop should work as follows:

```text
1. Generate candidates.
2. Score candidates.
3. Select best candidate.
4. If score >= threshold, accept.
5. If score < threshold and retries remain:
   a. CriticRefinerAgent analyzes problems.
   b. Produce RefinementPlan.
   c. Update prompt / layout / condition / provider strategy.
   d. Generate again.
6. If retries exhausted, return best candidate with warnings.
```

The system should never hide refinement steps. All refinements must be saved in metadata.

## 8. Text Rendering Strategy

For poster-like outputs, V3 should prefer:

```text
background / product visual generated by image model
+
accurate text rendered by layout engine
```

The prompt compiler should instruct the image model to reserve clean regions and avoid fake text.

## 9. Brand Memory Update Strategy

After completion, the system should update brand memory only when there is a successful output.

Possible update signals:

- user selected an image
- image score passed threshold
- commercial critic accepted output
- user reused the style later

Brand memory should not blindly store every generated candidate.

## 10. Architecture Non-Goals

V3 foundation should not initially include:

- video generation
- canvas UI
- node editor UI
- full ComfyUI embedding
- large GPU provider integration in the core service
- direct runtime import from V2

## 11. Definition of Architectural Success

The architecture is successful if:

```text
1. Every major step has a structured schema.
2. Every external capability is behind a provider interface.
3. Brand memory is first-class.
4. Layout and text are separated from raw image generation.
5. Prompt compilation is provider-neutral.
6. Candidate scoring and refinement are built into the workflow.
7. V3 runs independently from V2.
```