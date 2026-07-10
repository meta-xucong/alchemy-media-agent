# 85 V3 Image-To-Image Identity Transfer And Reference Truth Closure Spec

Doc93 authority update:

```text
Doc85 remains the reference-truth foundation. Doc93 is the current
implementation authority for per-channel truth strength, prompt ownership,
selected-output support, and conflict resolution. Whole-image inheritance must
not be inferred from an identity truth source.
```

## 1. Purpose

This document closes the next V3 gap after Doc84.

Doc84 fixed:

```text
general-template prompt purity
structured appearance continuity in the abstract rule layer
```

Doc85 fixes the next, more concrete layer:

```text
image-to-image identity transfer precision
reference-truth preservation for people, products, and structured appearance assets
```

Doc88 update:

```text
For portrait references, "reference-truth preservation" must not be interpreted
as copying the whole uploaded photo or making identity guidance dominate every
other channel. Uploaded portrait truth preserves the person; the current prompt
preserves task mood and art direction; user-approved generated outputs may
preserve positive tone, light, and composition.
```

The problem is not whether V3 can use references at all.

The current system already supports true reference-image generation:

```text
project references enter GenerationRequest.reference_assets
advanced asset mode is enabled
OpenAI-compatible generation uses images.edit when reference images exist
```

The remaining problem is quality:

```text
the reference image is often treated as one whole image
instead of separating identity truth from style/context truth
```

This can make the result:

```text
similar to the reference family
but not close enough to the exact person / exact product / exact appearance asset
```

Doc85 must solve this generically.

It is not tied to one person type, one product category, one clothing family, or
one specialized template.

## 2. Compatibility

Doc85 is compatible with the current V3 architecture and must not conflict with
existing foundation rules.

It extends:

```text
Doc48  LLM Brain Adapter and pre-generation reasoning
Doc49  General Template prompt deproductization
Doc56  Human natural variation
Doc58  Identity anchor and strong-reference continuation
Doc63  Image-edit provider health and fallback
Doc65  Human photorealism and anti-AI-face layer
Doc78  Long-term identity and beautiful realism
Doc80  Provider reference upload compression
Doc83  Retry delivery layer and uploaded-reference identity closure
Doc84  Structured appearance identity and general prompt purity closure
Doc88  Portrait reference balance and prompt mood preservation
```

Doc85 does not replace:

```text
Project Mode
General Template / E-Commerce Template split
Visual Capability Cluster
SubjectIdentityCard
IdentityLockProfile
StrongReferenceClosurePackage
OpenAI/GPT-Image-2 reference-image path
provider-reference compression
bounded retry rules
```

Doc85 adds a stronger interpretation rule:

```text
when V3 runs image-to-image or reference-image generation,
the reference must be decomposed into truth layers,
not treated as one undifferentiated image whenever a stronger split is possible
```

## 3. Current-State Audit

### 3.1 Current Strengths

The current V3 implementation already does these correctly:

```text
uploaded portrait references can become active identity references
selected project outputs can become strong continuation references
project-mode references are passed into GenerationRequest
advanced asset mode is enabled for reference-image generation
OpenAI-compatible provider uses images.edit when reference image files exist
structured appearance rules now exist in identity/variation/prompt layers
```

### 3.2 Current Gaps

The current implementation is still incomplete in image-to-image precision.

#### Human reference gap

Current behavior:

```text
the full uploaded portrait image is used as reference
```

Missing behavior:

```text
extract face-identity truth separately from scene/style/context truth
prioritize exact facial microfeatures over generic beauty archetype language
```

User-visible consequence:

```text
the result looks like the same beauty family or same vibe,
but not strongly enough like the exact uploaded person
```

#### Product reference gap

Current behavior:

```text
product identity rules are strong
product reference images can enter true reference-image generation
```

Missing behavior:

```text
separate the exact product truth object from surrounding scene clutter when possible
preserve the exact product instance more tightly when the source image contains
extra environment noise, accessories, or scene context
```

User-visible consequence:

```text
product results are usually stronger than portraits,
but exact object identity can still drift in angle-sensitive or context-heavy
reference images
```

#### Structured appearance gap

Current behavior:

```text
structured appearance rules are now present in prompt and identity locks
```

Missing behavior:

