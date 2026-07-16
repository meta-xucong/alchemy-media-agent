# Professional Mode Visual Asset Library And People Asset Module

## Independent Development Specification

> This is an unnumbered Professional Mode specification. It is intentionally
> outside the existing Doc numbering families. It defines a new visual-asset
> product boundary and must not be used to rewrite Standard Mode, General
> Template, E-Commerce, Photography, Central Brain, or the Web Provider path.

## 0. Status And Authority

Status:

```text
PROPOSED_ARCHITECTURE
DOCUMENT_ONLY
NO_STANDARD_MODE_CHANGE
NO_PRODUCTION_ASSET_GATE
```

This document is the preparation authority for:

```text
Professional Mode
  -> Visual Asset Library
      -> People Assets        [first module]
      -> Product Assets        [future sibling]
      -> Brand Assets          [future sibling]
      -> Other approved asset types [future siblings]
```

It does not activate Professional Mode, certify an identity provider, or make
any existing mode use a visual asset pack automatically.

### 0.1 Compatibility And Precedence

This document is a scoped overlay, not a replacement authority for the
numbered V3 documents. The precedence rule is:

```text
Standard Mode
  -> existing numbered V3 contracts remain unchanged

Professional Mode, only after an explicit mode choice and selected People Asset
  -> this document owns asset selection, pack lifecycle, and identity-source
     eligibility
  -> Doc93/95/96/97/100/101/121/128/134/135/136/137/138/139/140 continue to
     own reference channels, evidence, semantic task profiling, capability
     activation, provider-prompt finalization/signing, review, retry, and
     human-realism safety
```

The overlay may narrow or strengthen an existing shared contract for the
selected People Asset, but it may not weaken, bypass, or globally rewrite it.
No old document is edited, renumbered, or made obsolete by this specification.

### 0.2 Current Shared Forward Path

The Professional Mode overlay must attach to the current standard V3 forward
path. It must not preserve an older “local module writes a creative direction”
interpretation:

```text
explicit mode + selected People Asset evidence
  -> Remote Central Brain complete visual_task_profile and capability intent
  -> frozen CapabilityActivationPlan
  -> Remote Brain complete canonical_provider_prompts[] and prompt hashes
  -> Human Realism semantic preflight and independent re-signing when active
  -> exact GPT Image 2 provider materialization
  -> shared real-pixel review, bounded retry, and final-result selection
```

The Face Identity Module may supply typed identity evidence, view coverage,
and user-selected asset provenance to this path. It may not author provider
prompt prose, append local prompt fragments, classify semantics locally,
patch a retry prompt, or bypass a missing Brain decision. A missing or stale
semantic profile, frozen activation intent, canonical prompt, prompt hash, or
required Human Realism sign-off is a fail-closed condition before Provider or
MCP execution.

## 1. Product Decision

Alchemy V3 will have two independent creation modes:

```text
Standard Mode
  -> current General / E-Commerce / Photography behavior
  -> current uploaded-reference and prompt ownership behavior
  -> current provider, review, retry, and delivery contracts

Professional Mode
  -> explicit use of a selected asset from the Visual Asset Library
  -> professional asset truth is authoritative for its assigned channels
  -> a selected People Asset is the only human-identity source
  -> current shared V3 planning, GPT Image 2, review, retry, and delivery
```

Professional Mode is an opt-in execution contract, not a replacement for
Standard Mode. A request must carry an explicit mode choice before any
Professional Mode asset is consulted.

The two modes may share implementation components, but they must not share
implicit state or silently change one another's semantics.

## 2. Standard Mode Is Frozen By This Document

When a request is in Standard Mode:

```text
no Visual Asset Library lookup is performed
no People Asset is required
no professional asset metadata is injected into the Brain request
no Professional Mode prompt or reference rule is appended
no professional-mode failure can block or reroute the request
```

The following remain unchanged in Standard Mode:

