# 04 Open Source Reference Map

This document maps useful open-source projects and research directions to the Alchemy Creative Agent 3.0 architecture.

These projects are references and possible future providers.

They must not become the architecture itself.

## 1. Integration Principle

Alchemy 3.0 owns the core product contract.

External projects should be absorbed as optional provider implementations behind V3-owned interfaces.

Correct pattern:

```text
Alchemy Creative Core
  → V3 provider interface
    → external project adapter
```

Incorrect pattern:

```text
Alchemy 3.0 directly becomes a bundle of external repositories.
```

The system must remain independent, simple for the user, and replaceable at the provider level.

## 2. Reference Categories

```text
Brand / style consistency       → IP-Adapter, InstantStyle
Layout / structure control      → ControlNet, PosterLLaVA, PosterVerse
Identity / product consistency  → PhotoMaker, InstantID, EasyPhoto
Prompt optimization             → GenPilot, PromptSculptor, T2I-Copilot, GenAgent
Candidate scoring               → ImageReward, vision critic models
Default generation UX           → Fooocus
Backend workflow ideas          → ComfyUI, Diffusers
```

## 3. IP-Adapter

Repository:

```text
https://github.com/tencent-ailab/IP-Adapter
```

Core idea:

```text
Use images as prompts, not only text.
```

Why it matters:

IP-Adapter can help preserve brand style, product appearance, or prior successful visual patterns by conditioning generation on reference images.

Alchemy 3.0 usage:

```text
V3 module: condition_engine
V3 interface: StyleConditionProvider / ReferenceImageProvider
Possible provider: IPAdapterProvider
```

Use cases:

- preserve brand color and visual tone
- reuse best historical output as reference
- maintain product packaging appearance
- keep photography style consistent

Design warning:

Do not expose IP-Adapter controls to normal users.

The agent should decide:

- whether to use reference images
- which reference images to use
- reference strength
- when to reduce reference strength to avoid copying too much

## 4. InstantStyle

Repository:

```text
https://github.com/InstantStyle/InstantStyle
```

Core idea:

```text
Separate style from content when using reference images.
```

Why it matters:

Brand consistency usually requires preserving visual style, not copying the exact content of a reference image.

Alchemy 3.0 usage:

```text
V3 module: condition_engine
V3 interface: StyleConditionProvider
Possible provider: InstantStyleProvider
```

Use cases:

- preserve color palette
- preserve lighting
- preserve commercial photography tone
- preserve illustration style
- avoid unwanted content leakage from reference images

Design warning:

InstantStyle should be treated as a style-lock provider, not as the core product.

The BrandMemoryAgent should decide which reference assets are appropriate before style conditioning is applied.

## 5. ControlNet

Repository:

```text
https://github.com/lllyasviel/ControlNet
```

Core idea:

```text
Control diffusion generation with additional spatial conditions such as edges, depth, pose, masks, or layout-like maps.
```

Why it matters:

Prompt-only generation often causes layout drift.

Commercial images need stable structure:

- product area
- headline area
- CTA area
- logo area
- clean text regions
- platform-friendly composition

Alchemy 3.0 usage:

```text
V3 module: condition_engine / layout_engine
V3 interface: LayoutConditionProvider
Possible provider: ControlNetProvider
```

Use cases:

- keep product centered
- reserve text areas
- keep poster structure stable
- ensure consistent asset series layouts

Design warning:

The user should never manually draw ControlNet maps.

The LayoutAgent should create structure conditions automatically.

## 6. PosterLLaVA

Repository:

```text
https://github.com/posterllava/PosterLLaVA
```

Core idea:

```text
Generate poster layouts as structured multimodal layout data.
```

Why it matters:

Commercial posters are not just images. They are structured design layouts with text hierarchy, product focus, CTA placement, and visual balance.

Alchemy 3.0 usage:

```text
V3 module: layout_engine
V3 interface: PosterLayoutProvider / LayoutPlanner
```

