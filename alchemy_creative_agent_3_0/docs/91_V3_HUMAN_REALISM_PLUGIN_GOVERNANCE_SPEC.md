# 91 V3 Human Realism Plugin Governance Spec

> **Doc143 forward-path note:** fresh enforced Human Realism jobs use the
> v3 semantic contract and frozen pixel-authenticity attestation defined by
> Doc143. Historical detailed child/skin wording in this document remains
> read-only compatibility context and must not become a renderer word list.

> **Doc135 forward-path note:** this shared plugin may freeze whether Human
> Realism is required and what pixel evidence to review. It may not append
> local realism words after the remote Brain's final canonical sign-off.

Doc94 correction note:

```text
Doc91 remains the ownership authority for the Human Realism Plugin. Doc94
supersedes child/kidswear, East Asian summer/fair, and other narrow named
runtime profiles. New jobs use generic age fidelity, exposure, skin response,
complexion preservation, and real-human rendering variables. Legacy metadata
and issue codes remain readable only for compatibility.
```

Doc93 compatibility note:

```text
Doc91 remains the Human Realism placement, evidence, and contribution authority.
Doc101 owns activation. Reference inheritance belongs to Doc93. Human Realism
may improve real-camera rendering and reject AI artifacts, but it cannot promote
source hair, wardrobe, lighting, scene, camera, or style into identity truth.
```

Doc101 activation correction:

```text
Doc91 remains the Human Realism ownership and contribution authority. Doc101 is
the latest activation authority. Human Realism publishes manifest evidence and
contribution contracts; it must not independently inject rules from broad
keyword matching. Only a frozen Doc101 activation plan may enable its prompt,
review, or retry contributions.
```

Doc113/Doc117 execution correction:

```text
Doc113 owns the single normalized intent, execution envelope, resolved ledger,
and truthful review contract. Doc117 closes real-reference admission and
no-pixel Provider failure reporting without adding a second lifecycle. Human
Realism is a shared semantic quality capability inside that contract: it never
owns a template role, an age classifier, a vertical route, or a catalogue of
prompt atoms. The remote Brain owns natural-language creative direction; the
frozen local plan decides whether Human Realism is active.

The former `e458d23` candidate established the real-visible-person activation
invariant and is now historical integration provenance. Doc128 is the forward
implementation closure: it preserves that invariant while replacing casebook
prompt atoms with concise shared constraints and review dimensions.
```

## 1. Purpose

Doc91 formalizes the reusable Human Realism Plugin for V3.

The product term is simple:

```text
When V3 generates real people, models, hands, faces, skin, or people-worn
products, the result should look like a real camera photograph of a real person,
not a generic AI face, doll face, wax face, beauty-filter face, or synthetic
stock-model face.
```

This document exists because validation exposed a cross-template activation
gap. The activation invariant is integrated; its regression remains explicit
under Doc128:

```text
Real people can be present while the requested subject is a product.
Human quality must therefore depend on normalized visible-person evidence, not
on `subject_type`, template name, product category, or a prompt keyword list.
```

Therefore human realism must be governed as a shared V3 visual capability, not
as a General Template feature, not as an E-Commerce feature, and not as scattered
prompt snippets.

## 2. Compatibility And Authority

Doc91 extends and consolidates:

```text
Doc50  V3-native Visual Capability Cluster
Doc56  human natural variation and identity consistency
Doc61  portrait commercial consistency and Lovart benchmark
Doc64  commercial quality closure and retry planning
Doc65  human photorealism and anti-AI-face layer
Doc70  real-camera anti-AI-face tuning
Doc71  attractive realism balance
Doc72  East Asian fair-complexion and proportion guardrails
Doc76  foundation vs specialized-template governance
Doc77  real visual review and aesthetic stability
Doc78  long-term identity and beautiful realism tuning
Doc83  retry delivery and portrait reference conflict closure
Doc85  image-to-image identity/product truth transfer
Doc86  portrait bone-structure identity lock
Doc87  portrait reference identity/style separation
Doc88  portrait reference balance and prompt mood preservation
Doc90  General Template advanced reference priority controls
```