```text
General Template semantics
E-Commerce LLM-first and deliverable semantics
Photography LLM-first and role semantics
uploaded reference interpretation
Doc93 reference-channel ownership
shared provider routing
shared review/retry/final-delivery behavior
requested output count and public request schema
```

The Standard Mode branch must remain runnable if the entire Professional Mode
package is absent, disabled, unavailable, or removed.

Existing Standard Mode concepts such as `ProjectIdentityAnchor`,
`SubjectIdentityCard`, `auto_batch_identity_anchor`, and the Doc97 subject
continuity package remain valid for Standard Mode. They are job/project-scoped
foundation continuity records, not People Assets. Standard Mode never creates,
reads, activates, or upgrades a People Asset as a side effect.

## 3. Visual Asset Library Mother Boundary

The library is a project-scoped asset catalog, not a new image generation
template. A project may contain multiple independent People Assets; selecting
one is an explicit per-job choice. Its initial conceptual layout is:

```text
visual_asset_library
  people_assets
    people_asset_record
    identity_anchor_pack
      face_identity_module        [first release]
    identity_anchor_pack_version
    anchor_view
  product_assets             [future; not implemented here]
  brand_assets               [future; not implemented here]
  other_asset_types          [future; not implemented here]
```

The future runtime root may live under a dedicated visual-assets package, for
example:

```text
app/visual_assets/
  people_assets/
  product_assets/
  brand_assets/
```

No such future sibling is authorized by this document. The first implementation
must remain limited to People Assets and must not add product, brand,
marketplace, A+, or campaign-specific asset roles.

The catalog is not a second reference registry. It stores lifecycle, consent,
pack-version, and user-selection metadata plus references to existing
Project/Reference/Output/History records. Existing Doc93 policy, Doc97
retrieval, and shared provider/review storage remain the only source of truth
for reference admission and execution.

## 4. People Assets Scope

A People Asset represents a user-approved, reusable subject asset assembled
from independently versioned identity modules. It is not merely a file and it
is not a generated image candidate. The first release contains only the face
identity module; the container is deliberately extensible for future modules.

The first-release module boundary is:

```text
People Asset
  -> Face Identity Module        [implemented first]
  -> Body / silhouette Module    [future; not implemented here]
  -> Hair / styling Module       [future; not implemented here]
  -> Other identity dimensions  [future; not implemented here]
```

The Face Identity Module owns only:

```text
face geometry and feature relationships
same-face identity evidence
face-view coverage (front / three-quarter / profile)
face-specific age direction evidence
pack readiness, user activation, version lifecycle, and provenance
```

It does not own body shape, body proportions, pose, hair, makeup, wardrobe,
accessories, lighting, scene, camera, composition, or whole-image style. Those
channels remain prompt-owned or governed by another explicitly selected
reference/module under the existing V3 contracts.

Pixel-quality review, Human Realism semantic sign-off, retry planning, Provider
prompt creation, and final-result selection remain owned by the shared V3
runtime. “Face review” in this document means pack/view readiness and identity
evidence closure; it does not authorize a private face reviewer or private
identity repair path.

The People Asset container contains:

```text
the immutable root reference provenance
one or more verified identity anchor-pack versions
verified view/framing coverage
identity and review status
active/superseded state
source and consent provenance
```

The first People Asset implementation creates the Face Identity Module inside
an Identity Anchor Pack through an explicit preparation action:

```text
uploaded person reference, for image-to-image
or protected user prompt, for text-to-image character creation
  -> three neutral standard-front candidates
  -> likeness-first identity review
  -> best passing front anchor
  -> supplementary three-quarter/profile candidates as evidence permits
  -> per-view review
  -> whole-pack cross-view identity review
  -> activate the face module version only after the complete face pack passes
```

### Likeness-first candidate scoring

The first principle of Face Identity selection is **像不像 / same-person
likeness**. A candidate that is recognizably the same person must outrank a
more polished, more symmetrical, or more perfectly frontal candidate that has
lost the person's distinctive appearance. The review must never reward a
generic beauty archetype merely because it is attractive, clean, or technically
flawless.

