# 92 V3 Style-Aware Human Realism AI-Feel Suppression Spec

> Historical/compatibility note (Doc128): style-aware observations remain
> useful validation criteria, but new jobs use Doc128's concise resolved
> constraints and review dimensions. This document cannot restore local
> profile-specific prompt fragments or retry stacks.

Doc94 correction note:

```text
Doc92's valid requirement is that realism must respect the requested visual
conditions. Its named ancient/traditional, child-catalog, East Asian-summer,
and similar profiles are superseded by Doc94's orthogonal rendering profile.
Those scenes remain regression fixtures, not shared runtime branches.
```

Doc93 compatibility note:

```text
Doc92 remains the style-aware Human Realism authority. It may adapt realism
rendering to the requested style, but it must not infer that the uploaded
reference owns styling channels. Reference role and channel inheritance are
resolved only by Doc93.
```

## 1. Purpose

Doc92 tunes the Doc91 Human Realism Plugin after real VPS validation on two
different use cases:

```text
1. Kidswear product-on-child model image
2. Moody traditional / ancient-style beauty portrait
```

Both tests improved some structure and continuity, but both still showed
visible AI-feel:

```text
Kidswear:
  child model looked cleaner than before but still too doll-like and template
  catalog-like.

Moody ancient portrait:
  identity and composition were acceptable, but the face became more oily,
  glossy, and plastic than the older best image in the same project.
```

The root product rule:

```text
Human Realism must reduce AI-feel without forcing every human image toward the
same bright, fresh, polished commercial face.
```

## 2. Compatibility And Authority

Doc92 extends:

```text
Doc65  Human photorealism and anti-AI-face layer
Doc70  real-camera AI-feel reduction
Doc71  attractive realism balance
Doc72  complexion/proportion guardrails
Doc88  reference balance and prompt mood preservation
Doc91  Human Realism Plugin governance
```

Doc92 does not replace:

```text
Doc85-88 portrait identity/reference truth
Doc90 advanced reference controls
Doc91 plugin placement and activation contract
Specialized template deliverable maps
```

If Doc91 or earlier wording implies that `bright`, `fresh`, `luminous`,
`high-key`, `bounce light`, or `clean fair complexion` should be pushed into
every real-human image, Doc92 wins.

## 3. Problem Diagnosis

Real validation showed that generic positive realism wording can backfire.

Observed over-push words:

```text
bright
fresh
luminous
polished
glow
highlight
high-key
bounce light
clean fair complexion
commercial polish
```

These are useful for summer portraits, ecommerce freshness, and bright social
covers. They are harmful when the user's requested mood is:

```text
moody
dark
cinematic
ancient / traditional
gufeng / hanfu
cold blue / silver
low-key
soft-focus film
melancholic
night
shadow-rich
```

In those cases, the plugin must preserve:

```text
real skin texture
fine pores
natural under-eye detail
non-uniform skin tone
realistic eye moisture
hairline and flyaway hair
fabric and lens realism
```

but must suppress:

```text
oily face
waxy highlight
dewy plastic makeup
beauty-filter gloss
porcelain mask
over-polished commercial glow
generic AI influencer face
```

## 4. Style-Aware Realism Profiles

Human Realism must choose one realism profile before composing prompt fragments.

Required profiles:

```text
neutral_real_camera
bright_fresh_commercial
moody_cinematic_traditional
child_catalog_natural
hand_or_skin_detail
stylized_disabled
```

### 4.1 Bright Fresh Commercial

Use this when the prompt clearly asks for:

```text
summer
daylight
fresh
clean bright
social cover
high-key
healthy clean complexion
```

Allowed:

```text
soft bounce light
clear healthy complexion
bright but textured skin
fresh commercial polish
```

Still forbidden:

```text
poreless glow
beauty-app face
skin whitening mask
plastic highlight
```

### 4.2 Moody Cinematic Traditional

Use this when the prompt asks for:

```text
ancient
traditional
gufeng
hanfu
cinematic
moody
dark
cold blue
silver
low-key
melancholic
soft-focus film
night
spotlight
flower shadows
```

Rules:

```text
Do not add bright/fresh/high-key/bounce-light/luminous complexion pressure.
Do not fight the user's cold, dark, melancholic, or filmic mood.
Keep skin real through texture and natural light response, not through shine.
Treat requested highlights as controlled photographic specular detail, not oily
makeup gloss.
Prefer soft-matte real skin with subtle texture under moody light.
```

Negative emphasis:

```text
oily face
greasy forehead
plastic nose bridge
waxy cheek highlight
dewy beauty filter
porcelain mask
over-polished idol face
AI fantasy doll face
```

### 4.3 Child Catalog Natural

This remains an auxiliary branch under the general Human Realism Plugin.

Rules:

```text
Strengthen real child photography only when child/teen/kidswear signals appear.
Never turn the shared plugin into a child-specific module.
Avoid doll-like, pageant-polished, adultified, or toy-like child faces.
Keep child faces age-appropriate, natural, and commercially clean.
```

## 5. Implementation Plan

Future code must remain inside the existing Human Realism Plugin.

Implementation steps:

```text
1. Add a style_profile field into human_realism_plugin metadata.
2. Detect moody_cinematic_traditional from prompt, template metadata, and
   project context.
3. Detect bright_fresh_commercial only when the prompt actually asks for it.
4. Keep child_catalog_natural as an auxiliary profile layered on top of the
   general profile.
5. Filter positive prompt fragments by style profile:
   - suppress bright/fresh/luminous/high-key/bounce-light lines for moody
     cinematic traditional images
   - keep texture/asymmetry/real lens/flyaway hair/fabric rules
6. Add style-aware anti-gloss negatives for moody traditional portraits.
7. Keep identity/reference rules unchanged.
8. Add tests proving:
   - moody traditional portrait does not receive bright-fresh pressure
   - kidswear still gets child auxiliary realism
   - bright summer portrait keeps fresh complexion guidance
   - Product API retry patch delegates AI-face wording to the plugin
```

## 6. Acceptance Standard

For the ancient-style beauty comparison:

```text
The new output should be closer to the old best a661 image:
  less oily forehead/nose/cheek shine
  less plastic skin
  same or better identity consistency
  no loss of cold, moody, traditional film atmosphere
```

For kidswear:

```text
The child model should look less like an AI catalog doll:
  less frozen template smile
  less glossy eyes
  less porcelain skin
  more natural child expression and photographed skin
  clothing clarity remains intact
```

Lovart benchmark target for this phase:

```text
General human realism and ecommerce model realism should reach 75-80% of
Lovart-level quality on these two tests, without requiring specialized
Photography or E-Commerce template tuning.
```

## 7. Non-Goals

```text
Do not add a new visual framework.
Do not move identity truth into Human Realism.
Do not make the General Template a photography package director.
Do not overfit to one ancient-style prompt or one kidswear prompt.
Do not make all faces matte, dull, or less beautiful merely to avoid shine.
```