Doc91 is the latest authority for:

```text
where human realism logic lives
what evidence and profiles the activation planner may use for human realism
how anti-AI-face rules are shared across General, E-Commerce, and future
Photography templates
how recent portrait realism tuning is consolidated into one pluggable module
how to audit that no new human-realism rules are scattered into templates or
Central Brain code
```

Doc91 does not replace:

```text
Project Mode
ScenarioRuntime
Scenario Packs
LLM Brain Adapter
provider routing
reference upload compression
Doc85 reference truth layering
Doc86 bone-structure identity lock
Doc87 identity/style separation
Doc88 reference balance and prompt mood preservation
Doc90 Advanced Reference Priority Controls UI
```

If an earlier document implies that human realism is only a portrait or
General Template concern, Doc91 wins.

If an earlier implementation uses only `subject_type == "character"` to decide
whether anti-AI-face and real-human rules apply, Doc91 supplies the richer
evidence model and Doc101 owns the final activation decision.

If a template needs real people, it must call the shared Human Realism Plugin
instead of duplicating human face prompt rules locally.

## 3. Architecture Placement

The plugin belongs inside the existing Visual Capability Cluster.

```text
V3 Project
  -> Template / Scenario Pack
      -> ScenarioRuntime
          -> LLM Brain summary
          -> Visual Capability Cluster
              -> Human Realism Plugin
                  -> Activation classifier
                  -> Real-human prompt guidance
                  -> Anti-AI-face negative guidance
                  -> Child/teen model realism guard
                  -> Post-generation realism review
                  -> Retry patch builder
              -> Portrait Identity Modules
              -> Product Identity Modules
              -> Suite / Mode Director
              -> Commercial Quality Review
          -> Prompt Compiler
          -> Provider
          -> Project output reconciliation
```

The current `human_photorealism.py` module is the correct implementation home.
Future code may keep the existing file name or introduce a thin
`human_realism_plugin.py` wrapper, but it must not create a second parallel
human-realism framework.

Allowed dependencies:

```text
LLM Brain may provide intent and scene summary.
Template policies may provide subject slots, product category, and requested
deliverable type.
Asset role analysis may identify face/person/product/style references.
Portrait identity modules may provide bone-structure and reference-truth rules.
Commercial review may consume the plugin's issue codes.
```

Forbidden dependencies:

```text
Do not call V1/V2 runtime code.
Do not move human-realism prompt rules into Central Brain.
Do not place template-specific product-suite maps inside the plugin.
Do not let General Template become a Photography or E-Commerce deliverable map.
Do not expose raw engineering issue codes in beginner-facing UI.
```

## 4. Current execution contract

Human Realism is a shared quality capability, not a prompt template. Its active
contract is deliberately small:

```text
normalized factual evidence
  -> frozen CapabilityActivationPlan / CapabilityExecutionEnvelope
  -> remote Brain natural-language image direction
  -> GPT Image 2 materialization
  -> shared vision/hybrid pixel review
  -> bounded, observed-issue repair and final-winner selection
```

The capability contributes a semantic quality concern: preserve a convincing
real human without plastic skin, implausible anatomy, frozen expression, or a
person detached from the photographed environment. It preserves prompt-owned
style, light, scene, wardrobe, pose, and mood rather than replacing them with a
preferred commercial look. It also preserves Doc93 reference boundaries: an
identity reference establishes only the channels the user/reference policy has
actually assigned.

### 4.1 Evidence and activation

The local normalizer and activation planner use normalized evidence, not broad
keywords or product categories:

- a real, visible person or human surface is required by the request or trusted
  task profile;
- a person is actually required to wear, hold, or use a product
  (`product_on_person_detected`);
- a portrait/person reference or an explicit human-rendering request assigns a
  relevant reference channel; or
- the user explicitly requests age fidelity for a real-person target.

