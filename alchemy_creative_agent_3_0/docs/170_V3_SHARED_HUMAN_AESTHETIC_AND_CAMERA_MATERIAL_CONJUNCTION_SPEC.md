# Doc170 — Shared Human Aesthetic and Camera-Material Conjunction

## Status

Foundation refinement accepted by controlled pure-text validation. This document does
not create a child, casting, East Asian, beauty, skin-tone or template module.
It refines the existing Human Realism Brain sign-off and keeps all renderer
wording owned by the Remote Brain.

## 1. Controlled red evidence

The Doc167–169 developmental-presence work can produce a stage-coherent,
attractive person when reference evidence is admitted. The new controlled
question deliberately removed all image references and asked whether the same
foundation can author a six-year-old neutral casting portrait from text alone.
The external child-model board remained human-evaluation evidence only and was
never sent to Brain, MCP or Image 2.

Five independent canonical pure-text samples exposed a repeated trade-off:

1. prompts emphasizing high-end beauty produced a fair, attractive subject but
   Shared Vision found over-smoothed or synthetic skin;
2. prompts emphasizing untouched camera material retained more facial depth
   but the Brain reduced explicit aesthetic appeal and Image 2 still applied a
   mild catalog polish;
3. pure-white frontal studio light amplified the appearance of a globally
   smoothed surface even when the prompt explicitly prohibited it;
4. adding more skin terms or facial details did not improve the pixels and
   would violate Doc94's anti-overfitting rule.

The latest red sample was a canonical `image_generate` operation with zero
declared and zero admitted references. Shared Vision returned warning,
`human_realism=0.76`, with `synthetic_child_skin`, `over_smoothed_skin`,
`weak_photographic_imperfection` and `flat_scene_lighting`. The prior sample
scored `human_realism=0.74` with the same material failure. Neither is accepted.

## 2. Root cause

The existing typed contract contains both:

```text
aesthetic_boundary = preserve_user_style_without_generic_beauty_substitution
photographic_material_requirement = camera_observed_human_materiality
```

Both are correct, but the final Brain instruction allowed them to be optimized
as separate goals. A model could avoid generic beauty by making the subject
more ordinary, or preserve commercial beauty by using a cosmetically smooth
surface. This is a semantic conjunction failure, not missing facial anatomy,
skin terminology or age classification.

## 3. Governing rule

When the user explicitly owns aesthetic appeal and Human Realism is active,
the Brain must satisfy aesthetic appeal and camera-observed human material in
the same complete direction.

```text
individual aesthetic appeal AND camera-observed human material
```

Neither may be traded away to satisfy the other. Attractiveness belongs to the
particular person's whole presence in the requested scene. It must not become a
generic beauty face or retouched surface. Realism must not be implemented by
making the person bland, tired, coarse or less attractive.

This rule is age-, ethnicity-, gender-, scene- and template-neutral. It applies
equally to a child casting portrait, an adult editorial portrait and an older
person's documentary image when the user actually requests aesthetic appeal.
It does not invent attractiveness when the user asks for an ordinary or harsh
documentary presentation.

## 4. Implementation boundary

The existing `aesthetic_boundary` and `photographic_material_requirement`
remain the frozen typed authority. No new face schema is introduced. The
Remote Brain instruction clarifies their joint meaning and remains conditional
on Human Realism plus explicit user-owned aesthetic direction.

The runtime must not add:

- facial proportions, feature lists, age-band morphology or beauty templates;
- skin recipes, pore lists, color formulas or negative-word stacks;
- regex/keyword creative routing;
- local Provider prompt suffixes or retry patches;
- a child, casting, complexion or demographic capability;
- a second Brain, Provider, review or selection path.

The Brain still returns one complete natural-language canonical prompt. Shared
Vision still judges the resulting pixels. One bounded retry, when authorized,
returns normalized observations to the Brain for a whole-prompt rewrite.