Use cases:

- generate layout JSON
- decide title / product / CTA positions
- create editable poster structure
- guide text rendering later

Design warning:

Review dataset and license constraints before commercial model or data usage.

The safest first step is to absorb the layout-first design idea, not directly depend on datasets or weights.

## 7. PosterVerse

Reference direction:

```text
Text-to-poster pipeline with blueprint creation, background generation, and HTML-based layout-text rendering.
```

Core idea:

```text
Separate background / visual generation from accurate text rendering.
```

Why it matters:

Chinese commercial poster text must be accurate.

Image models often fail at:

- Chinese characters
- prices
- dates
- offer details
- phone numbers
- brand names

Alchemy 3.0 usage:

```text
V3 module: layout_engine / asset_pack
V3 interface: TypographyRenderer / HTMLPosterRenderer / SVGPosterRenderer
```

Use cases:

- render accurate Chinese text
- keep offer details correct
- output editable commercial posters
- avoid fake model-generated text

Design warning:

This should be a high-priority direction for Chinese commercial assets.

## 8. ImageReward

Repository:

```text
https://github.com/THUDM/ImageReward
```

Core idea:

```text
Score text-to-image outputs using a human preference reward model.
```

Why it matters:

Alchemy 3.0 should not return the first generated image blindly.

It should generate multiple candidates, score them, critique them, and refine when necessary.

Alchemy 3.0 usage:

```text
V3 module: evaluation
V3 interface: ScoringProvider
Possible provider: ImageRewardProvider
```

Use cases:

- rank generated candidates
- reject low-quality outputs
- trigger refinement loop
- combine with commercial critic and brand consistency scoring

Design warning:

ImageReward alone is not enough.

Commercial visual scoring should combine:

- aesthetic score
- business relevance
- brand consistency
- layout quality
- text-region quality
- platform suitability

## 9. GenPilot

Repository:

```text
https://github.com/27yw/GenPilot
```

Core idea:

```text
Use multi-agent test-time prompt optimization and feedback loops to improve image generation.
```

Why it matters:

Alchemy 3.0 should move beyond one-step prompt expansion.

It should support:

- problem detection
- candidate exploration
- fine-grained verification
- memory update
- iterative prompt / layout / condition refinement

Alchemy 3.0 usage:

```text
V3 module: evaluation / prompt_compiler / creative_core
V3 interface: PromptOptimizationProvider / RefinementPolicy
```

Use cases:

- improve weak outputs
- repair layout drift
- repair style drift
- adapt prompts for different providers
- remember successful prompt strategies

Design warning:

Do not copy a hidden prompt-refine loop without metadata.

Every refinement step must be auditable.

## 10. PromptSculptor / T2I-Copilot / GenAgent

Reference category:

```text
Agentic prompt optimization and tool-using text-to-image generation.
```

Core idea:

```text
Use agents to reason about prompt quality, tool selection, generation failures, and iterative correction.
```

Alchemy 3.0 usage:

```text
V3 module: agents / evaluation / generation_router
V3 interfaces:
- PromptCompilerAgent
- GenerationRouterAgent
- CriticRefinerAgent
```

Use cases:

- infer missing visual details
- choose tools automatically
- detect mismatches between user intent and result
- refine generation strategy

Design warning:

Agent reasoning should be converted into structured plans, not free-form hidden text.

## 11. PhotoMaker

Repository:

```text
https://github.com/TencentARC/PhotoMaker
```

Core idea:

```text
Fast identity-preserving personalized image generation.
```

Alchemy 3.0 usage:

```text
V3 module: condition_engine
V3 interface: IdentityConditionProvider
Possible provider: PhotoMakerProvider
```

Use cases:

- founder portrait posters
- personal brand images
- livestream seller images
- fixed model identity

Design warning:

Not a first-priority dependency for restaurant / e-commerce poster baseline, but useful later.

## 12. InstantID

Repository:

```text
https://github.com/InstantID/InstantID
```