```text
the provider still often receives the whole reference frame,
not an appearance-truth-focused reference object
```

User-visible consequence:

```text
the same person may remain recognizable,
and the same broad appearance asset family may remain recognizable,
but exact structure can still drift across later image-to-image continuations
```

## 4. Product Principles

### 4.1 Reference Truth Beats Archetype

When a real uploaded reference image is present:

```text
reference truth has priority over generic archetype wording
```

Examples of lower-priority archetype wording:

```text
young sweet East Asian beauty
soft oval face
premium skincare-model skin
hero product look
luxury bottle style
```

These words may guide mood and finish, but must not replace:

```text
the exact person's facial identity
the exact product's visual identity
the exact appearance asset's visible structure
```

### 4.2 Split Truth Layers

V3 must conceptually split reference truth into these layers:

```text
identity truth
appearance truth
style/context truth
```

For people:

```text
identity truth = face / feature relationships / body identity direction
appearance truth = hair + structured appearance asset when relevant
style/context truth = scene, palette, light, atmosphere, lens feeling
```

For products:

```text
identity truth = shape / proportions / material / label-logo placement / visible product facts
appearance truth = packaging surface / finish / accessory relations when relevant
style/context truth = scene, lighting, commercial atmosphere, environment
```

For structured appearance assets:

```text
identity truth = same person or same core subject
appearance truth = silhouette / layers / cut / trim / pattern / material behavior / accessory placement
style/context truth = scene, mood, palette, atmosphere
```

### 4.3 Selected Output Does Not Erase Uploaded Truth

If the user uploads a real portrait/product reference and later selects a
generated output:

```text
uploaded truth remains highest for identity-critical details
selected output becomes continuation/style/composition reinforcement
```

Selected output must not silently replace the uploaded human or product truth
source unless the user explicitly chooses to replace it.

## 5. Required Behavior

### 5.1 Human Image-To-Image

When an uploaded portrait identity reference exists:

```text
V3 must preserve the exact same recognizable person as the first identity source
```

This includes:

```text
face width/length ratio
eye shape and spacing
eyelid direction
eyebrow arc / thickness / temperament
nose tip / nose-wing / mouth relationship
jaw and chin direction
midface temperament
natural age impression
```

Allowed changes:

```text
expression
gaze
pose
head angle
camera angle
crop
scene
lighting micro-variation
small hair movement
```

Forbidden drift:

```text
generic AI beauty identity replacement
beauty-app face replacement
face slim / eye enlarge / V-chin distortion
new ethnicity direction
new age band
exact uploaded identity washed into a similar-looking model
```

### 5.2 Product Image-To-Image

When an uploaded product reference exists:

```text
V3 must preserve the same exact product truth
```

This includes:

```text
shape
proportions
material identity
color identity
visible label/logo placement
packaging silhouette
surface finishing cues
```

Allowed changes:

```text
camera angle
lighting
scene
lifestyle context
crop
layout
background
```

Forbidden drift:

```text
new product instance
shape drift
label drift
logo position drift
invented accessories that change product reading
```

### 5.3 Structured Appearance Image-To-Image

When an uploaded reference includes a structured appearance asset:

```text
V3 must preserve the same exact appearance asset structure
```

This includes:

```text
silhouette
layer order
collar / neckline logic
sleeve / cuff logic
closure / sash / belt logic
material behavior
transparency family
pattern or embroidery family
trim placement
accessory placement
```

Allowed changes:

```text
pose
camera
crop
scene
fabric motion
lighting micro-variation
```

Forbidden drift:

```text
new design
new layer architecture
new pattern family
new trim placement
new accessory system
```

## 6. Architecture Boundary

Doc85 must stay inside existing reusable modules.

### 6.1 Asset-Vision / Provider-Reference Preparation Layer

Add generic reference-truth preparation:

```text
portrait identity crop derivative
product truth crop derivative
structured appearance truth crop or focused derivative when possible
```

These are provider-input derivatives only.

They must not replace:

```text
user original upload
preview image
archive image
frontend display thumbnail
```

### 6.2 Visual Capability Cluster

Extend existing structures only:

```text
SubjectIdentityCard
VisualIdentityLockProfile
HumanNaturalVariationPlan
StrongReferenceClosurePackage
retry patch vocabulary
```