## 5. Acceptance

Pure-text acceptance uses the same controlled target, with zero image
references for every sample. The benchmark board remains view-only.

Required evidence:

1. `operation=image_generate` and declared/admitted reference counts both zero;
2. Remote Brain final signing with no fallback and exact canonical Prompt hash;
3. at least two independent samples from one accepted direction, or one initial
   sample plus the existing single bounded whole-Brain rewrite;
4. Shared Vision verified pass with no relevant synthetic-skin, over-smoothing,
   doll-face, age-presence or stock-expression finding;
5. strict human comparison at least 9.0/10 overall and in the benchmark quality
   band for natural beauty, fair neutral complexion, living skin material,
   developmental facial presence and calm alert attention;
6. adult and no-person regression controls proving no demographic or person
   treatment leaks into unrelated work;
7. complete V3 regression and canonical MCP/Web Prompt-parity tests.

Passing this controlled foundation test does not activate Professional,
Photography or E-Commerce production gates.

## 6. Iteration record

| Iteration | Pure T2I | Human finding | Shared Vision |
| --- | --- | --- | --- |
| V4 | yes, 0 refs | attractive and fair; surface too porcelain | HR 0.78/0.82, smoothing warnings |
| V5 | yes, 0 refs | good beauty and age; still globally polished | HR 0.74, synthetic/doll warnings |
| V6 | yes, 0 refs | more camera-like but less beautiful, warmer and older-reading | HR 0.76, smoothing/flat-light warnings |
| V7 | yes, 0 refs | stage/material pass, but explicit high-end individual beauty was weakened in developmental re-sign | verified pass, HR 0.88, overall 0.90 |
| V8 | yes, 0 refs | benchmark-band beauty and complexion in one sample, but skin remained stably polished across two samples | HR 0.78/0.78, smoothing warnings |
| V10 | yes, 0 refs | safer fully-clothed casting semantics and better depth; beauty still ordinary and stock-like | HR 0.84, smoothing/stock-finish warning |
| V12 | yes, 0 refs | beauty, complexion and cool presence near target; professional framing still induced stock-photo smoothing | HR 0.82, smoothing/stock-finish warning |
| V13 plan | no pixels | rejected before Image 2 because Brain invented a rounded-cheek/small-chin age recipe absent from user intent | architectural prompt-signoff failure |
| V13 corrected | yes, 0 refs | recipe removed; clean age coherence, but white studio still produced smooth skin and glossy eyes | HR 0.78, smoothing/eye warning |
| V14 | yes, 0 refs | real-room light reduced stock staging but lost vertical canvas, cool complexion and benchmark polish | HR 0.82; non-counting 1536x1024 canvas |
| V8 sample 3 | yes, 0 refs | strict human comparison reached benchmark band across beauty, stage, gaze and complexion | human 9.1; Vision HR 0.78 smoothing warning |
| V15 | yes, 0 refs | individual presence and developmental reading improved, but the output remained visibly warmer/yellower than the explicitly requested cool-fair benchmark | human color rejection; fixed warm-default conflict found in Doc159 Brain instruction |
| V16 | yes, 0 refs | fixed warmth removed and yellow reduced; complexion became slightly gray/ordinary and material remained too smooth | Vision warning, HR 0.84, age direction 0.92 |
| V17 | yes, 0 refs | cold-fair color reached the target band, but Brain treated `unretouched` as sufficient and compacted away the required light-dependent material relationship; pixels became uniformly pale and porcelain-like | human material rejection; final-signoff semantic gap |
| V18 | yes, 0 refs | final sign-off preserved color and material together; one renderer sample violated portrait canvas and the valid sample remained too polished | raw provider-only review HR 0.78; not accepted |
| V19 | yes, 0 refs | strongest cold-fair beauty and stage reading, but commercial fill still produced doll-like polish | raw provider-only review HR 0.72; human about 9.1 |
| V20 | yes, 0 refs | straight-out-of-camera treatment removed doll warning and improved naturalness, while one sample traded away some beauty/color lift | raw provider-only review HR 0.82 |
| V21 | yes, 0 refs | the single shared evidence-only Brain rewrite retained beauty, stage, cold-fair color and material; no local repair wording | raw provider-only review HR 0.84; human about 9.2 |
| V22 | yes, 0 refs | north-window photographic causality retained benchmark-band cold-fair beauty, six-year-old presence and living material | formal frozen-contract review hybrid/verified/pass, HR 0.91, overall 0.92; human 9.2–9.3 |

