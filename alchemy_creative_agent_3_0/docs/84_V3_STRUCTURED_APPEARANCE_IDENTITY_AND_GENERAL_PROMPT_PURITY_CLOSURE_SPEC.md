# 84 V3 Structured Appearance Identity And General Prompt Purity Closure Spec

## 1. Purpose

This document closes two related V3 quality gaps using one generic solution:

1. General human image requests with detailed clothing or styling language can
   still be pulled into product or e-commerce prompt vocabulary.
2. Human identity continuity currently preserves the same person well enough for
   simple outfits, but it still under-specifies complex appearance assets such
   as layered garments, patterned trims, structured uniforms, ceremonial
   costumes, or other high-structure styling systems.

The required fix is generic. It is not tied to one keyword, one culture, one
wardrobe type, or one narrow scene category.

The new shared concept is:

```text
structured appearance asset
```

This means:

```text
a styling or appearance object whose identity depends on visible structure,
layering, cut, material behavior, pattern family, trim placement, and accessory
placement
```

Examples include but are not limited to:

```text
layered traditional dress
ceremonial clothing
uniform systems
editorial costume looks
stage styling
formal gowns
character-defining branded looks
```

The system must preserve the same recognizable person and, when the project
requires it, the same recognizable appearance asset.

## 2. Compatibility

This document is compatible with the current V3 architecture and does not
replace the foundation:

```text
Project Mode
Template-first project creation
General Template / E-Commerce Template split
LLM Brain Adapter
Visual capability cluster
Identity lock profile builder
Subject identity card
Human natural variation plan
Generation provider
Post-generation review / retry
```

This document updates the latest authority for the intersection of:

```text
Doc49  General Template deproductization
Doc56  Human natural variation
Doc58  Identity anchor / strong reference continuation
Doc61  Portrait commercial consistency benchmark
Doc65  Human photorealism and anti-AI-face layer
Doc78  Long-term identity and beautiful realism
Doc83  Reference identity conflict closure
```

If wording or examples in those earlier documents conflict with this document,
this document wins.

## 3. Problem Statement

### 3.1 Prompt Purity Failure

V3 must not treat generic human styling language as e-commerce intent.

Wrong behavior:

```text
The user describes a person and detailed clothing or appearance styling.
Because the request contains clothing-related nouns, the planning chain infers
ecommerce_product or chooses an ecommerce vertical pack.
The final provider prompt receives:
  product hero
  ecommerce_generic
  feature label regions
  product clarity
  product silhouette
```

This contaminates the result:

```text
camera language becomes less human/editorial
framing becomes conversion-oriented instead of scene-oriented
wardrobe direction competes with object/product assumptions
overall realism and identity stability degrade
```

### 3.2 Appearance Consistency Failure

Current V3 human consistency logic largely preserves:

```text
face
body type
hair direction
broad wardrobe category
lighting language
```

That is not enough for complex appearance assets.

Wrong behavior:

```text
same person is preserved
same broad outfit family is preserved
but the visible structure of the clothing drifts
```

Typical drift forms:

```text
different layer count
different sleeve/cuff shape
different collar/neckline direction
different sash / belt / closure structure
different pattern family or trim placement
different material behavior such as transparency, weight, or fold logic
```

This creates a set that feels AI-variable rather than art-directed.

## 4. Required Product Behavior

### 4.1 General Template Prompt Purity

For `general_template` / `general_creative`, detailed clothing or styling words
must not, by themselves, unlock product or ecommerce language.

Allowed conclusion:

```text
human portrait / fashion / style / cinematic / editorial / scene-driven request
```

Forbidden conclusion:

```text
ecommerce product request
marketplace main image request
product hero request
```

unless the user also provides explicit e-commerce signals such as:

```text
template_id == ecommerce_template
scenario_id == ecommerce
platform words like taobao / jd / amazon marketplace / main image / detail page
uploaded product-reference assets
explicit product-photography wording
```

### 4.2 Structured Appearance Asset Lock

When a human-led request clearly describes a structured appearance asset, the
system must preserve more than wardrobe category.

It must preserve the same appearance asset across the batch unless the user
explicitly asks for a change.

The preserved appearance structure includes, when visible or relevant:

```text
overall silhouette
layer order and outer/inner relationship
neckline / collar direction
sleeve or cuff shape
waist / closure / sash direction
material behavior
transparency / opacity family
pattern or embroidery family
trim placement
accessory placement
color-block relationship
```

### 4.3 Identity Variation Policy

For structured appearance assets:

```text
pose may vary
expression may vary
gaze may vary
head angle may vary
camera distance and crop may vary
scene may vary
small hair movement may vary
fabric motion may vary
```

But these must not vary unless explicitly requested:

```text
appearance asset redesign
new garment cut
new layer architecture
new pattern family
new trim placement
new closure / sash logic
new accessory placement
```

### 4.4 Beautiful Realism

The human-realism layer must continue to optimize for:

```text
beautiful real person first
realism through skin / light / hair / fabric / camera texture
not realism through uglification or feature degradation
```

The new closure must not solve AI-feel by making the person less attractive.

## 5. Architecture Rule

Do not solve this by adding a special-case narrow scene pack.

Do not solve this by hardcoding one clothing keyword into the provider prompt.

Do not solve this by moving more logic into the central brain.

The fix must stay inside the current reusable module structure:

```text
prompt vocabulary guard
vertical-pack selection guard
visual capability cluster
subject identity card
identity lock profile
human natural variation policy
provider prompt assembly
retry patch vocabulary
```

## 6. Implementation Plan

### Step 1 - Add Human-appearance vs Ecommerce Boundary

Add shared detection helpers for:

```text
explicit ecommerce signal
human subject context
human structured appearance context
```

Use them in:

```text
creative_core.rules.detect_industry
vertical_agents.ecommerce_pack.match
```

Behavior:

```text
If the request is clearly human-led and styling-led, ecommerce pack selection
must not win unless explicit ecommerce signals exist.
```

### Step 2 - Extend Subject Identity Card

The subject identity card currently stores:

```text
identity_keep_rules
facial_feature_integrity_rules
beautiful_realism_rules
allowed_variations
forbidden_drift
```

Extend it with:

```text
appearance_structure_rules
metadata flag: structured_appearance_lock = true/false
```

Rules must say, in generic language:

```text
preserve the same structured appearance asset
keep silhouette, layer order, neckline/collar, sleeve/cuff, closure/sash,
material behavior, pattern family, trim placement, and accessory placement
coherent across the set
```

### Step 3 - Strengthen Identity Lock Profile

When subject type is `character` and structured appearance applies:

```text
wardrobe_lock must become a structured-asset lock, not only a category lock
```

Add explicit metadata such as:

```text
level = structured_asset
preserve_specific_design = true
preserve_layering = true
preserve_material_behavior = true
preserve_pattern_family = true
preserve_accessory_placement = true
```

### Step 4 - Tighten Human Variation Policy

For structured appearance assets, variation policy must not imply that styling
may freely drift.

Update:

```text
locked_traits
stable_style_traits
forbidden_drift
prompt_additions
negative_additions
variation axes
```

Keep role diversity, but do not allow unrequested appearance redesign.

### Step 5 - Provider Prompt Consumption

Provider prompt assembly must explicitly consume the new appearance-structure
rules, not only face/body/hair rules.

The provider prompt must gain a line similar to:

```text
Structured appearance lock:
preserve the same appearance asset structure while varying pose, camera, and scene
```

It must also tighten uploaded-reference priority wording when structured
appearance applies:

```text
do not redesign the appearance asset unless the user explicitly asks for a new one
```

### Step 6 - Retry Patch Vocabulary

When the review or retry layer talks about `hair_or_outfit_drift`, the retry
patch must become more specific.

Instead of only:

```text
preserve hair and outfit direction
```

it must also be able to say:

```text
preserve the same appearance structure, layer logic, material behavior, pattern
family, trim placement, and accessory placement
```

### Step 7 - Regression Tests

Add tests for:

1. A human style prompt with detailed clothing/styling language remains on the
   general/default path and does not inherit product/ecommerce prompt wording.
2. Vertical agent selection does not choose ecommerce pack for a human styling
   request without explicit ecommerce signals.
3. Subject identity card exposes structured appearance rules when applicable.
4. Provider prompt contains structured appearance lock language.
5. Project mode identity lock profile upgrades wardrobe lock from category-level
   to structured-asset-level when applicable.

## 7. Out Of Scope

This document does not require:

```text
pixel-perfect garment segmentation
3D wardrobe reconstruction
biometric face vectors
new specialized template packs
new frontend surfaces
```

The goal is a stronger generic commercial-quality closure inside the existing
V3 foundation.

## 8. Acceptance Criteria

The work is only accepted when all of these are true:

1. A structured human appearance prompt under `general_template` does not
   produce product/ecommerce wording in the final provider prompt.
2. The selected vertical pack for that prompt is not the ecommerce pack.
3. Subject identity card contains appearance-structure preservation rules.
4. Provider prompt exposes those rules in a compact model-facing form.
5. Human natural variation still allows pose / expression / angle diversity.
6. Wardrobe changes are constrained to same-asset continuity unless the user
   explicitly asks for change.
7. Existing ecommerce tests still pass.
8. Existing Doc49 and Doc78 deproductization / beautiful-realism tests still
   pass.
