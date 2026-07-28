# Professional Mode Body-Proportion Runtime Projection Design

Status: **documented design approved; runtime implementation feature branch
under reviewer audit.** The current feature work implements typed
body-proportion projection and deterministic regression coverage for
Professional `general_template`, `ecommerce_template`, and
`photographer_template`, but it has not yet passed planning-only materialization
audit or controlled per-module visual acceptance. No Host/MCP/ImageGen call,
business receipt, slot, activation, Character Card generation, Body
preparation, slot review, activation, or asset-storage change is authorized by
this document.

Implementation closure note (2026-07-28): the runtime feature branch now
projects existing active Body Silhouette evidence through a body-only reference
role/truth layer, validates per-output closed body receipts, and tests final
materialized provider references for body role/view/count parity. This is not a
production completion claim: planning-only evidence, controlled visual review,
and reviewer merge approval remain pending.

Scope: Professional runtime reference inheritance for existing active
Character Card Body Silhouette evidence. This design covers the current native
Professional templates that exist in code: `general_template`,
`ecommerce_template`, and `photographer_template`.

Non-scope:

- Character Card generation;
- Body Silhouette preparation, slot definitions, review, activation, or asset
  storage;
- new General, Photography, E-Commerce, children, kidswear, beach, poolside, or
  shared Human Realism prompt recipes;
- Product Truth selection semantics;
- Provider cap expansion;
- formal project delivery receipt, slot, activation, UI, or storage mutation.

Current upstream authorities remain current:

- Doc93 reference-channel ownership;
- Doc95 same-person portrait identity evidence;
- Doc96 high-fidelity identity execution;
- Doc178 Character Card modules and Body Silhouette production lifecycle.

This document only defines how already-active Body Silhouette evidence is
projected into Professional runtime materialization when a Professional output
is a visible-body or full-body human output.

## 1. Code-first observed facts

Current native Professional public template IDs are:

```text
general_template
ecommerce_template
photographer_template
```

Current specialized native mapping is:

```text
ecommerce_template     -> ecommerce
photographer_template  -> photography
```

The project template registry may list future placeholders such as New Media,
Private Domain, or Brand IP, but they are not current native Professional image
planning modules and are intentionally outside this design.

The current Visual Asset Library Professional resolver reads active
`card.face_slots` and projects:

```text
portrait_identity
selected_identity_reference
```

It does not read active `card.body_slots`.

`CharacterCardState` already defines Body Silhouette slots:

```text
body.front_full
body.side_full
body.rear_full
```

Those slots have their own active/winner/review/parity/formal-receipt
constraints in the Character Card module. This design reuses that existing
truth read-only; it does not change how the body slots are produced.

The current native reference channel and Provider materialization contracts do
not have a body-only reference role. Passing Body Silhouette as a face
reference is forbidden because it would reuse portrait identity semantics and
can incorrectly lock pose, camera, framing, or full-frame body presentation.

## 2. Module applicability matrix

| Native Professional template | Code scenario/mode | Output role or scene | `professional_body_proportion_requirement` | Body reference behavior |
| --- | --- | --- | --- | --- |
| `general_template` | `general_creative` | Professional visible/full human body output, including torso/neck/shoulder transition or obvious body scale | `visible_body_required` or `full_body_required` | Require active body-only reference. |
| `general_template` | `general_creative` | face-only identity crop, pure local detail, product, object, still-life, landscape, abstract, no-person, nonhuman | `not_required` or field absent when not Professional | Do not read Professional body. |
| `ecommerce_template` | `ecommerce` product-on-person | visible-body or full-body commerce image, including standing, seated with body visible, walking, back/garment structure, lifestyle product-on-person | `visible_body_required` or `full_body_required` | Require active body-only reference plus selected product truth. |
| `ecommerce_template` | `ecommerce` | product detail, print/detail close-up, fabric/texture, face-only expression, flat-lay/no-person product image | `not_required` | Do not attach body. |
| `photographer_template` | `photography`, `single_hero` | portrait/environmental human with visible or full body | `visible_body_required` or `full_body_required` | Require active body-only reference. |
| `photographer_template` | `photography`, `reference_reshoot` | human visible/full-body reshoot | `visible_body_required` or `full_body_required` | Require active body-only reference. |
| `photographer_template` | `photography`, `professional_set.session_hero` | visible/full human body role | `visible_body_required` or `full_body_required` | Require active body-only reference. |
| `photographer_template` | `photography`, `professional_set.environmental_context` | environmental human with visible body | `visible_body_required` | Require active body-only reference. |
| `photographer_template` | `photography`, `professional_set.detail_or_moment` | face, hand, object, or local detail that does not show torso/neck/shoulder transition or obvious body scale | `not_required` | Keep old path; no body. |
| `photographer_template` | `photography` | still-life, landscape, animal, no-person | `not_required` | Do not read Character Card body. |