An explicitly non-photoreal/stylized person, a nonhuman target, or conflicting
evidence must result in an explicit inactive/blocked decision. A garment size,
an ecommerce label, a word such as "photo", or a human-like product shape is
not enough. The plan is authoritative: remote Brain output cannot remove an
active shared capability, and the capability cannot self-activate after the
plan has frozen.

### 4.2 Contribution, review, and retry

Human Realism receives the resolved evidence and envelope; it must not emit a
second structured prompt, static camera/lighting/pose recipe, named demographic
profile, or template delivery role. The remote Brain remains the sole owner of
the complete natural-language creative image direction. The capability and
review share only broad quality dimensions such as facial-feature coherence,
skin/material response, anatomy/contact/drape plausibility, expression
naturalness, person-to-scene light/depth integration, and explicit age fidelity
when the request supplies it.

After pixels exist, shared vision/hybrid review records observed defects using
generic issue evidence. Any bounded retry is an owner-local repair of that
observed defect through the frozen envelope and ledger; it is not an appended
catalogue of anti-AI phrases. `metadata_only` and local heuristics can never
certify person, anatomy, age, identity, or product truth. Before pixels exist,
Doc117's Provider classifier owns the terminal no-pixel state and no visual
repair occurs.

### 4.3 Compatibility and regression locks

`product_on_person_detected` is the only emitted generic field. The older
`product_on_person` and `ecommerce_human_model_detected` spellings may be read
at an explicit compatibility boundary only; they must not be emitted into new
plans, ledger entries, prompts, review records, or retries. Historical child
issue aliases may be displayed/read for old data but cannot form a new child
branch or direct retry instruction.

The required regression set covers at least a real adult portrait/lifestyle
target, product-on-person, a non-person product, and an explicitly stylized
human target. Child/apparel fixtures remain useful regression samples, but they
are not a runtime category. A real-provider sample is a quality gate only after
candidate pixels plus vision/hybrid provenance exist.

## H1. Historical pre-Doc94 contract (compatibility material only)

The remainder of this document records the earlier proposal that led to the
shared capability. It is **not** forward implementation authority where it
describes subject kinds, strictness tiers, named demographic branches, prompt
fragments, or template/product-category activation. Retain it solely to read
legacy records and understand the historical test vocabulary. The current
contract is Sections 1--4.3 plus Docs93, 94, 102, 111, 113, 114, and 117.

### Historical plugin-contract proposal

Future code should expose a single activation contract.

```text
HumanRealismActivation:
  applies: bool
  disabled_by_style: bool
  human_subject_kind:
    none
    adult_portrait
    child_or_teen_model
    fashion_model
    product_on_person
    hand_or_skin_detail
    crowd_or_background_people
  strictness:
    off
    light
    balanced
    commercial_strict
    child_strict
  reason_codes: list[str]
  evidence: dict
  inherited_identity_policy_id: optional string
  review_issue_codes: list[str]
```

Required inputs:

```text
user_input
template_id
scenario_id
subject_type
variation_mode
requested_count
asset roles and reference roles
template policy
product category or product brief when available
LLM Brain intent summary when available
advanced reference controls
selected project references
```

Required outputs:

```text
positive prompt fragments
negative prompt fragments
reference preserve rules
review targets
retry issue codes
retry patch fragments
metadata for audit
```

Metadata must be easy to audit:

```text
human_realism_plugin:
  applies: true
  reason_codes:
    - ecommerce_human_model_detected
    - real_photo_intent
  human_subject_kind: product_on_person
  strictness: commercial_strict
  disabled_by_style: false
  doc: "91"
```

## H2. Historical activation-evidence examples

The signals below are evidence supplied to Central Brain and the Doc101
Activation Planner. They are not permission for the plugin to self-activate or
write directly into the final prompt.

The Activation Planner may enable the plugin when verified task evidence says
the requested image contains or implies real humans.

Strong enable signals:

```text
portrait
photo portrait
real person
model
woman / man / girl / boy / child / kid / baby / family
face
skin
hand
person wearing the product
fashion model
clothing on model
kidswear model
beauty photo
lifestyle photo with people
street photo
documentary portrait
commercial photography with a person
product-in-use by a person
hand-held product
```

Chinese evidence may include equivalent natural-language concepts such as:

```text
真人, 人像, 写真, 模特, 美女, 人物, 女孩, 男孩, 儿童, 小朋友,
脸, 皮肤, 手, 穿着, 服装上身, 有人物的生活方式图, 街拍人物
```

Generic words such as `photo`, `photography`, `照片`, or `摄影` are not human
evidence by themselves. They require a visible-person entity, person reference,
or explicit human-subject phrase in the task profile.

The planner may enable it even if `subject_type` is `product` when:

```text
the product is worn by a person
the product is held by a visible hand
the scene includes a clear model face or body
the product category is fashion, apparel, kidswear, accessories, beauty,
fitness, lifestyle, or other people-present product photography
the user uploads a face/person reference for a product scene
```

The planner must disable or reduce the plugin when there is no verified human
entity or when the user clearly requests a non-real human rendering:

```text
anime
manga
cartoon
illustration
3D render
CG / CGI
game character
toy figure
doll as the desired subject
mascot
clay / vinyl / plastic figurine
intentional surreal synthetic beauty
```

Important distinction:

```text
"avoid doll-like face" is a negative realism instruction and must not disable
the plugin.

"make a doll character" is a positive stylized request and may disable or
reduce the plugin.
```

## H3. Historical ownership table

The following ownership table is mandatory.

| Area | Owning module | Doc91 rule |
| --- | --- | --- |
| Real skin texture, pores, natural facial asymmetry, real-camera face rendering | Human Realism Plugin | Consolidate here |
| Anti-AI-face negative prompts and issue codes | Human Realism Plugin | Consolidate here |
| Attractive but real facial-feature balance | Human Realism Plugin plus identity modules | Prompt/review wording here, identity geometry elsewhere |
| East Asian fresh/fair complexion guard when user did not request tan/dark skin | Human Realism Plugin | Consolidate as realism/beauty guard |
| Head/body proportion and neck/shoulder realism for people | Human Realism Plugin | Consolidate as realism guard |
| Child/teen model naturalness | Human Realism Plugin | Add child-strict branch |
| Uploaded portrait same-person identity | Portrait Identity Modules | Do not move into Human Realism Plugin |
| Bone structure and facial-feature relationship locks | Portrait Identity Modules | Human Realism consumes, does not own |
| Reference identity/style separation | Portrait Identity Modules | Doc87/Doc88 remain authority |
| Product shape, label, SKU, surface, and package identity | Product identity/template modules | Do not move into Human Realism Plugin |
| Product-on-model human face realism | Human Realism Plugin | Must activate even in E-Commerce |
| Suite role planning and shot purpose | Mode/Suite Director or specialized template | Do not move into Human Realism Plugin |
| Real-output review, retry budget, final delivery filtering | Quality/retry/output reconciliation modules | Consume plugin issue codes |

## H4. Historical tuning observations

The following recent updates must be treated as Human Realism Plugin behavior,
not scattered template behavior:

```text
do not make people less attractive merely to make them look real
preserve beautiful facial-feature proportions, including brows, eyes, nose,
mouth, jaw, chin, and face harmony
avoid AI idol-card polish, beauty-app smoothing, waxy highlights, poreless
skin, plastic eyes, generic influencer face, and template smile
for East Asian portrait or fresh summer briefs, do not darken skin by default
unless the user requests tan, bronze, dark, sunburned, or similar direction
use soft bounce light, real lens imperfection, natural skin texture, under-eye
detail, hairline detail, flyaway hair, and believable skin response to light
allow expression, pose, head angle, camera distance, and hair styling variation
while preserving identity-critical traits through Doc86/87/88
for child/teen/family/commercial kidswear models, avoid doll-like face, adult
makeup, pageant polish, frozen smile, over-large glossy eyes, and synthetic
skin
```

