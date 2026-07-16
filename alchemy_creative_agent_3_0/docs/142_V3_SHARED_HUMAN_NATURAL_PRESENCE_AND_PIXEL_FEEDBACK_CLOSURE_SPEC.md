# Doc142 - V3 Shared Human Natural Presence and Pixel Feedback Closure

Status: **active shared-foundation baseline; M0-M4 are implemented and
recorded.** Doc143 refines the next forward Human Realism contract after M4
exposed remaining generic-personhood and painterly-material weaknesses.

This is the bounded quality phase after Doc141. It improves the existing shared
Human Realism capability without replacing V3 architecture, adding a template,
or restoring a local prompt-composition path.

## 1. Decision and scope

The blue-dress comparison proved that the correct common planning path can be
active while the rendered person remains overly polished, catalog-like, or
generically idealized. That is a quality-depth gap. It is not evidence that a
child, garment, regional, or template-specific module is missing.

The forward path remains unchanged:

```text
protected user and admitted-reference truth
  -> Remote Brain semantic task profile and activation intent
  -> frozen CapabilityActivationPlan / envelope / constraint ledger
  -> Remote Brain complete canonical prompt finalization
  -> Remote Brain Human Realism natural-presence deliberation and re-signing
  -> exact GPT Image 2 materialization
  -> shared vision_model or hybrid pixel review
  -> bounded Remote Brain whole-prompt revision when review warrants it
  -> shared final-result selection and append-only history
```

Doc142 changes the depth and auditability of Human Realism. It does **not**
change the Template -> ScenarioRuntime -> Brain -> envelope -> Provider ->
review/retry/delivery architecture.

## 2. Governing boundaries

The following remain authoritative:

```text
Doc93   reference-channel ownership
Doc95/96/97 portrait evidence, high-fidelity identity, and continuity
Doc100  GPT Image 2 renderer boundary
Doc101/102 frozen capability activation and execution
Doc113  execution truth, template ownership, and constraint ledger
Doc121  provider/reviewer evidence continuity
Doc128  shared Human Realism contract and real-pixel withholding
Doc134/135 LLM-first ownership and retirement of forward local creative logic
Doc136-140 Human Realism sign-off, natural presence, and complete Brain input
Doc141  accepted planning/parity baseline and quality follow-up evidence
```

Doc142 is shared foundation work. It applies only when the frozen plan
activates `human_realism` for a photoreal visible person. It must not create a
child, teen, kidswear, East Asian, fashion, e-commerce, photography, or
social-media capability, route, template rule, review profile, or prompt
recipe.

### 2.1 Authority resolution

Doc136 records the v1 typed-contract baseline and its historical implementation
evidence. Doc138 records the former forward v2 Human Realism semantic-contract
authority: it retains the v1 boundary and adds only the generic
natural-presence and aesthetic-boundary decisions. Doc137 preflight remains
mandatory. Doc139 remains the one independent re-signing pass. Doc142 extends
that same pass with a schema-only `approved|rewritten` receipt; it neither adds
a third Brain call nor creates a local decision, prompt, retry or review path.

Where an older document describes a retry repair intent, it means normalized
semantic review evidence supplied to the Brain, never literal runtime prose.
Where a legacy record contains v1 fields or local phrase data, it remains
read-only archival provenance and cannot reach a new enforced finalizer,
Provider or Local MCP relay.

## 3. Non-negotiable invariants

```text
1. Remote Brain owns semantic judgment and every complete renderer-facing
   natural-language prompt.
2. Local runtime validates contract shape, cardinality, hashes, immutable
   bindings, evidence links, budgets, and safety boundaries only.
3. Human Realism supplies typed obligations and review ownership only. It
   never supplies local positive prompts, negative prompts, camera/pose rules,
   beauty wording, anatomy wording, or retry prose.
4. Provider receives exactly the final complete prompt signed by Remote Brain;
   it may bind transport/reference inputs but cannot append natural language.
5. Review supplies normalized semantic evidence only. A retry receives it via
   the shared Brain path and returns a new whole signed prompt.
6. General remains neutral. E-Commerce and Photography keep their existing
   LLM-first delivery contracts. No template owns Human Realism creativity.
7. Local MCP remains a canonical-prompt/reference relay, conversation-only and
   non-certifying. It cannot review pixels, retry, persist candidates, or
   create delivery.
```