The red record is closed by V22, which passes both the formal frozen-contract
pixel review and strict benchmark comparison.

### V15 root-cause correction

The V15 canonical prompt explicitly asked for a cool-fair complexion, yet the
shared Brain instruction still required `restrained peach-pink warmth` and a
`neutral-to-slightly-warm` white balance. Those fixed defaults conflict with
user-owned undertone and can pull a correct cool-neutral request back toward
yellow warmth. Doc159 is therefore corrected in place: explicit hue and
undertone now win; an unspecified brief remains scene-balanced neutral; no
ethnicity or historical benchmark activates a complexion treatment. The
change is semantic Brain authority, not a color formula, local prompt suffix,
pixel correction, demographic branch or benchmark reference injection.

### V17 material-signoff correction

The V17 finalizer preserved the owned cold-fair color but reduced the material
decision to a generic `unretouched` label. Image 2 then rendered a uniform pale
surface. The shared Human Naturalness sign-off now treats this exactly like a
generic `photorealistic` label: it is insufficient when the complete high-key,
fair, cool or warm direction collapses human material into a uniform polished
surface. The Brain must reconcile the owned complexion and its
scene-observed, light-dependent human material in the same complete direction.
This remains a whole-image semantic requirement, not a pore list, facial
recipe, color formula or local Provider suffix.

## 7. Controlled acceptance closure

The accepted V22 sample used the normal General planning path and the exact
Brain-authored canonical Provider prompt:

```text
operation=image_generate
declared_reference_count=0
admitted_reference_count=0
creative_direction_owner=remote_v3_llm_brain
fallback_used=false
provider_prompt_sha256=1510444882732197d197c41215b1bf78c67a7256046b6e186de46c44ae1db429
```

The external child-model board remained view-only human evaluation evidence;
it was never supplied to Brain, Image 2 or Vision. The image was rendered once
from that canonical prompt through Codex built-in ImageGen. A later formal
review replay used the same user goal and a fresh frozen enforced Human Realism
contract, but did not generate or alter pixels.

Formal review result:

```text
mode=hybrid
verification_state=verified
status=pass
confidence=0.91
human_realism=0.91
overall=0.92
human_naturalness_attestation=pass
issue_codes=[]
```

Strict human comparison scores the accepted frame approximately 9.2–9.3/10:
the complexion reads as the explicitly requested cold-fair commercial ivory
without yellow warmth, gray bleaching or oily polish; the person reads as an
individual six-year-old with calm living attention; the lower-face presence,
beauty and clean white capture are in the benchmark quality band.

Earlier direct calls to the low-level Vision Provider were intentionally
non-certifying diagnostics. Without frozen user goal, active capability plan or
review contract they reported irrelevant `weak_lifestyle_context` on a casting
portrait and could not verify prompt-owned color or age. They remain useful red
observations, but they must not override the formal
`ScenarioRuntime → frozen review contract → VisionOutputInspector` result.

The accepted implementation changes only shared Remote-Brain semantic
authority. It adds no child or East-Asian runtime branch, no facial morphology,
age estimator, complexion formula, regex routing, local prompt suffix, pixel
postprocess, Provider, reviewer or retry path. Cool-fair color is honored only
when explicitly owned; unspecified and differently owned complexions remain
scene-balanced under Doc159.