## H5. Retired child/teen branch proposal

When `human_subject_kind` is `child_or_teen_model`, strictness must be at least
`child_strict` unless the user explicitly requests a stylized illustration.

This branch is only an auxiliary specialization inside the general Human
Realism Plugin. It exists to prevent child, teen, family, and kidswear model
images from becoming doll-like or adultified. It must not turn Doc91 into a
child-specific or kidswear-specific module, and it must not weaken the main
general-person realism solution.

Positive guidance:

```text
real child or teen photography
natural child facial proportions
soft real skin texture
age-appropriate expression
relaxed real-camera smile or quiet natural expression
believable hairline, teeth, eyes, cheeks, and neck/shoulder proportion
commercial catalog polish without doll-like retouching
```

Negative guidance:

```text
doll-like child face
plastic toy face
adult beauty makeup on child
pageant-model polish
frozen perfect smile
over-large glossy eyes
over-smoothed child skin
synthetic catalog mannequin
unreal teeth
AI child model face
```

Retryable issue codes:

```text
doll_like_child_face
adultified_child_model
synthetic_child_skin
pageant_polish_child_face
frozen_child_smile
unreal_child_eyes
unreal_child_teeth
child_face_ai_render
```

## H6. Historical review/retry examples

When the plugin applies, post-generation review must check:

```text
skin realism
eye realism
expression realism
face geometry attractiveness
beauty-filter / idol-card / AI-influencer artifacts
doll-like or mannequin-like face
head/body proportion
child/teen age-appropriate realism when relevant
watermark, fake text, or obvious generation artifacts
```

The plugin does not own retry orchestration, but it must provide retry patches.

Retry patch examples:

```text
issue: plastic_skin
patch: add natural skin texture, pore-level variation, non-uniform cheek tone;
       reduce beauty-filter smoothing and wax highlights

issue: generic_ai_beauty_identity
patch: preserve individual facial character and feature relationships; avoid
       generic influencer face replacement

issue: doll_like_child_face
patch: real child photography, age-appropriate face, natural expression, no
       doll/toy/pageant polish
```

Bounded retry remains controlled by the existing retry layer. Doc91 does not
increase retry loops by itself.

## H7. Historical frontend note

No new default beginner UI complexity is required.

Default behavior:

```text
The system detects whether Human Realism is needed.
The user does not need to understand or select the plugin.
```

Advanced controls may expose a simple option later, but only inside existing
advanced/collapsed panels. The interface should not show internal terms such as
`human_realism_plugin`, `anti_ai_face_issue_codes`, or `subject_type`.

Beginner-facing wording should be simple:

```text
V3 will keep people looking like real photographed humans.
V3 will avoid fake skin, doll faces, and over-polished AI faces.
```

## H8. Retired implementation plan

Future coding must follow this order:

```text
1. Audit current rules in visual_cluster/human_photorealism.py,
   visual_cluster/module.py, portrait_identity.py, commercial_quality.py,
   product_api/service.py, vision_inspector.py, vision_provider.py, and
   related tests. `casebook_recipes.py` is compatibility-only history, not a
   forward contribution source.

2. Keep the existing HumanPhotorealismLayer as the implementation base.
   Rename only if it is a thin compatibility wrapper; do not duplicate it.

3. Add a formal activation classifier that considers prompt, template,
   subject_type, product category, asset roles, face/person references,
   selected references, and LLM Brain intent summary.

4. Replace subject_type-only activation with human-present activation.

5. Ensure E-Commerce product-on-model, kidswear, apparel, beauty, lifestyle,
   and hand-held product scenes can activate the plugin even when the primary
   subject remains product.

6. Add child/teen model strictness and issue codes.

7. Attach anti-AI-face review whenever Human Realism applies.

8. Emit human_realism_plugin metadata for every job.

9. Keep portrait identity transfer, bone-structure lock, and prompt mood
   preservation in Doc85-88 modules. Human Realism may consume their output but
   must not replace their ownership.

10. Update tests before real-image validation.
```

