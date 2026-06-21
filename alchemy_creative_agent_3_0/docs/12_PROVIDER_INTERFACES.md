# 12 Provider Interfaces

This document defines provider interfaces for future V3 integrations.

V3.0 foundation does not need real heavy providers, but it should define stable interfaces so later integrations do not rewrite the core architecture.

## 1. Provider Principle

Alchemy Creative Agent 3.0 owns the product logic.

External projects are optional providers.

Correct direction:

```text
Creative Core → V3 provider interface → provider adapter → external model/tool
```

Incorrect direction:

```text
Creative Core directly depends on IP-Adapter / ControlNet / ComfyUI internals
```

## 2. Common Provider Requirements

Every provider should expose:

```text
provider_name
provider_version
capabilities
is_available()
health_check()
```

Provider output should include metadata:

```text
provider_name
provider_version
runtime_config_summary
warnings
errors
```

Providers must fail gracefully.

## 3. Capability Descriptor

Recommended fields:

```text
name: str
version: str
supports_generation: bool
supports_style_conditioning: bool
supports_layout_conditioning: bool
supports_identity_conditioning: bool
supports_scoring: bool
supports_text_rendering: bool
supports_batch: bool
requires_gpu: bool
requires_network: bool
is_deterministic: bool
metadata: dict
```

V3 core should route based on capabilities, not provider names only.

## 4. GenerationProvider

Purpose:

```text
Generate or mock image candidates from prompt and condition plans.
```

Interface concept:

```python
class GenerationProvider:
    def capabilities(self) -> ProviderCapabilities: ...
    def generate(self, request: GenerationRequest) -> GenerationResponse: ...
```

GenerationRequest fields:

```text
asset_spec
layout_plan
prompt_compilation
condition_plan
generation_plan
metadata
```

GenerationResponse fields:

```text
candidates: list[CandidateResult]
provider_metadata: dict
warnings: list[str]
```

First-pass providers:

```text
PlanningOnlyGenerationProvider
MockGenerationProvider
```

Future providers:

```text
GPTImageProvider
FluxProvider
RecraftProvider
SDXLProvider
ComfyUISidecarProvider
DiffusersProvider
```

## 5. StyleConditionProvider

Purpose:

```text
Create style conditioning payloads from BrandProfile and reference assets.
```

Interface concept:

```python
class StyleConditionProvider:
    def build_style_condition(self, request: StyleConditionRequest) -> StyleConditionResponse: ...
```

Request fields:

```text
brand_profile
asset_spec
creative_plan
reference_assets
strength
metadata
```

Response fields:

```text
condition_spec
provider_payload
warnings
metadata
```

First-pass providers:

```text
NoopStyleConditionProvider
SimpleReferenceStyleProvider
```

Future providers:

```text
InstantStyleProvider
IPAdapterProvider
```

Rules:

- Normal users never choose provider manually.
- BrandMemoryAgent and GenerationRouterAgent decide if style conditioning is needed.
- If no reference assets exist, provider should return disabled condition.

## 6. LayoutConditionProvider

Purpose:

```text
Create spatial or structural conditioning payloads from LayoutPlan.
```

Interface concept:

```python
class LayoutConditionProvider:
    def build_layout_condition(self, request: LayoutConditionRequest) -> LayoutConditionResponse: ...
```

Request fields:

```text
asset_spec
layout_plan
creative_plan
strength
metadata
```

Response fields:

```text
condition_spec
layout_map
provider_payload
warnings
metadata
```

First-pass providers:

```text
NoopLayoutConditionProvider
RuleBasedLayoutMapProvider
```

Future providers:

```text
ControlNetProvider
PosterLayoutProvider
ComfyUILayoutProvider
```

Rules:

- The user should not draw control maps.
- LayoutAgent should create structure automatically.
- LayoutConditionProvider should convert structure into provider-specific payload later.

## 7. IdentityConditionProvider

Purpose:

```text
Maintain person, character, model, or spokesperson identity.
```

Interface concept:

```python
class IdentityConditionProvider:
    def build_identity_condition(self, request: IdentityConditionRequest) -> IdentityConditionResponse: ...
```

Future providers:

```text
PhotoMakerProvider
InstantIDProvider
EasyPhotoProvider
```

V3.0 / V3.1:

```text
Not required. Use NoopIdentityConditionProvider.
```

Privacy rule:

```text
Real-person identity conditioning must require explicit user-provided assets and future consent handling.
```

## 8. ProductConditionProvider

Purpose:

```text
Maintain product appearance, packaging, or SKU identity.
```

Potential future providers:

```text
IPAdapterProductProvider
ReferenceProductProvider
ProductMaskProvider
```

Use cases:

```text
fixed milk tea cup packaging
fixed e-commerce product
fixed restaurant dish photo
fixed brand mascot
```

V3.0:

```text
Noop provider only.
```

## 9. ScoringProvider

Purpose:

```text
Score candidate images or planning outputs.
```

Interface concept:

```python
class ScoringProvider:
    def score(self, request: ScoringRequest) -> EvaluationReport: ...
```