Core idea:

```text
Preserve human identity using face embedding and control signals.
```

Alchemy 3.0 usage:

```text
V3 module: condition_engine
V3 interface: IdentityConditionProvider
Possible provider: InstantIDProvider
```

Use cases:

- owner image
- spokesperson image
- personal IP content

Design warning:

Requires careful consent and privacy handling if real people are used.

## 13. EasyPhoto

Repository:

```text
https://github.com/aigc-apps/sd-webui-EasyPhoto
```

Core idea:

```text
Personal portrait generation pipeline with face LoRA and templates.
```

Alchemy 3.0 usage:

```text
Future personal-brand or portrait module.
```

Design warning:

Not needed in V3 foundation.

## 14. StoryDiffusion / MasaCtrl

Repositories:

```text
https://github.com/HVision-NKU/StoryDiffusion
https://github.com/TencentARC/MasaCtrl
```

Core idea:

```text
Maintain consistency across multiple images or editing steps.
```

Alchemy 3.0 usage:

```text
V3 module: condition_engine / series_planner
Future interface: SeriesConsistencyProvider
```

Use cases:

- multi-image campaign consistency
- recurring character / mascot / brand world
- visual story sequence

Design warning:

Useful later, but not necessary for the first commercial poster foundation.

## 15. Fooocus

Repository:

```text
https://github.com/lllyasviel/Fooocus
```

Core idea:

```text
Good default generation experience for non-expert users.
```

Why it matters:

Fooocus is useful as a product philosophy reference:

- hide complex parameters
- provide strong defaults
- process prompts automatically
- reduce user burden

Alchemy 3.0 usage:

```text
V3 module: generation_router / prompt_compiler
Reference idea: default presets and non-expert UX
```

Design warning:

Do not copy a UI-heavy local generation app model. Absorb the default-simplicity philosophy.

## 16. ComfyUI

Repository:

```text
https://github.com/comfyanonymous/ComfyUI
```

Core idea:

```text
Modular backend workflow graph and queue for image generation.
```

Alchemy 3.0 usage:

```text
V3 module: generation_router
Possible future provider: ComfyUISidecarProvider
```

Useful ideas:

- workflow JSON
- queue execution
- node-like backend composability
- reproducible generation plans

Design warning:

Do not expose node workflows to normal users.

ComfyUI should be a backend sidecar idea, not the user experience.

## 17. Diffusers

Repository:

```text
https://github.com/huggingface/diffusers
```

Core idea:

```text
Composable diffusion pipelines and model integrations.
```

Alchemy 3.0 usage:

```text
V3 module: generation_router / condition_engine
Possible future provider: DiffusersProvider
```

Design warning:

Use as implementation backend only when needed. Do not let low-level model parameters leak into product UX.

## 18. Priority Recommendation

### Phase 1: Study and absorb ideas only

```text
PosterLLaVA / PosterVerse → layout-first commercial poster thinking
Fooocus → default-simple UX thinking
GenPilot → agentic refinement loop thinking
ImageReward → candidate scoring thinking
```

### Phase 2: Implement lightweight V3-owned interfaces

```text
StyleConditionProvider
LayoutConditionProvider
ScoringProvider
GenerationProvider
PromptOptimizationProvider
```

### Phase 3: Add optional providers

```text
ImageRewardProvider
SimpleReferenceProvider
HTMLTextRenderer
RuleBasedLayoutProvider
```

### Phase 4: Add heavy model sidecars

```text
IPAdapterProvider
InstantStyleProvider
ControlNetProvider
ComfyUISidecarProvider
DiffusersProvider
```

## 19. Final Rule

Open-source projects provide useful parts.

Alchemy 3.0 must provide the product brain.

The product brain is:

```text
commercial understanding
brand memory
creative planning
series planning
layout planning
prompt compilation
provider routing
candidate evaluation
refinement loop
asset packaging
```

Do not outsource this core to any external repository.