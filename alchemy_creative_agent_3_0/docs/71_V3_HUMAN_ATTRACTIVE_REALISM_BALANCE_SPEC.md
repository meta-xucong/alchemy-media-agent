# 71 V3 Human Attractive Realism Balance Spec

> Historical/compatibility notice (Doc128): this is validation history, not a
> forward Provider prompt or retry catalogue. New Human Realism work uses only
> Doc128's shared resolved constraints and review dimensions; it must not
> restore this document's named lighting, complexion, or beauty fragments.

Doc94 correction note:

```text
Doc71's attractive-realism balance remains active, but its bright summer
treatment is one historical test condition only. It must not be injected into
low-key, documentary, indoor, mature-subject, or other unrelated requests.
Exposure, complexion, color, and beauty treatment follow prompt/reference truth
through Doc94's universal rendering profile.
```

Status: accepted micro-tuning document after Doc70.

Doc70 successfully reduced the obvious AI-beauty feel in photoreal human
portraits, but the user review found a new quality tradeoff: the portrait can
become less attractive, slightly darker, and too documentary. Doc71 fixes that
balance without returning to skin blur, face-slimming, idol-card polish, or
generic AI beauty.

## 1. Goal

Doc71 keeps the Doc70 real-camera direction, then adds a narrow attractive
realism layer:

```text
real skin texture stays visible
face remains naturally shaped
expression stays non-template
skin tone looks clean, healthy, and fresh
face is lifted by soft natural bounce light
summer daylight feels bright and flattering
commercial beauty comes from lighting and color, not beauty filters
```

## 2. Compatibility

Doc71 must remain compatible with Docs50-70:

```text
Project Mode unchanged.
CentralCreativeBrain unchanged.
Scenario Pack contracts unchanged.
Provider routing unchanged.
Visual Capability Cluster remains the owner.
Doc70 still owns anti-AI-face and anti-beauty-geometry pressure.
Doc71 only adds attractive realism balance on top of Doc70.
No V1/V2 runtime dependency.
No duplicate human realism module.
```

If Doc71 conflicts with Doc70 on "too dark / too plain / too documentary",
Doc71 wins. If it conflicts with Doc70 on beauty filters, face geometry,
identity drift, or architecture ownership, Doc70 and Docs50/67 win.

## 3. Prompt Rules

### 3.1 Positive Balance

Photoreal human prompts should add compact pressure for:

```text
healthy clear complexion with visible real texture
fresh bright skin tone from light, not skin whitening
soft natural bounce light lifting face shadows
clean high-key summer daylight without overexposure
gentle cheek warmth and natural lip color
eyes look awake and clear, not tired or glassy
attractive fresh expression without template sweetness
natural skin tone and ethnicity remain unchanged
```

### 3.2 Negative Balance

Photoreal human prompts should reject:

```text
dull complexion
muddy skin tone
gray or green color cast on skin
underexposed face
harsh facial shadow
tired expression
overly matte documentary look
unflattering dark tan or bronze cast unless requested
skin whitening filter
beauty-app glow
```

The important distinction:

```text
Doc71 wants brighter healthier lighting.
Doc71 does not want whitening, poreless glow, face reshaping, or beauty filters.
```

## 4. Implementation Targets

Update only existing visual/providing files:

```text
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/casebook_recipes.py
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/human_photorealism.py
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/vision_inspector.py
alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/vision_provider.py
alchemy_creative_agent_3_0/app/generation_router/providers.py
```

Tests may be added in:

```text
alchemy_creative_agent_3_0/tests/test_v3_doc71_human_attractive_realism_balance.py
```

## 5. Review And Retry

Add or verify issue codes:

```text
dull_complexion
muddy_skin_tone
underexposed_face
harsh_facial_shadow
overly_matte_documentary_look
tired_expression
unflattering_color_cast
```

Retry patches must add:

```text
soft natural bounce light
healthy clear complexion
clean bright summer daylight
gentle cheek warmth
natural skin tone preserved
visible real skin texture retained
```

Retry patches must not ask for:

```text
skin whitening
face slimming
poreless glow
idol photocard retouch
beauty-app smoothing
```

Doc53 retry budget still limits loops.

## 6. Tests

Required focused tests:

```text
Doc71 code remains V3-owned and has no V1/V2 runtime import.
Human photorealism guidance contains attractive realism positives.
Human photorealism guidance rejects dull/dark/unflattering complexion issues.
Provider prompt renders attractive realism without product/commercial leakage.
New issue codes create retry patches for bounce light and healthy complexion.
Doc70 anti-AI-face rules remain present.
Stylized/anime requests remain exempt.
```

## 7. Real Validation Loop

After implementation:

```text
1. Run focused Doc71 tests.
2. Run Doc70/Doc69/human/provider/general regressions.
3. Run real portrait generation with the same East Asian summer prompt.
4. Compare against Doc70 final contact sheet.
5. Accept when the output looks healthier, brighter, and more attractive while
   still avoiding obvious AI beauty-face artifacts.
```

## 8. Acceptance Criteria

Doc71 is acceptable when:

```text
the person does not look darker, duller, or less attractive than intended;
skin remains real and textured;
the face is lit by flattering real light, not beauty filters;
natural identity and natural skin tone are preserved;
General Template boundaries remain intact;
tests pass;
real output is generated and assessed honestly.
```