The requirement must not be guessed from keywords in `user_input`, canonical
prompt text, filenames, or upload order. Module-owned applicability is decided
by the specialized/Professional deliverable owner; once an output is in an
applicable visible/full human body class, a valid closed per-output receipt
from the existing Remote Brain output-evidence flow is mandatory.

Applicability and receipt are separate gates:

| Gate | Owner | Failure behavior |
| --- | --- | --- |
| Module-owned applicability | E-Commerce/Photography/Professional General deliverable owner decides whether this output is a person visible/full-body output. | If applicable but no valid Brain receipt is returned, block before Host. |
| Brain per-output receipt | Remote Brain returns `not_required`, `visible_body_required`, or `full_body_required` for each Professional output in scope. | Missing, null, unknown, duplicate, or contradictory receipt fails closed. |
| Native materialization | Planner/provider projection proves required body reference is present in final materialized refs. | Missing body, wrong role, wrong view, or cap overflow fails closed. |

## 3. Per-output closed requirement and body-view receipt

The minimal contract adds two closed fields to the existing per-output
`BrainOutputEvidenceContract` shape for applicable Professional outputs:

```text
professional_body_proportion_requirement:
  not_required | visible_body_required | full_body_required

professional_body_view_kind:
  front_full | side_full | rear_full | null
```

Rules:

1. It is meaningful only in Professional mode.
2. Standard and non-Professional requests must not receive or act on it.
3. The shared response model may omit these fields only for historical
   responses and non-applicable outputs. Runtime must treat absence as invalid, not
   ready, once the module-owned applicability gate has classified the output
   as Professional visible/full human body.
4. Missing, null, or present-but-invalid values fail closed for applicable
   Professional visible/full human body outputs.
5. For a Professional output that returns `visible_body_required` or
   `full_body_required`, Host materialization is forbidden unless the active
   Body Silhouette is admitted as a body-only reference in the final Provider
   input plan and actual materialized reference assets.
6. `not_required` is allowed only for face-only identity crops, pure local
   details, nonhuman/object, landscape, still-life, no-person, or other outputs
   whose module-owned applicability gate says body-proportion evidence is not
   in scope. Upper-body framing is not automatically exempt: if torso,
   neck/shoulder transition, arm/torso relation, or obvious body scale is
   visible, it is `visible_body_required`, not `not_required`.
7. `professional_body_view_kind` is required for every
   `visible_body_required` or `full_body_required` output and must be one of
   `front_full`, `side_full`, or `rear_full`. It must match the module-owned
   body view intent. Missing, null, unknown, or intent-mismatched values fail
   closed before Host.
8. When `professional_body_proportion_requirement` is `not_required`,
   `professional_body_view_kind` must be absent or null. A `not_required`
   receipt that carries `front_full`, `side_full`, or `rear_full` is
   contradictory and fails closed; the planner/provider must not attach body
   evidence merely because a view value is present.
9. These fields are evidence/receipts, not renderer prompt prose and not a local
   creative decision.

Module owners constrain the meaning before Remote Brain:

- E-Commerce owns product-on-person visible/full-body commerce roles.
- Photography owns portrait/environmental/shot-role classification.
- General Professional remains scenario-neutral; Remote Brain decides
  per-output body requirement only for the current Professional human
  composition.

The native planner consumes this receipt. It must not infer body requirements
from prompt strings or role-name substrings.

## 3A. Closed body view selection

The resolver/planner must choose from the existing server-owned Character Card
Body Silhouette slots only:

```text
front_full
side_full
rear_full
```

These are normalized from server-owned slot keys:

```text
body.front_full -> front_full
body.side_full  -> side_full
body.rear_full  -> rear_full
```

