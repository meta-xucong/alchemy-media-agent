# V3 Prompt-Owned Channel Evidence Isolation And Portrait Stability Spec

Status: implementation authority after Doc101/Doc102  
Scope: V3 General Template foundation capabilities only  
Renderer: GPT Image 2 API remains the sole production pixel renderer

## 1. Purpose

Doc103 closes a general image-to-image failure mode: an uploaded portrait is
correctly assigned to identity, but non-identity pixels in that same image still
overpower the current prompt. Hair color, hairstyle, makeup, wardrobe, source
light, source scene, camera mood, or whole-frame style may leak even though the
reference policy says those channels are prompt-owned.

This document does not add a new top-level capability, template, Brain policy,
or renderer. It extends the existing `reference_channel_policy` child plugin and
its provider evidence preparation, review, and bounded retry contracts.

## 2. Compatibility And Authority

The following authorities remain unchanged:

- Doc50 owns the Visual Capability Cluster boundary.
- Doc76 owns foundation-versus-specialized-template governance.
- Doc85 owns uploaded reference truth priority.
- Doc86 owns same-person bone-structure and feature-relationship continuity.
- Doc87 and Doc88 own identity-versus-style separation and prompt mood balance.
- Doc93 owns per-reference channel assignment and prompt ownership.
- Doc100 keeps GPT Image 2 as the sole production renderer.
- Doc101/Doc102 own capability activation, frozen plans, and hot-plug execution.

Doc103 refines how Doc93 identity evidence is materialized and repaired. It may
not widen portrait identity authority into styling channels and may not bypass
the frozen activation plan.

## 3. Core Rule

For an ordinary identity-only portrait reference:

```text
Reference owns:
  face geometry, facial-feature relationships, age direction,
  body identity direction, natural recognizable-person cues

Current prompt owns when stated:
  hair color/style, makeup, wardrobe, accessories, complexion direction,
  lighting/color grade, scene, camera, mood, art direction, finish
```

Pixels are evidence, not permission to inherit every visible attribute. When
the current prompt owns a channel, provider evidence must reduce conflicting
visual pressure before the image is sent upstream.

## 4. Evidence Isolation Profile

The existing provider-only portrait evidence pyramid remains two complementary
images from one source person:

1. `portrait_identity_crop`: feature-detail evidence for brow-eye, eye spacing,
   nose-mouth, philtrum, mouth width, and lip contour.
2. `portrait_identity_geometry_crop`: head-geometry evidence for face ratio,
   forehead/midface/lower-face, temple-cheek-jaw contour, cheek volume, jaw
   slope, and chin scale.

When hair, makeup, light, scene, or whole-image style is prompt-owned, both
derivatives use `prompt_owned_channel_isolation_v1`:

- retain central facial detail, luminance, and natural skin response;
- reduce chroma outside the central facial region so source hair color and
  source color grade are weak evidence;
- lightly soften outer context so background, clothing, and source lighting are
  less likely to be copied;
- never modify the user's uploaded original;
- preserve provider minimum edge, byte limits, and existing compression rules;
- version the derivative cache so old cached crops are not silently reused.

When the user explicitly locks hair or structured appearance to a reference,
the corresponding evidence is not decontextualized for that assigned channel.
Product, scene, composition, style, and structured-appearance references keep
their own existing truth-layer behavior.

## 5. Prompt Contract

For every explicit prompt-owned channel, the compiled provider contract must:

- name that channel as current-prompt authority;
- state that conflicting reference pixels are non-authoritative;
- require the exact current request rather than a generic alternative;
- preserve identity geometry while changing only the requested surface or
  environmental channel;
- keep the complete user request lossless within the existing provider budget.

The implementation must be channel-generic. It must not contain scenario words
such as a particular costume, historical style, location, or one hair color as
special-case logic.

## 6. Review And Retry Contract

The active `reference_channel_policy` plugin owns these issue families:

- source hair or makeup over-inheritance;
- source wardrobe or accessory over-inheritance;
- source lighting, color, scene, camera, mood, or whole-style over-inheritance;
- identity-only references used as style references;
- explicit prompt-owned channels ignored;
- selected generated anchors overriding uploaded truth or the new prompt;
- structured appearance locks applied to the wrong channel.