The reviewer records the following safe, non-biometric summary fields:

```text
same_face_score              primary likeness score; identity-critical
                              feature relationships and distinctive traits
                              are mandatory evidence, not generic face category
distinctive_feature_score    supporting score for local asymmetry, eye/brow
                              character, nose-mouth relationship, cheek/jaw
                              contour, and other source-specific traits
human_realism_score          natural human presence and non-plastic rendering;
                              it is a supporting signal, not a beauty score
ai_overperfection_penalty    explicit penalty for a too-perfect, averaged,
                              synthetic-looking face that erases individuality
visual_quality_score         technical/readability quality only
pose_compliance_score        view-contract compliance; deliberately lowest
                              priority so a modest head tilt does not erase
                              a stronger likeness
```

Front candidates are ordered lexicographically by:

```text
(same_face_score,
 distinctive_feature_score,
 human_realism_score,
 1 - ai_overperfection_penalty,
 visual_quality_score,
 pose_compliance_score)
```

Missing legacy supporting fields fall back to the historical same-face score
for readability, but new reviewers must emit the full summary. A small tilt,
slight expression difference, or non-perfect symmetry is not an automatic
failure. Extreme occlusion, a materially wrong person, face distortion, or a
pose that defeats the requested evidence view may still fail the candidate.

The human-realism review has two duties: preserve the real person's natural
imperfections and prevent an AI-averaged face from receiving an inflated
likeness score. It must not override a clearly stronger likeness merely because
another candidate is more conventionally beautiful. Scoring is still only
preparation evidence; the complete pack requires per-view review, cross-view
identity review, root-truth continuity, and explicit user activation.

The exact candidate counts for supplementary views remain a later module
design decision, but every supplementary view must use the same bounded
candidate, review, and best-result contract. There is no unbounded generation
loop.

The standard-front and supplementary images are full GPT Image 2 outputs. They
are face-evidence views, not a body or fashion asset. The
module must not create a face card through local face swapping, coordinate
warping, canvas overlays, deterministic facial reconstruction, or a private
pixel-repair path.

The view names are evidence contracts, not static image recipes. The Remote
Brain must first return a complete semantic task profile and capability
activation intent, then create the complete canonical Provider prompt for every
candidate. The pack module may declare the requested view, identity evidence,
safety, and review target as typed inputs, but it must not hard-code a camera,
lens, makeup, lighting, background, pose, or cosmetic prompt recipe. It must
not emit local prompt additions, negative lists, retry prose, or a fallback
creative direction when Brain output is incomplete.

The default pack has one required `standard_front`, one required
`three_quarter`, and one required `profile` view after the winning front is
known. A second three-quarter/profile view may be generated when the source,
identity evidence, or downstream use justifies it. Candidate counts remain
bounded and configuration-driven. The user explicitly activates the complete
passing pack; scoring alone never makes an unconfirmed pack active.

## 5. Root Truth And Anchor Authority

People Assets have a strict authority hierarchy:

```text
uploaded root portrait truth
  > verified generated anchor support
  > selected/generated continuation support
```

For a text-only character project with no uploaded portrait, the first approved
anchor version becomes the project's initial fictional-character root, but it
must be recorded as generated origin rather than misrepresented as uploaded
human truth.

An Identity Anchor Pack may improve view coverage and reduce reference-style
leakage. It may not silently replace an uploaded root portrait. Every later
Professional Mode generation must preserve the root truth relationship in its
provenance and final review.

An explicit current prompt may request an age direction change while retaining
the same People Asset. Age transformation is therefore a prompt-owned change
that remains subject to Doc128 human-realism constraints, safety policy, and
same-person review; it is not a reason to replace the asset or create a second
identity source. A request for a different person identity must stop and ask
the user to choose another People Asset or resubmit in Standard Mode.