## 4. Interpreting the supplied realism observations

The supplied observations about face regularity, expression, anatomy, hands,
clothing, hair, light, depth, background integration, artificial gloss, and
ordinary social presence are useful quality evidence. They must not become a
fixed prompt appendix or a local detection-and-rewrite checklist.

They are represented only through existing broad shared dimensions:

| Observation family | Shared semantic/review interpretation | Owner |
| --- | --- | --- |
| Face, expression, age, over-beautification | individual human presence and age/identity fidelity | Brain + shared review |
| Hands, body, relaxed action, hair and clothing contact | physical coherence | Brain + shared review |
| Skin retouch, sheen and material response | human rendering and skin/retouch | Brain + shared review |
| Light, shadow, depth and background integration | scene coherence | Brain + shared review |
| Artificial, stock or over-polished finish | rendering artifact and overall quality | Brain + shared review |

“Ordinary SNS post” is not a default quality target. It is used only if the
user explicitly asks for it. Editorial, glamorous, dark, historical,
cinematic, commercial, or stylized user intent remains prompt-owned; Human
Realism prevents synthetic rendering without flattening legitimate style.

## 5. Current gap and target behaviour

Docs137-140 correctly guarantee:

```text
complete remote semantic task profile
-> frozen generic Human Realism contract
-> Remote Brain canonical finalizer
-> one independent Remote Brain re-signer
```

The remaining gap is qualitative. A formally valid re-signer can retain a
direction that only says “natural”, “candid”, or “photorealistic”, leaving the
renderer too much room to create a generic commercial beauty archetype.

The target is a more accountable Brain decision, not a stronger local prompt:

```text
Does the complete direction describe a particular person plausibly present in
the user-owned situation, with age, physical relationship, material response,
light and environment cohering as one photograph?
```

The Brain silently answers this from the full user direction, admitted
evidence, rendering intent, and shared semantic contract. It keeps or rewrites
the whole prompt. It must not expose hidden reasoning, issue codes, checklists,
or fragments for local concatenation.

## 6. Phase A: upgrade the existing re-signer

The first implementation does **not** add a third Remote Brain round trip. It
upgrades the existing `provider_prompt_human_naturalness_resign` request into
a mandatory natural-presence deliberation plus whole-prompt re-signing.

The re-signer may receive only:

```text
protected user direction
prior Brain-authored complete canonical candidate
frozen rendering intent and template deliverable binding
admitted reference roles and immutable provenance bindings
typed generic Human Realism semantic contract
bounded normalized retry evidence, only for an existing shared retry
```

It must not receive local prompt/negative text, regex hits, keyword labels,
template recipes, slots, camera/crop defaults, raw visual-cluster prose,
private provider errors, raw pixels, hidden reasoning, or
demographic-specific phrase lists.

For each output index, the response still contains one complete canonical
prompt and the existing preflight receipt. It additionally carries this small
auditable receipt:

```text
human_naturalness_decision:
  contract_version: v3_human_naturalness_decision_v1
  status: approved | rewritten
  owner: remote_v3_llm_brain
```

This receipt is not a score, rationale, prompt fragment, or provider
instruction. Runtime validates only its schema, cardinality, owner and frozen
binding. It must never inspect prompt words with a regex or phrase heuristic.

`rewritten` means the returned complete prompt differs because Brain judged a
revision necessary. `approved` means Brain independently accepted it. The
returned prompt is the only renderer-facing text in either case.