The body view is chosen by trusted server/runtime structure, never by MCP raw
path, output ID, filename, user text, canonical prompt text, or keyword
matching:

| Module-owned output body view intent | Required `body_view_kind` | Server-owned slot | Failure behavior |
| --- | --- | --- | --- |
| ordinary front, front-facing, three-quarter-front, commercial presentation, or unspecified visible-body presentation | `front_full` | `body.front_full` | Missing/inactive/invalid slot blocks before Host. |
| explicit side/profile body presentation | `side_full` | `body.side_full` | Missing/inactive/invalid slot blocks before Host; do not substitute `front_full`. |
| explicit rear/back garment-structure body presentation | `rear_full` | `body.rear_full` | Missing/inactive/invalid slot blocks before Host; do not substitute face, front, or side. |

When the module-owned role does not express a side or rear body intent, the
default is `front_full`; the planner must not infer side/rear from natural
language tokens. When an exact required body view is unavailable, the output
fails closed or remains body-proportion uncertified before Host. It must not
substitute a face view, generated winner, raw path, or another body view.

The selected body view must be recorded in the Remote Brain per-output
evidence contract as `professional_body_view_kind`, then copied into the
per-output reference contract as closed `body_view_kind`. The final Provider
input plan and actual materialized reference assets must expose the same
closed value without private asset/output identifiers. If the Brain receipt,
native reference contract, Provider input plan, or materialized assets disagree
on the body view, Host is blocked before materialization.

## 4. Body-only reference channel and policy

The body reference must be distinct from face and product references.

Required channel/role concept:

```text
body_proportion_reference
```

Provider truth-layer concept:

```text
body_proportion_truth
```

Allowed inheritance:

- body scale;
- neck/shoulder transition;
- torso/limb proportion;
- developmental-age-stage coherence.

Forbidden inheritance:

- wardrobe;
- pose;
- studio or white-sweep background;
- lighting;
- camera, lens, focal length, or framing;
- expression;
- scene;
- product appearance;
- styling or makeup.

If the current Provider projection cannot express this as a separate
body-only truth layer, the minimal owning change is in the shared Provider
reference projection/materializer. It must not be implemented as final prompt
patching, E-Commerce-specific safety prose, or a fake `face_reference`.

## 5. Five-reference cap and final materialized input structure

`max_provider_reference_images=5` remains unchanged. Compliance is measured
after canonical materialization, by final Provider derivative/reference count,
not by raw source count.

The current Provider path may expand one identity source into multiple face
derivatives. Body projection therefore needs a deterministic
source-to-derivative admission contract rather than a source-count target.
For body-required outputs, the hard sources and final materialized derivatives
are closed:

```text
portrait/root source        -> at most one admitted identity derivative when body is required
selected face winner source -> at most one admitted identity derivative when body is required
body source                 -> exactly one body_proportion_truth derivative
selected product/source     -> at most one module hard-truth derivative
```

The body source must never generate portrait-identity derivatives. If the
Provider cannot produce this compact body-aware derivative plan, the output
blocks before Host instead of increasing the cap or dropping a hard reference.

Deterministic compact derivative policy:

| Source | Body-required derivative policy | May be dropped? |
| --- | --- | --- |
| immutable root portrait | exactly one identity-preserving derivative selected by the existing identity evidence owner | No |
| selected face winner | exactly one identity/view derivative selected by the existing identity evidence owner | No |
| active Body Silhouette | exactly one `body_proportion_truth` derivative with the selected closed `body_view_kind` | No |
| E-Commerce selected product truth | exactly one `product_truth` derivative | No |
| Photography hard reference | exactly one Photography-owned derivative only when that shot contract requires it | No, if required |
| General hard reference | exactly one General-owned derivative only when that output contract requires it | No, if required |

There is no open-ended residual slot in this contract. If a module hard
reference plus root, face, and body require more than five final materialized
references, Host is blocked before materialization. The system must not fit by
silently deleting body, face, product, Photography hard truth, or General hard
truth.

### 5.1 E-Commerce visible/full body

Provider-facing final references must fit within five materialized assets:

```text
1. root portrait identity derivative
2. selected face winner derivative
3. body_proportion_truth derivative with body_view_kind
4. selected product_truth derivative
```