## 6. Professional Mode Reference Contract

Professional Mode requires the caller to select an active People Asset or to
stop with a public-safe blocked state. It must never fall back to Standard Mode
because a People Asset is missing, stale, invalid, or below its review gate.

When Professional Mode is active:

```text
face identity, face geometry, and same-face continuity
  come only from the selected People Asset's active Face Identity Module

body shape, body proportion, hair, makeup, wardrobe, and other non-face
identity channels
  are not locked by the first-release module and remain prompt-owned or
  explicitly governed by another approved module/reference

age direction
  may be changed only by an explicit current prompt and remains subject to
  shared Human Realism, safety, and same-person review

current prompt
  owns requested hair, makeup, clothing, pose, light, scene, camera, mood,
  composition, and style unless the user explicitly assigns those channels
  to another approved asset

other uploaded images
  may contribute only the explicitly assigned non-identity channels
```

The explicit Professional Mode choice and selected `people_asset_id`/
`pack_version_id` are sanitized user controls and evidence bindings. They must
reach the Remote Brain semantic task profile before the capability plan is
frozen; they must not be hidden in local metadata that the Brain never sees.
The binding carries identity-source eligibility and provenance, not private
asset-library internals, raw prompt bodies, or provider instructions.

The selected pack is a bounded reference source, not an instruction to replay
every stored view. The shared adaptive reference selector must honor the
current maximum admitted identity sources (currently three per job unless the
shared contract is versioned otherwise). A project may store more views, but a
job must choose a view-aware subset and record the exact reference IDs and
hashes used by Provider and Reviewer.

An uploaded image that contains another person must not be sent as a complete
style or scene reference while claiming that its person is ignored. Full image
pixels can still carry face, body, clothing, and pose identity. The input
boundary must therefore do one of the following:

```text
use a verified non-person visual derivative;
use a safe channel-specific evidence representation;
or block that reference assignment when isolation cannot be proven.
```

Natural-language instructions alone are not sufficient to guarantee that an
unwanted person's pixels will be ignored.

## 7. User Experience Contract

The top-level UI exposes:

```text
Visual Assets
  -> People Assets
```

General, E-Commerce, Photography, and future Video surfaces expose only a
small mode choice:

```text
Standard Mode
Professional Mode: use Visual Assets
```

Standard Mode remains the default when no Professional Mode choice is made.
Professional Mode shows a People Asset selector. It must not expose internal
identity metrics, prompt sections, provider capability names, or biometric
terms in the beginner surface.

The selector is project-scoped and may contain multiple People Assets. The
selected asset and pack version are recorded per job; selecting one asset never
changes or deactivates the other assets in the project.

When the user explicitly selects Professional Mode but the selected People
Asset has no active valid pack, the UI may offer:

```text
Build this People Asset now
Choose another People Asset
Return to Standard Mode [explicit user action only]
```

After all required views pass shared review, the user confirms `Activate this
pack version`. A scored candidate or an unconfirmed pack remains preparation
history and cannot enter Professional Mode provider inputs.

Building a pack is a visible preparation stage. Its candidate images do not
count toward the requested formal delivery count. On failure, the system stops
and explains the next safe action; it must not silently continue in Standard
Mode.

The People Assets workspace additionally supports the professional workflow:

```text
create a People Asset
upload or declare its root source
build/rebuild an anchor-pack version
inspect coverage and review state
activate, supersede, or archive a version
set an asset as the current project character
```

## 8. Shared Capability Reuse

Professional Mode may call existing shared components, subject to their
current contracts:

| Existing capability | Professional Mode use |
| --- | --- |
| Doc93 reference-channel policy | Keep identity channels separate from prompt-owned style/scene channels. |
| Doc95 identity evidence | Build complementary feature-detail and head-geometry evidence; retain root truth. |
| Doc96 high-fidelity identity | Request high input fidelity where applicable; use ephemeral metrics, fused review, bounded shared rerender, and best-result selection. No new local face/pixel repair is introduced. |
| Doc97 subject continuity | Store generated anchors as reviewed support, retain uploaded root truth, route views adaptively, quarantine weak generated support. |
| Doc100 sole renderer | All anchor candidates and Professional Mode images use the existing GPT Image 2 provider; no sidecar or second pixel renderer. |
| Doc101 activation plan | Professional Mode must be active before the job plan freezes; no late capability injection or hidden fallback. The Face Identity binding is registered as a typed capability input, not a local creative prompt contribution. |
| Doc121 evidence continuity | Review receives the same admitted root/anchor evidence actually used by Provider materialization. |
| Doc128 Human Realism | Preserve shared age, safety, realism, and review constraints without taking ownership of asset selection. |
| Doc134 semantic ownership | Brain owns visible-subject judgment, evidence interpretation, and semantic creative intent; the module supplies evidence, not local semantic classification. |
| Doc135 heuristic retirement | No local prompt fragments, deterministic scene recipes, keyword activation, retry prose, or forward creative logic may be emitted by the Face Identity Module. |
| Doc136 lean review closure | Shared review consumes the final pixels and Brain-owned evidence; pack readiness does not certify a generated delivery. |
| Doc137/139 Human Realism Brain gates | When Human Realism is active, semantic preflight and independent natural-presence re-signing must pass before Provider/MCP execution. |
| Doc138 natural human presence | Human-presence quality remains a Brain-owned semantic deliverable, not a Face Identity prompt recipe. |
| Doc140 task-profile completeness | A new enforced real-image job requires a complete remote semantic task profile and capability activation intent; local fallback cannot fill semantic gaps. |
| Module boundary | The first release activates only Face Identity; future body/style modules require their own contracts and explicit activation. |
| Doc91/92 Human Realism | Improve human rendering without acquiring reference-channel ownership. |
| shared GPT Image 2 provider | Render anchor candidates and later Professional Mode images through the existing provider contract. |
| shared vision review/retry/history | Review every candidate, keep append-only attempts, and activate only the reviewed winner/pack. |

No People Asset implementation may create a second Brain, provider, review
system, retry system, image store, or reference registry. It may add a
project-scoped catalog/index and a Doc101-governed typed binding adapter, but
reference admission, semantic judgment, evidence preparation, Provider prompt
finalization, Provider execution, review, retry, and final delivery remain
shared.

## 9. Ownership And Isolation

### 9.1 Visual Asset Library owns

```text
project-scoped People Asset catalog records
root-source provenance pointers, not copied files
anchor-pack version lifecycle
view coverage and pack activation/supersession
user consent and per-job asset selection state
typed Professional Mode binding and asset/version provenance
```

The library may contain multiple People Assets in one project. It does not
decide which reference files are admitted to a Provider request, rewrite
channel policy, or become final delivery.

### 9.2 Existing creation modules own

```text
their current prompt and deliverable semantics
their current role/scene/package behavior
the explicit choice to run Standard or Professional Mode
the final user-facing creation result
```

### 9.3 Shared V3 foundation owns

```text
reference-channel ownership
identity/product/appearance evidence
semantic task profile and capability activation intent
canonical Provider prompt creation, signing, and hash verification
Human Realism semantic preflight and independent re-signing
provider transport
pixel review
bounded retry
final-result selection
```

The Professional Mode adapter may assemble these existing contracts, but it
must not redefine their meaning.

Each future People Asset module must declare its owned channels, evidence
inputs, review gate, provenance, activation state, and allowed interaction with
other modules. Adding a future module must not expand Face Identity's channel
ownership or change Standard Mode behavior.

## 10. Conceptual Data Contracts

The eventual contracts should be additive and versioned. Names below are
conceptual and are not yet public API commitments.