Request fields:

```text
candidate
asset_spec
commercial_brief
brand_profile
creative_plan
layout_plan
prompt_compilation
metadata
```

Response:

```text
EvaluationReport
```

First-pass providers:

```text
MockScoringProvider
RuleBasedPlanningScorer
```

Future providers:

```text
ImageRewardProvider
VisionLLMCommercialCritic
BrandConsistencyScorer
LayoutVisionScorer
TextRegionScorer
```

Rules:

- Scoring outputs must normalize to EvaluationReport.
- Real scoring providers should not change core schema.

## 10. PromptOptimizationProvider

Purpose:

```text
Improve prompts, layout notes, or condition strategies when evaluation fails.
```

Interface concept:

```python
class PromptOptimizationProvider:
    def propose_refinement(self, request: RefinementRequest) -> RefinementPlan: ...
```

First-pass providers:

```text
RuleBasedRefinementProvider
```

Future providers:

```text
GenPilotInspiredProvider
PromptSculptorInspiredProvider
T2ICopilotInspiredProvider
```

Rules:

- Refinement must produce structured RefinementPlan.
- No hidden prompt rewriting without metadata.

## 11. RendererProvider

Purpose:

```text
Render accurate text overlays and final poster assets.
```

Interface concept:

```python
class RendererProvider:
    def render(self, request: RenderRequest) -> RenderResponse: ...
```

Request fields:

```text
base_visual_candidate
layout_plan
asset_spec
text_content
typography_strategy
metadata
```

Response fields:

```text
rendered_asset
manifest_entry
warnings
metadata
```

First-pass providers:

```text
NoopRendererProvider
HTMLSpecRenderer
```

Future providers:

```text
HTMLPosterRenderer
SVGPosterRenderer
CanvasRenderer
```

Rules:

- For Chinese commercial posters, accurate external text rendering is preferred.
- Model-generated final Chinese text should be avoided unless provider is proven reliable.

## 12. WorkflowSidecarProvider

Purpose:

```text
Allow heavy workflow tools to run outside V3 core.
```

Future providers:

```text
ComfyUISidecarProvider
DiffusersSidecarProvider
```

Rules:

```text
1. Sidecars are optional.
2. Sidecars must implement V3 interfaces.
3. Core tests must pass without sidecars.
4. Sidecar failure must degrade gracefully.
5. No user-facing node graph is required.
```

## 13. Noop Provider Requirements

Every provider category should have a Noop or Mock provider.

Purpose:

```text
allow offline testing
allow planning-only mode
avoid heavy dependencies in V3.0 foundation
```

Noop providers should:

```text
return disabled conditions
return planning-only candidates
return deterministic mock scores
record metadata
not raise unless input schema is invalid
```

## 14. Provider Selection Policy

GenerationRouterAgent should select providers by:

```text
1. task need
2. platform requirement
3. brand memory requirement
4. text rendering requirement
5. provider capability
6. runtime availability
7. cost / speed policy later
```

First-pass policy:

```text
always select planning_only providers
```

V3.2 policy:

```text
select mock or configured generation provider
```

V3.4+ policy:

```text
select style/layout/identity providers when needed
```

## 15. Provider Error Handling

Provider errors should become structured warnings or provider failure problems.

Do not crash the entire pipeline unless:

```text
schema is invalid
required planning output is missing
all providers fail and no fallback exists
```

Recommended provider failure problem code:

```text
provider_failure
```

## 16. Provider Metadata

Every provider result should include:

```text
provider_name
provider_version
capabilities_used
runtime_mode
warnings
cost_estimate later
latency_ms later
```

## 17. V3.0 Provider Goal

Implement:

```text
PlanningOnlyGenerationProvider
NoopStyleConditionProvider
NoopLayoutConditionProvider
NoopIdentityConditionProvider
MockScoringProvider
NoopRendererProvider
```

## 18. V3.1 Provider Goal

Implement:

```text
RuleBasedLayoutMapProvider
SimpleReferenceStyleProvider
RuleBasedPlanningScorer
RuleBasedRefinementProvider
HTMLSpecRenderer
```

## 19. V3.2 Provider Goal

Implement:

```text
MockGenerationProvider or first real GenerationProvider
candidate ranking
refinement loop execution
asset packaging with generated or mock files
```

## 20. V3.3+ Provider Goal

Integrate optional heavy providers:

```text
ImageRewardProvider
IPAdapterProvider
InstantStyleProvider
ControlNetProvider
ComfyUISidecarProvider
DiffusersProvider
```

## 21. Required Tests

Tests should verify:

```text
1. Noop providers return valid schemas
2. provider capabilities serialize
3. GenerationRouterAgent selects planning_only provider in V3.0
4. StyleConditionProvider disables when no references exist
5. LayoutConditionProvider can produce Noop condition
6. ScoringProvider returns EvaluationReport
7. RendererProvider can produce render spec without real rendering
8. provider failure creates structured problem
9. V3 core tests do not require heavy dependencies
```