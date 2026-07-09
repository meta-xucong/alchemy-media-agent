# 76 V3 Foundation vs Specialized Template Governance

## 1. Purpose

This document is a long-term governance rule for V3 development.

It prevents a recurring drift:

```text
General Template receives too many scenario-specific suite/package rules.
Core visual modules become too heavy or too vertical-specific.
Specialized templates lose their reason to exist.
```

The accepted architecture is:

```text
V3 foundation quality layer
  -> General Template as simple, scenario-neutral creation entry
  -> Specialized templates as professional scenario packages
```

## 2. Core Rule

V3 must separate:

```text
universal visual quality capability
from
scenario-specific deliverable design
```

Short form:

```text
Foundation makes every image better.
General Template stays simple and neutral.
Specialized templates decide what a professional set should contain.
```

## 3. Foundation-Owned Capabilities

The following belong in the V3 foundation because every image or most templates
benefit from them:

```text
single-image aesthetics
prompt understanding and refinement
reference-image usage
identity/product/style consistency primitives
photorealism and anti-AI-feel rules
automatic curation / multi-generate-select-best
generated-image visual review
bounded retry
watermark/text/artifact detection
negative-prompt splitting and safety
provider prompt rendering quality
project memory and selected-result continuity
```

Foundation-owned code should normally live under:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/
alchemy_creative_agent_3_0/app/llm_brain/
alchemy_creative_agent_3_0/app/generation_router/
alchemy_creative_agent_3_0/app/product_api/ review and retry paths
alchemy_creative_agent_3_0/app/project_mode/ project context and memory paths
```

Foundation modules may expose knobs or contracts for templates, but they must
not hard-code one vertical's output taxonomy.

## 4. General Template Responsibility

The General Template is the default low-friction visual creation entry.

It should provide:

```text
one-sentence natural-language creation
optional reference image
simple project continuation
similar alternatives
basic suite expansion
creative exploration
format/layout adaptation
beginner-friendly result summaries
access to the foundation quality layer
```

It must not become:

```text
an ecommerce listing builder
a professional photographer package builder
a brand-kit generator
a storyboard/video campaign director
a social-media content calendar planner
```

General Template may support lightweight roles such as:

```text
cover hero
subject focus
angle variation
scene context
```

These roles are generic placeholders only. They are not a substitute for a
professional module's deliverable map.

## 5. Specialized Template Responsibility

Specialized templates own scenario-specific deliverables, suite direction, and
packaging.

Examples:

```text
E-Commerce Template:
  main image, white-background image, detail image, selling-point scene,
  lifestyle image, A+ module image, marketplace-safe export checks

Photography Template:
  cover portrait, half body, full body, profile/side angle, motion capture,
  emotional atmosphere, outfit variation, location variation, retouching style

Brand Template:
  logo, color system, typography direction, poster, packaging, social grid,
  brand guideline, export package

New Media Template:
  cover, thumbnail, carousel, short-video storyboard, copy-safe layout,
  platform crop variants
```

Specialized template code should live in its own Scenario Pack, template
workspace, or future vertical module. It may call foundation visual quality
capabilities, but it must own its own deliverable taxonomy and acceptance
criteria.

## 6. Decision Rule For New Features

Before adding a new feature, the developer must classify it:

```text
Question 1:
  Does this improve almost every generated image regardless of use case?
  -> Foundation capability.

Question 2:
  Does this define what images a specific professional scenario should output?
  -> Specialized template.

Question 3:
  Does this require guessing the user's hidden business/use case from a vague prompt?
  -> Do not put it in General Template. Keep General simple or ask/offer a mode.

Question 4:
  Is this only a light generic continuation mode?
  -> General Template can own it if it remains scenario-neutral.

Question 5:
  Would ecommerce, photography, brand, and new-media users disagree on the right output set?
  -> Specialized template.
```

If the answer is unclear, keep the implementation in the foundation as a
reusable primitive or leave an extension interface for specialized templates.
Do not hard-code a vertical workflow into the General Template.

## 7. Lovart Benchmark Interpretation

Lovart should be used as a product benchmark, not as a reason to overload the
General Template.

Public descriptions emphasize:

```text
natural-language task breakdown
Talk / Tab / Tune interaction
multi-option generation and selection
unified canvas
multi-model orchestration
style consistency
many different deliverable types depending on the task
```

The lesson for V3 is:

```text
Build a strong universal foundation.
Use project/canvas context for continuity.
Use task-specific modules for professional deliverables.
```

Do not interpret Lovart as:

```text
one generic template should know every possible suite package.
```

## 8. Conflict Rules

If documents conflict:

```text
Doc50 and Doc67 win for module boundary ownership.
Doc53 wins for retry budget and loop safety.
Doc76 wins for foundation-vs-specialized-template placement.
Doc75 remains the latest identity hero / strict review closure authority inside foundation quality.
Doc77 remains the latest real visual review / aesthetic stability tuning authority inside foundation quality.
Doc78 remains the latest long-term identity / beautiful realism balance tuning authority inside foundation quality.
Doc86 remains the latest portrait image-to-image authority for the rule that makeup, wardrobe, styling, lighting, pose, expression, and scene may change, but bone structure and facial-feature relationships must stay recognizably the same person when a portrait reference exists.
Doc54/59 remain the four-mode General Template mode authority, but only for generic modes.
Specialized template docs win for their own deliverable taxonomy after they are accepted.
```

## 9. Development Guardrails

Hard rules:

```text
1. Do not add ecommerce-specific deliverables to General Template.
2. Do not add photography-package-specific deliverables to General Template.
3. Do not add brand-kit deliverables to General Template.
4. Do not make Visual Capability Cluster own one vertical's full output map.
5. Do not duplicate visual quality modules per template unless the template adds a truly specialized layer.
6. Do not weaken foundation quality to satisfy one vertical's narrow style.
7. Do not expose engineering concepts in beginner UI.
8. Do not infer a full professional package from vague prompts without an explicit template or user-selected mode.
```

Preferred pattern:

```text
Foundation:
  reusable quality primitives and review signals

General Template:
  simple modes and easy continuation

Specialized Template:
  professional deliverable map and packaging
```

## 10. Acceptance Criteria For Future Work

Every future V3 task that changes visual generation must answer:

```text
1. Is this foundation, General Template, or specialized template work?
2. Why is that placement correct?
3. Which existing document gives authority?
4. Which tests prove it does not leak into the wrong layer?
5. Does General Template remain beginner-friendly and scenario-neutral?
6. Does the specialized template still own its professional output package?
```

Minimum tests for boundary-sensitive changes:

```text
General Template does not inherit ecommerce role slots unless ecommerce intent/template is explicit.
General Template does not inherit photography package roles unless photography template is explicit.
Foundation visual quality changes are available to at least General Template and one future/specialized template path.
Specialized template deliverable maps do not pollute shared foundation metadata.
Provider prompts stay product-language-clean for non-product General Template requests.
```

## 11. Current Authority

Doc76 is now the placement governance document.

It does not replace Doc75 quality work. It constrains where future quality and
professional-suite improvements should be added.

The next quality push should prefer:

```text
better foundation curation
better real visual review
better identity/product consistency scoring
better anti-AI realism checks
```

The next professional-output push should prefer:

```text
E-Commerce Template deliverable map
Photography Template deliverable map
Brand Template deliverable map
New Media Template deliverable map
```