An active Human Realism operation blocks before Provider/MCP materialization
when re-signing is unavailable or malformed, has the wrong count, lacks the
semantic-preflight or naturalness receipt, has a wrong owner/version, or has a
stale envelope/ledger binding. There is no local recovery prompt and no
one-pass-finalizer downgrade.

## 7. Shared pixel-feedback closure

The existing `vision_model` or `hybrid` reviewer remains the only authority
that can assess rendered pixels. Doc142 strengthens its handoff, not its
ownership.

For active Human Realism, review evaluates the five broad dimensions in section
4 against final pixels and the same admitted evidence used by Provider. It
returns the ordinary shared verdict:

```text
pass | warning | fail_retryable | fail_final | manual_confirmation_required
```

```text
vision_model/hybrid pass or allowed warning -> normal shared delivery policy
metadata_only -> non-certifying; cannot make a Human Realism quality claim
fail_retryable -> only the existing bounded retry allocation
fail_final -> withhold delivery and preserve append-only evidence
manual_confirmation_required -> visible to the user and excluded from
                                automatic certification
```

One allowed retry passes normalized semantic evidence to the next Brain
finalization/re-signing cycle. Brain reauthors the full prompt from frozen facts
and evidence; it never receives a local “fix face/skin/hand” phrase.

## 8. Legacy compatibility retirement

Historical compatibility helpers may remain readable for archival jobs, but the
following are forbidden as executable forward inputs for new enforced jobs:

```text
Human Realism retry_patch_templates
Human Realism prompt_additions / negative_additions
locally compiled age, beauty, anatomy, skin, hand, hair, light, or background
repair prose
keyword/regex results used to decide visual style, human quality, or final
renderer wording
legacy retry patch fields projected to Provider materialization
```

Allowed deterministic local checks remain limited to schema/cardinality/hash
verification, dependency and evidence-link validation, reference admission,
transport capability, safety policy handling, frozen provenance, and retry
budget enforcement. They never choose a person’s appearance, creative medium,
or visual language.

## 9. Template and reference isolation

```text
General: shared improvement only when remote semantics say a photoreal visible
person is present; no lifestyle recipe or professional-set behaviour.

E-Commerce: Human Realism may improve a visible model/person but never owns
products, platform rules, copy, roles, or delivery count.

Photography: Human Realism may improve rendering but never provides camera,
lighting, pose, or named-photographer direction.

Reference: a product-only reference is product truth, not portrait identity.
Without a portrait reference, a task may request an age/appearance direction
but cannot claim same-person identity fidelity.
```

## 10. Required red regressions

```text
1. Remote visible-person profile -> Human Realism -> finalizer + deliberating
   re-signer exactly once each.
2. Product-only, animal-only, hidden-person and whole-image-stylized profiles
   do not invoke the human deliberation.
3. Missing/malformed decision receipt blocks before Provider and Local MCP.
4. Runtime validates receipt shape/binding, never prose quality by keywords.
5. Web materialization and Local MCP relay preserve the exact final prompt and
   admitted-reference hashes.
6. Review retry supplies normalized evidence only; no local Human Realism
   string reaches the next Brain prompt or Provider.
7. metadata_only cannot certify or automatically deliver an active Human
   Realism result.
8. Legacy retry fields may be read from history but cannot execute for a new
   enforced job.
9. General, E-Commerce and Photography retain their contracts; no narrow
   demographic/apparel/template branch is introduced.
10. The same improvement passes adult ordinary-person, young-person with an
    authorized product reference, person/object interaction, and a non-bright
    real-person context.
```

## 11. Delivery sequence

### M0 - Contract and red tests

Add the receipt schema and red regressions. Do not modify templates or the
Provider materializer.

### M1 - Deliberation receipt

Extend the existing re-signer request/response contract and ScenarioRuntime
validation. Preserve fail-closed behavior and exact prompt cardinality.

### M2 - Forward-path closure

Remove or hard-disable local Human Realism string-patch execution for new
enforced jobs. Preserve clearly labelled archive-read compatibility only.