```python
class PeopleAsset:
    people_asset_id: str
    project_id: str                 # project-scoped; many assets are allowed
    subject_kind: str                 # human_person | fictional_character
    root_source_refs: list[dict]      # existing asset/output/reference IDs only
    modules: dict[str, dict]           # face_identity first; future modules additive
    active_pack_version_id: str | None
    status: str                       # draft | active | superseded | blocked
    provenance: dict

class FaceIdentityModule:
    module_id: str
    people_asset_id: str
    active_version_id: str | None
    owned_channels: list[str]          # face geometry, feature relations, face age direction
    status: str                         # draft | active | blocked | superseded
    provenance: dict

class IdentityAnchorPackVersion:
    pack_version_id: str
    people_asset_id: str
    status: str                       # preparing | review | active | failed | superseded
    anchor_views: list[dict]            # Face Identity views in first release
    root_truth_ids: list[str]
    review_summary: dict
    source_provenance: dict
    user_activation_confirmed: bool

class AnchorView:
    view_id: str
    view_role: str                    # standard_front | three_quarter | profile | ...
    output_id: str
    source_candidate_ids: list[str]
    identity_scores: dict              # safe summary; never raw biometric data
    view_coverage: dict
    active: bool
```

These records may refer to existing Project/Job/Output/History identifiers;
they must not duplicate image storage or final-delivery records.

Forbidden in these contracts:

```text
persisted face embeddings or raw biometric vectors
provider credentials
private prompt bodies in user-facing asset cards
unreviewed candidate as active identity truth
unbounded retry state
mode-specific marketplace, A+, or photography role fields
raw filesystem paths, provider-private prompts, or unredacted source payloads
```

The catalog contract is intentionally separate from the shared execution
contract. A future change to Standard Mode may improve a shared capability,
but it must not silently change People Asset semantics. Each shared contract
version used by an active pack/job must be recorded in internal provenance;
the Professional Mode adapter must either support the new version or block
with a structured incompatibility state. It must never reinterpret a stale
pack as a new module, silently migrate a selected asset, or copy Standard Mode
defaults into Professional Mode.

## 11. Runtime Integration Boundary

The intended execution seam is:

```text
Professional Mode selection
  -> resolve selected People Asset
  -> resolve its active Face Identity Module (first release)
  -> bind sanitized mode/asset/version evidence before semantic planning
  -> require complete Remote Brain visual_task_profile and capability intent
  -> activate the declared Professional Mode capability before plan freeze
  -> inject approved face root/anchor reference IDs into existing V3 capability input
  -> require complete Brain canonical_provider_prompts[] and hashes
  -> require Human Realism preflight/re-signing when active
  -> run exact-prompt Provider / shared review / bounded retry / final delivery
  -> preserve Professional Mode provenance and selected asset version
```

The uploaded root, when one exists, remains the immutable Doc95/Doc97 root
guard. The active pack is the reviewed operational support. Provider
materialization must use Doc93/95 evidence preparation rather than sending a
synthetic white-background card as an unrestricted full-frame reference.

The Standard Mode seam remains unchanged:

```text
Standard Mode selection or absence of mode selection
  -> existing V3 capability input
  -> no Professional Mode records or references
```

Mode identity must be carried as an internal execution boundary, not as
E-Commerce slot fields, Photography role fields, General Template recipe
fields, or new Brain prompt prose. A UI/session selection may carry the mode
into the existing sanitized project-job context, but it must not become a
variation mode, scenario role, marketplace field, or provider control.

The adapter may bind typed reference IDs, view roles, hashes, and channel
eligibility. It must not translate those values into local prompt prose. The
Provider receives only the exact complete canonical prompt signed by Remote
Brain. The Local MCP/Codex Native path, if used later, may relay that same
prompt and reference hashes for conversation-only rendering; it may not
re-plan, rewrite, or certify the Professional Mode delivery.

The Professional Mode bridge must fail closed for:

```text
missing selected People Asset
inactive or superseded pack version
pack review not complete
root provenance missing where required
reference-channel isolation failure
Remote Brain semantic task profile or capability activation intent incomplete
canonical Provider prompt missing, stale, or hash-mismatched
required Human Realism semantic preflight or independent re-signing failed
local creative fallback, legacy prompt fragment, or heuristic activation detected
provider/review failure during pack creation
```

There is no automatic Professional-to-Standard fallback. A user may
explicitly switch modes and resubmit.

If the user asks for a different person identity while Professional Mode is
active, the job is blocked until the user selects another project People Asset
or explicitly resubmits in Standard Mode. An explicit age direction change is
allowed only as a prompt-owned transformation subject to shared review.

Future modules are never inferred from a prompt or silently activated. A later
body, hair, or other module must be explicitly selected, capability-negotiated,
and reviewed under its own contract.

## 12. Future Video Compatibility

The first implementation does not build a video generator, temporal tracker,
character rig, or storyboard package.

It only makes the People Asset contract reusable by a future Video module:

```text
Video selects People Asset + active pack version
Video chooses an approved Face Identity view for a shot
Video retains root truth provenance
Video may later select additional body/style modules when those modules have
their own approved contracts
Video adds its own temporal consistency and motion review later
```

The first-release face pack is useful identity input for future video but is
not by itself evidence of body continuity, temporal consistency, or
frame-to-frame consistency.

## 13. Implementation Phases

### Phase A — Documentation And Mode Boundary

```text
freeze Standard/Professional mode separation
define Visual Asset Library and People Asset ownership
define no-fallback and no-raw-person-reference rules
add isolation contract tests before runtime work
```

### Phase B — People Asset Records And Pack Lifecycle

```text
add additive project-scoped People Asset records
add a module registry with Face Identity as the only active first-release module
add pack-version state and provenance
reuse existing output/history storage
add active/superseded/failed handling
```

### Phase C — Anchor Pack Preparation

```text
explicit root-source intake
three standard-front candidates
Remote Brain semantic task profile and capability activation intent
likeness-first identity scoring and winner selection
supplementary view generation using root + selected front anchor
per-view and whole-pack review
complete canonical Provider prompt and hash for every candidate
Human Realism semantic preflight/re-signing when active
activate only a complete passing Face Identity pack after user confirmation
```

### Phase D — Professional Mode Consumers

```text
add Professional Mode selection to General, E-Commerce, and Photography
consume only the selected People Asset in Professional Mode
bind the explicit mode and selected asset/version before Brain planning
use the existing portrait/reference capabilities through a Doc101 adapter
never emit local prompt prose or semantic fallback from the Face module
keep Standard Mode byte/contract compatible
prove no raw person reference leaks into Professional Mode provider inputs
```

### Phase E — Real Acceptance And Video Handoff Contract

```text
cross-scene image acceptance
cross-view pack acceptance
project continuation acceptance
document the stable asset interface for future Video
```

No phase authorizes a production claim before the existing real provider,
review, and template gates pass.

## 14. Required Isolation Tests

At minimum:

```text
Standard Mode with no People Asset behaves exactly as before.
Standard Mode cannot read Professional Mode asset metadata.
Standard Mode's existing ProjectIdentityAnchor/SubjectIdentityCard paths remain
available and never auto-promote into a People Asset.
Professional Mode requires an active selected People Asset.
Professional Mode never silently falls back to Standard Mode.
Professional Mode uses only the selected asset's active Face Identity Module
for face identity in the first release.
The first-release module does not lock body, hair, wardrobe, or whole-image style.
Future modules cannot activate from prompt keywords or legacy metadata.
Professional Mode may contain multiple project People Assets and binds one per job.
The selected asset is activated before the frozen capability plan.
Professional Mode supplies a complete Brain semantic task profile and
capability activation intent before the plan freezes.
Face Identity cannot emit local prompt additions, negative lists, retry prose,
or keyword-based activation.
Provider execution is blocked when the canonical prompt or its hash is absent,
stale, or mismatched.
Human Realism preflight and independent natural-presence re-signing are
required whenever the shared plan activates Human Realism.
Provider and Local MCP/Codex Native paths receive the same canonical prompt
and reference hashes; Local MCP cannot re-plan or certify the result.
Stored pack views may exceed the per-job reference limit, but adaptive routing
selects a bounded, view-aware subset and records the exact IDs used.
An explicit age change preserves same-person geometry and is reviewed as a
prompt-owned transformation.
An uploaded second person cannot enter as a full style reference.
Style/scene references retain their allowed non-identity channels.
Pack candidates remain append-only and only active winners enter routing.
Root truth remains in every strict Professional Mode identity review.
Provider inputs and Reviewer evidence use the same admitted root/anchor IDs.
E-Commerce and Photography role semantics remain unchanged in both modes.
General remains scenario-neutral in both modes.
No public request or Brain schema gains asset-library internals.
```