The final input plan must not silently drop root identity, selected face,
body, or selected product truth. If the materializer cannot fit those hard
references within the cap, the output blocks before Host.

Example final count:

```text
root identity 1 + selected face 1 + body 1 + product 1 = 4 <= 5
```

If a future E-Commerce output also requires a second product truth derivative,
the final count becomes five and remains valid only when all five materialized
assets are present with correct roles. A sixth derivative is a hard block.

### 5.2 Photography visible/full human body

Provider-facing final references must fit within five materialized assets:

```text
1. root portrait identity derivative
2. selected face winner derivative
3. body_proportion_truth derivative with body_view_kind
4. Photography-owned hard reference, only when required by the shot contract
```

Photography must not load E-Commerce product truth. Still-life, landscape,
animal, and no-person photography outputs do not read Character Card body.
If a Photography visible-body output requires more than two Photography-owned
hard derivatives in addition to root, face, and body, it exceeds the cap and
blocks before Host.

### 5.3 General Professional visible human body

General remains scenario-neutral. A body reference may be used only when the
Professional per-output receipt requires visible/full human body evidence:

```text
1. root portrait identity derivative
2. selected face winner derivative
3. body_proportion_truth derivative with body_view_kind
4. General-owned hard reference, if any
```

General product/object/still-life/landscape/abstract/no-person outputs must
not read Professional body evidence.
If General visible-human output would require more than two General-owned hard
derivatives in addition to root, face, and body, it exceeds the cap and blocks
before Host.

## 6. Fail-closed and uncertified states

For `visible_body_required` or `full_body_required` outputs, Host is blocked
before materialization when:

- active Body Silhouette is missing;
- body reference cannot be resolved from server-owned Character Card evidence;
- body reference is mapped to `face_reference`, `portrait_identity`, product
  truth, or any non-body role;
- body reference is missing a closed `body_view_kind`;
- the closed `body_view_kind` does not match the selected server-owned body
  slot;
- final Provider input plan lacks body-only truth;
- actual materialized reference assets lack body-only truth;
- final materialized reference count exceeds five;
- the materializer fits the cap only by silently dropping root, selected face,
  body, selected product truth, or a module hard reference;
- raw paths, provider payloads, private IDs, or unselected cross-module
  references leak into public evidence.

For `not_required` outputs, the existing face-only/detail/no-person path
remains compatible. The system must not attach body reference merely because
an output belongs to Professional mode.

## 7. Planning/materialization versus visual acceptance

This design narrows "correctly applied" to an auditable runtime fact:

```text
The active Body Silhouette body-only reference appears in the final
provider_input_plan and actual materialized reference assets for each required
visible/full-body Professional output, with final materialized refs <= 5.
```

It does not claim pixel-perfect body realism. Head/body scale, neck/shoulder
continuity, torso/limb proportion, doll-like face, pasted-face feel, and
age-stage coherence remain controlled visual-review outcomes.

Therefore final acceptance requires both:

1. planning-only materialization audit for channel/role/ref-count/no-leakage;
2. controlled visual review of actual pixels.

## 8. Compatibility and migration

Historical Face Identity documents remain readable. The old statement
"Professional identity is root portrait plus selected face winner" is narrowed:

- still valid for face-only and pure local-detail outputs;
- insufficient for visible-body or full-body Professional outputs that need
  body-proportion certification.

No historical asset is rewritten. Historical evidence that passed identity
does not retroactively become body-proportion certified.

For shared Brain-model compatibility, historical and non-applicable responses
may have no `professional_body_proportion_requirement` or
`professional_body_view_kind` fields. That absence is not allowed to pass an
applicable Professional visible/full-body output. When the module-owned
applicability gate has classified an output as Professional visible/full human
body, missing, null, invalid, or intent-mismatched values fail closed before
Host. General/Standard non-Professional responses require no migration and
must not act on the fields.

For `not_required` outputs, `professional_body_view_kind` remains absent or
null. Historical or future payloads that combine `not_required` with
`front_full`, `side_full`, or `rear_full` are contradictory receipts and must
not be migrated into body admission.

## 9. Old-document superseded/narrowed index

This document-only gate adds explicit markers to these conflict surfaces:

| Document | Marking applied in this gate | Reason |
| --- | --- | --- |
| `docs/visual_assets/PROFESSIONAL_MODE_DOCUMENT_SET_INDEX.md` | Current document added to inventory; runtime projection does not change Doc178 Body production. | Establish current design location. |
| `docs/visual_assets/PROFESSIONAL_MODE_ASSET_CHANNEL_AUTHORITY_AND_REFERENCE_ADMISSION_SPEC.md` | First Face Identity ownership language narrowed for visible/full-body runtime outputs. | Face channels remain face-only; body proportion requires body-only channel. |
| `docs/visual_assets/PROFESSIONAL_MODE_VISUAL_ASSET_LIBRARY_AND_PEOPLE_ASSET_MODULE_SPEC.md` | Face Identity reference contract narrowed. | First-release face contract remains, but visible/full-body certification must also consume active Body Silhouette. |
| `docs/visual_assets/PROFESSIONAL_MODE_IMPLEMENTATION_HANDOFF_AND_ACCEPTANCE.md` | "root plus winner" acceptance language narrowed. | Those references certify face/anchor chain, not body proportion. |
| `docs/ecommerce_module/E25_PROFESSIONAL_ECOMMERCE_POSE_ACCEPTANCE_CONTRACT.md` | Pose-v2 scope narrowed. | Pose contract solves seated/standing presentation, not body-proportion inheritance. |
| `docs/259_V3_NATIVE_ECOMMERCE_BRAIN_TRANSPORT_TIMEOUT_CORRECTION_MODEL.md` | E-Commerce `root + winner + product_truth` capacity wording marked pre-body-projection historical/narrowed. | Product-on-person visible/full body must add body-only reference or block. |
| `docs/photography_module/P09_P6_PROFESSIONAL_SET_AND_CONTINUATION_AUDIT.md` and `P11_LLM_FIRST_CREATIVE_DIRECTION_AND_REAL_PIXEL_QUALITY_GATE.md` | Photography full/visible human body note added. | Photography role planning remains Photography-owned, but body evidence is required only for human visible/full-body roles. |

Do not modify Doc178's Body Silhouette generation, slot, review, activation, or
storage definitions. This design only consumes active Body Silhouette
downstream at Professional runtime materialization.

## 10. Isolation and acceptance test matrix

Documented implementation must add deterministic tests before any real
planning or Host call:

| Area | Required deterministic evidence |
| --- | --- |
| Resolver | Active body slots are read; missing/inactive/bad hash/bad receipt blocks or marks uncertified. |
| No modeling mutation | Character Card generation, slots, review, activation, and storage are untouched. |
| Brain receipt | `professional_body_proportion_requirement` accepts only `not_required`, `visible_body_required`, `full_body_required`; `professional_body_view_kind` accepts only `front_full`, `side_full`, `rear_full`, or null; required outputs must carry a matching non-null view; `not_required` outputs must carry absent/null view; invalid/missing/null/intent-mismatched or contradictory receipts fail closed for module-applicable visible/full-body outputs. |
| E-Commerce | visible/full product-on-person requires body; detail/print/face-only does not; product truth selection/cap/no-leakage unchanged. |
| Photography | portrait/environmental visible/full human body requires body; still-life/landscape/animal/no-person does not; no product-truth leakage. |
| General | only Professional visible/full human body consumes body; product/object/scene/nonhuman does not. |
| Provider projection | body maps to body-only role/truth, never face/product; forbidden inheritance policy and closed `body_view_kind` are present. |
| Final materialization | each template/mode asserts final Provider input plan and materialized reference assets contain body-only role, closed `body_view_kind`, derivative count <= 5, and no forbidden channels when required. |
| Capacity | over-cap blocks before Host; no silent deletion of body, face, product, or module hard truth. |
| Privacy/no leakage | no raw paths, provider payloads, asset/output IDs, or prompt fragments in public evidence. |
| Visual acceptance | planning-only body gate does not claim pixel perfection; controlled visual review remains required. |

## 11. Next gate

After reviewer accepts this document-only gate, the next allowed phase is an
independent feature worktree implementing the minimal Professional runtime
projection:

```text
binding resolver -> native planner -> Provider body-only projection -> focused tests
```

No Host/MCP/ImageGen or business delivery mutation is authorized until
document review, code review, planning-only materialization audit, and visual
review gates pass in order.