## H9. Historical test inventory

Focused tests:

```text
General portrait prompt activates Human Realism.
General non-human product prompt does not activate Human Realism.
E-Commerce kidswear/model prompt activates Human Realism even when subject_type
is product.
Fashion/clothing-on-person prompt activates Human Realism.
Hand-held product prompt activates at light or balanced strictness.
Explicit anime/cartoon/3D/CG request disables or reduces Human Realism.
"avoid doll-like face" does not disable Human Realism.
Child model path adds child-strict guidance and child issue codes.
Uploaded portrait reference still routes identity ownership through Doc85-88.
No new Central Brain prompt snippets duplicate Human Realism rules.
No template-local anti-AI-face prompt block is introduced.
```

Regression tests:

```text
test_v3_human_photorealism_layer.py
test_v3_doc70_human_ai_feel_reduction.py
test_v3_doc71_human_attractive_realism_balance.py
test_v3_doc72_east_asian_fair_complexion_and_proportion_guard.py
test_v3_doc78_long_term_identity_beautiful_realism.py
test_v3_doc85_image_to_image_reference_truth.py
test_v3_doc86_portrait_bone_identity_lock.py
test_v3_doc87_portrait_reference_identity_style_separation.py
test_v3_doc88_portrait_reference_balance.py
test_v3_doc90_general_advanced_reference_controls.py
```

Real validation:

```text
1. Adult portrait image-to-image reference test.
2. Text-only portrait suite test.
3. E-Commerce apparel/kidswear model test.
4. Product-only image without people.
5. Stylized/anime/CG human request that should not force photorealism.
```

Acceptance target:

```text
People should remain attractive, recognizable when referenced, and visibly real.
Commercial product images with human models should not have doll-like or AI
stock-model faces.
The plugin should improve human realism without changing suite purpose,
template deliverable maps, product truth, or prompt mood.
```

## H10. Historical audit commands

Use these commands before implementation:

```text
rg -n "human_photorealism|anti_ai_face|AI-face|doll-like|plastic skin|beauty-filter|subject_type == \"character\"" alchemy_creative_agent_3_0/app alchemy_creative_agent_3_0/tests
rg -n "Human Realism Plugin|Doc91|human_realism_plugin" AGENTS.md alchemy_creative_agent_3_0/README.md alchemy_creative_agent_3_0/docs
git diff --check -- AGENTS.md alchemy_creative_agent_3_0/README.md alchemy_creative_agent_3_0/docs
```

After implementation, add focused tests for Doc91 before running real image
validation.

## H11. Historical audit snapshot

Current structure is mostly compatible:

```text
Human realism code already lives under shared_capabilities/visual_cluster.
Existing docs already prohibit hard-coding this capability in Central Brain.
Existing identity modules already own reference identity and bone structure.
Existing retry/output modules already own bounded retry and final presentation.
```

Current gaps to fix in code later:

```text
Activation can still depend too much on subject_type == "character".
E-Commerce product-on-model images can skip human realism when subject_type is
product.
Child/teen model realism is not yet a first-class strictness branch.
Metadata does not yet expose a single human_realism_plugin activation record.
Some tests validate portrait paths but not product-with-human paths.
```

Therefore the next coding phase should be a small modular refactor inside the
Visual Capability Cluster, not a central-framework rewrite.

Scattered-content audit:

```text
product_api/service.py currently contains some human-face retry prompt fragments
for issue-code repair. This is not the desired long-term ownership.

Allowed:
  API/service layers may pass issue codes, metadata, and retry payloads through.
  API/service layers may preserve backward compatibility for existing metadata.

Not allowed:
  API/service layers must not own new anti-AI-face wording, child-model realism
  wording, or human-realism retry prompt fragments.

Required future cleanup:
  Move or delegate human-face retry wording to the Human Realism Plugin.
  Keep product_api/service.py as a transport/orchestration boundary only.
  Keep vision_provider.py issue-code vocabulary aligned with the plugin without
  turning it into the rule owner.
```