Retry repair must be channel-specific. A hair failure repairs hair only; a
scene failure repairs scene only. Every repair must retain identity geometry,
must not increase whole-image reference strength, and remains subject to the
existing one-retry default budget. If live review is unavailable, the result is
kept for manual review; no blind retry loop is allowed.

Vision-provider waiting is independent from image-provider waiting. Image
generation may remain slow, while visual review defaults to two attempts and
must not call a second protocol after a timeout from the first protocol.

## 7. Four-Scene Stability Matrix

Use one unchanged uploaded identity reference across four prompt-owned visual
directions:

1. cinematic traditional/fantasy portrait;
2. modern indoor editorial portrait;
3. outdoor natural-light lifestyle portrait;
4. visibly changed hair and makeup portrait.

Each scene runs at least twice when upstream availability permits. Record:

- same-person readability;
- face outline and proportion;
- brow-eye geometry;
- nose-mouth relationship;
- jaw/chin geometry;
- human realism;
- prompt-owned channel obedience;
- commercial finish;
- first-pass result, retry reason, final state, and elapsed time.

Practical acceptance requires:

- identity and human-realism assessment at or above 8.5/10 for the accepted
  set, with no obvious different-person result;
- explicit prompt-owned channel leakage below 10 percent across accepted runs;
- no unrelated product/template capability activation;
- no more than one image rerender by default;
- no false success when review reports a hard commercial failure;
- all deterministic and regression suites passing.

External review or image-provider timeouts are reported separately from code
failures and do not justify weakening the contracts.

## 8. Implementation Order

1. Add versioned identity-evidence isolation metadata and processing beneath
   `prepare_reference_truth_derivatives`.
2. Pass the resolved per-asset reference policy from the provider into that
   preparation function.
3. Strengthen generic explicit-channel provider rules.
4. Centralize channel-specific retry patches in the reference policy module and
   consume them from post-generation review and Product API retry assembly.
5. Add unit, provider-materialization, activation-isolation, and retry tests.
6. Run full V3 and root regressions.
7. Run the real four-scene matrix and archive prompts, plans, review records,
   outputs, timings, and a contact sheet.

## 9. Stop Conditions

Do not add another capability merely because one sample is imperfect. Stop and
report an external blocker when repeated provider or vision-provider outages
prevent meaningful visual comparison after bounded retries. Do not claim visual
acceptance from metadata-only tests.

## 10. Implementation And Acceptance Record

The 2026-07-12 local acceptance run used one unchanged uploaded portrait across
the four required directions, twice per direction. All eight outputs were
rendered by `openai_gpt_image / gpt-image-2`; no local renderer or pixel-rewrite
model participated.

- eight of eight image requests succeeded on their first provider attempt;
- each request used the versioned provider-only identity isolation profile;
- source green hair, beach lighting, source wardrobe, and beach scene were not
  visibly inherited in the accepted outputs;
- the current prompt visibly controlled traditional/fantasy, modern indoor,
  outdoor natural-light, and strong hair/makeup-change directions;
- calibrated SFace identity scores ranged from `0.8505` to `0.9881`, with a
  mean of `0.9387`; all eight exceeded the `0.82` commercial identity gate;
- geometry relationship scores ranged from `0.7710` to `0.9397`, with a mean
  of `0.8554`;
- the strongest hair/makeup transformation remained the hardest case, scoring
  `0.8505` and `0.8643`, so it remains a monitored quality boundary rather than
  grounds for another architecture layer;
- V3 enforced-mode regression passed `475` tests and the repository root suite
  passed `141` tests; compile and diff checks passed.

The first outdoor run exposed a generic language gap for `natural-light` and
`open shade`. The existing prompt-ownership resolver was extended to recognize
these photography terms and to evaluate every occurrence of preserve/change
language within a clause, preventing a leading phrase such as `keep the same
person` from accidentally locking a later light, scene, or styling channel. A
post-fix real outdoor generation confirmed the lighting, hair, and scene rules
were all present in the provider prompt and scored `0.9454` for identity.
