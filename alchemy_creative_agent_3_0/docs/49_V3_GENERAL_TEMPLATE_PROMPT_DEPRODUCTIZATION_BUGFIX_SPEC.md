# 49 V3 General Template Prompt Deproductization Bugfix Spec

## 1. Purpose

This document fixes a concrete V3 General Template bug found during real
`gpt-image-2` validation:

```text
a pure portrait / atmosphere request was generated as a beauty product ad
because the final provider prompt contained default product-poster language
```

The user asked for a summer East Asian woman visual. The final provider prompt
did not contain explicit skincare, perfume, bottle, or jar words, but it did
contain repeated product-oriented defaults such as:

```text
center product
product label
product facts
product identity
product claims
```

For a pure General Template project, this is prompt contamination. It can cause
the image model to invent bottles, jars, packaging, skincare props, or other
commercial product objects that the user did not request.

The fix is not to weaken the V3 architecture. The fix is to make the existing
architecture context-aware:

```text
General Template -> subject / scene / style language
E-Commerce Template -> product / label / packaging language
```

The same boundary also applies to ad-copy language. A General Template image may
still be polished enough for commercial use, but the model-facing and
user-facing planning text must not default to:

```text
commercial product
commercial campaign
CTA
offer
selling point
copy tone
final offer text
```

unless the user explicitly asks for a product, campaign, poster, marketplace,
or advertising asset.

## 2. Compatibility

This bugfix is compatible with documents `32` through `48`.

It does not replace:

```text
Project Mode
Template-first project creation
ProjectContextPackage
ScenarioRuntime
Scenario Pack Registry
LLM Brain Adapter
CentralCreativeBrain
PromptCompilerAgent
Generation Provider
Brand Memory confirmation
```

It only tightens the vocabulary boundary in the shared prompt chain.

The V3 architecture remains:

```text
V3 Foundation
  -> Project
      -> Template
          -> Scenario Pack
              -> LLM Brain
              -> CentralCreativeBrain
              -> Prompt Compiler
              -> Provider Prompt
              -> Image Output
```

## 3. Root Cause

The issue is not a project-history leak.

The tested job had no uploaded reference image and no prior selected output
used as provider input before the first successful retry. The unexpected
skincare object came from prompt wording, not from image reference leakage.

The root cause is that V3's early foundation used a commercial production
pipeline for both General and E-Commerce paths. Some internal classes are still
named with product-oriented terms, and several of those terms leaked into
model-facing text.

There are three kinds of `product` language in V3:

| Kind | Meaning | Allowed in provider prompt? |
| --- | --- | --- |
| Engineering product | Productized software/API naming such as Product API | No |
| Generic commercial product | Product/service subject in a campaign poster | Only if user intent is commercial product/service |
| E-Commerce product | Physical SKU, packaging, label, feature facts | Only in E-Commerce Template or explicit product requests |

The bug is that the second and third kinds were inserted into General Template
provider prompts by default.

## 4. Required Behavior

### 4.1 General Template Default

For `general_template` / `general_creative`, if the user did not explicitly ask
for a product, e-commerce output, product packaging, product photography,
skincare, cosmetics, bottle, jar, label, SKU, or marketplace image:

```text
do not inject product-oriented prompt terms
do not mention product labels
do not mention product facts
do not mention product claims
do not mention product identity
do not mention center product
do not mention product category
do not add product props to improve commercial polish
```

Use neutral image-making language instead:

```text
main subject
focal subject
scene
visual atmosphere
composition
lighting
color palette
style consistency
optional clean blank space
```

### 4.2 E-Commerce Template

For `ecommerce_template`, `ecommerce` Scenario Pack, explicit e-commerce
platforms, product asset types, or uploaded product-reference assets:

```text
product-oriented prompt language remains allowed
```

E-Commerce still needs product clarity, packaging fidelity, feature proof,
label preservation, and product-reference conditioning.

### 4.3 Explicit Product Requests Inside General

If the user stays in General Template but clearly asks for a product visual,
for example:

```text
make a perfume ad
make a skincare bottle poster
create a product photography image
show the packaging
```

then product terms may be used, but only because the user explicitly requested
that subject.

### 4.4 LLM Brain

The LLM Brain must not reintroduce product props into General Template output
unless the input or confirmed project context calls for them.

If the remote LLM Brain fails and the deterministic fallback is used, the same
deproductized boundary still applies.

For pure General Template jobs, the LLM Brain must use neutral creative
planning language:

```text
creative visual
professional composition
professional finish
ready to use
optional clean blank space
```

It must not expose product-ad wording in user-visible workflow summaries or in
the metadata that later feeds the prompt compiler:

```text
commercial visual
commercial publishing
commercial finish
later copy
CTA
offer
selling point
```

unless product language is allowed by the shared predicate.

## 5. Implementation Plan

### Step 1 - Add Context Predicate

Add a small shared predicate or local helper for prompt-facing code:

```text
product_language_allowed
```

It should return true when any of these are true:

```text
template_id == ecommerce_template
scenario_id == ecommerce
industry == ecommerce_product
asset_type in ecommerce_main_image / product_detail_banner
platform in taobao / jd / ecommerce_generic
uploaded/reference asset role is product_reference or subject_reference for ecommerce
user prompt explicitly contains product/object/package words
```

It should return false for a pure General Template portrait, atmosphere, style,
scene, or illustration request.

### Step 2 - Brand Profile Defaults

Change temporary brand profile defaults:

```text
E-Commerce/product context:
  layout_preference = center product, top headline, bottom CTA

General neutral context:
  layout_preference = main subject centered with balanced clean space
```

General typography defaults should no longer imply generated commercial text or
CTA.

### Step 3 - Creative Defaults

For `IndustryCategory.UNKNOWN`, remove default product-ad framing from the
model-facing chain.

Unknown/general creative defaults should describe a clean creative image, not a
commercial product campaign.

### Step 4 - Layout Plan

For non-product General Template jobs:

```text
visual_hierarchy = main_subject, scene_atmosphere, optional_overlay_space
region name may remain schema-compatible, but model-facing notes must say subject
```

Do not send `headline, product, offer_or_cta` to the provider unless product
language is allowed.

### Step 5 - Prompt Compiler

For non-product General Template jobs:

```text
replace "Keep product or service subject clear and prominent"
with "Keep the requested subject, scene, and mood clear and prominent"

replace "product runtime"
with "runtime"

replace "product category"
with "subject type"
```

Only add E-Commerce recipe text when the E-Commerce recipe exists.

### Step 6 - LLM Brain Fallback And Remote Prompt Guard

For non-product General Template jobs:

```text
fallback intent scene -> creative visual
fallback output use -> creative publishing
fallback composition -> professional composition
fallback finish -> professional finish
fallback optimized direction -> professionally polished image set
```

The remote LLM Brain system prompt must also state that General Template uses
subject / scene / style / lighting language by default and must not introduce
product, packaging, label, CTA, offer, selling-point, or ad-copy concepts unless
the user explicitly requested such an image.

### Step 7 - Provider Prompt Builder

For non-product General Template jobs:

```text
Create a polished, directly usable creative image asset
Preserve the requested subject, scene, style, and proportions
Avoid adding unrequested products, packaging, bottles, jars, labels, logos, badges, claims, or text
Avoid adding watermarks, signatures, AI-generated marks, or any fake text overlays
```

Do not include:

```text
product label
product facts
product identity
product claims
```

unless product language is allowed.

### Step 8 - Tests

Add focused tests that verify:

```text
pure General portrait final provider prompt contains no product contamination
pure General portrait prompt explicitly avoids unrequested products / packaging / bottles / jars
pure General LLM Brain fallback metadata contains no product/ad-copy contamination
E-Commerce provider prompt still preserves product label / identity constraints
temporary General brand profile has neutral layout preference
temporary E-Commerce brand profile still has product layout preference
```

### Step 9 - Real Validation

After tests pass, rerun the same real generation task:

```text
创建一组东亚年轻女性的夏日清凉写真，要求清爽、高级、通透。头发为黑发本色，染色成的绿色，与夏日、清凉的风格搭配
```

Validation target:

```text
no skincare bottle
no perfume bottle
no invented product packaging
no product label
no watermark
no signature
no AI-generated mark
subject remains East Asian young woman
summer cool feeling remains visible
green-dyed black hair remains visible
style remains clean, premium, translucent
```

If the image model still invents a product object after the final prompt has no
product contamination, record it as model drift and add a stronger negative
prompt. If the final prompt still contains product terms, the code is not fixed.

## 6. Audit Checklist

Before delivery:

```text
rg final output metadata for product terms in the new General job
rg code path for unconditional product-facing provider prompt lines
confirm E-Commerce tests still pass
confirm General prompt tests pass
confirm V1/V2 isolation remains intact
confirm real sample output is attached to its V3 project
```

## 7. Non-Goals

This document does not:

```text
rename Product API or ProductJobRecord engineering classes
remove E-Commerce Template product fidelity rules
change the V3 Project Mode architecture
change V1/V2/Alchemy Lab behavior
turn General Template into a non-commercial toy generator
```

General Template may still produce commercially usable images. It just must not
invent product-ad objects when the user asked for a pure creative image.