No new independent top-level quality framework should be created.

### 6.3 Generation Provider

The generation provider must consume:

```text
reference truth layers
provider input plan with reference derivatives
identity priority map
appearance truth priority map
```

### 6.4 Product API / Project Mode

Project Mode must preserve:

```text
which references are truth sources
which are continuation sources
which derivative provider references were used
```

## 7. Implementation Plan

### Step 1 - Add Reference Truth Classifier

Create shared logic to classify active references into:

```text
portrait_identity_truth
product_identity_truth
structured_appearance_truth
style_context_truth
```

This classification must be derived from:

```text
reference role / use_policy
visual-cluster subject type
asset-vision hints
user input
template policy
```

### Step 2 - Build Provider-Only Derivatives

Add provider-input derivatives:

#### Portrait

If face detection is available:

```text
create a portrait-identity crop centered on the main face
```

If face detection is unavailable:

```text
use the original image but record fallback metadata
```

#### Product

If subject/product localization is available:

```text
create a product-truth crop centered on the main product
```

If localization is unavailable:

```text
use the original image but record fallback metadata
```

#### Structured appearance

If body/garment region is available:

```text
create an appearance-truth crop that preserves the structured asset region
```

If unavailable:

```text
use the original image but record fallback metadata
```

### Step 3 - Dual / Layered Reference Usage

For human portrait image-to-image, provider input should support:

```text
face identity crop
full-frame style/context reference
```

For product image-to-image:

```text
product truth crop
full-frame scene/context reference when useful
```

For structured appearance:

```text
appearance-truth crop
full-frame scene/context reference when useful
```

### Step 4 - Priority Rules

Human:

```text
uploaded portrait identity truth
> uploaded structured appearance truth
> selected generated continuation frame
> style/context truth
> archetype wording
```

Product:

```text
uploaded product truth
> selected generated continuation frame
> product style/context truth
> generic commercial product wording
```

### Step 5 - Provider Prompt Wording

Prompt wording must explicitly describe:

```text
identity truth source
appearance truth source
context/style truth source
allowed changes
forbidden drift
```

The prompt must not leave this implicit.

### Step 6 - Metadata And Debuggability

Output metadata must record enough to debug image-to-image quality:

```text
provider_input_plan
reference_image_count
reference truth source ids
portrait/product/appearance truth derivative ids
operation type
```

Current ambiguity where output metadata shows the final prompt but not a clear
provider-input reference plan must be removed.

### Step 7 - Review / Retry Upgrade

When review detects:

```text
identity_drift
reference_guard_ignored
hair_or_outfit_drift
product_identity_drift
```

retry patch must become more precise:

```text
preserve exact face identity source
preserve exact product truth source
preserve exact structured appearance truth source
```

not just:

```text
preserve outfit direction
preserve style
```

## 8. Current-State Assessment

Current V3 image-to-image consistency is:

### Human

```text
partially implemented
```

Reason:

```text
real reference-image generation is active
identity locks exist
beautiful-realism rules exist
but exact-person transfer is still too weak because the reference is not split
into stronger face-truth and context-truth layers
```

### Product

```text
stronger than human, but not fully closed
```

Reason:

```text
product truth rules and reference-image usage are already stronger
but exact object truth can still drift when the uploaded product image contains
scene clutter and no product-truth-focused derivative is prepared
```

### Structured appearance

```text
improved in prompt/lock language, not fully closed in provider-reference truth
```

Reason:

```text
Doc84 added structured appearance lock semantics
but image-to-image still lacks a dedicated appearance-truth derivative/focus path
```

## 9. Acceptance Criteria

The work is accepted only when all of these are true:

1. Uploaded portrait references in image-to-image generation preserve the exact
   person more strongly than the current release.
2. Uploaded product references preserve the exact product more strongly than the
   current release.
3. Structured appearance assets preserve exact structure more strongly than the
   current release.
4. Selected generated continuation frames do not silently override uploaded
   human/product truth.
5. Provider metadata clearly records image-to-image reference truth usage.
6. General Template prompt purity remains intact.
7. Existing ecommerce tests continue to pass.
8. Existing Doc78 and Doc84 identity/realism/appearance tests continue to pass.