### M3 - Review-to-Brain retry handoff

Prove every bounded retry uses frozen normalized review evidence and returns a
new complete signed prompt plus decision receipt.

### M4 - Cross-scene acceptance

For adult ordinary-person, young-person/product-reference, person/object
interaction, and a non-bright real-person context, retain only safe
provenance: active capabilities, Brain-stage receipts, prompt/reference hash
parity, review mode/verdict, retry count, and final delivery/withholding state.
Do not commit raw prompts, credentials, endpoints, hidden reasoning, or
unlicensed media.

### Implementation record (2026-07-16)

M0-M3 are implemented in the shared Brain, ScenarioRuntime, Human Realism and
Local MCP provenance paths. The receipt is required only for the existing
active Human Realism re-signing stage; it is validated for exact output
cardinality, version, owner and `approved|rewritten` status. A missing or
malformed receipt blocks before Provider or Local MCP materialization.

Enforced review-to-retry transport now contains only normalized shared issue
evidence. It cannot construct Human Realism renderer phrases. Regression
coverage proves the same contract across ordinary adult, young-person/product,
person/object interaction and low-key older-adult code contexts, plus full V3
and Local MCP parity suites.

M4 real-pixel acceptance completed in an isolated controlled runtime. Every
matrix cell received a remote-Brain direction with no fallback, an approved
natural-presence re-signing receipt, real Provider pixels, and a shared
`hybrid / pass / verified` review before one final delivery. Planning/MCP
parity remains supporting provenance only; it is not used as a substitute for
the pixel result.

## 12. Acceptance and non-goals

Doc142 code closure is accepted when architecture and template boundaries remain
unchanged; enforced real-person prompts are Brain-authored and signed; no local
Human Realism text affects Provider input; metadata-only cannot certify
delivery; bounded retry reuses Brain; and cross-template/full-V3 regressions
pass. The release-quality portion is accepted only when the cross-scene matrix
has shared-review evidence where real pixels are available.

MCP may prove planning, prompt, reference and materialization parity. It cannot
by itself satisfy pixel review, production Provider, Gate C/D, P10,
E-Commerce Gate, or delivery certification.

This document does not authorize a new Provider, Brain, storage system, review
system, retry loop, template, specialist mode, image lifecycle, local prompt
optimization, twenty-five rendered instructions, or a subject-specific quality
branch.

### M4 controlled evidence record (2026-07-16)

The complete four-cell matrix ran in one isolated controlled runtime. This is
safe provenance only: it contains no media, raw prompts, credentials,
endpoints, hidden reasoning, or provider-internal responses.

| Matrix cell | Provider operation | Shared review | Retry | Final delivery |
| --- | --- | --- | --- | --- |
| young person with authorized product reference | one image edit; pixels received | `hybrid / pass / verified` | 0 of 1 | one ready output |
| ordinary adult person | one image generation; pixels received | `hybrid / pass / verified` | 0 of 1 | one ready output |
| person/object interaction | one image generation; pixels received | `hybrid / pass / verified` | 0 of 1 | one ready output |
| non-bright real-person context | one image generation; pixels received | `hybrid / pass / verified` | 0 of 1 | one ready output |

Across all four cells, the active Human Realism path used the remote Brain,
did not fall back, produced exactly one complete direction, and carried an
`approved` natural-presence re-signing receipt owned by
`remote_v3_llm_brain`. The outputs were physically coherent with their
requested contexts and did not show a systematic bright-commercial-style
override in the low-key scene.

For the young-person/product-reference cell, the result is age-appropriate,
fully clothed, and coherent with the supplied garment. It is **not** a
SKU-level garment-print certification: the authorized reference was retained
materially, but generated artwork remains an approximation and must not be
represented as an exact print match.

This completes Doc142's M4 cross-scene Human Realism release-quality matrix.
It does not certify template-specific production gates such as E-Commerce Gate
C/D or Photography P10, which retain their own material, workflow and
browser-acceptance requirements.