## 15. Acceptance Criteria

The Professional Mode foundation is not ready to integrate until:

```text
1. Standard Mode regression passes with Professional Mode disabled and enabled
   in the same deployment.
2. A People Asset can build a three-candidate standard-front stage.
3. Only a passing front candidate can seed supplementary views.
4. Supplementary views are evaluated against both root truth and the selected
   front anchor.
5. The complete pack is rejected if any required view or cross-view identity
   gate fails.
6. Active packs are versioned, provenance-bound, and reversible.
7. Weak, failed, or superseded candidates cannot enter provider inputs.
8. Professional Mode prevents unwanted human identity pixels from other
   uploaded references.
9. A project can hold multiple People Assets, but each job binds one explicit
   selected asset and pack version.
10. The first-release pack activates only Face Identity; non-face dimensions
    remain unclaimed until a future module is explicitly approved.
11. The active capability plan is frozen before Professional Mode contributions
    enter generation, review, or retry.
12. Standard, E-Commerce, Photography, and future Video consumers can select
    the same asset contract without duplicating identity logic.
13. No production or Provider Gate claim is made solely from pack creation.
14. A Professional Mode job uses the same complete Remote Brain semantic
    profile, frozen activation plan, canonical prompt signing, and shared
    review/retry path as the current standard V3 forward path.
15. An incomplete semantic profile, missing activation intent, missing prompt
    signature/hash, or failed Human Realism sign-off blocks before Provider.
16. The Face Identity Module contains no local creative prompt, heuristic
    semantic classifier, private retry patch, or second reviewer/provider.
17. Future Standard Mode shared-capability upgrades can be adopted through a
    versioned adapter or produce a structured incompatibility block; they do
    not silently change Professional Mode asset semantics.
```

## 16. Non-Goals

This specification does not authorize:

```text
rewriting, renumbering, or globally superseding existing V3 documents
changing existing Standard Mode behavior
changing General Template semantics
changing E-Commerce or Photography deliverable contracts
building an A+ module or marketplace asset package
building a Video module
adding a second image provider or sidecar
adding a second reference registry, image store, or review/retry system
local face swap, face compositing, font/OCR, or pixel overlay
storing biometric embeddings
automatic professional-mode activation
silent fallback from Professional Mode to Standard Mode
```

## 17. Architectural Summary

```text
Standard Mode remains the current product.

Professional Mode is a separate opt-in contract.

Visual Asset Library is the Professional Mode mother boundary.

People Assets are the first child module.

Identity Anchor Packs are versioned, reviewed support containers. The first
release activates only a modular Face Identity component; body, hair, styling,
and other dimensions remain future additive components.

Existing V3 foundation modules remain the implementation machinery.

The mode boundary controls whether those assets are consulted; it does not
rewrite the existing foundation contracts.

Future Standard Mode improvements may improve the shared foundation used by
Professional Mode, but only through an explicit, versioned compatibility
adapter and regression review. Standard Mode UI, defaults, heuristics, and
scenario semantics never become implicit Professional Mode behavior.
```
