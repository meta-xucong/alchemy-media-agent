# 94 V3 Universal Visual Capability De-Overfitting And Governance Spec

> **Current-status note (Docs 134–135):** This governance rule now includes
> final-prompt ownership: orthogonal variables and evidence may be resolved
> deterministically, but only the remote Brain may translate them into a
> complete renderer instruction. Keyword/regex subject interpretation remains
> technical admission evidence, never creative or stylistic authority.

## 1. Purpose

Doc94 is the corrective authority for V3 foundation quality and the General
Template. It prevents a successful single-case fix from becoming a permanent
scene-specific branch in shared runtime code.

The governing rule is:

```text
Historical cases may prove a problem.
They may not become the vocabulary of the shared solution.
Shared capabilities operate on orthogonal visual variables and truth channels.
Specialized templates own scenario-specific recipes and deliverables.
```

This phase does not rebuild the V3 foundation. It corrects rule ownership and
runtime vocabulary inside the existing Visual Capability Cluster.

## 2. Compatibility And Authority

Doc94 extends and governs:

```text
Doc50  V3-native Visual Capability Cluster
Doc65  human photorealism and anti-AI-face layer
Doc70  real-camera anti-AI-face tuning
Doc71  attractive realism balance
Doc72  complexion and proportion guardrails
Doc76  foundation vs specialized-template governance
Doc77  real visual review and aesthetic stability
Doc78  long-term identity and beautiful realism
Doc86  portrait bone-structure identity lock
Doc87  portrait identity/style separation
Doc88  reference balance and prompt direction
Doc91  Human Realism Plugin ownership
Doc92  style-aware Human Realism
Doc93  reference-channel policy and prompt ownership
```

Doc94 does not replace their valid architecture. It supersedes any wording or
implementation that makes a shared runtime branch depend on a narrow cultural,
costume, demographic, marketplace, or one-project example.

Examples that are no longer valid shared-runtime authorities include:

```text
ancient / traditional / gufeng / hanfu profile names
East Asian summer complexion as an unconditional person default
kidswear or child catalog as a rendering profile
Korean or K-idol wording as a generic anti-AI-face category
one historic image id or one project prompt as an identity policy
```

These terms may remain in test fixtures, user prompts, migration notes, or
specialized-template data. They must not own a branch in the shared foundation.

## 3. Current Audit Finding

The V3 architecture is compatible. The following implementation details are
not fully compatible and require correction:

```text
human_photorealism.py has a moody/traditional keyword branch
human_photorealism.py has child/kidswear-specific rendering and retry branches
generic Human Realism positives contain East Asian summer/fair defaults
providers.py can inject an East Asian complexion guard into generic portraits
legacy negative guidance contains culturally named beauty stereotypes
Doc92 names concrete styles instead of orthogonal rendering conditions
```

The correct reusable concepts already exist underneath those examples:

```text
real-human intent
age fidelity
exposure key
contrast and color-temperature direction
skin specular response
skin texture retention
complexion preservation
identity geometry
prompt-owned styling channels
```

Doc94 keeps those concepts and removes the scene vocabulary.

## 4. Universal Runtime Contract

Shared Human Realism must consume or derive a generic rendering profile:

```text
UniversalHumanRenderingProfile:
  real_human_intent: true | false
  subject_presence: none | face | person | hand_skin | background_people
  age_fidelity: preserve_reference | follow_explicit_prompt | neutral
  exposure_key: low | medium | high | prompt_defined
  contrast_direction: soft | balanced | hard | prompt_defined
  color_temperature: cool | neutral | warm | prompt_defined
  skin_specularity: matte | natural | luminous | prompt_defined
  skin_texture: natural | detailed | soft_natural
  complexion_policy: preserve_reference | follow_explicit_prompt | neutral
  identity_priority: none | normal | high
  stylized_rendering: true | false
```

The LLM Brain may provide these values through structured intent, style notes,
or checkpoint metadata. Deterministic fallback may classify only generic visual
axes such as low/high key, cool/warm, matte/luminous, and real/stylized.

Forbidden fallback behavior:

```text
creating a cultural-style profile
creating a costume-specific profile
creating a marketplace-category rendering profile
assigning skin lightness from ethnicity alone
assigning an age-specific beauty recipe
```

## 5. Human Realism Correction

### 5.1 Base Guidance

Every real-human image may receive the same style-neutral foundation:

```text
real camera facial planes and lens perspective
natural skin texture and non-uniform tonal response
believable eye moisture and catchlight
real hairline, flyaways, and non-perfect strands
attractive facial harmony without geometry reshaping
age-consistent morphology
natural head, neck, shoulder, and body proportion
commercial polish through photography rather than beauty-app retouching
```

### 5.2 Complexion

Replace ethnicity-specific lightness defaults with:

```text
preserve the reference person's natural complexion direction
follow an explicit user-requested complexion change
do not let exposure, color grading, or retries accidentally gray, darken,
bleach, tan, or flatten the subject
```

Legacy issue codes remain readable for persisted jobs, but new review should
prefer generic codes:

```text
complexion_direction_drift
unintended_skin_darkening
unintended_skin_lightening
unflattering_skin_color_cast
```

### 5.3 Age Fidelity

Replace child-specific rendering profiles with one age-fidelity rule:

```text
preserve the age band and age-appropriate facial/body relationships visible in
the reference or explicitly requested by the user
reject adultification, infantilization, doll-like morphology, age-inappropriate
retouching, frozen template expression, and synthetic skin
```

Legacy child issue codes may map to `age_identity_drift` or
`age_inappropriate_rendering` at the compatibility boundary. They must not
activate a separate shared prompt recipe.

### 5.4 Style Adaptation

Replace named style profiles with orthogonal rendering conditions:

```text
low exposure key:
  preserve shadow detail and controlled highlight roll-off

high exposure key:
  preserve facial texture and avoid washed-out skin

matte skin specularity:
  preserve fine texture without dull or dead skin

luminous skin specularity:
  preserve pores and natural highlight roll-off without oily or plastic shine
```

The current prompt remains the authority for costume, culture, period, genre,
scene, light source, camera, and mood.

## 6. Ownership And File Placement

```text
visual_cluster/human_photorealism.py
  owns universal real-human rendering guidance and generic retry patches

visual_cluster/portrait_identity.py
  owns same-person geometry and feature relationships

visual_cluster/reference_channel_policy.py
  owns which reference channels may be inherited

generation_router/providers.py
  materializes accepted contracts; it does not invent demographic or scene
  defaults

src_skeleton/app/services/provider_reference.py
  performs byte-level reference preparation from a V3-owned evidence plan; it
  does not decide business meaning

product_api/service.py
  owns bounded retry orchestration and result assembly, not visual prose
```

No new top-level module is required for this correction.

## 7. Backward Compatibility

Persisted metadata may still contain:

```text
bright_fresh_commercial
moody_cinematic_traditional
child_catalog_natural
child_strict
Doc72 East Asian issue codes
```

Readers must continue to tolerate those values. New jobs write the universal
profile and may include a `legacy_profile_alias` only for audit migration.

Compatibility must not mean continuing to emit the old prompt fragments.

## 8. Development Steps

1. Add Doc94 authority notes to AGENTS.md and Docs 72, 91, 92, and 93.
2. Remove narrow cultural/costume style sets from Human Realism runtime code.
3. Replace bright/moody/child profile branching with generic rendering axes.
4. Remove unconditional East Asian/fair-complexion provider guidance.
5. Replace culturally named negatives with visual failure descriptions.
6. Keep Human Realism activation for any real person, including product-on-
   person, without adding a product-category rendering recipe.
7. Preserve legacy issue-code acceptance at review boundaries.
8. Add source audits proving the shared runtime has no narrow scene vocabulary.
9. Run the identity reinforcement phase only after this correction passes.

## 9. Required Tests

Unit tests must cover at least:

```text
low-key modern portrait and low-key historical styling resolve to the same
generic low-key rendering behavior
bright indoor and bright outdoor portraits resolve to the same generic high-key
texture guard
different age bands use one age-fidelity contract
different ethnicities preserve reference complexion without a shared ethnicity
default
product-on-person activates Human Realism while product-only does not
explicit illustration/CG intent disables photoreal Human Realism
```

Static source audit:

```text
the shared Human Realism and provider materializer must not contain active
hanfu/gufeng/ancient/kidswear/East-Asian/K-idol scene recipes
```

Test fixtures may contain those terms to prove the generic system handles them.

## 10. Acceptance Gate

Doc94 passes only when:

```text
no scene-specific shared runtime branch remains
legacy metadata remains readable
the General Template UI gains no new complexity
real-human quality guidance remains active across templates
identity, product truth, and prompt ownership tests still pass
full V3 and root regressions pass
```

